#!/usr/bin/env python3
"""Boundary margins at UNI-1 resets: turnover ratio of the last kept incumbent / last entrant vs the next-ranked coin, and the effect of
H = 17 (flip the rank-18 incumbent) -- how much a small turnover-data error could move the result."""
import sys
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
import numpy as np, data, sim, variants_universe as vu
P = vu.load_pool(); ctx = vu._ctx(P)
spec = vu.SPECS["UNI-1"]; inc = {}
rows = vu._reset_rows(ctx, False, "yearly")
for k, r in enumerate(rows):
    sel, rank = vu._select(ctx, r, inc, 9, 18, None if k == 0 else 365)
    order = sorted(rank, key=rank.get)
    cols = np.array(order)
    med = np.nanmedian(ctx.Qc[r - 29:r + 1][:, cols], axis=0)
    mq = {int(j): float(m) for j, m in zip(cols, med)}
    notes = []
    for j in sel:
        if j in inc and rank[j] > 9:   # incumbent kept by hysteresis
            nxt = [o for o in order if rank[o] == 19]
            if nxt:
                notes.append(f"kept {ctx.coins[j]}({rank[j]}) Q {mq[j]/1e6:.0f}M vs rank19 {ctx.coins[nxt[0]]} {mq[nxt[0]]/1e6:.0f}M (ratio {mq[j]/mq[nxt[0]]:.2f})" if rank[j] >= 16 else "")
    ent = [j for j in sel if j not in inc]
    out_best = [o for o in order if o not in sel]
    if ent and out_best and k > 0:
        lastin = max(ent, key=rank.get); firstout = min(out_best, key=rank.get)
        notes.append(f"last entrant {ctx.coins[lastin]}({rank[lastin]}) {mq[lastin]/1e6:.0f}M vs best non-member {ctx.coins[firstout]}({rank[firstout]}) {mq[firstout]/1e6:.0f}M ratio {mq[lastin]/mq[firstout]:.2f}")
    print(P.dates[r], "; ".join(n for n in notes if n))
    inc = {j: int(ctx.LIFE[r, j]) for j in sel}
for H in (16, 17, 18, 19, 20):
    res = []
    for cad in (vu.DAILY, vu.WEEKLY):
        ctx.cache.clear()
        U, log = vu._membership(ctx, cad, dict(N=9, H=H, age=365, reset="yearly"))
        r = vu._sim(ctx, vu._weights(ctx, cad, U), vu._kw(ctx, cad))
        res.append(f"{cad['name']} {sim.sharpe(r['rets']):.3f}/{sim.stats(r, vu.POST)['sharpe']:.3f}")
    print(f"H {H}: {' | '.join(res)}")
