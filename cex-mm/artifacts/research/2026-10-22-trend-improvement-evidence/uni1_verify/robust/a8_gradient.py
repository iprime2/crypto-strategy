"""Extra: liquidity gradient. Deterministic universes from the eligible list each January (no hysteresis): ranks 1-9, 10-18, 19-27, 28-36."""
from common import *
c = ctx()
def ranked(cad, lo, hi):
    rows = vu._reset_rows(c, cad["weekly"], "yearly")
    U = np.zeros((c.T, c.N), bool); inc = {}; log = []
    for k, r in enumerate(rows):
        floor = None if k == 0 else 365
        base = c.pos[r] & ~c.excl & (c.AGE[r] >= vu.MED_WIN)
        inc_ok = np.zeros(c.N, bool)
        for j, L in inc.items():
            inc_ok[j] = base[j] and c.LIFE[r, j] == L
        elig = (base & (c.AGE[r] >= floor)) if floor else base.copy()
        elig |= inc_ok
        cols = np.flatnonzero(elig)
        med = np.nanmedian(c.Qc[max(r - vu.MED_WIN + 1, 0):r + 1][:, cols], axis=0)
        order = [int(j) for _, _, j in sorted(zip(-med, [c.coins[j] for j in cols], cols))]
        sel = order[lo - 1:hi]
        inc = {j: int(c.LIFE[r, j]) for j in sel}
        end = rows[k + 1] if k + 1 < len(rows) else c.T
        for j, L in inc.items():
            U[r:end, j] = c.LIFE[r:end, j] == L
        log.append((str(c.dates[r]), [str(c.coins[j]) for j in sel]))
    return U, log
for name, cad in CADS.items():
    b = run(c, cad, W_of(c, cad, U_static24(c)))
    print(f"\n=== {name}: static-24 FULL {sh(b):.3f} POST {sh(b, POST):.3f}")
    for lo, hi in ((1, 9), (10, 18), (19, 27), (28, 36), (1, 4), (5, 9)):
        U, lg = ranked(cad, lo, hi); r = run(c, cad, W_of(c, cad, U))
        print(f"  ranks {lo:2d}-{hi:2d}: FULL {sh(r):.3f} POST {sh(r, POST):.3f} (d {sh(r, POST)-sh(b, POST):+.3f}) | 2022/2024 sets: {','.join(lg[2][1])} / {','.join(lg[4][1])}")
