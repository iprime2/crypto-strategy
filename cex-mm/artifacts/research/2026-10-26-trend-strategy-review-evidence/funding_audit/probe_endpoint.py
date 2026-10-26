#!/usr/bin/env python3
"""Online, public data: how /v2/history/candles serves a FUNDING series. (1) For a fixed end, which candle comes
first for each start offset; (2) end semantics; (3) a price series for contrast; (4) how often a 24 h FUNDING request
for one of the nine coins answers an empty list, and whether an immediate retry recovers.
Run: python3 probe_endpoint.py [DAY as YYYY-MM-DD, default 2026-10-24]"""
import datetime as dt
import json
import sys
import time
import urllib.request

UTC = dt.timezone.utc
COINS = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()


def raw(sym, start, end):
    url = f"https://api.india.delta.exchange/v2/history/candles?resolution=1h&symbol={sym}&start={start}&end={end}"
    return json.loads(urllib.request.urlopen(url, timeout=30).read())["result"]


def get(sym, start, end):
    for k in range(6):
        res = raw(sym, start, end)
        if res:
            return res, k
        time.sleep(0.4)
    return [], 6


h = lambda t: dt.datetime.fromtimestamp(t, UTC).strftime("%d %H:%M:%S")  # noqa: E731
day = int(dt.datetime.fromisoformat((sys.argv[1] if len(sys.argv) > 1 else "2026-10-24") + "T00:00:00+00:00").timestamp())
end = day + 86400 + 313
print(f"(1) FUNDING:BTCUSD, end {h(end)}")
for off in [0, 1, 300, 3600, 7 * 3600, 8 * 3600 - 1, 8 * 3600, 8 * 3600 + 1, 12 * 3600, 16 * 3600, 16 * 3600 + 300]:
    res, k = get("FUNDING:BTCUSD", day + off, end)
    t = sorted(r["time"] for r in res)
    print(f"  start {h(day + off)} -> {len(res):>2} candles, first {h(t[0]) if t else '-'}, last {h(t[-1]) if t else '-'} (empty answers before data: {k})")
print(f"(2) end semantics, start {h(day)}")
for eoff in [0, 1, 300, 3599, 3600]:
    e = day + 16 * 3600 + eoff
    res, _ = get("FUNDING:BTCUSD", day, e)
    print(f"  end {h(e)} -> {len(res):>2} candles, last {h(max(r['time'] for r in res))}")
res, _ = get("BTCUSD", day + 300, end)
print(f"(3) price series BTCUSD, start {h(day + 300)} -> {len(res)} candles, first {h(min(r['time'] for r in res))}")
now = int(time.time())
n = empty = recovered = 0
for rnd in range(12):
    for c in COINS:
        n += 1
        if not raw(f"FUNDING:{c}USD", now - 86400, now):
            empty += 1
            time.sleep(0.5)
            recovered += bool(raw(f"FUNDING:{c}USD", now - 86400, now))
        time.sleep(0.25)
print(f"(4) {n} requests for 24 h of FUNDING candles at {dt.datetime.now(UTC):%Y-%m-%d %H:%M} UTC: {empty} empty ({100 * empty / n:.1f}%), {recovered} recovered on one retry")
