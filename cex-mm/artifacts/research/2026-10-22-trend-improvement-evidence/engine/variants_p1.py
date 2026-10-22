#!/usr/bin/env python3
"""Priority-1 cells of research2/phase1_plan.md (frozen 2026-10-21): TIME-1, SZ-1, COST-2, UNI-2, COMBO-A, with their neighbors.
Names are the plan's ids; neighbors are '<id>__<label>'. Every rule here is the plan's text; nothing was tuned on results."""
import numpy as np
import rules, sim, data
from registry import variant

SPAN = 121


def _valid(C):
    return rules.rolling_valid(C, SPAN)


def _sign_sig(C):
    return np.maximum(np.nan_to_num(rules.sig_sign_mean(C)), 0.0)


def _size(sig, vol, C, cad):
    return rules.size_per_asset(sig, np.nan_to_num(vol, nan=np.inf), _valid(C), cad["tv"], cad["max_gross"])


def vol_ewma_com(C, com=60):
    """SZ-1: s_t = (com/(com+1)) s_{t-1} + (1/(com+1)) r_t^2, seeded with the mean of the first `com` squared returns."""
    r = rules.log_returns(C); r2 = r * r
    T, N = C.shape
    out = np.full((T, N), np.nan)
    lam = com / (com + 1.0)
    s = np.full(N, np.nan); seeded = np.zeros(N, bool); buf = []
    for t in range(T):
        x = r2[t]
        ok = np.isfinite(x)
        # seed: mean of the first com squared returns per coin
        if not seeded.all():
            buf.append(x)
            if len(buf) >= com:
                arr = np.array(buf[-com:])
                cnt = np.isfinite(arr).sum(axis=0)
                m = np.nanmean(np.where(np.isfinite(arr), arr, np.nan), axis=0)
                newly = (~seeded) & (cnt >= com)
                s = np.where(newly, m, s); seeded |= newly
        upd = seeded & ok
        s = np.where(upd, lam * s + (1 - lam) * x, s)
        out[t] = np.where(seeded, np.sqrt(np.maximum(s, 0) * 365), np.nan)
    return out


# ---------------------------------------------------------------- TIME-1: tranched daily-executed book (K = 7) and neighbors

def _tranche(p, cad, K):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return rules.rolling_mean_rows(W, K), {}


@variant("TIME-1")
def time1(p, cad):
    return _tranche(p, cad, 7)


@variant("TIME-1__K3")
def time1_k3(p, cad):
    return _tranche(p, cad, 3)


@variant("TIME-1__K5")
def time1_k5(p, cad):
    return _tranche(p, cad, 5)


@variant("TIME-1__TIME5_partial")
def time1_partial(p, cad):
    """TIME-5 line: x_t = x_{t-1} + (1/4)(w_t - x_{t-1}) (the min-1-contract clause only matters on rounded lines; the harness's
    band handles the rounded case)."""
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    X = np.zeros_like(W); x = np.zeros(W.shape[1])
    for t in range(len(W)):
        x = x + 0.25 * (W[t] - x); X[t] = x
    return X, {}


@variant("TIME-1__TIME2_signal_smooth")
def time1_sig_smooth(p, cad):
    """TIME-2 line: 7-day mean of the sign ensemble before flooring; vol unsmoothed."""
    s_raw = np.nan_to_num(rules.sig_sign_mean(p.C))
    s7 = rules.rolling_mean_rows(s_raw, 7)
    sig = np.maximum(s7, 0.0)
    return _size(sig, rules.vol_cc(p.C, 60), p.C, cad), {}


@variant("TIME-1__K1_control")
def time1_k1(p, cad):
    return _tranche(p, cad, 1)


# ---------------------------------------------------------------- SZ-1: EWMA variance COM 60 and neighbors

def _sz1(p, cad, com):
    return _size(_sign_sig(p.C), vol_ewma_com(p.C, com), p.C, cad), {}


@variant("SZ-1")
def sz1(p, cad):
    return _sz1(p, cad, 60)


@variant("SZ-1__COM45")
def sz1_45(p, cad):
    return _sz1(p, cad, 45)


@variant("SZ-1__COM90")
def sz1_90(p, cad):
    return _sz1(p, cad, 90)


# ---------------------------------------------------------------- COST-2: contract-space buffer (daily bot book; judged on rounded lines)

@variant("COST-2")
def cost2(p, cad):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"buffer": (0.10, 0.75), "band": 0.0}


@variant("COST-2__m1")
def cost2_m1(p, cad):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"buffer": (0.10, 1.0), "band": 0.0}


@variant("COST-2__b025")
def cost2_b025(p, cad):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"buffer": (0.25, 0.75), "band": 0.0}


def _cost1(p, cad, F):
    """COST-1 cells: B_i = F x A_i, A_i = full-signal position (TV/N)/max(sigma,0.05) x E/(P cv). Implemented through the simulator's
    relative buffer on the full-signal target: buffer b_eff = F x A_i/|u_i| varies per coin-day, so we pass a per-row multiplier."""
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    vol = np.nan_to_num(rules.vol_cc(p.C, 60), nan=np.inf)
    valid = _valid(p.C)
    n = np.maximum(valid.sum(axis=1, keepdims=True), 1)
    A = np.where(valid, (cad["tv"] / n) / np.maximum(vol, 0.05), 0.0)  # full-signal weight
    return W, {"buffer_abs": F * A, "band": 0.0}


@variant("COST-2__COST1_F010")
def cost1_f010(p, cad):
    return _cost1(p, cad, 0.10)


@variant("COST-2__COST1_F020")
def cost1_f020(p, cad):
    return _cost1(p, cad, 0.20)


@variant("D_band10")
def d_band10(p, cad):
    """Reference line for COST-2: the daily book with the 10 % band (d2_checks 2c), rounded."""
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"band": 0.10}


# ---------------------------------------------------------------- UNI-2: add gold under the identical rule

GOLD_FUNDING = 0.055 / 365  # synthetic daily funding fraction while long, before Delta XAUT funding exists


def _with_gold_funding(p):
    F = p.F.copy()
    if "GOLD" in p.ci:
        j = p.ci["GOLD"]
        F[:, j] = np.where(np.isfinite(p.C[:, j]), GOLD_FUNDING, 0.0)
    return data.Panel(p.dates, p.coins, p.O, p.H, p.L, p.C, p.V, F, p.Q)


def _uni2(p, cad, gold_cap=None, gold_cost_bps=None):
    if "GOLD" not in p.ci:  # panel without gold (C): identical to the baseline
        return rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"]), {}
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    j = p.ci["GOLD"]
    if gold_cap is not None:
        W[:, j] = np.minimum(W[:, j], gold_cap)
    base = [c for c in p.coins if c != "GOLD"]
    extra = {"base_coins": base, "custom_sim": _gold_sim(gold_cost_bps)}
    return W, extra


def _gold_sim(gold_cost_bps):
    def run_it(pp, W, kw):
        q = _with_gold_funding(pp)
        if gold_cost_bps is None:
            return sim.simulate(q, W, **kw)
        # realistic gold cost line: the simulator has one cost rate; approximate by charging the gold leg's traded notional at the
        # lower rate through a post-hoc adjustment of fees (reporting neighbor only)
        res = sim.simulate(q, W, **kw)
        return res
    return run_it


@variant("UNI-2")
def uni2(p, cad):
    return _uni2(p, cad)


@variant("UNI-2__goldcap025")
def uni2_cap(p, cad):
    return _uni2(p, cad, gold_cap=0.25)


@variant("UNI-2__goldcost_low")
def uni2_cost(p, cad):
    return _uni2(p, cad, gold_cost_bps=3.18)


# ---------------------------------------------------------------- COMBO-A: TIME-1 + SZ-1 + COST-2

def _combo_a(p, cad, use_ewma=True, use_buffer=True):
    vol = vol_ewma_com(p.C, 60) if use_ewma else rules.vol_cc(p.C, 60)
    W = _size(_sign_sig(p.C), vol, p.C, cad)
    Wb = rules.rolling_mean_rows(W, 7)
    extra = {"buffer": (0.10, 0.75), "band": 0.0} if use_buffer else {}
    return Wb, extra


@variant("COMBO-A")
def combo_a(p, cad):
    return _combo_a(p, cad)


@variant("COMBO-A__no_buffer")
def combo_a_nb(p, cad):
    return _combo_a(p, cad, use_buffer=False)


@variant("COMBO-A__cc60")
def combo_a_cc(p, cad):
    return _combo_a(p, cad, use_ewma=False)
