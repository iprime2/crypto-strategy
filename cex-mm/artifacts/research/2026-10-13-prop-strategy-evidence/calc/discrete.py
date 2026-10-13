import math
def ruin_discrete(p,b,r,T,D):
    """Win prob p, payoff b:1 (win +b*r, loss -r). Approximates with unit steps when b==1;
    for b!=1 use Monte Carlo."""
    import numpy as np
    rng=np.random.default_rng(1)
    n=20000; passes=0; ntr=[]
    for _ in range(n):
        eq=0; k=0
        while True:
            k+=1
            eq += b*r if rng.random()<p else -r
            if eq>=T: passes+=1; ntr.append(k); break
            if eq<=-D: break
            if k>5000: break
    return passes/n, (sum(ntr)/len(ntr) if ntr else float('nan'))
print("=== I. Per-trade gambler's ruin: target 8%, max DD 10%, no daily limit, no time limit ===")
for (p,b) in [(0.55,1.0),(0.40,3.0),(0.70,0.8),(0.52,1.0)]:
    edge=p*b-(1-p); sd=math.sqrt(p*(1-p))*(1+b); sr=edge/sd
    for r in [0.005,0.01,0.02]:
        pp,nt=ruin_discrete(p,b,r,0.08,0.10)
        print(f"p={p} b={b} (per-trade edge {edge:+.3f}R, per-trade Sharpe {sr:.3f}) r={r*100:.1f}%: P(pass)={pp:.3f}, mean trades to pass={nt:.0f} -> at 1 trade/day {nt:.0f} days, at 3/day {nt/3:.0f} days")
print()
print("=== J. Daily-limit breach from k consecutive losses in one day (p=0.55, 1:1), daily limit 5% ===")
for r in [0.01,0.0167,0.02,0.025]:
    k=math.ceil(0.05/r)  # losses needed to breach
    for tpd in [1,3,5]:
        if tpd<k: pb=0.0
        else:
            # prob that within tpd trades the running loss hits -5% (approx: at least k net losses in a row from start... use MC)
            import numpy as np
            rng=np.random.default_rng(2); n=20000; c=0
            for _ in range(n):
                eq=0
                for t in range(tpd):
                    eq += r if rng.random()<0.55 else -r
                    if eq<=-0.05+1e-12: c+=1; break
            pb=c/n
        print(f"r={r*100:.2f}% ({k} losses to breach), {tpd} trades/day: P(breach/day)={pb:.4f}, P(survive 30 days)={(1-pb)**30:.3f}")
print()
print("=== K. Rule of thumb: Sharpe needed to hit T within N days while keeping daily vol <= d/z (z=3) ===")
print("S_annual >= sqrt(365) * z * T / (N * d)")
for (T,d) in [(0.08,0.05),(0.10,0.03),(0.10,0.05),(0.06,0.04)]:
    for N in [30,60,90]:
        S=math.sqrt(365)*3*T/(N*d)
        print(f"T={T:.2f} d={d:.2f} N={N}: S>={S:.2f}")
