import json, urllib.request, datetime as dt, time, sys
UA={"User-Agent":"cex-mm-trend-review/0.1"}
D="https://api.india.delta.exchange"
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
def get(url):
    for a in range(3):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30).read())["result"]
        except Exception as e:
            if a==2: raise
            time.sleep(3)
today=dt.date(2026,10,27)  # end exclusive: want closes through 26 Oct (the 26 Oct candle is still open at ~17:40Z; drop later)
t1=int(dt.datetime.combine(today,dt.time(),dt.timezone.utc).timestamp())
t0=t1-220*86400
out={}
for c in COINS:
    bars=get(f"{D}/v2/history/candles?resolution=1d&symbol={c}USD&start={t0}&end={t1}")
    rates=[]
    for s in range(t0,t1,1999*3600):
        rates+=get(f"{D}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={s}&end={min(s+1999*3600,t1)}")
    out[c]={"close":[[b["time"],b["close"],b.get("open"),b.get("high"),b.get("low"),b.get("volume")] for b in bars],
            "funding":[[r["time"],r["close"]] for r in rates]}
    print(c,"bars",len(bars),"first",dt.datetime.fromtimestamp(bars[0]["time"],dt.timezone.utc).date() if bars else None,
          "last",dt.datetime.fromtimestamp(bars[-1]["time"],dt.timezone.utc).date() if bars else None,"funding rows",len(rates),flush=True)
# contract values
prods=get(f"{D}/v2/products")
cv={p["symbol"]:float(p["contract_value"]) for p in prods}
out["_cvals"]={c:cv[c+"USD"] for c in COINS}
print("cvals",out["_cvals"])
json.dump(out,open("delta_daily_2026-10-27.json","w"))
print("saved")
