#!/usr/bin/env python3
"""Read-only: Delta India hourly FUNDING:<sym> candles 2026-07-01..2026-10-01 (UTC) for the UNI-1 2026/2027 names. ./dl/fund_<sym>.json"""
import json, os, time, urllib.request, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f"{HERE}/dl"
D = "https://api.india.delta.exchange"
a = int(dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp()); b = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp())
for c in "BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK ZEC HYPE ADA LTC BCH".split():
    rows = []
    for s in range(a, b, 1999 * 3600):
        u = f"{D}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={s}&end={min(s + 1999 * 3600, b)}"
        r = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "uni1-live-lens/0.1"}), timeout=30).read())
        rows += r.get("result") or []
        time.sleep(0.2)
    json.dump(rows, open(f"{OUT}/fund_{c}USD.json", "w"))
    print(c, len(rows))
