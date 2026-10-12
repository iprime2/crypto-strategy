#!/usr/bin/env python3
"""Read-only check that the Delta mainnet API key in quote-bot/.env works. Places no orders.

Signs requests the way mm-delta does (HMAC-SHA256 of method + timestamp + path + query) and calls
the same endpoints the bot uses at a live start: wallet, order leverage, position. Never prints
the key or secret.

    python3 scripts/delta_key_check.py [path/to/quote-bot/.env] [SYMBOL]   # default ~/crypto-strategy/cex-mm/quote-bot/.env ADAUSD

Run it on the VM: the key is whitelisted to the VM's IP. Exit 0 means the key can read the account and
the product's order leverage is at most 5x (the bot's MM_MAX_LEVERAGE default).
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("DELTA_REST_BASE", "https://api.india.delta.exchange")
ENV_FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "crypto-strategy/cex-mm/quote-bot/.env"
SYMBOL = sys.argv[2] if len(sys.argv) > 2 else "ADAUSD"
MAX_LEVERAGE = 5.0


def load_env(path: Path) -> dict:
    vals = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"')  # like the OEMS's load_env_file, so this checks what the bot sends
    return vals


env = load_env(ENV_FILE)
KEY, SECRET = env.get("DELTA_MAINNET_API_KEY", ""), env.get("DELTA_MAINNET_API_SECRET", "")
if not KEY or not SECRET:
    names = sorted(k for k in env if "KEY" in k or "SECRET" in k)
    sys.exit(f"FAIL: DELTA_MAINNET_API_KEY / DELTA_MAINNET_API_SECRET not in {ENV_FILE} (found names: {names}). "
             "The bot and the OEMS read exactly those two names.")


def get(path: str, query: str = "", auth: bool = True) -> tuple[int, dict]:
    qs = f"?{query}" if query else ""
    headers = {"User-Agent": "mm-delta/0.1", "Accept": "application/json"}
    if auth:
        ts = str(int(time.time()))
        sig = hmac.new(SECRET.encode(), f"GET{ts}{path}{qs}".encode(), hashlib.sha256).hexdigest()
        headers.update({"api-key": KEY, "timestamp": ts, "signature": sig})
    req = urllib.request.Request(BASE + path + qs, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, {"error": {"code": f"network: {e}"}}


def err(body: dict) -> str:
    e = body.get("error") or {}
    return str(e.get("code") or e) if e else "no error body"


ok = True
status, body = get(f"/v2/products/{SYMBOL}", auth=False)
product = body.get("result") or {}
if status != 200 or "id" not in product:
    sys.exit(f"FAIL public  {SYMBOL}: HTTP {status} {err(body)} (is api.india.delta.exchange reachable?)")
pid = product["id"]
print(f"ok   public  {SYMBOL}: product id {pid}, contract value {product.get('contract_value')}")

status, body = get("/v2/wallet/balances")
if status == 200 and body.get("success") is not False:
    print(f"ok   wallet  key works: net equity {(body.get('meta') or {}).get('net_equity')}")
else:
    ok = False
    print(f"FAIL wallet  HTTP {status} {err(body)}  (ip_not_whitelisted -> wrong IP; "
          "invalid api key / signature -> key or secret pasted wrong)")

status, body = get(f"/v2/products/{pid}/orders/leverage")
res = body.get("result") or {}
try:
    lev = float(res.get("leverage"))
except (TypeError, ValueError):
    lev = None
if status == 200 and lev is not None:
    verdict = "ok  " if lev <= MAX_LEVERAGE else "FAIL"
    ok &= lev <= MAX_LEVERAGE
    print(f"{verdict} leverage {SYMBOL} {lev:g}x (margin mode {res.get('margin_mode')}; bot refuses above "
          f"{MAX_LEVERAGE:g}x). Response fields: {sorted(res)}")
else:
    ok = False
    print(f"FAIL leverage HTTP {status} {err(body)}; result fields: {sorted(res)}")

status, body = get("/v2/positions/margined", f"product_ids={pid}")
if status == 200 and body.get("success") is not False:
    sizes = [row.get("size") for row in body.get("result") or []]
    print(f"ok   position {SYMBOL}: {sizes or [0]} contracts")
else:
    ok = False
    print(f"FAIL position HTTP {status} {err(body)}")

print("PASS: the key can read this account. No orders were placed." if ok else "Not ready: fix the FAIL lines above.")
sys.exit(0 if ok else 1)
