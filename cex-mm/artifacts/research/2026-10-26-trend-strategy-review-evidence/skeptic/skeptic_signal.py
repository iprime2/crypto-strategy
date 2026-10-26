"""Own implementation of the rule (from resource/07's specification, not imported from the repo) applied to Delta closes fetched today:
(a) reproduce the journal weights, (b) own close-to-close whole-contract backtest 9-26 Oct, (c) funding recomputation per rebalance interval,
(d) rounding at other capitals (weekly book), (e) ex-ante book vol, (f) exposure-expressed ratio."""
import json, math, datetime as dt, statistics as st, sys
OUT=sys.argv[1]
R="/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/"
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
cv=json.load(open(f"{OUT}/delta_raw/products_cv.json"))
raw=json.load(open(f"{OUT}/delta_raw/daily_candles.json"))
fund_raw=json.load(open(f"{OUT}/delta_raw/funding_1h.json"))
today=dt.datetime.now(dt.timezone.utc).date()
close={}
for c in COINS:
    close[c]={}
    for t,o,h,l,cl,v in raw[c]:
        d=dt.datetime.fromtimestamp(t,dt.timezone.utc).date()
        if d<today: close[c][d]=float(cl)   # drop today's partial candle
def sgn(x): return (x>0)-(x<0)
def weights(d, tv):
    sig,vol={},{}
    for c in COINS:
        px=close[c]
        hist=[px.get(d-dt.timedelta(k)) for k in range(121)]
        if any(h is None for h in hist): continue
        s=sum(sgn(hist[0]/hist[L]-1) for L in (20,60,120))/3
        sig[c]=max(s,0.0)
        r=[math.log(hist[k]/hist[k+1]) for k in range(60)]
        vol[c]=math.sqrt(sum(x*x for x in r)/60*365)
    n=len(sig) or 1
    w={c:sig[c]*(tv/n)/max(vol[c],0.05) for c in sig}
    g=sum(abs(x) for x in w.values())
    if g>2.0: w={c:x*2.0/g for c,x in w.items()}
    return w,sig,vol
res={}
# (a) weights reproduction
for name,tv in (("daily",0.40),("weekly",0.25)):
    J=[json.loads(l) for l in open(R+f"{name}_journal.jsonl") if l.strip()]
    maxdiff=0; sigs=[]
    for r in J:
        d=dt.date.fromisoformat(r["signal_day"])
        w,sig,vol=weights(d,tv)
        for c in COINS: maxdiff=max(maxdiff, abs(w.get(c,0)-r["weights"].get(c,0)))
        sigs.append(sig)
    res[f"{name}_weights_maxabsdiff"]=maxdiff
    if name=="daily":
        flat=sum(1 for s in sigs for v in s.values() if v==0); third=sum(1 for s in sigs for v in s.values() if abs(v-1/3)<1e-9); full=sum(1 for s in sigs for v in s.values() if v==1)
        res["daily_signal_counts"]=dict(coin_days=sum(len(s) for s in sigs), flat=flat, third=third, two_thirds=sum(1 for s in sigs for v in s.values() if abs(v-2/3)<1e-9), full=full, mean=round(sum(v for s in sigs for v in s.values())/sum(len(s) for s in sigs),3))
# (b) own close-to-close backtest, whole contracts, $1000, TV 0.40, taker 5.31 + 2 bps slippage, funding from hourly mean x3 per day
def fund_day(c,d):
    xs=[float(cl) for t,o,h,l,cl in fund_raw[c] if dt.datetime.fromtimestamp(t,dt.timezone.utc).date()==d]
    return sum(xs)/len(xs)/100*3 if xs else 0.0
def backtest(start,end,capital,tv,round_contracts=True):
    days=sorted(set.intersection(*[set(close[c]) for c in COINS]))
    eq=capital; units={}; rets=[]; traded_tot=0; fees_tot=0; fund_tot=0
    for d,nxt in zip(days,days[1:]):
        if not(start<=nxt<=end): continue
        w,_,_=weights(d,tv)
        new={}
        for c,x in w.items():
            u=x*eq/close[c][d]
            if round_contracts: u=round(u/cv[c])*cv[c]
            if u: new[c]=u
        traded=sum(abs(new.get(c,0)-units.get(c,0))*close[c][d] for c in set(new)|set(units))
        pnl=sum(u*(close[c][nxt]-close[c][d]) for c,u in new.items())
        fpay=sum(u*close[c][d]*fund_day(c,nxt) for c,u in new.items())
        cost=traded*(5.31+2.0)/1e4
        r=(pnl-fpay-cost)/eq
        eq*=1+r; rets.append((nxt.isoformat(),round(r*100,3)))
        traded_tot+=traded; fees_tot+=cost; fund_tot+=fpay
        units=new
    return dict(final=round(eq,2), ret_pct=round((eq/capital-1)*100,3), rets=rets, traded=round(traded_tot,2), costs=round(fees_tot,3), funding=round(fund_tot,3))
s,e=dt.date(2026,10,9),dt.date(2026,10,25)
res["bt_1000_rounded_9to25Oct"]=backtest(s,e,1000,0.40,True)
res["bt_unrounded_9to25Oct"]=backtest(s,e,1000,0.40,False)
res["bt_1000_rounded_8to25Oct_incl_first_day"]=backtest(dt.date(2026,10,8),e,1000,0.40,True)
# matching paper window: 9 Oct 00:05 -> 26 Oct 00:05 rows
J=[json.loads(l) for l in open(R+"daily_journal.jsonl") if l.strip()]
res["paper_9Oct_to_26Oct_ret_pct"]=round((J[-1]["equity"]/J[1]["equity"]-1)*100,3)
res["model_9Oct_to_26Oct_ret_pct"]=round((J[-1]["model_equity"]/J[1]["model_equity"]-1)*100,3)
# daily-return correlation paper vs rounded backtest (paper row dated D+1 <-> backtest nxt=D)
pr=[(J[i+1]["equity"]/J[i]["equity"]-1) for i in range(1,len(J)-1)]  # 9->10 ... 25->26
br=[r/100 for d,r in res["bt_1000_rounded_9to25Oct"]["rets"]][1:]   # nxt 10..25 -> paper rows 11..26? align: backtest nxt=D covers close D-1 -> close D; paper row D+1 covers 00:05 D -> 00:05 D+1. So backtest nxt=D pairs with paper period ending row dated D+1.
# paper periods: index i: row i -> row i+1 (row i+1 dated D+1), i from 1 (9->10 Oct) to 17 (25->26). backtest rets nxt from 9 Oct..25 Oct: 17 entries. pair backtest nxt=D (D=9..25) with paper period ending on row dated D+1 (10..26) => same index
br=[r/100 for d,r in res["bt_1000_rounded_9to25Oct"]["rets"]]
n=min(len(pr),len(br)); pr,br=pr[:n],br[:n]
mp,mb=st.mean(pr),st.mean(br)
corr=sum((a-mp)*(b-mb) for a,b in zip(pr,br))/math.sqrt(sum((a-mp)**2 for a in pr)*sum((b-mb)**2 for b in br))
res["corr_paper_vs_backtest_daily"]=round(corr,4); res["n_pairs"]=n
# (c) funding recomputation per interval with trend_paper's formula (sum of hourly closes with since<=t<until, /100/8) on today's candles
fund_cmp=[]
tot_j=tot_r=0
for a,b in zip(J,J[1:]):
    since=int(dt.datetime.fromisoformat(a["time"]).timestamp()); until=int(dt.datetime.fromisoformat(b["time"]).timestamp())
    paid=0; hours=None
    for c,q in a["positions"].items():
        xs=[float(cl) for t,o,h,l,cl in fund_raw[c] if since<=t<until]
        hours=len(xs)
        rate=sum(xs)/100/8
        paid+=q*cv[c]*b["mids"][c]*rate
    fund_cmp.append((b["time"][:16], round(b["funding"],4), round(paid,4), hours))
    tot_j+=b["funding"]; tot_r+=paid
res["funding_journal_vs_recomputed"]=dict(rows=fund_cmp, journal_total=round(tot_j,4), recomputed_total=round(tot_r,4), journal_lower_on=sum(1 for r in fund_cmp if r[1]<r[2]))
# funding by hour-of-day: are the hours just after 00:00 provisional? compare BTC funding candle close at 00:00-02:00 vs 03:00+ (can't see provisional values now; report the pattern instead)
# annualised funding cost of the book: journal and recomputed, as % of equity
res["funding_annualised_pct_of_equity"]=dict(journal=round(tot_j/17.31*365/1000*100,2), recomputed=round(tot_r/17.31*365/1000*100,2))
# (d) rounding at other capitals for the weekly rows
W=[json.loads(l) for l in open(R+"weekly_journal.jsonl") if l.strip()]
rnd={}
for r in W:
    eq=r["equity_before"]; w=r["weights"]; mids=r["mids"]
    model_gross=sum(abs(x) for x in w.values())
    row={}
    for cap in (1000,2500,5000,10000):
        g=sum(abs(round(w.get(c,0)*cap/(mids[c]*cv[c])))*mids[c]*cv[c] for c in COINS)/cap
        row[cap]=round(g/model_gross,3) if model_gross else None
    btc_t=w.get("BTC",0)*eq/(mids["BTC"]*cv["BTC"]); bnb_t=w.get("BNB",0)*eq/(mids["BNB"]*cv["BNB"])
    rnd[r["signal_day"]]=dict(model_gross=round(model_gross,4), paper_gross=round(r["gross"],4), ratio_by_capital=row, btc_target_contracts_at_1000=round(btc_t,2), bnb_target_contracts_at_1000=round(bnb_t,2))
res["weekly_rounding"]=rnd
# daily book: same ratio by capital, summary
drows=[]
for r in J:
    w=r["weights"]; mids=r["mids"]; mg=sum(abs(x) for x in w.values())
    if mg==0: continue
    drows.append({cap: sum(abs(round(w.get(c,0)*cap/(mids[c]*cv[c])))*mids[c]*cv[c] for c in COINS)/cap/mg for cap in (1000,2500,5000)})
res["daily_rounding_ratio_range"]={cap:(round(min(x[cap] for x in drows),2), round(max(x[cap] for x in drows),2)) for cap in (1000,2500,5000)}
# (e) ex-ante book vol: 60-day covariance of log returns on the last signal day; model weights, paper weights, all-full-signal weights
d=dt.date.fromisoformat(J[-1]["signal_day"])
rets={c:[math.log(close[c][d-dt.timedelta(k)]/close[c][d-dt.timedelta(k+1)]) for k in range(60)] for c in COINS}
def cov(a,b):
    ma,mb=st.mean(a),st.mean(b); return sum((x-ma)*(y-mb) for x,y in zip(a,b))/len(a)*365
Sig={(a,b):cov(rets[a],rets[b]) for a in COINS for b in COINS}
def book_vol(w): return math.sqrt(sum(w.get(a,0)*w.get(b,0)*Sig[(a,b)] for a in COINS for b in COINS))
wm=J[-1]["weights"]
eq=J[-1]["equity"]; wp={c:q*cv[c]*J[-1]["mids"][c]/eq for c,q in J[-1]["positions"].items()}
_,_,vol=weights(d,0.40)
wfull={c:(0.40/9)/max(vol[c],0.05) for c in COINS}
corrs=[Sig[(a,b)]/math.sqrt(Sig[(a,a)]*Sig[(b,b)]) for i,a in enumerate(COINS) for b in COINS[i+1:]]
res["ex_ante_vol_last_signal_day"]=dict(model=round(book_vol(wm)*100,1), paper=round(book_vol(wp)*100,1), all_full_signal_TV040=round(book_vol(wfull)*100,1), mean_pairwise_corr=round(st.mean(corrs),3), coin_vols={c:round(vol[c]*100,0) for c in COINS})
json.dump(res, open(f"{OUT}/signal_recompute.json","w"), indent=1, default=str)
for k,v in res.items():
    if k in ("bt_1000_rounded_9to25Oct","bt_unrounded_9to25Oct","bt_1000_rounded_8to25Oct_incl_first_day"):
        print(k, {kk:vv for kk,vv in v.items() if kk!="rets"}); print("   rets:", v["rets"])
    elif k=="funding_journal_vs_recomputed":
        print(k); [print("   ",r) for r in v["rows"]]; print("   totals", v["journal_total"], v["recomputed_total"], "journal lower on", v["journal_lower_on"])
    else: print(k, v)
