import csv, json, math, datetime as dt, collections, statistics
UTC=dt.timezone.utc
def load_hourly(p):
    rows=[]
    with open(p) as f:
        r=csv.DictReader(f)
        for x in r:
            rows.append((dt.datetime.fromisoformat(x['ts_utc']), float(x['ret']), float(x['gross'])))
    return rows
# ---- (b) day-stop at k=0.5 on the native daily series: stop-fill level at hourly resolution
for name,path,k,stop in [('prop daily native k=0.5',"qd_runs/hourly_daily_tv40.csv",0.5,0.015),('prop weekly native k=0.5',"qd_runs/hourly_weekly_tv40.csv",0.5,0.015),('own weekly TV0.25 (no stop)',"qd_runs/hourly_design_weekly_tv25_band10.csv",1.0,None)]:
    rows=load_hourly(path)
    bydays=collections.defaultdict(list)
    for t,r,g in rows: bydays[t.date()].append((t,r*k,g))
    recs=[]
    for d,hs in bydays.items():
        eq=1.0; lo=1.0; fill=None; fillhr=None; closeret=None
        for t,r,g in hs:
            eq*=(1+r); lo=min(lo,eq)
            if stop and fill is None and eq-1<=-stop: fill=eq-1; fillhr=t.hour
        recs.append((d, eq-1, lo-1, fill, fillhr, max(g for _,_,g in hs)))
    worst=sorted(recs,key=lambda x:x[2])[:12]
    print('==',name)
    print('  worst intraday-low days (date, close, low, stopfill@hourly, hourUTC of fill, gross):')
    for w in worst: print('   ',w[0],f'close {w[1]:+.2%} low {w[2]:+.2%}', ('fill %+.2f%% at %02d UTC (%02d:30 IST)'%(w[3]*100,w[4],(w[4]+5)%24) if w[3] is not None else 'no fill'), f'gross {w[5]:.2f}')
    if stop:
        fills=[x for x in recs if x[3] is not None]
        print(f'  stop trips: {len(fills)} ({len(fills)/ (len(recs)/365):.1f}/yr); fill below -2.0%: {sum(1 for x in fills if x[3]<=-0.02)}; below -2.5%: {sum(1 for x in fills if x[3]<=-0.025)}; below -3.0% (breach): {sum(1 for x in fills if x[3]<=-0.03)}')
        # hours with a single-hour loss >= 1.5% at k (i.e. one hour alone could trip from flat to the stop)
        big=[(t,r) for t,r,g in rows if r*k<=-0.015]
        print(f'  single hours with ret <= -1.5% at k: {len(big)}:', [(t.isoformat(),round(r*k*100,2)) for t,r in big])
    # IST hour distribution of the big losing hours
    big=[(t,r*k) for t,r,g in rows if r*k<=-0.0075]
    ist=collections.Counter(((t.hour*60+330)//60)%24 for t,_ in big)
    night=sum(v for h,v in ist.items() if h<7 or h>=23)
    print(f'  hours with ret <= -0.75%: {len(big)}; share falling 23:00-07:00 IST: {night/len(big):.0%}; IST-hour histogram {dict(sorted(ist.items()))}')
# ---- (a) Delta vs Binance funding per coin, overlapping window
d=json.load(open('trend-cache/delta-2026-10-12.json'))
import glob
print('== funding per coin (annualized %, long pays): Delta hourly samples are pct per 8h; Binance 8h archive')
for c in ['BTC','ETH','XRP','BNB','ADA','LTC','LINK','DOGE','BCH']:
    fu=d[c]['funding']
    ts=[dt.datetime.fromtimestamp(t,UTC) for t,_ in fu]
    t0,t1=min(ts),max(ts)
    # take samples at 00/08/16 UTC only (one per interval)
    smp=[p for t,p in fu if dt.datetime.fromtimestamp(t,UTC).hour in (0,8,16)]
    m=statistics.mean(smp); ann=m/100*3*365*100
    # Binance same window
    rates=[]
    for f in sorted(glob.glob(f'trend-cache/binance-{c}USDT-fundingRate-*.csv')):
        for row in csv.DictReader(open(f)):
            t=dt.datetime.fromtimestamp(int(row['calc_time'])/1000,UTC)
            if t0<=t<=t1: rates.append(float(row['last_funding_rate']))
    bann=statistics.mean(rates)*3*365*100 if rates else float('nan')
    share_cap=sum(1 for p in smp if p>=0.0099)/len(smp)
    print(f'  {c:5s} Delta {t0.date()}..{t1.date()} n={len(smp)} mean {m:.4f}%/8h = {ann:5.1f}%/yr, at>=0.0099 {share_cap:.0%} | Binance same window {bann:5.1f}%/yr | candles to {dt.datetime.fromtimestamp(d[c]["close"][0][0],UTC).date()}')
# ---- (e) rounding granularity at $1,000, TV 0.25, full-on signal, today's Delta closes and 60d vol
cv={'BTC':0.001,'ETH':0.01,'XRP':1.0,'BNB':0.1,'ADA':1.0,'LTC':0.1,'LINK':1.0,'DOGE':100.0,'BCH':0.01}
print('== rounding at E=$1,000, TV 0.25, sig=1 (full on): target $ vs contract $ (Delta closes 2026-10-12, 60d realized vol)')
for c in cv:
    cl=sorted(d[c]['close'])  # ascending by time
    px=[p for t,p in cl]
    lr=[math.log(px[i]/px[i-1]) for i in range(len(px)-60,len(px))]
    vol=math.sqrt(365*sum(x*x for x in lr)/60)
    w=(0.25/9)/max(vol,0.05)
    tgt=w*1000; cval=cv[c]*px[-1]; n=round(tgt/cval)
    print(f'  {c:5s} px {px[-1]:>10.4f} vol {vol:4.0%} w {w:5.1%} target ${tgt:6.1f} contract ${cval:7.2f} -> {n} contracts (${n*cval:6.1f}, {((n*cval)/tgt-1) if tgt else 0:+.0%} vs target)')
