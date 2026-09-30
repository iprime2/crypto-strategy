#!/usr/bin/env python3
"""Download every Delta Exchange fill for the account in cex-mm/.env to a JSON file.

Read-only (GET /v2/fills). Uses the signing helper in cex-mm/dashboard/delta_pnl.py,
so MM_ENV=mainnet in the environment switches to the production API.

    python3 fetch_delta_fills.py --out /tmp/fills.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CEX_MM = Path(__file__).resolve().parents[4] / "cex-mm"
sys.path.insert(0, str(CEX_MM / "dashboard"))
import delta_pnl  # noqa: E402


def fetch_all(max_pages: int) -> list[dict]:
    delta_pnl._load_env_file()
    rows: list[dict] = []
    after = None
    for _ in range(max_pages):
        query = "page_size=100" + (f"&after={after}" if after else "")
        resp = delta_pnl._get("/v2/fills", query)
        if resp.get("success") is not True:
            raise SystemExit(f"Delta /v2/fills failed: {resp}")
        page = resp.get("result") or []
        rows.extend(page)
        after = (resp.get("meta") or {}).get("after")
        if not after or not page:
            break
        time.sleep(0.2)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=500)
    args = ap.parse_args()
    rows = fetch_all(args.max_pages)
    Path(args.out).write_text(json.dumps(rows))
    if rows:
        first, last = rows[-1]["created_at"], rows[0]["created_at"]
        print(f"{len(rows)} fills, {first} -> {last}, written to {args.out}")
    else:
        print("no fills")


if __name__ == "__main__":
    main()
