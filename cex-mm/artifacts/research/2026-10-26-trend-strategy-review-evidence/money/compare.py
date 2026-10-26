#!/usr/bin/env python3
"""Comparison lines, the 'real money' capital table and the time-to-know notes, from mc_summary.json plus the memos' numbers."""
import json, os, math
OUT = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(OUT, "mc_summary.json")))
L = []; P = L.append
# ---------------- (3) comparison lines
P("(3) COMPARISON LINES, expected $ per month, with the source of each number")
P("-" * 118)
P(f"{'line':52s} {'$1k':>9s} {'$5k':>9s} {'$25k':>9s} {'$100k':>9s}   basis")
def row(name, ann_frac, basis, caps=(1000, 5000, 25000, 100000)):
    P(f"{name:52s} " + " ".join(f"{ann_frac*c/12:>+9,.0f}" for c in caps) + f"   {basis}")
for k, lab in (("weekly S0.3", "Trend weekly TV0.25, Sharpe 0.3, pre-tax"), ("weekly S0.5", "Trend weekly TV0.25, Sharpe 0.5, pre-tax"), ("weekly S0.8", "Trend weekly TV0.25, Sharpe 0.8, pre-tax")):
    row(lab, S[k]["after_tax_ann_gain"]["none"], "MC, 5y mean gain / 5 (resource/07 forward range)")
for k, lab in (("weekly S0.5", "  same, after slab 30% on net (carry-forward)"), ):
    row(lab, S[k]["after_tax_ann_gain"]["slab_cf"], "MC + resource/08 slab reading")
row("  same, after VDA 30% per coin-segment", S["weekly S0.5"]["after_tax_ann_gain"]["segment"], "MC + T6b per-segment fit")
row("  same, after VDA 30% per coin-day", S["weekly S0.5"]["after_tax_ann_gain"]["coinday"], "MC + T6b per-coin-day fit")
for k, lab in (("daily S0.3", "Trend daily TV0.40 (19% vol), Sharpe 0.3, pre-tax"), ("daily S0.5", "Trend daily TV0.40 (19% vol), Sharpe 0.5, pre-tax"), ("daily S0.8", "Trend daily TV0.40 (19% vol), Sharpe 0.8, pre-tax")):
    row(lab, S[k]["after_tax_ann_gain"]["none"], "MC; -20%% pause fires within 3y on %d%% of paths" % round(100*S[k]["p_pause_monday"]["0.20"]["3"]))
row("Indian FD 6.5% [UNVERIFIED]", 0.065, "resource/07 expected-performance table [UNVERIFIED rate]")
row("Indian FD 7.0% [UNVERIFIED]", 0.07, "resource/07 [UNVERIFIED]")
row("Indian FD after slab tax ~4.7% [UNVERIFIED]", 0.047, "resource/07 tax section [UNVERIFIED]")
row("Hold BTC, Sharpe 0.5 at 57% vol (MC arithmetic mean)", 0.285, "resource/07 table: BTC 2022-26 Sharpe 0.50, vol 57%; MC median CAGR 12.2%, 5y max DD p50 -70%")
P(f"{'Hold BTC, memo history 2020-05..2026-09':52s} {'':>9s} {'':>9s} {'':>9s} {'':>9s}   CAGR +42.4%, max DD -76.7%, 2022 -64%, 2025 -6%, 2026 -6% (resource/07 comparison table)")
P("")
P("ADA market maker (live, DATA.txt section A): +$33.29 in 6.27 days on $292 = $5.31/day = ~$161/month = ~$1,940/yr at the CURRENT size,")
P("  which already trades $15-17k/day = 2.5-3% of ADAUSD's $595k/day venue turnover: that IS the stated capacity, so the rate does not scale with capital.")
P("  net60 +3.44 bps per $ traded (markout_since20.txt, 5,148 fills) rests on the Scalper Offer maker fee of 1.25 bps; at the 2.12 bps tier it is ~2.57 bps -> ~$120/month.")
P("  Six days of data; the venue is the source of truth (+33.29 cash-flow, equity 292.16 -> 325.45). 'Real money' from MM needs ~3-4 more ADA-sized markets passing the gate, not more capital on ADA.")
P("")
P("Breakout prop route (resource/07, all firm facts [UNVERIFIED]/[THIRD-PARTY]):")
for acct, fee, ev_lo, ev_hi in (("$100k", 999, 1250, 2480), ("$25k", 275, 300, 750)):
    cyc_lo, cyc_hi = ev_lo * 12 / 17, ev_hi * 12 / 17
    P(f"  {acct} account, fee ${fee}: EV {ev_lo:+,}..{ev_hi:+,} per attempt at forward Sharpe 0.5-0.9 after a 15% non-payment haircut; pass 42-52%; median pass 120-140 d; cycle ~17 months")
    note = " (memo quotes $1.3-1.8k/yr for $100k)" if acct == "$100k" else ""
    P(f"    -> ${cyc_lo:,.0f}-{cyc_hi:,.0f} per year of daily operation per account{note}; = ${cyc_lo/12:,.0f}-{cyc_hi/12:,.0f} per month")
    P(f"    -> concurrent accounts for $500/month: {6000/cyc_hi:.1f} to {6000/cyc_lo:.1f}; the owner's rules allow one account at a time and never more than one unrefunded ${fee} fee per $2,500 of own capital")
    P(f"       (so {math.ceil(6000/cyc_hi)}-{math.ceil(6000/cyc_lo)} concurrent fees need >= ${2500*math.ceil(6000/cyc_hi):,}-{2500*math.ceil(6000/cyc_lo):,} of own liquid capital AND a rule change)." + (" $0.2-0.8k of each $100k EV is option value any zero-edge trader collects." if acct == "$100k" else ""))
P("  After slab tax the $100k after-tax EV is roughly $0.8-1.7k per attempt (resource/07). In a 2025-26 regime the EV is negative (-$0.5k per $100k attempt, pass 17%).")
P("")
P("Live trend books for reference (facts_check.txt): daily $992.94 after 19 rebalances (-0.71%), weekly $997.00 after 2; costs 6.33 bps per $ traded; funding +$0.35 received.")
P("  At $1,000 the daily book's EXPECTED gain at Sharpe 0.5 is about $7/month before tax ($5/month weekly); the 19-day realised -0.71% is the 34-36th percentile of that distribution, i.e. noise.")
P("")
# ---------------- (4) real money table
P("(4) CAPITAL FOR 'REAL MONEY' (>= $500/month = $6,000/yr EXPECTED gain), from the MC's 5-year mean gain / 5")
P("-" * 118)
P(f"{'book / Sharpe':16s} {'pre-tax':>12s} {'slab 30% (cf)':>14s} {'slab no cf':>12s} {'per-segment VDA':>16s} {'per-coin-day VDA':>17s}   P(losing yr)  P(-20% pause <=3y)  5y max DD p50/p90")
for k in ("weekly S0.3", "weekly S0.5", "weekly S0.8", "daily S0.3", "daily S0.5", "daily S0.8"):
    a = S[k]["after_tax_ann_gain"]
    def cap(x): return f"${6000/x:,.0f}" if x > 0 else "never"
    P(f"{k:16s} {cap(a['none']):>12s} {cap(a['slab_cf']):>14s} {cap(a['slab_nocf']):>12s} {cap(a['segment']):>16s} {cap(a['coinday']):>17s}   {S[k]['p_losing_year']:>11.0%}  {S[k]['p_pause_monday']['0.20']['3']:>17.0%}  {S[k]['mdd']['5']['p50']:.0%} / {S[k]['mdd']['5']['p90']:.0%}")
P("Closed form check: capital = 6000 / (Sharpe x vol): weekly 0.3/0.5/0.8 -> $166,667 / $100,000 / $62,500; daily (19%) -> $105,263 / $63,158 / $39,474.")
P("With the 30%-on-venue rule, 'capital' is total strategy capital; e.g. $100k means ~$30k on Delta and ~$70k in an FD (whose ~$4.5k/yr of interest is not strategy edge).")
P("Every number is an EXPECTATION with a p10 that is negative at 1 and 3 years for every cell below Sharpe 0.8 (mc_outcomes.txt): at $100k weekly S0.5 the 1-year p10 is about -$8k and the 3-year p10 about -$5k.")
P("")
# ---------------- (5) time to know
P("(5) TIME TO KNOW")
P("-" * 118)
for T, lab in ((0.25, "month 3"), (0.5, "month 6"), (1.0, "month 12"), (2.0, "year 2"), (5.0, "year 5")):
    P(f"  {lab:9s} Sharpe SE ~ 1/sqrt({T:.2f}) = {1/math.sqrt(T):.2f}; a true 0.5 book shows an observed Sharpe below 0 with probability {0.5*(1+math.erf(-0.5*math.sqrt(T)/math.sqrt(2))):.0%}; a zero-edge book shows > 0.5 with probability {0.5*(1-math.erf(0.5*math.sqrt(T)/math.sqrt(2))):.0%}")
for s_ in (0.3, 0.5, 0.8):
    P(f"  true Sharpe {s_}: years to reject Sharpe 0 at 95% one-sided with 50% power = (1.645/{s_})^2 = {(1.645/s_)**2:.1f}; with 80% power {((1.645+0.8416)/s_)**2:.1f}")
P("  What CAN be concluded by month 3 / 6 / 12: whether the process works (every slot executed, cost per $ inside 2x model, reconciliation exact, funding line as modelled, no kill #2/#3).")
P("  What CANNOT: whether the edge is 0, 0.5 or 0.8 Sharpe. At 12 months the 80% band of the observed Sharpe at true 0.5 is -0.8..+1.8 (mc_outcomes.txt), and a positive year is only 1.3-1.6x more likely under Sharpe 0.5 than under zero edge.")
P("  Watch instead (all measurable now, from the journals): executed on time (19/19 daily, 2/2 weekly so far); cost per $ traded 6.33 bps vs 7.31 model / 14.62 gate; paper-minus-model within +-0.26%;")
P("  funding received +$0.35 (failure signature: funding PAID > 2%/yr of equity); gross within 0.11-0.64x (cap 2x daily, 1x weekly); live: venue position == order list every slot, leverage <= 5x, margin cross, withdrawal <= 7 business days.")
P("  Equity-based kills are useless at this horizon: the -20% pause fires on luck 15% of the time within 2 years at Sharpe 0.5 (MC; memo T6g 18%), and the modelled 30-day cost ($3.88 on $1,000) is a tenth of a month's standard deviation (resource/07 T6d).")
txt = "\n".join(L) + "\n"
open(os.path.join(OUT, "compare_realmoney_timetoknow.txt"), "w").write(txt)
print(txt)
