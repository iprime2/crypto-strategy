#!/usr/bin/env python3
"""Daily simulator: weights decided at the close of day t are held over t -> t+1 (no look-ahead).

simulate(panel, W, ...) where W[t, j] is the target weight (fraction of equity) decided at the close of day t.
Costs: cost_bps on traded notional at the close of t; funding F[t+1, j] on the notional held (longs pay).
Cadence: decide[t] False carries units unchanged (they are re-marked, not re-sized). Band: skip a trade when
|target - held| < band * |target| (closes always trade). Capital: whole contracts (CVALS). Delisting: a coin with no
close at t+1 is dropped at the close of t (its trade is charged, as in the repo's weekly variant it is not: `lenient`).
Reproduces cex-mm/scripts/trend_backtest.py::backtest for the baseline to the printed precision.
"""
from __future__ import annotations
import math
import numpy as np
from data import CVALS

COST_BPS = 5.31 + 2.0


def simulate(p, W, *, decide=None, band=0.0, capital=None, cost_bps=COST_BPS, max_gross=None, start=None, end=None, lenient_delist=True, buffer=None, buffer_abs=None):
    """Returns dict(rets (daily, aligned to dates[1:] within [start, end]), dates, gross, traded, fees, funding, trades, units history)."""
    T, N = p.C.shape
    C = p.C
    valid_next = np.isfinite(C)
    cost = cost_bps / 1e4
    eq = float(capital or 1.0)
    units = np.zeros(N)
    rets, dates, grosses, traded_l, fees, fpaid, ntr = [], [], [], [], 0.0, 0.0, 0
    coin_pnl, cost_frac, fund_frac, rgain, rloss = [], [], [], [], []  # per-day reporting (A1 after-tax lines)
    avg_cost = np.zeros(N)  # average entry price per coin for realized-segment P&L
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
        traded = 0.0
        if decide is None or decide[t]:
            u = np.where(np.isfinite(px), w * eq / np.where(np.isfinite(px), px, 1.0), 0.0)  # unrounded target, coin units
            tgt = u
            if capital:
                cv = np.array([CVALS.get(c, 1.0) for c in p.coins])
                tgt = np.round(u / cv) * cv
            if buffer is not None or buffer_abs is not None:
                # Carver position buffering around the UNROUNDED target u (plan COST-2): B = max(b*|u|, m contracts) when trading
                # whole contracts, B = b*|u| on unrounded lines (a contract floor has no meaning at equity 1.0); or an absolute
                # per-row buffer in weight units (COST-1 cells: B = F x full-signal weight). Inside [u-B, u+B] hold; outside,
                # trade to the edge (whole contracts: the integer inside the band nearest the holding; none -> round(u)).
                # u == 0 always closes. Replaces the band for these cells.
                cvb = np.array([CVALS.get(c, 1.0) for c in p.coins])
                if buffer is not None:
                    b, m = buffer
                    B = np.maximum(b * np.abs(u), m * cvb) if capital else b * np.abs(u)
                else:
                    B = np.where(np.isfinite(px), buffer_abs[t] * eq / np.where(np.isfinite(px), px, 1.0), 0.0)
                lo, hi = u - B, u + B
                if capital:
                    lo_i, hi_i = np.ceil(lo / cvb - 1e-9) * cvb, np.floor(hi / cvb + 1e-9) * cvb
                    has_int = lo_i <= hi_i + 1e-12
                    edge = np.where(units < lo, lo_i, np.where(units > hi, hi_i, units))
                    edge = np.where(((units < lo) | (units > hi)) & ~has_int, tgt, edge)
                else:
                    edge = np.where(units < lo, lo, np.where(units > hi, hi, units))
                tgt = np.where(u == 0, 0.0, edge)
            elif band:
                keep = (tgt != 0) & (np.abs(tgt - units) < band * np.abs(tgt))
                tgt = np.where(keep, units, tgt)
            new = tgt
        else:
            new = units.copy()
        # a coin with no close tomorrow cannot be held (repo: `if u and nxt in close[c]`)
        new = np.where(valid_next[t + 1] & np.isfinite(px), new, 0.0)
        if lenient_delist:
            # the repo daily backtest charges the close of a delisted coin; the weekly variant does not. Daily rule: charge.
            pass
        d_units = new - units
        pxs = np.where(np.isfinite(px), px, 0.0)
        traded = float(np.abs(d_units * pxs).sum())
        ntr += int((np.abs(d_units) > 1e-15).sum())
        # realized-segment P&L (average cost): reducing a position realizes (px - avg_cost) on the reduced units
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


# ---------------------------------------------------------------- statistics

def sharpe(x):
    x = np.asarray(x)
    return float(x.mean() / x.std(ddof=1) * math.sqrt(365)) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0


def cagr(x):
    x = np.asarray(x)
    return float(np.prod(1 + x) ** (365 / len(x)) - 1) if len(x) else 0.0


def maxdd(x):
    e = np.cumprod(1 + np.asarray(x))
    return float((e / np.maximum.accumulate(e) - 1).min()) if len(e) else 0.0


def stats(res, a=None, b=None):
    d = np.array(res["dates"]); x = res["rets"]
    m = np.ones(len(x), bool)
    if a: m &= d >= a
    if b: m &= d <= b
    x = x[m]; yrs = np.array([dd.year for dd in d[m]])
    out = dict(days=int(len(x)), sharpe=sharpe(x), cagr=cagr(x), vol=float(x.std(ddof=1) * math.sqrt(365)) if len(x) > 2 else 0.0, mdd=maxdd(x),
               gross=float(res["gross"][m].mean()) if m.any() else 0.0, turnover=float(res["traded"][m].sum() / max(len(x), 1) * 365),
               yearly={int(y): float(np.prod(1 + x[yrs == y]) - 1) for y in sorted(set(yrs))},
               worst_day=float(x.min()) if len(x) else 0.0)
    out["fees_yr"] = out["turnover"] * COST_BPS / 1e4
    e = np.cumprod(1 + x)
    out["worst7"] = float((e[7:] / e[:-7] - 1).min()) if len(e) > 7 else 0.0
    out["funding_yr"] = float(res["fund_frac"][m].sum() / max(len(x), 1) * 365) if "fund_frac" in res else 0.0
    out["max_gross"] = float(res["gross"][m].max()) if m.any() else 0.0
    out["share_gross_gt_0_6"] = float((res["gross"][m] > 0.6).mean()) if m.any() else 0.0
    return out


def line(label, s):
    ys = " ".join(f"{y}:{v:+.0%}" for y, v in s["yearly"].items())
    return (f"{label:44s} Sharpe {s['sharpe']:5.2f} CAGR {s['cagr']:+6.1%} vol {s['vol']:5.1%} maxDD {s['mdd']:6.1%} "
            f"gross {s['gross']:.2f}x turn {s['turnover']:4.1f}x/yr fees {s['fees_yr']:.2%} | {ys}")


def block_bootstrap_diff(ra, rb, n=1000, block=20, seed=7):
    """Paired stationary-ish block bootstrap of Sharpe(a) - Sharpe(b) on the same resampled days. Returns (diff, lo95, hi95, p_b_ge_a)."""
    ra, rb = np.asarray(ra), np.asarray(rb)
    assert len(ra) == len(rb)
    T = len(ra); rng = np.random.default_rng(seed)
    diffs = np.empty(n)
    nb = T // block + 1
    for k in range(n):
        starts = rng.integers(0, T - block + 1, nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:T]
        diffs[k] = sharpe(ra[idx]) - sharpe(rb[idx])
    d = sharpe(ra) - sharpe(rb)
    return d, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float((diffs <= 0).mean())


def expected_max_sharpe(n_trials, sd_trials):
    """Bailey & Lopez de Prado: E[max of n null Sharpes] given the sd of trial Sharpes."""
    from statistics import NormalDist
    if n_trials <= 1:
        return 0.0
    N = NormalDist(); g = 0.5772156649
    return sd_trials * ((1 - g) * N.inv_cdf(1 - 1 / n_trials) + g * N.inv_cdf(1 - 1 / (n_trials * math.e)))
