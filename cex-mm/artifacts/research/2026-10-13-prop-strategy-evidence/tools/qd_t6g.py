"""[post hoc] T6g: probability that the design's -20% kill (and -15%) fires on path luck. Stationary block bootstrap (mean block 20 d,
day-aligned) of the design's daily returns (weekly Mon TV 0.25 band 10%), 4000 paths x 1/2/3 years; max drawdown on daily closes
(hourly adds ~0.5-1 pp). Three drifts: as-is (Sharpe 1.13), mean shifted to Sharpe 0.7 and 0.5 (D3's forward range), and 0."""
import csv, math, collections, numpy as np
rng = np.random.default_rng(7)
by = collections.OrderedDict()
for r in csv.DictReader(open("qd_runs/hourly_design_weekly_tv25_band10.csv")):
    by.setdefault(r["ts_utc"][:10], []).append(float(r["ret"]))
x = np.array([math.prod(1 + v for v in vals) - 1 for vals in by.values()]); N = len(x)
sd = x.std(ddof=1); sr0 = x.mean() / sd * math.sqrt(365)
def boot(n, L, p=1 / 20):
    out = np.empty((n, L), dtype=int)
    for i in range(n):
        k = 0
        while k < L:
            s = rng.integers(N); l = rng.geometric(p); seg = np.arange(s, min(s + l, N)); take = min(len(seg), L - k)
            out[i, k:k + take] = seg[:take]; k += take
    return out
print(f"design daily series: {N} days, Sharpe {sr0:.2f}, ann vol {sd*math.sqrt(365):.1%}")
print(f"{'drift':>14} {'horizon':>8} | {'P(DD<=-15%)':>11} {'P(DD<=-20%)':>11} {'P(DD<=-25%)':>11} | {'median DD':>9} {'p90 DD':>7} | {'P(total<0)':>10} {'median ret':>10}")
for label, sr in (("as-is", sr0), ("Sharpe 0.7", 0.7), ("Sharpe 0.5", 0.5), ("Sharpe 0.0", 0.0)):
    shift = (sr - sr0) * sd / math.sqrt(365)
    for yrs in (1, 2, 3):
        L = 365 * yrs; ip = boot(4000, L); paths = x[ip] + shift
        eq = np.cumprod(1 + paths, axis=1); peak = np.maximum.accumulate(eq, axis=1); dd = (eq / peak - 1).min(axis=1); tot = eq[:, -1] - 1
        print(f"{label:>14} {yrs:>6} y | {(dd <= -0.15).mean():11.1%} {(dd <= -0.20).mean():11.1%} {(dd <= -0.25).mean():11.1%} | {np.median(dd):9.1%} {np.percentile(dd, 10):7.1%} | {(tot < 0).mean():10.1%} {np.median(tot):+10.1%}")
