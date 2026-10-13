import sys, csv, datetime as dt, collections, math
sys.path.insert(0, '/home/user/crypto-strategy/cex-mm/scripts')
import trend_backtest as T
UTC=dt.timezone.utc
close, fund = T.load_binance('trend-cache', dt.date(2026,9,30))
close={c:v for c,v in close.items() if c in ['BTC','ETH','XRP','BNB','ADA','LTC','LINK','DOGE','BCH']}
COINS=['BTC','ETH','XRP','BNB','ADA','LTC','LINK','DOGE','BCH']
# hourly lows
lows={}
for c in COINS:
    rows={}
    with open(f'hourly/{c}USDT-1h.csv') as f:
        r=csv.DictReader(f)
        cols=r.fieldnames
        tcol=[k for k in cols if 'time' in k.lower() or k.lower() in ('ts','ts_utc','date')][0]
        lcol=[k for k in cols if k.lower()=='low'][0]; ocol=[k for k in cols if k.lower()=='open'][0]
        for x in r:
            t=x[tcol]
            try:
                ts=dt.datetime.fromisoformat(t.replace('Z','')) if not t.isdigit() else dt.datetime.fromtimestamp(int(t)/(1000 if int(t)>1e11 else 1),UTC).replace(tzinfo=None)
            except Exception: continue
            rows[ts]=(float(x[ocol]),float(x[lcol]))
    lows[c]=rows
start=dt.date(2020,5,1); end=dt.date(2026,9,30)
days=sorted(set().union(*[set(v) for v in close.values()]))
# decision = Sunday candle (closes Monday 00:00 UTC); hold Monday 00:00 -> next Monday 00:00
n_on=0; hits={-0.1975:0,-0.30:0,-0.50:0}; worst=[]
for d in days:
    if not (start<=d<=end) or d.weekday()!=6: continue
    w=T.target_weights(close,d,T.LOOKS,T.VOL_WIN,0.25,True)
    t0=dt.datetime.combine(d+dt.timedelta(1),dt.time())  # Monday 00:00 UTC
    for c,x in w.items():
        if x<=0 or c not in COINS: continue
        if t0 not in lows[c]: continue
        n_on+=1
        p0=lows[c][t0][0]
        mn=min((lows[c][t0+dt.timedelta(hours=h)][1] for h in range(0,168) if t0+dt.timedelta(hours=h) in lows[c]), default=p0)
        dd=mn/p0-1
        for k in hits:
            if dd<=k: hits[k]+=1
        worst.append((dd,c,d+dt.timedelta(1)))
worst.sort()
print(f'coin-weeks long (Sunday-candle decision, TV 0.25): {n_on}; intra-week low vs Monday 00:00 open <= -19.75%: {hits[-0.1975]}, <= -30%: {hits[-0.30]}, <= -50%: {hits[-0.50]}')
print('worst 12 coin-weeks:', [(f'{dd:.0%}',c,str(m)) for dd,c,m in worst[:12]])
# per-year count of >=19.75% hits
by=collections.Counter(m.year for dd,c,m in worst if dd<=-0.1975)
print('by year (<= -19.75%):', dict(sorted(by.items())))
