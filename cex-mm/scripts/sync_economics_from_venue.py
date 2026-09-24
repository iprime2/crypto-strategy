#!/usr/bin/env python3
"""Set artifacts/economics/*.json position from Delta venue (interim until mm-bot venue reconcile)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
from delta_pnl import fetch_venue_pnl  # noqa: E402


def main() -> None:
    v = fetch_venue_pnl()
    if not v.get("ok"):
        raise SystemExit(v)
    eco_dir = ROOT / "artifacts" / "economics"
    eco_dir.mkdir(parents=True, exist_ok=True)
    for sym, p in (v.get("positions") or {}).items():
        path = eco_dir / f"{sym}.json"
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        data["position"] = p["position_base"]
        if p.get("entry_price"):
            data["avg_entry"] = p["entry_price"]
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"{sym}: position={data['position']} entry={data.get('avg_entry')}")


if __name__ == "__main__":
    main()
