#!/usr/bin/env python3
"""Cancel all MM symbols' orders and close all Delta positions (demo/mainnet via MM_ENV)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
from delta_pnl import _delta_base, _load_env_file, _sign  # noqa: E402


def request(method: str, path: str, query: str = "", body: str = "") -> dict:
    key = os.environ.get("DELTA_API_KEY", "")
    secret = os.environ.get("DELTA_API_SECRET", "")
    if not key or not secret:
        return {"error": "missing DELTA_API_KEY/SECRET"}
    ts, sig = _sign(secret, method, path, query, body)
    url = _delta_base() + path + (f"?{query}" if query else "")
    req = urllib.request.Request(
        url,
        data=body.encode() if body else None,
        method=method,
        headers={
            "api-key": key,
            "timestamp": ts,
            "signature": sig,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "cex-mm-flatten/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode(errors="replace")[:800]}


def product_ids_for_symbols() -> list[int]:
    raw = os.environ.get("MM_SYMBOLS", "BTCUSDT,ETHUSDT")
    syms = [s.strip().upper() for s in raw.split(",") if s.strip()]
    mapping = {"BTCUSDT": "BTCUSD", "ETHUSDT": "ETHUSD", "SOLUSDT": "SOLUSD"}
    prod = request("GET", "/v2/products", "contract_types=perpetual_futures&page_size=200")
    if prod.get("error"):
        raise SystemExit(prod)
    ids: list[int] = []
    for row in prod.get("result") or []:
        sym = row.get("symbol", "")
        for mm in syms:
            if sym == mapping.get(mm, mm.replace("USDT", "USD")):
                ids.append(int(row["id"]))
    return ids


def main() -> None:
    _load_env_file()
    print("Delta base:", _delta_base())
    pids = product_ids_for_symbols()
    print("Cancel orders for product_ids:", pids)
    for pid in pids:
        body = json.dumps({"product_id": pid})
        r = request("DELETE", "/v2/orders/all", "", body)
        print("  cancel product", pid, r.get("success", r))

    body = json.dumps(
        {
            "close_all_portfolio": True,
            "close_all_isolated": True,
            "user_id": 0,
        }
    )
    print("Close all positions…")
    r = request("POST", "/v2/positions/close_all", "", body)
    print(json.dumps(r, indent=2)[:1200])

    pos = request("GET", "/v2/positions/margined")
    open_pos = [p for p in (pos.get("result") or []) if int(p.get("size") or 0) != 0]
    print("Open positions remaining:", len(open_pos))
    for p in open_pos:
        print(" ", p.get("product", {}).get("symbol"), "size", p.get("size"))


if __name__ == "__main__":
    main()
