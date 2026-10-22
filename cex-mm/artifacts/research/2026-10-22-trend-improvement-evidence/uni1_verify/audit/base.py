#!/usr/bin/env python3
"""Audit base: rebuild UNI-1 (daily, weekly) and the static-24 baseline exactly through variants_universe, save arrays for the audit.
Read-only on tools2 (imports only)."""
import sys, os, json, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
import numpy as np
import data, sim, rules
import variants_universe as vu

OUT = f"{SP}/uni1_verify/audit"


def build(P=None):
    P = P or vu.load_pool()
    ctx = vu._ctx(P)
    out = {}
    for cad in (vu.DAILY, vu.WEEKLY):
        U, log = vu._membership(ctx, cad, vu.SPECS["UNI-1"])
        W = vu._weights(ctx, cad, U)
        kw = vu._kw(ctx, cad)
        r = vu._sim(ctx, W, kw)
        Ws = vu._weights(ctx, cad, vu._static_mask(ctx, data.EXANTE24))
        b = vu._sim(ctx, Ws, kw)
        out[cad["name"]] = dict(U=U, log=log, W=W, kw=kw, r=r, Ws=Ws, b=b)
    return P, ctx, out


if __name__ == "__main__":
    P, ctx, out = build()
    for name, o in out.items():
        s, bs = sim.stats(o["r"]), sim.stats(o["b"])
        print(name, "UNI-1 FULL Sharpe %.4f vol %.4f mdd %.4f | static24 %.4f" % (s["sharpe"], s["vol"], s["mdd"], bs["sharpe"]))
        for e in o["log"]:
            print("  reset", e["date"], " ".join(f"{m}({k})" for m, k in zip(e["members"], e["ranks"])), "+", e["entrants"], "-", e["leavers"])
        cols = np.flatnonzero(np.abs(o["W"]).sum(axis=0) > 0)
        print("  cols with weight:", [ctx.coins[j] for j in cols])
        np.savez(f"{OUT}/uni1_{name}.npz", rets=o["r"]["rets"], dates=np.array([str(d) for d in o["r"]["dates"]]), coin_pnl=o["r"]["coin_pnl"],
                 cols=np.array(o["r"]["cols"]), W=o["W"][:, cols], Wcols=np.array([ctx.coins[j] for j in cols]),
                 brets=o["b"]["rets"], gross=o["r"]["gross"], fund_frac=o["r"]["fund_frac"], cost_frac=o["r"]["cost_frac"])
