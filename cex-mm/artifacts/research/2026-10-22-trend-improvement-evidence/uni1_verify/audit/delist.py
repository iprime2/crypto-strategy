#!/usr/bin/env python3
"""(2) Delisting / zombie / gap audit for the coins UNI-1 ever holds, plus where LUNA/FTT/SRM and other blow-ups ranked at each reset."""
import sys, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data, sim, rules
import variants_universe as vu
from base import build

P, ctx, out = build()
T = len(P.dates)
a0, a1 = P.idx[vu.A0], P.idx[vu.A1]

for name, o in out.items():
    ev = vu.delisting_events(ctx, o["U"], o["r"], o["W"], o["kw"]["decide"])
    print(f"== {name}: delisting events of U members inside the window: {len(ev)}")
    for e in ev:
        print("  ", vu._ev_line(e))
    # every coin ever in U: lives, delisting rows (LAST) anywhere, zero-Q rows, missing rows, frozen rows inside held stretches
    held_cols = np.flatnonzero(o["U"].any(axis=0))
    W = o["W"]
    print(f"   coins ever in U: {[ctx.coins[j] for j in held_cols]}")
    for j in held_cols:
        c = ctx.coins[j]
        inU = o["U"][:, j]
        rowsU = np.flatnonzero(inU)
        fin = np.isfinite(P.C[:, j]); q0 = fin & ~ctx.pos[:, j]
        last = np.flatnonzero(ctx.LAST[:, j] & (np.arange(T) < T - 1))
        # missing rows (no kline) between first and last finite row inside the window
        f = np.flatnonzero(fin)
        miss = [t for t in range(max(f[0], a0), min(f[-1], a1) + 1) if not fin[t]]
        miss_inU = [t for t in miss if inU[t] or (t > 0 and inU[t - 1])]
        frozen = [t for t in range(max(f[0] + 1, a0), min(f[-1], a1) + 1) if ctx.pos[t, j] and P.C[t, j] == P.C[t - 1, j] and P.H[t, j] == P.L[t, j]]
        lowq = [t for t in range(a0, a1 + 1) if ctx.pos[t, j] and inU[t] and P.Q[t, j] < 1e6]
        wdays = int((W[a0:a1 + 1, j] != 0).sum())
        print(f"   {c:9s} U rows {len(rowsU):5d} ({P.dates[rowsU[0]]}..{P.dates[rowsU[-1]]}) W!=0 days {wdays:5d} lives {ctx.LIFE[:, j].max()} "
              f"LAST rows {[str(P.dates[t]) for t in last]} zeroQ rows {int(q0.sum())} (in window {int(q0[a0:a1+1].sum())}) "
              f"missing rows in window {len(miss)} ({len(miss_inU)} while in U: {[str(P.dates[t]) for t in miss_inU][:12]}) "
              f"frozen-with-Q>0 {len(frozen)} Q<$1M while in U {len(lowq)}")

# what the MATIC end looks like
for c in ("MATIC", "POL", "EOS", "XTZ"):
    j = P.ci[c]
    f = np.flatnonzero(np.isfinite(P.C[:, j]))
    lastpos = np.flatnonzero(ctx.pos[:, j])[-1]
    print(f"\n{c}: first {P.dates[f[0]]} last finite {P.dates[f[-1]]} last Q>0 {P.dates[lastpos]}")
    for t in range(lastpos - 4, min(lastpos + 4, T)):
        print(f"   {P.dates[t]} O {P.O[t,j]:.5g} H {P.H[t,j]:.5g} L {P.L[t,j]:.5g} C {P.C[t,j]:.5g} Q {P.Q[t,j]:.4g} F {P.F[t,j]:.6f} "
              f"W_d {out['daily']['W'][t,j]:.4f} W_w {out['weekly']['W'][t,j]:.4f} U_d {out['daily']['U'][t,j]}")

# blow-up names: where they ranked at each reset (eligible list rank and shadow rank without age floor) and whether they could enter
print("\nReset ranks of blow-up / delisted high-turnover names (daily resets, eligible-list rank; '-' = not eligible):")
spec = vu.SPECS["UNI-1"]
rows = vu._reset_rows(ctx, False, "yearly")
inc = {}
names = ["LUNA", "FTT", "SRM", "LUNC", "1000LUNC", "UST", "USTC", "ANC", "WAVES", "BTCST", "CVC", "MATIC", "FTM", "ADA", "DOT", "SOL", "AVAX", "DOGE", "1000SHIB", "SHIB", "XTZ", "EOS"]
for k, r in enumerate(rows):
    sel, rank = vu._select(ctx, r, inc, spec["N"], spec["H"], None if k == 0 else spec["age"])
    # shadow with no age floor
    _, rank_noage = vu._select(ctx, r, inc, spec["N"], spec["H"], None)
    s = []
    for c in names:
        if c not in P.ci:
            continue
        j = P.ci[c]
        s.append(f"{c}:{rank.get(j, '-')}/{rank_noage.get(j, '-')}(age {ctx.AGE[r, j]})")
    top = sorted(rank, key=rank.get)[:12]
    print(f"  {P.dates[r]} top12 eligible: {' '.join(f'{ctx.coins[j]}({rank[j]})' for j in top)}")
    print(f"      {' '.join(s)}")
    inc = {j: int(ctx.LIFE[r, j]) for j in sel}

# LUNA, FTT, SRM lives and ends
for c in ("LUNA", "FTT", "SRM", "1000LUNC", "WAVES"):
    if c not in P.ci:
        print(c, "not in pool"); continue
    j = P.ci[c]
    lastpos = np.flatnonzero(ctx.pos[:, j])
    f = np.flatnonzero(np.isfinite(P.C[:, j]))
    print(f"{c}: first close {P.dates[f[0]]}, last finite {P.dates[f[-1]]}, last Q>0 {P.dates[lastpos[-1]]} close {P.C[lastpos[-1], j]:.6g}, "
          f"lives {ctx.LIFE[:, j].max()}, zero-Q rows {int((np.isfinite(P.C[:, j]) & ~ctx.pos[:, j]).sum())}, ever in UNI-1 U: {bool(out['daily']['U'][:, j].any())}")
