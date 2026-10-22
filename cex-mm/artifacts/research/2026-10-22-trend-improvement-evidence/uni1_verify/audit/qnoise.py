#!/usr/bin/env python3
"""Turnover-data sensitivity of UNI-1: (a) targeted counterfactuals at the two knife-edge resets (EOS +3 % at 2023-01-01, LTC +6 % at
2024-01-01); (b) Monte Carlo: per-coin, per-calendar-year multiplicative error on quote volume (lognormal sd 2 %, 5 %, 10 %), 100 draws each,
distribution of FULL / POST Sharpe on both books vs the static 24 (which does not depend on Q)."""
import sys, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
import numpy as np
import data, sim
import variants_universe as vu

P = vu.load_pool(); ctx = vu._ctx(P)
Qc0 = ctx.Qc.copy()
spec = vu.SPECS["UNI-1"]
years = np.array([d.year for d in P.dates])
base = {}
for cad in (vu.DAILY, vu.WEEKLY):
    base[cad["name"]] = vu._sim(ctx, vu._weights(ctx, cad, vu._static_mask(ctx, data.EXANTE24)), vu._kw(ctx, cad))


def run(mult):
    ctx.Qc = Qc0 * mult
    ctx.cache.clear()
    out = {}
    for cad in (vu.DAILY, vu.WEEKLY):
        U, log = vu._membership(ctx, cad, spec)
        r = vu._sim(ctx, vu._weights(ctx, cad, U), vu._kw(ctx, cad))
        out[cad["name"]] = (sim.sharpe(r["rets"]), sim.stats(r, vu.POST)["sharpe"], tuple(tuple(e["members"]) for e in log))
    return out


ref = run(np.ones_like(Qc0))
print("reference:", {k: (round(v[0], 4), round(v[1], 4)) for k, v in ref.items()})
print("static-24:", {k: (round(sim.sharpe(b["rets"]), 4), round(sim.stats(b, vu.POST)["sharpe"], 4)) for k, b in base.items()})

# (a) targeted
def bump(coin, d_end, f):
    m = np.ones_like(Qc0); j = P.ci[coin]; t = P.idx[d_end]
    m[t - 40:t + 8, j] = f   # covers the 30 rows before both the daily (Jan 1) and weekly (first Sunday) reset rows
    return m
for coin, d, f in (("EOS", dt.date(2023, 1, 1), 1.03), ("LTC", dt.date(2024, 1, 1), 1.06), ("AVAX", dt.date(2022, 1, 1), 1.30)):
    o = run(bump(coin, d, f))
    ch = {k: [set(a) ^ set(b) for a, b in zip(o[k][2], ref[k][2]) if set(a) != set(b)] for k in o}
    print(f"(a) {coin} Q x{f} around {d}: " + " | ".join(f"{k} {v[0]:.3f}/{v[1]:.3f} (ref {ref[k][0]:.3f}/{ref[k][1]:.3f}) membership change {ch[k]}" for k, v in o.items()))
m = bump("EOS", dt.date(2023, 1, 1), 1.03) * bump("LTC", dt.date(2024, 1, 1), 1.06)
o = run(m)
print(f"(a) EOS x1.03 @2023 and LTC x1.06 @2024: " + " | ".join(f"{k} {v[0]:.3f}/{v[1]:.3f}" for k, v in o.items()))

# (b) Monte Carlo
rng = np.random.default_rng(11)
uy = sorted(set(years)); yi = np.array([uy.index(y) for y in years])
for sd in (0.02, 0.05, 0.10):
    res = {"daily": [], "weekly": []}; nchg = 0
    for k in range(100):
        z = rng.normal(0, sd, (len(uy), P.C.shape[1]))
        mult = np.exp(z[yi])
        o = run(mult)
        nchg += any(o[c][2] != ref[c][2] for c in o)
        for c in o:
            res[c].append(o[c][:2])
    line = []
    for c, v in res.items():
        a = np.array(v); bs = sim.sharpe(base[c]["rets"]); bp = sim.stats(base[c], vu.POST)["sharpe"]
        line.append(f"{c}: FULL median {np.median(a[:,0]):.3f} [p5 {np.percentile(a[:,0],5):.3f}, p95 {np.percentile(a[:,0],95):.3f}] "
                    f"share FULL<=static {np.mean(a[:,0] <= bs):.2f}; POST median {np.median(a[:,1]):.3f} [p5 {np.percentile(a[:,1],5):.3f}, p95 {np.percentile(a[:,1],95):.3f}] "
                    f"share POST delta<=0 {np.mean(a[:,1] <= bp):.2f}")
    print(f"(b) per-coin-year Q error sd {sd:.0%}: membership changed in {nchg}/100 draws | " + " || ".join(line))
ctx.Qc = Qc0
