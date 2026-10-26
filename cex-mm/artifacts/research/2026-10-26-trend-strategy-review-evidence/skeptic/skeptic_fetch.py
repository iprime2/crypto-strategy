"""Fetch Delta India public data needed to re-derive the trend signals, backtest and funding. Own code."""
import json, urllib.request, datetime as dt, time, sys
D="https://api.india.delta.exchange"
UA={"User-Agent":"skeptic-check/0.1"}
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
def get(url):
    for i in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30).read())["result"]
        except Exception as e:
            if i==2: raise
            time.sleep(3)
outdir=sys.argv[1]
now=int(time.time())
# products -> contract values
prods=get(f"{D}/v2/products?page_size=500")
cv={p["symbol"]:float(p["contract_value"]) for p in prods if p["symbol"] in [c+"USD" for c in COINS]}
json.dump(cv, open(f"{outdir}/products_cv.json","w"), indent=1)
print("contract values", cv)
# daily candles, last 220 days (need 121 closes before 7 Oct)
t1=now; t0=now-220*86400
daily={}
for c in COINS:
    bars=get(f"{D}/v2/history/candles?resolution=1d&symbol={c}USD&start={t0}&end={t1}")
    daily[c]=[[b["time"],b["open"],b["high"],b["low"],b["close"],b.get("volume")] for b in bars]
    print(c, len(bars), dt.datetime.fromtimestamp(bars[0]["time"],dt.timezone.utc).date(), "->", dt.datetime.fromtimestamp(bars[-1]["time"],dt.timezone.utc).date())
json.dump(daily, open(f"{outdir}/daily_candles.json","w"))
# funding hourly candles 7 Oct 00:00 -> now
f0=int(dt.datetime(2026,10,7,tzinfo=dt.timezone.utc).timestamp())
fund={}
for c in COINS:
    rates=get(f"{D}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={f0}&end={now}")
    fund[c]=[[r["time"],r["open"],r["high"],r["low"],r["close"]] for r in rates]
    print("FUNDING",c,len(rates), dt.datetime.fromtimestamp(rates[0]["time"],dt.timezone.utc), "->", dt.datetime.fromtimestamp(rates[-1]["time"],dt.timezone.utc))
json.dump(fund, open(f"{outdir}/funding_1h.json","w"))
json.dump({"fetched_utc":dt.datetime.now(dt.timezone.utc).isoformat()}, open(f"{outdir}/fetch_meta.json","w"))
