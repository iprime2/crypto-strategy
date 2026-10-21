#!/usr/bin/env python3
"""Every USDT-M perpetual symbol in Binance's public archive (delisted ones included), from the S3 index; daily klines for
all, funding for those with >= 180 daily bars. Survivorship-free pool for the rolling-universe tests."""
import concurrent.futures as cf, io, json, os, re, urllib.request, zipfile
SP = os.path.dirname(os.path.abspath(__file__)); CACHE = f"{SP}/cache_all"
UA = {"User-Agent": "cex-mm-trend/0.1"}
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
# S3 listing with pagination
syms, marker = [], ""
while True:
    xml = get("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/" + (f"&marker={marker}" if marker else "")).decode()
    pre = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^/<]+)/</Prefix>", xml)
    syms += pre
    if "<IsTruncated>true</IsTruncated>" in xml and pre:
        marker = f"data/futures/um/monthly/klines/{pre[-1]}/"
    else:
        break
usdt = sorted(s for s in set(syms) if s.endswith("USDT") and not s.endswith("_") and "_" not in s)
have = set()
for d in ("cache", "../trend-cache", "../av_cache"):
    for fn in os.listdir(f"{SP}/{d}"):
        if fn.startswith("binance-") and "-1d-" in fn:
            have.add(fn.split("-")[1])
todo = [s for s in usdt if s not in have]
print(f"{len(usdt)} USDT-M symbols in the archive; {len(have)} already cached; fetching {len(todo)}", flush=True)
months = []
y, m = 2019, 9
while (y, m) <= (2026, 9):
    months.append(f"{y}-{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
def fetch(kind, sym, ym):
    path = f"{CACHE}/binance-{sym}-{kind}-{ym}.csv"
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
with cf.ThreadPoolExecutor(32) as ex:
    ok = sum(ex.map(lambda j: fetch(*j), [("1d", s, ym) for s in todo for ym in months]))
print(f"1d: fetched {ok} monthly files", flush=True)
# funding for symbols with >= 6 monthly files
cnt = {}
for fn in os.listdir(CACHE):
    if "-1d-" in fn:
        cnt[fn.split("-")[1]] = cnt.get(fn.split("-")[1], 0) + 1
fsyms = [s for s, n in cnt.items() if n >= 6]
with cf.ThreadPoolExecutor(32) as ex:
    ok = sum(ex.map(lambda j: fetch(*j), [("fundingRate", s, ym) for s in fsyms for ym in months]))
print(f"funding: fetched {ok} monthly files for {len(fsyms)} symbols", flush=True)
json.dump(sorted(cnt.items()), open(f"{SP}/all_symbols_months.json", "w"))
print("done", flush=True)
