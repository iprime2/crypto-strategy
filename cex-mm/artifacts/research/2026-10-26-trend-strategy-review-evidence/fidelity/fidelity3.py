import json, datetime as dt, math, sys
import numpy as np
UTC=dt.timezone.utc
old=json.load(open('/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/trend-cache/delta-2026-10-12.json'))
new=json.load(open('delta_daily_2026-10-27.json'))
COINS="BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
print("=== FUNDING candle revision check: cache fetched ~12-13 Oct vs fetch today, overlapping hours 1..11 Oct ===")
t_lo=int(dt.datetime(2026,10,1,tzinfo=UTC).timestamp()); t_hi=int(dt.datetime(2026,10,12,tzinfo=UTC).timestamp())
for c in COINS:
    o={t:v for t,v in old[c]['funding'] if t_lo<=t<t_hi}; n={t:v for t,v in new[c]['funding'] if t_lo<=t<t_hi}
    common=sorted(set(o)&set(n)); diffs=[(t,o[t],n[t]) for t in common if abs(o[t]-n[t])>1e-12]
    print("  %-4s old n=%d new n=%d common=%d  differing=%d  only-old=%d only-new=%d"%(c,len(o),len(n),len(common),len(diffs),len(set(o)-set(n)),len(set(n)-set(o))), end='')
    if diffs: print("  e.g.",[(dt.datetime.fromtimestamp(t,UTC).strftime('%d %H:%M'),a,b) for t,a,b in diffs[:3]])
    else: print()
# daily closes revision check
print("=== daily close revision check (same window) ===")
for c in COINS:
    o={t:v for t,v,*_ in old[c]['close'] if t_lo<=t<t_hi}; n={t:v for t,v,*_ in new[c]['close'] if t_lo<=t<t_hi}
    d=[(t,o[t],n[t]) for t in set(o)&set(n) if abs(o[t]-n[t])>1e-9]
    print("  %-4s common %d differing %d %s"%(c,len(set(o)&set(n)),len(d),d[:2]))

R='/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/'
rows=[json.loads(l) for l in open(R+'daily_journal.jsonl')]
CV={'BTC':0.001,'ETH':0.01,'XRP':1.0,'BNB':0.1,'ADA':1.0,'LTC':0.1,'LINK':1.0,'DOGE':100.0,'BCH':0.01}
print("\n=== model turnover vs paper notional ===")
mt=sum(sum(abs(rows[k]['weights'].get(c,0)-(rows[k-1]['weights'].get(c,0) if k else 0)) for c in COINS)*(rows[k-1]['model_equity'] if k else 1000) for k in range(len(rows)))
pn=sum(o['notional'] for r in rows for o in r['orders'])
print("  model turnover $%.0f x 7.31 bps = $%.3f ; paper notional $%.0f at 6.33 bps = $%.3f ; paper traded %.0f%% more notional"%(mt,mt*7.31e-4,pn,pn*6.33e-4,(pn/mt-1)*100))
print("\n=== basket moves on the big days (equal-weight mean of mid changes) vs book ===")
for k in range(1,len(rows)):
    p,r=rows[k-1],rows[k]; bm=np.mean([r['mids'][c]/p['mids'][c]-1 for c in COINS]); br=r['equity_before']/p['equity']-1
    if abs(bm)>0.025 or abs(br)>0.005: print("  %s -> %s basket %+.2f%%  book %+.2f%%  gross held %.2fx  beta-implied %+.2f%%"%(p['time'][5:10],r['time'][5:10],bm*100,br*100,p['gross'],p['gross']*bm*100))
print("\n=== run-time regularity (UTC) ===")
print("  ",[r['time'][11:19] for r in rows])
print("\n=== weekly vs daily over 19 Oct 00:05 -> 26 Oct 00:05 ===")
w=[json.loads(l) for l in open(R+'weekly_journal.jsonl')]
d19=[r for r in rows if r['time'].startswith('2026-10-19')][0]; d26=rows[-1]
print("  daily %.2f -> %.2f = %+.2f%% (gross 0.20x at start); weekly %.2f -> %.2f = %+.2f%% (gross 0.08x)"%(d19['equity'],d26['equity'],(d26['equity']/d19['equity']-1)*100,w[0]['equity'],w[1]['equity'],(w[1]['equity']/w[0]['equity']-1)*100))
print("  basket 19->26 Oct: %+.2f%%"%(np.mean([d26['mids'][c]/d19['mids'][c]-1 for c in COINS])*100))
