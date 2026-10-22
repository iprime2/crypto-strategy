#!/usr/bin/env python3
"""UNI-1 live lens, part 4: the UNI-5 gate and whole-contract lines at $1,000 / $2,500 / $5,000 with (i) the implementation's cv
table (data.CVALS else $25 / first close) and (ii) Delta India's real contract values (delta_perps.json; MATIC -> POL's 10;
coins never on Delta keep the fallback). The cv array is replaced on this process's in-memory ctx only; no file is changed.
Compared with the static 24 and the live nine rounded with the same table. stdout only."""
import json, os, sys, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.dont_write_bytecode = True
import data, rules, sim, variants_universe as vu  # noqa: E402

P = vu.load_pool(); ctx = vu._ctx(P); spec = vu.SPECS["UNI-1"]
perps = {p["underlying"]: p for p in json.load(open(f"{SP}/universe/delta_perps.json"))}
cv_fallback = ctx.cv.copy()
cv_delta = cv_fallback.copy()
for j, c in enumerate(ctx.coins):
    key = "POL" if c == "MATIC" else c
    if key in perps:
        cv_delta[j] = float(perps[key]["contract_value"])
U24 = vu._static_mask(ctx, data.EXANTE24); U9 = vu._static_mask(ctx, data.NINE)
for lab, cvarr in (("implementation cv (CVALS else $25/first close)", cv_fallback), ("Delta India real cv", cv_delta)):
    ctx.cv = cvarr
    print(f"\n######## {lab}")
    for cad in (vu.DAILY, vu.WEEKLY):
        for cap in (1000, 2500, 5000):
            kc = vu._kw(ctx, cad, cap)
            Ug, lg = vu._membership(ctx, cad, spec, capital=cap, kw=kc)
            rc = vu._sim(ctx, vu._weights(ctx, cad, Ug), kc)
            b24 = vu._sim(ctx, vu._weights(ctx, cad, U24), kc)
            b9 = vu._sim(ctx, vu._weights(ctx, cad, U9), kc)
            yrs = len(rc["rets"]) / 365
            s, s24, s9 = sim.stats(rc), sim.stats(b24), sim.stats(b9)
            sp, s24p, s9p = sim.stats(rc, vu.POST), sim.stats(b24, vu.POST), sim.stats(b9, vu.POST)
            h2 = (sim.stats(rc, dt.date(2024, 5, 1))["sharpe"], sim.stats(b9, dt.date(2024, 5, 1))["sharpe"])
            print(f"  {cad['name']:6s} ${cap:>5,}: FULL {s['sharpe']:.3f} (static24 {s24['sharpe']:.3f}, nine {s9['sharpe']:.3f}) POST {sp['sharpe']:.3f} "
                  f"({s24p['sharpe']:.3f}, {s9p['sharpe']:.3f}) 2024-05.. {h2[0]:.3f} (nine {h2[1]:.3f}) mdd {s['mdd']:.1%} vol {s['vol']:.1%} "
                  f"orders/yr {rc['orders']/yrs:.0f} fees/yr {rc['fees']/yrs:.2%}")
            print("          gated out: " + "; ".join(f"{e['date'][:4]}:{','.join(e['gated_out'])}" for e in lg if e["gated_out"]) +
                  f" | 2026 members {' '.join(lg[-1]['members'])} (E ${lg[-1]['equity']:,.0f})")
ctx.cv = cv_fallback
