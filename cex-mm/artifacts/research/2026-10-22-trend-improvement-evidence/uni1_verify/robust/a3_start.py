"""(3) start-universe effect and concentration-vs-rotation controls."""
from common import *
c = ctx()
H1b = (vu.A0, dt.date(2021, 12, 31))

def line(lbl, r, b):
    bt = boot(r, b, POST, None, r); bf = boot(r, b, None, None, r)
    return (f"  {lbl:44s} FULL {sh(r):.3f} (d {bf[0]:+.3f} [{bf[1]:+.2f},{bf[2]:+.2f}] P {bf[3]:.2f}) | 2020-21 {sh(r, *H1b):.3f} (d {sh(r, *H1b)-sh(b, *H1b):+.3f}) | "
            f"POST {sh(r, POST):.3f} (d {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P {bt[3]:.2f}) | vol {r['rets'].std(ddof=1)*np.sqrt(365):.1%} mdd {sim.maxdd(r['rets']):.1%}")

out = {}
for name, cad in CADS.items():
    U, log = U_uni1(c, cad); r = run(c, cad, W_of(c, cad, U))
    Ub = U_static24(c); Wb = W_of(c, cad, Ub); b = run(c, cad, Wb)
    print(f"\n=== {name} (all deltas vs static-24 through D-0; bootstrap block 20, 1000 draws)")
    print(line("UNI-1", r, b))
    print(f"  static-24: FULL {sh(b):.3f} 2020-21 {sh(b, *H1b):.3f} POST {sh(b, POST):.3f} vol {b['rets'].std(ddof=1)*np.sqrt(365):.1%} mdd {sim.maxdd(b['rets']):.1%}")
    # restart both books on 2022-01-01 (fresh book; weights decided from the 2021-12-31 close)
    r2 = run(c, cad, W_of(c, cad, U), start=POST); b2 = run(c, cad, Wb, start=POST)
    bt = boot(r2, b2, None, None, r2)
    print(f"  restart 2022-01-01..2026-09-30: UNI-1 {sh(r2):.3f} vs static-24 {sh(b2):.3f} d {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P<=0 {bt[3]:.2f}; "
          f"CAGR {sim.cagr(r2['rets']):+.1%} vs {sim.cagr(b2['rets']):+.1%}; mdd {sim.maxdd(r2['rets']):.1%} vs {sim.maxdd(b2['rets']):.1%}")
    # hybrid: static-24 weights through 2021-12-31, UNI-1 weights from then on
    cut = c.idx[dt.date(2021, 12, 31)]
    Wh = Wb.copy(); Wh[cut:] = W_of(c, cad, U)[cut:]
    rh = run(c, cad, Wh)
    print(line("hybrid: static-24 to 2021, UNI-1 from 2022", rh, b))
    # C1: static top-9 on 2020-04-30, never reset (first listing life)
    S9 = log[0]["members"]
    U1 = vu._static_mask(c, S9); r1 = run(c, cad, W_of(c, cad, U1))
    print(line(f"C1 static start-9 never reset {S9}", r1, b))
    print(f"     C1 vs UNI-1: FULL {sh(r1)-sh(r):+.3f} POST {sh(r1, POST)-sh(r, POST):+.3f}")
    # C4: static 2022-01 UNI-1 members, never reset (only meaningful POST)
    S22 = log[2]["members"]
    U4 = np.zeros_like(U)
    r0 = c.idx[dt.date.fromisoformat(log[2]["date"])]
    for m in S22:
        j = c.coins.index(m); L = c.LIFE[r0, j]; U4[r0:, j] = c.LIFE[r0:, j] == L
    U4[:r0] = U[:r0]
    r4 = run(c, cad, W_of(c, cad, U4))
    print(line(f"C4 UNI-1 frozen at its 2022 set {S22}", r4, b))
    print(f"     C4 vs UNI-1: POST {sh(r4, POST)-sh(r, POST):+.3f}")
    # C3: rotation within the static-24 only (same rule, pool restricted to the 24 ex-ante coins)
    ex = np.array([cn not in set(data.EXANTE24) for cn in c.coins])
    U3, lg3 = membership_custom(c, cad, excl=ex); r3 = run(c, cad, W_of(c, cad, U3))
    print(line("C3 UNI-1 rule inside the static-24 only", r3, b))
    for d_, m_ in lg3: print(f"       {d_} {m_}")
    # C5: hindsight nine (data.NINE) on the pool
    U5 = vu._static_mask(c, data.NINE); r5 = run(c, cad, W_of(c, cad, U5))
    print(line("C5 hindsight nine (reference, not ex-ante)", r5, b))
    # C6: UNI-1 at N=24 (no concentration: same rule, 24 names, H=48)
    U6, lg6 = membership_custom(c, cad, N=24, H=48); r6 = run(c, cad, W_of(c, cad, U6))
    print(line("C6 UNI-1 rule with N=24, H=48", r6, b))
    # C7: static-24 cohort but only the first 9 by 2020-04-30 turnover inside it = C1 (C1 members are all in the 24) -> skip; instead N=9 vs N=24 within the same cohort for each year
    out[name] = dict(uni=(sh(r), sh(r, POST)), s24=(sh(b), sh(b, POST)), restart=(sh(r2), sh(b2)), hybrid=(sh(rh), sh(rh, POST)), C1=(sh(r1), sh(r1, POST)),
                     C4=(sh(r4), sh(r4, POST)), C3=(sh(r3), sh(r3, POST)), C5=(sh(r5), sh(r5, POST)), C6=(sh(r6), sh(r6, POST)))
json.dump(out, open(f"{OUT}/a3.json", "w"), default=float)
