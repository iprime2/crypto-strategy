"""JWT sub extraction for GoDark user_uuid when not set in env."""

from __future__ import annotations

import base64
import json


def user_uuid_from_jwt(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (json.JSONDecodeError, ValueError):
        return None
    sub = data.get("sub")
    return sub.strip() if isinstance(sub, str) and sub.strip() else None
