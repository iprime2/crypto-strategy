#!/usr/bin/env python3
"""Online: does Delta's FUNDING:<sym> candle series answer right now, for the two books' windows and for windows that
start on an 8-hour stamp? Run here and over ssh on the VM: python3 - < probe_funding_outage.py"""
import json, time, urllib.request, datetime as dt
UTC = dt.timezone.utc
D = "https://api.india.delta.exchange"
h = lambda t: dt.datetime.fromtimestamp(t, UTC).strftime("%d %H:%M:%S")
now = int(time.time())
cases = {"daily window (since 27 00:05:30)": 1793059530, "weekly window (since 26 00:05:14)": 1792973114,
         "start on a stamp (26 00:00)": 1792972800, "30 h back on a stamp": (now - 30 * 3600) // 28800 * 28800}
for coin in ("BTC", "ETH"):
    for name, start in cases.items():
        url = f"{D}/v2/history/candles?resolution=1h&symbol=FUNDING:{coin}USD&start={start}&end={now}"
        res = []
        for k in range(5):
            body = json.loads(urllib.request.urlopen(url, timeout=30).read())
            res = body.get("result") or []
            if res: break
            time.sleep(1)
        ts = sorted(r["time"] for r in res)
        print(f"{coin} {name:<36} -> {len(res):>2} candles after {k} retries" + (f", {h(ts[0])} .. {h(ts[-1])}" if ts else f", body {json.dumps(body)[:120]}"))
print("now", h(now))
