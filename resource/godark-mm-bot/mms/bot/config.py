"""Load MM bot settings from environment (after source-secrets.sh or .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (_env(name) or "").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


@dataclass(frozen=True)
class BotConfig:
    api_key_id: str
    api_secret: str
    passphrase: str
    edge_url: str
    symbol: str
    half_spread_bps: float
    inventory_skew_bps: float
    max_inventory: float
    order_qty: float
    loop_interval_sec: float
    stale_fair_sec: float
    jump_bps: float
    tick_size: float
    maker_fee_bps: float
    dry_run: bool
    fair_override: float | None
    environment: str

    @classmethod
    def from_env(cls) -> BotConfig:
        env_name = (_env("GODARK_ENV", "testnet") or "testnet").lower()
        is_devnet = env_name == "devnet"

        if is_devnet:
            api_key_id = (
                _env("GODARK_DEVNET_API_KEY_ID")
                or _env("GODARK_DEVNET_API_KEY")
                or _env("GODARK_API_KEY_ID")
                or ""
            )
            api_secret = _env("GODARK_DEVNET_API_SECRET") or _env("GODARK_API_SECRET") or ""
            passphrase = (
                _env("GODARK_DEVNET_PASSPHRASE")
                or _env("GODARK_PASSPHRASE")
                or _env("GODARK_API_PASSPHRASE")
                or ""
            )
            edge_url = (
                _env("GODARK_DEVNET_EDGE_URL", "wss://api.devnet.godark-dex.com")
                or "wss://api.devnet.godark-dex.com"
            )
            symbol = (
                _env("GODARK_DEVNET_SYMBOL")
                or _env("GODARK_SYMBOL", "BTC-USDC-PERP")
                or "BTC-USDC-PERP"
            )
            cred_prefix = "GODARK_DEVNET"
        else:
            api_key_id = _env("GODARK_API_KEY_ID") or _env("GODARK_API_KEY") or ""
            api_secret = _env("GODARK_API_SECRET") or ""
            passphrase = _env("GODARK_PASSPHRASE") or _env("GODARK_API_PASSPHRASE") or ""
            edge_url = _env("GODARK_EDGE_URL", "wss://api.godark-dex.com") or "wss://api.godark-dex.com"
            symbol = _env("GODARK_SYMBOL", "BTC-USDC-PERP") or "BTC-USDC-PERP"
            cred_prefix = "GODARK"

        missing = [
            f"{cred_prefix}_API_KEY_ID",
            f"{cred_prefix}_API_SECRET",
            f"{cred_prefix}_PASSPHRASE",
        ]
        missing = [
            name
            for name, val in zip(
                missing,
                (api_key_id, api_secret, passphrase),
                strict=True,
            )
            if not val
        ]
        if missing and not _env_bool("MM_DRY_RUN"):
            raise SystemExit(
                "Missing credentials: "
                + ", ".join(missing)
                + ". Fill ~/.cursor/secrets.env or bot/.env, then: source ~/scripts/source-secrets.sh"
            )

        fair_override_raw = _env("MM_FAIR_OVERRIDE")
        return cls(
            api_key_id=api_key_id,
            api_secret=api_secret,
            passphrase=passphrase,
            edge_url=edge_url,
            symbol=symbol,
            half_spread_bps=_env_float("MM_HALF_SPREAD_BPS", 50.0),
            inventory_skew_bps=_env_float("MM_INVENTORY_SKEW_BPS", 5.0),
            max_inventory=_env_float("MM_MAX_INVENTORY", 0.05),
            order_qty=_env_float("MM_ORDER_QTY", 0.01),
            loop_interval_sec=_env_float("MM_LOOP_INTERVAL_SEC", 5.0),
            stale_fair_sec=_env_float("MM_STALE_FAIR_SEC", 30.0),
            jump_bps=_env_float("MM_JUMP_BPS", 25.0),
            tick_size=_env_float("MM_TICK_SIZE", 0.01),
            maker_fee_bps=_env_float("MM_MAKER_FEE_BPS", 2.0),
            dry_run=_env_bool("MM_DRY_RUN"),
            fair_override=float(fair_override_raw) if fair_override_raw else None,
            environment=env_name,
        )
