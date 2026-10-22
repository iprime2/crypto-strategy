#!/usr/bin/env python3
"""Reproduce the published baselines with the numpy engine before any variant is run.
Targets (evidence/backtest_results.md T0, av_runs/av_universe_9.txt):
  9 coins daily TV0.40 2020-05-01..2026-09-30: Sharpe 1.25 CAGR +24.2% maxDD -21.9%, by year 53/47/-5/16/47/3/8
  9 coins weekly Sun-candle TV0.25 band10 cap1.0: Sharpe 1.12 CAGR +14.1% maxDD -16.9%
  24 ex-ante perps daily: Sharpe 0.86 CAGR +13.8%; weekly: 0.82 +8.8%
"""
import datetime as dt, sys, time
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools2")
import numpy as np
import data, sim, rules

t0 = time.time()
P = data.load_binance()
print(f"loaded {len(P.dates)} days x {len(P.coins)} coins in {time.time()-t0:.1f}s")
start, end = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
for label, coins in [("9 coins", data.NINE), ("24 ex-ante", data.EXANTE24)]:
    p = P.sub(coins)
    W = rules.baseline_weights(p.C, tv=0.40)
    r = sim.simulate(p, W, start=start, end=end)
    print(sim.line(f"{label} daily TV0.40", sim.stats(r)))
    Wk = rules.baseline_weights(p.C, tv=0.25, max_gross=1.0)
    rk = sim.simulate(p, Wk, decide=rules.decide_weekly(p.dates, 6), band=0.10, start=start, end=end)
    print(sim.line(f"{label} weekly Sun TV0.25 band10", sim.stats(rk)))
    s = sim.stats(r, dt.date(2022, 1, 1))
    print(f"   daily 2022-26: Sharpe {s['sharpe']:.2f} CAGR {s['cagr']:+.1%} DD {s['mdd']:.1%}")
    sk = sim.stats(rk, dt.date(2022, 1, 1))
    print(f"   weekly 2022-26: Sharpe {sk['sharpe']:.2f} CAGR {sk['cagr']:+.1%} DD {sk['mdd']:.1%}")
# exact cross-check against the repo function on 9 coins
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
tb.COINS = data.NINE
close, fund = tb.load_binance(data.SP + "/trend-cache", end)
ref = tb.backtest(close, fund, start, end, long_only=True)
p9 = P.sub(data.NINE)
W = rules.baseline_weights(p9.C, tv=0.40)
r9 = sim.simulate(p9, W, start=start, end=end)
print(f"repo: Sharpe {ref['sharpe']:.4f} CAGR {ref['cagr']:+.4%} DD {ref['mdd']:.4%} | engine: Sharpe {sim.sharpe(r9['rets']):.4f} CAGR {sim.cagr(r9['rets']):+.4%} DD {sim.maxdd(r9['rets']):.4%}")
a = np.array(ref["rets"]); b = r9["rets"]
print(f"max |daily return diff| = {np.abs(a - b).max():.2e} over {len(a)} vs {len(b)} days")
D = data.load_delta()
pd_ = D.sub(data.NINE)
W = rules.baseline_weights(pd_.C, tv=0.40)
r = sim.simulate(pd_, W, start=dt.date(2024, 8, 10), end=dt.date(2026, 10, 12))
print(sim.line("Delta 9 daily TV0.40 2024-08-10..2026-10-12", sim.stats(r)), " (ref: Sharpe 0.99 CAGR +16.5% DD -14.1%)")
Wk = rules.baseline_weights(pd_.C, tv=0.25, max_gross=1.0)
rk = sim.simulate(pd_, Wk, decide=rules.decide_weekly(pd_.dates, 6), band=0.10, start=dt.date(2024, 8, 10), end=dt.date(2026, 10, 12))
print(sim.line("Delta 9 weekly TV0.25 band10", sim.stats(rk)), " (ref unrounded: Sharpe 0.70 CAGR +7.0% DD -9.1%)")
rk2 = sim.simulate(pd_, Wk, decide=rules.decide_weekly(pd_.dates, 6), band=0.10, capital=1000.0, start=dt.date(2024, 8, 10), end=dt.date(2026, 10, 12))
print(sim.line("Delta 9 weekly TV0.25 band10 $1000", sim.stats(rk2)), " (ref: Sharpe 0.81 CAGR +8.3% DD -9.5%)")
print(f"total {time.time()-t0:.1f}s")
