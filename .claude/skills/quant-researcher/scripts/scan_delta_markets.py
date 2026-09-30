#!/usr/bin/env python3
"""Rank Delta Exchange India MAINNET perpetuals by how much room a maker has to earn.

Public data only (GET /v2/tickers). Samples the touch several times and reports the
median spread, the tick size in bps, 24h turnover and funding. A pair is worth a
passive quote only if its natural spread is well above the round-trip maker fee
(2 x 2.12 bps at the retail tier, GST included).

    python3 scan_delta_markets.py --samples 8 --gap 15 --min-turnover 1e6
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request

URL = "https://api.india.delta.exchange/v2/tickers?contract_types=perpetual_futures"


def snapshot() -> dict[str, dict]:
    req = urllib.request.Request(URL, headers={"User-Agent": "cex-mm-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return {r["symbol"]: r for r in json.loads(resp.read())["result"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--gap", type=float, default=15.0, help="seconds between samples")
    ap.add_argument("--min-turnover", type=float, default=1e6)
    ap.add_argument("--round-trip-fee-bps", type=float, default=4.25)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    snaps = []
    for i in range(args.samples):
        snaps.append(snapshot())
        if i + 1 < args.samples:
            time.sleep(args.gap)

    rows = []
    for sym, last in snaps[-1].items():
        spreads = []
        for s in snaps:
            q = (s.get(sym) or {}).get("quotes") or {}
            try:
                b, a = float(q["best_bid"]), float(q["best_ask"])
            except (KeyError, TypeError, ValueError):
                continue
            if b > 0 and a > b:
                spreads.append((a - b) / ((a + b) / 2) * 1e4)
        mark = float(last.get("mark_price") or 0)
        if len(spreads) < max(2, args.samples // 2) or mark <= 0:
            continue
        rows.append(
            {
                "sym": sym,
                "spread": statistics.median(spreads),
                "tick": float(last["tick_size"]) / mark * 1e4,
                "turnover": float(last.get("turnover_usd") or 0),
                "oi": float(last.get("oi_value_usd") or 0),
                "funding": float(last.get("funding_rate") or 0),
            }
        )
    rows.sort(key=lambda r: -r["turnover"])
    print(f"{'symbol':12s} {'spread':>7s} {'tick':>6s} {'turnover24h':>14s} {'OI':>12s} {'fund%':>8s}")
    for r in rows[: args.top]:
        print(
            f"{r['sym']:12s} {r['spread']:7.2f} {r['tick']:6.2f} {r['turnover']:14,.0f} "
            f"{r['oi']:12,.0f} {r['funding']:8.4f}"
        )
    floor = 1.4 * args.round_trip_fee_bps
    print(f"\nCandidates: median spread >= {floor:.1f} bps and turnover >= ${args.min_turnover:,.0f}")
    for r in rows:
        if r["spread"] >= floor and r["turnover"] >= args.min_turnover:
            ticks = r["spread"] / r["tick"] if r["tick"] else float("nan")
            print(
                f"  {r['sym']:12s} spread {r['spread']:6.2f} bps = {ticks:5.1f} ticks, "
                f"turnover ${r['turnover']:,.0f}"
            )


if __name__ == "__main__":
    main()
