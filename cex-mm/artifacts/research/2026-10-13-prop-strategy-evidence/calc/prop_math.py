import math, numpy as np
rng = np.random.default_rng(7)

def p_closed(mu, sig, T, D):
    """P(hit +T before -D) for X_t = mu t + sig W_t, no time limit, no daily limit."""
    if abs(mu) < 1e-12: return D/(T+D)
    k = 2*mu/sig**2
    return (1-math.exp(-k*D))/(1-math.exp(-k*(T+D)))

print("=== A. Closed-form, no time limit, no daily limit ===")
print("sigma_daily=1%, target T, maxDD D; annual Sharpe S -> daily mu = S/sqrt(365)*sigma")
for S in [0.5,1,1.5,2,3]:
    row=[]
    for (T,D) in [(0.08,0.05),(0.10,0.10),(0.08,0.10),(0.10,0.06),(0.06,0.06)]:
        mu = S/math.sqrt(365)*0.01
        row.append(f"T{int(T*100)}/D{int(D*100)}={p_closed(mu,0.01,T,D):.3f}")
    print(f"S={S}: "+"  ".join(row))
print()
print("=== B. Leverage effect (closed form): S=1.5, base sigma 1%, T=8%, D=10% ===")
for L in [0.25,0.5,1,2,3,5,10]:
    mu=1.5/math.sqrt(365)*0.01*L; sig=0.01*L
    print(f"L={L}: p={p_closed(mu,sig,0.08,0.10):.3f}  (expected days to exit ~ {( (0.08*p_closed(mu,sig,0.08,0.10) - 0.10*(1-p_closed(mu,sig,0.08,0.10)))/mu if mu>0 else float('nan')):.0f})")
print("limit L->inf: D/(T+D) =", 0.10/0.18)
print()

def sim(S, sig_d, T, D, dlim, N, steps=24, two_phase=False, T2=None, consist=None, trials=20000):
    """Monte Carlo: daily vol sig_d, annual Sharpe S (365d), target T, static max DD D (from start),
    daily loss limit dlim on intraday equity from day's opening balance, time limit N days.
    Intraday path in `steps` substeps. Returns pass prob and breach breakdown."""
    mu_d = S/math.sqrt(365)*sig_d
    res = {"pass":0,"daily":0,"maxdd":0,"time":0,"consist":0}
    for _ in range(trials):
        eq=0.0; ok=None; best_day=-1e9; tot_days_pnl=[]
        for day in range(N):
            start=eq
            inc = rng.normal(mu_d/steps, sig_d/math.sqrt(steps), steps)
            path = start+np.cumsum(inc)
            # daily limit (intraday, equity-based) and static max DD
            hit_daily = np.min(path-start) <= -dlim
            hit_dd = np.min(path) <= -D
            hit_tgt = np.max(path) >= T
            # order: find first index for each
            idx_d = np.argmax(path-start <= -dlim) if hit_daily else 10**9
            idx_dd = np.argmax(path <= -D) if hit_dd else 10**9
            idx_t = np.argmax(path >= T) if hit_tgt else 10**9
            first=min(idx_d,idx_dd,idx_t)
            if first==10**9:
                eq=path[-1]; tot_days_pnl.append(eq-start); continue
            if idx_t==first:
                eq=path[idx_t]; tot_days_pnl.append(eq-start)
                if consist is not None:
                    if max(tot_days_pnl) > consist*eq:  # best day > consist share of total profit
                        ok="consist"; break
                ok="pass"; break
            elif idx_d==first: ok="daily"; break
            else: ok="maxdd"; break
        if ok is None: ok="time"
        res[ok]+=1
    return {k:v/trials for k,v in res.items()}

print("=== C. Monte Carlo with time limit N and intraday daily-loss limit (equity-based) ===")
print("Setup: T=8%, D=10% static, daily limit 5%, annual Sharpe S, base sigma_daily = 1% x leverage L")
for S in [1.0,2.0,3.0]:
    for N in [30,60,365]:
        line=[]
        for L in [0.5,1,2,3,4]:
            r=sim(S,0.01*L,0.08,0.10,0.05,N,trials=6000)
            line.append(f"L{L}:p={r['pass']:.2f}(d{r['daily']:.2f},m{r['maxdd']:.2f},t{r['time']:.2f})")
        print(f"S={S} N={N}: "+" ".join(line))
print()
print("=== D. Tight 1-step style: T=10%, D=6% static, daily 3% (Breakout-like 1-step), N=365 (no limit) and N=60 ===")
for S in [1.0,2.0,3.0]:
    for N in [60,365]:
        line=[]
        for L in [0.25,0.5,1,1.5,2,3]:
            r=sim(S,0.01*L,0.10,0.06,0.03,N,trials=6000)
            line.append(f"L{L}:p={r['pass']:.2f}(d{r['daily']:.2f},m{r['maxdd']:.2f},t{r['time']:.2f})")
        print(f"S={S} N={N}: "+" ".join(line))
print()
print("=== E. Consistency rule (best day <= 40% of total profit) effect, T=8%,D=10%,dl=5%, N=60, S=2 ===")
for L in [1,2,3,4]:
    r0=sim(2.0,0.01*L,0.08,0.10,0.05,60,trials=6000)
    r1=sim(2.0,0.01*L,0.08,0.10,0.05,60,consist=0.40,trials=6000)
    print(f"L{L}: no-rule pass={r0['pass']:.2f}  with-40%-rule pass={r1['pass']:.2f} (consist-fail {r1['consist']:.2f})")
print()
print("=== F. Daily-limit breach prob per day (single day), close-based vs intraday (reflection) ===")
from math import erf, sqrt
Phi=lambda x:0.5*(1+erf(x/sqrt(2)))
for sig in [0.01,0.015,0.02,0.025,0.03]:
    for d in [0.03,0.05]:
        pc=Phi(-d/sig); pi=2*Phi(-d/sig)
        print(f"sigma_d={sig:.3f} d={d:.2f}: close-based {pc:.4f}/day, intraday ~{pi:.4f}/day; P(no breach in 30d) close {((1-pc)**30):.3f} intraday {((1-pi)**30):.3f}")
print()
print("=== G. Fractional Kelly lifetime breach prob alpha^(2/f-1), alpha=0.90 (10% DD) and 0.94 (6% DD) ===")
for f in [1,0.5,0.25,0.1,0.05]:
    print(f"f={f}: P(ever breach 10%DD)={0.9**(2/f-1):.3f}  P(ever breach 6%DD)={0.94**(2/f-1):.3f}")
for a in [0.9,0.94]:
    fmax=2/(math.log(0.1)/math.log(a)+1)
    print(f"alpha={a}: Kelly fraction for lifetime breach<=10%: f<={fmax:.3f}")
print()
print("=== H. Fee EV worked example ===")
fee=600; p_pass=0.10; p_payout_given_funded=0.45; avg_payout=4000  # 4% of $100k plan (FPFX)
ev=p_pass*p_payout_given_funded*avg_payout-fee
be=fee/(p_payout_given_funded*avg_payout)
print(f"fee={fee}, p_pass={p_pass}, P(payout|funded)={p_payout_given_funded}, avg payout={avg_payout}: EV={ev:.0f}, break-even p_pass={be:.2f}")
for p in [0.1,0.2,0.33,0.5]:
    print(f" expected fee cost per funded account at p_pass={p}: {fee/p:.0f}")
