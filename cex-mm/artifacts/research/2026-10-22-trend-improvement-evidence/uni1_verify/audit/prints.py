#!/usr/bin/env python3
"""(3) Bad-print audit: the 20 largest single-coin daily contributions to UNI-1 daily (and weekly) P&L, bar consistency, next-day
reversal, cross-check vs Delta India daily closes where available; plus a whole-panel scan of the held coins for inconsistent bars."""
import sys, json, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d"
SP = SP + "/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data, sim
import variants_universe as vu
from base import build

P, ctx, out = build()
dl = data.load_delta(coins=data.NINE)
didx = dl.idx

for name, o in out.items():
    r = o["r"]; cols = r["cols"]; cp = r["coin_pnl"]; dates = r["dates"]; rets = r["rets"]
    flat = [(abs(cp[i, k]), i, k) for i in range(cp.shape[0]) for k in range(cp.shape[1]) if cp[i, k] != 0]
    flat.sort(reverse=True)
    print(f"\n== {name}: top 20 |coin-day P&L| (fraction of equity; P&L dated d = held over d-1 -> d)")
    print("   rank coin      date        pnl      ret_d    ret_d+1  w_held  O/H/L/C(d)                         O[d]/C[d-1]-1 C in[L,H] DeltaRet")
    tot_top = 0.0
    for n, (a, i, k) in enumerate(flat[:20]):
        c = cols[k]; j = P.ci[c]; d = dates[i]; t = P.idx[d]
        Cc = P.C[:, j]
        rd = Cc[t] / Cc[t - 1] - 1; rn = Cc[t + 1] / Cc[t] - 1 if t + 1 < len(P.dates) else np.nan
        w = o["W"][t - 1, j]
        gap = P.O[t, j] / P.C[t - 1, j] - 1
        inrng = P.L[t, j] <= P.C[t, j] <= P.H[t, j] and P.L[t, j] <= P.O[t, j] <= P.H[t, j]
        dr = ""
        if c in dl.ci and d in didx and (d - dt.timedelta(days=1)) in didx:
            jj = dl.ci[c]; x1, x0 = dl.C[didx[d], jj], dl.C[didx[d - dt.timedelta(days=1)], jj]
            dr = f"{x1 / x0 - 1:+.3f}" if np.isfinite(x1) and np.isfinite(x0) else ""
        tot_top += cp[i, k]
        print(f"   {n+1:3d}  {c:9s} {d}  {cp[i,k]:+.4f}  {rd:+.3f}  {rn:+.3f}  {w:.3f}  {P.O[t,j]:.5g}/{P.H[t,j]:.5g}/{P.L[t,j]:.5g}/{P.C[t,j]:.5g}"
              f"   {gap:+.4f}  {inrng}  {dr}  (port ret {rets[i]:+.4f})")
    print(f"   sum of top-20 coin-day P&L: {tot_top:+.4f}; Sharpe with these 20 coin-days zeroed:", end=" ")
    adj = rets.copy()
    for a, i, k in flat[:20]:
        adj[i] -= cp[i, k]
    print(f"{sim.sharpe(adj):.3f} (vs {sim.sharpe(rets):.3f}); base {sim.sharpe(o['b']['rets']):.3f}")
    # same treatment for the baseline's top-20 for symmetry
    b = o["b"]; bcp = b["coin_pnl"]
    bflat = sorted(((abs(bcp[i, k]), i, k) for i in range(bcp.shape[0]) for k in range(bcp.shape[1]) if bcp[i, k] != 0), reverse=True)[:20]
    badj = b["rets"].copy()
    for a, i, k in bflat:
        badj[i] -= bcp[i, k]
    print(f"   static-24 with its own top-20 coin-days zeroed: {sim.sharpe(badj):.3f} (vs {sim.sharpe(b['rets']):.3f}); top-20 sum {sum(bcp[i,k] for _,i,k in bflat):+.4f}")
    # per-coin P&L totals
    tots = {cols[k]: float(cp[:, k].sum()) for k in range(len(cols))}
    print("   per-coin P&L (sum of daily fractions, price net of funding):", {c: round(v, 4) for c, v in sorted(tots.items(), key=lambda x: -x[1])})

# Whole-panel scan of the held coins, A window: bars with C or O outside [L, H], H < L, |log ret| > 0.3, or spike-and-revert
print("\n== Bar-consistency scan of the 14 held coins over 2020-01..2026-09")
held = sorted(set(out["daily"]["r"]["cols"]))
for c in held:
    j = P.ci[c]
    O, H, L, C = P.O[:, j], P.H[:, j], P.L[:, j], P.C[:, j]
    fin = np.isfinite(C)
    bad_rng = np.flatnonzero(fin & ((C > H * (1 + 1e-9)) | (C < L * (1 - 1e-9)) | (O > H * (1 + 1e-9)) | (O < L * (1 - 1e-9)) | (H < L)))
    lr = np.full(len(C), np.nan); lr[1:] = np.log(C[1:] / C[:-1])
    big = np.flatnonzero(np.abs(np.nan_to_num(lr)) > 0.3)
    spike = [t for t in range(1, len(C) - 1) if np.isfinite(lr[t]) and np.isfinite(lr[t + 1]) and abs(lr[t]) > 0.15 and lr[t] * lr[t + 1] < 0 and abs(lr[t + 1]) > 0.8 * abs(lr[t])]
    ogap = np.full(len(C), np.nan); ogap[1:] = O[1:] / C[:-1] - 1
    gaps = np.flatnonzero(np.abs(np.nan_to_num(ogap)) > 0.01)
    print(f"   {c:9s} bars {int(fin.sum())}: C/O outside [L,H]: {[str(P.dates[t]) for t in bad_rng]}; |logret|>0.3: "
          f"{[(str(P.dates[t]), round(float(lr[t]), 3)) for t in big]}; spike-revert(>15%, >=80% back): {[(str(P.dates[t]), round(float(lr[t]),3), round(float(lr[t+1]),3)) for t in spike]}; "
          f"open != prior close by >1%: {[(str(P.dates[t]), round(float(ogap[t]), 4)) for t in gaps][:8]}")
