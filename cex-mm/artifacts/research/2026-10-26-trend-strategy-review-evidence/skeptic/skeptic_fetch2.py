"""Second pass: contract values per product, and funding candles with retries (BNB returned empty once)."""
import json, urllib.request, datetime as dt, time, sys
D="https://api.india.delta.exchange"; UA={"User-Agent":"skeptic-check/0.1"}
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
def get(url, tries=4):
    for i in range(tries):
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30).read())
            return r["result"]
        except Exception as e:
            if i==tries-1: raise
            time.sleep(4*(i+1))
outdir=sys.argv[1]
cv={}
for c in COINS:
    p=get(f"{D}/v2/products/{c}USD")
    cv[c]=float(p["contract_value"]); 
    print(c, "cv", cv[c], "tick", p.get("tick_size"), "state", p.get("state"))
    time.sleep(0.3)
json.dump(cv, open(f"{outdir}/products_cv.json","w"), indent=1)
now=int(time.time())
f0=int(dt.datetime(2026,10,7,tzinfo=dt.timezone.utc).timestamp())
fund={}
for c in COINS:
    rates=[]
    for k in range(5):
        rates=get(f"{D}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={f0}&end={now}")
        if rates: break
        time.sleep(5)
    fund[c]=sorted([[r["time"],r["open"],r["high"],r["low"],r["close"]] for r in rates])
    print("FUNDING",c,len(rates), dt.datetime.fromtimestamp(fund[c][0][0],dt.timezone.utc) if rates else None, "->", dt.datetime.fromtimestamp(fund[c][-1][0],dt.timezone.utc) if rates else None)
    time.sleep(0.5)
json.dump(fund, open(f"{outdir}/funding_1h.json","w"))
json.dump({"fetched_utc":dt.datetime.now(dt.timezone.utc).isoformat()}, open(f"{outdir}/fetch_meta.json","w"))
