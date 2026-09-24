#!/usr/bin/env python3
"""Slice 7b stub: summarize recorder JSONL and emit AS vs GLFT comparison scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--recording", required=True)
    p.add_argument("--out", default="artifacts/backtest/report.json")
    args = p.parse_args()
    path = Path(args.recording)
    lines = path.read_text().splitlines()
    bybit = sum(1 for ln in lines if '"source": "bybit"' in ln)
    binance = sum(1 for ln in lines if '"source": "binance"' in ln)
    report = {
        "recording": str(path),
        "events_bybit": bybit,
        "events_binance": binance,
        "godark_as": {"half_spread_bps": 8.0, "kappa": 1.2, "vol_horizon_sec": 900},
        "glft_calibrated": {"A": 0.02, "k": 1.5, "sigma_bps": 12.0},
        "note": "Install hftbacktest==2.4.4 for full queue replay; this file is the gate artifact scaffold.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    summary = out.with_name("summary.md")
    summary.write_text(
        f"# Backtest summary\n\n- Recording: `{path}`\n- Bybit events: {bybit}\n- Binance events: {binance}\n\n"
        "Run full hftbacktest with RiskAdverseQueueModel before mainnet.\n"
    )
    print(f"wrote {out} and {summary}")


if __name__ == "__main__":
    main()
