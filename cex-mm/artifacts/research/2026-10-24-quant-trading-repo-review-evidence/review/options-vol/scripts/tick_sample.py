import json, sys
t = json.load(open(sys.argv[1]))["result"]
opt = [x for x in t if x.get("contract_type") == "call_options" and x["symbol"].startswith("C-BTC")]
mv = [x for x in t if x.get("contract_type") == "move_options"]
print(json.dumps(opt[0], indent=1)[:3500])
print("----- move")
print(json.dumps(mv[0], indent=1)[:3000])
