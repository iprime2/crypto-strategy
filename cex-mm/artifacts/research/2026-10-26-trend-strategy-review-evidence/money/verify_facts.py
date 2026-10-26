#!/usr/bin/env python3
"""Recompute the lead's inline facts about the two trend paper books from the journals (read-only)."""
import json, math, sys, statistics as st
R = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm"
rows = [json.loads(l) for l in open(f"{R}/daily_journal.jsonl")]
wk = [json.loads(l) for l in open(f"{R}/weekly_journal.jsonl")]
out = []
P = out.append
P("DAILY BOOK (TV 0.40, band 0), journal %s" % f"{R}/daily_journal.jsonl")
P("rebalances: %d  first %s  last %s" % (len(rows), rows[0]["time"][:16], rows[-1]["time"][:16]))
eq0, eqN = 1000.0, rows[-1]["equity"]
P("equity at last rebalance %.2f -> %.3f%% since start; model %.2f -> %.3f%%" % (eqN, 100*(eqN/eq0-1), rows[-1]["model_equity"], 100*(rows[-1]["model_equity"]/eq0-1)))
dev = [(r["equity"]/r["model_equity"]-1)*100 for r in rows]
P("paper minus model, pct, min %.3f max %.3f (last %.3f)" % (min(dev), max(dev), dev[-1]))
orders = [o for r in rows for o in r["orders"]]
notional = sum(abs(o["notional"]) for o in orders)
fees = sum(o["fee"] for o in orders)
fee_j = sum(r["fees"] for r in rows)
slip = sum(abs(o["notional"])*o["slippage_bps"] for o in orders)/notional
P("orders %d  traded notional $%.2f  fees $%.3f (journal fee field %.3f) = %.2f bps per $  slippage notional-wtd %.2f bps  total %.2f bps (model 7.31, gate 14.62)" % (len(orders), notional, fees, fee_j, 1e4*fees/notional, slip, 1e4*fees/notional+slip))
fund = sum(r["funding"] for r in rows)
P("funding received, sum of journal field: $%.3f (positive = received)" % fund)
gross = [r["gross"] for r in rows]
P("gross exposure min %.3fx max %.3fx mean %.3fx last %.3fx" % (min(gross), max(gross), st.mean(gross), gross[-1]))
# realised vol from rebalance-to-rebalance equity (equity_before[t+1]/equity[t]), 365 d/yr
rets = []
for a, b in zip(rows, rows[1:]):
    rets.append(b["equity_before"]/a["equity"]-1)
sd = st.stdev(rets)
P("rebalance-to-rebalance returns n=%d mean %.4f%% sd %.4f%% -> annualised vol %.1f%%/yr (x sqrt 365); using eq/eq %.1f%%" % (
    len(rets), 100*st.mean(rets), 100*sd, 100*sd*math.sqrt(365), 100*st.stdev([b["equity"]/a["equity"]-1 for a,b in zip(rows,rows[1:])])*math.sqrt(365)))
# max drawdown on rebalance marks
peak, mdd = 0, 0
for r in rows:
    peak = max(peak, r["equity"]); mdd = min(mdd, r["equity"]/peak-1)
P("max drawdown on rebalance marks %.2f%% (peak %.2f)" % (100*mdd, peak))
# buy and hold of the 9 coins, first-row mids to last-row mids
m0, m1 = rows[0]["mids"], rows[-1]["mids"]
bh = [(m1[c]/m0[c]-1) for c in m0]
P("buy-and-hold 9 coins equal weight, %s -> %s mids: %.2f%%  (BTC %.2f%%)" % (rows[0]["time"][:10], rows[-1]["time"][:10], 100*st.mean(bh), 100*(m1["BTC"]/m0["BTC"]-1)))
P("per coin: " + ", ".join("%s %+.1f%%" % (c, 100*(m1[c]/m0[c]-1)) for c in m0))
# percentile of the realised 19-day return under Sharpe 0.5, 12% vol (normal), and under the realised 10.1% vol
days = (19)  # 8 Oct 16:37 -> 26 Oct 00:05 is 17.3 days; the lead used 19 rebalances
from math import erf, sqrt
def Phi(z): return 0.5*(1+erf(z/sqrt(2)))
import datetime as dt
t0 = dt.datetime.fromisoformat(rows[0]["time"]); t1 = dt.datetime.fromisoformat(rows[-1]["time"])
elapsed = (t1-t0).total_seconds()/86400
for lab, dd in (("19 days", 19.0), ("elapsed %.1f days" % elapsed, elapsed)):
    for vol in (0.12, sd*math.sqrt(365)):
        mu = 0.5*vol*dd/365; s = vol*math.sqrt(dd/365)
        z = ((eqN/eq0-1)-mu)/s
        P("realised %.2f%% over %s at Sharpe 0.5, vol %.1f%%: expected %.2f%% sd %.2f%% z %.2f -> percentile %.0f" % (100*(eqN/eq0-1), lab, 100*vol, 100*mu, 100*s, z, 100*Phi(z)))
P("")
P("WEEKLY BOOK (TV 0.25, band 10%%), journal %s" % f"{R}/weekly_journal.jsonl")
P("rebalances %d: " % len(wk) + "; ".join("%s eq %.2f model %.2f gross %.3fx orders %d fees %.3f funding %.3f" % (w["time"][:10], w["equity"], w["model_equity"], w["gross"], len(w["orders"]), w["fees"], w["funding"]) for w in wk))
wn = sum(abs(o["notional"]) for w in wk for o in w["orders"]); wf = sum(o["fee"] for w in wk for o in w["orders"])
ws = sum(abs(o["notional"])*o["slippage_bps"] for w in wk for o in w["orders"])/wn
P("weekly orders %d traded $%.2f fee %.2f bps slippage %.2f bps total %.2f bps" % (sum(len(w["orders"]) for w in wk), wn, 1e4*wf/wn, ws, 1e4*wf/wn+ws))
P("")
P("SHARPE STANDARD ERROR / TIME TO KNOW (SE ~ 1/sqrt(T years); Lo 2002 adds (1+S^2/2) factor)")
for T, lab in ((0.25, "month 3"), (0.5, "month 6"), (1.0, "month 12"), (2.0, "year 2"), (5.0, "year 5")):
    P("  %-8s T=%.2f yr  SE %.2f (plain)  %.2f (S=0.5 Lo)" % (lab, T, 1/math.sqrt(T), math.sqrt((1+0.125)/T)))
for S in (0.3, 0.5, 0.8):
    T50 = (1.645/S)**2; T80 = ((1.645+0.8416)/S)**2
    P("  true Sharpe %.1f: years to reject 0 at 95%% one-sided with 50%% power %.1f, with 80%% power %.1f" % (S, T50, T80))
P("")
P("ADA MM COMPARATOR (DATA.txt section A, venue ledger): +33.29 over 20 Oct 11:06Z -> 26 Oct 17:30Z")
d = (dt.datetime(2026,10,26,17,30)-dt.datetime(2026,10,20,11,6)).total_seconds()/86400
P("  elapsed %.2f days -> $%.2f/day -> $%.0f/month (30.4 d) -> $%.0f/yr if the rate holds; capital 292.16 -> 325.45" % (d, 33.29/d, 33.29/d*30.4, 33.29/d*365))
P("  bot turnover ~$15-17k/day = 2.5-3% of ADAUSD 24h turnover $595,184 (DATA.txt): already at the stated capacity; net60 +3.44 bps per $ (markout_since20.txt)")
P("  if the Scalper Offer (maker 1.25 bps) is revoked and the fee returns to 2.12 bps: net60 ~ %.2f bps per $ -> ~$%.0f/month" % (3.44-(2.12-1.25), 33.29/d*30.4*(3.44-0.87)/3.44))
open(sys.argv[1] if len(sys.argv)>1 else "/dev/stdout", "w").write("\n".join(out)+"\n")
print("\n".join(out))
