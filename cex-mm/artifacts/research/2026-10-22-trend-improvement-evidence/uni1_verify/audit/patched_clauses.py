#!/usr/bin/env python3
"""The four 6.3 pass clauses (R1 FULL Sharpe, R2 POST delta + bootstrap, R3 matched-vol maxDD vs static-24 raw maxDD, R4 H1/H2 deltas) on the
original Bw panel and on the gap-patched panel (patch_gaps.P1)."""
import sys, io, contextlib
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np, data, sim, variants_universe as vu
with contextlib.redirect_stdout(io.StringIO()):
    import patch_gaps as pg
H1 = (vu.A0, vu.WINDOWS["h1"][1]); H2 = vu.WINDOWS["h2"]
for lab, P in (("original", pg.P0), ("gap-patched", pg.P1)):
    ctx = vu._ctx(P)
    for cad in (vu.DAILY, vu.WEEKLY):
        U, _ = vu._membership(ctx, cad, vu.SPECS["UNI-1"])
        kw = vu._kw(ctx, cad)
        r = vu._sim(ctx, vu._weights(ctx, cad, U), kw)
        b = vu._sim(ctx, vu._weights(ctx, cad, vu._static_mask(ctx, data.EXANTE24)), kw)
        s, bs = sim.stats(r), sim.stats(b)
        cm = dict(cad); cm["tv"] = cad["tv"] * bs["vol"] / s["vol"]
        rm = vu._sim(ctx, vu._weights(ctx, cm, U), kw)
        sm = sim.stats(rm)
        d = np.array(r["dates"]); m = d >= vu.POST
        boot = sim.block_bootstrap_diff(r["rets"][m], b["rets"][m])
        h = []
        for a, z in (H1, H2):
            mm = (d >= a) & (d <= z)
            h.append(sim.sharpe(r["rets"][mm]) - sim.sharpe(b["rets"][mm]))
        print(f"{lab:11s} {cad['name']:6s} R1 FULL {s['sharpe']:.3f} vs {bs['sharpe']:.3f} | R2 POST d {boot[0]:+.3f} [{boot[1]:+.2f},{boot[2]:+.2f}] P {boot[3]:.2f} | "
              f"R3 mv maxDD {sm['mdd']:.2%} (tv {cm['tv']:.3f}) vs static {bs['mdd']:.2%}, raw {s['mdd']:.2%} -> {'ok' if sm['mdd'] >= bs['mdd'] else 'FAIL'} | "
              f"R4 H1 {h[0]:+.3f} H2 {h[1]:+.3f} | vol {s['vol']:.3f} vs {bs['vol']:.3f}")
