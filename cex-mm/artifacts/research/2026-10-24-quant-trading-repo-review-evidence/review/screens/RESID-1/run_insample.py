#!/usr/bin/env python3
"""RESID-1 in-sample screen on the nine, 2020-05..2026-09 (spec.md). Prints the screen's pass rule and the frozen-file criteria."""
import csv, datetime as dt, math, sys
HERE = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/RESID-1"
sys.path.insert(0, HERE)
import numpy as np
import resid1_lib as L
from checks import load_nine, NINE

S, E = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
HALVES = [(dt.date(2020, 5, 1), dt.date(2023, 6, 30)), (dt.date(2023, 7, 1), dt.date(2026, 9, 30))]
ALTS = NINE[1:]


def trend_book(coins_list):
    sys.path.insert(0, f"{L.SP}/tools2")
    import data, rules, sim
    P = data.load_binance().sub(coins_list)
    Wk = rules.baseline_weights(P.C, tv=0.25, max_gross=1.0)
    r = sim.simulate(P, Wk, decide=rules.decide_weekly(P.dates, 6), band=0.10, start=S, end=E)
    return {c + dt.timedelta(days=1): x for c, x in zip(r["dates"], r["rets"])}


def corr_with(res, tb):
    a = [(x, tb[d]) for d, x in zip(res["dates"], res["rets"]) if d in tb]
    u = np.array(a)
    return float(np.corrcoef(u[:, 0], u[:, 1])[0, 1]), len(a)


def screen_pass(s, n_alts_needed):
    t1 = s["mean_net_bps"] > 0 and s["boot_P"] <= 0.01
    t2 = all(m > 0 for _, _, n, m in s["halves"] if True) and all(n > 0 for _, _, n, _ in s["halves"])
    t3 = s["alts_pos"] >= n_alts_needed
    return t1, t2, t3


def main():
    coins = load_nine()
    alts = [coins[c] for c in ALTS]
    X = coins["BTC"]
    base = L.simulate(alts, X, S, E, L.Params(), n_alts=8)
    sb = L.summarize(base, S, E, HALVES, ALTS, "BASE nine (8 alts vs BTC), 7.31 bps/leg fill, fill at 01:00 UTC")
    print(L.fmt(sb))
    t1, t2, t3 = screen_pass(sb, 6)
    print(f"\nSCREEN PASS RULE: (1) mean > 0 & P <= 0.01: {t1}  (2) both halves > 0: {t2}  (3) >= 6 of 8 alts > 0: {t3}"
          f"  -> {'PASS' if (t1 and t2 and t3) else 'FAIL'}")
    # funding-month coverage over held periods
    miss = set()
    for t in base["trades"]:
        for leg in t["legs"]:
            d = t["entry_date"]
            while d <= t["exit_date"]:
                m = f"{d.year:04d}-{d.month:02d}"
                if m not in leg.coin.fund_months:
                    miss.add((leg.coin.name, m))
                d += dt.timedelta(days=1)
    print(f"funding coin-months missing over held periods: {len(miss)} {sorted(miss)[:10]}")

    # ---- frozen-file criteria (descriptive on the nine)
    stress = L.simulate(alts, X, S, E, L.Params(cost_bps=15.31), n_alts=8)
    ss = L.summarize(stress, S, E, HALVES, ALTS, "STRESS 15.31 bps/leg fill (10 bps slippage)")
    print("\n" + L.fmt(ss))
    sh_a = L.sharpe(L.sub_r(base, dt.date(2020, 5, 1), dt.date(2023, 12, 31)))
    sh_b = L.sharpe(L.sub_r(base, dt.date(2024, 1, 1), dt.date(2026, 9, 30)))
    pboot = L.week_bootstrap_sharpe(base["dates"], base["rets"])
    tb = trend_book(NINE)
    rho, nco = corr_with(base, tb)
    print("\nFROZEN-FILE CRITERIA on the nine (descriptive; the frozen file scores them on the 16 unseen perps):")
    print(f"  F1 Sharpe {sb['sharpe']:.3f} >= 0.50: {sb['sharpe'] >= 0.5}")
    print(f"  F2 Sharpe 2020-05..2023-12 {sh_a:.3f}, 2024-01..2026-09 {sh_b:.3f} both > 0: {sh_a > 0 and sh_b > 0}")
    print(f"  F3 mean net {sb['mean_net_bps']:+.1f} >= +29.24 bps: {sb['mean_net_bps'] >= 29.24}")
    print(f"  F4 week-cluster bootstrap of daily returns P(Sharpe <= 0) = {pboot:.4f} <= 0.10: {pboot <= 0.10}")
    print(f"  F5 Sharpe at 10 bps slippage {ss['sharpe']:.3f} > 0: {ss['sharpe'] > 0}")
    print(f"  F6 corr with weekly TV 0.25 trend book on the nine = {rho:+.3f} over {nco} days, |corr| <= 0.30: {abs(rho) <= 0.30}")

    # ---- labelled neighbours (never selected)
    print("\nLABELLED NEIGHBOURS (nine, base costs; never selected):")
    neigh = [("fill at the decision close", L.Params(fill="close")), ("refit daily while flat", L.Params(refit_daily=True)),
             ("R^2 > 0.6", L.Params(r2=0.6)), ("R^2 > 0.8", L.Params(r2=0.8)), ("band 1.5 sigma", L.Params(k=1.5)),
             ("band 2.5 sigma", L.Params(k=2.5)), ("hold 6 d (counter > 5)", L.Params(hold=5)), ("hold 18 d (counter > 16)", L.Params(hold=16)),
             ("unhedged single leg", L.Params(hedged=False))]
    for lab, prm in neigh:
        r = L.simulate(alts, X, S, E, prm, n_alts=8)
        s = L.summarize(r, S, E, HALVES, ALTS, lab)
        a, b, c = screen_pass(s, 6)
        print(f"  {lab:28s} trades {s['n_trades']:4d} mean net {s['mean_net_bps']:+7.1f} bps P {s['boot_P']:.4f} halves "
              f"{s['halves'][0][3]:+7.1f}/{s['halves'][1][3]:+7.1f} alts>0 {s['alts_pos']}/8 Sharpe {s['sharpe']:+.3f} CAGR {s['cagr']:+.1%} "
              f"maxDD {s['maxdd']:.1%} -> screen {'PASS' if (a and b and c) else 'FAIL'}")

    # ---- write trades and daily series
    with open(f"{HERE}/insample_trades.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alt", "side", "entry_date", "exit_date", "exit_how", "b", "r2", "sigma", "N", "gross_bps", "cost_bps", "fund_bps", "net_bps"])
        for t in base["trades"]:
            w.writerow([t["alt"], t["side"], t["entry_date"], t["exit_date"], t["exit_how"], f"{t['b']:.4f}", f"{t['r2']:.4f}", f"{t['sigma']:.5f}",
                        f"{t['N']:.6f}", f"{t['gross_bps']:.2f}", f"{t['cost_bps']:.2f}", f"{t['fund_bps']:.2f}", f"{t['net_bps']:.2f}"])
    with open(f"{HERE}/insample_daily.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "ret", "equity"])
        for d, r, e in zip(base["dates"], base["rets"], base["equity"]):
            w.writerow([d, f"{r:.8f}", f"{e:.6f}"])
    return (t1 and t2 and t3)


if __name__ == "__main__":
    ok = main()
    print(f"\nIN-SAMPLE VERDICT: {'PASS' if ok else 'FAIL'}")
