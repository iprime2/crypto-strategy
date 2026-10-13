#!/usr/bin/env python3
"""Adversarial: Delta vs Binance alignment and Delta funding coverage."""
import sys, datetime as dt, json, math, statistics
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
bc, bf = tb.load_binance(f"{SP}/trend-cache", dt.date(2026, 9, 30))
dc, df = tb.load_delta(f"{SP}/trend-cache", dt.date(2026, 10, 12))
for c in tb.COINS:
    ds = [d for d in dc[c] if d in bc[c] and d >= dt.date(2024, 8, 10)]
    same = [1e4 * (dc[c][d] / bc[c][d] - 1) for d in ds]
    lag = [1e4 * (dc[c][d] / bc[c][d - dt.timedelta(1)] - 1) for d in ds if d - dt.timedelta(1) in bc[c]]
    r_d = [math.log(dc[c][d] / dc[c][d - dt.timedelta(1)]) for d in ds if d - dt.timedelta(1) in dc[c]]
    r_b = [math.log(bc[c][d] / bc[c][d - dt.timedelta(1)]) for d in ds if d - dt.timedelta(1) in dc[c]]
    corr = statistics.correlation(r_d, r_b)
    within20 = sum(1 for x in same if abs(x) <= 20) / len(same)
    fdays = sorted(df[c]); 
    print(f"{c:5s} days {len(ds)} | Delta/Binance same-day close diff: median {statistics.median(same):+6.1f} bps, MAD {statistics.median([abs(x) for x in same]):5.1f}, within 20 bps {within20:5.1%}, max |diff| {max(abs(x) for x in same):6.1f} | vs prior-day Binance close MAD {statistics.median([abs(x) for x in lag]):6.1f} | daily log-return corr {corr:.4f} | Delta funding days {fdays[0]}..{fdays[-1]}; mean daily funding Delta {statistics.mean([df[c][d] for d in ds if d in df[c]])*365:+.2%}/yr vs Binance {statistics.mean([bf[c].get(d,0) for d in ds])*365:+.2%}/yr")
# funding gap: days in the Delta window with no funding record
for c in ["BTC", "ETH", "DOGE"]:
    miss = [d for d in dc[c] if d >= dt.date(2024, 8, 10) and d not in df[c]]
    print(f"{c}: Delta trading days without a funding record: {len(miss)} ({miss[0] if miss else None}..{miss[-1] if miss else None})")
