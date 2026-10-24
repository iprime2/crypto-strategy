"""Quick descriptive check of the three mean-reversion families from je-suis-tm/quant-trading,
re-implemented from scratch (no code from that repo is imported or executed), on Binance USDT-M
daily candles of our nine coins.  NOT a pre-registered test: one run, no multiple-testing haircut.

Usage: python3 -I quick_check.py <trend-cache-dir>

Costs: 7.31 bps per side (Delta taker 5.31 incl. GST + 2 bps slippage), i.e. 14.62 bps round trip,
charged on every unit change of position. Funding is NOT charged (longs usually pay it).
Timing: signal from the close of day t, position held over close t -> close t+1 (no same-bar fill).
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

COINS = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
SIDE_COST = 7.31e-4
START, END = "2020-05-01", "2026-09-30"
SPLIT = "2022-01-01"


def load(cache, coin):
    files = sorted(glob.glob(os.path.join(cache, f"binance-{coin}USDT-1d-20*.csv")))
    parts = []
    for f in files:
        d = pd.read_csv(f)
        if not str(d.columns[0]).startswith("open_time"):
            d = pd.read_csv(f, header=None, names=["open_time", "open", "high", "low", "close", "volume",
                                                   "close_time", "qv", "count", "tbv", "tbqv", "ignore"])
        parts.append(d[["open_time", "open", "high", "low", "close"]])
    d = pd.concat(parts)
    d["open_time"] = pd.to_numeric(d["open_time"])
    # some archives are in microseconds
    d.loc[d["open_time"] > 1e14, "open_time"] //= 1000
    d["date"] = pd.to_datetime(d["open_time"], unit="ms").dt.normalize()
    d = d.drop_duplicates("date").set_index("date").sort_index()
    return d[["open", "high", "low", "close"]].astype(float)


def wilder_rsi(close, n=14):
    delta = close.diff()
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    au = up.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = au / ad
    return 100.0 - 100.0 / (1.0 + rs)


def pos_rsi(d, long_only):
    r = wilder_rsi(d["close"])
    p = pd.Series(0.0, index=d.index)
    p[r < 30] = 1.0
    if not long_only:
        p[r > 70] = -1.0
    p[r.isna()] = 0.0
    return p


def pos_bb(d, long_only, n=20, k=2.0):
    c = d["close"]
    mid = c.rolling(n, min_periods=n).mean()
    sd = c.rolling(n, min_periods=n).std()
    up, lo = mid + k * sd, mid - k * sd
    out = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if np.isnan(mid.iloc[i]):
            out[i] = 0.0
            continue
        x = c.iloc[i]
        if cur == 1.0 and x >= mid.iloc[i]:
            cur = 0.0
        elif cur == -1.0 and x <= mid.iloc[i]:
            cur = 0.0
        if cur == 0.0:
            if x < lo.iloc[i]:
                cur = 1.0
            elif x > up.iloc[i] and not long_only:
                cur = -1.0
        out[i] = cur
    return pd.Series(out, index=c.index)


def strat_returns(d, pos):
    ret = d["close"].pct_change()
    held = pos.shift(1).fillna(0.0)
    cost = pos.diff().abs().fillna(pos.abs()) * SIDE_COST  # trade at close t, cost booked on day t
    gross = held * ret
    net = gross - cost
    return gross.fillna(0.0), net.fillna(0.0), pos.diff().abs().fillna(0.0)


def sharpe(x):
    x = x.dropna()
    return float(x.mean() / x.std() * np.sqrt(365)) if x.std() > 0 else float("nan")


def ann(x):
    return float(x.mean() * 365)


def portfolio(data, fn):
    g, n, t = {}, {}, {}
    for c, d in data.items():
        p = fn(d)
        gg, nn, tt = strat_returns(d, p)
        g[c], n[c], t[c] = gg, nn, tt
    G = pd.DataFrame(g).loc[START:END]
    N = pd.DataFrame(n).loc[START:END]
    T = pd.DataFrame(t).loc[START:END]
    live = pd.DataFrame({c: d["close"] for c, d in data.items()}).loc[START:END].notna()
    w = live.div(live.sum(axis=1), axis=0)
    return (G * w).sum(axis=1), (N * w).sum(axis=1), T, live


def shooting_star(d, lookahead):
    o, h, l, c = d["open"], d["high"], d["low"], d["close"]
    body = (o - c).abs()
    c1 = o >= c
    c2 = (c - l) < 0.2 * body
    c3 = body < 0.5 * body.rolling(20, min_periods=20).mean().shift(1)  # causal stand-in for full-sample mean
    c4 = (h - o) >= 2 * (o - c)
    c5 = c >= c.shift(1)
    c6 = c.shift(1) >= c.shift(2)
    sig = c1 & c2 & c3 & c4 & c5 & c6
    if lookahead:
        sig = sig & (h.shift(-1) <= h) & (c.shift(-1) <= c)
    return sig.fillna(False)


def star_trades(d, sig, hold=7, stop=0.05):
    c = d["close"].values
    idx = np.where(sig.values)[0]
    out = []
    nxt = -1
    for i in idx:
        if i <= nxt:  # one position at a time per coin (the original stacks overlapping shorts)
            continue
        e = c[i]
        j = i
        k = 0
        while j + 1 < len(c):
            j += 1
            k += 1
            if abs(c[j] / e - 1) > stop or k >= hold:
                break
        if k == 0:
            continue
        gross = -(c[j] / e - 1)
        out.append((d.index[i], gross, gross - 2 * SIDE_COST))
        nxt = j
    return out


def main(cache):
    data = {}
    for c in COINS:
        data[c] = load(cache, c)
    print("data:", {c: (str(d.index[0].date()), str(d.index[-1].date()), len(d)) for c, d in data.items()})
    rules = {
        "RSI14 30/70 long/short (repo rule, lagged)": lambda d: pos_rsi(d, False),
        "RSI14 <30 long only": lambda d: pos_rsi(d, True),
        "BB20/2 revert-to-mid long/short": lambda d: pos_bb(d, False),
        "BB20/2 revert-to-mid long only": lambda d: pos_bb(d, True),
    }
    print("\nEqual-weight nine-coin book, unit notional per coin, daily, costs 7.31 bps/side, no funding")
    print(f"{'rule':45s} {'window':10s} {'gross ann':>9s} {'net ann':>8s} {'net Sh':>7s} {'exposure':>8s} {'sides/coin/yr':>13s}")
    for name, fn in rules.items():
        G, N, T, live = portfolio(data, fn)
        for wname, a, b in (("FULL", START, END), ("2020-21", START, "2021-12-31"), ("2022-26", SPLIT, END)):
            g, n = G.loc[a:b], N.loc[a:b]
            tt = T.loc[a:b]
            lv = live.loc[a:b]
            sides = float(tt.sum().sum() / lv.sum().sum() * 365)
            expo = None
            print(f"{name:45s} {wname:10s} {ann(g)*100:8.1f}% {ann(n)*100:7.1f}% {sharpe(n):7.2f} {'':>8s} {sides:13.1f}")
    # buy-and-hold reference over the same windows (equal weight, daily rebalanced, no cost)
    R = pd.DataFrame({c: d["close"].pct_change() for c, d in data.items()}).loc[START:END]
    bh = R.mean(axis=1)
    for wname, a, b in (("FULL", START, END), ("2020-21", START, "2021-12-31"), ("2022-26", SPLIT, END)):
        print(f"{'reference: always long, equal weight':45s} {wname:10s} {ann(bh.loc[a:b])*100:8.1f}% {'':>7s}  {sharpe(bh.loc[a:b]):7.2f}")

    print("\nShooting star short, exit at |close/entry-1|>5% or 7 bars, one trade at a time per coin, 14.62 bps round trip")
    for la in (False, True):
        rows = []
        for c, d in data.items():
            for (dt, g, n) in star_trades(d, shooting_star(d, la)):
                if pd.Timestamp(START) <= dt <= pd.Timestamp(END):
                    rows.append((c, dt, g, n))
        df = pd.DataFrame(rows, columns=["coin", "date", "gross", "net"])
        tag = "WITH next-bar look-ahead (conditions 7-8, entry at the star's close)" if la else "causal (conditions 1-6 only)"
        for wname, a, b in (("FULL", START, END), ("2020-21", START, "2021-12-31"), ("2022-26", SPLIT, END)):
            x = df[(df.date >= a) & (df.date <= b)]
            if len(x) == 0:
                print(f"  {tag:70s} {wname}: no trades")
                continue
            t = x.net.mean() / (x.net.std() / np.sqrt(len(x))) if len(x) > 1 else float("nan")
            print(f"  {tag:70s} {wname:8s} n={len(x):4d} gross {x.gross.mean()*1e4:8.1f} bps  net {x.net.mean()*1e4:8.1f} bps  t {t:5.2f}  win {100*(x.net>0).mean():4.1f}%")


if __name__ == "__main__":
    main(sys.argv[1])
