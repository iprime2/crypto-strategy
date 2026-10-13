"""Sharpe sampling error for the repo rule: Lo (2002) SE and a stationary block bootstrap (mean block 20 d).
Input: hourly_lo_tv40.csv (hourly returns of the fixed rule at TV 0.40). Aggregates to daily (UTC), then windows.
Also: the weekly Monday series (D3) for comparison. Prints 1-SE, t-stat and 2.5/97.5 bootstrap percentiles."""
import sys, csv, math, random
import numpy as np
random.seed(7); np.random.seed(7)

def load_daily(path):
    rows = list(csv.reader(open(path)))
    hdr = rows[0]; body = rows[1:]
    # detect columns
    ti = 0
    ri = None
    for i, h in enumerate(hdr):
        if h.lower() in ("ret", "return", "r", "strategy", "hourly_ret", "ret_h"):
            ri = i
    if ri is None:
        ri = len(hdr) - 1
    daily = {}
    for r in body:
        ts = r[ti][:10]
        v = float(r[ri])
        daily[ts] = daily.get(ts, 0.0) + v   # hourly log-ish returns: sum ≈ compound for small values
    ds = sorted(daily)
    return np.array(ds), np.array([daily[d] for d in ds]), hdr, ri

def sharpe(x):
    return x.mean() / x.std(ddof=1) * math.sqrt(365) if x.std(ddof=1) > 0 else float('nan')

def lo_se(sr_ann, years):
    return math.sqrt((1 + 0.5 * sr_ann ** 2) / years)

def stat_boot(x, n=4000, mean_block=20):
    out = []
    N = len(x); p = 1.0 / mean_block
    for _ in range(n):
        idx = np.empty(N, dtype=int); i = np.random.randint(N)
        for k in range(N):
            if k == 0 or np.random.rand() < p:
                i = np.random.randint(N)
            else:
                i = (i + 1) % N
            idx[k] = i
        out.append(sharpe(x[idx]))
    return np.percentile(out, [2.5, 50, 97.5])

for path, label in [(sys.argv[1], "daily rule (D1/D2 base, TV 0.40)"), (sys.argv[2], "weekly Monday rule (D3 base, TV 0.40)")]:
    ds, r, hdr, ri = load_daily(path)
    print(f"\n=== {label}: file {path.split('/')[-1]} cols={hdr} ret_col={hdr[ri]} days={len(ds)} {ds[0]}..{ds[-1]}")
    for a, b, name in [("2020-05-01", "2026-09-30", "full 2020-05..2026-09"), ("2022-01-01", "2026-09-30", "OOS-ish 2022-01..2026-09"), ("2025-01-01", "2026-09-30", "recent 2025-01..2026-09"), ("2020-05-01", "2021-12-31", "2020-05..2021-12")]:
        m = (ds >= a) & (ds <= b)
        x = r[m]; yrs = len(x) / 365
        sr = sharpe(x); se = lo_se(sr, yrs)
        lo, med, hi = stat_boot(x)
        print(f"  {name:28s} days {len(x):4d} Sharpe {sr:5.2f}  Lo-SE {se:4.2f}  t={sr/se:4.1f}  block-boot 95% [{lo:5.2f}, {hi:5.2f}]  ann.vol {x.std(ddof=1)*math.sqrt(365)*100:4.1f}%  skew {((x-x.mean())**3).mean()/x.std()**3:5.2f}  kurt {((x-x.mean())**4).mean()/x.std()**4:5.1f}")
