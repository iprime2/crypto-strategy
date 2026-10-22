#!/usr/bin/env python3
"""Part 5: Delta vs Binance funding (2026-07-01..2026-09-30, annualized, paid by longs) for the UNI-1 names; correlation and
tracking error of UNI-1 vs the live nine (daily returns, 2024-05-01..2026-09-30). stdout only."""
import json, os, sys, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f"{SP}/tools2"); sys.dont_write_bytecode = True
import data, sim, variants_universe as vu  # noqa: E402
P = vu.load_pool(); ctx = vu._ctx(P)
a, b = P.idx[dt.date(2026, 7, 1)], P.idx[dt.date(2026, 9, 30)]
ndays = b - a + 1
print(f"funding paid by longs, annualized, {P.dates[a]}..{P.dates[b]} ({ndays} days): Binance (panel F) vs Delta (FUNDING:<sym>USD hourly, %/8h /100/8)")
for c in "BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK ZEC HYPE ADA LTC BCH".split():
    j = ctx.coins.index(c)
    bf = float(P.F[a:b + 1, j].sum()) * 365 / ndays
    rows = json.load(open(f"{HERE}/dl/fund_{c}USD.json"))
    t0 = int(dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp()); t1 = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp())
    df = sum(float(r["close"]) for r in rows if t0 <= r["time"] < t1) / 100 / 8 * 365 / ndays
    print(f"   {c:9s} Binance {bf:+7.2%}/yr  Delta {df:+7.2%}/yr  diff {df - bf:+7.2%}")
spec = vu.SPECS["UNI-1"]
for cad in (vu.DAILY, vu.WEEKLY):
    kw = vu._kw(ctx, cad)
    U, _ = vu._membership(ctx, cad, spec)
    ru = vu._sim(ctx, vu._weights(ctx, cad, U), kw); r9 = vu._sim(ctx, vu._weights(ctx, cad, vu._static_mask(ctx, data.NINE)), kw)
    d = np.array(ru["dates"]); m = d >= dt.date(2024, 5, 1)
    x, y = ru["rets"][m], r9["rets"][m]
    rho = float(np.corrcoef(x, y)[0, 1]); te = float((x - y).std(ddof=1) * np.sqrt(365))
    # 8-week (56-day) tracking error -> how far apart two books drift over the A4 window
    print(f"{cad['name']:6s}: corr(UNI-1, nine) 2024-05..2026-09 {rho:.3f}; tracking error {te:.2%}/yr; 56-day TE ~ {te*np.sqrt(56/365):.2%}; "
          f"ann. mean diff {(x - y).mean()*365:+.2%}/yr -> t over 8 weeks {((x - y).mean()*56) / (te*np.sqrt(56/365)):.2f}")
