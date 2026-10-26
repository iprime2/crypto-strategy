#!/usr/bin/env python3
"""Download Binance USDT-M perp 5m monthly klines 2020-01..2023-12 for the nine coins.

Public data only (data.binance.vision). For each month in the S3 listing:
  download <SYM>USDT-5m-YYYY-MM.zip and its .CHECKSUM into its own fresh temp folder,
  verify sha256, extract the single CSV member (bytes only, no path from the archive is used),
  write it to universe/klines5m/binance-<SYM>USDT-5m-YYYY-MM.csv.
If the monthly file is missing from the listing (but daily files exist for that month) or the
download / checksum fails, fall back to the daily zips for that month and concatenate them.
Existing files (2024-01..2026-09) are never touched: the script refuses to overwrite.
Writes a JSON log to research3/data/download_log.json.

Usage: python3 -I download_klines.py <scratchpad_root>
"""
import hashlib
import io
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
OUT = os.path.join(ROOT, "universe", "klines5m")
WORK = os.path.join(ROOT, "research3", "data")
TMP = os.path.join(WORK, "tmp_dl")
SYMS = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
MONTHS = [f"{y}-{m:02d}" for y in range(2020, 2024) for m in range(1, 13)]
BASE = "https://data.binance.vision/"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def curl(url, dest=None):
    """Return bytes (dest None) or write to dest. Raises on HTTP error."""
    args = ["curl", "-sS", "--fail", "--retry", "4", "--retry-delay", "2", "--max-time", "120", url]
    if dest:
        args[1:1] = ["-o", dest]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode} {url}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def s3_keys(prefix):
    keys, marker = [], ""
    while True:
        q = {"delimiter": "/", "prefix": prefix}
        if marker:
            q["marker"] = marker
        t = curl(S3 + "?" + urllib.parse.urlencode(q)).decode()
        ks = re.findall(r"<Key>([^<]*)</Key>", t)
        keys += ks
        if "<IsTruncated>true" in t and ks:
            marker = ks[-1]
        else:
            return keys


def fetch_zip_csv(rel_zip, tag):
    """Download zip + checksum into a fresh temp dir; return (csv_bytes, info)."""
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
    try:
        ck = curl(BASE + rel_zip + ".CHECKSUM").decode().split()
        info["checksum_expected"] = ck[0]
        info["checksum_ok"] = (ck[0].lower() == h)
    except RuntimeError as e:
        info["checksum_expected"] = None
        info["checksum_ok"] = None
        info["checksum_error"] = str(e)
    if info["checksum_ok"] is False:
        shutil.rmtree(d)
        raise RuntimeError(f"checksum mismatch {rel_zip}")
    with zipfile.ZipFile(zpath) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        info["members"] = [m.filename for m in members]
        want = name[:-4] + ".csv"
        cands = [m for m in members if os.path.basename(m.filename) == want]
        if len(cands) != 1:
            shutil.rmtree(d)
            raise RuntimeError(f"unexpected zip members {info['members']} in {rel_zip}")
        data = z.read(cands[0])
    shutil.rmtree(d)
    return data, info


def has_header(b):
    first = b.split(b"\n", 1)[0]
    return not first[:1].isdigit()


def write_new(path, data):
    if os.path.exists(path):
        raise RuntimeError(f"refusing to overwrite existing {path}")
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def do_month(sym, month, monthly_set, daily_by_month):
    pair = f"{sym}USDT"
    out = os.path.join(OUT, f"binance-{pair}-5m-{month}.csv")
    rec = {"sym": pair, "month": month, "out": out}
    if os.path.exists(out):
        rec["status"] = "exists_skipped"
        return rec
    zname = f"{pair}-5m-{month}.zip"
    if zname in monthly_set:
        try:
            data, info = fetch_zip_csv(f"data/futures/um/monthly/klines/{pair}/5m/{zname}", f"{pair}-{month}")
            rec.update(info)
            rec["header"] = has_header(data)
            rec["source"] = "monthly"
            write_new(out, data)
            rec["status"] = "ok"
            return rec
        except Exception as e:  # fall through to daily
            rec["monthly_error"] = str(e)
    else:
        rec["monthly_error"] = "not in S3 listing"
    days = sorted(daily_by_month.get(month, []))
    if not days:
        rec["status"] = "missing_no_daily"
        return rec
    parts, dinfo, header_line = [], [], None
    for dz in days:
        try:
            data, info = fetch_zip_csv(f"data/futures/um/daily/klines/{pair}/5m/{dz}", f"{pair}-{dz[:-4]}")
        except Exception as e:
            dinfo.append({"zip": dz, "error": str(e)})
            continue
        info["header"] = has_header(data)
        dinfo.append(info)
        lines = data.splitlines(keepends=True)
        if info["header"]:
            if header_line is None:
                header_line = lines[0]
            lines = lines[1:]
        if lines and not lines[-1].endswith(b"\n"):
            lines[-1] += b"\n"
        parts.append(b"".join(lines))
    body = (header_line or b"") + b"".join(parts)
    rec["daily"] = dinfo
    rec["source"] = "daily_concat"
    rec["header"] = header_line is not None
    write_new(out, body)
    rec["status"] = "patched_from_daily"
    return rec


def main():
    os.makedirs(TMP, exist_ok=True)
    log = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "records": [], "listing": {}}
    jobs = []
    for sym in SYMS:
        pair = f"{sym}USDT"
        mk = s3_keys(f"data/futures/um/monthly/klines/{pair}/5m/")
        monthly = {k.split("/")[-1] for k in mk if k.endswith(".zip")}
        log["listing"][pair] = sorted(re.search(r"(\d{4}-\d{2})\.zip", z).group(1) for z in monthly)
        for month in MONTHS:
            daily = {}
            if f"{pair}-5m-{month}.zip" not in monthly:
                dk = s3_keys(f"data/futures/um/daily/klines/{pair}/5m/{pair}-5m-{month}-")
                daily = {month: [k.split("/")[-1] for k in dk if k.endswith(".zip")]}
            jobs.append((sym, month, monthly, daily))
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(do_month, *j) for j in jobs]
        for f in futs:
            r = f.result()
            log["records"].append(r)
            print(r["sym"], r["month"], r["status"], r.get("source", ""), r.get("checksum_ok", ""),
                  r.get("monthly_error", ""), flush=True)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(WORK, "download_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    try:
        os.rmdir(TMP)
    except OSError:
        pass


if __name__ == "__main__":
    main()
