#!/usr/bin/env python3
"""Sizing family of research2/phase1_plan.md (frozen 2026-10-21, section 6.2) plus amendment A-2026-10-21 A7:
SZ-3, SZ-6b, SZ-13, SZ-17 and their neighbors. Every parameter is the plan's; nothing here was tuned on results.

Cells (ids as registered; neighbors are '<id>__<label>'):
  SZ-3   Carver mixed vol 0.7 fast + 0.3 long-run          neighbors SZ-3__wfast06, SZ-3__wfast08
  SZ-6b  Baltas-Kosowski correlation factor, time variation  neighbors SZ-6b__ref060, SZ-6b__ref080
  SZ-13  minimum-contract eligibility + risk re-allocation   neighbors SZ-13__thr2_exit16, SZ-13__exit09
  SZ-17  hourly realized-variance vol, EWMA COM 60 (A7)       neighbors SZ-17__COM30, SZ-17__COM90

Common to all cells (the baseline's pieces, unchanged): signal = max(mean_L sign(P_t/P_{t-L} - 1), 0), L in (20, 60, 120);
validity / N = coins with 121 consecutive closes at row t; w_i = sig_i (TV/N)/max(vol_i, 0.05); gross cap (2x daily, 1x weekly);
band and cadence from the harness. Row t uses rows <= t only (checked by the truncation test in __main__).

Interpretations (rules the plan leaves open; each picks the reading closest to the cited source):

SZ-3
  I-3.1 "EWMA span-35 std of daily log returns (min 10 obs)" is implemented as pysystemtrade's simple_ewvol_calc, i.e. pandas
        `ewm(span=35, adjust=True, min_periods=10).std()` (centred, bias-corrected) on daily log returns, because the plan cites the
        pysystemtrade defaults and "min 10 obs" is that function's min_periods. (The verifier's diag_sizing2.py used an uncentred
        recursion; the difference is a mean^2/var term of ~0.3 % of the variance.)
  I-3.2 sigma_slow = pandas `rolling(365, min_periods=120).mean()` of sigma_fast (simple mean of the finite sigma_fast values in the
        trailing 365 rows ending at t); where fewer than 120 finite values exist, sigma_slow = sigma_fast. Blend in vol units
        (w_fast sigma_fast + (1 - w_fast) sigma_slow), times sqrt(365), floor 0.05 in the sizing, as written.
  I-3.3 Neighbors change w_fast only (0.6 -> 0.6/0.4, 0.8 -> 0.8/0.2); span, 365 d and the 120-obs rule stay.

SZ-6b
  I-6.1 The coin set on row t is {valid coins with sig_i > 0}; if that set has fewer than 3 coins it is all valid coins (the plan's
        "all N"). N_t = size of the set used. Each pair's correlation is the Pearson correlation of the 60 daily log returns ending at
        t (np.corrcoef), floored at 0 pair by pair, then averaged over the N_t(N_t - 1)/2 pairs. N_t = 1 gives CF = CF_ref = 1
        (ratio 1); N_t = 0 (warm-up) gives no ratio, which the EWMA skips.
  I-6.2 m_t = EWMA span 20 (alpha = 2/21, rules.ewma: recursive, seeded with the first ratio, NaN rows skipped) of CF_t/CF_ref,t.
  I-6.3 Order: uncapped baseline weights x m_t, THEN the unchanged gross cap ("TV and cap unchanged" read as: the cap still binds the
        final weights). Matched-vol judgement is the harness's re-run.

SZ-13 (custom_sim; the simulator's whole-contract loop is reproduced verbatim with equity-dependent weights; equivalence to
sim.simulate for a static W is asserted in __main__)
  I-13.1 Unrounded lines (capital None): no contract constraint exists, every full_i is infinite, every coin is eligible and the
        cell IS the baseline (Delta = 0 by construction); the cell's content is on the whole-contract lines, judged against the
        harness's rounded baseline at the same capital (orders/yr) and against the unrounded baseline line (realized vol, Sharpe).
  I-13.2 full_i = (TV/N_t)/max(CC60 vol_i, 0.05) x E_t/(cv_i P_i), with N_t = valid coins at the evaluation row, E_t = running
        equity at the close of t before that row's trade (the equity the simulator sizes with), P_i = close of t, cv_i = data.CVALS
        (1.0 for coins without a Delta contract, as in sim.py). Invalid coins have full_i = 0.
  I-13.3 Evaluation rows: the first decision row the book processes (its first decision day, i.e. the first decision day of its
        first, possibly partial, month) and then the first decision row of every later calendar month (month of the row's date;
        weekly book: the first Sunday decision row of the month); there every valid coin is re-tested with hysteresis (an
        ineligible coin enters iff full_i >= threshold, an eligible coin stays iff full_i >= exit) and between evaluations the set
        is frozen. A coin that enters the baseline universe between evaluations (reaches 121 consecutive closes, e.g. DOGE in
        2020-11 or XRP/LTC after their 2022 data gap) gets its entry test (full_i >= threshold) on its first valid decision row,
        then joins the monthly cycle; a coin that drops out of validity loses its state. Reason: the plan states the rule is "a
        no-op at $5,000 by construction"; making a newly valid coin wait for the next month would break that (it shifted the
        A-daily $5,000 line by +0.014 Sharpe in a check of the alternative reading) and Carver's minimum-capital test is applied
        when an instrument is added.
  I-13.4 N_eff,t = coins eligible (latest evaluation) AND valid on row t; w_i = sig_i (TV/N_eff)/max(vol_i, 0.05) on them, 0
        elsewhere, gross cap; then the simulator's round-nearest contracts and the cadence band, exactly as the rounded baseline.
  I-13.5 B is not applicable (plan): on B there are no capital lines in the harness, so B's rows equal the baseline.

SZ-17 (A7)
  I-17.1 RV_d on row t (date d) = sum of the squared hourly log returns of the 24 bars opened on day d; the first bar's return is
        taken from the same source's 23:00 bar of day d-1, or from the panel's daily close of d-1 when that bar is missing or the
        source changes at d (Delta's first hourly day 2025-01-01). Binance 23:00 closes equal the Binance daily closes on every day
        of panel A's window and Delta's equal Delta's daily closes on all 650 days from 2025-01-01 (checked), so RV_d spans exactly
        the interval of the daily return r_t. Missing bars inside a day: returns between consecutive available closes (forward-fill),
        and a missing 23:00 bar on the panel's own venue is replaced by the daily close. RV is defined only where r_t is finite.
  I-17.2 A day with a finite daily return but no hourly bar at all would use RV_d = r_t^2 (the 24-hour-sampled member of the same
        estimator) so the recursion runs on the same rows as SZ-1. This never fires on A or C: the only whole-day hourly gaps
        (XRP and LTC, 2022-02-26..28 and 2022-04-01..02) are missing from the daily panel too, so r_t is NaN there and both SZ-1 and
        SZ-17 skip the update (and the baseline's 121-close validity drops both coins for 121 days, as it does in every cell).
  I-17.3 Sources: panel A (Binance) -> Binance 1 h perp closes (hourly/<SYM>USDT-1h.csv). Panel C (Delta; detected by O = H = L = C and
        no volume) -> Delta 1 h (research2/delta_data/hourly_<SYM>USD.json) for days >= 2025-01-01, Binance 1 h before.
  I-17.4 "rest as SZ-1": the seeded recursion is variants_p1.vol_ewma_com's code with r^2 replaced by RV (seed = mean of the first
        COM values; COM 30 / 90 neighbors seed with 30 / 90 values, as SZ-1's COM45/COM90 do). Asserted identical to vol_ewma_com
        when RV is replaced by r^2.
  I-17.5 B "falls back to A's nine, reported as A/C only": on a panel holding coins outside the nine the cell trades only the
        nine-coin subset present (B has no DOGE, so 8 coins) and sets base_coins to that subset, so the B row compares like with
        like on that subset and is NOT a B-panel result; the decision for SZ-17 uses A and C only. (Binance 1 h files for all 16
        other B coins exist in universe/hourly_extra; they are not used because A7 fixes the fallback.)

Deviations forced: none in the rules. SZ-13 reproduces sim.simulate's loop in this module (custom_sim) because eligibility needs
the running equity, which the simulator does not expose.
"""
from __future__ import annotations
import csv, datetime as dt, json, os, warnings
import numpy as np
import pandas as pd
import rules, sim, data
from registry import variant

SPAN = 121
NINE = data.NINE
HOURLY_BIN = f"{data.SP}/hourly"
HOURLY_DELTA = f"{data.SP}/research2/delta_data"
DELTA_HOURLY_FROM = dt.date(2025, 1, 1)


def _valid(C):
    return rules.rolling_valid(C, SPAN)


def _sign_sig(C):
    return np.maximum(np.nan_to_num(rules.sig_sign_mean(C)), 0.0)


def _size(sig, vol, C, cad):
    return rules.size_per_asset(sig, np.nan_to_num(vol, nan=np.inf), _valid(C), cad["tv"], cad["max_gross"])


def _cap(W, max_gross):
    g = np.abs(W).sum(axis=1, keepdims=True)
    return np.where(g > max_gross, W * max_gross / np.maximum(g, rules.EPS), W)


def _pkey(p):
    """Cache key for quantities that depend only on the panel's closes (the A6 stress panel shares p.C)."""
    with np.errstate(invalid="ignore"):
        cs = float(np.nansum(p.C))
    return (tuple(p.coins), p.dates[0], p.dates[-1], len(p.dates), round(cs, 6), _is_delta(p))


def _is_delta(p):
    return bool(np.all(np.isnan(p.V)) and np.array_equal(p.O, p.C, equal_nan=True) and np.array_equal(p.H, p.C, equal_nan=True))


# ================================================================= SZ-3 Carver mixed vol

def vol_mixed_carver(C, w_fast=0.7, span=35, min_obs=10, slow_days=365, slow_min=120):
    """sqrt(365) x (w_fast sigma_fast + (1 - w_fast) sigma_slow); sigma_fast = pandas ewm(span, adjust=True, min_periods).std() of
    daily log returns; sigma_slow = trailing slow_days simple mean of sigma_fast (>= slow_min obs, else sigma_fast)."""
    r = rules.log_returns(C)
    fast = pd.DataFrame(r).ewm(span=span, adjust=True, min_periods=min_obs).std().to_numpy()
    slow = pd.DataFrame(fast).rolling(slow_days, min_periods=slow_min).mean().to_numpy()
    slow = np.where(np.isfinite(slow), slow, fast)
    v = np.sqrt(365.0) * (w_fast * fast + (1.0 - w_fast) * slow)
    return np.where(np.isfinite(C), v, np.nan)


def _sz3(p, cad, w_fast):
    return _size(_sign_sig(p.C), vol_mixed_carver(p.C, w_fast), p.C, cad), {}


@variant("SZ-3")
def sz3(p, cad):
    return _sz3(p, cad, 0.7)


@variant("SZ-3__wfast06")
def sz3_06(p, cad):
    return _sz3(p, cad, 0.6)


@variant("SZ-3__wfast08")
def sz3_08(p, cad):
    return _sz3(p, cad, 0.8)


# ================================================================= SZ-6b Baltas-Kosowski correlation factor (time variation)

_CF_CACHE = {}


def corr_ratio_bk(C, ref, win=60, span=20):
    """Returns (m, ratio, rho_bar, n_set): m = EWMA_span(CF_t / CF_ref,t), CF = sqrt(N/(1 + (N-1) rho_bar)), rho_bar = mean of the
    pairwise 60-day Pearson correlations (each floored at 0) among valid coins with sig > 0 (all valid coins if fewer than 3)."""
    valid = _valid(C); sig = _sign_sig(C)
    r = rules.log_returns(C)
    T, N = C.shape
    ratio = np.full(T, np.nan); rho_bar = np.full(T, np.nan); n_set = np.zeros(T, int)
    for t in range(win, T):
        R = r[t - win + 1:t + 1]
        ok = valid[t] & np.isfinite(R).all(axis=0)
        act = ok & (sig[t] > 0)
        S = act if act.sum() >= 3 else ok
        n = int(S.sum()); n_set[t] = n
        if n == 0:
            continue
        if n == 1:
            ratio[t] = 1.0; rho_bar[t] = np.nan
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            cm = np.corrcoef(R[:, S], rowvar=False)
        iu = np.triu_indices(n, 1)
        rho = float(np.mean(np.maximum(np.nan_to_num(cm[iu], nan=0.0), 0.0)))
        rho_bar[t] = rho
        cf = np.sqrt(n / (1.0 + (n - 1) * rho)); cf_ref = np.sqrt(n / (1.0 + (n - 1) * ref))
        ratio[t] = cf / cf_ref
    m = rules.ewma(ratio[:, None], span)[:, 0]
    return m, ratio, rho_bar, n_set


def _sz6b(p, cad, ref):
    key = (_pkey(p), ref)
    if key not in _CF_CACHE:
        _CF_CACHE[key] = corr_ratio_bk(p.C, ref)
    m = _CF_CACHE[key][0]
    vol = np.nan_to_num(rules.vol_cc(p.C, 60), nan=np.inf)
    W0 = rules.size_per_asset(_sign_sig(p.C), vol, _valid(p.C), cad["tv"], max_gross=1e18)  # uncapped; cap after m_t (I-6.3)
    W = W0 * np.nan_to_num(m, nan=1.0)[:, None]
    return _cap(W, cad["max_gross"]), {}


@variant("SZ-6b")
def sz6b(p, cad):
    return _sz6b(p, cad, 0.70)


@variant("SZ-6b__ref060")
def sz6b_060(p, cad):
    return _sz6b(p, cad, 0.60)


@variant("SZ-6b__ref080")
def sz6b_080(p, cad):
    return _sz6b(p, cad, 0.80)


# ================================================================= SZ-13 minimum-contract eligibility (custom whole-contract loop)

def simulate_hooked(p, wfn, *, decide=None, band=0.0, capital=None, cost_bps=sim.COST_BPS, max_gross=None, start=None, end=None,
                    lenient_delist=True, buffer=None, buffer_abs=None):
    """sim.simulate's loop, line for line, except that the target weight row is wfn(t, eq) (called on decision rows only, with the
    equity at the close of t before that row's trade). Returns the same keys as sim.simulate."""
    if buffer is not None or buffer_abs is not None:
        raise ValueError("simulate_hooked: buffers are not used by the sizing cells")
    T, N = p.C.shape
    C = p.C
    valid_next = np.isfinite(C)
    cost = cost_bps / 1e4
    eq = float(capital or 1.0)
    units = np.zeros(N)
    rets, dates, grosses, traded_l, fees, fpaid, ntr = [], [], [], [], 0.0, 0.0, 0
    coin_pnl, cost_frac, fund_frac, rgain, rloss = [], [], [], [], []
    avg_cost = np.zeros(N)
    cv = np.array([data.CVALS.get(c, 1.0) for c in p.coins])
    for t in range(T - 1):
        nxt = p.dates[t + 1]
        if (start and nxt < start) or (end and nxt > end):
            continue
        px = C[t]
        if decide is None or decide[t]:
            w = np.array(wfn(t, eq), dtype=float).copy()
            w[~np.isfinite(w)] = 0.0
            if max_gross is not None:
                g = np.abs(w).sum()
                if g > max_gross:
                    w *= max_gross / g
            u = np.where(np.isfinite(px), w * eq / np.where(np.isfinite(px), px, 1.0), 0.0)
            tgt = u
            if capital:
                tgt = np.round(u / cv) * cv
            if band:
                keep = (tgt != 0) & (np.abs(tgt - units) < band * np.abs(tgt))
                tgt = np.where(keep, units, tgt)
            new = tgt
        else:
            new = units.copy()
        new = np.where(valid_next[t + 1] & np.isfinite(px), new, 0.0)
        d_units = new - units
        pxs = np.where(np.isfinite(px), px, 0.0)
        traded = float(np.abs(d_units * pxs).sum())
        ntr += int((np.abs(d_units) > 1e-15).sum())
        reduce = np.where((np.abs(new) < np.abs(units)) & (units * new >= 0), units - new, np.where(units * new < 0, units, 0.0))
        realized = reduce * (pxs - avg_cost)
        rgain.append(float(np.where(realized > 0, realized, 0.0).sum()) / eq); rloss.append(float(np.where(realized < 0, realized, 0.0).sum()) / eq)
        add = np.where((np.abs(new) > np.abs(units)) & (units * new >= 0), new - units, np.where(units * new < 0, new, 0.0))
        base_u = np.where(units * new < 0, 0.0, np.where(np.abs(new) > np.abs(units), units, new))
        with np.errstate(invalid='ignore', divide='ignore'):
            avg_cost = np.where(np.abs(add) > 1e-15, (avg_cost * np.abs(base_u) + pxs * np.abs(add)) / np.maximum(np.abs(base_u) + np.abs(add), 1e-15), avg_cost)
        avg_cost = np.where(np.abs(new) < 1e-15, 0.0, avg_cost)
        cpnl = np.nan_to_num(new * (C[t + 1] - px)) - np.nan_to_num(new * pxs * p.F[t + 1])
        coin_pnl.append(cpnl / eq); cost_frac.append(traded * cost / eq); fund_frac.append(float(np.nansum(new * pxs * p.F[t + 1])) / eq)
        pnl = float(np.nansum(new * (C[t + 1] - px)))
        fpay = float(np.nansum(new * pxs * p.F[t + 1]))
        r = (pnl - fpay - traded * cost) / eq
        fees += traded * cost / eq
        fpaid += fpay / eq
        grosses.append(float(np.abs(new * pxs).sum()) / eq)
        traded_l.append(traded / eq)
        eq *= 1 + r
        rets.append(r); dates.append(nxt)
        units = new
    return dict(rets=np.array(rets), dates=dates, gross=np.array(grosses), traded=np.array(traded_l), fees=fees, funding=fpaid, trades=ntr, orders=ntr, final=eq,
                coin_pnl=np.array(coin_pnl), cost_frac=np.array(cost_frac), fund_frac=np.array(fund_frac), realized_gain=np.array(rgain), realized_loss=np.array(rloss))


def _sz13_custom(cad, thr, exit_thr, log=None):
    """custom_sim for SZ-13: unrounded -> the baseline (I-13.1); whole contracts -> equity-aware monthly eligibility with hysteresis."""
    tv, mg = cad["tv"], cad["max_gross"]

    def custom(pp, W, kw):
        if not kw.get("capital"):
            return sim.simulate(pp, W, **kw)
        C = pp.C
        valid = _valid(C); sig = _sign_sig(C)
        vol = np.maximum(np.nan_to_num(rules.vol_cc(C, 60), nan=np.inf), 0.05)
        cv = np.array([data.CVALS.get(c, 1.0) for c in pp.coins])
        nval = valid.sum(axis=1)
        NC = C.shape[1]
        st = {"elig": np.zeros(NC, bool), "seen": np.zeros(NC, bool), "ym": None}

        def wfn(t, eq):
            d = pp.dates[t]
            v = valid[t]
            st["elig"] &= v; st["seen"] &= v  # a coin that left the universe loses its state
            monthly = (d.year, d.month) != st["ym"]  # first decision row of this month that the book processes (I-13.3)
            fresh = v & ~st["seen"]  # newly valid coins: entry test now
            if monthly or fresh.any():
                n = max(int(nval[t]), 1)
                with np.errstate(invalid="ignore", divide="ignore"):
                    full = (tv / n) / vol[t] * eq / (cv * C[t])
                full = np.where(v & np.isfinite(full), full, 0.0)
                e = st["elig"]
                if monthly:
                    st["elig"] = v & np.where(e, full >= exit_thr, full >= thr)
                    st["seen"] = v.copy(); st["ym"] = (d.year, d.month)
                else:
                    st["elig"] = e | (fresh & (full >= thr))
                    st["seen"] = st["seen"] | fresh
                if log is not None:
                    log.append((d, float(eq), int(n), [c for c, x in zip(pp.coins, st["elig"]) if x], dict(zip(pp.coins, np.round(full, 2))), bool(monthly)))
            e = st["elig"] & v
            neff = int(e.sum())
            if neff == 0:
                return np.zeros(C.shape[1])
            w = np.where(e, sig[t] * (tv / neff) / vol[t], 0.0)
            g = np.abs(w).sum()
            return w * mg / g if g > mg else w

        return simulate_hooked(pp, wfn, **kw)
    return custom


def _sz13(p, cad, thr=1.0, exit_thr=0.8):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"custom_sim": _sz13_custom(cad, thr, exit_thr)}


@variant("SZ-13")
def sz13(p, cad):
    return _sz13(p, cad, 1.0, 0.8)


@variant("SZ-13__thr2_exit16")
def sz13_thr2(p, cad):
    return _sz13(p, cad, 2.0, 1.6)


@variant("SZ-13__exit09")
def sz13_exit09(p, cad):
    return _sz13(p, cad, 1.0, 0.9)


# ================================================================= SZ-17 hourly realized-variance vol (A7)

_HOURLY = {}
_RV_CACHE = {}


def _hourly_binance(coin):
    """{day_ordinal: np.array(24) of closes by hour of open}, from hourly/<SYM>USDT-1h.csv (timestamps > 1e14 are microseconds)."""
    key = ("bin", coin)
    if key not in _HOURLY:
        path = f"{HOURLY_BIN}/{coin}USDT-1h.csv"
        out = {}
        if os.path.exists(path):
            with open(path) as f:
                for row in csv.reader(f):
                    if not row or not row[0].isdigit():
                        continue
                    ts = int(row[0]); sec = ts // 1_000_000 if ts > 1e14 else ts // 1000
                    day, hr = divmod(sec, 86400)
                    out.setdefault(day, np.full(24, np.nan))[hr // 3600] = float(row[4])
        _HOURLY[key] = out
    return _HOURLY[key]


def _hourly_delta(coin):
    key = ("delta", coin)
    if key not in _HOURLY:
        path = f"{HOURLY_DELTA}/hourly_{coin}USD.json"
        out = {}
        if os.path.exists(path):
            for x in json.load(open(path)):
                day, hr = divmod(int(x["time"]), 86400)
                out.setdefault(day, np.full(24, np.nan))[hr // 3600] = float(x["close"])
        _HOURLY[key] = out
    return _HOURLY[key]


_EPOCH = dt.date(1970, 1, 1)


def rv_daily(p):
    """(T, N) RV_d per I-17.1..I-17.3; NaN where the daily log return is NaN. Returns (RV, info)."""
    key = _pkey(p)
    if key in _RV_CACHE:
        return _RV_CACHE[key]
    C = p.C; T, N = C.shape
    is_delta = _is_delta(p)
    days = np.array([(d - _EPOCH).days for d in p.dates])
    src = np.array([1 if (is_delta and d >= DELTA_HOURLY_FROM) else 0 for d in p.dates])  # 1 = Delta 1 h, 0 = Binance 1 h
    venue_src = 1 if is_delta else 0
    H = np.full((T, N, 24), np.nan)
    for j, c in enumerate(p.coins):
        hb, hd = _hourly_binance(c), (_hourly_delta(c) if is_delta else {})
        for t in range(T):
            h = (hd if src[t] == 1 else hb).get(int(days[t]))
            if h is not None:
                H[t, j] = h
    r = rules.log_returns(C)
    has_any = np.isfinite(H).any(axis=2)
    X = np.full((T, N, 25), np.nan)
    X[:, :, 1:] = H
    # last bar missing on the panel's own venue -> the daily close (they are equal where both exist)
    own = (src == venue_src)[:, None]
    X[:, :, 24] = np.where(np.isnan(X[:, :, 24]) & own & has_any, C, X[:, :, 24])
    # anchor: same-source 23:00 bar of d-1, else the panel's daily close of d-1
    prev23 = np.full((T, N), np.nan); prev23[1:] = H[:-1, :, 23]
    same = np.zeros(T, bool); same[1:] = src[1:] == src[:-1]
    Cprev = np.full((T, N), np.nan); Cprev[1:] = C[:-1]
    X[:, :, 0] = np.where(same[:, None] & np.isfinite(prev23), prev23, Cprev)
    for k in range(1, 25):  # forward-fill gaps inside the day: returns between consecutive available closes
        X[:, :, k] = np.where(np.isfinite(X[:, :, k]), X[:, :, k], X[:, :, k - 1])
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.diff(np.log(X), axis=2)
    rv = np.nansum(lr * lr, axis=2)
    rv = np.where(has_any & np.isfinite(X[:, :, 0]), rv, r * r)  # I-17.2: no bar that day -> r_t^2
    rv = np.where(np.isfinite(r), rv, np.nan)
    info = dict(is_delta=is_delta, fallback_days={c: int((np.isfinite(r[:, j]) & ~has_any[:, j]).sum()) for j, c in enumerate(p.coins)})
    _RV_CACHE[key] = (rv, info)
    return rv, info


def vol_ewma_com_x2(x2, com=60):
    """variants_p1.vol_ewma_com with the squared daily return replaced by an arbitrary daily variance input x2 (I-17.4)."""
    T, N = x2.shape
    out = np.full((T, N), np.nan)
    lam = com / (com + 1.0)
    s = np.full(N, np.nan); seeded = np.zeros(N, bool); buf = []
    for t in range(T):
        x = x2[t]
        ok = np.isfinite(x)
        if not seeded.all():
            buf.append(x)
            if len(buf) >= com:
                arr = np.array(buf[-com:])
                cnt = np.isfinite(arr).sum(axis=0)
                with warnings.catch_warnings():  # all-NaN columns (coins not yet listed) -> NaN, as in vol_ewma_com
                    warnings.simplefilter("ignore", RuntimeWarning)
                    m = np.nanmean(np.where(np.isfinite(arr), arr, np.nan), axis=0)
                newly = (~seeded) & (cnt >= com)
                s = np.where(newly, m, s); seeded |= newly
        upd = seeded & ok
        s = np.where(upd, lam * s + (1 - lam) * x, s)
        out[t] = np.where(seeded, np.sqrt(np.maximum(s, 0) * 365), np.nan)
    return out


def _sz17_core(p, cad, com):
    rv, _ = rv_daily(p)
    return _size(_sign_sig(p.C), vol_ewma_com_x2(rv, com), p.C, cad)


def _sz17(p, cad, com):
    if all(c in NINE for c in p.coins):
        return _sz17_core(p, cad, com), {}
    base = [c for c in p.coins if c in NINE]  # I-17.5: B falls back to the nine-coin subset present
    W = np.zeros(p.C.shape)
    if base:
        q = p.sub(base)
        Wq = _sz17_core(q, cad, com)
        for k, c in enumerate(base):
            W[:, p.ci[c]] = Wq[:, k]
    return W, {"base_coins": base}


@variant("SZ-17")
def sz17(p, cad):
    return _sz17(p, cad, 60)


@variant("SZ-17__COM30")
def sz17_30(p, cad):
    return _sz17(p, cad, 30)


@variant("SZ-17__COM90")
def sz17_90(p, cad):
    return _sz17(p, cad, 90)


# ================================================================= self-checks (python3 variants_sizing.py)

if __name__ == "__main__":
    import time
    from variants_p1 import vol_ewma_com
    t0 = time.time()
    P25 = data.load_binance(); A = P25.sub(NINE); Cp = data.load_delta().sub(NINE); B = P25.sub(data.EXANTE24)
    D = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)
    Wk = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)
    A0, A1, C0, C1 = dt.date(2020, 5, 1), dt.date(2026, 9, 30), dt.date(2024, 8, 10), dt.date(2026, 10, 12)

    # 1. SZ-17's recursion equals SZ-1's when fed r^2
    r = rules.log_returns(A.C)
    v1, v2 = vol_ewma_com(A.C, 60), vol_ewma_com_x2(r * r, 60)
    assert np.allclose(np.nan_to_num(v1, nan=-1), np.nan_to_num(v2, nan=-1), rtol=0, atol=1e-14), "vol_ewma_com_x2 != vol_ewma_com"
    print("ok 1: vol_ewma_com_x2(r^2) == variants_p1.vol_ewma_com")

    # 2. hooked simulator == sim.simulate for a static W (daily/weekly, A/C, rounded and unrounded)
    for pan, a, b in ((A, A0, A1), (Cp, C0, C1)):
        for cad in (D, Wk):
            Wb = rules.baseline_weights(pan.C, tv=cad["tv"], max_gross=cad["max_gross"])
            dec = rules.decide_weekly(pan.dates, 6) if cad["weekly"] else None
            for cap in (None, 1000.0):
                x = sim.simulate(pan, Wb, decide=dec, band=cad["band"], start=a, end=b, capital=cap)
                y = simulate_hooked(pan, lambda t, eq: Wb[t], decide=dec, band=cad["band"], start=a, end=b, capital=cap)
                for k in x:
                    if isinstance(x[k], np.ndarray):
                        assert np.array_equal(x[k], y[k]), (k, cad["name"], cap)
                    else:
                        assert x[k] == y[k], (k, cad["name"], cap)
    print("ok 2: simulate_hooked == sim.simulate (A/C x daily/weekly x unrounded/$1,000)")

    # 3. no look-ahead: weights on rows < t0 are unchanged when the panel is truncated at t0
    def trunc(pan, n):
        return data.Panel(pan.dates[:n], pan.coins, pan.O[:n], pan.H[:n], pan.L[:n], pan.C[:n], pan.V[:n], pan.F[:n], pan.Q[:n])
    from registry import VARIANTS
    for pan in (A, Cp):
        n = len(pan.dates) - 200
        for vid in ("SZ-3", "SZ-6b", "SZ-17", "SZ-17__COM30"):
            Wf = VARIANTS[vid](pan, D)[0][:n]; Wt = VARIANTS[vid](trunc(pan, n), D)[0]
            assert np.allclose(Wf, Wt, rtol=0, atol=1e-12), (vid, "look-ahead")
    print("ok 3: no look-ahead (truncation test) for SZ-3, SZ-6b, SZ-17")

    # 4. RV sanity: level vs r^2 and fallback days
    for name, pan in (("A", A), ("C", Cp)):
        rv, info = rv_daily(pan)
        r = rules.log_returns(pan.C)
        m = np.isfinite(rv) & np.isfinite(r)
        print(f"   RV {name}: delta={info['is_delta']} mean RV / mean r^2 = {np.nanmean(rv[m]) / np.nanmean((r * r)[m]):.3f}; no-bar fallback days {info['fallback_days']}")
    print("   SZ-17 on B -> base_coins", sz17(B, D)[1]["base_coins"])

    # 5. SZ-6b: rho_bar and m ranges on A
    m, ratio, rho, ns = corr_ratio_bk(A.C, 0.70)
    k = np.array([d >= A0 for d in A.dates])
    print(f"   SZ-6b A: rho_bar median {np.nanmedian(rho[k]):.3f} [p5 {np.nanpercentile(rho[k], 5):.3f}, p95 {np.nanpercentile(rho[k], 95):.3f}]; "
          f"m median {np.nanmedian(m[k]):.3f} [min {np.nanmin(m[k]):.3f}, max {np.nanmax(m[k]):.3f}]; N_t median {int(np.median(ns[k]))}")

    # 6. SZ-13 whole-contract path at $1,000 on A and C daily (vs the rounded baseline), with the eligibility log
    for name, pan, a, b in (("A", A, A0, A1), ("C", Cp, C0, C1)):
        for cad in (D, Wk):
            dec = rules.decide_weekly(pan.dates, 6) if cad["weekly"] else None
            Wb = rules.baseline_weights(pan.C, tv=cad["tv"], max_gross=cad["max_gross"])
            kw = dict(decide=dec, band=cad["band"], start=a, end=b, capital=1000.0)
            lg = []
            x = _sz13_custom(cad, 1.0, 0.8, log=lg)(pan, Wb, kw)
            y = sim.simulate(pan, Wb, **kw)
            yrs = len(x["rets"]) / 365
            sx, sy = sim.stats(x), sim.stats(y)
            print(f"   SZ-13 {name}-{cad['name']} $1000: Sharpe {sx['sharpe']:.2f} vs rounded base {sy['sharpe']:.2f}; orders/yr {x['orders'] / yrs:.0f} vs {y['orders'] / yrs:.0f}; "
                  f"vol {sx['vol']:.3f} vs {sy['vol']:.3f}; evals {len(lg)}; last eligible {lg[-1][3]} (n={lg[-1][2]}, E={lg[-1][1]:.0f})")
            mon = [l for l in lg if l[5]]
            assert all((l[0].year, l[0].month) != (m_[0].year, m_[0].month) for l, m_ in zip(mon, mon[1:])), "one monthly evaluation per month"
            print(f"      monthly evals {len(mon)}, entry tests of newly valid coins {len(lg) - len(mon)}")
            # no-op at a capital where every coin always passes: equals the rounded baseline exactly
            kw5 = dict(kw, capital=1e7)
            assert np.array_equal(_sz13_custom(cad, 1.0, 0.8)(pan, Wb, kw5)["rets"], sim.simulate(pan, Wb, **kw5)["rets"]), "no-op at large capital"
        # unrounded line is the baseline
        Wb = rules.baseline_weights(pan.C, tv=0.40, max_gross=2.0)
        kw = dict(decide=None, band=0.0, start=a, end=b, capital=None)
        assert np.array_equal(_sz13_custom(D, 1.0, 0.8)(pan, Wb, kw)["rets"], sim.simulate(pan, Wb, **kw)["rets"])
    print("ok 6: SZ-13 unrounded == baseline; == rounded baseline at $10M; one monthly evaluation per month")
    print(f"done in {time.time() - t0:.0f}s")
