#!/usr/bin/env python3
"""D1 design stats: scale the hourly long-only trend series by k and report CAGR/vol/Sharpe/DD, by-year,
worst/best days, intraday-loss day counts, and consistency-rule exposure. Also writes sub-period CSVs for prop_sim."""
import csv, math, sys, collections
import numpy as np
SRC = sys.argv[1]; OUT = sys.argv[2]
rows = list(csv.DictReader(open(SRC)))
ts = [r["ts_utc"] for r in rows]; ret = np.array([float(r["ret"]) for r in rows]); gross = np.array([float(r["gross"]) for r in rows])
days = [t[:10] for t in ts]
def stats(k, lo=None, hi=None, label=""):
    sel = np.array([(lo is None or d >= lo) and (hi is None or d <= hi) for d in days])
    r = k * ret[sel]; d = [x for x, s in zip(days, sel) if s]
    eq = np.cumprod(1 + r); n_h = len(r)
    # daily
    by_day = collections.OrderedDict()
    for x, dd in zip(r, d): by_day.setdefault(dd, []).append(x)
    dret = np.array([np.prod(1 + np.array(v)) - 1 for v in by_day.values()])
    intraday_low = np.array([np.min(np.cumprod(1 + np.array(v))) - 1 for v in by_day.values()])
    yrs = len(dret) / 365
    cagr = np.prod(1 + dret) ** (1 / yrs) - 1
    vol = dret.std(ddof=1) * math.sqrt(365); sharpe = dret.mean() / dret.std(ddof=1) * math.sqrt(365)
    deq = np.cumprod(1 + dret); mdd = (deq / np.maximum.accumulate(deq) - 1).min()
    hmdd = (eq / np.maximum.accumulate(eq) - 1).min()
    yearly = collections.OrderedDict()
    for x, dd in zip(dret, by_day.keys()): yearly[dd[:4]] = yearly.get(dd[:4], 1.0) * (1 + x)
    worst = sorted(zip(dret, by_day.keys()))[:3]; best = sorted(zip(dret, by_day.keys()))[-3:]
    print(f"\n[{label}] k={k:.2f} {d[0]}..{d[-1]} days={len(dret)}")
    print(f"  CAGR {cagr:+.1%}  vol {vol:.1%}  Sharpe {sharpe:.2f}  maxDD daily {mdd:.1%}  hourly {hmdd:.1%}  avg gross {k*gross[sel].mean():.2f}x")
    print("  by year: " + "  ".join(f"{y}:{v-1:+.1%}" for y, v in yearly.items()))
    print(f"  daily sd {dret.std(ddof=1):.2%}  worst days: " + ", ".join(f"{dd} {x:+.2%}" for x, dd in worst) + "  best: " + ", ".join(f"{dd} {x:+.2%}" for x, dd in best))
    for thr in (0.01, 0.015, 0.02, 0.03, 0.04):
        print(f"  intraday low < -{thr:.1%}: {(intraday_low < -thr).sum()} days ({(intraday_low < -thr).mean()*365:.1f}/yr); close < -{thr:.1%}: {(dret < -thr).sum()} days")
    print(f"  best day as share of a 10% target: {dret.max()/0.10:.0%} (40% consistency rule needs < 40%); days > +4%: {(dret > 0.04).sum()}")
    # longest time to make +10% from any start day (static), median over starts
    tt = []
    for i in range(len(deq) - 1):
        j = np.argmax(deq[i:] >= deq[i] * 1.10) if (deq[i:] >= deq[i] * 1.10).any() else -1
        tt.append(j if j > 0 else np.nan)
    tt = np.array(tt, dtype=float); ok = ~np.isnan(tt)
    print(f"  +10% reached (no rules) from {ok.mean():.0%} of start days; median {np.nanmedian(tt):.0f} d, p90 {np.nanpercentile(tt[ok],90):.0f} d")
for k in (0.35, 0.5, 0.6, 0.75, 1.0):
    stats(k, label="full")
for k in (0.5, 0.75):
    stats(k, "2022-01-01", "2023-12-31", "bear/chop 2022-23")
    stats(k, "2025-01-01", "2026-09-30", "recent 2025-26")
    stats(k, "2024-01-01", "2024-12-31", "2024")
# sub-period CSVs for prop_sim
for lo, hi, name in (("2025-01-01", "2026-09-30", "recent"), ("2022-01-01", "2023-12-31", "bear"), ("2024-01-01", "2026-09-30", "post2024")):
    with open(f"{OUT}/hourly_{name}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts_utc", "ret", "gross"])
        for r in rows:
            if lo <= r["ts_utc"][:10] <= hi: w.writerow([r["ts_utc"], r["ret"], r["gross"]])
    print(f"wrote {OUT}/hourly_{name}.csv")
