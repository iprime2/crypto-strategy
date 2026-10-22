"""Shared helpers for the UNI-1 robustness/attribution lens. Read-only use of tools2 (imports only)."""
import datetime as dt, json, math, os, sys, time
TOOLS = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools2"
sys.path.insert(0, TOOLS)
import numpy as np
import data, rules, sim
import variants_universe as vu

OUT = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/uni1_verify/robust"
POST = dt.date(2022, 1, 1)
CADS = {"daily": vu.DAILY, "weekly": vu.WEEKLY}

_P = {}
def ctx():
    if "ctx" not in _P:
        P = vu.load_pool(); _P["P"] = P; _P["ctx"] = vu._ctx(P)
    return _P["ctx"]

def kw(c, cad, start=vu.A0, end=vu.A1):
    return dict(decide=rules.decide_weekly(c.dates, 6) if cad["weekly"] else None, band=cad["band"], start=start, end=end, capital=None)

def U_uni1(c, cad, spec="UNI-1"):
    return vu._membership(c, cad, vu.SPECS[spec])

def U_static24(c):
    return vu._static_mask(c, data.EXANTE24)

def W_of(c, cad, U):
    return vu._weights(c, cad, U)

def run(c, cad, W, start=vu.A0, end=vu.A1, F=None):
    """sim on the cleaned pool; F = optional replacement funding (T, N) for the full pool."""
    k = kw(c, cad, start, end)
    if F is None:
        return vu._sim(c, W, k)
    cols = np.flatnonzero(np.abs(W).sum(axis=0) > 0)
    names = [c.coins[j] for j in cols]
    pc = c.pc
    sub = data.Panel(pc.dates, names, pc.O[:, cols], pc.H[:, cols], pc.L[:, cols], pc.C[:, cols], pc.V[:, cols], F[:, cols], pc.Q[:, cols])
    res = sim.simulate(sub, W[:, cols], **k); res["cols"] = names
    return res

def mask(res, a=None, b=None):
    d = np.array(res["dates"]); m = np.ones(len(d), bool)
    if a: m &= d >= a
    if b: m &= d <= b
    return m

def sh(res, a=None, b=None):
    return sim.sharpe(res["rets"][mask(res, a, b)])

def yearly(res):
    d = np.array(res["dates"]); x = res["rets"]; yrs = np.array([q.year for q in d])
    out = {}
    for y in sorted(set(yrs)):
        k = yrs == y
        out[int(y)] = dict(sharpe=sim.sharpe(x[k]), ret=float(np.prod(1 + x[k]) - 1), vol=float(x[k].std(ddof=1) * math.sqrt(365)), days=int(k.sum()))
    return out

def boot(ra, rb, a=None, b=None, resa=None):
    m = mask(resa, a, b)
    return sim.block_bootstrap_diff(ra["rets"][m], rb["rets"][m])

def coin_cost(res, W_cols_units=None):
    """Not used: per-coin costs are recomputed in attribution via the traded notional per coin."""
    pass


def membership_custom(c, cad, N=9, H=18, age=365, reset="yearly", excl=None, pick=None, rng=None, start_floor=None):
    """Copy of vu._membership (no capital gate) with (a) an extra exclusion mask and (b) an optional random picker:
    pick=None -> UNI-1 rule (vu._select); pick='random' -> draw min(N, |eligible|) uniformly from the eligible list
    (age-eligible candidates + incumbents still candidates in the same life; no hysteresis, no ranking);
    pick=('random_top', K) -> uniform draw of N from the top-K of the eligible list by turnover."""
    ex = c.excl if excl is None else (c.excl | excl)
    rows = vu._reset_rows(c, cad["weekly"], reset)
    U = np.zeros((c.T, c.N), bool); inc = {}; log = []
    for k, r in enumerate(rows):
        floor = start_floor if k == 0 else age
        if pick is None:
            sel, _ = vu._select(c, r, inc, N, H, floor, excl=ex)
        else:
            base = c.pos[r] & ~ex & (c.AGE[r] >= vu.MED_WIN)
            inc_ok = np.zeros(c.N, bool)
            for j, L in inc.items():
                inc_ok[j] = base[j] and c.LIFE[r, j] == L
            elig = (base & (c.AGE[r] >= floor)) if floor else base.copy()
            elig |= inc_ok
            cols = np.flatnonzero(elig)
            if pick != "random":
                K = pick[1]
                med = np.nanmedian(c.Qc[max(r - vu.MED_WIN + 1, 0):r + 1][:, cols], axis=0)
                cols = cols[np.argsort(-med, kind="stable")][:K]
            sel = list(rng.choice(cols, size=min(N, len(cols)), replace=False)) if len(cols) else []
        inc = {int(j): int(c.LIFE[r, j]) for j in sel}
        end = rows[k + 1] if k + 1 < len(rows) else c.T
        for j, L in inc.items():
            U[r:end, j] = c.LIFE[r:end, j] == L
        log.append((str(c.dates[r]), [str(c.coins[j]) for j in sel]))
    return U, log


def static_mask_excl(c, coins, drop=()):
    return vu._static_mask(c, [x for x in coins if x not in set(drop)])


def excl_mask(c, names):
    m = np.zeros(c.N, bool)
    for n in names:
        m[c.coins.index(n)] = True
    return m
