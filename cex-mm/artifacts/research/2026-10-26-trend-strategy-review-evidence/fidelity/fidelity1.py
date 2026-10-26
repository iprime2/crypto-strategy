"""Reproduce the lead's daily-book numbers from the journal alone (no external data)."""
import json, math
import numpy as np
J='/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/daily_journal.jsonl'
rows=[json.loads(l) for l in open(J)]
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
CV={'BTC':0.001,'ETH':0.01,'XRP':1.0,'BNB':0.1,'ADA':1.0,'LTC':0.1,'LINK':1.0,'DOGE':100.0,'BCH':0.01}
MODEL_COST=7.31e-4
n=len(rows)
print("rows",n,"first",rows[0]['time'],"last",rows[-1]['time'])
print("start 1000.00  last equity %.2f  (%.2f%%)  model %.2f (%.2f%%)"%(rows[-1]['equity'],(rows[-1]['equity']/1000-1)*100,rows[-1]['model_equity'],(rows[-1]['model_equity']/1000-1)*100))
# 1. internal consistency
maxerr=0
for r in rows:
    eq=r['cash']+sum(q*CV[c]*r['mids'][c] for c,q in r['positions'].items())
    maxerr=max(maxerr,abs(eq-r['equity']))
print("equity == cash + positions*mid: max abs err %.2e"%maxerr)
# 2. per-rebalance decomposition
tot_price=0; tot_fund=0; tot_fee=0; tot_slip=0; tot_notional=0; n_orders=0
percoin_price={c:0.0 for c in COINS}; percoin_fee={c:0.0 for c in COINS}; percoin_slip={c:0.0 for c in COINS}; percoin_notional={c:0.0 for c in COINS}; percoin_orders={c:0 for c in COINS}
prs=[]  # paper period returns (equity_before[k]/equity[k-1]-1), incl funding, excl costs at k
prs_net=[] # equity[k]/equity[k-1]-1
mrs=[]
track=[]
print("\nk date        eq_prev   eq_before  eq_after   pricePnL  funding   fees   slip$   notional  gross  n_pos  n_ord  paper%  model%  diff_bp")
for k in range(1,n):
    p,r=rows[k-1],rows[k]
    price=sum(q*CV[c]*(r['mids'][c]-p['mids'][c]) for c,q in p['positions'].items())
    fund=r['funding']
    eb=p['equity']+price-fund
    assert abs(eb-r['equity_before'])<1e-6,(k,eb,r['equity_before'])
    fees=r['fees']; slip=sum(abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']) for o in r['orders'])
    assert abs((r['equity_before']-fees-slip)-r['equity'])<1e-6,(k,r['equity_before']-fees-slip,r['equity'])
    notional=sum(o['notional'] for o in r['orders'])
    for o in r['orders']:
        percoin_fee[o['coin']]+=o['fee']; percoin_slip[o['coin']]+=abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']); percoin_notional[o['coin']]+=o['notional']; percoin_orders[o['coin']]+=1
    for c,q in p['positions'].items(): percoin_price[c]+=q*CV[c]*(r['mids'][c]-p['mids'][c])
    tot_price+=price; tot_fund+=fund; tot_fee+=fees; tot_slip+=slip; tot_notional+=notional; n_orders+=len(r['orders'])
    pr=r['equity']/p['equity']-1; mr=r['model_equity']/p['model_equity']-1
    prs.append(r['equity_before']/p['equity']-1); prs_net.append(pr); mrs.append(mr)
    track.append((r['equity']/r['model_equity']-1)*1e4)
    print("%2d %s %9.2f %9.2f %9.2f %+9.2f %+8.3f %6.3f %6.3f %9.2f %5.2fx %4d %4d %+7.3f %+7.3f %+7.1f"%(k,r['time'][:10],p['equity'],r['equity_before'],r['equity'],price,-fund,fees,slip,notional,r['gross'],len(r['positions']),len(r['orders']),pr*100,mr*100,(pr-mr)*1e4))
# first rebalance costs
f0=rows[0]['fees']; s0=sum(abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']) for o in rows[0]['orders']); n0=sum(o['notional'] for o in rows[0]['orders'])
for o in rows[0]['orders']:
    percoin_fee[o['coin']]+=o['fee']; percoin_slip[o['coin']]+=abs(o['contracts'])*CV[o['coin']]*abs(o['price']-o['mid']); percoin_notional[o['coin']]+=o['notional']; percoin_orders[o['coin']]+=1
tot_fee+=f0; tot_slip+=s0; tot_notional+=n0; n_orders+=len(rows[0]['orders'])
print("\nTOTALS 8 Oct 16:37 -> 26 Oct 00:05")
print("  price P&L      %+8.2f"%tot_price)
print("  funding (paid) %+8.2f  (negative = received)"%(-tot_fund) if False else "  funding charge %+8.2f  (positive = paid by the book; journal 'funding' field summed)"%tot_fund)
print("  fees           %8.2f"%tot_fee)
print("  slippage $     %8.2f"%tot_slip)
print("  sum            %+8.2f   vs equity change %+8.2f"%(tot_price-tot_fund-tot_fee-tot_slip, rows[-1]['equity']-1000))
print("  orders %d  notional traded $%.2f"%(n_orders,tot_notional))
print("  cost per $ traded: fees %.2f bps, slippage %.2f bps, total %.2f bps (model 7.31, gate 14.62)"%(tot_fee/tot_notional*1e4,tot_slip/tot_notional*1e4,(tot_fee+tot_slip)/tot_notional*1e4))
print("\nPER COIN   pricePnL  fees   slip   notional  orders")
for c in COINS: print("  %-5s %+8.2f %6.3f %6.3f %9.2f %4d"%(c,percoin_price[c],percoin_fee[c],percoin_slip[c],percoin_notional[c],percoin_orders[c]))
# tracking
print("\nTRACKING paper/model-1 (bp) per rebalance:",[round(x,1) for x in track])
print("  min %.1f bp  max %.1f bp"%(min(track),max(track)))
# vol
prs=np.array(prs); prs_net=np.array(prs_net); mrs=np.array(mrs)
def ann(x): return x.std(ddof=1)*math.sqrt(365)*100
print("\nREALISED VOL of the book (period returns at rebalance marks, 18 periods, first = 7.5 h):")
print("  paper net-of-cost: %.1f%%/yr all 18; %.1f%%/yr excluding the first 7.5 h period"%(ann(prs_net),ann(prs_net[1:])))
print("  paper pre-cost   : %.1f%%/yr all 18; %.1f%%/yr excl first"%(ann(prs),ann(prs[1:])))
print("  model            : %.1f%%/yr all 18; %.1f%%/yr excl first"%(ann(mrs),ann(mrs[1:])))
print("  mean daily paper net %.3f%%, Sharpe-ish ann %.2f"%(prs_net[1:].mean()*100, prs_net[1:].mean()/prs_net[1:].std(ddof=1)*math.sqrt(365)))
# gross / positions
print("\nGROSS and positions per rebalance:")
for r in rows:
    held={c:q for c,q in r['positions'].items()}
    wpos=sum(1 for c in COINS if r['weights'].get(c,0)>0)
    print("  %s sig=%s gross %.2fx  n_held %d  n_weights>0 %d  cash %.1f%%  held %s"%(r['time'][:10],r['signal_day'],r['gross'],len(held),wpos,r['cash']/r['equity']*100,held))
# weight path & flips
print("\nWEIGHTS per coin per signal day (x100):")
print("  sig_day     "+" ".join("%6s"%c for c in COINS)+"  sum_w")
flips={c:0 for c in COINS}; lvl_changes={c:0 for c in COINS}
for i,r in enumerate(rows):
    w=r['weights']; print("  %s "%r['signal_day']+" ".join("%6.2f"%(w.get(c,0)*100) for c in COINS)+"  %5.2f"%sum(w.values()))
    if i:
        pw=rows[i-1]['weights']
        for c in COINS:
            a,b=pw.get(c,0)>0,w.get(c,0)>0
            if a!=b: flips[c]+=1
print("  on/off flips per coin over 18 transitions:",flips,"total",sum(flips.values()))
# model gross vs paper gross (rounding)
print("\nMODEL gross (sum w) vs PAPER gross per day:")
for r in rows: print("  %s model %.3f paper %.3f ratio %.2f"%(r['signal_day'],sum(r['weights'].values()),r['gross'],r['gross']/max(sum(r['weights'].values()),1e-9)))
# max drawdown on rebalance marks
eq=np.array([1000]+[r['equity'] for r in rows]); peak=np.maximum.accumulate(eq); dd=(eq/peak-1).min()
print("\nmax DD on rebalance marks %.2f%%  peak %.2f"%(dd*100,eq.max()))
json.dump({"track_bp":track,"paper_net_returns":prs_net.tolist(),"model_returns":mrs.tolist()},open("fidelity1_out.json","w"))
