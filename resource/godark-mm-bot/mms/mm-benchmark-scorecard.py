#!/usr/bin/env python3
"""Weekly MM quality scorecard — testnet + devnet from logs + dashboard JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mm_markout import parse_markout_samples, summarize_markout_samples  # noqa: E402

SYMS = ["BTC", "ETH", "SOL"]
STACKS = [
    ("testnet", Path.home() / "scripts/mms/artifacts"),
    ("devnet", Path.home() / "scripts/mms/artifacts/devnet"),
]
DASH = Path.home() / "scripts/mms/artifacts/mm-metrics/dashboard-both-latest.json"


def tier_a_pass(mk: dict, inv: float, max_inv: float, slug: str) -> tuple[bool, str]:
    buy_avg = mk.get("buy_avg_bps")
    inv_ratio = abs(inv) / max_inv if max_inv and max_inv > 0 else 0.0
    if slug == "SOL" and buy_avg is not None and buy_avg < -20.0 and inv > 0 and inv_ratio > 0.15:
        return False, f"SOL long + toxic buys (buy_30s={buy_avg:+.1f}bps, inv_ratio={inv_ratio:.0%})"
    if mk.get("count", 0) >= 8 and mk.get("avg_bps") is not None and mk["avg_bps"] < -25.0:
        return False, f"avg 30s markout {mk['avg_bps']:+.1f}bps (n={mk['count']})"
    return True, "ok"


def main() -> int:
    dash = {}
    if DASH.exists():
        dash = json.loads(DASH.read_text())
    generated = dash.get("generated_at", "—")

    print(f"# MM benchmark scorecard (dashboard {generated})")
    print()

    for stack, root in STACKS:
        print(f"## {stack.upper()}")
        stack_row = next((s for s in dash.get("stacks", []) if s.get("stack") == stack), None)
        pf = (stack_row or {}).get("portfolio") or {}
        print(
            f"Portfolio (bot last): net={pf.get('net_realized_pnl_usdc')} "
            f"realized={pf.get('realized_pnl_usdc')} uPnL={pf.get('unrealized_pnl_usdc')}"
        )
        print("Compare to GoDark FE realized PnL for ground truth.")
        print()

        for sym in SYMS:
            log = root / f"mm-bot-{sym}.log"
            mk = summarize_markout_samples(parse_markout_samples(log))
            sym_row = None
            if stack_row:
                sym_row = next((s for s in stack_row.get("symbols", []) if s["slug"] == sym), None)
            m = (sym_row or {}).get("last_metric") or {}
            inv = float(m.get("inventory") or 0)
            max_inv = float(m.get("max_inventory") or 1)
            ok, reason = tier_a_pass(mk, inv, max_inv, sym)
            flag = "PASS" if ok else "FAIL"
            print(f"  {sym} [{flag}] {reason}")
            print(
                f"    inv={inv:.4f} cap={max_inv} net={m.get('net_realized_pnl_usdc')} "
                f"markout30 n={mk['count']} avg={mk['avg_bps']} "
                f"buy={mk['buy_avg_bps']} sell={mk['sell_avg_bps']}"
            )
        print()

    print("Tier A: no symbol FAIL; portfolio net trend vs FE weekly.")
    print("Run: python3 ~/scripts/mms/mm-benchmark-scorecard.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
