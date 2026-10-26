"""Diagnostics for rule B of quick_check.py (Oil Money analogue, L/S): which side earns, by year,
correlation with the equal-weight nine, and the same entries hedged with beta x BTC.
Usage: python3 -I quick_check_diag.py <av_cache-dir>"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import quick_check as q

cache = sys.argv[1]
close = pd.DataFrame({c: q.load_close(cache, c) for c in q.COINS}).loc[q.START:q.END]
fund = pd.DataFrame({c: q.load_funding(cache, c) for c in q.COINS}).reindex(close.index).fillna(0.0)
rets = close.pct_change()
side_ret = {1: [], -1: []}
hedged, ents = [], {1: 0, -1: 0}
hside = {1: [], -1: []}
trade_net = []
for Y in q.COINS[1:]:
    d = close[["BTC", Y]].dropna(); idx = d.index
    lx, ly = np.log(d["BTC"].values), np.log(d[Y].values)
    n = len(idx); pos = np.zeros(n); beta = np.zeros(n)
    holding, trained, counter = 0, False, 0
    for i in range(50, n):
        if holding != 0:
            if counter > 10:
                holding, trained, counter = 0, False, 0
                continue
            counter += 1; pos[i] = holding; beta[i] = fc[1]; continue
        if not trained:
            coef, e = q.ols(ly[i-50:i], lx[i-50:i])
            sst = float(((ly[i-50:i]-ly[i-50:i].mean())**2).sum())
            if sst > 0 and 1 - float(e @ e)/sst > 0.7:
                trained, fc, sig = True, coef, e.std()
        if trained:
            f = fc[0] + fc[1]*lx[i]
            if ly[i] > f + 2*sig: holding = 1
            elif ly[i] < f - 2*sig: holding = -1
            if holding != 0:
                ents[holding] += 1; pos[i] = holding; beta[i] = fc[1]
    p = pd.Series(pos, idx); b = pd.Series(beta, idx)
    held = p.shift(1).fillna(0.0); bh = b.shift(1).fillna(0.0)
    ry = rets[Y].reindex(idx); rb = rets["BTC"].reindex(idx)
    dp = p.diff().abs().fillna(p.abs())
    leg = held*ry - held*fund[Y].reindex(idx) - dp.shift(1).fillna(0.0)*q.SIDE
    side = held.where(held != 0, held.shift(1).fillna(0.0))  # exit-day cost belongs to the closed side
    for s in (1, -1):
        side_ret[s].append(leg.where(side == s, 0.0).reindex(close.index).fillna(0.0))
    dpb = (p*b).diff().abs().fillna((p*b).abs())
    h = leg - held*bh*rb + held*bh*fund["BTC"].reindex(idx) - dpb.shift(1).fillna(0.0)*q.SIDE
    hedged.append(h.reindex(close.index).fillna(0.0))
    for s in (1, -1):
        hside[s].append(h.where(side == s, 0.0).reindex(close.index).fillna(0.0))
    # per-trade net of the hedged trade, in bps of alt notional
    cur, prevside = 0.0, 0.0
    for hv, sv in zip(h.fillna(0.0).values, side.values):
        if sv != 0:
            cur += hv
        if prevside != 0 and sv == 0:
            trade_net.append(cur); cur = 0.0
        prevside = sv
L = pd.concat(side_ret[1], axis=1).mean(axis=1); S = pd.concat(side_ret[-1], axis=1).mean(axis=1)
H = pd.concat(hedged, axis=1).mean(axis=1); B = L + S
ew = rets[q.COINS].mean(axis=1).fillna(0.0)
print("entries long / short:", ents[1], "/", ents[-1])
tn = np.array(trade_net) * 1e4
print(f"BTC-hedged closed trades {len(tn)}: mean net {tn.mean():.1f} bps of alt notional, median {np.median(tn):.1f}, "
      f"share > 0 {np.mean(tn > 0) * 100:.1f}%; cost charged per hedged round trip about {4 * q.SIDE * 1e4:.1f} bps at beta 1")
HL = pd.concat(hside[1], axis=1).mean(axis=1); HS = pd.concat(hside[-1], axis=1).mean(axis=1)
print("year   long-leg  short-leg  L/S book  BTC-hedged  hedged-long-alt  hedged-short-alt  EW-nine   (sum of daily returns, %)")
for y, g in B.groupby(B.index.year):
    yy = str(y)
    print(f"{y}  {L.loc[yy].sum()*100:8.1f}  {S.loc[yy].sum()*100:9.1f}  {B.loc[yy].sum()*100:8.1f}  {H.loc[yy].sum()*100:10.1f}  {HL.loc[yy].sum()*100:15.1f}  {HS.loc[yy].sum()*100:16.1f}  {ew.loc[yy].sum()*100:7.1f}")
for nm, a, bnd in (("FULL", q.START, q.END), ("2022-26", "2022-01-01", q.END)):
    print(nm, "corr(L/S book, EW nine) =", round(float(np.corrcoef(B.loc[a:bnd], ew.loc[a:bnd])[0, 1]), 3),
          "| BTC-hedged Sharpe =", round(float(H.loc[a:bnd].mean()/H.loc[a:bnd].std()*np.sqrt(365)), 2),
          "| L/S Sharpe =", round(float(B.loc[a:bnd].mean()/B.loc[a:bnd].std()*np.sqrt(365)), 2))
