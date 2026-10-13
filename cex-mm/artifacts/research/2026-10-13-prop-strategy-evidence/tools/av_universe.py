#!/usr/bin/env python3
"""Adversarial: universe/survivorship. Repo rule (daily, TV 0.40) and the design (weekly Sunday candle, TV 0.25, band 10%) on
(a) the 9 coins, (b) 9 minus DOGE (no perp before 2020-07-10), (c) 9 minus DOGE minus BNB (no perp before 2020-02-10),
(d) all 16 extra USDT-M perps that existed by Feb 2020 + the 7 true Jan/Feb-2020 names (when downloaded), (e) extras only.
Uses the repo's own daily backtest for the daily rule and a minimal weekly variant with the same target_weights."""
import sys, os, datetime as dt, math, collections
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
cache = sys.argv[1] if len(sys.argv) > 1 else f"{SP}/trend-cache"
ALL = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST".split()
tb.COINS = ALL  # only affects fetch list; loader reads whatever files exist
close, fund = tb.load_binance(cache, dt.date(2026, 9, 30))
start, end = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
def sub(coins): return {c: close[c] for c in coins if c in close}, {c: fund[c] for c in coins if c in fund}
def weekly(cl, fu, tv=0.25, band=0.10, wd=6):
    cost = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
    days = sorted(set().union(*[set(v) for v in cl.values()]))
    eq, units, rets, yearly = 1.0, {}, [], collections.defaultdict(lambda: 1.0); peak = mdd = 0.0; peak = 1.0; gross = []
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end): continue
        if d.weekday() == wd:
            w = tb.target_weights(cl, d, tb.LOOKS, tb.VOL_WIN, tv, True)
            g = sum(abs(x) for x in w.values())
            if g > 1.0: w = {c: x / g for c, x in w.items()}
            new = {}
            for c in set(w) | set(units):
                if d not in cl[c]: continue
                tgt = w.get(c, 0.0) * eq / cl[c][d]; cur = units.get(c, 0.0)
                if tgt and band and abs(tgt - cur) < band * abs(tgt): tgt = cur
                if tgt: new[c] = tgt
            traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * cl[c][d] for c in set(new) | set(units) if d in cl[c])
            units = new
        else:
            traded = 0.0
        units = {c: u for c, u in units.items() if nxt in cl[c] and d in cl[c]}  # delisted coin drops (no cost: lenient)
        pnl = sum(u * (cl[c][nxt] - cl[c][d]) for c, u in units.items())
        fpay = sum(u * cl[c][d] * fu[c].get(nxt, 0.0) for c, u in units.items())
        r = (pnl - fpay - traded * cost) / eq
        gross.append(sum(abs(u) * cl[c][d] for c, u in units.items()) / eq)
        eq *= 1 + r; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1); rets.append(r); yearly[nxt.year] *= 1 + r
    return tb.summarize(rets, yearly, mdd, 0, 0, gross)
def show(label, s):
    print(f"{label:52s} CAGR {s['cagr']:+6.1%} vol {s['vol']:5.1%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} gross {s['gross']:.2f}x | " + " ".join(f"{y}:{v:+.0%}" for y, v in s['yearly'].items()))
sets = {"9 coins (repo)": "BTC ETH XRP BNB ADA LTC LINK DOGE BCH",
        "8 = 9 minus DOGE (no perp until 2020-07-10)": "BTC ETH XRP BNB ADA LTC LINK BCH",
        "7 = 9 minus DOGE, BNB (true Jan-2020 perps on Delta)": "BTC ETH XRP ADA LTC LINK BCH",
        "DOGE only": "DOGE"}
have_extra = all(c in close and len(close[c]) > 1000 for c in "EOS TRX ETC XLM".split())
if have_extra:
    sets["all 24 perps listed by 2020-02-20 (no DOGE)"] = "BTC ETH BCH XRP EOS LTC TRX ETC LINK XLM ADA XMR DASH ZEC XTZ BNB ATOM ONT IOTA BAT VET NEO QTUM IOST"
    sets["all 25 = 24 + DOGE"] = "BTC ETH BCH XRP EOS LTC TRX ETC LINK XLM ADA XMR DASH ZEC XTZ BNB ATOM ONT IOTA BAT VET NEO QTUM IOST DOGE"
    sets["16 extras only (not in the repo universe)"] = "EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST"
    sets["Jan-2020 perps NOT chosen: EOS TRX ETC XLM"] = "EOS TRX ETC XLM"
for label, cs in sets.items():
    cl, fu = sub(cs.split())
    print(f"\n[{label}] coins with data: {len(cl)}")
    show("  daily TV0.40 (repo rule)", tb.backtest(cl, fu, start, end, long_only=True))
    show("  weekly Sun-candle TV0.25 band10 (design)", weekly(cl, fu))
    show("  buy&hold EW", tb.buy_and_hold(cl, start, end))
