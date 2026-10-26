"""ADA market-maker comparator: daily venue cash-flow from the Delta wallet ledger (tx.json), 20 Oct 11:06Z -> 26 Oct 17:30Z.
Purpose: how strong is 6 days of MM evidence vs 19 days of trend evidence."""
import json, datetime as dt, math, statistics as st
Q="/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/quant/"
tx=json.load(open(Q+"dash_state/tx.json"))
t0=dt.datetime(2026,10,20,11,6,tzinfo=dt.timezone.utc).timestamp()*1000
rows=[r for r in tx if r["t"]>=t0]
byday={}
tot={}
for r in rows:
    d=dt.datetime.fromtimestamp(r["t"]/1000,dt.timezone.utc).date().isoformat()
    byday.setdefault(d,{"cashflow":0,"commission":0,"funding":0})
    byday[d][r["type"]]=byday[d].get(r["type"],0)+r["amount"]
    tot[r["type"]]=tot.get(r["type"],0)+r["amount"]
print("totals since 20 Oct 11:06Z:", {k:round(v,2) for k,v in tot.items()}, "net", round(sum(tot.values()),2))
print("first balance", rows[0]["balance"], "last balance", rows[-1]["balance"])
net=[]
for d,v in sorted(byday.items()):
    n=sum(v.values()); net.append(n)
    print(d, {k:round(x,2) for k,x in v.items()}, "net", round(n,2))
# exclude partial first and last days for a daily series
full=net[1:-1]
print("full days", len(full), "mean", round(st.mean(full),2), "sd", round(st.stdev(full),2), "daily Sharpe", round(st.mean(full)/st.stdev(full),2), "annualised", round(st.mean(full)/st.stdev(full)*math.sqrt(365),1))
print("on $292: mean %/day", round(st.mean(full)/292*100,3), "-> %/yr simple", round(st.mean(full)/292*365*100,1))
# equity samples for a drawdown look
eq=[json.loads(l) for l in open(Q+"dash_state/equity.jsonl")]
pk=mdd=0; pk=eq[0]["equity"]
for e in eq:
    pk=max(pk,e["equity"]); mdd=min(mdd,e["equity"]/pk-1)
print("equity samples", len(eq), eq[0], eq[-1], "max DD on samples", round(mdd*100,2),"%")
