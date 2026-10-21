#!/usr/bin/env python3
"""Signal-family cells of research2/phase1_plan.md (FROZEN 2026-10-21, sha256 9ad0a829...c095), section 6.1 plus amendment A8.

Cells: SIG-2, SIG-1B, SIG-3a, SIG-3b, SIG-4, SIG-7A, SIG-10, SIG-11, SIG-13 with their pre-registered neighbors ('<ID>__<label>').
SIG-9 is NOT registered: phase2/diagnostics.md says "SIG-9 runs = False" (the D-1 Correction state's next-7-day return is below the
Bull state's on the 24-coin panel in both windows), so the conditional line does not run.

Every cell changes the signal only. Sizing is the repo form w_i = sig_i (TV/N)/max(vol60_i, 0.05) (N = coins with 121 contiguous
closes, the harness's baseline convention), gross cap, band and cadence from the cadence dict, unless the plan says otherwise
(SIG-4 D-book band rule and the SIG-4 paper-sizing neighbor). All parameters are the plan's; nothing was set from results.
No look-ahead: every quantity at row t uses rows <= t (rolling windows end at t; pandas ewm/rolling are causal). The module's
self-test (python3 variants_signal.py) checks this by truncating the panel and comparing W.

Registered ids
  SIG-2, SIG-2__d0.5, SIG-2__d1.5, SIG-2__SIG1A_form
  SIG-1B, SIG-1B__t0.75, SIG-1B__t1.25
  SIG-3a, SIG-3a__speed_x0.75, SIG-3a__speed_x1.25
  SIG-3b, SIG-3b__denom15, SIG-3b__denom30
  SIG-4, SIG-4__7_lookbacks, SIG-4__paper_sizing, SIG-4__same_day_norm
  SIG-7A, SIG-7A__L200, SIG-7A__L300
  SIG-10, SIG-10__map_0_25_50_100, SIG-10__map_0_50_75_100
  SIG-11, SIG-11__control_breakout_only, SIG-11__looks_20_80_160, SIG-11__smooth_L8
  SIG-13, SIG-13__sleeve120_only, SIG-13__funding_x2

Interpretations (each is the reading closest to the plan text / cited source; recorded here as the contract asks)
 I1  SIG-2: vol60 is the rule's estimator UNFLOORED (sqrt(365 x mean of the last 60 squared log returns)); the 0.05 floor belongs to
     sizing, not to the z-score. z_L = ln(P_t/P_{t-L})/((vol60/sqrt(365)) sqrt(L)); s_L = clip(z_L/d, 0, 1); sig = mean over the 3 L
     (a NaN z, i.e. a coin without history, contributes 0; such coins are outside the 121-close valid set anyway).
 I2  SIG-1A / SIG-1B t-statistic: t_L = mean(r)/(sd(r)/sqrt(L)) over the last L daily log returns, sd the SAMPLE std (ddof 1, the
     plan's own `statistics.stdev` convention); all L returns must exist (rules.rolling_mean convention); sd = 0 -> t = 0.
     SIG-1B: s_L = sign(t_L) if |t_L| >= threshold else 0 ("0 if |t_L| < 1"), sig = max(mean_L s_L, 0).
 I3  SIG-3a/3b EWMAs follow the cited pysystemtrade code literally: pandas ewm(span=n, min_periods=1).mean() (adjust=True) for the
     price EWMAs; sigma_px = pandas ewm(span=35, adjust=True, min_periods=10).std(bias=False) of daily price changes (robust_vol_calc's
     estimator) WITHOUT robust_vol_calc's 5th-percentile/500-day vol floor, because the plan's rule line defines sigma_px as the
     EWMA span-35 std only (the floor is not in the plan). sigma_px is forward-filled across missing rows (ewmac's vol.ffill()).
     No extra warm-up gate beyond the repo's 121-close validity (the plan notes the span-256 warm-up as a caveat, not a rule).
     SIG-3a: sig = mean_n 1[raw_n > 0] in {0, 1/3, 2/3, 1}. SIG-3b: f = clip(mean_n clip(raw_n x scalar_n, -20, 20), 0, D)/D,
     D = 20 (neighbors 15, 30), scalars (16,64) 3.75, (32,128) 2.65, (64,256) 1.87.
 I4  SIG-4 channels: Up_n/Down_n = max/min over the closes that exist among the last n rows incl. t (NaN-aware); a channel "has
     history" once the coin's first close is >= n-1 rows before t (listing age), so a missing archive day (XRP/LTC/VET... 2022-02/04,
     DASH 2022-10) does not reset a 250/360-day channel. On a row without a close the channel state and stop are carried, not updated.
     Order per row, exactly as the plan: exit first (Pos=1 and close <= Stop -> 0), then entry (Pos=0 and close >= Up_n -> 1,
     Stop = Mid_n(t)), then the ratchet Stop(t+1) = max(Stop(t), Mid_n(t)) while long; an exit and a re-entry on the same row are
     therefore possible (sequential reading). The exit test at t uses Stop(t), i.e. mids up to t-1 (plus the entry-day mid).
 I5  SIG-4 D book: "trade on any Pos change, 10 % band only on vol-driven changes" = per coin-day band 0 when any of that coin's
     channels changed Pos on that row, else 0.10 on |target - held| < 0.10 |target| (closes and entries always trade, as in sim).
     Changes of the eligible-channel denominator or of N without a Pos flip are banded (they are not Pos changes). Implemented with a
     custom_sim that is a line-by-line copy of sim.simulate with an array-valued band (the self-test checks it reproduces
     sim.simulate exactly for constant bands, rounded and unrounded, daily and weekly). W book: the harness's standard weekly path
     (daily-evaluated state machine, Sunday-candle decision, 10 % band on every change), since the plan states no exemption there.
     Applied only when cad["name"] == "daily" (the D book).
 I6  SIG-4 paper-sizing neighbor: w_i = sig_i x min(TV/vol90_i, 2.0) / N with the repo's N and gross cap, i.e. the paper's per-asset
     rule min(0.25/sigma90, 2) applied to each coin's 1/N capital sleeve; TV = the cadence's TV (0.25 on W, which is the paper's 0.25;
     0.40 on D) so that the harness's matched-vol re-run (which rescales cad["tv"]) works; vol90 = sample std (ddof 1) of the last
     90 simple close-to-close returns x sqrt(365) (all 90 must exist). Implemented as size_per_asset with vol_eff = max(vol90, TV/2).
 I7  SIG-4 same-day-normalisation neighbor: sig_i = (# long)/9 only on rows where all nine channels have history, else 0 (the state
     machines run from each channel's own start; only the counting waits); N is unchanged (repo valid set).
 I8  SIG-7A: a sleeve L counts on row t iff P_{t-L} exists (lag return finite); sig = max(mean of sign over counted sleeves, 0).
     The 20/60/120 sleeves always exist on valid rows, so before the 250-day sleeve exists the cell equals the baseline.
 I9  SIG-10 neighbors map the count k of positive sleeves (P_t/P_{t-L} > 1, strict) k = 0..3 to {0, 1/4, 1/2, 1} and {0, 1/2, 3/4, 1}.
 I10 SIG-11 follows pysystemtrade breakout.py: rolling max/min with min_periods = ceil(L/2) (so after L closes the window is exactly
     "the last L closes incl. t"), raw = 40 (P - mid)/(max - min) (max == min -> NaN, skipped), smoothed by pandas ewm(span=s,
     min_periods=ceil(s/2)).mean() with s = max(int(L/4), 1) (neighbor: max(int(L/8), 1)), then clipped to [-20, 20]; no forecast
     scalar (the plan's b_L has none); f_B = max(mean_L b_L / 20, 0) with a missing b_L counted as 0. Primary: 0.5 sig_sign + 0.5 f_B,
     sig_sign = the baseline's max(mean_L sign, 0) on (20, 60, 120). Control: f_B alone. The (20, 80, 160) neighbor changes the
     breakout lookbacks only (the sign half stays on (20, 60, 120)), as the original spec did; it uses the 50/50 form.
 I11 SIG-13: TR_t = P_t x prod_{s<=t} (1 - k F_s) (k = 1; 2 for the funding-x2 neighbor), which equals the plan's recursion
     TR_t = TR_{t-1}(P_t/P_{t-1})(1 - f_t) on contiguous data and is defined across missing days; F is the panel's daily funding
     fraction paid by longs (0 where missing), F[t] = the funding charged on day t (known at the close of t). Sign ensemble on TR
     (floor 0); vol60, N and sizing from P (sizing unchanged). The 120-sleeve-only neighbor uses TR for L = 120 and P for 20, 60.
     The harness's A6 Delta-funding-stress line calls fn on the original panel, so SIG-13's signal there uses the archive funding
     while costs use the stressed funding (a harness property, noted, not changed).

Deviations forced by the harness: none beyond I5 (SIG-4's D-book band needs a custom_sim because sim.simulate takes one scalar band).

Structural notes (properties of the plan's rules, found while self-testing on panel A daily; nothing was changed because of them)
 N1  SIG-3b__denom30 is an exact 2/3 rescale of SIG-3b: combined is already capped at 20 <= 30, so clip(combined, 0, 30)/30 =
     (20/30) clip(combined, 0, 20)/20. Its Sharpe equals the primary's by construction (only vol/TV differ); as a saturation
     neighbor it is degenerate. denom15 is the only neighbor that changes the shape.
 N2  SIG-4__same_day_norm has zero exposure per coin until its 360-day channel exists (Binance 2020-12..2021-07, Delta 2025-04),
     so its FULL window misses the 2020-21 run-up; POST is the informative window for it (the verifier's caveat).
 N3  SIG-2 and SIG-2__SIG1A_form are almost the same object (corr 0.995 of the signal on valid coin-days, panel A), as the
     verifier said (z uses the 60-day RMS, t the L-day sample sd).
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
import rules, sim
from data import CVALS, Panel
from registry import variant

SPAN = 121
LOOKS = (20, 60, 120)
_CACHE: dict = {}


def _memo(tag, arrays, fn):
    """Cache signal arrays per input-array identity (the harness re-calls fn for the base check, matched vol, stress and capitals).
    The cache keeps references to the inputs, so an id can never be reused while its entry lives."""
    k = (tag, tuple(id(a) for a in arrays))
    hit = _CACHE.get(k)
    if hit is not None and all(x is y for x, y in zip(hit[0], arrays)):
        return hit[1]
    val = fn()
    _CACHE[k] = (tuple(arrays), val)
    return val


def _valid(C):
    return rules.rolling_valid(C, SPAN)


def _vol60(C):
    return _memo("vol60", (C,), lambda: rules.vol_cc(C, 60))


def _size(sig, C, cad, vol=None):
    vol = _vol60(C) if vol is None else vol
    return rules.size_per_asset(np.nan_to_num(sig), np.nan_to_num(vol, nan=np.inf), _valid(C), cad["tv"], cad["max_gross"])


def _sign_sig(C, looks=LOOKS):
    return np.maximum(np.nan_to_num(rules.sig_sign_mean(C, looks)), 0.0)


def _ewm_mean(X, span, min_periods=1):
    return pd.DataFrame(X).ewm(span=span, min_periods=min_periods).mean().to_numpy()


# ================================================================ SIG-2 (vol-normalised clipped ensemble) and SIG-1A / SIG-1B (t-stat)

def _sig2(C, d=1.0):
    vd = _vol60(C) / math.sqrt(365.0)
    s = np.zeros(C.shape)
    with np.errstate(divide="ignore", invalid="ignore"):
        for L in LOOKS:
            z = np.log1p(rules.lag_return(C, L)) / (vd * math.sqrt(L))
            s += np.nan_to_num(np.clip(z / d, 0.0, 1.0), nan=0.0)
    return s / len(LOOKS)


def _tstat(C, L):
    def f():
        r = rules.log_returns(C)
        m = rules.rolling_mean(r, L)
        sd = rules.rolling_std(r, L)  # sample std, ddof 1
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(np.isfinite(sd) & (sd > 0), m / (sd / math.sqrt(L)), np.where(np.isfinite(sd), 0.0, np.nan))
    return _memo(f"tstat{L}", (C,), f)


def _sig1a(C):
    s = np.zeros(C.shape)
    for L in LOOKS:
        s += np.nan_to_num(np.clip(_tstat(C, L), 0.0, 1.0), nan=0.0)
    return s / len(LOOKS)


def _sig1b(C, thr=1.0):
    s = np.zeros(C.shape)
    for L in LOOKS:
        t = np.nan_to_num(_tstat(C, L), nan=0.0)
        s += np.where(np.abs(t) >= thr, np.sign(t), 0.0)
    return np.maximum(s / len(LOOKS), 0.0)


@variant("SIG-2")
def sig2(p, cad):
    return _size(_sig2(p.C, 1.0), p.C, cad), {}


@variant("SIG-2__d0.5")
def sig2_d05(p, cad):
    return _size(_sig2(p.C, 0.5), p.C, cad), {}


@variant("SIG-2__d1.5")
def sig2_d15(p, cad):
    return _size(_sig2(p.C, 1.5), p.C, cad), {}


@variant("SIG-2__SIG1A_form")
def sig2_1a(p, cad):
    return _size(_sig1a(p.C), p.C, cad), {}


@variant("SIG-1B")
def sig1b(p, cad):
    return _size(_sig1b(p.C, 1.0), p.C, cad), {}


@variant("SIG-1B__t0.75")
def sig1b_075(p, cad):
    return _size(_sig1b(p.C, 0.75), p.C, cad), {}


@variant("SIG-1B__t1.25")
def sig1b_125(p, cad):
    return _size(_sig1b(p.C, 1.25), p.C, cad), {}


# ================================================================ SIG-3a / SIG-3b (EWMAC, pysystemtrade chapter-15 pairs)

PAIRS = ((16, 64), (32, 128), (64, 256))
SCALARS = {16: 3.75, 32: 2.65, 64: 1.87}


def _sigma_px(C):
    def f():
        d = np.full(C.shape, np.nan); d[1:] = C[1:] - C[:-1]
        return pd.DataFrame(d).ewm(span=35, adjust=True, min_periods=10).std(bias=False).ffill().to_numpy()
    return _memo("sigma_px35", (C,), f)


def _ewmac_raw(C, n):
    def f():
        with np.errstate(divide="ignore", invalid="ignore"):
            return (_ewm_mean(C, n) - _ewm_mean(C, 4 * n)) / _sigma_px(C)
    return _memo(f"ewmac{n}", (C,), f)


def _sig3a(C, fasts):
    s = np.zeros(C.shape)
    for n in fasts:
        s += (np.nan_to_num(_ewmac_raw(C, n), nan=0.0) > 0).astype(float)
    return s / len(fasts)


def _sig3b(C, denom=20.0):
    comb = np.zeros(C.shape)
    for n, _ in PAIRS:
        comb += np.clip(np.nan_to_num(_ewmac_raw(C, n) * SCALARS[n], nan=0.0), -20.0, 20.0)
    comb /= len(PAIRS)  # FDM 1.0
    return np.clip(comb, 0.0, denom) / denom


@variant("SIG-3a")
def sig3a(p, cad):
    return _size(_sig3a(p.C, (16, 32, 64)), p.C, cad), {}


@variant("SIG-3a__speed_x0.75")
def sig3a_075(p, cad):
    return _size(_sig3a(p.C, (12, 24, 48)), p.C, cad), {}


@variant("SIG-3a__speed_x1.25")
def sig3a_125(p, cad):
    return _size(_sig3a(p.C, (20, 40, 80)), p.C, cad), {}


@variant("SIG-3b")
def sig3b(p, cad):
    return _size(_sig3b(p.C, 20.0), p.C, cad), {}


@variant("SIG-3b__denom15")
def sig3b_15(p, cad):
    return _size(_sig3b(p.C, 15.0), p.C, cad), {}


@variant("SIG-3b__denom30")
def sig3b_30(p, cad):
    return _size(_sig3b(p.C, 30.0), p.C, cad), {}


# ================================================================ SIG-4 Donchian ensemble with ratcheting mid-line exit

DON9 = (5, 10, 20, 30, 60, 90, 150, 250, 360)
DON7 = (5, 10, 20, 30, 60, 90, 150)
SIG4_BAND = 0.10


def donchian_states(C, looks):
    """Returns (pos, has): bool arrays (len(looks), T, N). See interpretation I4."""
    def f():
        T, N = C.shape
        fin = np.isfinite(C)
        first = np.array([int(np.argmax(fin[:, j])) if fin[:, j].any() else T for j in range(N)])
        age = np.arange(T)[:, None] - first[None, :] + 1
        df = pd.DataFrame(C)
        pos_all = np.zeros((len(looks), T, N), bool); has_all = np.zeros((len(looks), T, N), bool)
        for k, n in enumerate(looks):
            up = df.rolling(n, min_periods=1).max().to_numpy()
            dn = df.rolling(n, min_periods=1).min().to_numpy()
            mid = (up + dn) / 2.0
            has = age >= n
            pos = np.zeros(N, bool); stop = np.full(N, np.nan)
            for t in range(T):
                ok = fin[t] & has[t]
                c = C[t]
                with np.errstate(invalid="ignore"):
                    ex = pos & ok & (c <= stop)                  # exit first
                    pos = pos & ~ex
                    en = (~pos) & ok & (c >= up[t])             # then entry
                pos = pos | en
                stop = np.where(en, mid[t], stop)
                stop = np.where(pos & ok, np.fmax(stop, mid[t]), stop)  # ratchet: Stop(t+1) = max(Stop(t), Mid(t))
                stop = np.where(pos, stop, np.nan)
                pos_all[k, t] = pos
            has_all[k] = has
        return pos_all, has_all
    return _memo(f"donchian{looks}", (C,), f)


def _sig4(C, looks=DON9, same_day=False):
    pos, has = donchian_states(C, looks)
    nl = pos.sum(axis=0).astype(float); nh = has.sum(axis=0).astype(float)
    if same_day:
        return np.where(nh == len(looks), nl / len(looks), 0.0)
    return np.where(nh > 0, nl / np.maximum(nh, 1.0), 0.0)


def _pos_change(C, looks):
    pos, _ = donchian_states(C, looks)
    chg = np.zeros(pos.shape[1:], bool)
    chg[1:] = (pos[:, 1:] != pos[:, :-1]).any(axis=0)
    chg[0] = pos[:, 0].any(axis=0)
    return chg


def simulate_band_array(p, W, band_arr, *, decide=None, capital=None, cost_bps=sim.COST_BPS, max_gross=None, start=None, end=None, **_ignored):
    """Line-by-line copy of sim.simulate (no buffer branch) with a per-coin-day band band_arr[t, j]. Same return keys."""
    T, N = p.C.shape
    C = p.C
    valid_next = np.isfinite(C)
    cost = cost_bps / 1e4
    eq = float(capital or 1.0)
    units = np.zeros(N)
    rets, dates, grosses, traded_l, fees, fpaid, ntr = [], [], [], [], 0.0, 0.0, 0
    coin_pnl, cost_frac, fund_frac, rgain, rloss = [], [], [], [], []
    avg_cost = np.zeros(N)
    for t in range(T - 1):
        nxt = p.dates[t + 1]
        if (start and nxt < start) or (end and nxt > end):
            continue
        w = W[t].copy()
        w[~np.isfinite(w)] = 0.0
        if max_gross is not None:
            g = np.abs(w).sum()
            if g > max_gross:
                w *= max_gross / g
        px = C[t]
        if decide is None or decide[t]:
            u = np.where(np.isfinite(px), w * eq / np.where(np.isfinite(px), px, 1.0), 0.0)
            tgt = u
            if capital:
                cv = np.array([CVALS.get(c, 1.0) for c in p.coins])
                tgt = np.round(u / cv) * cv
            bnd = band_arr[t]
            keep = (tgt != 0) & (np.abs(tgt - units) < bnd * np.abs(tgt))
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


def _sig4_extra(p, cad, looks):
    """D book (I5): band 0 on rows with a Pos change of the coin, 0.10 otherwise, via a custom simulator. W book: standard path."""
    if cad.get("name") != "daily":
        return {}
    band_arr = np.where(_pos_change(p.C, looks), 0.0, SIG4_BAND)

    def run_it(pp, W, kw):
        kw = dict(kw); kw.pop("band", None)
        return simulate_band_array(pp, W, band_arr, **kw)
    return {"custom_sim": run_it}


def _vol90(C):
    def f():
        r = np.full(C.shape, np.nan); r[1:] = C[1:] / C[:-1] - 1
        return rules.rolling_std(r, 90) * math.sqrt(365.0)
    return _memo("vol90", (C,), f)


@variant("SIG-4")
def sig4(p, cad):
    return _size(_sig4(p.C, DON9), p.C, cad), _sig4_extra(p, cad, DON9)


@variant("SIG-4__7_lookbacks")
def sig4_7(p, cad):
    return _size(_sig4(p.C, DON7), p.C, cad), _sig4_extra(p, cad, DON7)


@variant("SIG-4__paper_sizing")
def sig4_paper(p, cad):
    v90 = _vol90(p.C)
    vol_eff = np.maximum(v90, cad["tv"] / 2.0)  # sig x min(TV/vol90, 2) = sig x TV / max(vol90, TV/2); NaN vol90 -> no weight
    return _size(_sig4(p.C, DON9), p.C, cad, vol=vol_eff), _sig4_extra(p, cad, DON9)


@variant("SIG-4__same_day_norm")
def sig4_same(p, cad):
    return _size(_sig4(p.C, DON9, same_day=True), p.C, cad), _sig4_extra(p, cad, DON9)


# ================================================================ SIG-7A add a slow sleeve (eligible-sleeve normalisation)

def _sig_eligible(C, looks):
    num = np.zeros(C.shape); den = np.zeros(C.shape)
    for L in looks:
        lr = rules.lag_return(C, L)
        ok = np.isfinite(lr)
        num += np.where(ok, np.sign(np.nan_to_num(lr)), 0.0); den += ok
    return np.maximum(np.where(den > 0, num / np.maximum(den, 1.0), 0.0), 0.0)


@variant("SIG-7A")
def sig7a(p, cad):
    return _size(_sig_eligible(p.C, (20, 60, 120, 250)), p.C, cad), {}


@variant("SIG-7A__L200")
def sig7a_200(p, cad):
    return _size(_sig_eligible(p.C, (20, 60, 120, 200)), p.C, cad), {}


@variant("SIG-7A__L300")
def sig7a_300(p, cad):
    return _size(_sig_eligible(p.C, (20, 60, 120, 300)), p.C, cad), {}


# ================================================================ SIG-10 linear agreement count

def _sig10(C, mapping):
    k = np.zeros(C.shape, int)
    with np.errstate(invalid="ignore"):
        for L in LOOKS:
            k += (np.nan_to_num(rules.lag_return(C, L), nan=0.0) > 0).astype(int)
    return np.asarray(mapping, float)[k]


@variant("SIG-10")
def sig10(p, cad):
    return _size(_sig10(p.C, (0.0, 1 / 3, 2 / 3, 1.0)), p.C, cad), {}


@variant("SIG-10__map_0_25_50_100")
def sig10_a(p, cad):
    return _size(_sig10(p.C, (0.0, 0.25, 0.5, 1.0)), p.C, cad), {}


@variant("SIG-10__map_0_50_75_100")
def sig10_b(p, cad):
    return _size(_sig10(p.C, (0.0, 0.5, 0.75, 1.0)), p.C, cad), {}


# ================================================================ SIG-11 Carver breakout, 50/50 with the sign ensemble

def _breakout(C, L, smooth):
    def f():
        df = pd.DataFrame(C)
        mp = int(min(len(C), math.ceil(L / 2.0)))
        mx = df.rolling(L, min_periods=mp).max(); mn = df.rolling(L, min_periods=mp).min()
        mean = (mx + mn) / 2.0
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = 40.0 * (df - mean) / (mx - mn)
        raw = raw.replace([np.inf, -np.inf], np.nan)
        sm = raw.ewm(span=smooth, min_periods=int(math.ceil(smooth / 2.0))).mean().to_numpy()
        return np.clip(sm, -20.0, 20.0)
    return _memo(f"breakout{L}_{smooth}", (C,), f)


def _f_b(C, looks=LOOKS, div=4):
    s = np.zeros(C.shape)
    for L in looks:
        s += np.nan_to_num(_breakout(C, L, max(int(L / div), 1)), nan=0.0)
    return np.maximum(s / len(looks) / 20.0, 0.0)


@variant("SIG-11")
def sig11(p, cad):
    return _size(0.5 * _sign_sig(p.C) + 0.5 * _f_b(p.C), p.C, cad), {}


@variant("SIG-11__control_breakout_only")
def sig11_ctrl(p, cad):
    return _size(_f_b(p.C), p.C, cad), {}


@variant("SIG-11__looks_20_80_160")
def sig11_looks(p, cad):
    return _size(0.5 * _sign_sig(p.C) + 0.5 * _f_b(p.C, (20, 80, 160)), p.C, cad), {}


@variant("SIG-11__smooth_L8")
def sig11_s8(p, cad):
    return _size(0.5 * _sign_sig(p.C) + 0.5 * _f_b(p.C, LOOKS, div=8), p.C, cad), {}


# ================================================================ SIG-13 trend on the funding-adjusted total-return index (A8)

def total_return_index(C, F, k=1.0):
    D = np.cumprod(1.0 - k * np.nan_to_num(F, nan=0.0), axis=0)
    return C * D


def _sig13(p, k=1.0, sleeves_tr=LOOKS):
    TR = _memo(f"tr{k}", (p.C, p.F), lambda: total_return_index(p.C, p.F, k))
    s = np.zeros(p.C.shape)
    for L in LOOKS:
        s += np.sign(rules.lag_return(TR if L in sleeves_tr else p.C, L))
    return np.maximum(np.nan_to_num(s / len(LOOKS)), 0.0)


@variant("SIG-13")
def sig13(p, cad):
    return _size(_sig13(p), p.C, cad), {}


@variant("SIG-13__sleeve120_only")
def sig13_120(p, cad):
    return _size(_sig13(p, 1.0, (120,)), p.C, cad), {}


@variant("SIG-13__funding_x2")
def sig13_x2(p, cad):
    return _size(_sig13(p, 2.0), p.C, cad), {}


IDS = ["SIG-2", "SIG-2__d0.5", "SIG-2__d1.5", "SIG-2__SIG1A_form", "SIG-1B", "SIG-1B__t0.75", "SIG-1B__t1.25",
       "SIG-3a", "SIG-3a__speed_x0.75", "SIG-3a__speed_x1.25", "SIG-3b", "SIG-3b__denom15", "SIG-3b__denom30",
       "SIG-4", "SIG-4__7_lookbacks", "SIG-4__paper_sizing", "SIG-4__same_day_norm", "SIG-7A", "SIG-7A__L200", "SIG-7A__L300",
       "SIG-10", "SIG-10__map_0_25_50_100", "SIG-10__map_0_50_75_100",
       "SIG-11", "SIG-11__control_breakout_only", "SIG-11__looks_20_80_160", "SIG-11__smooth_L8",
       "SIG-13", "SIG-13__sleeve120_only", "SIG-13__funding_x2"]


# ================================================================ self-test (look-ahead, custom simulator equivalence, sanity)

def _selftest():
    import data
    from registry import VARIANTS
    P = data.load_binance().sub(data.NINE)
    daily = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)
    weekly = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)
    ok = True
    # 1. custom simulator reproduces sim.simulate for constant bands (unrounded/rounded, daily/weekly)
    Wb = rules.baseline_weights(P.C, tv=0.40)
    dec = rules.decide_weekly(P.dates, 6)
    for band in (0.0, 0.10):
        for cap in (None, 1000.0):
            for decide in (None, dec):
                a = sim.simulate(P, Wb, decide=decide, band=band, capital=cap)
                b = simulate_band_array(P, Wb, np.full(P.C.shape, band), decide=decide, capital=cap)
                same = all(np.array_equal(np.asarray(a[k]), np.asarray(b[k])) for k in ("rets", "gross", "traded", "coin_pnl", "realized_gain")) and a["orders"] == b["orders"]
                ok &= same
                print(f"custom sim == sim.simulate band {band} cap {cap} weekly {decide is not None}: {same}")
    # 2. no look-ahead: W on a truncated panel equals W on the full panel for the shared rows
    t0 = P.idx[data.dt.date(2023, 6, 30)] if hasattr(data, "dt") else len(P.dates) // 2
    Q = Panel(P.dates[:t0 + 1], P.coins, P.O[:t0 + 1], P.H[:t0 + 1], P.L[:t0 + 1], P.C[:t0 + 1].copy(), P.V[:t0 + 1], P.F[:t0 + 1].copy(), P.Q[:t0 + 1])
    for vid in IDS:
        for cad in (daily, weekly):
            Wf, _ = VARIANTS[vid](P, cad); Wt, _ = VARIANTS[vid](Q, cad)
            diff = float(np.nanmax(np.abs(Wf[:t0 + 1] - Wt)))
            good = diff < 1e-12
            ok &= good
            if not good:
                print(f"LOOK-AHEAD FAIL {vid} {cad['name']}: max |dW| {diff:.3g}")
        Wf, ex = VARIANTS[vid](P, daily)
        sig_mean = float(np.abs(Wf).sum(axis=1).mean())
        print(f"{vid:32s} no-look-ahead ok; mean gross weight (daily TV0.40) {sig_mean:.3f}; custom_sim {'custom_sim' in ex}")
    # 3. sanity: SIG-7A equals the baseline before any coin has a 250-day sleeve; SIG-13 with zero funding equals the baseline
    W7, _ = VARIANTS["SIG-7A"](P, daily)
    first250 = 250 + int(np.argmax(np.isfinite(P.C).any(axis=1)))
    same7 = np.allclose(W7[:first250], Wb[:first250])
    Z = Panel(P.dates, P.coins, P.O, P.H, P.L, P.C, P.V, np.zeros_like(P.F), P.Q)
    W13, _ = VARIANTS["SIG-13"](Z, daily)
    same13 = np.array_equal(W13, Wb)
    print(f"SIG-7A == baseline before the first 250-day sleeve: {same7}; SIG-13 with zero funding == baseline: {same13}")
    ok &= same7 and same13
    pos, has = donchian_states(P.C, DON9)
    print("SIG-4 share of channel-days long (eligible):", round(float(pos.sum() / max(has.sum(), 1)), 3),
          "| D-book rows with a Pos change:", round(float(_pos_change(P.C, DON9).mean()), 3))
    print("SELFTEST", "OK" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
