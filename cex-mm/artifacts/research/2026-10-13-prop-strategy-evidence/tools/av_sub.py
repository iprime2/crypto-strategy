#!/usr/bin/env python3
"""Adversarial: sample dependence of the design line. Daily aggregation of the hourly CSVs; Sharpe by year, leave-one-year-out,
ex-2020-21, ex-2020-21-2024, and the vol-scaled always-long basket on the same windows."""
import csv, math, collections, sys
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
def daily(path):
    by = collections.OrderedDict()
    for r in csv.DictReader(open(path)):
        d = r["ts_utc"][:10]; by[d] = by.get(d, 1.0) * (1 + float(r["ret"]))
    ds = list(by); x = np.array([by[d] - 1 for d in ds]); return np.array(ds), x
def sh(x): return x.mean() / x.std(ddof=1) * math.sqrt(365)
def cagr(x): return math.prod(1 + v for v in x) ** (365 / len(x)) - 1
def mdd(x):
    e = np.cumprod(1 + x); return (e / np.maximum.accumulate(e) - 1).min()
files = {"design weekly Mon TV0.25 band10": f"{SP}/qd_runs/hourly_design_weekly_tv25_band10.csv",
         "baseline daily TV0.40": f"{SP}/qd_runs/hourly_daily_tv40.csv",
         "always-long basket weekly TV0.25": f"{SP}/qd_runs/hourly_alwayslong_weekly_tv25.csv"}
for name, p in files.items():
    ds, x = daily(p); yrs = np.array([int(d[:4]) for d in ds])
    print(f"\n=== {name}: {len(x)} days {ds[0]}..{ds[-1]} Sharpe {sh(x):.2f} CAGR {cagr(x):+.1%} maxDD {mdd(x):.1%}")
    print("  by year Sharpe/CAGR: " + "  ".join(f"{y}:{sh(x[yrs==y]):.2f}/{cagr(x[yrs==y]):+.0%}" for y in sorted(set(yrs))))
    for lab, m in [("ex 2020-21", (yrs >= 2022)), ("ex 2020-21 & 2024", (yrs >= 2022) & (yrs != 2024)), ("ex 2024", yrs != 2024),
                   ("2022-23 only", (yrs == 2022) | (yrs == 2023)), ("2025-26 only", yrs >= 2025), ("2022-26", yrs >= 2022), ("2023-26", yrs >= 2023)]:
        print(f"  {lab:20s} days {m.sum():4d} Sharpe {sh(x[m]):5.2f} CAGR {cagr(x[m]):+6.1%} maxDD {mdd(x[m]):6.1%} total {math.prod(1+x[m])-1:+.1%}")
    print("  leave-one-year-out Sharpe: " + "  ".join(f"-{y}:{sh(x[yrs!=y]):.2f}" for y in sorted(set(yrs))))
    # share of total log return from each year
    lr = np.log1p(x); tot = lr.sum()
    print("  share of total log-return by year: " + "  ".join(f"{y}:{lr[yrs==y].sum()/tot:+.0%}" for y in sorted(set(yrs))))
# rule minus basket (signal contribution) on same windows
d1, r = daily(files["design weekly Mon TV0.25 band10"]); d2, b = daily(files["always-long basket weekly TV0.25"])
assert (d1 == d2).all()
yrs = np.array([int(d[:4]) for d in d1])
print("\n=== signal contribution: rule vs always-long basket (same TV/cadence/costs); basket scaled to the rule's vol ===")
for lab, m in [("full", yrs > 0), ("2020-21", yrs <= 2021), ("2022-26", yrs >= 2022), ("2024-26", yrs >= 2024), ("2025-26", yrs >= 2025)]:
    bs = b[m] * (r[m].std() / b[m].std())
    print(f"  {lab:8s} rule Sharpe {sh(r[m]):5.2f} CAGR {cagr(r[m]):+6.1%} DD {mdd(r[m]):6.1%} | basket Sharpe {sh(b[m]):5.2f} CAGR {cagr(b[m]):+6.1%} DD {mdd(b[m]):6.1%} | basket at rule vol CAGR {cagr(bs):+6.1%} | corr {np.corrcoef(r[m], b[m])[0,1]:.2f} | rule-basket(volmatched) Sharpe {sh(r[m]-bs):5.2f}")
