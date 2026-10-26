import json, sys, collections
d = json.load(open(sys.argv[1]))
r = d.get("result") or []
print("n products", len(r), "meta", d.get("meta"))
if r:
    print("keys", sorted(r[0].keys()))
c = collections.Counter()
exp = collections.defaultdict(set)
states = collections.Counter()
for x in r:
    u = (x.get("underlying_asset") or {}).get("symbol")
    c[(u, x.get("contract_type"))] += 1
    exp[u].add(x.get("settlement_time"))
    states[x.get("state")] += 1
print(c)
print(states)
for u, s in exp.items():
    s = sorted(t for t in s if t)
    print(u, len(s), "expiries:", s[:20], "...", s[-5:])
# sample one product fields
for x in r[:1]:
    for k in ("symbol","contract_value","contract_unit_currency","settling_asset","quoting_asset","tick_size","maker_commission_rate","taker_commission_rate","strike_price","settlement_time","launch_time","product_specs","spot_index","state","trading_status","description","annualized_funding","default_leverage","initial_margin","maintenance_margin","position_size_limit"):
        print(k, "=", json.dumps(x.get(k))[:300])
