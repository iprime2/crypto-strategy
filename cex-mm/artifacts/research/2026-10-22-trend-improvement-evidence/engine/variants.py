#!/usr/bin/env python3
"""Variant registry. Each variant: fn(panel, cadence) -> (W, extra simulate kwargs). Add the plan's variants here.
A few generic building-block variants are defined up front so the harness can be smoke-tested; the pre-registered
list from research2/phase1_plan.md is appended below the marker once the plan exists."""
import numpy as np
import rules
from registry import variant

SPAN = 121


def _valid(C):
    return rules.rolling_valid(C, SPAN)


@variant("sig_continuous")
def sig_continuous(p, cad):
    vol = rules.vol_cc(p.C, 60)
    sig = np.maximum(np.nan_to_num(rules.sig_continuous(p.C, vol)), 0.0)
    return rules.size_per_asset(sig, np.nan_to_num(vol, nan=np.inf), _valid(p.C), cad["tv"], cad["max_gross"]), {}


@variant("vol_ewma32")
def vol_ewma32(p, cad):
    sig = np.maximum(np.nan_to_num(rules.sig_sign_mean(p.C)), 0.0)
    vol = rules.vol_ewma(p.C, 32)
    return rules.size_per_asset(sig, np.nan_to_num(vol, nan=np.inf), _valid(p.C), cad["tv"], cad["max_gross"]), {}


@variant("portfolio_vol")
def portfolio_vol(p, cad):
    sig = np.maximum(np.nan_to_num(rules.sig_sign_mean(p.C)), 0.0)
    vol = rules.vol_cc(p.C, 60)
    return rules.size_portfolio_vol(sig, np.nan_to_num(vol, nan=np.inf), _valid(p.C), p.C, cad["tv"] * 0.5, max_gross=cad["max_gross"]), {}

# ---- pre-registered variants from research2/phase1_plan.md are appended below this line ----


@variant("tranche7_smoke")
def tranche7_smoke(p, cad):
    W = rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])
    return W, {"tranches": 7}


# ---- generic helpers for the plan's families ----

def masked_sizing(sig, vol, valid, cad, universe_mask=None, sizing="per_asset", C=None, **kw):
    """Repo sizing with an optional ex-ante universe mask (coins outside the universe get no weight and do not count in N)."""
    v = valid if universe_mask is None else (valid & universe_mask)
    if sizing == "portfolio":
        return rules.size_portfolio_vol(sig, vol, v, C, cad["tv"], max_gross=cad["max_gross"], **kw)
    return rules.size_per_asset(sig, vol, v, cad["tv"], cad["max_gross"], **kw)


def bsc_scaled(p, cad, W, target=None, win=126, cap=2.0, floor=0.25, start=None, end=None):
    """Barroso-Santa-Clara: scale the weight path by target / trailing realized vol of the unscaled strategy's own
    returns (known at the close of t). Two passes through the simulator; the first pass uses the same cadence/band."""
    import sim
    decide = rules.decide_weekly(p.dates, 6) if cad["weekly"] else None
    r0 = sim.simulate(p, W, decide=decide, band=cad["band"])
    rows = np.array([p.idx[d] for d in r0["dates"]])
    m = rules.strategy_vol_multiplier(r0["rets"], rows, len(p.dates), target or cad["tv"], win=win, cap=cap, floor=floor)
    return W * m[:, None]
