#!/usr/bin/env python3
"""D3 (minimalist skeptic) checks. Read-only on the repo; data from the scratchpad cache (Binance USDT-M perp daily
closes + funding via cex-mm/scripts/trend_backtest.py loaders; Delta India daily candles + funding from delta-2026-10-12.json).

TEST PLAN, WRITTEN BEFORE RUNNING (every row below is printed; nothing is dropped):

A. Benchmarks the strategy must beat on a risk-adjusted basis
   A1 BTC buy-and-hold (no costs, no funding)                      A2 9-coin equal-weight buy-and-hold (repo benchmark)
   A3 BTC always-long, vol-targeted (no signal; TV 0.19 / 60d vol)  A4 9 coins always-long, vol-targeted (TV 0.40/N / 60d vol)
   (A3/A4 pay the same taker 5.31 + 2 bps slippage on turnover and the same funding as the rule.)
   Cash: 0% in the Sharpe column; the 'xS' column is Sharpe over a 4.5%/yr USD cash yield [UNVERIFIED T-bill level].

B. Ablations of the pre-registered rule (long-only, 60d vol, TV/N sizing, daily rebalance at 00:00 UTC unless stated)
   B0 9 coins, looks (20,60,120)            [the pre-registered rule, baseline]
   B1 BTC only, looks (20,60,120)           B2 BTC+ETH, looks (20,60,120)
   B3 BTC+ETH, single look 120              B4 BTC+ETH, single look 60
   B5 9 coins, single look 120              B6 9 coins, weekly rebalance (every 7th day)
   B7 BTC+ETH, weekly rebalance             B8 9 coins, NO vol targeting (w_i = sig_i / 9)
   B9 BTC+ETH, NO vol targeting (w_i = sig_i / 2)
   Sub-periods: 2020-05..2021-12, 2022, 2023, 2024, 2025, 2026 (to 10-12), 2022..2026-10-12.
   Each row also reports correlation and beta to BTC daily returns and annualized alpha vs BTC.

SELECTION RULE, DECLARED BEFORE RUNNING: D3 keeps B0 unless a strictly simpler variant has
   (i) full-period Sharpe >= Sharpe(B0) - 0.15, (ii) 2022..2026 Sharpe >= Sharpe_2022-26(B0) - 0.15, and
   (iii) CAGR/|maxDD| >= that of B0 - 0.2.
   Among qualifiers the simplest wins, simplicity ordered: fewer coins > weekly rebalance > single lookback > no vol targeting.
   Whatever is chosen, it is a choice made after seeing these results and is labelled as such in D3.md.

C. Delta reproduction: B0 and the chosen variant on Delta prices/funding 2024-08-10..2026-10-12, and the daily-return
   correlation with the Binance run over the same days (the session's earlier -0.036 was computed over mismatched days).
"""
from __future__ import annotations
import sys, os, math, datetime as dt, collections
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
CACHE = f"{SP}/trend-cache"
COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
END = dt.date(2026, 10, 12)
START = dt.date(2020, 5, 1)
PERIODS = [("2020-05..2021-12", dt.date(2020, 5, 1), dt.date(2021, 12, 31)), ("2022", dt.date(2022, 1, 1), dt.date(2022, 12, 31)),
           ("2023", dt.date(2023, 1, 1), dt.date(2023, 12, 31)), ("2024", dt.date(2024, 1, 1), dt.date(2024, 12, 31)),
           ("2025", dt.date(2025, 1, 1), dt.date(2025, 12, 31)), ("2026..10-12", dt.date(2026, 1, 1), END),
           ("2022..2026", dt.date(2022, 1, 1), END)]
CASH = 0.045


def sig_weights(close, d, coins, looks, tv, vol_target: bool, long_only=True):
    """Same math as tb.target_weights, restricted to `coins`; vol_target=False gives w_i = sig_i / N."""
    sub = {c: close[c] for c in coins if c in close}
    if vol_target:
        return tb.target_weights(sub, d, looks, tb.VOL_WIN, tv, long_only)
    sig = {}
    span = max(max(looks), tb.VOL_WIN) + 1
    for c, px in sub.items():
        hist = [px.get(d - dt.timedelta(k)) for k in range(span)]
        if any(h is None for h in hist):
            continue
        s = sum(tb.sign(hist[0] / hist[L] - 1) for L in looks) / len(looks)
        sig[c] = max(s, 0.0) if long_only else s
    n = len(sig) or 1
    return {c: s / n for c, s in sig.items()}


def run(close, fund, coins, looks=tb.LOOKS, tv=tb.TARGET_VOL, vol_target=True, rebal_days=1, always_long=False,
        start=START, end=END, costs=True):
    days = sorted(set().union(*[set(close[c]) for c in coins if c in close]))
    eq, units, out = 1.0, {}, collections.OrderedDict()
    fees = fpaid = 0.0; gross = []; trades = 0; i = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        if i % rebal_days == 0:
            if always_long:
                sub = {c: close[c] for c in coins if c in close}
                w = tb.target_weights(sub, d, (1,), tb.VOL_WIN, tv, True)  # sign of 1-day return, then forced to 1 below
                w = {}
                for c, px in sub.items():
                    hist = [px.get(d - dt.timedelta(k)) for k in range(tb.VOL_WIN + 1)]
                    if any(h is None for h in hist):
                        continue
                    r = [math.log(hist[k] / hist[k + 1]) for k in range(tb.VOL_WIN)]
                    v = math.sqrt(sum(x * x for x in r) / tb.VOL_WIN * 365)
                    w[c] = (tv / len(sub)) / max(v, 0.05) if vol_target else 1.0 / len(sub)
            else:
                w = sig_weights(close, d, coins, looks, tv, vol_target)
            new = {}
            for c, x in w.items():
                u = x * eq / close[c][d]
                if u and nxt in close[c]:
                    new[c] = u
        else:
            new = {c: u for c, u in units.items() if nxt in close[c]}
        i += 1
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units)) if costs else 0.0
        trades += sum(1 for c in set(new) | set(units) if abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] > 1e-9)
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items()) if costs else 0.0
        r = (pnl - fpay - traded * COST) / eq
        fees += traded * COST / eq; fpaid += fpay / eq
        gross.append(sum(abs(u) * close[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r
        out[nxt] = r
        units = new
    yrs = len(out) / 365
    return dict(rets=out, fees=fees / yrs, funding=fpaid / yrs, gross=sum(gross) / len(gross), trades=trades / yrs)


def bh(close, coins, start=START, end=END):
    days = sorted(set().union(*[set(close[c]) for c in coins]))
    out = collections.OrderedDict()
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        cs = [c for c in coins if d in close[c] and nxt in close[c]]
        out[nxt] = sum(close[c][nxt] / close[c][d] - 1 for c in cs) / len(cs)
    return dict(rets=out, fees=0.0, funding=0.0, gross=1.0, trades=0.0)


def stats(rets: list[float]):
    n = len(rets)
    if n < 10:
        return None
    mu = sum(rets) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    tot = math.prod(1 + x for x in rets); yrs = n / 365
    peak, mdd, e = 1.0, 0.0, 1.0
    for x in rets:
        e *= 1 + x; peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    vol = sd * math.sqrt(365)
    return dict(n=n, cagr=tot ** (1 / yrs) - 1, vol=vol, sharpe=mu / sd * math.sqrt(365) if sd else 0.0,
                xs=(mu * 365 - CASH) / vol if vol else 0.0, mdd=mdd, calmar=(tot ** (1 / yrs) - 1) / abs(mdd) if mdd else 0.0,
                worst=min(rets))


def beta_stats(sr: dict, br: dict):
    ks = [k for k in sr if k in br]
    a = [sr[k] for k in ks]; b = [br[k] for k in ks]
    n = len(ks); ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)
    vb = sum((y - mb) ** 2 for y in b) / (n - 1); va = sum((x - ma) ** 2 for x in a) / (n - 1)
    beta = cov / vb; corr = cov / math.sqrt(va * vb)
    alpha = (ma - beta * mb) * 365
    return corr, beta, alpha


def row(label, res, btc_rets):
    s = stats(list(res["rets"].values()))
    corr, beta, alpha = beta_stats(res["rets"], btc_rets)
    print(f"{label:44s} CAGR {s['cagr']:+6.1%} vol {s['vol']:4.0%} Sharpe {s['sharpe']:5.2f} xS {s['xs']:5.2f} maxDD {s['mdd']:6.1%} "
          f"CAGR/DD {s['calmar']:4.2f} worst {s['worst']:+6.2%} | fees {res['fees']:4.1%} fund {res['funding']:+4.1%} gross {res['gross']:.2f}x "
          f"trades/yr {res['trades']:5.0f} | corrBTC {corr:+.2f} beta {beta:+.2f} alpha {alpha:+.1%}")
    cells = []
    for name, a, b in PERIODS:
        sub = [r for d, r in res["rets"].items() if a <= d <= b]
        ps = stats(sub)
        cells.append(f"{name}: {ps['cagr']:+.0%}/S{ps['sharpe']:.2f}/DD{ps['mdd']:.0%}" if ps else f"{name}: n/a")
    print("    " + "  ".join(cells))
    return s


def main():
    close, fund = tb.load_binance(CACHE, END)
    print(f"Binance USDT-M perp daily data: coins {sorted(close)}; BTC days {len(close['BTC'])}; window {START}..{END}")
    btc = bh(close, ["BTC"])["rets"]
    print("\n=== A. Benchmarks ===")
    row("A1 BTC buy-and-hold (no costs)", bh(close, ["BTC"]), btc)
    row("A2 9-coin EW buy-and-hold (no costs)", bh(close, tb.COINS), btc)
    row("A3 BTC always-long vol-targeted TV0.19", run(close, fund, ["BTC"], tv=0.19, always_long=True), btc)
    row("A4 9 coins always-long vol-targeted TV0.40/N", run(close, fund, tb.COINS, tv=0.40, always_long=True), btc)
    print("\n=== B. Ablations of the pre-registered rule ===")
    res = {}
    res["B0"] = row("B0 9 coins, looks 20/60/120, daily [PRE-REG]", run(close, fund, tb.COINS), btc)
    res["B1"] = row("B1 BTC only, looks 20/60/120", run(close, fund, ["BTC"]), btc)
    res["B2"] = row("B2 BTC+ETH, looks 20/60/120", run(close, fund, ["BTC", "ETH"]), btc)
    res["B3"] = row("B3 BTC+ETH, single look 120", run(close, fund, ["BTC", "ETH"], looks=(120,)), btc)
    res["B4"] = row("B4 BTC+ETH, single look 60", run(close, fund, ["BTC", "ETH"], looks=(60,)), btc)
    res["B5"] = row("B5 9 coins, single look 120", run(close, fund, tb.COINS, looks=(120,)), btc)
    res["B6"] = row("B6 9 coins, weekly rebalance", run(close, fund, tb.COINS, rebal_days=7), btc)
    res["B7"] = row("B7 BTC+ETH, weekly rebalance", run(close, fund, ["BTC", "ETH"], rebal_days=7), btc)
    res["B8"] = row("B8 9 coins, no vol targeting (sig/N)", run(close, fund, tb.COINS, vol_target=False), btc)
    res["B9"] = row("B9 BTC+ETH, no vol targeting (sig/2)", run(close, fund, ["BTC", "ETH"], vol_target=False), btc)
    print("\n=== C. Delta India prices and funding, 2024-08-10..2026-10-12 ===")
    dclose, dfund = tb.load_delta(CACHE, END)
    s0, e0 = dt.date(2024, 8, 10), END
    dbtc = bh(dclose, ["BTC"], s0, e0)["rets"]
    for label, coins, kw in (("B0 on Delta", tb.COINS, {}), ("B2 BTC+ETH on Delta", ["BTC", "ETH"], {}),
                             ("B6 weekly on Delta", tb.COINS, {"rebal_days": 7}), ("B7 BTC+ETH weekly on Delta", ["BTC", "ETH"], {"rebal_days": 7}),
                             ("A1 BTC B&H (Delta)", None, None)):
        if coins is None:
            row(label, bh(dclose, ["BTC"], s0, e0), dbtc); continue
        rd = run(dclose, dfund, coins, start=s0, end=e0, **kw)
        rb = run(close, fund, coins, start=s0, end=e0, **kw)
        row(label, rd, dbtc)
        ks = [k for k in rd["rets"] if k in rb["rets"]]
        a = [rd["rets"][k] for k in ks]; b = [rb["rets"][k] for k in ks]
        n = len(ks); ma, mb = sum(a) / n, sum(b) / n
        corr = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
        print(f"    same-day correlation Delta vs Binance run over {n} days: {corr:.3f}")


if __name__ == "__main__":
    main()
