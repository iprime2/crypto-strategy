import json, sys, collections, re
p = json.load(open(sys.argv[1]))["result"]
print("product_specs sample:", json.dumps(p[0].get("product_specs")))
print("ui_config sample:", json.dumps(p[0].get("ui_config"))[:400])
idx = json.load(open(sys.argv[2]))
r = idx.get("result") or []
print("n indices", len(r), "keys", sorted(r[0].keys()) if r else None)
types = collections.Counter(x.get("index_type") for x in r)
print("index_type counts", types)
for x in r:
    s = (x.get("symbol") or "") + " " + (x.get("description") or "") + " " + str(x.get("index_type"))
    if re.search(r"(?i)vol|vix|\biv\b|dvol|implied", s):
        print("VOL-LIKE:", x.get("symbol"), "|", x.get("description"), "|", x.get("index_type"))
t = json.load(open(sys.argv[3]))
tr = t.get("result") or []
print("n tickers", len(tr))
ct = collections.Counter(x.get("contract_type") for x in tr)
print("ticker contract types", ct)
for x in tr:
    s = (x.get("symbol") or "") + " " + str(x.get("description"))
    if re.search(r"(?i)vol|vix|dvol|move", x.get("symbol") or "") or x.get("contract_type") not in ("call_options","put_options","perpetual_futures"):
        print("OTHER:", x.get("symbol"), x.get("contract_type"), x.get("description"))
