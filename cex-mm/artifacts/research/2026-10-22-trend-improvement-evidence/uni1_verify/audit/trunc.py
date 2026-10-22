#!/usr/bin/env python3
"""(1) Look-ahead audit of UNI-1: truncation test (panel cut at d) and perturbation test (all data after d replaced by noise),
on W, on the membership mask U, and on the simulated daily returns. Random cut dates + hand-picked risky dates."""
import sys, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
import numpy as np
import data, sim, rules
import variants_universe as vu

P = vu.load_pool()
T = len(P.dates)
rng = np.random.default_rng(20261021)
lo, hi = P.idx[dt.date(2020, 5, 2)], P.idx[dt.date(2026, 9, 28)]
rand_rows = sorted(rng.choice(np.arange(lo, hi), 16, replace=False).tolist())
picked = [dt.date(2020, 12, 31), dt.date(2021, 1, 1), dt.date(2021, 12, 31), dt.date(2022, 1, 1), dt.date(2022, 1, 2), dt.date(2022, 5, 10),
          dt.date(2022, 11, 9), dt.date(2023, 1, 1), dt.date(2024, 1, 1), dt.date(2024, 1, 7), dt.date(2024, 9, 10), dt.date(2025, 1, 1),
          dt.date(2025, 5, 21), dt.date(2026, 1, 1)]
rows = sorted(set(rand_rows + [P.idx[d] for d in picked if d in P.idx]))

SPECS = ["UNI-1", "UNI-1__quarterly", "UNI-1__age121", "UNI-1__N12"]
CADS = (vu.DAILY, vu.WEEKLY)


def cut(P, t):
    return data.Panel(P.dates[:t + 1], list(P.coins), P.O[:t + 1], P.H[:t + 1], P.L[:t + 1], P.C[:t + 1], P.V[:t + 1], P.F[:t + 1], P.Q[:t + 1])


def perturb(P, t, seed):
    """Rows > t: closes replaced by an independent random walk from C[t] (or random level where C[t] is NaN), Q by random lognormal
    (with random zeros and NaNs), F by random noise; rows <= t unchanged."""
    r = np.random.default_rng(seed)
    C = P.C.copy(); Q = P.Q.copy(); F = P.F.copy()
    n = T - t - 1
    base = np.where(np.isfinite(P.C[t]), P.C[t], r.uniform(0.1, 100, P.C.shape[1]))
    walk = base * np.exp(np.cumsum(r.normal(0, 0.2, (n, P.C.shape[1])), axis=0))
    mask_nan = r.random((n, P.C.shape[1])) < 0.1
    C[t + 1:] = np.where(mask_nan, np.nan, walk)
    Q[t + 1:] = np.where(r.random((n, P.C.shape[1])) < 0.1, 0.0, np.exp(r.normal(15, 3, (n, P.C.shape[1]))))
    F[t + 1:] = r.normal(0, 0.003, (n, P.C.shape[1]))
    return data.Panel(P.dates, list(P.coins), C.copy(), C.copy(), C.copy(), C, P.V, F, Q)


full = {}
for name in SPECS:
    for cad in CADS:
        ctx = vu._ctx(P)
        U, _ = vu._membership(ctx, cad, vu.SPECS[name])
        W = vu._weights(ctx, cad, U)
        r = vu._sim(ctx, W, vu._kw(ctx, cad))
        full[(name, cad["name"])] = (U, W, r)

fails = []
n_checks = 0
for t in rows:
    d = P.dates[t]
    for mode in ("cut", "perturb"):
        Pt = cut(P, t) if mode == "cut" else perturb(P, t, seed=t)
        ctx_t = vu._ctx(Pt)
        for name in SPECS:
            for cad in CADS:
                Uf, Wf, rf = full[(name, cad["name"])]
                Ut, _ = vu._membership(ctx_t, cad, vu.SPECS[name])
                Wt = vu._weights(ctx_t, cad, Ut)
                okU = np.array_equal(Ut[:t + 1], Uf[:t + 1])
                okW = np.array_equal(Wt[:t + 1], Wf[:t + 1])
                # returns: simulate with end = d on the cut/perturbed panel; compare rets dated <= d.
                # Expected exception: the last row d itself on the CUT panel -- nothing; rets dated d use valid_next[d] (row d exists).
                kw = vu._kw(ctx_t, cad); kw["end"] = d
                rt = vu._sim(ctx_t, Wt, kw)
                fd = [x for x in rf["dates"] if x <= d]
                k = len(fd)
                # the full-panel return dated d depends on whether coins have a close at d+1 (sim's valid_next look-ahead) only
                # through 'new' at row d-1 -> it is valid_next[d]; so rets dated <= d should match exactly
                okR = len(rt["rets"]) == k and np.allclose(rt["rets"], rf["rets"][:k], atol=1e-15, rtol=0)
                n_checks += 1
                if not (okU and okW and okR):
                    dW = float(np.max(np.abs(Wt[:t + 1] - Wf[:t + 1])))
                    dR = float(np.max(np.abs(rt["rets"] - rf["rets"][:k]))) if len(rt["rets"]) == k else float("nan")
                    bad = np.flatnonzero(np.any(Wt[:t + 1] != Wf[:t + 1], axis=1))
                    fails.append((mode, str(d), name, cad["name"], okU, okW, okR, dW, dR, [str(P.dates[i]) for i in bad[:5]]))
        vu._CTX.pop(Pt, None)
    print(f"{d} done; fails so far {len(fails)}", flush=True)

print(f"\ncut rows: {[str(P.dates[t]) for t in rows]}")
print(f"checks: {n_checks} (rows {len(rows)} x 2 modes x {len(SPECS)} cells x 2 cadences); failures: {len(fails)}")
for f in fails:
    print("FAIL", f)

# The simulator's own one-row look-ahead: rows where a held coin is flattened because C[t+1] is NaN on the cleaned panel.
print("\nSimulator one-row look-ahead (position forced to 0 at close t because row t+1 has no close/Q>0), UNI-1:")
ctx = vu._ctx(P)
for cad in CADS:
    U, W, r = full[("UNI-1", cad["name"])]
    Cc = ctx.Cc
    ev = []
    for j in np.flatnonzero(np.abs(W).sum(axis=0) > 0):
        for t in range(T - 1):
            if W[t, j] != 0 or (t > 0 and W[t - 1, j] != 0):
                if np.isfinite(Cc[t, j]) and not np.isfinite(Cc[t + 1, j]) and vu.A0 <= P.dates[t] <= vu.A1:
                    nxt = t + 1
                    while nxt < T and not np.isfinite(Cc[nxt, j]):
                        nxt += 1
                    reopen = P.dates[nxt] if nxt < T else None
                    gapret = Cc[nxt, j] / Cc[t, j] - 1 if nxt < T else float("nan")
                    ev.append((ctx.coins[j], str(P.dates[t]), float(W[t - 1, j]), float(W[t, j]), str(reopen), float(gapret)))
    print(f"  {cad['name']}: {len(ev)} forced flattens on rows the book holds or targets")
    for e in ev:
        print("   ", e)
