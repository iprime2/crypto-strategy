#!/usr/bin/env python3
"""PAIR-1 engine: daily cointegration spread reversion, market-neutral pairs (spec.md in this folder).

Own code only. Nothing from the external repo (je-suis-tm/quant-trading) is imported or executed.
Reads public Binance data from the session scratchpad caches. No orders, no keys, no network.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")  # our own trend engine (daily loader); not the external repo
import data as tdata  # noqa: E402

CACHES = [f"{SP}/trend-cache", f"{SP}/av_cache", f"{SP}/universe/cache", f"{SP}/universe/cache_all"]
NINE = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
H = 3_600_000
DAYMS = 86_400_000
EPOCH = dt.date(1970, 1, 1)


def d2ms(d: dt.date) -> int:
    return (d - EPOCH).days * DAYMS


def ms2d(ms: int) -> dt.date:
    return EPOCH + dt.timedelta(days=int(ms // DAYMS))


# ---------------------------------------------------------------- statistics: Engle-Granger with MacKinnon (1994) p

_TAU_MAX, _TAU_MIN, _TAU_STAR = 0.92, -18.86, -2.62  # regression "c", N = 2 (statsmodels adfvalues.py, index N-1 = 1)
_SMALLP = (2.92, 1.5012, 3.9796e-2)
_LARGEP = (2.1945, 6.4695e-1, -2.9198e-1, -4.2377e-2)


def _norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def mackinnonp_c2(t: float) -> float:
    if not np.isfinite(t):
        return 0.0 if t < 0 else 1.0
    if t > _TAU_MAX:
        return 1.0
    if t < _TAU_MIN:
        return 0.0
    c = _SMALLP if t <= _TAU_STAR else _LARGEP
    return _norm_cdf(sum(ci * t ** i for i, ci in enumerate(c)))


def _ols(y, X):
    coef, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    return coef, resid, rank


def adf_n_aic(x: np.ndarray, maxlag: int = 10) -> float:
    """ADF t-stat with no deterministic term, AIC lag choice 0..maxlag (statsmodels adfuller(regression='n', autolag='aic'))."""
    xdiff = np.diff(x)
    nd = len(xdiff)
    nobs = nd - maxlag
    ydep = xdiff[maxlag:]
    cols = [x[maxlag:maxlag + nobs]] + [xdiff[maxlag - i:maxlag - i + nobs] for i in range(1, maxlag + 1)]
    full = np.column_stack(cols)
    best = None
    for k in range(1, maxlag + 2):
        coef, resid, rank = _ols(ydep, full[:, :k])
        ssr = float(resid @ resid)
        llf = -nobs / 2 * math.log(2 * math.pi) - nobs / 2 * math.log(ssr / nobs) - nobs / 2
        aic = -2 * llf + 2 * rank
        if best is None or (aic, k) < best:
            best = (aic, k)
    used = best[1] - 1
    n2 = nd - used
    ydep = xdiff[used:]
    cols = [x[used:used + n2]] + [xdiff[used - i:used - i + n2] for i in range(1, used + 1)]
    X = np.column_stack(cols)
    coef, resid, _ = _ols(ydep, X)
    s2 = float(resid @ resid) / (n2 - X.shape[1])
    se = math.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
    return float(coef[0] / se)


@dataclass
class Formation:
    a: float = np.nan
    b: float = np.nan
    mean_e: float = np.nan
    sd_e: float = np.nan
    p: float = np.nan
    h: float = np.nan
    sig: float = np.nan
    ok: bool = False  # computable
    eligible: bool = False


def formation(ly: np.ndarray, lx: np.ndarray) -> Formation:
    f = Formation()
    if not (np.all(np.isfinite(ly)) and np.all(np.isfinite(lx))):
        return f
    X = np.column_stack([np.ones_like(lx), lx])
    coef, e, _ = _ols(ly, X)
    f.a, f.b = float(coef[0]), float(coef[1])
    f.mean_e, f.sd_e = float(e.mean()), float(e.std(ddof=1))
    try:
        t = adf_n_aic(e, 10)
    except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
        return f
    f.p = mackinnonp_c2(t)
    de = np.diff(e)
    cc, _, _ = _ols(de, np.column_stack([np.ones(len(de)), e[:-1]]))
    c = float(cc[1])
    f.h = -math.log(2) / math.log(1 + c) if -1 < c < 0 else np.nan
    f.sig = float(de.std(ddof=1)) * math.sqrt(365)
    f.ok = True
    f.eligible = bool(f.p < 0.05 and 0.25 <= f.b <= 4 and np.isfinite(f.h) and 2 <= f.h <= 30)
    return f


# ---------------------------------------------------------------- data

@dataclass
class Market:
    coins: list
    days: list            # decision days D (dates); CL[i] = ln close at 00:00 UTC of days[i]
    CL: np.ndarray        # (T, N) ln daily close, NaN where missing
    Q: np.ndarray         # (T, N) quote turnover of the candle that closes at D
    h0: int               # ms of hour index 0
    HO: np.ndarray        # (nh, N) hourly open
    HC: np.ndarray        # (nh, N) hourly close
    fund: dict            # coin -> (stamps ms int64 sorted, rates)
    hourly_rows: dict = field(default_factory=dict)
    HCff: np.ndarray = None  # HC forward-filled (last available hourly close at or before each hour)

    def __post_init__(self):
        if self.HCff is None:
            ff = self.HC.copy()
            for j in range(ff.shape[1]):
                col = ff[:, j]
                ok = np.isfinite(col)
                idx = np.where(ok, np.arange(len(col)), -1)
                np.maximum.accumulate(idx, out=idx)
                ff[:, j] = np.where(idx >= 0, col[np.maximum(idx, 0)], np.nan)
            self.HCff = ff

    def di(self, d):
        return (d - self.days[0]).days


def _read_hourly_nine(coin):
    rows = []
    with open(f"{SP}/hourly/{coin}USDT-1h.csv") as f:
        r = csv.reader(f)
        for row in r:
            if not row or not row[0].isdigit():
                continue
            rows.append((int(row[0]), float(row[1]), float(row[4])))
    return rows


def _read_hourly_extra(coin):
    rows = []
    d = f"{SP}/universe/hourly_extra"
    for fn in sorted(os.listdir(d)):
        if not fn.startswith(f"binance-{coin}USDT-1h-"):
            continue
        with open(os.path.join(d, fn)) as f:
            for row in csv.reader(f):
                if not row or not row[0].isdigit():
                    continue
                t = int(row[0])
                if t > 1e14:
                    t //= 1000
                rows.append((t, float(row[1]), float(row[4])))
    return rows


def _read_funding(coins):
    out, seen = {c: {} for c in coins}, set()
    for cache in CACHES:
        for fn in sorted(os.listdir(cache)):
            if not fn.startswith("binance-") or "-fundingRate-" not in fn or fn in seen:
                continue
            coin = fn.split("-")[1][:-4]
            if coin not in out:
                continue
            seen.add(fn)
            with open(os.path.join(cache, fn)) as f:
                for row in csv.reader(f):
                    if not row or not row[0].isdigit():
                        continue
                    t = int(row[0])
                    key = int(round(t / 1000.0))  # dedupe to the second
                    if key not in out[coin]:
                        out[coin][key] = (t, float(row[2]))
    res = {}
    for c in coins:
        v = sorted(out[c].values())
        res[c] = (np.array([a for a, _ in v], dtype=np.int64), np.array([b for _, b in v], dtype=float))
    return res


def load_market(coins, t_end=dt.date(2026, 10, 1)) -> Market:
    P = tdata.load_binance()  # ALL25 daily candles (date = candle open date), audited caches, first file wins
    p = P.sub(coins)
    assert list(p.coins) == list(coins), (p.coins, coins)
    d0 = p.dates[0] + dt.timedelta(days=1)
    T = (min(p.dates[-1] + dt.timedelta(days=1), t_end) - d0).days + 1
    days = [d0 + dt.timedelta(days=i) for i in range(T)]
    CL = np.full((T, len(coins)), np.nan)
    Q = np.full((T, len(coins)), np.nan)
    for t, d in enumerate(p.dates):
        i = (d + dt.timedelta(days=1) - d0).days
        if 0 <= i < T:
            with np.errstate(divide="ignore", invalid="ignore"):
                CL[i] = np.log(p.C[t])
            Q[i] = p.Q[t]
    CL[~np.isfinite(CL)] = np.nan
    h0 = d2ms(dt.date(2019, 12, 1))
    nh = (d2ms(t_end + dt.timedelta(days=2)) - h0) // H
    HO = np.full((nh, len(coins)), np.nan)
    HC = np.full((nh, len(coins)), np.nan)
    rows_n = {}
    for j, c in enumerate(coins):
        rows = _read_hourly_nine(c) if c in NINE else _read_hourly_extra(c)
        rows_n[c] = len(rows)
        for t, o, cl in rows:
            k = (t - h0) // H
            if 0 <= k < nh and (t - h0) % H == 0:
                HO[k, j], HC[k, j] = o, cl
    fund = _read_funding(coins)
    return Market(list(coins), days, CL, Q, h0, HO, HC, fund, rows_n)


# ---------------------------------------------------------------- simulation

@dataclass
class Params:
    window: int = 180
    entry: float = 2.0
    stop: float = 4.0
    target: float = 0.5
    K: int = 4
    vol_target: float = 0.10
    pair_gross: float = 0.5
    book_gross: float = 2.0
    p_enter: float = 0.05
    p_exit: float = 0.20
    max_hold: int = 30
    block_days: int = 3
    cost_bps: float = 7.31


@dataclass
class Trade:
    pair: tuple
    xi: int
    yi: int
    side: int            # +1 long spread (long Y, short X), -1 short spread
    d_entry: dt.date
    z_entry: float
    f: Formation
    t_entry: int = 0
    units: np.ndarray = None   # (uy, ux)
    px_entry: np.ndarray = None
    last_mark: np.ndarray = None
    L: float = 0.0
    d_exit: dt.date = None
    t_exit: int = 0
    reason: str = ""
    px_exit: np.ndarray = None
    pnl_px: float = 0.0
    fund: float = 0.0
    cost: float = 0.0
    fallback: int = 0
    pending_exit: str = ""
    eq_entry: float = 1.0
    N: float = 0.0


class Sim:
    def __init__(self, mk: Market, pairs, params: Params, start: dt.date, end: dt.date, form_cache=None):
        self.mk, self.pairs, self.P, self.start, self.end = mk, pairs, params, start, end
        self.form_cache = {} if form_cache is None else form_cache

    # -- helpers
    def form(self, pair, d):
        key = (pair, d, self.P.window)
        f = self.form_cache.get(key)
        if f is None:
            i = self.mk.di(d)
            w = self.P.window
            if i - w + 1 < 0:
                f = Formation()
            else:
                xi, yi = pair
                f = formation(self.mk.CL[i - w + 1:i + 1, yi], self.mk.CL[i - w + 1:i + 1, xi])
            self.form_cache[key] = f
        return f

    def hidx(self, d):
        return (d2ms(d) - self.mk.h0) // H

    def fill_px(self, d, j):
        """P01[d] for coin j with same-day fallback: returns (price, fill_time_ms, fallback_flag) or (nan, 0, 0)."""
        k = self.hidx(d)
        for o in range(0, 24):
            v = self.mk.HC[k + o, j]
            if np.isfinite(v):
                return float(v), int(self.mk.h0 + (k + o + 1) * H), int(o > 0)
        return np.nan, 0, 0

    def mark_px(self, d, j):
        """Mark at 01:00 UTC of d: the P01 close, forward-filled from the last available hourly close."""
        return float(self.mk.HCff[self.hidx(d), j])

    def stamp_px(self, s, j):
        k = (s - self.mk.h0) // H
        v = self.mk.HO[k, j]
        if np.isfinite(v):
            return float(v)
        return float(self.mk.HCff[k - 1, j])

    def z(self, f: Formation, i, pair):
        xi, yi = pair
        ly, lx = self.mk.CL[i, yi], self.mk.CL[i, xi]
        if not (np.isfinite(ly) and np.isfinite(lx)):
            return np.nan
        return (ly - f.b * lx - f.a - f.mean_e) / f.sd_e

    def select(self, M):
        el = []
        for pair in self.pairs:
            f = self.form(pair, M)
            if f.eligible:
                el.append((f.p, self.pairs.index(pair), pair))
        el.sort()
        cnt, S = {}, []
        for _, _, pair in el:
            if len(S) >= self.P.K:
                break
            xi, yi = pair
            if cnt.get(xi, 0) < 2 and cnt.get(yi, 0) < 2:
                S.append(pair)
                cnt[xi] = cnt.get(xi, 0) + 1
                cnt[yi] = cnt.get(yi, 0) + 1
        return S

    def last_valid_day(self, j):
        ok = np.flatnonzero(np.isfinite(self.mk.CL[:, j]))
        return self.mk.days[ok[-1]] if len(ok) else None

    # -- main loop
    def run(self):
        P, mk = self.P, self.mk
        cost = P.cost_bps / 1e4
        sz = P.vol_target / math.sqrt(P.K)
        eq = 1.0
        open_t, closed = {}, []
        block_until = {}
        S, S_monday = [], None
        rets, dates, gross_l, npos_l = [], [], [], []
        lastday = {j: self.last_valid_day(j) for j in range(len(mk.coins))}
        self.formations_used = []
        d = self.start
        while d <= self.end:
            i = mk.di(d)
            day_pnl = 0.0
            lo_ms, hi_ms = d2ms(d) - DAYMS + H, d2ms(d) + H  # (01:00 D-1, 01:00 D]
            # ---- decisions at the 00:00 UTC close of d
            if d.weekday() == 0:
                S = self.select(d)
                S_monday = d
                self.formations_used.append((d, list(S)))
            exits = []
            for pair, tr in list(open_t.items()):
                xi, yi = pair
                reason = tr.pending_exit
                if not reason:
                    zz = self.z(tr.f, i, pair)
                    if np.isfinite(zz):
                        held = (d - tr.d_entry).days
                        if (tr.side == -1 and zz >= P.stop) or (tr.side == 1 and zz <= -P.stop):
                            reason = "stop"
                        elif (tr.side == -1 and zz <= P.target) or (tr.side == 1 and zz >= -P.target):
                            reason = "target"
                        elif d.weekday() == 0 and not (self.form(pair, d).ok and self.form(pair, d).p <= P.p_exit):
                            reason = "retest"
                        elif held > min(2 * tr.f.h, P.max_hold):
                            reason = "time"
                    else:
                        for j in (xi, yi):
                            if lastday[j] is not None and d > lastday[j]:
                                reason = "delist"
                if d == self.end and not reason:
                    reason = "end"
                if reason:
                    exits.append((pair, tr, reason))
            for pair, tr, reason in exits:
                xi, yi = pair
                pxs, ts, fb = [], [], 0
                for j in (yi, xi):
                    px, t, f_ = self.fill_px(d, j)
                    if not np.isfinite(px) and reason in ("delist", "end"):
                        px, t, f_ = self.mark_px(d, j), d2ms(d) + H, 1
                    pxs.append(px); ts.append(t); fb += f_
                if not all(np.isfinite(pxs)):
                    tr.pending_exit = reason
                    continue
                tr.d_exit, tr.reason, tr.t_exit = d, reason, max(ts)
                tr.px_exit = np.array(pxs)
                tr.fallback += fb
                # funding stamps before the exit fill within this day's interval
                day_pnl += self._funding(tr, lo_ms, hi_ms)
                inc = float((tr.units * (tr.px_exit - tr.last_mark)).sum())
                tr.pnl_px += inc
                c = float(np.abs(tr.units * tr.px_exit).sum()) * cost
                tr.cost += c
                day_pnl += inc - c
                closed.append(tr)
                del open_t[pair]
                if reason == "stop":
                    block_until[pair] = d + dt.timedelta(days=P.block_days)
            exited_today = {pair for pair, tr, reason in exits if tr.d_exit == d}  # VERIFY PATCH: spec line 48
            # entries
            if S_monday is not None and (d - S_monday).days <= 6 and d < self.end:
                gross_open = 0.0
                for pair, tr in open_t.items():
                    xi, yi = pair
                    gross_open += abs(tr.units[0]) * self.mark_px(d, yi) + abs(tr.units[1]) * self.mark_px(d, xi)
                for pair in S:
                    if pair in open_t or pair in exited_today:
                        continue
                    if pair in block_until and d <= block_until[pair]:
                        continue
                    f = self.form(pair, S_monday)
                    zz = self.z(f, i, pair)
                    if not np.isfinite(zz):
                        continue
                    if P.entry <= zz < P.stop:
                        side = -1
                    elif -P.stop < zz <= -P.entry:
                        side = 1
                    else:
                        continue
                    xi, yi = pair
                    N = eq * min(sz / f.sig, P.pair_gross / (1 + f.b))
                    room = P.book_gross * eq - gross_open
                    if N * (1 + f.b) > room:
                        N = room / (1 + f.b)
                    if N <= 0:
                        continue
                    py, ty, fby = self.fill_px(d, yi)
                    px_, tx, fbx = self.fill_px(d, xi)
                    if not (np.isfinite(py) and np.isfinite(px_)):
                        continue
                    tr = Trade(pair, xi, yi, side, d, float(zz), f)
                    tr.units = np.array([side * N / py, -side * f.b * N / px_])
                    tr.px_entry = np.array([py, px_])
                    tr.last_mark = tr.px_entry.copy()
                    tr.t_entry = max(ty, tx)
                    tr.fallback = fby + fbx
                    tr.L = (N + f.b * N) / 2
                    tr.eq_entry = eq
                    tr.N = N
                    c = (N + f.b * N) * cost
                    tr.cost += c
                    day_pnl -= c
                    gross_open += N * (1 + f.b)
                    open_t[pair] = tr
            # ---- marks and funding for positions held over (01:00 D-1, 01:00 D]
            g = 0.0
            for pair, tr in open_t.items():
                xi, yi = pair
                if tr.d_entry == d:
                    m = np.array([self.mark_px(d, yi), self.mark_px(d, xi)])
                    # entry fill at 01:00 d (or later); its first mark comes on d+1
                    g += float(np.abs(tr.units * m).sum())
                    continue
                day_pnl += self._funding(tr, lo_ms, hi_ms)
                m = np.array([self.mark_px(d, yi), self.mark_px(d, xi)])
                if tr.t_entry <= hi_ms:
                    inc = float((tr.units * (m - tr.last_mark)).sum())
                    tr.pnl_px += inc
                    day_pnl += inc
                    tr.last_mark = m
                g += float(np.abs(tr.units * m).sum())
            r = day_pnl / eq
            eq *= 1 + r
            rets.append(r); dates.append(d); gross_l.append(g / eq if eq else 0.0); npos_l.append(len(open_t))
            d += dt.timedelta(days=1)
        self.trades = closed
        self.rets = np.array(rets)
        self.dates = dates
        self.gross = np.array(gross_l)
        self.npos = np.array(npos_l)
        self.final_eq = eq
        return self

    def _funding(self, tr: Trade, lo, hi):
        """Funding on both legs for stamps s in (lo, hi] with t_entry < s < t_exit (t_exit 0 = still open)."""
        tot = 0.0
        a = max(lo, tr.t_entry)
        b = hi if not tr.t_exit else min(hi, tr.t_exit - 1)
        if b <= a:
            return 0.0
        for leg, j in ((0, tr.yi), (1, tr.xi)):
            st, rt = self.mk.fund[self.mk.coins[j]]
            k0 = np.searchsorted(st, a, side="right")
            k1 = np.searchsorted(st, b, side="right")
            for k in range(k0, k1):
                px = self.stamp_px(int(st[k]), j)
                if np.isfinite(px):
                    tot -= tr.units[leg] * px * rt[k]
        tr.fund += tot
        return tot


# ---------------------------------------------------------------- metrics

def trade_table(sim: Sim):
    rows = []
    for t in sim.trades:
        net = t.pnl_px + t.fund - t.cost
        rows.append(dict(pair=(sim.mk.coins[t.xi], sim.mk.coins[t.yi]), side=t.side, d_entry=t.d_entry, d_exit=t.d_exit,
                         reason=t.reason, held=(t.d_exit - t.d_entry).days, z=t.z_entry, b=t.f.b, h=t.f.h, p=t.f.p,
                         L=t.L, gross_bps=1e4 * t.pnl_px / t.L, fund_bps=1e4 * t.fund / t.L, cost_bps=1e4 * t.cost / t.L,
                         net_bps=1e4 * net / t.L, fallback=t.fallback, net_eq=net / t.eq_entry, N_eq=t.N / t.eq_entry))
    return rows


def sharpe(x):
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return float(x.mean() / s * math.sqrt(365)) if len(x) > 2 and s > 0 else 0.0


def cagr(x):
    x = np.asarray(x, float)
    return float(np.prod(1 + x) ** (365 / len(x)) - 1) if len(x) else 0.0


def maxdd(x):
    e = np.cumprod(1 + np.asarray(x, float))
    return float((e / np.maximum.accumulate(e) - 1).min()) if len(e) else 0.0


def week_index(dates, first_monday):
    return np.array([(d - first_monday).days // 7 for d in dates], dtype=int)


def boot_trade_mean(net, wk, n_weeks, n=2000, seed=11):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_weeks, size=(n, n_weeks))
    s = np.bincount(wk, weights=net, minlength=n_weeks)
    c = np.bincount(wk, minlength=n_weeks).astype(float)
    num = np.zeros(n); den = np.zeros(n)
    for b in range(n):
        num[b] = s[idx[b]].sum(); den[b] = c[idx[b]].sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        m = num / den
    ok = np.isfinite(m)
    return float((m[ok] <= 0).mean()), float(np.percentile(m[ok], 2.5)), float(np.percentile(m[ok], 97.5)), int((~ok).sum())


def boot_daily_sharpe(r, wk, n_weeks, n=2000, seed=11):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_weeks, size=(n, n_weeks))
    s1 = np.bincount(wk, weights=r, minlength=n_weeks)
    s2 = np.bincount(wk, weights=r * r, minlength=n_weeks)
    c = np.bincount(wk, minlength=n_weeks).astype(float)
    out = np.zeros(n)
    for b in range(n):
        S1, S2, C = s1[idx[b]].sum(), s2[idx[b]].sum(), c[idx[b]].sum()
        var = (S2 - S1 * S1 / C) / (C - 1)
        out[b] = S1 / C / math.sqrt(var) * math.sqrt(365) if var > 0 else 0.0
    return float((out <= 0).mean())
