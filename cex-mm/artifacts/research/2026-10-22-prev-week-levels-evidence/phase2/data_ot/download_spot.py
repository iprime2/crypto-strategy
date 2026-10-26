#!/usr/bin/env python3
"""Download Binance SPOT 5m monthly klines for the Phase 2 OT panel (13 USDT pairs), first month .. 2020-04.

Public data only (data.binance.vision). For each pair:
  * the S3 listing data/spot/monthly/klines/<SYM>USDT/5m/ is fetched (saved under data_ot/listings/) and decides
    which months exist; months from the pair's first listed month through 2020-04 are taken;
  * each <SYM>USDT-5m-YYYY-MM.zip and its .CHECKSUM go into their own fresh temp folder, the sha256 is compared,
    the single expected CSV member is unzipped into that temp folder (bytes only, no path from the archive is used),
    then moved to universe/spot5m/binance-spot-<SYM>USDT-5m-YYYY-MM.csv; the temp folder is removed.
  * a month missing from the monthly listing between the first month and 2020-04 is reported; it is NOT silently
    filled here (patch_spot_gaps.py rebuilds such months from daily files and logs it).
The script refuses to overwrite an existing CSV. Log: data_ot/download_log.json.

Usage: python3 -I download_spot.py <scratchpad_root>
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = sys.argv[1]
OUT = os.path.join(ROOT, "universe", "spot5m")
WORK = os.path.join(ROOT, "research3", "p2", "data_ot")
LST = os.path.join(WORK, "listings")
TMP = os.path.join(WORK, "tmp_dl")
SYMS = ["BTC", "ETH", "BNB", "LTC", "NEO", "XRP", "ADA", "EOS", "XLM", "TRX", "ETC", "LINK", "DOGE"]
LAST_MONTH = "2020-04"
BASE = "https://data.binance.vision/"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def curl(url, dest=None):
    args = ["curl", "-sS", "--fail", "--retry", "4", "--retry-delay", "2", "--max-time", "180", url]
    if dest:
        args[1:1] = ["-o", dest]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode} {url}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def s3_keys(prefix, save_as=None):
    keys, marker, pages = [], "", []
    while True:
        q = {"delimiter": "/", "prefix": prefix}
        if marker:
            q["marker"] = marker
        t = curl(S3 + "?" + urllib.parse.urlencode(q)).decode()
        pages.append(t)
        ks = re.findall(r"<Key>([^<]*)</Key>", t)
        keys += ks
        if "<IsTruncated>true" in t and ks:
            marker = ks[-1]
        else:
            break
    if save_as:
        with open(save_as, "w") as f:
            f.write("\n<!-- page break -->\n".join(pages))
    return keys


def months_between(a, b):
    y, m = map(int, a.split("-"))
    out = []
    while f"{y}-{m:02d}" <= b:
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def fetch_zip_csv(rel_zip, tag, dest):
    """zip + .CHECKSUM into a fresh temp dir, verify, unzip the one CSV member there, move it to dest."""
    d = os.path.join(TMP, tag)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    name = rel_zip.split("/")[-1]
    zpath = os.path.join(d, name)
    curl(BASE + rel_zip, zpath)
    info = {"zip": rel_zip, "zip_bytes": os.path.getsize(zpath)}
    h = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    info["sha256"] = h
    ck = curl(BASE + rel_zip + ".CHECKSUM").decode().split()
    info["checksum_expected"] = ck[0].lower()
    info["checksum_ok"] = ck[0].lower() == h
    if not info["checksum_ok"]:
        shutil.rmtree(d)
        raise RuntimeError(f"checksum mismatch {rel_zip}")
    want = name[:-4] + ".csv"
    with zipfile.ZipFile(zpath) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        info["members"] = [m.filename for m in members]
        cands = [m for m in members if os.path.basename(m.filename) == want]
        if len(cands) != 1 or len(members) != 1:
            shutil.rmtree(d)
            raise RuntimeError(f"unexpected zip members {info['members']} in {rel_zip}")
        data = z.read(cands[0])
    csv_tmp = os.path.join(d, want)  # unzipped into its own temp folder
    with open(csv_tmp, "wb") as f:
        f.write(data)
    info["csv_bytes"] = len(data)
    info["csv_sha256"] = hashlib.sha256(data).hexdigest()
    info["header"] = not data[:1].isdigit()
    if os.path.exists(dest):
        shutil.rmtree(d)
        raise RuntimeError(f"refusing to overwrite existing {dest}")
    shutil.move(csv_tmp, dest + ".part")
    os.replace(dest + ".part", dest)
    shutil.rmtree(d)
    return info


def do_month(pair, month):
    out = os.path.join(OUT, f"binance-spot-{pair}-5m-{month}.csv")
    rec = {"pair": pair, "month": month, "out": out}
    if os.path.exists(out):
        rec["status"] = "exists_skipped"
        return rec
    try:
        rec.update(fetch_zip_csv(f"data/spot/monthly/klines/{pair}/5m/{pair}-5m-{month}.zip", f"{pair}-{month}", out))
        rec["status"] = "ok"
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = str(e)
    return rec


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LST, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    log = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "listing": {}, "missing_months": {},
           "records": []}
    jobs = []
    for sym in SYMS:
        pair = f"{sym}USDT"
        keys = s3_keys(f"data/spot/monthly/klines/{pair}/5m/", os.path.join(LST, f"{pair}_monthly.xml"))
        zips = sorted(k.split("/")[-1] for k in keys if k.endswith(".zip"))
        cks = {k.split("/")[-1][:-9] for k in keys if k.endswith(".zip.CHECKSUM")}
        months = sorted(re.search(r"-5m-(\d{4}-\d{2})\.zip$", z).group(1) for z in zips)
        first = months[0]
        want = months_between(first, LAST_MONTH)
        have = set(months)
        log["listing"][pair] = {"first_month": first, "last_month": months[-1], "n_months_listed": len(months),
                                "months_without_checksum": sorted(z for z in zips if z not in cks)}
        log["missing_months"][pair] = [m for m in want if m not in have]
        for m in want:
            if m in have:
                jobs.append((pair, m))
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(lambda j: do_month(*j), jobs):
            log["records"].append(r)
            print(r["pair"], r["month"], r["status"], r.get("checksum_ok", ""), r.get("header", ""),
                  r.get("error", ""), flush=True)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(WORK, "download_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    shutil.rmtree(TMP, ignore_errors=True)
    print(json.dumps({"listing": log["listing"], "missing_months": log["missing_months"]}, indent=1))


if __name__ == "__main__":
    main()
