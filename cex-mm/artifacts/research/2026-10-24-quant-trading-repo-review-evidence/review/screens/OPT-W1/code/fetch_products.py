"""Fetch all expired BTC/ETH call and put products from Delta India public API (compact fields only).
Same fields as options-research/fetch_products.py. Usage: python3 -I fetch_products.py <cache_dir>"""
import json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

B = "https://api.india.delta.exchange"
OUT = sys.argv[1]


def get(path, params):
    url = f"{B}{path}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"failed {url}: {last}")


def fetch(ctype):
    out, after, page = [], None, 0
    while True:
        params = {"contract_types": ctype, "states": "expired", "page_size": 1000,
                  "underlying_asset_symbols": "BTC,ETH"}
        if after:
            params["after"] = after
        d = get("/v2/products", params)
        rows = d.get("result") or []
        for x in rows:
            und = (x.get("underlying_asset") or {}).get("symbol")
            if und not in ("BTC", "ETH"):
                continue
            out.append({"symbol": x["symbol"], "id": x["id"], "type": "C" if ctype.startswith("call") else "P",
                        "underlying": und, "strike": float(x["strike_price"]),
                        "settlement_time": x.get("settlement_time"), "launch_time": x.get("launch_time"),
                        "cv": float(x["contract_value"])})
        page += 1
        after = (d.get("meta") or {}).get("after")
        oldest = min((x.get("settlement_time") or "9") for x in rows) if rows else None
        print(ctype, "page", page, "rows", len(rows), "oldest", oldest, file=sys.stderr, flush=True)
        if not after or not rows:
            break
    return out


with ThreadPoolExecutor(max_workers=2) as ex:
    res = list(ex.map(fetch, ("call_options", "put_options")))
allp = res[0] + res[1]
json.dump(allp, open(os.path.join(OUT, "expired_options.json"), "w"))
print("total", len(allp), file=sys.stderr)
