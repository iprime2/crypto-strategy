"""Extra robustness: (a) yearly reset date shifted by k days (start 2020-04-30 fixed); (b) N = 6..12 with H = 2N; (c) turnover window 14/30/60/90."""
from common import *
c = ctx()
def membership_rows(cad, rows, N=9, H=18, age=365):
    U = np.zeros((c.T, c.N), bool); inc = {}; log = []
    for k, r in enumerate(rows):
        sel, _ = vu._select(c, r, inc, N, H, None if k == 0 else age)
        inc = {int(j): int(c.LIFE[r, j]) for j in sel}
        end = rows[k + 1] if k + 1 < len(rows) else c.T
        for j, L in inc.items():
            U[r:end, j] = c.LIFE[r:end, j] == L
        log.append((str(c.dates[r]), [str(c.coins[j]) for j in sel]))
    return U, log
out = {}
for name, cad in CADS.items():
    b = run(c, cad, W_of(c, cad, U_static24(c))); sb, sbp = sh(b), sh(b, POST)
    base_rows = vu._reset_rows(c, cad["weekly"], "yearly")
    print(f"\n=== {name}: static-24 FULL {sb:.3f} POST {sbp:.3f}")
    print(" (a) reset shift (days; weekly in whole weeks so the reset stays a decision Sunday):")
    shifts = (-28, -21, -14, -7, 0, 7, 14, 21, 28, 42, 56)
    vals = []
    for s in shifts:
        rows = [base_rows[0]] + [r + s for r in base_rows[1:] if 0 <= r + s < c.T]
        U, lg = membership_rows(cad, rows); r_ = run(c, cad, W_of(c, cad, U))
        vals.append((s, sh(r_) - sb, sh(r_, POST) - sbp))
        sets = {d: m for d, m in lg[2:]}
        print(f"   {s:+3d}d: FULL {sh(r_):.3f} (d {sh(r_)-sb:+.3f}) POST {sh(r_, POST):.3f} (d {sh(r_, POST)-sbp:+.3f}) | 2022+ members: {' / '.join(d[2:7] + ':' + ','.join(m) for d, m in lg[2:])}")
    out[f"{name}|shift"] = vals
    print(" (b) N sweep (H = 2N):")
    for N in range(5, 13):
        U, lg = membership_custom(c, cad, N=N, H=2 * N); r_ = run(c, cad, W_of(c, cad, U))
        bt = boot(r_, b, POST, None, r_)
        print(f"   N={N:2d}: FULL {sh(r_):.3f} (d {sh(r_)-sb:+.3f}) POST {sh(r_, POST):.3f} (d {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P {bt[3]:.2f})")
        out[f"{name}|N{N}"] = (sh(r_) - sb, sh(r_, POST) - sbp)
    print(" (c) turnover median window:")
    saved = vu.MED_WIN
    try:
        for mw in (14, 30, 60, 90):
            vu.MED_WIN = mw
            U, lg = membership_custom(c, cad); r_ = run(c, cad, W_of(c, cad, U))
            print(f"   win {mw:2d}: FULL {sh(r_):.3f} (d {sh(r_)-sb:+.3f}) POST {sh(r_, POST):.3f} (d {sh(r_, POST)-sbp:+.3f}) | 2024+: {' / '.join(d[2:4] + ':' + ','.join(m) for d, m in lg[4:])}")
            out[f"{name}|win{mw}"] = (sh(r_) - sb, sh(r_, POST) - sbp)
    finally:
        vu.MED_WIN = saved
json.dump(out, open(f"{OUT}/a6.json", "w"), default=float)
