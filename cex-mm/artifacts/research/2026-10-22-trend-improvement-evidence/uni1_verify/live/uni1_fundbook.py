#!/usr/bin/env python3
"""Part 7: book-level funding 2026-07-01..2026-09-30 for UNI-1 and the live nine: target weights held t -> t+1 times Binance daily
funding (panel F, the backtest) vs Delta daily funding (sum of hourly FUNDING rates %/8h /100/8). Annualized, % of equity. stdout."""
import json, os, sys, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f"{SP}/tools2"); sys.dont_write_bytecode = True
import data, variants_universe as vu  # noqa: E402
P = vu.load_pool(); ctx = vu._ctx(P)
a, b = P.idx[dt.date(2026, 7, 1)], P.idx[dt.date(2026, 9, 30)]
names = "BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK ZEC HYPE ADA LTC BCH".split()
FD = {}
for c in names:
    rows = json.load(open(f"{HERE}/dl/fund_{c}USD.json")); d = {}
    for r in rows:
        day = dt.datetime.fromtimestamp(r["time"], dt.timezone.utc).date(); d[day] = d.get(day, 0.0) + float(r["close"]) / 100 / 8
    FD[c] = d
for cad in (vu.DAILY, vu.WEEKLY):
    for lab, U in (("UNI-1", vu._membership(ctx, cad, vu.SPECS["UNI-1"])[0]), ("nine", vu._static_mask(ctx, data.NINE))):
        W = vu._weights(ctx, cad, U)
        fb = fd = 0.0
        for t in range(a - 1, b):
            for j in np.flatnonzero(W[t]):
                c = ctx.coins[j]; fb += W[t, j] * P.F[t + 1, j]; fd += W[t, j] * FD[c].get(P.dates[t + 1], 0.0)
        n = b - a + 1
        print(f"{cad['name']:6s} {lab:5s}: funding paid {fb*365/n:+.2%}/yr on Binance rates vs {fd*365/n:+.2%}/yr on Delta rates (ratio {fd/fb:.2f}); mean gross {np.abs(W[a-1:b]).sum(axis=1).mean():.2f}")
