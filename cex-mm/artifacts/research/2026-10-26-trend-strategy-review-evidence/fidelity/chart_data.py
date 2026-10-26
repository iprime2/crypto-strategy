import json, sys, math, datetime as dt
sys.path.insert(0,'/home/user/crypto-strategy/cex-mm/scripts')
import trend_backtest as tb
R='/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/'
rows=[json.loads(l) for l in open(R+'daily_journal.jsonl')]
COINS=tb.COINS; CV={'BTC':0.001,'ETH':0.01,'XRP':1.0,'BNB':0.1,'ADA':1.0,'LTC':0.1,'LINK':1.0,'DOGE':100.0,'BCH':0.01}
D=json.load(open('delta_daily_2026-10-27.json')); UTC=dt.timezone.utc
closes={c:{dt.datetime.fromtimestamp(t,UTC).date():float(px) for t,px,*_ in D[c]['close'] if dt.datetime.fromtimestamp(t,UTC).date()<=dt.date(2026,10,25)} for c in COINS}
hourly={c:sorted((t,float(v)) for t,v in D[c]['funding']) for c in COINS}
fund_day={c:{} for c in COINS}
for c in COINS:
    bd={}
    for t,v in hourly[c]: bd.setdefault(dt.datetime.fromtimestamp(t,UTC).date(),[]).append(v)
    for d,xs in bd.items(): fund_day[c][d]=sum(xs)/len(xs)/100*3
bt=tb.backtest(closes,fund_day,dt.date(2026,10,9),dt.date(2026,10,25),long_only=True,capital=1000.0,cvals=CV)
labels=[r['time'][5:10].replace('-','/') for r in rows]  # 10/08 ..
paper=[r['equity'] for r in rows]; model=[r['model_equity'] for r in rows]
# backtest rebased to paper equity at row 1 (9 Oct 00:05), then chained
b=[None,paper[1]]
for x in bt['rets']: b.append(b[-1]*(1+x))
gross=[r['gross'] for r in rows]; mgross=[sum(r['weights'].values()) for r in rows]
# mean signal from fidelity2 output
sig=json.load(open('fidelity2_out.json'))['sigtab']; meansig=[s[6] for s in sig]
# per-coin price pnl
pc={c:0.0 for c in COINS}
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]
    for c,q in p['positions'].items(): pc[c]+=q*CV[c]*(r['mids'][c]-p['mids'][c])
json.dump({"labels":labels,"paper":paper,"model":model,"backtest":b,"gross":gross,"mgross":mgross,"meansig":meansig,"percoin":pc},open('chart_data.json','w'),indent=1)
print("labels",labels); print("backtest rebased path",[round(x,2) if x else None for x in b]); print("percoin",{c:round(v,2) for c,v in pc.items()})
