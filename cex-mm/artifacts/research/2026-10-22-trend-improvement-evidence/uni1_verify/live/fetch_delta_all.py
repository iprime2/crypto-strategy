#!/usr/bin/env python3
"""Read-only: 1d candles (last 60 days) for every Delta India USD perp launched on or before 2025-10-21 (>= 365 days on Delta),
for a Delta-own-turnover ranking. Writes ./dl/c1d_all/<symbol>.json. No keys, no orders."""
import json, os, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f"{HERE}/dl/c1d_all"; os.makedirs(OUT, exist_ok=True)
D = "https://api.india.delta.exchange"
perps = json.load(open(f"{HERE}/../../universe/delta_perps.json"))
now = int(time.time()); t1 = now - now % 86400
n = 0
for p in perps:
    if p["launch"] > "2025-10-21":
        continue
    s = p["symbol"]; fn = f"{OUT}/{s}.json"
    if os.path.exists(fn):
        continue
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(f"{D}/v2/history/candles?resolution=1d&symbol={s}&start={t1 - 60 * 86400}&end={t1}",
                       headers={"User-Agent": "uni1-live-lens/0.1"}), timeout=30).read())
    except Exception as e:
        r = {"error": str(e)}
    json.dump(r, open(fn, "w")); n += 1
    time.sleep(0.2)
print("fetched", n)
