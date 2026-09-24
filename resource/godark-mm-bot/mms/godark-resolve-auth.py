#!/usr/bin/env python3
"""Resolve GoDark devnet auth context from API keys (no secrets printed).

Usage:
  source ~/scripts/source-secrets.sh
  python3 ~/scripts/mms/godark-resolve-auth.py          # human summary
  python3 ~/scripts/mms/godark-resolve-auth.py --export # shell exports (no secrets)
  python3 ~/scripts/mms/godark-resolve-auth.py --uuid   # user_uuid only
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_DEVNET_REST = "https://api.devnet.godark-dex.com"
DEFAULT_DEVNET_WS = "wss://api.devnet.godark-dex.com"
DEFAULT_HPKE_PIN = "a6807e2f6cd04b54cc19be2fd4faea2a1239f1e2896912d91222678ab54cdd45"


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def jwt_sub(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (json.JSONDecodeError, ValueError):
        return None
    sub = data.get("sub")
    return sub if isinstance(sub, str) and sub.strip() else None


def fetch_access_token(rest_base: str, key_id: str, secret: str, passphrase: str) -> str:
    body = json.dumps(
        {
            "grant_type": "client_credentials",
            "client_id": key_id,
            "client_secret": secret,
            "passphrase": passphrase,
        }
    ).encode()
    req = urllib.request.Request(
        f"{rest_base.rstrip('/')}/api/v1/auth/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected auth/token response shape")
    token = data.get("access_token") or data.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("auth/token missing access_token")
    return token


def probe_time(rest_base: str) -> bool:
    try:
        with urllib.request.urlopen(f"{rest_base.rstrip('/')}/api/v1/time", timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def resolve() -> dict[str, str]:
    env = (_env("GODARK_ENV") or "testnet").lower()
    if env == "devnet":
        # Prefer GDX_/GODARK_* set by mm-env + mm-creds (per-symbol devnet keys).
        key_id = _env(
            "GDX_API_KEY_ID",
            "GODARK_API_KEY_ID",
            "GODARK_DEVNET_API_KEY_ID",
        )
        secret = _env(
            "GDX_API_SECRET",
            "GODARK_API_SECRET",
            "GODARK_DEVNET_API_SECRET",
        )
        passphrase = _env(
            "GDX_PASSPHRASE",
            "GODARK_PASSPHRASE",
            "GODARK_DEVNET_PASSPHRASE",
        )
        rest_base = _env("GODARK_DEVNET_REST_URL", "GODARK_REST_URL") or DEFAULT_DEVNET_REST
        ws_base = _env("GODARK_DEVNET_EDGE_URL", "GODARK_EDGE_URL") or DEFAULT_DEVNET_WS
        hpke = _env("GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY", "GDX_HPKE_STATIC_PUBLIC_KEY") or DEFAULT_HPKE_PIN
        user_uuid = _env("GODARK_DEVNET_USER_UUID", "GDX_USER_UUID", "GODARK_USER_UUID")
    elif env in ("testnet", "mainnet", ""):
        key_id = _env("GODARK_API_KEY_ID", "GDX_API_KEY_ID")
        secret = _env("GODARK_API_SECRET", "GDX_API_SECRET")
        passphrase = _env("GODARK_PASSPHRASE", "GDX_PASSPHRASE")
        rest_base = _env("GODARK_REST_URL", "GDX_REST_URL") or "https://api.godark-dex.com"
        ws_base = _env("GODARK_EDGE_URL", "GDX_EDGE_URL") or "wss://api.godark-dex.com"
        hpke = _env("GODARK_HPKE_STATIC_PUBLIC_KEY", "GDX_HPKE_STATIC_PUBLIC_KEY")
        user_uuid = _env("GODARK_USER_UUID", "GDX_USER_UUID")
    else:
        raise SystemExit(f"Unsupported GODARK_ENV={env!r} (use testnet or devnet)")

    if not (key_id and secret and passphrase):
        raise SystemExit(
            "Missing API credentials. Fill GODARK_DEVNET_* (or GODARK_*) in ~/.cursor/secrets.env, "
            "then: source ~/scripts/source-secrets.sh"
        )

    token = fetch_access_token(rest_base, key_id, secret, passphrase)
    # JWT sub is authoritative for REST client_credentials; env USER_UUID is
    # optional fallback only when the token omits sub (e.g. some local edges).
    user_uuid = jwt_sub(token) or user_uuid

    return {
        "rest_base": rest_base,
        "ws_base": ws_base.replace("http://", "ws://").replace("https://", "wss://"),
        "hpke_pin": hpke,
        "user_uuid": user_uuid,
        "time_ok": str(probe_time(rest_base)).lower(),
        "token_ok": "true" if token else "false",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve GoDark auth context from env API keys")
    parser.add_argument("--export", action="store_true", help="Print shell export lines (no secrets)")
    parser.add_argument("--uuid", action="store_true", help="Print user_uuid only")
    args = parser.parse_args()

    info = resolve()

    if args.uuid:
        if not info["user_uuid"]:
            raise SystemExit("user_uuid not found in env or JWT sub")
        print(info["user_uuid"])
        return

    if args.export:
        print(f'export GDX_REST_URL="{info["rest_base"]}"')
        print(f'export GDX_EDGE_URL="{info["ws_base"]}"')
        print(f'export GDX_HPKE_STATIC_PUBLIC_KEY="{info["hpke_pin"]}"')
        print(f'export GDX_USER_UUID="{info["user_uuid"]}"')
        print('export GDX_LIVE_EDGE=1')
        return

    print("GoDark auth context (no secrets shown)")
    print(f"  rest:      {info['rest_base']} (time ok: {info['time_ok']})")
    print(f"  ws:        {info['ws_base']}")
    print(f"  hpke pin:  {info['hpke_pin'][:8]}...{info['hpke_pin'][-8:]}")
    print(f"  user_uuid: {info['user_uuid'] or '(missing — check JWT sub)'}")
    print(f"  token:     ok={info['token_ok']}")


if __name__ == "__main__":
    main()
