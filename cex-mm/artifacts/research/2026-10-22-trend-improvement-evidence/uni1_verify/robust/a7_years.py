"""Extra: leave-one-year-out deltas, vol-matched yearly return differences, rolling 365-day Sharpe differences."""
from common import *
c = ctx()
for name, cad in CADS.items():
    U, _ = U_uni1(c, cad); r = run(c, cad, W_of(c, cad, U)); b = run(c, cad, W_of(c, cad, U_static24(c)))
    d = np.array(r["dates"]); yrs = np.array([q.year for q in d]); x, y = r["rets"], b["rets"]
    k = (y.std(ddof=1) / x.std(ddof=1))
    print(f"\n=== {name}: full-period vol ratio static24/UNI-1 = {k:.3f}")
    print(" year | vol-matched UNI-1 ret - static24 ret | mean daily diff (bps, vol-matched)")
    for yy in sorted(set(yrs)):
        m = yrs == yy
        print(f"  {yy}: {np.prod(1 + k * x[m]) - np.prod(1 + y[m]):+.1%} | {(k * x[m] - y[m]).mean()*1e4:+.2f}")
    post = d >= POST
    print(" leave-one-year-out (FULL and POST Sharpe delta with that calendar year removed):")
    for yy in sorted(set(yrs)):
        m = yrs != yy
        mp = m & post
        print(f"  -{yy}: FULL d {sim.sharpe(x[m]) - sim.sharpe(y[m]):+.3f} | POST d {sim.sharpe(x[mp]) - sim.sharpe(y[mp]):+.3f}" if yy >= 2022 else f"  -{yy}: FULL d {sim.sharpe(x[m]) - sim.sharpe(y[m]):+.3f}")
    # 2023+2024 removed together
    m = ~np.isin(yrs, [2023, 2024]) & post
    print(f"  -2023-24 together: POST d {sim.sharpe(x[m]) - sim.sharpe(y[m]):+.3f}; POST 2025-26 only: {sim.sharpe(x[yrs >= 2025]) - sim.sharpe(y[yrs >= 2025]):+.3f}")
    # rolling 365-day Sharpe difference
    W = 365; diffs = []
    for i in range(W, len(x) + 1, 7):
        diffs.append((d[i - 1], sim.sharpe(x[i - W:i]) - sim.sharpe(y[i - W:i]), np.prod(1 + k * x[i - W:i]) - np.prod(1 + y[i - W:i])))
    dd = np.array([v for _, v, _ in diffs]); dr = np.array([v for _, _, v in diffs])
    pm = np.array([q >= dt.date(2022, 12, 31) for q, _, _ in diffs])
    print(f" rolling 365d windows (weekly step): Sharpe diff > 0 in {np.mean(dd > 0):.0%} (all), {np.mean(dd[pm] > 0):.0%} (windows ending 2023+); vol-matched return diff > 0 in {np.mean(dr > 0):.0%} / {np.mean(dr[pm] > 0):.0%}")
    print(f"   rolling Sharpe diff p10/50/90: {np.percentile(dd, 10):+.2f} {np.percentile(dd, 50):+.2f} {np.percentile(dd, 90):+.2f}")
