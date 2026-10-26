"""Quick descriptive check of two je-suis-tm/quant-trading rules, re-implemented from scratch
(no code from that repo is imported or executed) on Binance USDT-M daily candles + funding of our nine.
NOT a pre-registered test: one run per rule, no multiple-testing haircut. The PAIR-1 screen is frozen
separately (screen_PAIR1_frozen.txt) and is NOT run here.

Usage: python3 -I quick_check.py <av_cache-dir>

A. "Pair trading backtest.py" rule, with its visible bugs fixed:
   rolling 250-day Engle-Granger step 1 (OLS ln Y on ln X over [t-250, t-1]) + ADF on the residual
   against the ordinary Dickey-Fuller 5% value (-2.87, what adfuller's p-value uses, as in the repo)
   + step 2 error-correction sign; model frozen at cointegration onset (as the repo);
   bands at z = +/-1 (README line 106, not the code's z_onset +/- sd_resid); hold while |z| > 1,
   flat when back inside or when cointegration breaks. Legs: Y notional 1, X notional beta.
B. "Oil Money Trading backtest.py" rule on alt vs BTC (ln prices): fit on the last 50 closes when
   untrained; valid if R^2 > 0.7; +/-2 sigma band from the frozen model; go WITH the break
   (long above, short below); exit after the repo's counter (> 10, i.e. 12 bars); stop disabled
   (the author's heatmap says the stop does not matter, README line 111). Single leg, as the repo.

Timing: signal on the close of day t, position held close t -> close t+1. Costs 7.31 bps per side
(Delta taker 5.31 incl. GST + 2 bps slippage) on every unit of notional traded. Funding charged:
long pays, short receives, Binance 8 h rates summed per day.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

COINS = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
SIDE = 7.31e-4
START, END = "2020-05-01", "2026-09-30"
WINDOWS = {"FULL": (START, END), "2020-21": (START, "2021-12-31"),
           "2022-26": ("2022-01-01", END), "2024-26": ("2024-01-01", END)}
DF_CRIT_5 = -2.873  # Dickey-Fuller, constant, n~250, 5 %


def load_close(cache, coin):
    parts = []
    for f in sorted(glob.glob(os.path.join(cache, f"binance-{coin}USDT-1d-20*.csv"))):
        d = pd.read_csv(f)
        if not str(d.columns[0]).startswith("open_time"):
            d = pd.read_csv(f, header=None, usecols=[0, 4], names=["open_time", "close"])
        parts.append(d[["open_time", "close"]])
    d = pd.concat(parts)
    d["open_time"] = pd.to_numeric(d["open_time"])
    d.loc[d["open_time"] > 1e14, "open_time"] //= 1000
    d["date"] = pd.to_datetime(d["open_time"], unit="ms").dt.normalize()
    return d.drop_duplicates("date").set_index("date").sort_index()["close"].astype(float)


def load_funding(cache, coin):
    parts = []
    for f in sorted(glob.glob(os.path.join(cache, f"binance-{coin}USDT-fundingRate-20*.csv"))):
        d = pd.read_csv(f)
        if not str(d.columns[0]).startswith("calc_time"):
            d = pd.read_csv(f, header=None, names=["calc_time", "funding_interval_hours", "last_funding_rate"])
        parts.append(d[["calc_time", "last_funding_rate"]])
    d = pd.concat(parts)
    d["calc_time"] = pd.to_numeric(d["calc_time"])
    d["date"] = pd.to_datetime(d["calc_time"], unit="ms").dt.normalize()
    return d.groupby("date")["last_funding_rate"].sum().astype(float)


def ols(y, x):
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    return coef, resid


def adf_t(e, maxlag=15):
    """ADF t-stat (constant, AIC lag choice on a common sample), like adfuller(autolag='AIC')."""
    de = np.diff(e)
    n = len(de)
    best = None
    for p in range(maxlag + 1):
        rows = n - maxlag
        y = de[maxlag:]
        cols = [np.ones(rows), e[maxlag:-1]]
        for k in range(1, p + 1):
            cols.append(de[maxlag - k:n - k])
        X = np.column_stack(cols)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ coef
        ssr = float(r @ r)
        aic = rows * np.log(ssr / rows) + 2 * X.shape[1]
        if best is None or aic < best[0]:
            best = (aic, p)
    p = best[1]
    y = de[p:]
    cols = [np.ones(len(y)), e[p:-1]]
    for k in range(1, p + 1):
        cols.append(de[p - k:n - k])
    X = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ coef
    s2 = float(r @ r) / (len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    return coef[1] / np.sqrt(cov[1, 1])


def stats(ret, pos_turn, label, window):
    a, b = WINDOWS[window]
    r = ret.loc[a:b]
    t = pos_turn.loc[a:b]
    if r.std() == 0 or len(r) == 0:
        return f"{label:<44}{window:<9} no exposure"
    ann = r.mean() * 365
    sh = r.mean() / r.std() * np.sqrt(365)
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return f"{label:<44}{window:<9}{ann * 100:>8.1f}%{sh:>8.2f}{dd * 100:>9.1f}%{t.sum() / (len(r) / 365):>10.1f}"


def rule_a(lx, ly, fx, fy, idx):
    n = len(idx)
    pos = np.zeros(n)        # +1 = short Y / long beta X (z > 1); -1 = the reverse
    beta_used = np.zeros(n)
    prev = False
    model = None
    for i in range(250, n - 1):
        ywin, xwin = ly[i - 250:i], lx[i - 250:i]
        coef, e = ols(ywin, xwin)
        ok = adf_t(e) <= DF_CRIT_5
        if ok:
            dy, dx = np.diff(ywin), np.diff(xwin)
            X = np.column_stack([np.ones(len(dy)), dx, e[:-1]])
            c2, *_ = np.linalg.lstsq(X, dy, rcond=None)
            ok = c2[-1] <= 0
        if ok and not prev:
            model = (coef, e.mean(), e.std())
        if ok and model is not None:
            (a, b), mu, sd = model
            z = (ly[i] - a - b * lx[i] - mu) / sd
            pos[i] = 1.0 if z > 1 else (-1.0 if z < -1 else 0.0)
            beta_used[i] = b
        prev = ok
    return pos, beta_used


def main():
    cache = sys.argv[1]
    close = pd.DataFrame({c: load_close(cache, c) for c in COINS}).loc[START:END]
    fund = pd.DataFrame({c: load_funding(cache, c) for c in COINS}).reindex(close.index).fillna(0.0)
    rets = close.pct_change()
    print("data:", {c: (str(close[c].first_valid_index().date()), int(close[c].notna().sum())) for c in COINS})
    print("columns: annual return, Sharpe (365), max DD, unit sides traded per instrument per year\n")

    # ---------------- A: pairs ----------------
    pair_ret, pair_turn, trips, gross_trip = [], [], 0, []
    for ix, X in enumerate(COINS):
        for Y in COINS[ix + 1:]:
            d = close[[X, Y]].dropna()
            idx = d.index
            lx, ly = np.log(d[X].values), np.log(d[Y].values)
            pos, b = rule_a(lx, ly, None, None, idx)
            rx = rets[X].reindex(idx).values
            ry = rets[Y].reindex(idx).values
            fxv = fund[X].reindex(idx).values
            fyv = fund[Y].reindex(idx).values
            p = pd.Series(pos, idx)
            bb = pd.Series(b, idx)
            held = p.shift(1).fillna(0.0)
            bh = bb.shift(1).fillna(0.0)
            pnl_px = held * (bh * rx - ry)
            pnl_f = held * (fyv - bh * fxv)
            dpos_y = p.diff().abs().fillna(p.abs())
            dpos_x = (p * bb).diff().abs().fillna((p * bb).abs())
            cost = (dpos_y + dpos_x).shift(1).fillna(0.0) * SIDE
            # normalise by the gross notional of the latest episode (1 + |beta|), forward-filled
            gnot = (1 + bb.where(bb != 0).abs()).ffill().fillna(1.0)
            r = ((pnl_px + pnl_f - cost) / gnot.shift(1).fillna(1.0)).fillna(0.0)
            pair_ret.append(r.reindex(close.index).fillna(0.0))
            pair_turn.append(((dpos_y + dpos_x) / gnot).reindex(close.index).fillna(0.0))
            # round trips and gross per trip (price only, per unit Y notional)
            entries = (p != 0) & (p.shift(1).fillna(0) != p)
            trips += int(entries.sum())
            cur = 0.0
            for v_hold, v_px, v_pos, v_prev in zip(held.values, pnl_px.fillna(0).values, p.values,
                                                   p.shift(1).fillna(0).values):
                if v_hold != 0:
                    cur += v_px
                if v_prev != 0 and v_pos != v_prev:
                    gross_trip.append(cur)
                    cur = 0.0
    book = pd.concat(pair_ret, axis=1).mean(axis=1)
    turn = pd.concat(pair_turn, axis=1).mean(axis=1)
    expo = (pd.concat(pair_ret, axis=1) != 0).mean(axis=1)
    print("A. Pair trading rule (bug-fixed), 36 pairs of the nine, equal weight, per unit of gross")
    for w in WINDOWS:
        print("  " + stats(book, turn, "EG-250, |z|>1 hold, exit at band", w))
    gt = np.array(gross_trip) * 1e4
    print(f"  round trips: {trips}; closed trips with P&L: {len(gt)}; mean gross price P&L per trip "
          f"{gt.mean():.1f} bps of Y notional (median {np.median(gt):.1f}); cost per trip about "
          f"{4 * SIDE * 1e4:.1f} bps for equal legs; mean share of pair-days in position {expo.mean() * 100:.1f}%\n")

    # ---------------- B: oil money analogue ----------------
    print("B. Oil Money rule on alt vs BTC (ln prices), equal weight over 8 alts")
    for long_only in (False, True):
        rr, tt = [], []
        ntr = 0
        for Y in COINS[1:]:
            d = close[["BTC", Y]].dropna()
            idx = d.index
            lx, ly = np.log(d["BTC"].values), np.log(d[Y].values)
            n = len(idx)
            pos = np.zeros(n)
            holding, trained, counter = 0, False, 0
            fc = sig = None
            for i in range(50, n):
                if holding != 0:
                    if counter > 10:
                        holding, trained, counter = 0, False, 0
                        pos[i] = 0
                        continue
                    counter += 1
                    pos[i] = holding
                    continue
                if not trained:
                    coef, e = ols(ly[i - 50:i], lx[i - 50:i])
                    sst = float(((ly[i - 50:i] - ly[i - 50:i].mean()) ** 2).sum())
                    r2 = 1 - float(e @ e) / sst if sst > 0 else 0
                    if r2 > 0.7:
                        trained, fc, sig = True, coef, e.std()
                if trained:
                    f = fc[0] + fc[1] * lx[i]
                    if ly[i] > f + 2 * sig:
                        holding = 1
                    elif ly[i] < f - 2 * sig and not long_only:
                        holding = -1
                    if holding != 0:
                        ntr += 1
                        pos[i] = holding
            p = pd.Series(pos, idx)
            held = p.shift(1).fillna(0.0)
            r = held * rets[Y].reindex(idx) - held * fund[Y].reindex(idx)
            dp = p.diff().abs().fillna(p.abs())
            r = r - dp.shift(1).fillna(0.0) * SIDE
            rr.append(r.reindex(close.index).fillna(0.0))
            tt.append(dp.reindex(close.index).fillna(0.0))
        book = pd.concat(rr, axis=1).mean(axis=1)
        turn = pd.concat(tt, axis=1).mean(axis=1)
        lab = "R2>0.7, 2-sigma break, follow, 12 bars" + (" (long only)" if long_only else " (L/S)")
        for w in WINDOWS:
            print("  " + stats(book, turn, lab, w))
        print(f"  entries: {ntr}\n")
    ew = rets[COINS].mean(axis=1).fillna(0.0)
    zero = pd.Series(0.0, ew.index)
    for w in WINDOWS:
        print("  " + stats(ew, zero, "reference: always long, equal weight, no cost", w))


if __name__ == "__main__":
    main()
