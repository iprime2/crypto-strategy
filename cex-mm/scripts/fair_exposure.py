#!/usr/bin/env python3
"""How stale are the quotes? Scores one symbol's MM_METRICS in a shadow run:

- how far the fair sits from the Binance-implied price;
- how often a resting quote is within --exposed-bps of that price, or through it (a faster trader can hit
  it for free);
- how often only one side is quoted.

Both the logged fair and `fair_delta` (the fair without the Binance anchor, logged since 2026-10-13) are
scored, so one run compares the anchored and the old fair on the same data.

Reference price = Binance mid x (1 + basis). The basis is a centred rolling median of the run's own Delta
book mid over the Binance mid (--basis-window-min). That estimate looks ahead, and it is only valid where
the book does not contain our own orders: a shadow run, or a live run before its start.
Resting quotes are rebuilt with the bot's rule: an order moves only when the new quote is more than
--requote-tol-bps away (MM_REQUOTE_TOL_BPS).

    python3 scripts/fair_exposure.py --run-dir artifacts/shadow/current --symbol ADAUSDT --hours 24
"""
from __future__ import annotations

import argparse
import bisect
import glob
import json
import os
import statistics
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shadow_fill_sim as sim  # noqa: E402


@dataclass
class Row:
    ts: float
    fair: float
    fair_delta: float | None
    bid: float
    ask: float
    place_bid: bool
    place_ask: bool
    binance: float
    book_mid: float
    anchored: bool


def load(paths: list[str], symbol: str, since_ms: float = 0.0, max_binance_age_ms: float = 5000.0) -> list[Row]:
    """Rows with a Binance mid, skipping those logged while the Binance feed was silent (binance_age_ms, logged
    since 2026-10-13): the bot keeps the last price then, and it is not a reference."""
    out = []
    for path in paths:
        for line in sim.iter_lines(path):
            i = line.find("MM_METRICS")
            j = line.find("{", i) if i >= 0 else -1
            if j < 0:
                continue
            try:
                m = json.loads(line[j:])
            except ValueError:
                continue
            b = m.get("binance_mid") or 0.0
            if m.get("symbol") != symbol or b <= 0 or m.get("ts_ms", 0) < since_ms:
                continue
            if (m.get("binance_age_ms") or 0) > max_binance_age_ms:
                continue
            out.append(Row(float(m["ts_ms"]), m["fair"], m.get("fair_delta"), m["bid"], m["ask"],
                           bool(m["place_bid"]), bool(m["place_ask"]), b,
                           (m["book_bid"] + m["book_ask"]) / 2, bool(m.get("anchored", False))))
    out.sort(key=lambda r: r.ts)
    return out


def rolling_basis(rows: list[Row], half_window_ms: float, step: int = 25) -> list[float]:
    """Centred rolling median of book mid over Binance mid (bps), one value per row (computed every `step` rows)."""
    ts = [r.ts for r in rows]
    vals = [(r.book_mid / r.binance - 1) * 1e4 for r in rows]
    anchors, meds = [], []
    for i in range(0, len(rows), step):
        lo = bisect.bisect_left(ts, ts[i] - half_window_ms)
        hi = bisect.bisect_right(ts, ts[i] + half_window_ms)
        anchors.append(ts[i])
        meds.append(statistics.median(vals[lo:hi:max(1, (hi - lo) // 2000)]))
    return [meds[max(0, bisect.bisect_right(anchors, t) - 1)] for t in ts]


def score(rows: list[Row], basis: list[float], quotes, tol_bps: float, exposed_bps: float) -> dict:
    """quotes(row) -> (fair, bid or None, ask or None)."""
    gaps, n, eb, ea = [], 0, 0, 0
    rest_b = rest_a = None
    for r, bas in zip(rows, basis):
        fair, qb, qa = quotes(r)
        if fair is None:
            continue
        ref = r.binance * (1 + bas / 1e4)
        gaps.append(abs(fair / ref - 1) * 1e4)
        rest_b = None if qb is None else (qb if rest_b is None or abs(qb / rest_b - 1) * 1e4 > tol_bps else rest_b)
        rest_a = None if qa is None else (qa if rest_a is None or abs(qa / rest_a - 1) * 1e4 > tol_bps else rest_a)
        n += 1
        eb += rest_b is not None and (ref / rest_b - 1) * 1e4 < exposed_bps
        ea += rest_a is not None and (rest_a / ref - 1) * 1e4 < exposed_bps
    if not n:
        return {"samples": 0}
    gaps.sort()
    return {"samples": n, "gap_median_bps": statistics.median(gaps), "gap_p90_bps": gaps[int(0.9 * (len(gaps) - 1))],
            "exposed_bid_pct": 100 * eb / n, "exposed_ask_pct": 100 * ea / n}


def report(rows: list[Row], half_spread_bps: float, tol_bps: float, exposed_bps: float, window_min: float) -> dict:
    basis = rolling_basis(rows, window_min * 60_000 / 2)
    logged = score(rows, basis, lambda r: (r.fair, r.bid if r.place_bid else None, r.ask if r.place_ask else None),
                   tol_bps, exposed_bps)
    logged["one_sided_pct"] = 100 * sum(1 for r in rows if r.place_bid != r.place_ask) / len(rows)
    logged["anchored_pct"] = 100 * sum(r.anchored for r in rows) / len(rows)
    h = half_spread_bps / 1e4
    unanchored = score(rows, basis, lambda r: (r.fair_delta, r.fair_delta * (1 - h), r.fair_delta * (1 + h))
                       if r.fair_delta else (None, None, None), tol_bps, exposed_bps)
    return {"hours": (rows[-1].ts - rows[0].ts) / 3.6e6, "basis_median_bps": statistics.median(basis),
            "logged_fair": logged, "fair_delta": unanchored}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--symbol", default="ADAUSDT")
    ap.add_argument("--hours", type=float, default=0.0, help="only the last N hours (0 = the whole run)")
    ap.add_argument("--half-spread-bps", type=float, default=5.0, help="for the rebuilt fair_delta quotes")
    ap.add_argument("--requote-tol-bps", type=float, default=3.0)
    ap.add_argument("--exposed-bps", type=float, default=1.0)
    ap.add_argument("--basis-window-min", type=float, default=20.0)
    ap.add_argument("--max-binance-age-ms", type=float, default=5000.0, help="skip samples with an older Binance mid")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    paths = sorted(glob.glob(os.path.join(a.run_dir, "dry-run*.log*"))) or sorted(glob.glob(os.path.join(a.run_dir, "bot*.log*")))
    rows = load(paths, a.symbol, max_binance_age_ms=a.max_binance_age_ms)
    if a.hours > 0 and rows:
        cut = rows[-1].ts - a.hours * 3.6e6
        rows = [r for r in rows if r.ts >= cut]
    if len(rows) < 100:
        print(f"only {len(rows)} {a.symbol} samples with a Binance mid in {a.run_dir}", file=sys.stderr)
        return 2
    out = report(rows, a.half_spread_bps, a.requote_tol_bps, a.exposed_bps, a.basis_window_min)
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{a.symbol}: {out['hours']:.1f} h, basis median {out['basis_median_bps']:+.2f} bps "
          f"(reference = Binance x rolling {a.basis_window_min:g}-min median basis)")
    for name, s in (("logged fair", out["logged_fair"]), ("fair_delta (no anchor)", out["fair_delta"])):
        if not s.get("samples"):
            print(f"  {name:24s} not logged in this run")
            continue
        extra = (f"  one-sided {s['one_sided_pct']:.1f}%  anchored {s['anchored_pct']:.1f}%"
                 if "one_sided_pct" in s else "")
        print(f"  {name:24s} |fair-ref| median {s['gap_median_bps']:.2f} p90 {s['gap_p90_bps']:.2f} bps  "
              f"exposed bid {s['exposed_bid_pct']:.1f}% ask {s['exposed_ask_pct']:.1f}%{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
