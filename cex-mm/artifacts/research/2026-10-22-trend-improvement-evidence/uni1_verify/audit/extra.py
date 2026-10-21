#!/usr/bin/env python3
"""Extra checks: (a) Q vs V*C consistency for every coin ranked <= 30 at a reset (turnover-rank data sanity); (b) the simulator's one-row
delisting/gap look-ahead in the static-24 arm; (c) funding-imputation effect on the static-24 arm; (d) bootstrap of the POST delta on the
gap-patched panel."""
import sys, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data, sim
import variants_universe as vu
from base import build

P, ctx, out = build()
T = len(P.dates)
# (a)
print("(a) Q/(V*C) at reset rows for coins ranked <= 30 (30-row medians):")
worst = []
for weekly in (False, True):
    for r in vu._reset_rows(ctx, weekly, "yearly"):
        _, rank = vu._select(ctx, r, {}, 9, 18, None)
        for j, k in rank.items():
            if k > 30:
                continue
            sl = slice(max(r - 29, 0), r + 1)
            q = np.nanmedian(ctx.Qc[sl, j]); vc = np.nanmedian((P.V[sl, j] * P.C[sl, j])[ctx.pos[sl, j]])
            worst.append((abs(np.log(q / vc)), str(P.dates[r]), ctx.coins[j], k, q / vc))
worst.sort(reverse=True)
print("   largest |log(Q/(V*C))|:", [(d, c, k, round(x, 3)) for _, d, c, k, x in worst[:8]])

# (b) static-24 forced flattens (C[t] finite, C[t+1] NaN while held)
for name, o in out.items():
    b = o["b"]; Ws = o["Ws"]
    ev = []
    for j in np.flatnonzero(np.abs(Ws).sum(axis=0) > 0):
        for t in range(1, T - 1):
            if (Ws[t, j] != 0 or Ws[t - 1, j] != 0) and np.isfinite(ctx.Cc[t, j]) and not np.isfinite(ctx.Cc[t + 1, j]) and vu.A0 <= P.dates[t] <= vu.A1:
                nxt = t + 1
                while nxt < T and not np.isfinite(ctx.Cc[nxt, j]):
                    nxt += 1
                ev.append((ctx.coins[j], str(P.dates[t]), round(float(Ws[t - 1, j]), 4), str(P.dates[nxt]) if nxt < T else None,
                           round(float(ctx.Cc[nxt, j] / ctx.Cc[t, j] - 1), 4) if nxt < T else None))
    print(f"(b) static-24 {name}: forced flattens on held/targeted rows: {ev}")

# (c) funding imputation on the static-24 arm (same rule as funding.py)
for name, o in out.items():
    for lab, r in (("UNI-1", o["r"]), ("static-24", o["b"])):
        cols = r["cols"]; cp = r["coin_pnl"]; dates = r["dates"]
        jb, je = P.ci["BTC"], P.ci["ETH"]
        adj = r["rets"].copy(); n = 0
        for k, c in enumerate(cols):
            j = P.ci[c]
            for i, d in enumerate(dates):
                if cp[i, k] != 0 and P.F[P.idx[d], j] == 0:
                    t = P.idx[d]
                    ref = np.mean([x for x in (P.F[t, jb], P.F[t, je]) if x != 0] or [0.0003])
                    px0, px1 = P.C[t - 1, j], P.C[t, j]
                    expo = cp[i, k] / (px1 / px0 - 1) if px1 != px0 else 0.0
                    adj[i] -= expo * ref; n += 1
        print(f"(c) {name} {lab}: imputed {n} coin-days, Sharpe {sim.sharpe(r['rets']):.4f} -> {sim.sharpe(adj):.4f}")
