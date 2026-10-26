"""Independent check of the paper books against Delta public data and trend_backtest.py (read-only import)."""
import sys, json, math, datetime as dt, statistics
import numpy as np
sys.path.insert(0, '/home/user/crypto-strategy/cex-mm/scripts')
import trend_backtest as tb
R='/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/'
rows=[json.loads(l) for l in open(R+'daily_journal.jsonl')]
wrows=[json.loads(l) for l in open(R+'weekly_journal.jsonl')]
D=json.load(open('delta_daily_2026-10-27.json'))
CV=D['_cvals']; COINS=tb.COINS
UTC=dt.timezone.utc
LAST=dt.date(2026,10,25)   # last completed close (26 Oct candle still open at fetch time)
closes={c:{dt.datetime.fromtimestamp(t,UTC).date():float(px) for t,px,*_ in D[c]['close'] if dt.datetime.fromtimestamp(t,UTC).date()<=LAST} for c in COINS}
hourly={c:sorted((t,float(v)) for t,v in D[c]['funding']) for c in COINS}
def fund_between(since,until):
    return {c:sum(v for t,v in hourly[c] if since<=t<until)/100/8 for c in COINS}
def hours_covered(since,until):
    return {c:sum(1 for t,v in hourly[c] if since<=t<until) for c in COINS}
ts=lambda s: int(dt.datetime.fromisoformat(s).timestamp())

print("=== A. weights: journal vs target_weights() on freshly fetched Delta closes ===")
maxd=0; sigtab=[]
for r in rows:
    sd=dt.date.fromisoformat(r['signal_day'])
    w=tb.target_weights(closes,sd,tb.LOOKS,tb.VOL_WIN,0.40,True)
    d=max(abs(w.get(c,0)-r['weights'].get(c,0)) for c in COINS); maxd=max(maxd,d)
    # per-coin sig and vol
    sig={};vol={}
    for c in COINS:
        px=closes[c]; hist=[px[sd-dt.timedelta(k)] for k in range(121)]
        sig[c]=max(sum(tb.sign(hist[0]/hist[L]-1) for L in tb.LOOKS)/3,0.0)
        lr=[math.log(hist[k]/hist[k+1]) for k in range(60)]; vol[c]=math.sqrt(sum(x*x for x in lr)/60*365)
    # ex-ante book vol from 60-day covariance of log returns
    M=np.array([[math.log(closes[c][sd-dt.timedelta(k)]/closes[c][sd-dt.timedelta(k+1)]) for k in range(60)] for c in COINS])
    S=np.cov(M)*365
    wv=np.array([w.get(c,0) for c in COINS]); exante=math.sqrt(wv@S@wv)
    wfull=np.array([(0.40/9)/max(vol[c],0.05) for c in COINS]); exfull=math.sqrt(wfull@S@wfull)
    # paper actual weights (positions at this rebalance)
    wa=np.array([r['positions'].get(c,0)*CV[c]*r['mids'][c]/r['equity'] for c in COINS]); expaper=math.sqrt(wa@S@wa)
    sigtab.append((r['signal_day'],sig,vol,exante,exfull,expaper,sum(sig.values())/9))
    print("  %s maxdiff %.1e  sig=%s  mean_sig %.2f  exante vol: model %.1f%% paper %.1f%% full-signal %.1f%%"%(r['signal_day'],d,"".join({0.0:'0',1/3:'1',2/3:'2',1.0:'3'}.get(round(sig[c],4) if sig[c] not in (1/3,2/3) else sig[c],'?') for c in COINS),sum(sig.values())/9,exante*100,expaper*100,exfull*100))
print("  MAX |journal w - recomputed w| over 19 days x 9 coins: %.2e"%maxd)
print("  coin order for sig string:",COINS,"(0=flat,1=1/3,2=2/3,3=full)")
print("  60-day vol on last signal day:",{c:round(v,3) for c,v in sigtab[-1][2].items()})
allsig=[s for _,sig,*_ in sigtab for s in sig.values()]
print("  coin-days: n=%d  sig=0 %.0f%%  1/3 %.0f%%  2/3 %.0f%%  1 %.0f%%  mean sig %.2f"%(len(allsig),100*sum(1 for s in allsig if s==0)/len(allsig),100*sum(1 for s in allsig if abs(s-1/3)<1e-9)/len(allsig),100*sum(1 for s in allsig if abs(s-2/3)<1e-9)/len(allsig),100*sum(1 for s in allsig if s==1)/len(allsig),sum(allsig)/len(allsig)))
# correlation
sd=dt.date.fromisoformat(rows[-1]['signal_day'])
M=np.array([[math.log(closes[c][sd-dt.timedelta(k)]/closes[c][sd-dt.timedelta(k+1)]) for k in range(60)] for c in COINS]); C=np.corrcoef(M)
print("  mean pairwise 60-day correlation of the 9 coins (to %s): %.2f"%(sd,(C.sum()-9)/72))

print("\n=== B. funding: journal funding vs Delta FUNDING candles over each holding interval ===")
fdiff=0
F=[]
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; since,until=ts(p['time']),ts(r['time'])
    f=fund_between(since,until); hc=hours_covered(since,until)
    mine=sum(q*CV[c]*r['mids'][c]*f[c] for c,q in p['positions'].items())
    F.append(f)
    fdiff=max(fdiff,abs(mine-r['funding']))
    if k<=2 or k==len(rows)-1 or abs(mine-r['funding'])>1e-6: print("  %s journal %+.4f mine %+.4f  hours covered %s"%(r['time'][:10],r['funding'],mine,set(hc.values())))
print("  max |journal - mine| funding per interval: %.2e $"%fdiff)
print("  BTC funding rate per day over the window (bp/day):",[round(f['BTC']*1e4,2) for f in F])

print("\n=== C. model equity recomputed from journal weights + journal mids + my funding ===")
m=1000.0; worst=0
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; f=F[k-1]
    ret=sum(x*(r['mids'][c]/p['mids'][c]-1) for c,x in p['weights'].items())
    ret-=sum(x*f[c] for c,x in p['weights'].items())
    turn=sum(abs(r['weights'].get(c,0)-p['weights'].get(c,0)) for c in COINS)
    ret-=turn*7.31e-4
    m*=1+ret
    worst=max(worst,abs(m-r['model_equity']))
# the first row's model: 1000*(1 - turnover*cost) with prev weights {} -> turnover = sum w0
m0=1000*(1-sum(rows[0]['weights'].values())*7.31e-4)
print("  first-row model: journal %.4f mine %.4f"%(rows[0]['model_equity'],m0))
print("  last-row model: journal %.4f mine (chained from 1000 without the first-row cost) %.4f; with it %.4f"%(rows[-1]['model_equity'],m,m*m0/1000))
print("  (max abs diff along the path, chained with the first-row cost): computing...")
m=m0; worst=0
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; f=F[k-1]
    ret=sum(x*(r['mids'][c]/p['mids'][c]-1) for c,x in p['weights'].items())-sum(x*f[c] for c,x in p['weights'].items())-sum(abs(r['weights'].get(c,0)-p['weights'].get(c,0)) for c in COINS)*7.31e-4
    m*=1+ret; worst=max(worst,abs(m-r['model_equity']))
print("  max |journal model - mine| along the path: %.2e $"%worst)

print("\n=== D. tracking-error decomposition per holding period (paper minus model, bp of equity) ===")
tot={'round':0,'fund':0,'cost':0,'sum':0,'actual':0}
print("  period         rounding  funding   cost    sum   actual(paper-model ret)")
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; f=F[k-1]; E=p['equity']
    ret={c:r['mids'][c]/p['mids'][c]-1 for c in COINS}
    wa={c:p['positions'].get(c,0)*CV[c]*p['mids'][c]/E for c in COINS}
    wm={c:p['weights'].get(c,0) for c in COINS}
    rnd=sum((wa[c]-wm[c])*ret[c] for c in COINS)
    fund=-(r['funding']/E - sum(wm[c]*f[c] for c in COINS))
    slip=sum(abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']) for o in r['orders'])
    cost=-(r['fees']+slip)/E + sum(abs(r['weights'].get(c,0)-wm[c]) for c in COINS)*7.31e-4
    pr=r['equity']/p['equity']-1; mr=r['model_equity']/p['model_equity']-1
    s=rnd+fund+cost
    for kk,v in (('round',rnd),('fund',fund),('cost',cost),('sum',s),('actual',pr-mr)): tot[kk]+=v
    print("  %s->%s %+7.1f %+7.1f %+7.1f %+7.1f %+7.1f"%(p['time'][5:10],r['time'][5:10],rnd*1e4,fund*1e4,cost*1e4,s*1e4,(pr-mr)*1e4))
print("  TOTAL (bp)       %+7.1f %+7.1f %+7.1f %+7.1f %+7.1f"%tuple(tot[k]*1e4 for k in ('round','fund','cost','sum','actual')))
print("  (residual sum-actual is the compounding/equity-base difference; 'cost' = model turnover*7.31 bps minus paper fees+slippage, positive = paper cheaper)")
print("  abs rounding effect per period: mean %.1f bp, max %.1f bp"%(np.mean([abs(x) for x in []] or [0]),0) if False else "")
rnds=[]
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; E=p['equity']
    rnds.append(sum((p['positions'].get(c,0)*CV[c]*p['mids'][c]/E-p['weights'].get(c,0))*(r['mids'][c]/p['mids'][c]-1) for c in COINS)*1e4)
print("  |rounding| per period: mean %.1f bp, max %.1f bp; std of rounding term %.1f bp/day"%(np.mean(np.abs(rnds)),np.max(np.abs(rnds)),np.std(rnds,ddof=1)))

print("\n=== E. close-to-close trend_backtest.backtest() on Delta closes, 9..25 Oct (signal 8 Oct .. 24 Oct) ===")
fund_day={c:{} for c in COINS}
byday={c:{} for c in COINS}
for c in COINS:
    for t,v in hourly[c]: byday[c].setdefault(dt.datetime.fromtimestamp(t,UTC).date(),[]).append(v)
    for d,xs in byday[c].items(): fund_day[c][d]=sum(xs)/len(xs)/100*3
start,end=dt.date(2026,10,9),dt.date(2026,10,25)
bt_r=tb.backtest(closes,fund_day,start,end,long_only=True,capital=1000.0,cvals=CV)
bt_u=tb.backtest(closes,fund_day,start,end,long_only=True)
print("  rounded $1,000: days %d total %+.2f%%  avg gross %.2fx  vol %.1f%%  fees(ann) %.2f%% funding(ann) %.2f%%"%(bt_r['days'],(math.prod(1+x for x in bt_r['rets'])-1)*100,bt_r['gross'],bt_r['vol']*100,bt_r['fees']*100,bt_r['funding']*100))
print("  unrounded     : days %d total %+.2f%%  avg gross %.2fx  vol %.1f%%"%(bt_u['days'],(math.prod(1+x for x in bt_u['rets'])-1)*100,bt_u['gross'],bt_u['vol']*100))
# pair with paper: backtest nxt=D  <->  paper row dated D+1 (k=2..18)
paper=[rows[k]['equity']/rows[k-1]['equity']-1 for k in range(2,len(rows))]
model=[rows[k]['model_equity']/rows[k-1]['model_equity']-1 for k in range(2,len(rows))]
print("  paired daily returns (bp): day  backtest$1k  backtest_unr  paper  model")
for i,(a,b,c_,d_) in enumerate(zip(bt_r['rets'],bt_u['rets'],paper,model)):
    print("    %s %+7.1f %+7.1f %+7.1f %+7.1f"%(rows[i+2]['time'][5:10],a*1e4,b*1e4,c_*1e4,d_*1e4))
pa=np.array(paper); ba=np.array(bt_r['rets']); bu=np.array(bt_u['rets']); mo=np.array(model)
print("  cumulative 9 Oct 00:05 -> 26 Oct 00:05: paper %+.2f%%  backtest$1k %+.2f%%  backtest unrounded %+.2f%%  model %+.2f%%"%((np.prod(1+pa)-1)*100,(np.prod(1+ba)-1)*100,(np.prod(1+bu)-1)*100,(np.prod(1+mo)-1)*100))
print("  corr(paper, backtest$1k) %.3f  corr(paper, unrounded) %.3f  corr(model, unrounded) %.3f"%(np.corrcoef(pa,ba)[0,1],np.corrcoef(pa,bu)[0,1],np.corrcoef(mo,bu)[0,1]))
print("  realised vol (ann) over the 17 paired days: paper %.1f%%  backtest$1k %.1f%%  unrounded %.1f%%"%(pa.std(ddof=1)*math.sqrt(365)*100,ba.std(ddof=1)*math.sqrt(365)*100,bu.std(ddof=1)*math.sqrt(365)*100))
print("  paper first period 8 Oct 16:37 -> 9 Oct 00:05 (not in the backtest): %+.2f%%"%((rows[1]['equity']/1000-1)*100))

print("\n=== F. buy-and-hold of the 9 coins at journal mids, row0 (8 Oct 16:37) -> row18 (26 Oct 00:05) ===")
bh={c:rows[-1]['mids'][c]/rows[0]['mids'][c]-1 for c in COINS}
print("  per coin:",{c:round(v*100,2) for c,v in bh.items()}); print("  equal weight %+.2f%%  BTC %+.2f%%"%(sum(bh.values())/9*100,bh['BTC']*100))

print("\n=== G. rounding sensitivity: paper gross / model gross at other capitals, same weights and mids ===")
def rounded_gross(w,mids,E):
    return sum(round(w.get(c,0)*E/(mids[c]*CV[c]))*mids[c]*CV[c] for c in COINS)/E
for label,rs in (("daily TV0.40",rows),("weekly TV0.25",wrows)):
    for E in (1000,2500,5000,10000):
        ratios=[rounded_gross(r['weights'],r['mids'],E)/sum(r['weights'].values()) for r in rs]
        zero_btc=sum(1 for r in rs if r['weights'].get('BTC',0)>0 and round(r['weights']['BTC']*E/(r['mids']['BTC']*CV['BTC']))==0)
        zero_bnb=sum(1 for r in rs if r['weights'].get('BNB',0)>0 and round(r['weights']['BNB']*E/(r['mids']['BNB']*CV['BNB']))==0)
        print("  %-14s $%6d: gross ratio mean %.2f  min %.2f  max %.2f  mean|ratio-1| %.2f  BTC rounds to 0 on %d/%d signal days, BNB %d/%d"%(label,E,np.mean(ratios),min(ratios),max(ratios),np.mean(np.abs(np.array(ratios)-1)),zero_btc,sum(1 for r in rs if r['weights'].get('BTC',0)>0),zero_bnb,sum(1 for r in rs if r['weights'].get('BNB',0)>0)))

print("\n=== H. weekly book ===")
for r in wrows:
    E=r['equity']; sw=sum(r['weights'].values())
    print("  %s sig %s equity %.2f model %.2f (paper-model %+.1f bp) fees %.3f funding %+.3f orders %d skipped %s gross %.3f model-gross %.3f ratio %.2f"%(r['time'][:10],r['signal_day'],E,r['model_equity'],(E/r['model_equity']-1)*1e4,r['fees'],r['funding'],len(r['orders']),r['skipped'],r['gross'],sw,r['gross']/sw))
    for c in COINS:
        w=r['weights'].get(c,0)
        if w>0:
            tgt=w*E/(r['mids'][c]*CV[c]); print("     %-4s w %.4f  target contracts %.2f -> %d  held %s"%(c,w,tgt,round(tgt),r['positions'].get(c,0)))
# weekly costs
wn=sum(o['notional'] for r in wrows for o in r['orders']); wf=sum(r['fees'] for r in wrows); wsl=sum(abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']) for r in wrows for o in r['orders'])
print("  weekly costs: %d orders, notional $%.2f, fees %.2f bps, slippage %.2f bps, total %.2f bps per $ traded"%(sum(len(r['orders']) for r in wrows),wn,wf/wn*1e4,wsl/wn*1e4,(wf+wsl)/wn*1e4))
# weekly: did the 10% band bite? recompute plan with band 0 vs 0.10 at row 2
p,r=wrows[0],wrows[1]
import importlib.util
spec=importlib.util.spec_from_file_location('trend_paper','/home/user/crypto-strategy/cex-mm/scripts/trend_paper.py'); tp=importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
plan0,sk0=tp.plan_orders(p['positions'],r['weights'],r['equity_before'],r['mids'],CV,0.0)
plan1,sk1=tp.plan_orders(p['positions'],r['weights'],r['equity_before'],r['mids'],CV,0.10)
print("  26 Oct weekly plan with band 0: %d orders; with band 0.10: %d orders, skipped %d -> the band changed nothing on either Monday so far"%(len(plan0),len(plan1),len(sk1)))
# weekly week-1 P&L per coin
print("  weekly week 1 P&L per coin (positions x mid change 19->26 Oct):",{c:round(q*CV[c]*(r['mids'][c]-p['mids'][c]),2) for c,q in p['positions'].items()})
# weekly weights vs my recompute
for r in wrows:
    sd=dt.date.fromisoformat(r['signal_day']); w=tb.target_weights(closes,sd,tb.LOOKS,tb.VOL_WIN,0.25,True)
    print("  weekly %s max |journal w - recomputed| %.1e"%(r['signal_day'],max(abs(w.get(c,0)-r['weights'].get(c,0)) for c in COINS)))

print("\n=== I. statistics the lead quoted ===")
from math import erf,sqrt
Phi=lambda z:0.5*(1+erf(z/sqrt(2)))
for days in (19,17.31):
    for vol in (0.12,0.19):
        mu=0.5*vol*days/365; sd=vol*sqrt(days/365); z=(-0.0071-mu)/sd
        print("  Sharpe 0.5, vol %.0f%%, %.1f days: expected %+.2f%% sd %.2f%% -> realised -0.71%% is the %.0fth percentile"%(vol*100,days,mu*100,sd*100,Phi(z)*100))
for S in (0.3,0.5,0.8): print("  years to reject Sharpe 0 at 95%% one-sided, 50%% power, true Sharpe %.1f: %.1f"%(S,(1.645/S)**2))
print("  with 80%% power (z 1.645+0.842): Sharpe 0.5 -> %.1f years"%(((1.645+0.842)/0.5)**2))
json.dump({"sigtab":[(a,b,c,d,e,f,g) for a,b,c,d,e,f,g in sigtab]},open("fidelity2_out.json","w"),default=str)
