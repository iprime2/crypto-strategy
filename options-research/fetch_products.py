import json, time, urllib.request, urllib.parse, collections, sys
B = "https://api.india.delta.exchange"
def get(path, params):
    url = f"{B}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research/0.1"}), timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"failed {url}")
out = []
for ctype in ("call_options", "put_options"):
    after = None
    for page in range(400):
        params = {"contract_types": ctype, "states": "expired", "page_size": 200}
        if after: params["after"] = after
        d = get("/v2/products", params)
        rows = d.get("result") or []
        for x in rows:
            sym = x["symbol"]; und = (x.get("underlying_asset") or {}).get("symbol")
            if und not in ("BTC", "ETH"): continue
            out.append({"symbol": sym, "id": x["id"], "type": "C" if ctype.startswith("call") else "P", "underlying": und,
                        "strike": float(x["strike_price"]), "settlement_time": x.get("settlement_time"),
                        "launch_time": x.get("launch_time"), "cv": float(x["contract_value"])})
        after = (d.get("meta") or {}).get("after")
        if not after or not rows: break
    print(ctype, "done pages", page + 1, file=sys.stderr)
json.dump(out, open("expired_options.json", "w"))
by_day = collections.Counter((o["underlying"], o["settlement_time"][:10]) for o in out if o["settlement_time"])
days = sorted({k[1] for k in by_day})
print(len(out), "BTC/ETH expired options;", len(days), "expiry dates from", days[0], "to", days[-1])
hours = collections.Counter(o["settlement_time"][11:16] for o in out if o["settlement_time"])
print("settlement times:", hours.most_common(3))
print("sample", out[0])
