#!/usr/bin/env python3
"""Prop-rules verifier: per-coin weight distribution of the repo rule at native TV 0.40 (prop leg k=0.5 -> x0.5),
against HyroTrader's 25% max exposure per position and 3% max risk per trade (with a 25% stop), and Breakout's
5x leverage cap. Read-only use of cex-mm/scripts/trend_backtest.py and the scratchpad cache."""
import sys, datetime as dt, math, collections
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
close, fund = tb.load_binance(f"{SP}/trend-cache", dt.date(2026, 9, 30))
days = sorted(set().union(*[set(v) for v in close.values()]))
start, end = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
maxw, grossl, rows = [], [], []
for d in days:
    if not (start <= d <= end):
        continue
    w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, 0.40, True)
    if not w:
        continue
    g = sum(w.values()); mw = max(w.values()); mc = max(w, key=w.get)
    maxw.append(mw); grossl.append(g); rows.append((d, mc, mw, g))
import numpy as np
mw = np.array(maxw); g = np.array(grossl)
for k, lab in [(1.0, "native TV 0.40"), (0.5, "prop leg k=0.5 (TV 0.20)"), (0.625, "own leg TV 0.25")]:
    x = mw * k
    print(f"{lab}: max single-coin weight: max {x.max():.1%} p99 {np.percentile(x, 99):.1%} p90 {np.percentile(x, 90):.1%} median {np.median(x):.1%}; "
          f"days > 25%: {(x > 0.25).sum()} of {len(x)}; days > 10%: {(x > 0.10).sum()}; gross max {(g * k).max():.2f}x mean {(g * k).mean():.2f}x")
top = sorted(rows, key=lambda r: -r[2])[:8]
print("largest single-coin weights (native):", [(str(d), c, f"{w:.1%}", f"gross {gg:.2f}") for d, c, w, gg in top])
# risk per trade with a 25% stop at k=0.5
x = mw * 0.5
print(f"k=0.5, 25% stop: risk per trade = weight x 25%: max {x.max() * 0.25:.2%} p99 {np.percentile(x, 99) * 0.25:.2%}; 3% rule breached on {(x * 0.25 > 0.03).sum()} days")
# number of coins with a position per day (HyroTrader stop orders needed per rebalance)
cnt = collections.Counter()
for d in days:
    if start <= d <= end:
        w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, 0.40, True)
        cnt[sum(1 for v in w.values() if v > 0)] += 1
print("positions per day (count of coins long):", dict(sorted(cnt.items())))
