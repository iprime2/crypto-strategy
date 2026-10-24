#!/usr/bin/env python3
"""RESID-1 gated runs (spec.md 'Gated runs'): run only because the nine passed the screen's in-sample rule.
G0 = the frozen file's 16 unseen ex-ante perps; Holdout A = Binance spot 2017-08..2020-04; Holdout B = 15 perps 2022-01..2026-09."""
import datetime as dt, math, os, sys
HERE = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/RESID-1"
sys.path.insert(0, HERE)
import numpy as np
import resid1_lib as L
from run_insample import corr_with, screen_pass

K5 = f"{L.SP}/universe/klines5m"
SIXTEEN = "ATOM BAT DASH EOS ETC IOST IOTA NEO ONT QTUM TRX VET XLM XMR XTZ ZEC".split()
SPOT_ALTS = "ETH XRP BNB ADA LTC LINK DOGE EOS ETC NEO TRX XLM".split()
OX15 = "1000SHIB SOL SAND LUNA MANA DOT AVAX FTM MATIC GALA AXS DYDX FIL LRC CRV".split()


def first_decision_day(alts, X, start, end, train=50):
    d = start
    while d <= end:
        for Y in alts:
            if all(Y.C(d - dt.timedelta(days=k)) is not None and X.C(d - dt.timedelta(days=k)) is not None for k in range(1, train + 1)) \
                    and Y.C(d) is not None and X.C(d) is not None:
                return d
        d += dt.timedelta(days=1)
    return None


def fund_coverage(res):
    miss = set()
    for t in res["trades"]:
        for leg in t["legs"]:
            d = t["entry_date"]
            while d <= t["exit_date"]:
                m = f"{d.year:04d}-{d.month:02d}"
                if m not in leg.coin.fund_months:
                    miss.add((leg.coin.name, m))
                d += dt.timedelta(days=1)
    return miss


def run_panel(label, alts, X, S, E, halves, need, n_alts, funding=True):
    names = [a.name for a in alts]
    for a in alts + [X]:
        print(f"  {a.name}: bars {len(a.t)} {L.ms_day(a.t[0])}..{L.ms_day(a.t[-1])} funding stamps {len(a.fund_t)}")
    base = L.simulate(alts, X, S, E, L.Params(funding=funding), n_alts=n_alts)
    sb = L.summarize(base, S, E, halves, names, f"{label} BASE 7.31 bps/leg fill")
    print(L.fmt(sb))
    t1, t2, t3 = screen_pass(sb, need)
    ok = t1 and t2 and t3
    print(f"SCREEN PASS RULE [{label}]: (1) mean > 0 & P <= 0.01: {t1}  (2) both halves > 0: {t2}  (3) >= {need} of {len(names)} alts > 0: {t3}"
          f"  -> {'PASS' if ok else 'FAIL'}")
    if funding:
        miss = fund_coverage(base)
        print(f"  funding coin-months missing over held periods: {len(miss)} {sorted(miss)[:12]}")
    st = L.simulate(alts, X, S, E, L.Params(cost_bps=15.31, funding=funding), n_alts=n_alts)
    ss = L.summarize(st, S, E, halves, names, f"{label} STRESS 15.31 bps/leg fill")
    print(f"  stress 10 bps slippage: trades {ss['n_trades']} mean net {ss['mean_net_bps']:+.1f} bps P {ss['boot_P']:.4f} "
          f"Sharpe {ss['sharpe']:+.3f} halves {ss['halves'][0][3]:+.1f}/{ss['halves'][1][3]:+.1f}")
    return base, sb, ss, ok


def main():
    btc = L.load_5m_dir(K5, "binance-", "BTCUSDT", "BTC")
    results = {}

    # ---------------- G0: the 16 unseen ex-ante perps (frozen file's own pass panel)
    print("\n######## G0: 16 ex-ante perps outside the nine, 2020-05..2026-09 (1 h bars; BTC 5 m)")
    S, E = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
    halves = [(dt.date(2020, 5, 1), dt.date(2023, 6, 30)), (dt.date(2023, 7, 1), dt.date(2026, 9, 30))]
    alts = [L.load_5m_dir(f"{L.SP}/universe/hourly_extra", "binance-", f"{c}USDT", c, bar=3_600_000) for c in SIXTEEN]
    base, sb, ss, ok = run_panel("G0 16 perps", alts, btc, S, E, halves, 11, 16)
    sh_a = L.sharpe(L.sub_r(base, dt.date(2020, 5, 1), dt.date(2023, 12, 31)))
    sh_b = L.sharpe(L.sub_r(base, dt.date(2024, 1, 1), dt.date(2026, 9, 30)))
    pboot = L.week_bootstrap_sharpe(base["dates"], base["rets"])
    sys.path.insert(0, f"{L.SP}/tools2")
    import data, rules, sim
    P = data.load_binance().sub(SIXTEEN)
    Wk = rules.baseline_weights(P.C, tv=0.25, max_gross=1.0)
    r = sim.simulate(P, Wk, decide=rules.decide_weekly(P.dates, 6), band=0.10, start=S, end=E)
    tb = {c + dt.timedelta(days=1): x for c, x in zip(r["dates"], r["rets"])}
    rho, nco = corr_with(base, tb)
    f = [sb["sharpe"] >= 0.5, sh_a > 0 and sh_b > 0, sb["mean_net_bps"] >= 29.24, pboot <= 0.10, ss["sharpe"] > 0, abs(rho) <= 0.30]
    print("FROZEN-FILE PASS (all six required, on the 16):")
    print(f"  F1 Sharpe {sb['sharpe']:.3f} >= 0.50: {f[0]}")
    print(f"  F2 Sharpe 2020-05..2023-12 {sh_a:.3f}, 2024-01..2026-09 {sh_b:.3f}, both > 0: {f[1]}")
    print(f"  F3 mean net {sb['mean_net_bps']:+.1f} >= +29.24 bps: {f[2]}")
    print(f"  F4 P(Sharpe <= 0) week-cluster bootstrap of daily returns = {pboot:.4f} <= 0.10: {f[3]}")
    print(f"  F5 Sharpe at 10 bps slippage {ss['sharpe']:.3f} > 0: {f[4]}")
    print(f"  F6 corr with the weekly TV 0.25 trend book on the same 16 = {rho:+.3f} ({nco} days), |corr| <= 0.30: {f[5]}")
    print(f"  -> frozen-file verdict on the 16: {'PASS' if all(f) else 'FAIL'}")
    results["G0"] = (ok, all(f))

    # ---------------- Holdout A: Binance spot 2017-08..2020-04
    print("\n######## HOLDOUT A: Binance spot 5 m, 2017-08..2020-04, BTC + 12 alts, no funding")
    sp = f"{L.SP}/universe/spot5m"
    X = L.load_5m_dir(sp, "binance-spot-", "BTCUSDT", "BTC", with_funding=False)
    alts = [L.load_5m_dir(sp, "binance-spot-", f"{c}USDT", c, with_funding=False) for c in SPOT_ALTS]
    S, E = dt.date(2017, 8, 1), dt.date(2020, 4, 30)
    d0 = first_decision_day(alts, X, S, E)
    mid = d0 + dt.timedelta(days=((E - d0).days) // 2)
    halves = [(S, mid), (mid + dt.timedelta(days=1), E)]
    print(f"  first possible decision day {d0}; halves {halves[0][0]}..{halves[0][1]} | {halves[1][0]}..{halves[1][1]}")
    base, sb, ss, ok = run_panel("HOLDOUT A spot", alts, X, S, E, halves, 8, 12, funding=False)
    results["A"] = ok

    # ---------------- Holdout B: 15 perps 2022-01..2026-09
    print("\n######## HOLDOUT B: Binance perps 5 m, 15 coins chosen by 2021-Q4 volume, 2022-01..2026-09, funding from caches")
    ox = f"{L.SP}/universe/ox5m"
    alts = [L.load_5m_dir(ox, "binance-", f"{c}USDT", c) for c in OX15]
    S, E = dt.date(2022, 1, 1), dt.date(2026, 9, 30)
    d0 = first_decision_day(alts, btc, S, E)
    mid = d0 + dt.timedelta(days=((E - d0).days) // 2)
    halves = [(S, mid), (mid + dt.timedelta(days=1), E)]
    print(f"  first possible decision day {d0}; halves {halves[0][0]}..{halves[0][1]} | {halves[1][0]}..{halves[1][1]}")
    base, sb, ss, ok = run_panel("HOLDOUT B 15 perps", alts, btc, S, E, halves, 10, 15)
    results["B"] = ok
    print(f"\nGATED RESULTS: G0 screen rule {'PASS' if results['G0'][0] else 'FAIL'}, G0 frozen-file rule {'PASS' if results['G0'][1] else 'FAIL'}; "
          f"holdout A {'PASS' if results['A'] else 'FAIL'}; holdout B {'PASS' if results['B'] else 'FAIL'}")


if __name__ == "__main__":
    main()
