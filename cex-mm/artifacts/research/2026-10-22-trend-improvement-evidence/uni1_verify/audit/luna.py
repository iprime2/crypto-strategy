#!/usr/bin/env python3
"""LUNA handling and the age-floor near miss: LUNA's last rows, its P&L in the age-121 neighbor (which admits it), and UNI-1's Sharpe as a
function of the age floor (sensitivity, not a data error)."""
import sys, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
import numpy as np
import data, sim
import variants_universe as vu

P = vu.load_pool(); ctx = vu._ctx(P)
j = P.ci["LUNA"]
t1 = np.flatnonzero(ctx.pos[:, j])[-1]
print("LUNA last rows:")
for t in range(t1 - 7, t1 + 2):
    print(f"   {P.dates[t]} O {P.O[t,j]:.5g} H {P.H[t,j]:.5g} L {P.L[t,j]:.5g} C {P.C[t,j]:.5g} Q {P.Q[t,j]:.4g} F {P.F[t,j]:+.5f}")

base = {}
for cad in (vu.DAILY, vu.WEEKLY):
    Ws = vu._weights(ctx, cad, vu._static_mask(ctx, data.EXANTE24))
    base[cad["name"]] = vu._sim(ctx, Ws, vu._kw(ctx, cad))

for nm in ("UNI-1__age121",):
    for cad in (vu.DAILY, vu.WEEKLY):
        U, log = vu._membership(ctx, cad, vu.SPECS[nm])
        W = vu._weights(ctx, cad, U)
        r = vu._sim(ctx, W, vu._kw(ctx, cad))
        cols = r["cols"]
        print(f"\n{nm} {cad['name']}: Sharpe {sim.sharpe(r['rets']):.4f}; resets: " + "; ".join(f"{e['date']} +{e['entrants']} -{e['leavers']}" for e in log[1:]))
        if "LUNA" in cols:
            k = cols.index("LUNA")
            cp = r["coin_pnl"][:, k]
            tot = cp.sum()
            m = [(str(d), float(cp[i])) for i, d in enumerate(r["dates"]) if dt.date(2022, 4, 25) <= d <= dt.date(2022, 5, 14)]
            print(f"   LUNA total P&L {tot:+.4%}; Apr25-May14 daily: {[(d, round(v, 4)) for d, v in m if v != 0]}")
            print(f"   W LUNA 2022-05-01..12: {[round(float(W[P.idx[dt.date(2022,5,d)], j]), 4) for d in range(1, 13)]}")
            adj = r["rets"] - cp
            print(f"   Sharpe with LUNA P&L removed: {sim.sharpe(adj):.4f}")
        ev = vu.delisting_events(ctx, U, r, W, vu._kw(ctx, cad)["decide"])
        for e in ev:
            print("  ", vu._ev_line(e))

print("\nUNI-1 FULL / POST Sharpe vs the age floor (N 9, H 18, yearly); static-24 daily %.4f weekly %.4f" % (sim.sharpe(base['daily']['rets']), sim.sharpe(base['weekly']['rets'])))
for age in (121, 200, 250, 300, 330, 335, 340, 345, 350, 365, 380, 400, 450, 500):
    line = []
    for cad in (vu.DAILY, vu.WEEKLY):
        spec = dict(N=9, H=18, age=age, reset="yearly")
        ctx.cache.clear()
        U, log = vu._membership(ctx, cad, spec)
        W = vu._weights(ctx, cad, U)
        r = vu._sim(ctx, W, vu._kw(ctx, cad))
        s, p = sim.stats(r), sim.stats(r, vu.POST)
        ent = sorted({m for e in log[1:] for m in e["entrants"]})
        line.append(f"{cad['name']} {s['sharpe']:.3f}/{p['sharpe']:.3f} mdd {s['mdd']:.1%}")
    print(f"   age {age:3d}: {' | '.join(line)} | entrants after start: {ent}")
