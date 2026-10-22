#!/usr/bin/env python3
"""UNI-1 live lens, part 3 (read-only on tools2; stdout only):
 a. stability of the 2027 pick: _select with the 2026 incumbents at several 30-day windows ending 2026-06-30..2026-09-30;
 b. per-coin P&L (fraction of equity, after funding, before costs) of UNI-1 vs the static 24, FULL and 2024-05-01..2026-09-30;
 c. a Delta-tradeable restriction: members only while listed on Delta India (current product launch dates; MATIC lenient = as
    if MATICUSD existed from 2024-04-08 and became POL), N_t shrinks like a delisting; Sharpe on 2024-05-01..2026-09-30 vs the
    unrestricted UNI-1, the static 24 and the live nine (both through D-0)."""
import json, os, sys, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.dont_write_bytecode = True
import data, rules, sim, variants_universe as vu  # noqa: E402

P = vu.load_pool(); ctx = vu._ctx(P); spec = vu.SPECS["UNI-1"]
perps = {p["underlying"]: p for p in json.load(open(f"{SP}/universe/delta_perps.json"))}

# a. stability
U, log = vu._membership(ctx, vu.DAILY, spec)
inc = {ctx.coins.index(m): int(ctx.LIFE[-1, ctx.coins.index(m)]) for m in log[-1]["members"]}
print("a. 2027 pick with the 2026 incumbents, 30-day median windows ending on:")
for d in (dt.date(2026, 6, 30), dt.date(2026, 7, 31), dt.date(2026, 8, 31), dt.date(2026, 9, 15), dt.date(2026, 9, 30)):
    r = P.idx[d]
    sel, rank = vu._select(ctx, r, inc, spec["N"], spec["H"], spec["age"])
    names = [ctx.coins[j] for j in sel]
    out_inc = sorted(ctx.coins[j] for j in inc if j not in sel)
    print(f"   {d}: {' '.join(f'{ctx.coins[j]}({rank[j]})' for j in sel)} | incumbents dropped {out_inc} | "
          f"LINK rank {rank.get(ctx.coins.index('LINK'))} AVAX rank {rank.get(ctx.coins.index('AVAX'))}")

# b/c
A0, A1 = vu.A0, vu.A1
W0 = dt.date(2024, 5, 1)
res = {}
for cad in (vu.DAILY, vu.WEEKLY):
    kw = vu._kw(ctx, cad)
    U, log = vu._membership(ctx, cad, spec)
    r_u = vu._sim(ctx, vu._weights(ctx, cad, U), kw)
    U24 = vu._static_mask(ctx, data.EXANTE24); r_24 = vu._sim(ctx, vu._weights(ctx, cad, U24), kw)
    U9 = vu._static_mask(ctx, data.NINE); r_9 = vu._sim(ctx, vu._weights(ctx, cad, U9), kw)
    print(f"\n== {cad['name']}")
    for lab, rr in (("UNI-1", r_u), ("static24", r_24)):
        cp = rr["coin_pnl"]; d = np.array(rr["dates"])
        tot = cp.sum(axis=0); h2 = cp[d >= W0].sum(axis=0)
        o = np.argsort(-tot)
        print(f"  b. {lab} per-coin P&L (sum of daily fractions) FULL top/bottom; and 2024-05..2026-09:")
        print("     FULL  " + " ".join(f"{rr['cols'][k]}:{tot[k]:+.3f}" for k in o[:8]) + " ... " + " ".join(f"{rr['cols'][k]}:{tot[k]:+.3f}" for k in o[-4:]))
        o2 = np.argsort(-h2)
        print("     24-26 " + " ".join(f"{rr['cols'][k]}:{h2[k]:+.3f}" for k in o2[:8]) + " ... " + " ".join(f"{rr['cols'][k]}:{h2[k]:+.3f}" for k in o2[-4:]))
    # names never in static24: their P&L inside UNI-1
    newn = [c for c in r_u["cols"] if c not in data.EXANTE24]
    cp = r_u["coin_pnl"]; d = np.array(r_u["dates"])
    print("     UNI-1 P&L from names outside the static 24: FULL " + " ".join(f"{c}:{cp[:, r_u['cols'].index(c)].sum():+.3f}" for c in newn)
          + f" | sum {sum(cp[:, r_u['cols'].index(c)].sum() for c in newn):+.3f} vs total {cp.sum():+.3f}")
    # c. Delta-tradeable restriction
    for strict in (False, True):
        Ud = U.copy()
        for j, c in enumerate(ctx.coins):
            if not U[:, j].any():
                continue
            key = "POL" if c == "MATIC" else c
            if c == "MATIC" and not strict:
                launch = dt.date(2024, 4, 8)
            elif key in perps:
                launch = dt.date.fromisoformat(perps[key]["launch"])
            else:
                launch = dt.date(2100, 1, 1)
            if c == "MATIC" and strict:
                launch = dt.date(2100, 1, 1)
            Ud[:, j] &= np.array([dd >= launch for dd in ctx.dates])
        r_d = vu._sim(ctx, vu._weights(ctx, cad, Ud), kw)
        tag = "strict (MATIC not tradeable)" if strict else "lenient (MATIC from 2024-04-08)"
        line = []
        for lab, rr in (("UNI-1", r_u), ("UNI-1 Delta-listed " + tag, r_d), ("static24", r_24), ("live nine", r_9)):
            s = sim.stats(rr, W0, A1)
            line.append(f"{lab}: Sharpe {s['sharpe']:.3f} CAGR {s['cagr']:+.1%} vol {s['vol']:.1%} mdd {s['mdd']:.1%}")
        bd = sim.block_bootstrap_diff(r_d["rets"][np.array(r_d['dates']) >= W0], r_9["rets"][np.array(r_9['dates']) >= W0])
        bu = sim.block_bootstrap_diff(r_u["rets"][np.array(r_u['dates']) >= W0], r_9["rets"][np.array(r_9['dates']) >= W0])
        print(f"  c. 2024-05-01..2026-09-30 ({tag}):\n     " + "\n     ".join(line))
        print(f"     Delta-listed UNI-1 minus live nine: {bd[0]:+.3f} [{bd[1]:+.2f},{bd[2]:+.2f}] P<=0 {bd[3]:.2f}; unrestricted UNI-1 minus nine {bu[0]:+.3f} [{bu[1]:+.2f},{bu[2]:+.2f}] P<=0 {bu[3]:.2f}")
    # full-window comparisons for reference (UNI-1 vs nine)
    s_u, s_9, s_24 = sim.stats(r_u), sim.stats(r_9), sim.stats(r_24)
    b9 = sim.block_bootstrap_diff(r_u["rets"], r_9["rets"])
    print(f"  FULL: UNI-1 {s_u['sharpe']:.3f} static24 {s_24['sharpe']:.3f} live nine (through D-0) {s_9['sharpe']:.3f}; UNI-1 - nine {b9[0]:+.3f} [{b9[1]:+.2f},{b9[2]:+.2f}] P<=0 {b9[3]:.2f}")
    for w, (a, b) in vu.WINDOWS.items():
        su, s9 = sim.stats(r_u, a, b), sim.stats(r_9, a, b)
        print(f"     {w:4s} UNI-1 {su['sharpe']:.3f} vs nine {s9['sharpe']:.3f}  turnover {su['turnover']:.1f}x vs {s9['turnover']:.1f}x")
