#!/usr/bin/env python3
"""Sanity of the gap patch (filled rows continuous with neighbours; only those rows differ) and attribution: Feb/Apr-2022 rows vs DASH Oct-2022."""
import sys, io, contextlib, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np, data, sim, variants_universe as vu
with contextlib.redirect_stdout(io.StringIO()):
    import patch_gaps as pg
P0, P1 = pg.P0, pg.P1
diff = np.argwhere(~((P0.C == P1.C) | (np.isnan(P0.C) & np.isnan(P1.C))))
print("rows differing in C:", len(diff), "coins:", sorted({P0.coins[j] for _, j in diff}))
for c in ("XRP", "SOL", "DASH"):
    j = P0.ci[c]
    for d in (dt.date(2022, 2, 25), dt.date(2022, 2, 26), dt.date(2022, 2, 28), dt.date(2022, 3, 1), dt.date(2022, 3, 31), dt.date(2022, 4, 1), dt.date(2022, 4, 3)) if c != "DASH" else (dt.date(2022, 9, 30), dt.date(2022, 10, 1), dt.date(2022, 10, 31), dt.date(2022, 11, 1)):
        t = P0.idx[d]
        print(f"   {c} {d} O {P1.O[t,j]:.5g} C {P1.C[t,j]:.5g} Q {P1.Q[t,j]:.3g} (orig C {P0.C[t,j]:.5g})")


def variant(only):
    C, O, H, L, V, Q = (x.copy() for x in (P0.C, P0.O, P0.H, P0.L, P0.V, P0.Q))
    for t, j in diff:
        c = P0.coins[j]
        if (only == "dash") != (c == "DASH"):
            continue
        for X, Y in ((C, P1.C), (O, P1.O), (H, P1.H), (L, P1.L), (V, P1.V), (Q, P1.Q)):
            X[t, j] = Y[t, j]
    return data.Panel(P0.dates, list(P0.coins), O, H, L, C, V, P1.F, Q)


for lab, P in (("orig", P0), ("feb/apr only", variant("febapr")), ("dash only", variant("dash")), ("both", P1)):
    ctx = vu._ctx(P)
    line = []
    for cad in (vu.DAILY, vu.WEEKLY):
        kw = vu._kw(ctx, cad)
        b = vu._sim(ctx, vu._weights(ctx, cad, vu._static_mask(ctx, data.EXANTE24)), kw)
        U, _ = vu._membership(ctx, cad, vu.SPECS["UNI-1"])
        r = vu._sim(ctx, vu._weights(ctx, cad, U), kw)
        e = np.cumprod(1 + b["rets"]); dd = e / np.maximum.accumulate(e) - 1; k = int(np.argmin(dd)); pk = int(np.argmax(e[:k + 1]))
        er = np.cumprod(1 + r["rets"]); ddr = er / np.maximum.accumulate(er) - 1; kr = int(np.argmin(ddr)); pkr = int(np.argmax(er[:kr + 1]))
        line.append(f"{cad['name']}: static FULL {sim.sharpe(b['rets']):.4f} mdd {dd[k]:.2%} ({b['dates'][pk]}..{b['dates'][k]}) | UNI-1 FULL {sim.sharpe(r['rets']):.4f} "
                    f"mdd {ddr[kr]:.2%} ({r['dates'][pkr]}..{r['dates'][kr]})")
    print(f"{lab:13s} " + " || ".join(line))
