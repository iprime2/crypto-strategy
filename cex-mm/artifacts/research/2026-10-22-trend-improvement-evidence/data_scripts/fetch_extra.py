#!/usr/bin/env python3
"""(a) 5 m klines for the nine, 2024-01..2026-09 (D-3 fill drift); (b) 1 h klines for the 15 extra ex-ante coins (TIME-3, A5);
(c) Delta MARK:<sym> daily candles for the nine (D-4). All public, read-only."""
import concurrent.futures as cf, io, json, os, urllib.request, zipfile, datetime as dt
SP = os.path.dirname(os.path.abspath(__file__)); UA = {"User-Agent": "cex-mm-trend/0.1"}
def get(u): return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()
def months(a, b):
    out = []; y, m = a
    while (y, m) <= b: out.append(f"{y}-{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out
def fetch(kind, sym, ym, outdir):
    path = f"{outdir}/binance-{sym}-{kind}-{ym}.csv"
    if os.path.exists(path): return True
    try: z = get(f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/{kind}/{sym}-{kind}-{ym}.zip")
    except Exception: return False
    with zipfile.ZipFile(io.BytesIO(z)) as f: open(path, "wb").write(f.read(f.namelist()[0]))
    return True
NINE = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
EXTRA = "EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST".split()
with cf.ThreadPoolExecutor(16) as ex:
    j5 = [("5m", c + "USDT", ym, f"{SP}/klines5m") for c in NINE for ym in months((2024, 1), (2026, 9))]
    print("5m:", sum(ex.map(lambda a: fetch(*a), j5)), "of", len(j5), flush=True)
    j1 = [("1h", c + "USDT", ym, f"{SP}/hourly_extra") for c in EXTRA for ym in months((2019, 12), (2026, 9))]
    print("1h extras:", sum(ex.map(lambda a: fetch(*a), j1)), "of", len(j1), flush=True)
# Delta MARK daily candles
t0 = int(dt.datetime(2023, 12, 1, tzinfo=dt.timezone.utc).timestamp()); t1 = int(dt.datetime(2026, 10, 21, tzinfo=dt.timezone.utc).timestamp())
for c in NINE:
    try:
        r = json.loads(get(f"https://api.india.delta.exchange/v2/history/candles?resolution=1d&symbol=MARK:{c}USD&start={t0}&end={t1}"))["result"]
        json.dump(r, open(f"{SP}/delta_mark/mark_{c}USD.json", "w")); print("MARK", c, len(r), flush=True)
    except Exception as e:
        print("MARK", c, "failed", str(e)[:100], flush=True)
print("done", flush=True)
