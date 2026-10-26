"""Diagnostics for quick_check.py: (1) why the shooting-star rule never fires on 24/7 daily bars,
(2) exposure and per-held-day return of the long-only dip legs vs the unconditional coin-day mean."""
import sys, importlib.util
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("qc", sys.argv[1]); qc = importlib.util.module_from_spec(spec); spec.loader.exec_module(qc)
data = {c: qc.load(sys.argv[2], c) for c in qc.COINS}
S, E = qc.START, qc.END
print("(1) open vs previous close, and shooting-star condition counts, 2020-05..2026-09")
tot = dict(n=0, gap=0, c1=0, c5=0, c1c5=0, c1c5_body=0)
for c, d in data.items():
    d = d.loc[S:E]
    o, h, l, cl = d.open, d.high, d.low, d.close
    gap = ((o / cl.shift(1) - 1).abs() > 1e-4)
    c1 = o >= cl; c5 = cl >= cl.shift(1)
    tot["n"] += len(d); tot["gap"] += int(gap.sum()); tot["c1"] += int(c1.sum()); tot["c5"] += int(c5.sum())
    tot["c1c5"] += int((c1 & c5).sum()); tot["c1c5_body"] += int((c1 & c5 & ((o - cl).abs() > 0)).sum())
print(f"   coin-days {tot['n']}; |open/prev close - 1| > 1 bp on {tot['gap']} days; red (c1) {tot['c1']}; up close (c5) {tot['c5']}; c1 & c5 {tot['c1c5']}; c1 & c5 with non-zero body {tot['c1c5_body']}")
print("(2) long-only dip legs: exposure and mean next-day return when held vs all coin-days (gross, bps/day)")
for name, fn in (("RSI14 <30 long only", lambda d: qc.pos_rsi(d, True)), ("BB20/2 revert-to-mid long only", lambda d: qc.pos_bb(d, True))):
    for wn, a, b in (("FULL", S, E), ("2020-21", S, "2021-12-31"), ("2022-26", qc.SPLIT, E)):
        held_r, all_r = [], []
        for c, d in data.items():
            p = fn(d).shift(1); r = d.close.pct_change()
            x = pd.DataFrame({"p": p, "r": r}).loc[a:b].dropna()
            held_r.append(x.r[x.p > 0]); all_r.append(x.r)
        H = pd.concat(held_r); A = pd.concat(all_r)
        t = H.mean() / (H.std() / np.sqrt(len(H)))
        print(f"   {name:32s} {wn:8s} exposure {100*len(H)/len(A):5.1f}% of coin-days; held-day mean {H.mean()*1e4:6.1f} bps (naive t {t:4.2f}, n {len(H)}); all coin-days {A.mean()*1e4:6.1f} bps")
