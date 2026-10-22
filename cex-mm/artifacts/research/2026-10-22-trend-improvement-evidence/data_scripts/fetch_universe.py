#!/usr/bin/env python3
"""Fetch Binance USDT-M daily klines + funding for every Delta India USD perp underlying that Binance also lists.
Probes data.binance.vision month by month (404 = not listed that month). Writes the repo's cache file format into universe/cache/."""
import concurrent.futures as cf, io, json, os, sys, urllib.request, zipfile, datetime as dt
SP = os.path.dirname(os.path.abspath(__file__)); CACHE = f"{SP}/cache"
UA = {"User-Agent": "cex-mm-trend/0.1"}
perps = json.load(open(f"{SP}/delta_perps.json"))
have = set(fn.split("-")[1][:-4] for d in (f"{SP}/../trend-cache", f"{SP}/../av_cache") for fn in os.listdir(d) if fn.startswith("binance-"))
unders = [p["underlying"] for p in perps if p["underlying"] not in have]
months = []
y, m = 2019, 9
while (y, m) <= (2026, 9):
    months.append(f"{y}-{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()

def fetch(kind, u, ym):
    sym = u + "USDT"; path = f"{CACHE}/binance-{sym}-{kind}-{ym}.csv"
    if os.path.exists(path):
        return True
    sub = f"klines/{sym}/1d" if kind == "1d" else f"fundingRate/{sym}"
    try:
        z = get(f"https://data.binance.vision/data/futures/um/monthly/{sub}/{sym}-{kind}-{ym}.zip")
    except Exception:
        return False
    with zipfile.ZipFile(io.BytesIO(z)) as f:
        open(path, "wb").write(f.read(f.namelist()[0]))
    return True

def listed(u):
    """Which year the symbol first has a daily file: probe January files and the last month."""
    if not fetch("1d", u, "2026-09") and not fetch("1d", u, "2026-08"):
        return None  # not a Binance USDT-M perp now (or delisted); skip the dead ones
    return u

with cf.ThreadPoolExecutor(16) as ex:
    live = [u for u in ex.map(listed, unders) if u]
print(f"{len(unders)} candidates, {len(live)} with Binance USDT-M perps live in 2026-08/09: {live}", flush=True)
jobs = [(k, u, ym) for u in live for k in ("1d", "fundingRate") for ym in months]
with cf.ThreadPoolExecutor(16) as ex:
    ok = sum(ex.map(lambda j: fetch(*j), jobs))
print(f"fetched {ok} of {len(jobs)} monthly files", flush=True)
first = {}
for fn in os.listdir(CACHE):
    if "-1d-" in fn:
        sym = fn.split("-")[1]; ym = fn[-11:-4]
        first[sym] = min(first.get(sym, ym), ym)
json.dump(first, open(f"{SP}/binance_first_month.json", "w"), indent=1, sort_keys=True)
print(sorted(first.items(), key=lambda x: x[1]))
