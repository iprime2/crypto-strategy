#!/usr/bin/env python3
"""Fetch Binance USDT-M perp 1h klines (monthly zips, plus daily zips for the current month) into OUT/<SYM>-1h.csv."""
import concurrent.futures as cf, csv, datetime as dt, io, os, sys, urllib.request, zipfile
OUT = sys.argv[1]; COINS = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
BASE = "https://data.binance.vision/data/futures/um"
END = dt.date(2026, 10, 12)
def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cs-research/0.1"}), timeout=60).read()
    except Exception as e:
        return None
def rows_from_zip(b):
    if not b: return []
    z = zipfile.ZipFile(io.BytesIO(b)); out = []
    for n in z.namelist():
        for r in csv.reader(io.TextIOWrapper(z.open(n), encoding="utf-8")):
            if not r or not r[0].isdigit(): continue
            out.append(r[:7])  # open_time, o, h, l, c, vol, close_time
    return out
def fetch(coin):
    sym = coin + "USDT"; rows = []
    y, m = 2019, 9
    while (y, m) <= (2026, 9):
        rows += rows_from_zip(get(f"{BASE}/monthly/klines/{sym}/1h/{sym}-1h-{y}-{m:02d}.zip"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    d = dt.date(2026, 10, 1)
    while d <= END:
        rows += rows_from_zip(get(f"{BASE}/daily/klines/{sym}/1h/{sym}-1h-{d}.zip")); d += dt.timedelta(days=1)
    rows.sort(key=lambda r: int(r[0]))
    with open(os.path.join(OUT, f"{sym}-1h.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms"]); w.writerows(rows)
    return sym, len(rows)
with cf.ThreadPoolExecutor(6) as ex:
    for sym, n in ex.map(fetch, COINS): print(sym, n, "rows", flush=True)
