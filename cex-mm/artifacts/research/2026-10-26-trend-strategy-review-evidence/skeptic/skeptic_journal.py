"""Independent recomputation of the trend paper-book numbers from the 26 Oct journal copies.
Reads only the jsonl journals. No repo code imported."""
import json, math, statistics as st, datetime as dt, sys
R = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/reports/run-2026-10-26-pm/"
def load(p): return [json.loads(l) for l in open(R+p) if l.strip()]
CV = {"BTC":0.001,"ETH":0.01,"XRP":1,"BNB":0.1,"ADA":1,"LTC":0.1,"LINK":1,"DOGE":100,"BCH":0.01}  # Delta contract values (resource/07)
out = {}
for name in ("daily","weekly"):
    J = load(f"{name}_journal.jsonl")
    n = len(J)
    eq = [r["equity"] for r in J]
    times = [dt.datetime.fromisoformat(r["time"]) for r in J]
    orders = [o for r in J for o in r["orders"]]
    notional = sum(o["notional"] for o in orders)
    fees = sum(o["fee"] for o in orders)
    slip_usd = sum(abs(o["price"]-o["mid"])*abs(o["contracts"])*CV[o["coin"]] for o in orders)
    # slippage sign check: slippage_bps positive = paid
    slip_bps_w = sum(o["slippage_bps"]*o["notional"] for o in orders)/notional
    fund = [r["funding"] for r in J]
    # identity checks
    id_eq = max(abs(r["equity"] - (r["cash"] + sum(q*CV[c]*r["mids"][c] for c,q in r["positions"].items()))) for r in J)
    # equity_before[k] == equity[k-1] + positions_{k-1} x (mid_k - mid_{k-1}) - funding_k
    id_before = 0.0
    for a,b in zip(J, J[1:]):
        pred = a["equity"] + sum(q*CV[c]*(b["mids"][c]-a["mids"][c]) for c,q in a["positions"].items()) - b["funding"]
        id_before = max(id_before, abs(pred - b["equity_before"]))
    # equity[k] == equity_before[k] - fees - slippage$ (paper fills at walked price, marked at mid)
    id_after = max(abs(r["equity_before"] - sum(o["fee"] for o in r["orders"]) - sum((o["price"]-o["mid"])*o["contracts"]*CV[o["coin"]] for o in r["orders"]) - r["equity"]) for r in J)
    # period returns (rebalance mark to rebalance mark, after costs)
    rets = [b["equity"]/a["equity"]-1 for a,b in zip(J,J[1:])]
    days = [(tb-ta).total_seconds()/86400 for ta,tb in zip(times,times[1:])]
    # vol conventions
    vol_naive = st.stdev(rets)*math.sqrt(365) if len(rets)>1 else float("nan")
    # per-day-normalised: r/sqrt(days) then annualise
    rn = [r/math.sqrt(d) for r,d in zip(rets,days)]
    vol_norm = math.sqrt(sum(x*x for x in rn)/len(rn)*365) if rn else float("nan")
    vol_norm_ex1 = math.sqrt(sum(x*x for x in rn[1:])/len(rn[1:])*365) if len(rn)>1 else float("nan")
    peak, mdd, pk = eq[0], 0.0, eq[0]
    # include start capital 1000 as a mark
    series = [1000.0]+eq
    pk=series[0]
    for e in series:
        pk=max(pk,e); mdd=min(mdd,e/pk-1)
    # buy and hold equal weight on mids from first to last row
    m0, m1 = J[0]["mids"], J[-1]["mids"]
    bh = {c: m1[c]/m0[c]-1 for c in m0}
    bh_mean = sum(bh.values())/len(bh)
    # per coin price pnl
    pnl = {c:0.0 for c in CV}
    for a,b in zip(J,J[1:]):
        for c,q in a["positions"].items(): pnl[c]+= q*CV[c]*(b["mids"][c]-a["mids"][c])
    gross = [r["gross"] for r in J]
    model = [r["model_equity"] for r in J]
    pm = [(e/m-1)*1e4 for e,m in zip(eq,model)]
    span_days = (times[-1]-times[0]).total_seconds()/86400
    out[name] = dict(n=n, start=J[0]["time"], end=J[-1]["time"], span_days=round(span_days,2),
        equity_last=eq[-1], ret_pct=round((eq[-1]/1000-1)*100,3), model_last=model[-1], model_ret_pct=round((model[-1]/1000-1)*100,3),
        paper_minus_model_bp_range=(round(min(pm),1), round(max(pm),1)), paper_minus_model_bp_last=round(pm[-1],1),
        n_orders=len(orders), notional=round(notional,2), fees=round(fees,4), fee_bps=round(fees/notional*1e4,3),
        slip_usd=round(slip_usd,4), slip_bps_notional_weighted=round(slip_bps_w,3), slip_bps_usd_over_notional=round(slip_usd/notional*1e4,3),
        cost_bps=round((fees+slip_usd)/notional*1e4,3), median_order_slip_bps=round(st.median(o["slippage_bps"] for o in orders),3),
        max_order_slip_bps=round(max(o["slippage_bps"] for o in orders),3),
        funding_sum=round(sum(fund),4), funding_sign_note="journal field = fund_paid; cash -= fund_paid; positive = PAID by the book",
        funding_intervals=len(fund)-1, funding_pos_intervals=sum(1 for f in fund if f>0), funding_neg_intervals=sum(1 for f in fund if f<0),
        id_eq=id_eq, id_before=id_before, id_after=id_after,
        vol_naive_pct=round(vol_naive*100,2), vol_daynorm_pct=round(vol_norm*100,2), vol_daynorm_ex_first_pct=round(vol_norm_ex1*100,2),
        mdd_pct=round(mdd*100,3), peak=round(max(series),2),
        bh_mean_pct=round(bh_mean*100,3), bh_btc_pct=round(bh["BTC"]*100,3), bh=({c:round(v*100,2) for c,v in bh.items()}),
        price_pnl={c:round(v,2) for c,v in pnl.items()}, price_pnl_sum=round(sum(pnl.values()),2),
        gross_min=round(min(gross),3), gross_max=round(max(gross),3), gross_last=round(gross[-1],3),
        period_rets_pct=[round(r*100,3) for r in rets], period_days=[round(d,3) for d in days],
        positions_last=J[-1]["positions"], cash_last=round(J[-1]["cash"],2),
        rebalance_utc_times=[t.strftime("%m-%d %H:%M:%S") for t in times])
    # per-coin slippage medians
    bycoin = {}
    for o in orders: bycoin.setdefault(o["coin"],[]).append(o["slippage_bps"])
    out[name]["slip_median_by_coin"] = {c:(round(st.median(v),2),len(v)) for c,v in bycoin.items()}
    out[name]["notional_by_coin"] = {c: round(sum(o["notional"] for o in orders if o["coin"]==c),2) for c in CV}
    # weights: how many coin-days flat / third / full (signal inferred from weights relative to...). Just count zero weights
    W = [r["weights"] for r in J]
    out[name]["zero_weight_coin_days"] = sum(1 for w in W for v in w.values() if v==0)
    out[name]["coin_days"] = sum(len(w) for w in W)
json.dump(out, open(sys.argv[1],"w"), indent=1, default=str)
for k,v in out.items():
    print("==",k)
    for kk,vv in v.items():
        if kk in ("period_rets_pct","period_days","rebalance_utc_times","bh","price_pnl"): continue
        print(f"  {kk}: {vv}")
    print("  period_rets_pct:", v["period_rets_pct"])
    print("  period_days:", v["period_days"])
    print("  price_pnl:", v["price_pnl"])
    print("  bh:", v["bh"])
