#!/usr/bin/env python3
"""Daily OHLCV + funding for the Binance USDT-M perp archive (both local caches) and Delta India, as aligned numpy arrays.

Arrays are (days x coins) with NaN where a coin has no bar. Dates are UTC calendar days of the kline open.
Funding is the sum of the day's funding fractions (paid by longs), keyed by the day the funding was charged, as in
cex-mm/scripts/trend_backtest.py::load_binance. Delta funding is the day's mean hourly rate (% per 8 h) * 3 / 100.
"""
from __future__ import annotations
import csv, datetime as dt, hashlib, json, os
import numpy as np

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
CACHES = [f"{SP}/trend-cache", f"{SP}/av_cache", f"{SP}/universe/cache", f"{SP}/universe/cache_all"]
NINE = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
EXANTE24 = "BTC ETH BCH XRP EOS LTC TRX ETC LINK XLM ADA XMR DASH ZEC XTZ BNB ATOM ONT IOTA BAT VET NEO QTUM IOST".split()
ALL25 = EXANTE24 + ["DOGE"]
CVALS = {"BTC": 0.001, "BNB": 0.1, "ETH": 0.01, "LTC": 0.1, "LINK": 1.0, "DOGE": 100.0, "BCH": 0.01, "XRP": 1.0, "ADA": 1.0}


class Panel:
    """dates: list[dt.date]; coins: list[str]; O,H,L,C,V,F: float arrays (T x N), NaN where missing (F=0 where missing)."""
    def __init__(self, dates, coins, O, H, L, C, V, F, Q=None):
        self.dates, self.coins = dates, coins
        self.O, self.H, self.L, self.C, self.V, self.F = O, H, L, C, V, F
        self.Q = Q if Q is not None else np.full(C.shape, np.nan)  # quote (USD) volume
        self.idx = {d: i for i, d in enumerate(dates)}
        self.ci = {c: j for j, c in enumerate(coins)}

    def sub(self, coins):
        j = [self.ci[c] for c in coins if c in self.ci]
        cs = [c for c in coins if c in self.ci]
        return Panel(self.dates, cs, self.O[:, j], self.H[:, j], self.L[:, j], self.C[:, j], self.V[:, j], self.F[:, j], self.Q[:, j])

    def window(self, a: dt.date, b: dt.date):
        i0 = next(i for i, d in enumerate(self.dates) if d >= a)
        i1 = max(i for i, d in enumerate(self.dates) if d <= b) + 1
        return Panel(self.dates[i0:i1], self.coins, self.O[i0:i1], self.H[i0:i1], self.L[i0:i1], self.C[i0:i1], self.V[i0:i1], self.F[i0:i1], self.Q[i0:i1])


def _read_binance(coins) -> dict:
    """{coin: {date: (o,h,l,c,v)}}, {coin: {date: funding}} from every cache dir (first file wins)."""
    bars, fund, seen = {c: {} for c in coins}, {c: {} for c in coins}, set()
    for cache in CACHES:
        for fn in sorted(os.listdir(cache)):
            if not fn.startswith("binance-") or fn in seen:
                continue
            coin = fn.split("-")[1][:-4]
            if coin not in bars:
                continue
            seen.add(fn)
            with open(os.path.join(cache, fn)) as f:
                for row in csv.reader(f):
                    if not row or not row[0].isdigit():
                        continue
                    ts = int(row[0]); ts = ts / 1e6 if ts > 1e14 else ts / 1000  # 2025+ spot files use microseconds
                    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()
                    if "-1d-" in fn:
                        bars[coin][d] = (float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[7]) if len(row) > 7 else float('nan'))
                    else:
                        fund[coin][d] = fund[coin].get(d, 0.0) + float(row[2])
    return bars, fund


def load_binance(coins=ALL25, start=dt.date(2019, 12, 1), end=dt.date(2026, 9, 30)) -> Panel:
    key = hashlib.sha1(("-".join(coins) + f"_{start}_{end}").encode()).hexdigest()[:12]
    cache = f"{SP}/tools2/cache_binance_{len(coins)}c_{key}.npz"
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return Panel([dt.date.fromisoformat(s) for s in z["dates"]], list(z["coins"]), z["O"], z["H"], z["L"], z["C"], z["V"], z["F"], z["Q"] if "Q" in z else None)
    bars, fund = _read_binance(coins)
    days = sorted(d for c in coins for d in bars[c] if start <= d <= end)
    dates = sorted(set(days))
    T, N = len(dates), len(coins)
    O, H, L, C, V, Q = (np.full((T, N), np.nan) for _ in range(6))
    F = np.zeros((T, N))
    idx = {d: i for i, d in enumerate(dates)}
    for j, c in enumerate(coins):
        for d, (o, h, l, cl, v, q) in bars[c].items():
            if d in idx:
                i = idx[d]; O[i, j], H[i, j], L[i, j], C[i, j], V[i, j], Q[i, j] = o, h, l, cl, v, q
        for d, f in fund[c].items():
            if d in idx:
                F[idx[d], j] = f
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez(cache, dates=np.array([d.isoformat() for d in dates]), coins=np.array(coins), O=O, H=H, L=L, C=C, V=V, F=F, Q=Q)
    return Panel(dates, list(coins), O, H, L, C, V, F, Q)


def load_delta(coins=NINE, path=f"{SP}/trend-cache/delta-2026-10-12.json") -> Panel:
    """Delta India daily closes + funding (close only; O/H/L are set equal to close, V is NaN)."""
    raw = json.load(open(path))
    close, fund = {}, {}
    for c in coins:
        v = raw[c]
        close[c] = {dt.datetime.fromtimestamp(t, dt.timezone.utc).date(): float(px) for t, px in v["close"]}
        hourly = {}
        for t, pct in v["funding"]:
            hourly.setdefault(dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), []).append(float(pct))
        fund[c] = {d: sum(xs) / len(xs) / 100 * 3 for d, xs in hourly.items()}
    dates = sorted(set(d for c in coins for d in close[c]))
    idx = {d: i for i, d in enumerate(dates)}
    T, N = len(dates), len(coins)
    C = np.full((T, N), np.nan); F = np.zeros((T, N))
    for j, c in enumerate(coins):
        for d, px in close[c].items():
            C[idx[d], j] = px
        for d, f in fund[c].items():
            if d in idx:
                F[idx[d], j] = f
    V = np.full((T, N), np.nan)
    return Panel(dates, list(coins), C.copy(), C.copy(), C.copy(), C, V, F)


if __name__ == "__main__":
    p = load_binance()
    print(len(p.dates), p.dates[0], p.dates[-1], p.coins)
    print("bars per coin:", {c: int(np.isfinite(p.C[:, j]).sum()) for j, c in enumerate(p.coins)})
    d = load_delta()
    print("delta", len(d.dates), d.dates[0], d.dates[-1], {c: int(np.isfinite(d.C[:, j]).sum()) for j, c in enumerate(d.coins)})
