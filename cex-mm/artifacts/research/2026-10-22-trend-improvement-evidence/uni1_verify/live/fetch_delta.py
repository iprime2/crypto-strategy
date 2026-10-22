#!/usr/bin/env python3
"""Read-only Delta India public data for the UNI-1 live lens: tickers (perps), products, L2 books (depth 50) and 1d candles
(last 90 days) for the candidate coins. Writes JSON into ./dl/. No keys, no orders."""
import json, os, sys, time, urllib.request, datetime as dt
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dl")
D = "https://api.india.delta.exchange"
COINS = ("BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK ZEC HYPE NEAR UNI SUI ENA ADA ARB TAO WLD PUMP FIL AKE TRUMP AAVE USELESS "
         "LTC BCH PEPE").split()


def get(url):
    for k in range(3):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "uni1-live-lens/0.1"}), timeout=30).read())
        except Exception as e:
            if k == 2:
                return {"error": str(e)}
            time.sleep(3)


os.makedirs(OUT, exist_ok=True)
tick = get(f"{D}/v2/tickers?contract_types=perpetual_futures")
json.dump(tick, open(f"{OUT}/tickers_now.json", "w"))
syms = {t["symbol"] for t in tick.get("result", [])}
print("perp tickers:", len(syms), "fetched", dt.datetime.now(dt.timezone.utc).isoformat())
now = int(time.time()); t1 = now - now % 86400
for c in COINS:
    s = f"{c}USD"
    if s not in syms:
        print(f"{s}: not a Delta India perp ticker"); continue
    book = get(f"{D}/v2/l2orderbook/{s}?depth=50")
    json.dump(book, open(f"{OUT}/l2_{s}.json", "w"))
    cnd = get(f"{D}/v2/history/candles?resolution=1d&symbol={s}&start={t1 - 90 * 86400}&end={t1}")
    json.dump(cnd, open(f"{OUT}/c1d_{s}.json", "w"))
    print(s, "book levels", len((book.get("result") or {}).get("buy", [])), len((book.get("result") or {}).get("sell", [])),
          "candles", len(cnd.get("result") or []))
    time.sleep(0.3)
