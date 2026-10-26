"""Own statistics: percentile of the 19-day result, years-to-reject, dollar outcomes by capital and Sharpe,
P(losing year), -20% pause false alarms, tax readings (slab with carry-forward, per-segment fit), capital for $500/month,
owner's time per dollar, FD-incremental comparison. numpy only."""
import numpy as np, math, json, sys
from math import erf, sqrt
rng=np.random.default_rng(7)
def Phi(z): return 0.5*(1+erf(z/sqrt(2)))
out={}
# ---- 1. where does -0.71% over 17.3 days sit?
res={}
for S in (0.0,0.3,0.5,0.8):
    for vol in (0.107,0.12,0.19):
        for days in (17.31,19):
            mu=S*vol*days/365; sd=vol*math.sqrt(days/365)
            z=(-0.00706-mu)/sd
            res[f"S{S}_vol{vol}_d{days}"]=round(Phi(z)*100,1)
out["percentile_of_minus0.71pct"]=res
# ---- 2. years to reject Sharpe 0 (one-sided 95%) at power 50% and 80%; also with kurtosis-inflated SE (Lo SE factor ~1.5 from T6f: Lo-SE 0.50 at n=2344 vs iid 1/sqrt(6.4)=0.395 -> 1.27x)
yrs={}
for S in (0.2,0.3,0.5,0.8):
    yrs[f"S{S}_power50"]=round((1.645/S)**2,1)
    yrs[f"S{S}_power80"]=round(((1.645+0.8416)/S)**2,1)
    yrs[f"S{S}_power50_LoSEx1.27"]=round((1.645*1.27/S)**2,1)
out["years_to_reject_zero"]=yrs
# ---- 3. Monte Carlo of dollar outcomes: daily t(4) returns scaled to vol, iid, 365 d/yr, 20000 paths, 5 years
def sim(S, vol, years=5, n=20000, nu=4):
    T=365*years
    t=rng.standard_t(nu, size=(n,T))*math.sqrt((nu-2)/nu)   # unit variance
    r=S*vol/365 + vol/math.sqrt(365)*t
    eq=np.cumprod(1+r,axis=1)
    return r, eq
mc={}
for S in (0.3,0.5,0.8):
    for vol,label in ((0.12,"weekly12"),(0.19,"daily19")):
        r,eq=sim(S,vol)
        yr_ret=eq[:,364::365]/np.concatenate([np.ones((eq.shape[0],1)),eq[:,364:-1:365]],axis=1)-1  # yearly returns
        yearly=yr_ret[:,:5]
        p_lose=float((yearly<0).mean())
        ann1=eq[:,364]-1
        gain5=eq[:,-1]-1
        # drawdown at weekly checks (every 7 days) from running peak of weekly marks
        wk=eq[:,6::7]
        pk=np.maximum.accumulate(wk,axis=1); dd=wk/pk-1
        def first_hit(level,yrs_):
            m=int(yrs_*52)
            return float((dd[:,:m]<=level).any(axis=1).mean())
        mc[f"S{S}_{label}"]=dict(
            exp_ann_ret_pct=round(float(ann1.mean())*100,2), median_ann_ret_pct=round(float(np.median(ann1))*100,2),
            p10_ann_pct=round(float(np.percentile(ann1,10))*100,2), p90_ann_pct=round(float(np.percentile(ann1,90))*100,2),
            p_losing_year=round(p_lose*100,1),
            p_5yr_total_neg=round(float((gain5<0).mean())*100,1),
            pause20_within_1y=round(first_hit(-0.20,1)*100,1), pause20_within_2y=round(first_hit(-0.20,2)*100,1), pause20_within_3y=round(first_hit(-0.20,3)*100,1),
            pause30_within_3y=round(first_hit(-0.30,3)*100,1),
            dd5y_median_pct=round(float(np.median(dd.min(axis=1)))*100,1),
            usd_per_month_at={cap: round(float(ann1.mean())*cap/12,0) for cap in (1000,2500,5000,25000,100000)})
out["mc"]=mc
# closed form $/month
cf={}
for S in (0.2,0.3,0.5,0.8):
    cf[f"S{S}_12vol"]={cap: round(S*0.12*cap/12,1) for cap in (1000,2500,5000,25000,100000)}
    cf[f"S{S}_12vol_capital_for_500pm"]=round(6000/(S*0.12))
out["closed_form_usd_per_month"]=cf
# ---- 4. slab tax with 4-year carry-forward, yearly, 30% on net positive; 5-year horizon; compare to 0.7x
def slab_after_tax(S, vol, n=20000, rate=0.30, years=5):
    r,eq=sim(S,vol,years,n)
    yr=eq[:,364::365]; prev=np.concatenate([np.ones((n,1)),yr[:,:-1]],axis=1)
    yret=yr/prev-1   # yearly returns (pre-tax, on pre-tax compounding; approximate: apply tax to $ gains on a $1 base each year, carry losses)
    gains=yret  # per $ of start-of-year equity; use $ on a constant 1.0 base to keep it simple (no compounding of tax drag)
    cf_=np.zeros(n); tot_pre=np.zeros(n); tot_tax=np.zeros(n)
    for y in range(years):
        g=gains[:,y]
        tot_pre+=g
        taxable=np.where(g>0, np.maximum(g-cf_,0), 0.0)
        cf_=np.where(g>0, np.maximum(cf_-g,0), cf_-g)   # carry forward grows on loss years (4-year limit ignored: horizon 5y)
        tot_tax+=rate*taxable
    after=tot_pre-tot_tax
    return float(tot_pre.mean()/years*100), float(after.mean()/years*100), float((after<0).mean()*100), float(cf_.mean()*100)
tax={}
for S in (0.3,0.5,0.8):
    for vol,label in ((0.12,"weekly12"),(0.19,"daily19")):
        pre,aft,pneg,unused=slab_after_tax(S,vol)
        tax[f"S{S}_{label}"]=dict(pre_tax_ann_pct=round(pre,2), slab30_after_tax_ann_pct=round(aft,2), keep_ratio=round(aft/pre,3), p_5y_after_tax_neg=round(pneg,1), unused_carryforward_pct_of_capital_at_5y=round(unused,2))
out["slab_tax_carryforward"]=tax
# per-segment VDA fit check from T6b (resource/07): net vs gross gains, six full years + 2026 partial
T6b=[(26.9,42.4),(30.6,57.7),(-6.8,3.6),(13.8,28.8),(22.4,43.4),(2.8,18.3),(1.5,7.9)]
x=np.array([a for a,b in T6b[:6]]); y=np.array([b for a,b in T6b[:6]])
A=np.vstack([np.ones_like(x),x]).T; coef,res_,_,_=np.linalg.lstsq(A,y,rcond=None)
fit=A@coef; rmse=float(np.sqrt(((fit-y)**2).mean()))
seg={}
for net in (3.8,6.9,12.2,4.0,9.0):
    gross=coef[0]+coef[1]*net
    seg[f"net{net}"]=dict(gross_gains=round(float(gross),1), after_tax=round(float(net-0.3*gross),2))
out["per_segment_vda_fit"]=dict(intercept=round(float(coef[0]),2), slope=round(float(coef[1]),3), rmse=round(rmse,2), lines=seg,
    T6b_check={f"{a}": (round(float(a-0.3*b),1)) for a,b in T6b})
# ---- 5. owner's time per expected dollar
time_={}
for cap in (1000,2500,5000,25000):
    for S in (0.3,0.5,0.8):
        exp=S*0.12*cap
        time_[f"cap{cap}_S{S}"]=dict(expected_usd_per_year=round(exp), weekly_book_usd_per_hour_at_26h=round(exp/26,1), daily_book_usd_per_hour_at_91h=round(exp*(0.19/0.12)/91,1))
out["owner_time"]=dict(assumption="weekly: 52 sessions x ~20 min + 12 monthly reconciliations x 30 min = ~23-26 h/yr; daily: 365 x 15 min = 91 h/yr (resource/07 says 'about 15 minutes' per daily execution)", table=time_)
# ---- 6. FD-incremental: owner's alternative is 100% FD. Design puts 70% in FD anyway; incremental = trend P&L - FD interest foregone on the 30% on venue
fd={}
for cap in (1000,5000,25000):
    for S in (0.3,0.5,0.8):
        trend=S*0.12*cap
        fd[f"cap{cap}_S{S}"]=dict(trend_pre_tax=round(trend), fd_foregone_on_30pct_at_6p75pct=round(0.3*cap*0.0675), incremental_over_all_FD=round(trend-0.3*cap*0.0675))
out["fd_incremental"]=fd
# ---- 7. excess Sharpe view: if USD cash ~4.5% (resource/07 [UNVERIFIED]) and raw Sharpe 0.5 at 12% vol = 6%/yr, excess = 1.5%/yr = Sharpe 0.125
out["excess_over_cash"]=dict(raw_S0p5_ret_pct=6.0, cash_pct=4.5, excess_pct=1.5, excess_sharpe=round(1.5/12,3), note="resource/07: design line excess Sharpe over 4.5% cash = 0.77 full-sample, ~0.2 over 2022-26 at TV 0.25")
json.dump(out, open(sys.argv[1],"w"), indent=1)
print(json.dumps(out, indent=1))
