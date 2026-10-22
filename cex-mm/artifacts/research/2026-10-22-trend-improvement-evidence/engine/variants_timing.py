#!/usr/bin/env python3
"""Timing-family cells of research2/phase1_plan.md (FROZEN 2026-10-21, sha256 9ad0a829...c095), sections 6.6-6.7.

Cells (plan ids; neighbors are '<ID>__<label>'):
  TIME-3   decision-hour tranche of the signal (six H-aligned closes)      | TIME-3__all24, TIME-3__h0_8_16
  TIME-4   two-session hand book Monday + Thursday, half-gap / 1-contract  | TIME-4__mon_fri, TIME-4__full_gap
  COMBO-B  SIG-2 + SZ-1 + COST-2 (daily bot book)                          | COMBO-B__no_buffer, COMBO-B__cc60
  COMBO-C  TIME-1 (K = 7) + TIME-3 (six hours)                             | COMBO-C__h0_8_16_K7, COMBO-C__six_K5
Target books (plan): TIME-3 both (daily, weekly); TIME-4 W (weekly); COMBO-B D (daily); COMBO-C T (tranche, judged vs W).
Every rule is the plan's text; nothing was set from results. No look-ahead: row t (daily candle dated D, decided at D+1 00:00 UTC)
uses daily rows <= t and hourly bars that close at or before D 23:00 + 1 h = the decision time (self-test checks both).

Interpretations (each the reading closest to the plan text / the cited verifier rule; recorded as the contract asks)
 I1  TIME-3 C^H. Row t = the daily candle dated D, decision at D+1 00:00 UTC. C^0_t = the panel's own daily close (the close of the
     1 h bar opening D 23:00: verified identical on the Binance nine and on Delta 2025+ in the self-test). For H in 1..23,
     C^H_t = close of the 1 h bar that CLOSES at D H:00 (opens D (H-1):00), i.e. "the previous day's H:00 bar" relative to the
     decision day, 24-H hours old at the decision. s^H_i,t = (1/3) sum_L sign(C^H_t / C^H_{t-L} - 1), L in (20, 60, 120) rows (days,
     the baseline's row-lag convention); sig_i = max(mean_H s^H_i, 0) (mean over hours first, then the long-only floor).
 I2  Hourly sources. Binance panels (A, B, B25; detected by a finite volume column): the nine from hourly/<SYM>USDT-1h.csv; the other
     16 B coins (ATOM BAT DASH EOS ETC IOST IOTA NEO ONT QTUM TRX VET XLM XMR XTZ ZEC; the task text says "15", it is 24 minus the 8 of
     the nine inside EXANTE24 = 16, all present) from universe/hourly_extra/binance-<SYM>USDT-1h-YYYY-MM.csv. Delta panel (C; detected
     by an all-NaN volume column, data.load_delta's signature): Delta 1 h (research2/delta_data/hourly_<SYM>USD.json, `time` = bar open,
     verified) for bars opening >= 2025-01-01 00:00 UTC, Binance USDT-M 1 h for bars opening before (the task's splice; the USDT/USD and
     venue basis across the splice is NOT adjusted). A Delta bar missing after the splice is missing (not Binance-filled).
 I3  Missing hourly data. s^H_i,t is defined only when C^H exists at t, t-20, t-60 and t-120; the hour mean runs over the hours with
     s^H defined. H = 0 is the daily close, defined on every valid row, so a coin-day without hourly data falls back to the hours it
     has (at worst the baseline signal): gold on A10/B25G (no 1 h series) and the five extras with a 73-hour archive gap (IOTA TRX
     VET XLM ZEC). Measured on the 121-close valid coin-days: s^H is defined on 100.0 % of them for every H in the six-hour set on
     A, B and C (the extras' 1 h archive starts with their daily archive, 2020-01/02), so the fallback is essentially inactive.
 I4  TIME-3 / COMBO-C sizing: vol = the rule's CC60 from the 00:00 (daily) closes, N = coins with 121 contiguous daily closes,
     w = sig (TV/N)/max(vol, 0.05), gross cap; band and cadence from cad (weekly = the harness's Sunday-candle decision on the same
     daily signal). Zero extra executions.
 I5  TIME-4 sessions. Monday 00:05 UTC = the Sunday candle row (weekday 6, the W book's decision row); Thursday 00:05 UTC = the
     Wednesday candle row (weekday 2), as the plan says; the Mon/Fri neighbor's Friday 00:05 session = the Thursday candle (weekday 3).
     Sessions are fixed by the rule whatever cadence dict is passed (cad supplies TV and cap); the band is fixed at the rule's 10 %
     (passed as the 'band' extra). Target weights = the baseline rule (CC60, sign ensemble) at the cad's TV/cap.
 I6  TIME-4 whole-contract lines: target n* = round-nearest(u / cv) contracts (np.round, exactly as sim.simulate rounds), held n,
     d = n* - n. n* = 0 -> close in full ("closes always trade in full"); |n* - n| < 0.10 |n*| -> no trade (the band on the FULL gap);
     otherwise q = sign(d) x max(1, ceil(0.5 |d|)) contracts (|d| >= 1 holds for every non-zero integer gap). Full-gap neighbor: q = d.
 I7  TIME-4 unrounded lines (capital None, equity 1.0): a contract has no meaning there (as in sim.simulate's buffer comment), so the
     half-gap rule is the spec's own form held + 0.5 (target - held) without rounding (q = d / 2), with the same band and full closes;
     the 1-contract minimum has no unrounded analog. The full-gap neighbor trades q = d (two-session W book).
 I8  TIME-4 trade logic needs its own simulator (custom_sim): simulate_sessions is a line-by-line copy of sim.simulate (costs, funding
     on t+1, delisting flatten, reporting keys) with only the trade rule replaced; the self-test checks it reproduces sim.simulate
     exactly on the Monday-only full-gap book, rounded and unrounded.
 I9  COMBO-B: SIG-2's z keeps SIG-2's own definition, z_L = ln(P_t/P_{t-L}) / ((vol60/sqrt(365)) sqrt(L)) with vol60 = the rule's CC60
     UNFLOORED (as variants_signal I1; the self-test checks equality with variants_signal._sig2); s_L = clip(z_L, 0, 1) (d = 1), sig =
     mean over L (a NaN z counts 0). SZ-1's vol (variants_p1.vol_ewma_com, COM 60) replaces the SIZING vol only. Execution: COST-2's
     buffer extra (0.10, 0.75) with band 0 (sim.simulate: B = max(0.10|u|, 0.75 contracts) on whole-contract lines, 0.10|u| on the
     unrounded line, the COST-2 / COMBO-A convention). Neighbors: no buffer (cad band, 0 on D); CC60 sizing vol with the buffer.
 I10 COMBO-C: W = rules.rolling_mean_rows(size(TIME-3 signal, CC60), K) (TIME-1's convention: rows < K average the rows available);
     K = 7 with six hours (primary), K = 7 with {0, 8, 16}, K = 5 with six hours; TV/cap/band from cad (target T = 'tranche').

Deviations forced by the harness or data: none in the rules. TIME-4 needs custom_sim (I8); it ignores the harness's 'decide' (its
sessions are the rule's) and is compared on the weekly cadence against the harness's Monday-only W baseline. Self-test ran per the
contract on panel A only, one cadence, no capitals; the TIME-4 lines were run on the weekly cadence (their target book; still one
cadence each), the others on daily.

Self-test notes (python3 variants_timing.py; properties of the data / construction, nothing was changed because of them)
 N1  The 23:00-bar close equals the daily close on every coin-day except XRP 2020-01-16/17 (pre-window, archive difference) on A,
     on all of B, and on all Delta coin-days from 2025-01-01 (C).
 N2  TIME-3 with hours (0,) reproduces the baseline weights exactly (A, C); COMBO-C with hours (0,) and K = 7 reproduces TIME-1;
     COMBO-B's SIG-2 equals variants_signal._sig2(d = 1); simulate_sessions (full gap, Mondays) equals sim.simulate bit for bit
     (unrounded, $1,000, $5,000); an independent replay of the half-gap rule at $1,000 finds 0 violations; truncating the daily panel
     or removing hourly bars that close after a row's decision time leaves that row's weights unchanged (all ids, both cadences).
"""
from __future__ import annotations
import csv, datetime as dt, glob, json, math, os
import numpy as np
import rules, sim
from data import CVALS, SP, Panel
from registry import variant
from variants_p1 import vol_ewma_com

SPAN = 121
LOOKS = (20, 60, 120)
SIX = (0, 4, 8, 12, 16, 20)
THREE = (0, 8, 16)
ALL24 = tuple(range(24))
SPLICE_TS = int(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp())  # C: Delta 1 h from here, Binance 1 h before
_EPOCH = dt.date(1970, 1, 1)

_HOURLY: dict = {}   # (src, coin) -> (ts_open_seconds int64 sorted, close float) or None
_HMAT: dict = {}     # memo of hour matrices
_MEMO: dict = {}     # memo of signals keyed by input-array identity


def _memo(tag, arrays, fn):
    """Cache per input-array identity (the harness re-calls fn for the base check, matched vol, stress and capitals). The cache keeps
    references to the inputs so an id cannot be reused while its entry lives."""
    k = (tag, tuple(id(a) for a in arrays))
    hit = _MEMO.get(k)
    if hit is not None and all(x is y for x, y in zip(hit[0], arrays)):
        return hit[1]
    val = fn()
    _MEMO[k] = (tuple(arrays), val)
    return val


# ================================================================ hourly data

def _read_binance_csvs(files):
    ts, cl = [], []
    for fn in files:
        with open(fn) as f:
            for row in csv.reader(f):
                if not row or not row[0].isdigit():
                    continue
                t = int(row[0])
                t = t // 1_000_000 if t > 1e14 else t // 1000  # microseconds in some 2025+ files
                ts.append(t); cl.append(float(row[4]))
    if not ts:
        return None
    ts = np.array(ts, dtype=np.int64); cl = np.array(cl)
    o = np.argsort(ts, kind="stable")
    ts, cl = ts[o], cl[o]
    keep = np.r_[True, ts[1:] != ts[:-1]]  # first file wins on a duplicate bar
    return ts[keep], cl[keep]


def _binance_hourly(coin):
    k = ("binance", coin)
    if k not in _HOURLY:
        f9 = f"{SP}/hourly/{coin}USDT-1h.csv"
        files = [f9] if os.path.exists(f9) else sorted(glob.glob(f"{SP}/universe/hourly_extra/binance-{coin}USDT-1h-*.csv"))
        _HOURLY[k] = _read_binance_csvs(files) if files else None
    return _HOURLY[k]


def _delta_hourly(coin):
    k = ("delta", coin)
    if k not in _HOURLY:
        fn = f"{SP}/research2/delta_data/hourly_{coin}USD.json"
        if os.path.exists(fn):
            rows = json.load(open(fn))
            ts = np.array([int(r["time"]) for r in rows], dtype=np.int64); cl = np.array([float(r["close"]) for r in rows])
            o = np.argsort(ts, kind="stable"); ts, cl = ts[o], cl[o]
            keep = np.r_[True, ts[1:] != ts[:-1]]
            _HOURLY[k] = (ts[keep], cl[keep])
        else:
            _HOURLY[k] = None
    return _HOURLY[k]


def _series(coin, src):
    """Hourly (bar-open ts, close) for a coin on a panel source; Delta panel = Delta >= 2025-01-01, Binance before (I2)."""
    if src == "binance":
        return _binance_hourly(coin)
    b, d = _binance_hourly(coin), _delta_hourly(coin)
    parts = []
    if b is not None:
        m = b[0] < SPLICE_TS; parts.append((b[0][m], b[1][m]))
    if d is not None:
        m = d[0] >= SPLICE_TS; parts.append((d[0][m], d[1][m]))
    if not parts:
        return None
    return np.concatenate([x[0] for x in parts]), np.concatenate([x[1] for x in parts])


def panel_source(p):
    """'delta' for data.load_delta panels (volume all NaN, O = C), else 'binance' (I2)."""
    return "delta" if (np.isnan(p.V).all() and np.array_equal(p.O, p.C, equal_nan=True)) else "binance"


def _day_ts(dates):
    return np.array([(d - _EPOCH).days * 86400 for d in dates], dtype=np.int64)


def hour_matrix(dates, coins, src, H, cutoff=None):
    """(T, N): row t -> close of the 1 h bar closing at dates[t] H:00 UTC (opening (H-1):00), H in 1..24 (24 = the bar closing at the
    next 00:00 = the daily close; used only by the self-test). cutoff: drop bars closing after this unix time (look-ahead test)."""
    bar_open = _day_ts(dates) + (H - 1) * 3600
    out = np.full((len(dates), len(coins)), np.nan)
    for j, c in enumerate(coins):
        ser = _series(c, src)
        if ser is None:
            continue
        ts, cl = ser
        if cutoff is not None:
            m = ts + 3600 <= cutoff; ts, cl = ts[m], cl[m]
        if len(ts) == 0:
            continue
        k = np.minimum(np.searchsorted(ts, bar_open), len(ts) - 1)
        out[:, j] = np.where(ts[k] == bar_open, cl[k], np.nan)
    return out


def _hour_matrix_memo(p, src, H):
    key = (src, tuple(p.coins), p.dates[0], p.dates[-1], len(p.dates), H)
    if key not in _HMAT:
        _HMAT[key] = hour_matrix(p.dates, p.coins, src, H)
    return _HMAT[key]


# ================================================================ signals and sizing

def _valid(C):
    return rules.rolling_valid(C, SPAN)


def _vol60(C):
    return _memo("vol60", (C,), lambda: rules.vol_cc(C, 60))


def _size(sig, C, cad, vol=None):
    vol = _vol60(C) if vol is None else vol
    return rules.size_per_asset(np.nan_to_num(sig), np.nan_to_num(vol, nan=np.inf), _valid(C), cad["tv"], cad["max_gross"])


def _s_hour(CH):
    """(1/3) sum_L sign(CH_t / CH_{t-L} - 1); NaN unless all three lagged closes and CH_t exist (I3)."""
    s = np.zeros(CH.shape); ok = np.ones(CH.shape, bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for L in LOOKS:
            lr = rules.lag_return(CH, L)
            ok &= np.isfinite(lr)
            s += np.where(np.isfinite(lr), np.sign(lr), 0.0)
    return np.where(ok, s / len(LOOKS), np.nan)


def sig_hours(p, hours, src=None, cutoff=None):
    """TIME-3 signal: max(mean over the hours with data of s^H, 0) (I1-I3). cutoff only for the look-ahead self-test (no memo)."""
    src = src or panel_source(p)
    def f():
        acc = np.zeros(p.C.shape); cnt = np.zeros(p.C.shape)
        for H in hours:
            if H == 0:
                CH = p.C
            else:
                CH = hour_matrix(p.dates, p.coins, src, H, cutoff) if cutoff is not None else _hour_matrix_memo(p, src, H)
            s = _s_hour(CH)
            has = np.isfinite(s)
            acc += np.where(has, s, 0.0); cnt += has
        m = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0)
        return np.maximum(m, 0.0)
    if cutoff is not None:
        return f()
    return _memo(("sig_hours", tuple(hours), src), (p.C,), f)


def _sig2(C):
    """SIG-2 (d = 1): mean_L clip(ln(P_t/P_{t-L}) / ((vol60/sqrt(365)) sqrt(L)), 0, 1), vol60 = CC60 unfloored (I9)."""
    def f():
        vd = _vol60(C) / math.sqrt(365.0)
        s = np.zeros(C.shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            for L in LOOKS:
                z = np.log1p(rules.lag_return(C, L)) / (vd * math.sqrt(L))
                s += np.nan_to_num(np.clip(z, 0.0, 1.0), nan=0.0)
        return s / len(LOOKS)
    return _memo("sig2", (C,), f)


def _sz1_vol(C):
    return _memo("ewma_com60", (C,), lambda: vol_ewma_com(C, 60))


# ================================================================ TIME-3: decision-hour tranche of the signal

def _time3(p, cad, hours):
    return _size(sig_hours(p, hours), p.C, cad), {}


@variant("TIME-3")
def time3(p, cad):
    return _time3(p, cad, SIX)


@variant("TIME-3__all24")
def time3_all24(p, cad):
    return _time3(p, cad, ALL24)


@variant("TIME-3__h0_8_16")
def time3_three(p, cad):
    return _time3(p, cad, THREE)


# ================================================================ TIME-4: two-session hand book (custom simulator)

def simulate_sessions(p, W, *, sessions, half_gap=True, band=0.10, capital=None, cost_bps=sim.COST_BPS, max_gross=None, start=None,
                      end=None, **_ignored):
    """sim.simulate with the trade rule replaced by TIME-4's (I6-I8). sessions: (T,) bool, the rows whose close is traded at 00:05."""
    T, N = p.C.shape
    C = p.C
    valid_next = np.isfinite(C)
    cost = cost_bps / 1e4
    eq = float(capital or 1.0)
    cv = np.array([CVALS.get(c, 1.0) for c in p.coins])
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
        if sessions[t]:
            u = np.where(np.isfinite(px), w * eq / np.where(np.isfinite(px), px, 1.0), 0.0)  # unrounded target, coin units
            if capital:
                tgt_n = np.round(u / cv)                 # target contracts, round-nearest exactly as sim.simulate
                tgt = tgt_n * cv
                keep = (tgt != 0) & (np.abs(tgt - units) < band * np.abs(tgt))   # 10 % band on the full gap
                if half_gap:
                    held_n = np.rint(units / cv)         # integers by construction
                    d_n = tgt_n - held_n
                    q_n = np.where(np.abs(d_n) >= 1, np.sign(d_n) * np.maximum(1.0, np.ceil(0.5 * np.abs(d_n))), 0.0)
                    moved = (held_n + q_n) * cv
                else:
                    moved = tgt
            else:
                tgt = u
                keep = (tgt != 0) & (np.abs(tgt - units) < band * np.abs(tgt))
                moved = units + 0.5 * (tgt - units) if half_gap else tgt
            new = np.where(tgt == 0, 0.0, np.where(keep, units, moved))   # closes always trade in full
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


def _sessions(dates, weekdays):
    return np.array([d.weekday() in weekdays for d in dates])


def _time4(p, cad, weekdays, half_gap):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    def run_it(pp, Wx, kw):
        return simulate_sessions(pp, Wx, sessions=_sessions(pp.dates, weekdays), half_gap=half_gap, band=kw.get("band", 0.10),
                                 capital=kw.get("capital"), start=kw.get("start"), end=kw.get("end"))
    return W, {"custom_sim": run_it, "band": 0.10}


@variant("TIME-4")
def time4(p, cad):
    return _time4(p, cad, (6, 2), True)       # Sunday candle -> Mon 00:05, Wednesday candle -> Thu 00:05


@variant("TIME-4__mon_fri")
def time4_mon_fri(p, cad):
    return _time4(p, cad, (6, 3), True)       # Sunday candle -> Mon 00:05, Thursday candle -> Fri 00:05


@variant("TIME-4__full_gap")
def time4_full_gap(p, cad):
    return _time4(p, cad, (6, 2), False)


# ================================================================ COMBO-B: SIG-2 + SZ-1 + COST-2

def _combo_b(p, cad, ewma_vol=True, buffer=True):
    vol = _sz1_vol(p.C) if ewma_vol else _vol60(p.C)
    W = _size(_sig2(p.C), p.C, cad, vol=vol)
    return W, ({"buffer": (0.10, 0.75), "band": 0.0} if buffer else {})


@variant("COMBO-B")
def combo_b(p, cad):
    return _combo_b(p, cad)


@variant("COMBO-B__no_buffer")
def combo_b_nb(p, cad):
    return _combo_b(p, cad, buffer=False)


@variant("COMBO-B__cc60")
def combo_b_cc(p, cad):
    return _combo_b(p, cad, ewma_vol=False)


# ================================================================ COMBO-C: TIME-1 + TIME-3

def _combo_c(p, cad, hours, K):
    W = _size(sig_hours(p, hours), p.C, cad)
    return rules.rolling_mean_rows(W, K), {}


@variant("COMBO-C")
def combo_c(p, cad):
    return _combo_c(p, cad, SIX, 7)


@variant("COMBO-C__h0_8_16_K7")
def combo_c_three(p, cad):
    return _combo_c(p, cad, THREE, 7)


@variant("COMBO-C__six_K5")
def combo_c_k5(p, cad):
    return _combo_c(p, cad, SIX, 5)


IDS = ["TIME-3", "TIME-3__all24", "TIME-3__h0_8_16", "TIME-4", "TIME-4__mon_fri", "TIME-4__full_gap",
       "COMBO-B", "COMBO-B__no_buffer", "COMBO-B__cc60", "COMBO-C", "COMBO-C__h0_8_16_K7", "COMBO-C__six_K5"]


# ================================================================ self-test

def _selftest():
    import data
    from registry import VARIANTS
    daily = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)
    weekly = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)
    P25 = data.load_binance()
    A, B = P25.sub(data.NINE), P25.sub(data.EXANTE24)
    Cd = data.load_delta().sub(data.NINE)
    ok = True

    # 1. bar alignment: the 1 h bar closing at the next 00:00 (H = 24) equals the daily close (Binance A and B; Delta 2025+ on C)
    for name, p in (("A", A), ("B", B), ("C", Cd)):
        src = panel_source(p)
        H24 = hour_matrix(p.dates, p.coins, src, 24)
        m = np.isfinite(H24) & np.isfinite(p.C)
        if src == "delta":
            m &= (_day_ts(p.dates) >= SPLICE_TS)[:, None]
        rel = np.abs(H24[m] / p.C[m] - 1)
        share = float((rel > 1e-9).mean()) if m.any() else 1.0
        print(f"[{name} src={src}] 23:00-bar close == daily close on {int(m.sum())} coin-days; mismatch share {share:.4f}")
        ok &= share < 0.001
        vd = _valid(p.C)
        cov = {H: float(np.isfinite(_s_hour(hour_matrix(p.dates, p.coins, src, H)))[vd].mean()) for H in SIX if H}
        print(f"    share of valid coin-days with s^H defined: " + " ".join(f"H{H}:{v:.3f}" for H, v in cov.items()))

    # 2. TIME-3 with hours (0,) equals the baseline; bar close times precede the decision; no look-ahead in daily or hourly data
    for name, p in (("A", A), ("C", Cd)):
        same0 = np.array_equal(_size(sig_hours(p, (0,)), p.C, daily), rules.baseline_weights(p.C, tv=0.40, max_gross=2.0))
        print(f"[{name}] TIME-3 hours=(0,) == baseline weights: {same0}"); ok &= same0
    for H in range(1, 24):
        assert (H - 1) * 3600 + 3600 <= 23 * 3600 < 86400  # bar for H closes at D H:00 <= D 23:00 < decision D+1 00:00
    t0 = A.idx[dt.date(2023, 6, 30)]
    cutoff = int(_day_ts([A.dates[t0]])[0]) + 86400       # the decision time of row t0
    s_full = sig_hours(A, ALL24); s_cut = sig_hours(A, ALL24, cutoff=cutoff)
    hour_la = np.array_equal(s_full[:t0 + 1], s_cut[:t0 + 1])
    print(f"hourly look-ahead: signal rows <= t0 unchanged when bars closing after t0's decision are removed: {hour_la}"); ok &= hour_la
    tc = Cd.idx[dt.date(2025, 3, 3)]
    cut_c = int(_day_ts([Cd.dates[tc]])[0]) + 86400
    hc = np.array_equal(sig_hours(Cd, SIX)[:tc + 1], sig_hours(Cd, SIX, cutoff=cut_c)[:tc + 1])
    print(f"hourly look-ahead on C (Delta splice): {hc}"); ok &= hc
    Q = Panel(A.dates[:t0 + 1], A.coins, A.O[:t0 + 1], A.H[:t0 + 1], A.L[:t0 + 1], A.C[:t0 + 1].copy(), A.V[:t0 + 1], A.F[:t0 + 1].copy(), A.Q[:t0 + 1])
    for vid in IDS:
        for cad in (daily, weekly):
            Wf, _ = VARIANTS[vid](A, cad); Wt, _ = VARIANTS[vid](Q, cad)
            diff = float(np.nanmax(np.abs(Wf[:t0 + 1] - Wt)))
            if diff >= 1e-12:
                ok = False; print(f"LOOK-AHEAD FAIL {vid} {cad['name']}: {diff:.3g}")
    print("daily-row look-ahead (truncated panel) checked for all ids, both cadences")

    # 3. TIME-4 simulator: Monday-only full-gap reproduces sim.simulate exactly (unrounded and $1,000, $5,000)
    Wb = rules.baseline_weights(A.C, tv=0.25, max_gross=1.0)
    mon = rules.decide_weekly(A.dates, 6)
    for cap in (None, 1000.0, 5000.0):
        a = sim.simulate(A, Wb, decide=mon, band=0.10, capital=cap)
        b = simulate_sessions(A, Wb, sessions=mon, half_gap=False, band=0.10, capital=cap)
        same = all(np.array_equal(np.asarray(a[k]), np.asarray(b[k])) for k in ("rets", "gross", "traded", "coin_pnl", "realized_gain", "fund_frac")) and a["orders"] == b["orders"]
        print(f"simulate_sessions(full gap, Mondays) == sim.simulate band 0.10 cap {cap}: {same}"); ok &= same
    # half-gap rule check at $1,000: every session trade is a full close, a hold, or sign(d) max(1, ceil(|d|/2)) contracts
    ses = _sessions(A.dates, (6, 2))
    r = simulate_sessions(A, Wb, sessions=ses, half_gap=True, capital=1000.0)
    print(f"TIME-4 $1,000 weekly-TV: orders/yr {r['orders'] / (len(r['rets']) / 365):.0f}, mean gross {r['gross'].mean():.3f}; "
          f"Monday-only W: orders/yr {sim.simulate(A, Wb, decide=mon, band=0.10, capital=1000.0)['orders'] / (len(r['rets']) / 365):.0f}")
    pr = Panel(A.dates[:400], A.coins, A.O[:400], A.H[:400], A.L[:400], A.C[:400], A.V[:400], A.F[:400], A.Q[:400])
    viol = _check_half_gap(pr, Wb[:400], ses[:400], 1000.0)
    print(f"half-gap rule violations on the first 400 rows at $1,000: {viol}"); ok &= viol == 0

    # 4. COMBO-B's SIG-2 equals the signal family's SIG-2; COMBO-C with hours (0,) equals TIME-1
    try:
        import variants_signal
        s2 = np.array_equal(_sig2(A.C), variants_signal._sig2(A.C, 1.0))
        print(f"COMBO-B SIG-2 == variants_signal._sig2(d=1): {s2}"); ok &= s2
    except Exception as e:  # pragma: no cover
        print("variants_signal not importable:", e)
    import variants_p1
    tranche = dict(name="tranche", tv=0.25, max_gross=1.0, band=0.10, weekly=False)
    c0 = np.array_equal(_combo_c(A, tranche, (0,), 7)[0], variants_p1._tranche(A, tranche, 7)[0])
    print(f"COMBO-C hours=(0,) K=7 == TIME-1: {c0}"); ok &= c0
    for vid in IDS:
        W, ex = VARIANTS[vid](A, daily)
        print(f"{vid:22s} mean gross weight (daily TV 0.40) {float(np.abs(W).sum(axis=1).mean()):.3f}; extras {sorted(ex)}")
    print("SELFTEST", "OK" if ok else "FAIL")
    return ok


def _check_half_gap(p, W, ses, capital):
    """Replays simulate_sessions' position path and checks each session trade against the written rule."""
    cv = np.array([CVALS.get(c, 1.0) for c in p.coins])
    eq = capital; units = np.zeros(len(p.coins)); bad = 0
    res = simulate_sessions(p, W, sessions=ses, half_gap=True, capital=capital)
    # rebuild the path step by step with the same equity path
    eqs = [float(capital)]
    for x in res["rets"]:
        eqs.append(eqs[-1] * (1 + x))
    for t in range(len(p.dates) - 1):
        eq = eqs[t]
        px = p.C[t]; w = np.nan_to_num(W[t])
        if ses[t]:
            u = np.where(np.isfinite(px), w * eq / np.where(np.isfinite(px), px, 1.0), 0.0)
            n_star = np.round(u / cv); n = np.rint(units / cv); d = n_star - n
            new_n = n.copy()
            for j in range(len(cv)):
                if n_star[j] == 0:
                    new_n[j] = 0
                elif abs(d[j]) < 0.10 * abs(n_star[j]):
                    pass
                elif abs(d[j]) >= 1:
                    new_n[j] = n[j] + math.copysign(max(1, math.ceil(0.5 * abs(d[j]))), d[j])
            new = new_n * cv
        else:
            new = units.copy()
        new = np.where(np.isfinite(p.C[t + 1]) & np.isfinite(px), new, 0.0)
        g = float(np.abs(new * np.where(np.isfinite(px), px, 0.0)).sum()) / eq
        if abs(g - res["gross"][t]) > 1e-9:
            bad += 1
        units = new
    return bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
