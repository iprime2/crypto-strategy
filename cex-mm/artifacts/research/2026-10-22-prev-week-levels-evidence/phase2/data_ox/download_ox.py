#!/usr/bin/env python3
"""Phase 2 panel OX: download Binance USDT-M perp 5 m monthly klines 2021-12..2026-09 for the 15 selected coins.

Public data only (data.binance.vision). Coins come from selection_meta.json ("selected", written by select_ox.py before
this script existed). For each coin:
  - save the S3 listings of monthly and daily 5 m keys (listings/<SYM>_{monthly,daily}.txt);
  - for each month in the window that is in the monthly listing: download <SYM>-5m-YYYY-MM.zip and its .CHECKSUM into a
    fresh temp folder, verify sha256, read only the single expected CSV member, write its bytes unchanged to
    universe/ox5m/binance-<SYM>-5m-YYYY-MM.csv;
  - if a month is not in the monthly listing (or its download / checksum fails) but daily files exist for it, rebuild it
    from the daily zips (each checksum-verified), concatenated in date order, header rows stripped except the first
    (status patched_from_daily, logged);
  - otherwise record missing_no_daily (pre-listing or post-delisting month).
Refuses to overwrite an existing CSV. Writes download_log.json next to this script.

Usage: python3 -I download_ox.py
"""
import hashlib, json, os, re, shutil, subprocess, sys, time, urllib.parse, zipfile
from concurrent.futures import ThreadPoolExecutor

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
WORK = f"{SP}/research3/p2/data_ox"
OUT = f"{SP}/universe/ox5m"
TMP = f"{OUT}/_tmp"
LIST = f"{WORK}/listings"
BASE = "https://data.binance.vision/"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
MONTHS = [f"{y}-{m:02d}" for y in range(2021, 2027) for m in range(1, 13) if (2021, 12) <= (y, m) <= (2026, 9)]


def curl(url, dest=None):
    args = ["curl", "-sS", "--fail", "--retry", "5", "--retry-delay", "2", "--retry-all-errors", "--max-time", "180", url]
    if dest:
        args[1:1] = ["-o", dest]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode} {url}: {r.stderr.decode(errors='replace').strip()[:300]}")
    return r.stdout


def s3_keys(prefix):
    keys, marker = [], ""
    while True:
        q = {"prefix": prefix}
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
    d = os.path.join(TMP, tag)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    name = rel_zip.split("/")[-1]
    zpath = os.path.join(d, name)
    try:
        curl(BASE + rel_zip, zpath)
        info = {"zip": rel_zip, "zip_bytes": os.path.getsize(zpath)}
        h = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
        info["sha256"] = h
        try:
            ck = curl(BASE + rel_zip + ".CHECKSUM").decode().split()
            info["checksum_expected"] = ck[0]
            info["checksum_ok"] = ck[0].lower() == h
        except RuntimeError as e:
            info["checksum_expected"], info["checksum_ok"], info["checksum_error"] = None, None, str(e)
        if info["checksum_ok"] is not True:
            raise RuntimeError(f"checksum not verified for {rel_zip}: {info.get('checksum_error', 'mismatch')}")
        with zipfile.ZipFile(zpath) as z:
            members = [m for m in z.infolist() if not m.is_dir()]
            info["members"] = [m.filename for m in members]
            want = name[:-4] + ".csv"
            cands = [m for m in members if os.path.basename(m.filename) == want]
            if len(cands) != 1:
                raise RuntimeError(f"unexpected zip members {info['members']} in {rel_zip}")
            data = z.read(cands[0])
        info["csv_sha256"] = hashlib.sha256(data).hexdigest()
        return data, info
    finally:
        shutil.rmtree(d, ignore_errors=True)


def has_header(b):
    return not b[:1].isdigit()


def write_new(path, data):
    if os.path.exists(path):
        raise RuntimeError(f"refusing to overwrite existing {path}")
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def concat_daily(sym, days, tagp):
    parts, dinfo, header_line = [], [], None
    for dz in days:
        try:
            data, info = fetch_zip_csv(f"data/futures/um/daily/klines/{sym}/5m/{dz}", f"{tagp}-{dz[:-4]}")
        except Exception as e:
            dinfo.append({"zip": dz, "error": str(e)})
            continue
        info["header"] = has_header(data)
        lines = data.splitlines(keepends=True)
        if info["header"]:
            if header_line is None:
                header_line = lines[0] if lines[0].endswith(b"\n") else lines[0] + b"\n"
            lines = lines[1:]
        if lines and not lines[-1].endswith(b"\n"):
            lines[-1] += b"\n"
        info["rows"] = len(lines)
        dinfo.append(info)
        parts.append(b"".join(lines))
    return (header_line or b"") + b"".join(parts), dinfo, header_line is not None


def do_month(sym, month, monthly_set, daily_days):
    out = os.path.join(OUT, f"binance-{sym}-5m-{month}.csv")
    rec = {"sym": sym, "month": month, "out": out}
    if os.path.exists(out):
        rec["status"] = "exists_skipped"
        return rec
    zname = f"{sym}-5m-{month}.zip"
    if zname in monthly_set:
        try:
            data, info = fetch_zip_csv(f"data/futures/um/monthly/klines/{sym}/5m/{zname}", f"{sym}-{month}")
            rec.update(info)
            rec["header"] = has_header(data)
            rec["source"] = "monthly"
            write_new(out, data)
            rec["status"] = "ok"
            return rec
        except Exception as e:
            rec["monthly_error"] = str(e)
    else:
        rec["monthly_error"] = "not in S3 listing"
    days = sorted(d for d in daily_days if d.startswith(f"{sym}-5m-{month}-"))
    rec["daily_files_in_listing"] = len(days)
    if not days:
        rec["status"] = "missing_no_daily"
        return rec
    body, dinfo, hdr = concat_daily(sym, days, f"{sym}-{month}")
    rec["daily"] = dinfo
    rec["source"] = "daily_concat"
    rec["header"] = hdr
    if any("error" in x for x in dinfo):
        rec["daily_errors"] = [x for x in dinfo if "error" in x]
    write_new(out, body)
    rec["status"] = "patched_from_daily"
    return rec


def main():
    sel = json.load(open(f"{WORK}/selection_meta.json"))["selected"]
    assert len(sel) == 15, sel
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(LIST, exist_ok=True)
    log = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "coins": sel, "months": [MONTHS[0], MONTHS[-1]],
           "listing": {}, "records": []}
    jobs = []
    for sym in sel:
        mk = s3_keys(f"data/futures/um/monthly/klines/{sym}/5m/")
        dk = s3_keys(f"data/futures/um/daily/klines/{sym}/5m/")
        open(f"{LIST}/{sym}_monthly.txt", "w").write("\n".join(mk) + "\n")
        open(f"{LIST}/{sym}_daily.txt", "w").write("\n".join(dk) + "\n")
        monthly = {k.split("/")[-1] for k in mk if k.endswith(".zip")}
        daily = sorted(k.split("/")[-1] for k in dk if k.endswith(".zip"))
        mck = {k.split("/")[-1][:-9] for k in mk if k.endswith(".zip.CHECKSUM")}
        mm = sorted(re.search(r"(\d{4}-\d{2})\.zip$", z).group(1) for z in monthly)
        dd = sorted(re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", z).group(1) for z in daily)
        log["listing"][sym] = {"monthly_first": mm[0] if mm else None, "monthly_last": mm[-1] if mm else None,
                               "monthly_n": len(mm), "monthly_without_checksum": sorted(monthly - mck),
                               "daily_first": dd[0] if dd else None, "daily_last": dd[-1] if dd else None, "daily_n": len(dd)}
        print(sym, log["listing"][sym], flush=True)
        for month in MONTHS:
            jobs.append((sym, month, monthly, daily))
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(lambda j: do_month(*j), jobs):
            log["records"].append(r)
            if r["status"] != "ok":
                print(r["sym"], r["month"], r["status"], r.get("monthly_error", ""), flush=True)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(log, open(f"{WORK}/download_log.json", "w"), indent=1)
    from collections import Counter
    print(Counter(r["status"] for r in log["records"]))
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
