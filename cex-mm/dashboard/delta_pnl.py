"""Delta Exchange venue PnL (positions + wallet) for dashboard — read-only REST."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

CEX_MM = Path(__file__).resolve().parent.parent

DELTA_SYMBOL_TO_MM = {
    "BTCUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT",
    "SOLUSD": "SOLUSDT",
}


def _load_env_file() -> None:
    env_path = CEX_MM / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v


def _demo_keys() -> tuple[str, str]:
    """Demo key and secret: DELTA_DEMO_API_KEY/SECRET, else the older DELTA_API_KEY/SECRET (one pair, never mixed)."""
    for key_var, secret_var in (("DELTA_DEMO_API_KEY", "DELTA_DEMO_API_SECRET"), ("DELTA_API_KEY", "DELTA_API_SECRET")):
        key, secret = os.environ.get(key_var, ""), os.environ.get(secret_var, "")
        if key and secret:
            return key, secret
    return "", ""


def _delta_base() -> str:
    env_flag = os.environ.get("MM_ENV", "testnet").lower()
    if env_flag in ("mainnet", "prod", "production"):
        return "https://api.india.delta.exchange"
    return "https://cdn-ind.testnet.deltaex.org"


def _sign(secret: str, method: str, path: str, query: str = "", body: str = "") -> tuple[str, str]:
    ts = str(int(time.time()))
    q = f"?{query}" if query else ""
    pre = f"{method}{ts}{path}{q}{body}"
    sig = hmac.new(secret.encode(), pre.encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _get(path: str, query: str = "") -> dict:
    key, secret = _demo_keys()
    if not key or not secret:
        return {"error": "missing DELTA_DEMO_API_KEY/SECRET (or DELTA_API_KEY/SECRET)"}
    ts, sig = _sign(secret, "GET", path, query)
    url = _delta_base() + path + (f"?{query}" if query else "")
    req = urllib.request.Request(
        url,
        headers={
            "api-key": key,
            "timestamp": ts,
            "signature": sig,
            "Accept": "application/json",
            "User-Agent": "cex-mm-dashboard/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        return {"error": f"HTTP {e.code}", "detail": body}
    except OSError as e:
        return {"error": str(e)}


def _f(val: object) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def fetch_venue_pnl() -> dict:
    """
    Returns account-level and per-symbol PnL from Delta (source of truth for demo/mainnet UI).
    Amounts in USD wallet asset; includes INR display fields when present.
    """
    _load_env_file()
    out: dict = {
        "source": "delta",
        "fetched_at": time.time(),
        "ok": False,
    }
    if os.environ.get("MM_VENUE", "delta").lower() != "delta":
        out["error"] = "venue not delta"
        return out

    bal = _get("/v2/wallet/balances")
    pos = _get("/v2/positions/margined")

    if bal.get("error"):
        out["error"] = bal["error"]
        out["detail"] = bal.get("detail")
        return out
    if pos.get("error"):
        out["error"] = pos["error"]
        out["detail"] = pos.get("detail")
        return out

    meta = bal.get("meta") or {}
    usd_wallet = None
    for row in bal.get("result") or []:
        if row.get("asset_symbol") == "USD":
            usd_wallet = row
            break

    by_symbol: dict[str, dict] = {}
    total_realized = 0.0
    total_unrealized = 0.0
    for row in pos.get("result") or []:
        prod = row.get("product") or {}
        delta_sym = prod.get("symbol") or row.get("product_symbol") or "?"
        mm_sym = DELTA_SYMBOL_TO_MM.get(delta_sym, delta_sym.replace("USD", "USDT"))
        cv = _f(prod.get("contract_value", "0.001"))
        size = int(row.get("size") or 0)
        base_qty = size * cv
        realized = _f(row.get("realized_pnl"))
        unrealized = _f(row.get("unrealized_pnl"))
        total_realized += realized
        total_unrealized += unrealized
        by_symbol[mm_sym] = {
            "delta_symbol": delta_sym,
            "contracts": size,
            "position_base": base_qty,
            "entry_price": _f(row.get("entry_price")),
            "mark_price": _f(row.get("mark_price")),
            "realized_pnl_usd": realized,
            "unrealized_pnl_usd": unrealized,
            "margin_usd": _f(row.get("margin")),
        }

    out["ok"] = True
    out["net_equity_usd"] = _f(meta.get("net_equity"))
    out["total_realized_pnl_usd"] = total_realized
    out["total_unrealized_pnl_usd"] = total_unrealized
    out["total_pnl_usd"] = total_realized + total_unrealized
    if usd_wallet:
        out["wallet"] = {
            "balance_usd": _f(usd_wallet.get("balance")),
            "available_usd": _f(usd_wallet.get("available_balance")),
            "blocked_margin_usd": _f(usd_wallet.get("blocked_margin")),
            "position_margin_usd": _f(usd_wallet.get("position_margin")),
            "order_margin_usd": _f(usd_wallet.get("order_margin")),
            "balance_inr": _f(usd_wallet.get("balance_inr")),
            "available_inr": _f(usd_wallet.get("available_balance_inr")),
        }
    out["positions"] = by_symbol
    return out
