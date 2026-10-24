#!/usr/bin/env python3
"""PAIR-1 in-sample run on the nine (spec.md). Writes results.json next to this file and prints the scorecard.
Usage: python3 -I run.py
"""
import datetime as dt
import json
import math
import sys
import time
from collections import Counter

HERE = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1"
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import engine as E  # noqa: E402

START, END = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
H1_END = dt.date(2023, 6, 30)          # screen halves (by entry decision date)
F_H1_END = dt.date(2023, 12, 31)       # frozen-file halves (daily Sharpe)
FIRST_MON = START - dt.timedelta(days=START.weekday())
N_WEEKS = (END - FIRST_MON).days // 7 + 1


def scorecard(sim, label):
    tt = E.trade_table(sim)
    net = np.array([r["net_bps"] for r in tt])
    out = dict(label=label, n_trades=len(tt))
    yrs = ((END - START).days + 1) / 365.25
    out["trades_per_year"] = len(tt) / yrs
    r = sim.rets
    dates = np.array(sim.dates)
    out["sharpe"] = E.sharpe(r)
    out["cagr"] = E.cagr(r)
    out["maxdd"] = E.maxdd(r)
    out["sharpe_2020-05..2023-06"] = E.sharpe(r[dates <= H1_END])
    out["sharpe_2023-07..2026-09"] = E.sharpe(r[dates > H1_END])
    out["sharpe_2020-05..2023-12"] = E.sharpe(r[dates <= F_H1_END])
    out["sharpe_2024-01..2026-09"] = E.sharpe(r[dates > F_H1_END])
    out["share_days_in_position"] = float(np.mean(sim.npos > 0))
    out["mean_gross_exposure"] = float(np.mean(sim.gross))
    out["final_equity"] = sim.final_eq
    wkd = E.week_index(sim.dates, FIRST_MON)
    out["F5_P_sharpe_le0"] = E.boot_daily_sharpe(r, wkd, N_WEEKS)
    if len(tt):
        wk = E.week_index([x["d_entry"] for x in tt], FIRST_MON)
        p, lo, hi, nan = E.boot_trade_mean(net, wk, N_WEEKS)
        out.update(mean_net_bps=float(net.mean()), median_net_bps=float(np.median(net)), boot_P_mean_le0=p, boot_ci95=[lo, hi],
                   boot_nan_draws=nan, hit_rate=float(np.mean(net > 0)),
                   mean_gross_bps=float(np.mean([x["gross_bps"] for x in tt])),
                   median_gross_bps=float(np.median([x["gross_bps"] for x in tt])),
                   mean_fund_bps=float(np.mean([x["fund_bps"] for x in tt])),
                   mean_cost_bps=float(np.mean([x["cost_bps"] for x in tt])),
                   mean_days_held=float(np.mean([x["held"] for x in tt])),
                   exit_reasons=dict(Counter(x["reason"] for x in tt)),
                   worst_trade_net_bps=float(net.min()), worst_trade_pct_equity=float(min(x["net_eq"] for x in tt)),
                   best_trade_pct_equity=float(max(x["net_eq"] for x in tt)),
                   mean_N_over_equity=float(np.mean([x["N_eq"] for x in tt])),
                   fallback_fills=int(sum(x["fallback"] for x in tt)))
        h1 = np.array([x["d_entry"] <= H1_END for x in tt])
        out["H1_n"], out["H2_n"] = int(h1.sum()), int((~h1).sum())
        out["H1_mean_net_bps"] = float(net[h1].mean()) if h1.any() else None
        out["H2_mean_net_bps"] = float(net[~h1].mean()) if (~h1).any() else None
        per = {}
        for c in E.NINE:
            m = np.array([c in x["pair"] for x in tt])
            per[c] = dict(n=int(m.sum()), mean_net_bps=float(net[m].mean()) if m.any() else None)
        out["per_coin"] = per
        out["coins_positive"] = int(sum(1 for v in per.values() if v["mean_net_bps"] is not None and v["mean_net_bps"] > 0))
        by_year = {}
        for y in range(2020, 2027):
            m = np.array([x["d_entry"].year == y for x in tt])
            ry = r[np.array([d.year == y for d in sim.dates])]
            by_year[y] = dict(n=int(m.sum()), mean_net_bps=float(net[m].mean()) if m.any() else None,
                              ret_sum_pct=float(100 * ry.sum()), sharpe=E.sharpe(ry))
        out["by_year"] = by_year
        pairs = Counter(f"{x['pair'][0]}-{x['pair'][1]}" for x in tt)
        out["top_pairs"] = pairs.most_common(8)
        by_reason = {}
        for k in out["exit_reasons"]:
            m = np.array([x["reason"] == k for x in tt])
            by_reason[k] = dict(n=int(m.sum()), mean_net_bps=float(net[m].mean()),
                                mean_gross_bps=float(np.mean([x["gross_bps"] for x in tt if x["reason"] == k])))
        out["by_reason"] = by_reason
    else:
        out.update(mean_net_bps=None, boot_P_mean_le0=None, coins_positive=0, H1_mean_net_bps=None, H2_mean_net_bps=None)
    return out, tt


def trend_weekly_book():
    sys.path.insert(0, f"{E.SP}/tools2")
    import data as tdata, rules, sim as tsim
    P = tdata.load_binance()
    p = P.sub(tdata.NINE)
    Wk = rules.baseline_weights(p.C, tv=0.25, max_gross=1.0)
    rk = tsim.simulate(p, Wk, decide=rules.decide_weekly(p.dates, 6), band=0.10, start=dt.date(2020, 5, 1), end=dt.date(2026, 9, 30))
    ref = tsim.sharpe(rk["rets"])
    # candle date c covers 00:00 c+1 -> 00:00 c+2 ... the return dated nxt=c closes at 00:00 c+1; align to D = c+1
    ser = {d + dt.timedelta(days=1): x for d, x in zip(rk["dates"], rk["rets"])}
    return ser, ref


def verdict(o):
    t1 = o["mean_net_bps"] is not None and o["mean_net_bps"] > 0 and o["boot_P_mean_le0"] <= 0.01
    t2 = (o.get("H1_mean_net_bps") or -1) > 0 and (o.get("H2_mean_net_bps") or -1) > 0
    t3 = o["coins_positive"] >= 6
    return dict(test1=bool(t1), test2=bool(t2), test3=bool(t3), PASS=bool(t1 and t2 and t3))


def main():
    t0 = time.time()
    mk = E.load_market(E.NINE)
    pairs = [(i, j) for i in range(9) for j in range(i + 1, 9)]
    cache = {}
    res = {}
    base = E.Sim(mk, pairs, E.Params(), START, END, cache).run()
    res["base"], tt = scorecard(base, "base 7.31 bps")
    res["base"]["screen_verdict"] = verdict(res["base"])
    stress = E.Sim(mk, pairs, E.Params(cost_bps=15.31), START, END, cache).run()
    res["stress"], _ = scorecard(stress, "stress 15.31 bps")
    ser, ref = trend_weekly_book()
    common = [d for d in base.dates if d in ser]
    a = np.array([base.rets[base.dates.index(d)] for d in common]); b = np.array([ser[d] for d in common])
    res["F7"] = dict(corr=float(np.corrcoef(a, b)[0, 1]), n_days=len(common), trend_weekly_sharpe=ref)
    # formation diagnostics
    n_sel = [len(S) for _, S in base.formations_used]
    res["formation"] = dict(mondays=len(n_sel), mondays_with_selection=int(sum(1 for x in n_sel if x)), mean_selected=float(np.mean(n_sel)))
    neigh = {}
    for lab, prm in [("window 120", E.Params(window=120)), ("window 365", E.Params(window=365)),
                     ("entry 1.5", E.Params(entry=1.5)), ("entry 2.5", E.Params(entry=2.5)),
                     ("K 2", E.Params(K=2)), ("K 6", E.Params(K=6))]:
        s = E.Sim(mk, pairs, prm, START, END, cache).run()
        o, _ = scorecard(s, lab)
        neigh[lab] = {k: o.get(k) for k in ("n_trades", "trades_per_year", "sharpe", "mean_net_bps", "boot_P_mean_le0",
                                            "H1_mean_net_bps", "H2_mean_net_bps", "coins_positive", "maxdd")}
        neigh[lab]["screen_verdict"] = verdict(o)
    res["neighbours_never_selected"] = neigh
    b_ = res["base"]
    res["frozen_criteria"] = {
        "F1 sharpe>=0.50": b_["sharpe"] >= 0.50,
        "F2 sharpe>0 both halves": b_["sharpe_2020-05..2023-12"] > 0 and b_["sharpe_2024-01..2026-09"] > 0,
        "F3 24-panel": "not run (gated on the screen's pass)",
        "F4 mean net>=29.24": (b_["mean_net_bps"] or -1e9) >= 29.24,
        "F5 P(sharpe<=0)<=0.10": b_["F5_P_sharpe_le0"] <= 0.10,
        "F6 stress sharpe>0": res["stress"]["sharpe"] > 0,
        "F7 |corr|<=0.30": abs(res["F7"]["corr"]) <= 0.30,
    }
    res["runtime_s"] = time.time() - t0
    json.dump(res, open(f"{HERE}/results.json", "w"), indent=1, default=str)
    with open(f"{HERE}/trades_base.csv", "w") as f:
        keys = ["pair", "side", "d_entry", "d_exit", "reason", "held", "z", "b", "h", "p", "gross_bps", "fund_bps", "cost_bps", "net_bps", "net_eq", "fallback"]
        f.write(",".join(keys) + "\n")
        for r in tt:
            f.write(",".join(("-".join(r[k]) if k == "pair" else (f"{r[k]:.6g}" if isinstance(r[k], float) else str(r[k]))) for k in keys) + "\n")
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
