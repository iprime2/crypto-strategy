#!/usr/bin/env python3
"""Signal, volatility and sizing building blocks on (T x N) arrays. Every function uses data up to and including row t
for row t (no look-ahead): rolling windows end at t.

baseline_weights() reproduces cex-mm/scripts/trend_backtest.py::target_weights exactly:
  signal = mean of sign(C[t]/C[t-L] - 1) for L in looks, floored at 0 (long-only)
  vol    = sqrt(mean of squared daily log returns over vol_win * 365), floored at 0.05
  w      = signal * (tv / n_valid) / vol, where n_valid = coins with a complete (max(looks), vol_win)+1 day history
  gross cap 2x.
"""
from __future__ import annotations
import numpy as np

EPS = 1e-12


def rolling_valid(C, span):
    """valid[t, j]: the last `span` closes (t-span+1..t) all exist."""
    f = np.isfinite(C).astype(int)
    cs = np.cumsum(f, axis=0)
    cs = np.vstack([np.zeros((1, C.shape[1]), int), cs])
    out = np.zeros(C.shape, bool)
    out[span - 1:] = (cs[span:] - cs[:-span]) == span
    return out


def lag_return(C, L):
    out = np.full(C.shape, np.nan)
    out[L:] = C[L:] / C[:-L] - 1
    return out


def log_returns(C):
    r = np.full(C.shape, np.nan)
    r[1:] = np.log(C[1:] / C[:-1])
    return r


def rolling_mean(x, win):
    """Mean over the trailing `win` rows ending at t (NaN if any NaN in the window)."""
    out = np.full(x.shape, np.nan)
    if len(x) < win:
        return out
    cs = np.cumsum(np.nan_to_num(x), axis=0)
    cs = np.vstack([np.zeros((1, x.shape[1])), cs])
    s = cs[win:] - cs[:-win]
    ok = rolling_valid(x, win)[win - 1:]
    out[win - 1:] = np.where(ok, s / win, np.nan)
    return out


def ewma(x, span):
    """Exponential moving average with pandas-style span (alpha = 2/(span+1)), NaN-aware (NaN inputs are skipped)."""
    a = 2.0 / (span + 1)
    out = np.full(x.shape, np.nan)
    prev = np.full(x.shape[1], np.nan)
    for t in range(len(x)):
        v = x[t]
        has = np.isfinite(v)
        cur = np.where(np.isfinite(prev), prev, v)
        cur = np.where(has, a * v + (1 - a) * cur, prev)
        prev = cur; out[t] = cur
    return out


# ---------------------------------------------------------------- volatility (annualized, daily units)

def vol_cc(C, win=60):
    r = log_returns(C)
    return np.sqrt(rolling_mean(r * r, win) * 365)


def vol_ewma(C, span=32):
    r = log_returns(C)
    return np.sqrt(ewma(r * r, span) * 365)


def vol_parkinson(H, L, win=30):
    x = np.log(H / L) ** 2 / (4 * np.log(2))
    return np.sqrt(rolling_mean(x, win) * 365)


def vol_garman_klass(O, H, L, C, win=30):
    x = 0.5 * np.log(H / L) ** 2 - (2 * np.log(2) - 1) * np.log(C / O) ** 2
    return np.sqrt(np.maximum(rolling_mean(x, win), 0) * 365)


def vol_yang_zhang(O, H, L, C, win=30):
    """Yang & Zhang (2000): overnight + open-to-close + Rogers-Satchell, k = 0.34/(1.34+(n+1)/(n-1))."""
    Cp = np.vstack([np.full((1, C.shape[1]), np.nan), C[:-1]])
    o = np.log(O / Cp); c = np.log(C / O)
    rs = np.log(H / O) * np.log(H / C) + np.log(L / O) * np.log(L / C)
    k = 0.34 / (1.34 + (win + 1) / (win - 1))
    var_o = rolling_mean(o * o, win) - rolling_mean(o, win) ** 2
    var_c = rolling_mean(c * c, win) - rolling_mean(c, win) ** 2
    v = var_o + k * var_c + (1 - k) * rolling_mean(rs, win)
    return np.sqrt(np.maximum(v, 0) * 365 * win / (win - 1))


# ---------------------------------------------------------------- signals in [-1, 1] (long-only callers floor at 0)

def sig_sign_mean(C, looks=(20, 60, 120)):
    s = np.zeros(C.shape)
    for L in looks:
        s += np.sign(lag_return(C, L))
    return s / len(looks)


def sig_continuous(C, vol, looks=(20, 60, 120), cap=2.0):
    """Risk-adjusted momentum: mean over lookbacks of (return_L / (vol * sqrt(L/365))), clipped to ±cap, divided by cap."""
    s = np.zeros(C.shape)
    for L in looks:
        z = lag_return(C, L) / (vol * np.sqrt(L / 365) + EPS)
        s += np.clip(z, -cap, cap) / cap
    return s / len(looks)


def sig_ewmac(C, vol, pairs=((8, 32), (16, 64), (32, 128)), scalars=None, cap=20.0):
    """Carver EWMAC: (EWMA_fast - EWMA_slow) / daily price vol, scaled to an average absolute forecast of 10, capped at ±20,
    averaged over pairs, divided by 20 so the result is in [-1, 1]. Default scalars from pysystemtrade (8/32: 5.3, 16/64: 3.75, 32/128: 2.65)."""
    default = {(2, 8): 10.6, (4, 16): 7.5, (8, 32): 5.3, (16, 64): 3.75, (32, 128): 2.65, (64, 256): 1.87}
    dvol = vol / np.sqrt(365) * C  # price-unit daily vol
    s = np.zeros(C.shape)
    for pr in pairs:
        f = (ewma(C, pr[0]) - ewma(C, pr[1])) / (dvol + EPS)
        f = np.clip(f * (scalars or default)[pr], -cap, cap) / cap
        s += f
    return s / len(pairs)


def sig_breakout(C, win=120):
    """Carver breakout: (C - mid of rolling [min, max]) / (max - min) * 2 in [-1, 1]."""
    out = np.full(C.shape, np.nan)
    for t in range(win - 1, len(C)):
        w = C[t - win + 1:t + 1]
        hi, lo = np.nanmax(w, axis=0), np.nanmin(w, axis=0)
        out[t] = (C[t] - (hi + lo) / 2) / (hi - lo + EPS) * 2
    return out


def sig_tstat(C, looks=(20, 60, 120), cap=2.0):
    """Baltas-Kosowski TREND-style: t-statistic of the mean daily return over L days, clipped and scaled to [-1, 1]."""
    r = log_returns(C)
    s = np.zeros(C.shape)
    for L in looks:
        m = rolling_mean(r, L); v = rolling_mean(r * r, L) - m * m
        t = m / (np.sqrt(np.maximum(v, EPS) / L) + EPS)
        s += np.clip(t, -cap * 2, cap * 2) / (cap * 2)
    return s / len(looks)


# ---------------------------------------------------------------- sizing

def size_per_asset(sig, vol, valid, tv, max_gross=2.0, vol_floor=0.05):
    """Repo sizing: w = sig * (tv / n_valid) / max(vol, floor); gross cap."""
    n = np.maximum(valid.sum(axis=1, keepdims=True), 1)
    w = np.where(valid, sig * (tv / n) / np.maximum(vol, vol_floor), 0.0)
    w = np.nan_to_num(w)
    g = np.abs(w).sum(axis=1, keepdims=True)
    return np.where(g > max_gross, w * max_gross / np.maximum(g, EPS), w)


def size_portfolio_vol(sig, vol, valid, C, tv, cov_win=60, max_gross=2.0, vol_floor=0.05, lev_cap=None):
    """Per-asset raw weights as above (sig/vol), then scale the whole vector so the ex-ante portfolio vol
    (rolling cov_win-day covariance of log returns, annualized) equals tv. lev_cap bounds the scaling multiplier."""
    r = log_returns(C)
    T, N = C.shape
    raw = np.where(valid, sig / np.maximum(vol, vol_floor), 0.0)
    raw = np.nan_to_num(raw)
    W = np.zeros((T, N))
    for t in range(cov_win, T):
        w = raw[t]
        if not np.any(w):
            continue
        R = r[t - cov_win + 1:t + 1]
        ok = np.isfinite(R).all(axis=0) & (w != 0)
        if ok.sum() == 0:
            continue
        Rk = R[:, ok]
        cov = (Rk.T @ Rk) / cov_win * 365  # uncentered, like the repo's vol
        wv = w[ok]
        pv = float(np.sqrt(max(wv @ cov @ wv, EPS)))
        k = tv / pv
        if lev_cap is not None:
            k = min(k, lev_cap)
        W[t, ok] = wv * k
    g = np.abs(W).sum(axis=1, keepdims=True)
    return np.where(g > max_gross, W * max_gross / np.maximum(g, EPS), W)


def baseline_weights(C, looks=(20, 60, 120), vol_win=60, tv=0.40, max_gross=2.0, long_only=True):
    span = max(max(looks), vol_win) + 1
    valid = rolling_valid(C, span)
    sig = sig_sign_mean(C, looks)
    if long_only:
        sig = np.maximum(sig, 0.0)
    vol = vol_cc(C, vol_win)
    return size_per_asset(np.nan_to_num(sig), np.nan_to_num(vol, nan=np.inf), valid, tv, max_gross)


def decide_weekly(dates, weekday=6):
    return np.array([d.weekday() == weekday for d in dates])


# ---------------------------------------------------------------- additions for the phase-1 candidates

def ewma_std(x, span):
    """EWMA standard deviation of x (NaN-aware), pandas span semantics, uncentered."""
    return np.sqrt(ewma(x * x, span))


def price_vol_carver(C, span=35):
    """Carver's sigma_px: EWMA std of daily price CHANGES in price units (span 35 by default)."""
    d = np.full(C.shape, np.nan); d[1:] = C[1:] - C[:-1]
    return ewma_std(d, span)


def sig_ewmac_carver(C, pairs=((8, 32), (16, 64), (32, 128), (64, 256)), span_vol=35, cap=20.0):
    """EWMAC forecasts per Carver: (EWMA_f - EWMA_s) / sigma_px * scalar, capped ±20; averaged, then /20 -> [-1, 1]."""
    scalars = {(2, 8): 10.6, (4, 16): 7.5, (8, 32): 5.3, (16, 64): 3.75, (32, 128): 2.65, (64, 256): 1.87}
    spx = price_vol_carver(C, span_vol)
    s = np.zeros(C.shape)
    for f, sl in pairs:
        raw = (ewma(C, f) - ewma(C, sl)) / (spx + EPS)
        s += np.clip(raw * scalars[(f, sl)], -cap, cap) / cap
    return s / len(pairs)


def sig_ols_tstat(C, looks=(20, 60, 120), cap=2.0, variant="2020"):
    """Baltas-Kosowski TREND: t-statistic of the OLS slope of log price on time over L days.
    variant '2013': +1 if t>2, -1 if t<-2, else 0; '2020' (continuous): clip(t/2, -1, 1)."""
    y = np.log(C)
    s = np.zeros(C.shape)
    for L in looks:
        k = np.arange(L) - (L - 1) / 2.0
        skk = float((k * k).sum())
        out = np.full(C.shape, np.nan)
        for t in range(L - 1, len(C)):
            w = y[t - L + 1:t + 1]
            if not np.isfinite(w).all(axis=0).any():
                continue
            ym = w.mean(axis=0)
            slope = (k[:, None] * (w - ym)).sum(axis=0) / skk
            resid = w - ym - k[:, None] * slope
            se = np.sqrt((resid * resid).sum(axis=0) / max(L - 2, 1) / skk)
            out[t] = slope / (se + EPS)
        if variant == "2013":
            s += np.where(out > 2, 1.0, np.where(out < -2, -1.0, 0.0))
        else:
            s += np.clip(out / 2.0, -1, 1)
    return s / len(looks)


def sig_donchian(C, looks=(10, 20, 60, 120, 250), min_valid=1):
    """Zarattini-Pagani-Barbon channel ensemble: for each L, state=1 from the first close >= max of the prior L closes,
    state=0 from the first close < mid of the prior-L channel ((max+min)/2). Signal = mean of states over the L with history."""
    T, N = C.shape
    states = np.zeros((len(looks), T, N))
    for i, L in enumerate(looks):
        st = np.zeros(N)
        for t in range(L, T):
            w = C[t - L:t]  # prior L closes (t-L .. t-1)
            ok = np.isfinite(w).all(axis=0) & np.isfinite(C[t])
            hi, lo = np.nanmax(w, axis=0), np.nanmin(w, axis=0)
            mid = (hi + lo) / 2
            st = np.where(ok & (C[t] >= hi), 1.0, st)
            st = np.where(ok & (C[t] < mid), 0.0, st)
            st = np.where(ok, st, 0.0)
            states[i, t] = st
    return states.mean(axis=0)


def sig_macd_baz(C, pairs=((8, 24), (16, 48), (32, 96))):
    """Baz et al. (2015): x = (EWMA_S - EWMA_L)/std(P,63); y = x/std(x,252); u = y exp(-y^2/4)/0.89; mean over pairs.
    EWMA half-lives S, L are converted to spans: alpha = 1 - 2^(-1/hl), span = 2/alpha - 1."""
    def span_from_hl(hl):
        a = 1 - 2 ** (-1.0 / hl)
        return 2 / a - 1
    s = np.zeros(C.shape)
    for S_, L_ in pairs:
        x = (ewma(C, span_from_hl(S_)) - ewma(C, span_from_hl(L_))) / (rolling_std(C, 63) + EPS)
        y = x / (rolling_std(x, 252) + EPS)
        s += y * np.exp(-y * y / 4) / 0.89
    return s / len(pairs)


def rolling_std(x, win):
    m = rolling_mean(x, win); m2 = rolling_mean(x * x, win)
    return np.sqrt(np.maximum(m2 - m * m, 0) * win / max(win - 1, 1))


def sig_signcount(C, vol_daily_span=33, looks=(20, 60, 120), cap=3.0):
    """Sepp-Lucic sign-count: S_N = sum sign(r~)/sqrt(N) over N days; signal = mean_N clip(S_N, -cap, cap)/cap."""
    r = log_returns(C)
    rn = r / (ewma_std(r, vol_daily_span) + EPS)
    s = np.zeros(C.shape)
    for N in looks:
        cnt = rolling_mean(np.sign(rn), N) * N / np.sqrt(N)
        s += np.clip(cnt, -cap, cap) / cap
    return s / len(looks)


def sig_sepp_ls(C, long_span=250, short_span=20, vol_span=33, cap=2.0):
    """Sepp-Lucic 'European' LS filter: EWMA_short(r~) - EWMA_long(r~) of vol-normalised returns, variance-preserving
    scaling so the signal is in z-score units, clipped at ±cap and divided by cap."""
    r = log_returns(C)
    rn = r / (ewma_std(r, vol_span) + EPS)
    def var_ewma(span):  # variance of an EWMA of unit-variance noise: a/(2-a)
        a = 2.0 / (span + 1); return a / (2 - a)
    f = ewma(rn, short_span) - ewma(rn, long_span)
    # variance of the difference of two EWMAs of white noise: a1/(2-a1) + a2/(2-a2) - 2*a1*a2/(a1+a2-a1*a2)
    a1, a2 = 2.0 / (short_span + 1), 2.0 / (long_span + 1)
    v = a1 / (2 - a1) + a2 / (2 - a2) - 2 * a1 * a2 / (a1 + a2 - a1 * a2)
    z = f / np.sqrt(v)
    return np.clip(z, -cap, cap) / cap


def vol_max_short_long(C, short=20, long_=60):
    return np.maximum(vol_cc(C, short), vol_cc(C, long_))


def vol_floor_percentile(vol, q=0.05, win=500, min_obs=100):
    """pysystemtrade apply_vol_floor: vol floored at its own trailing q-quantile over win days (after min_obs)."""
    out = vol.copy()
    T = len(vol)
    for t in range(T):
        a = max(0, t - win + 1)
        w = vol[a:t + 1]
        n = np.isfinite(w).sum(axis=0)
        fl = np.where(n >= min_obs, np.nanquantile(np.where(np.isfinite(w), w, np.nan), q, axis=0), 0.0) if (n >= min_obs).any() else np.zeros(vol.shape[1])
        out[t] = np.maximum(vol[t], fl)
    return out


def corr_factor_bk(C, active, win=63):
    """Baltas-Kosowski CF_t = sqrt(N_t / (1 + (N_t-1) rho_bar_t)) with rho_bar the mean pairwise correlation of daily
    log returns over `win` days among the active (nonzero-signal) coins; 1.0 when fewer than 2 active."""
    r = log_returns(C)
    T, N = C.shape
    cf = np.ones(T)
    for t in range(win, T):
        ok = active[t] & np.isfinite(r[t - win + 1:t + 1]).all(axis=0)
        n = int(ok.sum())
        if n < 2:
            continue
        R = r[t - win + 1:t + 1][:, ok]
        R = R - R.mean(axis=0)
        sd = R.std(axis=0) + EPS
        Cm = (R.T @ R) / win / np.outer(sd, sd)
        rho = (Cm.sum() - n) / (n * (n - 1))
        cf[t] = np.sqrt(n / (1 + (n - 1) * max(rho, -1.0 / (n - 1) + 1e-6)))
    return cf


def strategy_vol_multiplier(rets, dates_idx, T, target, win=126, cap=2.0, floor=0.25):
    """Barroso-Santa-Clara: m_t = target / sqrt(365 * mean(r^2 over the last `win` strategy returns ending at t-1)),
    clipped to [floor, cap]. rets are the daily returns of the unscaled strategy aligned to rows dates_idx (the row of
    the day the return accrued). Returns a (T,) multiplier applied to the weights decided at row t."""
    m = np.ones(T)
    r2 = np.zeros(T); has = np.zeros(T, bool)
    r2[dates_idx] = rets * rets; has[dates_idx] = True
    cs = np.cumsum(r2); cn = np.cumsum(has)
    for t in range(T):
        a = t - win  # window of returns accrued on rows t-win+1 .. t (known at the close of t)
        n = cn[t] - (cn[a] if a >= 0 else 0)
        if n < win // 2:
            continue
        s = cs[t] - (cs[a] if a >= 0 else 0.0)
        rv = np.sqrt(s / n * 365)
        m[t] = float(np.clip(target / max(rv, EPS), floor, cap))
    return m


def universe_topn_by_turnover(Q, C, n, win=30, min_hist=180, reset="monthly", dates=None):
    """Ex-ante rolling universe: on each reset day keep the top-n coins by median USD turnover over the past `win`
    days among those with >= min_hist daily closes; the membership holds until the next reset. Returns a (T,N) bool mask."""
    T, N = C.shape
    medQ = np.full((T, N), np.nan)
    for t in range(win - 1, T):
        w = Q[t - win + 1:t + 1]
        medQ[t] = np.nanmedian(np.where(np.isfinite(w), w, np.nan), axis=0)
    hist = np.cumsum(np.isfinite(C), axis=0)
    mask = np.zeros((T, N), bool)
    cur = np.zeros(N, bool)
    for t in range(T):
        is_reset = (t == 0) or (reset == "monthly" and dates[t].month != dates[t - 1].month) or (reset == "weekly" and dates[t].weekday() == 6)
        if is_reset:
            elig = (hist[t] >= min_hist) & np.isfinite(medQ[t])
            score = np.where(elig, medQ[t], -np.inf)
            order = np.argsort(-score)
            cur = np.zeros(N, bool)
            cur[order[:n]] = elig[order[:n]]
        mask[t] = cur
    return mask


# ---------------------------------------------------------------- overlays, universe screens, more vol estimators

def avg_pairwise_corr(C, win=60, members=None):
    """(T,) average pairwise correlation of daily log returns over `win` days among `members` (bool (T,N) mask or None)."""
    r = log_returns(C)
    T, N = C.shape
    out = np.full(T, np.nan)
    for t in range(win, T):
        ok = np.isfinite(r[t - win + 1:t + 1]).all(axis=0)
        if members is not None:
            ok &= members[t]
        n = int(ok.sum())
        if n < 2:
            continue
        R = r[t - win + 1:t + 1][:, ok]
        R = R - R.mean(axis=0)
        sd = R.std(axis=0) + EPS
        Cm = (R.T @ R) / win / np.outer(sd, sd)
        out[t] = (Cm.sum() - n) / (n * (n - 1))
    return out


def ew_index(C, members=None):
    """Equal-weight chain-linked daily total-return index (level) of the coins in `members` (bool (T,N) or None)."""
    r = np.exp(log_returns(C)) - 1
    T, N = C.shape
    lvl = np.ones(T)
    for t in range(1, T):
        ok = np.isfinite(r[t])
        if members is not None:
            ok &= members[t - 1]
        lvl[t] = lvl[t - 1] * (1 + (r[t][ok].mean() if ok.any() else 0.0))
    return lvl


def vol_carver_blend(C, span=35, slow_days=365, w_fast=0.7):
    """pysystemtrade mixed_vol_calc: 0.7 x EWMA-span-35 vol + 0.3 x trailing-365-day mean of that vol."""
    fast = vol_ewma(C, span)
    slow = np.full(fast.shape, np.nan)
    cs = np.cumsum(np.nan_to_num(fast), axis=0); cn = np.cumsum(np.isfinite(fast), axis=0)
    for t in range(len(fast)):
        a = max(-1, t - slow_days)
        n = cn[t] - (cn[a] if a >= 0 else 0)
        s = cs[t] - (cs[a] if a >= 0 else 0.0)
        slow[t] = np.where(n > 20, s / np.maximum(n, 1), fast[t])
    return w_fast * fast + (1 - w_fast) * slow


def rolling_mean_rows(W, k):
    """Trailing k-row mean of a weight path (tranching: trade toward the 7-day mean of daily targets)."""
    out = np.zeros_like(W)
    cs = np.cumsum(W, axis=0)
    for t in range(len(W)):
        a = t - k
        out[t] = (cs[t] - (cs[a] if a >= 0 else 0.0)) / min(t + 1, k)
    return out


def funding_annualized(F, win=30):
    """Trailing `win`-day mean daily funding fraction x 365 (per coin), NaN before `win` days."""
    return rolling_mean(np.where(np.isfinite(F), F, 0.0), win) * 365


def universe_topn_screened(Q, C, F, n, win=30, min_hist=180, reset="monthly", dates=None, entry_usd=None, exit_usd=None,
                           fund_cap=None, fund_win=90, exclude=()):
    """Top-n by median turnover with optional listing-age floor, liquidity hysteresis (entry/exit $ thresholds on the
    30-day median), a funding-cost screen (trailing mean annualized funding <= fund_cap) and excluded symbols (by index)."""
    T, N = C.shape
    medQ = np.full((T, N), np.nan)
    for t in range(win - 1, T):
        w = Q[t - win + 1:t + 1]
        medQ[t] = np.nanmedian(np.where(np.isfinite(w), w, np.nan), axis=0)
    hist = np.cumsum(np.isfinite(C), axis=0)
    fa = funding_annualized(F, fund_win) if fund_cap is not None else None
    mask = np.zeros((T, N), bool); cur = np.zeros(N, bool)
    ex = np.zeros(N, bool); ex[list(exclude)] = True
    for t in range(T):
        is_reset = (t == 0) or (reset == "monthly" and dates[t].month != dates[t - 1].month) or (reset == "yearly" and dates[t].year != dates[t - 1].year) or (reset == "weekly" and dates[t].weekday() == 6)
        if is_reset:
            elig = (hist[t] >= min_hist) & np.isfinite(medQ[t]) & ~ex
            if entry_usd is not None:
                elig &= (medQ[t] >= entry_usd) | cur
            if fund_cap is not None:
                elig &= ~(fa[t] > fund_cap)
            score = np.where(elig, medQ[t], -np.inf)
            order = np.argsort(-score)
            cur = np.zeros(N, bool); cur[order[:n]] = elig[order[:n]]
        if exit_usd is not None:
            cur = cur & ~(np.isfinite(medQ[t]) & (medQ[t] < exit_usd))
        mask[t] = cur
    return mask
