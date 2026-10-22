#!/usr/bin/env python3
"""Independent rebuild of UNI-1 (plan 6.3) on the Bw survivorship-free pool, written from the plan text only.
Uses data.load_binance, sim.simulate, rules primitives (signal/vol/rolling_valid/decide_weekly); universe logic is new."""
import sys, json, datetime as dt, math
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools2")
import numpy as np, data, sim, rules

SP = data.SP
A0, A1 = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
POST = dt.date(2022, 1, 1)
H1 = (dt.date(2020, 5, 1), dt.date(2023, 12, 31)); H2 = (dt.date(2024, 1, 1), dt.date(2026, 9, 30))
DAILY = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)
WEEKLY = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)

# non-crypto / excluded tags (metals, commodities, xStocks/ETFs, stablecoins, composite indices)
EXCL = set("XAU XAG XPD XPT XAUT PAXG COPPER NATGAS CL BZ "
           "AAPL AMZN AVGO BABA COIN CRCL GOOGL HOOD INTC META MSFT MSTR MU NVDA PLTR QQQ SPY TSLA TSM EWJ EWY SNDK PAYP "
           "USDC BTCDOM DEFI BLUEBIRD FOOTBALL".split())

_P = {}
def load():
    if "p" not in _P:
        pool = json.load(open(f"{SP}/universe/pool_all.json"))
        _P["p"] = data.load_binance(coins=pool)
    return _P["p"]


def d0_panel(p):
    """D-0: candidate on day d only if quote_volume(d) > 0; delisting day = last day with qv > 0, closes after it are removed
    (so sim flattens at that close at taker cost). Returns (panel_with_trimmed_C, cand mask)."""
    C = p.C.copy(); Q = p.Q
    qpos = np.isfinite(Q) & (Q > 0) & np.isfinite(C)
    T, N = C.shape
    last = np.full(N, -1)
    for j in range(N):
        ii = np.where(qpos[:, j])[0]
        if len(ii):
            last[j] = ii[-1]
            C[ii[-1] + 1:, j] = np.nan
        else:
            C[:, j] = np.nan
    q = data.Panel(p.dates, p.coins, p.O, p.H, p.L, C, p.V, p.F, p.Q)
    return q, qpos, last


def med30(Q, t, win=30):
    w = Q[max(0, t - win + 1):t + 1]
    w = np.where(np.isfinite(w), w, np.nan)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.nanmedian(w, axis=0)


def universe(p, qpos, last, *, n=9, keep_rank=18, age_min=365, reset_rows=None, rank_pop="eligible", start_elig="any",
             age_applies_to_incumbents=False, start_date=dt.date(2020, 4, 30), continuous_hyst=False, log=None, med_win=30, rank_lag=0):
    """Membership mask (T,N). reset_rows: list of row indices where the universe is re-formed (yearly January).
    rank_pop: 'eligible' = rank among crypto candidates with age >= age_min (incumbents ranked within that set plus themselves);
              'all' = rank among all crypto candidates (any age).
    start_elig: eligibility for the 2020-04-30 start set: 'any' (any crypto candidate), 'sig121' (121 closes)."""
    C, Q = p.C, p.Q
    T, N = C.shape
    age = np.cumsum(np.isfinite(p.C), axis=0)  # closes so far (trimmed panel)
    crypto = np.array([c not in EXCL for c in p.coins])
    mask = np.zeros((T, N), bool)
    cur = np.zeros(N, bool)
    t0 = p.idx[start_date]
    resets = set(reset_rows)
    for t in range(T):
        if t < t0:
            continue
        cand = qpos[t] & crypto
        if t == t0:
            m = med30(Q, t - rank_lag, med_win)
            el = cand & np.isfinite(m)
            if start_elig == "sig121":
                el &= age[t] >= 121
            order = np.argsort(-np.where(el, m, -np.inf), kind="stable")
            cur = np.zeros(N, bool); cur[order[:n]] = el[order[:n]]
            if log is not None: log.append((p.dates[t], "start", [p.coins[j] for j in np.where(cur)[0]]))
        elif t in resets or continuous_hyst:
            m = med30(Q, t - rank_lag, med_win)
            elig_new = cand & np.isfinite(m) & (age[t] >= age_min)
            inc = cur & cand & np.isfinite(m)
            if age_applies_to_incumbents:
                inc &= age[t] >= age_min
            if rank_pop == "eligible":
                pop = elig_new | inc
            else:
                pop = cand & np.isfinite(m)
            score = np.where(pop, m, -np.inf)
            order = np.argsort(-score, kind="stable")
            rank = np.empty(N, int); rank[order] = np.arange(1, N + 1)
            keep = inc & (rank <= keep_rank)
            if t in resets:
                new = keep.copy()
                for j in order:
                    if new.sum() >= n:
                        break
                    if elig_new[j] and not new[j]:
                        new[j] = True
                if log is not None:
                    log.append((p.dates[t], "reset", [p.coins[j] for j in np.where(new)[0]],
                                {"dropped": [p.coins[j] for j in np.where(cur & ~new)[0]], "added": [p.coins[j] for j in np.where(new & ~cur)[0]],
                                 "inc_ranks": {p.coins[j]: int(rank[j]) for j in np.where(cur)[0]}}))
                cur = new
            else:  # continuous hysteresis between resets: drop incumbents ranked > keep_rank, no replacement
                cur = cur & (keep | ~(cand & np.isfinite(m)))
        # delisting: a member past its last qv>0 day goes flat, not replaced
        cur = cur & (np.arange(T)[t] <= last)
        mask[t] = cur
    return mask


def weights(p, qpos, mask, cad, nmode="valid", umask_size=None):
    """sig * (TV/N)/max(vol60, 0.05), gross cap; N = members with 121 closes (nmode 'valid') or |U| at the reset ('U')."""
    C = p.C
    valid121 = rules.rolling_valid(C, 121)
    sig = np.nan_to_num(np.maximum(rules.sig_sign_mean(C, (20, 60, 120)), 0.0))
    vol = np.nan_to_num(rules.vol_cc(C, 60), nan=np.inf)
    ok = mask & valid121 & qpos
    if nmode == "valid":
        n = np.maximum(ok.sum(axis=1, keepdims=True), 1)
    elif nmode == "U":
        n = np.maximum(umask_size[:, None], 1)
    elif nmode == "U9":
        n = np.full((len(C), 1), 9.0)
    w = np.where(ok, sig * (cad["tv"] / n) / np.maximum(vol, 0.05), 0.0)
    w = np.nan_to_num(w)
    g = np.abs(w).sum(axis=1, keepdims=True)
    return np.where(g > cad["max_gross"], w * cad["max_gross"] / np.maximum(g, 1e-12), w)


def run(p, W, cad):
    kw = dict(decide=rules.decide_weekly(p.dates, 6) if cad["weekly"] else None, band=cad["band"], start=A0, end=A1)
    return sim.simulate(p, W, **kw)


def summarize(r, b=None):
    out = {}
    for wn, (a, bb) in {"full": (None, None), "post": (POST, None), "h1": H1, "h2": H2}.items():
        s = sim.stats(r, a, bb)
        rec = dict(sharpe=s["sharpe"], vol=s["vol"], mdd=s["mdd"], cagr=s["cagr"], gross=s["gross"], turnover=s["turnover"], worst7=s["worst7"], yearly=s["yearly"])
        if b is not None:
            d = np.array(r["dates"]); m = np.ones(len(d), bool)
            if a: m &= d >= a
            if bb: m &= d <= bb
            bs = sim.block_bootstrap_diff(r["rets"][m], b["rets"][m])
            rec.update(delta=bs[0], ci=[bs[1], bs[2]], p_le0=bs[3])
        out[wn] = rec
    return out


def reset_rows_for(p, cad, mode="calendar"):
    rows = []
    for y in range(2021, 2027):
        if mode == "calendar" or not cad["weekly"]:
            rows.append(p.idx[dt.date(y, 1, 1)])
        else:  # first Sunday candle in January
            d = dt.date(y, 1, 1)
            while d.weekday() != 6:
                d += dt.timedelta(days=1)
            rows.append(p.idx[d])
    return rows
