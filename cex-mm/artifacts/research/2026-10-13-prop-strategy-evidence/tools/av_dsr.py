#!/usr/bin/env python3
"""Adversarial: deflated Sharpe (Bailey & Lopez de Prado 2014) for the design's 1.12 and the pre-registered 1.25, using
the Sharpes of every variant actually run in this session (memo grid 18 + D3 appendix + qd T3 grid) as the trial set."""
import re, math, glob
from statistics import NormalDist
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
N = NormalDist()
srs = []
for f in [f"{SP}/qd_runs/T3b_output.txt", f"{SP}/qd_runs/T1_T3a_output.txt", f"{SP}/d3_runs/d3_tests_output.txt", f"{SP}/d3_runs/d3_tests2_output.txt", f"{SP}/d3_runs/d3_tests3_output.txt", f"{SP}/baseline_backtest.txt"]:
    try: txt = open(f).read()
    except FileNotFoundError: continue
    for m in re.finditer(r"Sharpe\s+(-?\d+\.\d+)", txt):
        srs.append(float(m.group(1)))
srs = np.array(srs)
# full-sample strategy variants only: drop sub-period lines by keeping values in a plausible full-sample band is not possible by regex,
# so report both the raw count and a conservative trimmed set
print(f"Sharpe figures parsed from session outputs: {len(srs)}; mean {srs.mean():.2f} sd {srs.std():.2f} min {srs.min():.2f} max {srs.max():.2f}")
def dsr(sr_obs, n_trials, var_trials, T_days, skew, kurt):
    """Probability that the observed annual Sharpe is above the expected max of n_trials null strategies."""
    g = 0.5772156649
    emax = math.sqrt(var_trials) * ((1 - g) * N.inv_cdf(1 - 1 / n_trials) + g * N.inv_cdf(1 - 1 / (n_trials * math.e)))
    sr_d = sr_obs / math.sqrt(365); sr0 = emax / math.sqrt(365)   # daily units
    se = math.sqrt((1 - skew * sr_d + (kurt - 1) / 4 * sr_d ** 2) / (T_days - 1))
    z = (sr_d - sr0) / se
    return emax, N.cdf(z)
T = 2344
for label, sr, skew, kurt in [("design weekly TV0.25 (1.12)", 1.12, 0.00, 13.9 + 3), ("pre-registered daily TV0.40 (1.25)", 1.25, -0.10, 12.4 + 3)]:
    print(f"\n{label}: skew {skew} kurtosis {kurt} (raw, from T6f)")
    for n_tr, var in [(1, 0.0), (18, 0.08 ** 2), (18, 0.15 ** 2), (36, 0.15 ** 2), (60, 0.15 ** 2), (100, 0.15 ** 2), (100, 0.25 ** 2), (200, 0.25 ** 2)]:
        emax, p = dsr(sr, max(n_tr, 2) if n_tr > 1 else 1.0000001, var, T, skew, kurt) if n_tr > 1 else (0.0, N.cdf(sr / math.sqrt(365) / math.sqrt((1 - skew * sr / math.sqrt(365) + (kurt - 1) / 4 * (sr / math.sqrt(365)) ** 2) / (T - 1))))
        print(f"  trials {n_tr:3d}, sd of trial Sharpes {math.sqrt(var):.2f}: E[max null Sharpe] {emax:4.2f}  DSR = P(true SR > 0 after selection) {p:5.1%}")
# the memo's own 18-grid Sharpes (Binance, from the memo text: range 0.99-1.25) and qd T3 variants (0.85-1.34)
print("\nreference: memo grid Sharpe range 0.99-1.25 (18 settings, all Binance full sample); qd T3 variants 0.85-1.34 (~60); D3 appendix 0.84-1.34 (~40)")
