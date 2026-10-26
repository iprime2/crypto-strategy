#!/usr/bin/env python3
"""Check every gap found by audit_spot.py (pre) against Binance's daily spot 5m files, and patch where they hold bars.

For each gap (consecutive open times > 5 min apart) of each pair, every UTC day the missing interval touches is looked up
in the S3 listing data/spot/daily/klines/<PAIR>/5m/<PAIR>-5m-YYYY-MM-; if the daily zip exists it goes, with its
.CHECKSUM, into its own fresh temp folder, the sha256 is verified, its single CSV member is unzipped there and read.
Per day it records: daily rows, monthly rows of that day, monthly rows not byte-identical in the daily file, daily rows
not in the monthly file, and daily rows whose open time falls inside the gap.
Patch rule (mode "apply"): daily rows inside a gap are inserted verbatim into the monthly CSV (sorted by open time) only if
every monthly row of that day has a daily row with the same open time and identical open, high, low, close, volume,
quote volume, trade count and taker-buy volumes (fields 1-6, 8-11). close_time and the unused 12th "ignore" field are
not required to match (Binance's 2017 monthly files carry non-zero "ignore" values the daily files do not, and a bar
cut by a maintenance start can carry a different close_time); every such difference is counted in the log.
Off-grid repair: for every run of consecutive days whose monthly rows include open times off the 5 m grid (Binance's
2018-02-09/10 restart printed bars at hh:mm:14.789), the daily files of those days are fetched the same way; if they
are entirely on the grid and their totals over the run (base volume, quote volume, trade count, taker-buy volumes),
max high, min low, first open and last close equal the monthly rows', the monthly rows of those days are replaced by
the daily rows (the same trades re-bucketed onto the 5 m grid). Every comparison is logged.
The original monthly CSV is copied to
data_ot/replaced_monthly/ first; sha256 before / after are logged. Mode "check" writes the log and changes nothing.
Log: data_ot/patch_log.json.

Usage: python3 -I patch_spot_gaps.py <scratchpad_root> check|apply
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import zipfile
from collections import defaultdict

import pandas as pd

ROOT, MODE = sys.argv[1], sys.argv[2]
assert MODE in ("check", "apply")
KD = os.path.join(ROOT, "universe", "spot5m")
WORK = os.path.join(ROOT, "research3", "p2", "data_ot")
TMP = os.path.join(WORK, "tmp_patch")
KEEP = os.path.join(WORK, "replaced_monthly")
BASE = "https://data.binance.vision/"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DAY = 86_400_000
PAIRS = [f"{s}USDT" for s in ["BTC", "ETH", "BNB", "LTC", "NEO", "XRP", "ADA", "EOS", "XLM", "TRX", "ETC", "LINK", "DOGE"]]


def curl(url, dest=None):
    args = ["curl", "-sS", "--fail", "--retry", "6", "--retry-all-errors", "--retry-delay", "3", "--max-time", "120", url]
    if dest:
        args[1:1] = ["-o", dest]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode} {url}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


_listing = {}


def daily_listing(pair, month):
    k = (pair, month)
    if k not in _listing:
        q = urllib.parse.urlencode({"delimiter": "/", "prefix": f"data/spot/daily/klines/{pair}/5m/{pair}-5m-{month}-"})
        t = curl(S3 + "?" + q).decode()
        assert "<IsTruncated>true" not in t
        _listing[k] = set(re.findall(r"<Key>([^<]*)</Key>", t))
    return _listing[k]


def fetch_daily(pair, d):
    name = f"{pair}-5m-{d}.zip"
    key = f"data/spot/daily/klines/{pair}/5m/{name}"
    keys = daily_listing(pair, d[:7])
    info = {"zip": key, "in_listing": key in keys, "checksum_in_listing": (key + ".CHECKSUM") in keys}
    if not info["in_listing"]:
        return None, info
    tdir = os.path.join(TMP, f"{pair}-{d}")
    if os.path.exists(tdir):
        shutil.rmtree(tdir)
    os.makedirs(tdir)
    zp = os.path.join(tdir, name)
    curl(BASE + key, zp)
    h = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    ck = curl(BASE + key + ".CHECKSUM").decode().split()[0].lower()
    info.update(sha256=h, checksum_ok=(ck == h))
    if ck != h:
        shutil.rmtree(tdir)
        raise RuntimeError(f"checksum mismatch {key}")
    with zipfile.ZipFile(zp) as z:
        ms = [m for m in z.infolist() if not m.is_dir()]
        cand = [m for m in ms if os.path.basename(m.filename) == name[:-4] + ".csv"]
        assert len(cand) == 1 and len(ms) == 1, [m.filename for m in ms]
        data = z.read(cand[0])
    with open(os.path.join(tdir, name[:-4] + ".csv"), "wb") as f:  # unzipped into its own temp folder
        f.write(data)
    data = open(os.path.join(tdir, name[:-4] + ".csv"), "rb").read()
    shutil.rmtree(tdir)
    ls = [x.strip() for x in data.splitlines() if x.strip()]
    info["header"] = bool(ls) and not ls[0][:1].isdigit()
    rows = ls[1:] if info["header"] else ls
    return rows, info


def key_of(line):
    f = line.split(b",")
    return tuple(f[0:6] + f[7:11])


def ot_of(line):
    v = int(line.split(b",", 1)[0])
    return v // 1000 if v > 1e14 else v


_cache = {}


def fetch_cached(pair, d):
    if (pair, d) not in _cache:
        _cache[(pair, d)] = fetch_daily(pair, d)
    return _cache[(pair, d)]


def totals(lines):
    f = [x.split(b",") for x in lines]
    return {"rows": len(f),
            "volume": round(sum(float(r[5]) for r in f), 6), "quote_volume": round(sum(float(r[7]) for r in f), 4),
            "trades": sum(int(r[8]) for r in f), "taker_buy_volume": round(sum(float(r[9]) for r in f), 6),
            "taker_buy_quote_volume": round(sum(float(r[10]) for r in f), 4),
            "max_high": max(float(r[2]) for r in f), "min_low": min(float(r[3]) for r in f),
            "first_open": float(f[0][1]), "last_close": float(f[-1][4])}


def off_grid_runs(pair):
    """[(file, [day_ms, ...]), ...]: runs of consecutive days with off-grid open times in the monthly files."""
    days = set()
    for fn in sorted(os.listdir(KD)):
        if fn.startswith(f"binance-spot-{pair}-5m-") and fn.endswith(".csv"):
            for x in open(os.path.join(KD, fn), "rb").read().splitlines():
                if x[:1].isdigit() and ot_of(x) % 300_000:
                    days.add(ot_of(x) // DAY)
    runs, cur = [], []
    for dd in sorted(days):
        if cur and dd != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(dd)
    if cur:
        runs.append(cur)
    return runs


def main():
    os.makedirs(TMP, exist_ok=True)
    g = pd.read_csv(os.path.join(WORK, "pre", "gaps_all.csv"))
    # (pair, day) -> list of gap intervals [first_missing_ms, next_bar_ms)
    need = defaultdict(list)
    for r in g.itertuples():
        a, b = int(r.first_missing_ms), int(r.next_bar_ms)
        d0, d1 = a // DAY, (b - 1) // DAY
        for dd in range(d0, d1 + 1):
            need[(r.coin, dd)].append((a, b, float(r.missing_minutes)))
    log = {"mode": MODE, "days": [], "patched_files": []}
    adds = defaultdict(list)  # monthly file -> rows to insert
    for (pair, dd) in sorted(need):
        d = pd.Timestamp(dd * DAY, unit="ms", tz="UTC").strftime("%Y-%m-%d")
        fn = os.path.join(KD, f"binance-spot-{pair}-5m-{d[:7]}.csv")
        mlines = [x.strip() for x in open(fn, "rb").read().splitlines() if x.strip()]
        mday = [x for x in mlines if x[:1].isdigit() and dd * DAY <= ot_of(x) < (dd + 1) * DAY]
        rows, info = fetch_cached(pair, d)
        rec = {"pair": pair, "day": d, "gaps": [[pd.Timestamp(a, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
                                                 pd.Timestamp(b, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"), m]
                                                for a, b, m in need[(pair, dd)]],
               "monthly_rows_day": len(mday), **info}
        if rows is None:
            rec["result"] = "no daily file in listing"
            log["days"].append(rec)
            print(pair, d, rec["result"], flush=True)
            continue
        dset, mset = set(rows), set(mday)
        dkey, mkey = {key_of(x) for x in rows}, {key_of(x) for x in mday}
        mot = {ot_of(x) for x in mday}
        ingap = sorted({x for x in rows if any(a <= ot_of(x) < b for a, b, _ in need[(pair, dd)])}, key=ot_of)
        rec.update(daily_rows=len(rows), monthly_rows_not_byte_identical_in_daily=len(mset - dset),
                   monthly_rows_key_fields_not_in_daily=len(mkey - dkey),
                   daily_rows_not_byte_identical_in_monthly=len(dset - mset),
                   daily_open_times_not_in_monthly=len({ot_of(x) for x in rows} - mot),
                   monthly_open_times_not_in_daily=len(mot - {ot_of(x) for x in rows}),
                   daily_rows_in_gap=len(ingap))
        if mset - dset:
            f = lambda x: x.split(b",")
            dby = {ot_of(x): x for x in rows}
            rec["field_differences"] = sorted({"close_time" if f(x)[6] != f(dby[ot_of(x)])[6] else "ignore"
                                               for x in mset - dset if ot_of(x) in dby and key_of(x) == key_of(dby[ot_of(x)])})
        new = [x for x in ingap if ot_of(x) not in mot]
        if not new:
            rec["result"] = "daily file has no bar inside the gap (same hole): real outage, nothing to patch"
        elif mkey - dkey:
            rec["result"] = "daily has bars in the gap but monthly price/volume fields differ from daily: NOT patched"
        else:
            rec["result"] = f"patch: {len(new)} bars from the daily file"
            rec["added_open_times"] = [pd.Timestamp(ot_of(x), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S") for x in new]
            adds[fn] += new
        log["days"].append(rec)
        print(pair, d, rec["result"], rec["daily_rows"], rec["monthly_rows_day"], rec["monthly_rows_not_byte_identical_in_daily"],
              rec["monthly_rows_key_fields_not_in_daily"], rec["daily_open_times_not_in_monthly"],
              rec["monthly_open_times_not_in_daily"], rec.get("field_differences", ""), flush=True)
    # off-grid repair
    repl = defaultdict(dict)  # monthly file -> {day_ms: daily rows}
    log["off_grid_runs"] = []
    for sym in sorted({k[0] for k in need} | set(PAIRS)):
        for run in off_grid_runs(sym):
            ds = [pd.Timestamp(dd * DAY, unit="ms", tz="UTC").strftime("%Y-%m-%d") for dd in run]
            mrows, drows, infos, ok = [], [], [], True
            for dd, d in zip(run, ds):
                fn = os.path.join(KD, f"binance-spot-{sym}-5m-{d[:7]}.csv")
                ml = [x.strip() for x in open(fn, "rb").read().splitlines() if x[:1].isdigit()]
                md = sorted([x for x in ml if dd * DAY <= ot_of(x) < (dd + 1) * DAY], key=ot_of)
                rows, info = fetch_cached(sym, d)
                info = dict(info, day=d, monthly_rows=len(md), monthly_off_grid=sum(1 for x in md if ot_of(x) % 300_000))
                if rows is None:
                    ok = False
                    infos.append(info)
                    continue
                rows = sorted(rows, key=ot_of)
                info.update(daily_rows=len(rows), daily_off_grid=sum(1 for x in rows if ot_of(x) % 300_000),
                            daily_out_of_day=sum(1 for x in rows if not (dd * DAY <= ot_of(x) < (dd + 1) * DAY)))
                ok = ok and info["daily_off_grid"] == 0 and info["daily_out_of_day"] == 0
                infos.append(info)
                mrows += md
                drows += rows
            tm, td = (totals(mrows), totals(drows)) if ok else ({}, {})
            same = ok and all(tm[k] == td[k] for k in tm if k != "rows")
            rec = {"pair": sym, "days": ds, "per_day": infos, "monthly_totals": tm, "daily_totals": td,
                   "totals_equal": bool(same)}
            if same:
                rec["result"] = "replace: monthly rows of these days -> daily on-grid rows (same trades re-bucketed)"
                for dd, d in zip(run, ds):
                    fn = os.path.join(KD, f"binance-spot-{sym}-5m-{d[:7]}.csv")
                    rows, _ = fetch_cached(sym, d)
                    repl[fn][dd] = sorted(rows, key=ot_of)
            else:
                rec["result"] = "NOT replaced (daily missing, off grid, or totals differ)"
            log["off_grid_runs"].append(rec)
            print(sym, ds, rec["result"], json.dumps(tm), json.dumps(td), flush=True)
    if MODE == "apply":
        os.makedirs(KEEP, exist_ok=True)
        for fn in sorted(set(adds) | set(repl)):
            new = adds.get(fn, [])
            rdays = repl.get(fn, {})
            orig = open(fn, "rb").read()
            ol = [x for x in orig.splitlines() if x.strip()]
            hdr = [x for x in ol if not x[:1].isdigit()]
            body0 = [x.strip() for x in ol if x[:1].isdigit()]
            body = [x for x in body0 if ot_of(x) // DAY not in rdays]
            rrows = [x for v in rdays.values() for x in v]
            assert not ({ot_of(x) for x in body} & {ot_of(x) for x in new})
            assert not ({ot_of(x) for x in rrows} & {ot_of(x) for x in new})
            allr = sorted(body + new + rrows, key=ot_of)
            ts = [ot_of(x) for x in allr]
            assert len(set(ts)) == len(ts), f"duplicate open times after patch in {fn}"
            out = b"\n".join(hdr + allr) + b"\n"
            shutil.copy2(fn, os.path.join(KEEP, os.path.basename(fn)))
            with open(fn + ".part", "wb") as f:
                f.write(out)
            os.replace(fn + ".part", fn)
            log["patched_files"].append({"file": os.path.basename(fn), "rows_before": len(body0), "rows_added_in_gaps": len(new),
                                         "days_replaced": [pd.Timestamp(dd * DAY, unit="ms", tz="UTC").strftime("%Y-%m-%d") for dd in sorted(rdays)],
                                         "rows_removed_by_day_replacement": len(body0) - len(body),
                                         "rows_inserted_by_day_replacement": len(rrows),
                                         "rows_after": len(allr), "sha256_before": hashlib.sha256(orig).hexdigest(),
                                         "sha256_after": hashlib.sha256(out).hexdigest()})
    shutil.rmtree(TMP, ignore_errors=True)
    with open(os.path.join(WORK, "patch_log.json" if MODE == "apply" else "patch_check_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    n_new = sum(len(v) for v in adds.values())
    print("days checked", len(log["days"]), "files with gap bars to add", len(adds), "bars to add", n_new,
          "off-grid runs replaced", sum(r["totals_equal"] for r in log["off_grid_runs"]))


if __name__ == "__main__":
    main()
