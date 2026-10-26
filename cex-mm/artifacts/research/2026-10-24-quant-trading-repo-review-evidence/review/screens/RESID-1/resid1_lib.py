#!/usr/bin/env python3
"""RESID-1 engine: BTC-hedged 'co-movement break, follow it' (spec.md in this folder). Own code; nothing from the external repo."""
from __future__ import annotations
import datetime as dt, math, os, re
import numpy as np
import pandas as pd

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
HERE = f"{SP}/ext_repo/review/screens/RESID-1"
CACHE_DIR = f"{HERE}/cache"
FUND_CACHES = [f"{SP}/trend-cache", f"{SP}/av_cache", f"{SP}/universe/cache", f"{SP}/universe/cache_all"]
DAY = 86_400_000
H = 3_600_000
EPOCH = dt.date(1970, 1, 1)


def day_ms(d: dt.date) -> int:
    return (d - EPOCH).days * DAY


def ms_day(t: int) -> dt.date:
    return EPOCH + dt.timedelta(days=int(t // DAY))


# ------------------------------------------------------------------ data
class Coin:
    """Bars of one coin: t (open ms, int64), o, c (float), bar (ms). Derived daily C[D], P01[D]."""

    def __init__(self, name, t, o, c, bar):
        self.name, self.t, self.o, self.c, self.bar = name, t, o, c, bar
        self.first_t, self.last_close_t = int(t[0]), int(t[-1]) + bar
        self.fund_t = np.zeros(0, dtype=np.int64)
        self.fund_r = np.zeros(0)
        self.fund_missing_months = set()
        self._C, self._P01 = {}, {}
        self._build_daily()

    def _idx(self, ts):
        i = np.searchsorted(self.t, ts)
        return i if i < len(self.t) and self.t[i] == ts else -1

    def _build_daily(self):
        d0, d1 = ms_day(self.t[0]), ms_day(self.t[-1]) + dt.timedelta(days=1)
        d = d0
        while d <= d1:
            D = day_ms(d)
            # C[D]: bar opening D - bar (closes at 00:00 D); fallback: last bar opening in [D-1 23:00, D - bar]
            i = self._idx(D - self.bar)
            if i < 0:
                j = np.searchsorted(self.t, D - self.bar, side="right") - 1
                if j >= 0 and self.t[j] >= D - H:
                    i = j
            if i >= 0:
                self._C[d] = float(self.c[i])
            # P01[D]: bar opening D 01:00 - bar (closes at 01:00); exact only (fallback handled by fill())
            k = self._idx(D + H - self.bar)
            if k >= 0:
                self._P01[d] = float(self.c[k])
            d += dt.timedelta(days=1)

    def C(self, d):
        return self._C.get(d)

    def P01(self, d):
        return self._P01.get(d)

    def fill(self, d):
        """(price, fill_time_ms, fallback) at 01:00 UTC of d, else the first later bar close on d; None if none."""
        p = self._P01.get(d)
        D = day_ms(d)
        if p is not None:
            return p, D + H, False
        lo = D + H - self.bar
        j = np.searchsorted(self.t, lo, side="right")
        if j < len(self.t) and self.t[j] <= D + DAY - self.bar:
            return float(self.c[j]), int(self.t[j]) + self.bar, True
        return None

    def price_at(self, ts):
        """Open of the bar opening at floor(ts / bar) * bar; fallback: the last close at or before ts."""
        b = (ts // self.bar) * self.bar
        i = self._idx(b)
        if i >= 0:
            return float(self.o[i])
        j = np.searchsorted(self.t, ts - self.bar, side="right") - 1
        return float(self.c[j]) if j >= 0 else None

    def last_close_before(self, ts):
        j = np.searchsorted(self.t, ts - self.bar, side="right") - 1
        return (float(self.c[j]), int(self.t[j]) + self.bar) if j >= 0 else None

    def funding_between(self, lo, hi):
        """Stamps s with lo < s < hi: list of (s, rate)."""
        a = np.searchsorted(self.fund_t, lo, side="right")
        b = np.searchsorted(self.fund_t, hi, side="left")
        return list(zip(self.fund_t[a:b].tolist(), self.fund_r[a:b].tolist()))


def _read_bars(files, cache_key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = f"{CACHE_DIR}/{cache_key}.npz"
    if os.path.exists(cp):
        z = np.load(cp)
        return z["t"], z["o"], z["c"]
    ts, os_, cs = [], [], []
    for fn in sorted(files):
        with open(fn) as f:
            first = f.readline()
        if not first.strip():
            continue
        hdr = 0 if not first[0].isdigit() else None
        df = pd.read_csv(fn, header=hdr, usecols=[0, 1, 4])
        df.columns = ["t", "o", "c"]
        t = df["t"].to_numpy(dtype=np.int64)
        t = np.where(t > 10**14, t // 1000, t)
        ts.append(t); os_.append(df["o"].to_numpy(float)); cs.append(df["c"].to_numpy(float))
    t = np.concatenate(ts); o = np.concatenate(os_); c = np.concatenate(cs)
    order = np.argsort(t, kind="stable")
    t, o, c = t[order], o[order], c[order]
    keep = np.ones(len(t), bool); keep[1:] = t[1:] != t[:-1]
    t, o, c = t[keep], o[keep], c[keep]
    np.savez(cp, t=t, o=o, c=c)
    return t, o, c


def load_funding(coin: Coin, sym: str):
    seen, rows = set(), []
    for cache in FUND_CACHES:
        if not os.path.isdir(cache):
            continue
        for fn in sorted(os.listdir(cache)):
            if not fn.startswith(f"binance-{sym}-fundingRate-") or fn in seen:
                continue
            seen.add(fn)
            with open(os.path.join(cache, fn)) as f:
                for line in f:
                    p = line.strip().split(",")
                    if not p or not p[0].isdigit():
                        continue
                    rows.append((int(p[0]), float(p[2])))
    rows.sort()
    coin.fund_t = np.array([r[0] for r in rows], dtype=np.int64)
    coin.fund_r = np.array([r[1] for r in rows], dtype=float)
    coin.fund_months = {m.group(1) for fn in seen for m in [re.search(r"(\d{4}-\d{2})\.csv$", fn)] if m}
    return coin


def load_5m_dir(folder, prefix, sym, name, bar=300_000, with_funding=True, months=None):
    files = [os.path.join(folder, f) for f in os.listdir(folder)
             if f.startswith(f"{prefix}{sym}-") and f.endswith(".csv") and os.path.isfile(os.path.join(folder, f))]
    if months:
        files = [f for f in files if re.search(r"(\d{4}-\d{2})\.csv$", f).group(1) in months]
    key = re.sub(r"[^A-Za-z0-9]", "_", f"{folder.split('scratchpad/')[-1]}_{prefix}{sym}_{bar}_{len(files)}")
    t, o, c = _read_bars(files, key)
    coin = Coin(name, t, o, c, bar)
    if with_funding:
        load_funding(coin, sym)
    else:
        coin.fund_months = set()
    return coin


# ------------------------------------------------------------------ rule + book
class Params:
    def __init__(self, train=50, r2=0.70, k=2.0, hold=10, cost_bps=7.31, fill="p01", refit_daily=False, hedged=True,
                 funding=True):
        self.train, self.r2, self.k, self.hold, self.cost_bps = train, r2, k, hold, cost_bps
        self.fill, self.refit_daily, self.hedged, self.funding = fill, refit_daily, hedged, funding


def ols(y, x):
    n = len(y)
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    if sxx <= 0:
        return None
    b = ((x - xm) * (y - ym)).sum() / sxx
    a = ym - b * xm
    e = y - (a + b * x)
    sst = ((y - ym) ** 2).sum()
    r2 = 1.0 - (e ** 2).sum() / sst if sst > 0 else 0.0
    return a, b, r2, float(np.std(e))  # np.std ddof 0, as the repo


class Leg:
    __slots__ = ("coin", "units", "entry_px", "entry_t", "mark", "exit_px", "exit_t", "fund", "cost", "fallback")

    def __init__(self, coin, units, px, t, fb):
        self.coin, self.units, self.entry_px, self.entry_t, self.mark = coin, units, px, t, px
        self.exit_px = self.exit_t = None
        self.fund = 0.0; self.cost = 0.0; self.fallback = fb


class AltState:
    def __init__(self, coin):
        self.coin = coin
        self.holding, self.trained, self.counter = 0, False, 0
        self.a = self.b = self.sigma = self.r2 = None
        self.pending_exit = False
        self.trade = None  # dict with legs


def _fill(coin, d, p: Params):
    if p.fill == "close":
        c = coin.C(d)
        return (c, day_ms(d), False) if c is not None else None
    return coin.fill(d)


def simulate(alts: list, X: Coin, start: dt.date, end: dt.date, p: Params, n_alts: int):
    """Returns dict(dates, rets, pnl, trades, counters)."""
    states = [AltState(a) for a in alts]
    days = []
    d = start
    while d <= end:
        days.append(d); d += dt.timedelta(days=1)
    E = 1.0
    out_r, out_pnl, out_E, trades = [], [], [], []
    cnt = {"fallback_fills": 0, "skipped_entries": 0, "pending_exits": 0, "forced_end": 0, "forced_delist": 0,
           "skipped_days": 0, "fits": 0, "fits_ok": 0}
    cost = p.cost_bps / 1e4

    def close_trade(st, d, how):
        tr = st.trade
        tr["exit_date"] = d; tr["exit_how"] = how
        gross = sum(l.units * (l.exit_px - l.entry_px) for l in tr["legs"])
        fund = sum(l.fund for l in tr["legs"]); cst = sum(l.cost for l in tr["legs"])
        tr["gross"], tr["fund"], tr["cost"] = gross, fund, cst
        tr["net"] = gross + fund - cst
        N = tr["N"]
        tr["net_bps"], tr["gross_bps"], tr["fund_bps"], tr["cost_bps"] = (1e4 * tr["net"] / N, 1e4 * gross / N,
                                                                          1e4 * fund / N, 1e4 * cst / N)
        trades.append(tr)
        st.trade = None

    for d in days:
        E_prev = E
        pnl = 0.0
        t_mark = day_ms(d) + H
        t_prev = t_mark - DAY
        last_day = d == days[-1]
        for st in states:
            Y = st.coin
            exit_now = None  # (how)
            # ---- forced exit on delisting: alt has no data at or after 01:00 d
            if st.holding != 0 and Y.last_close_t < t_mark and Y.fill(d) is None:
                exit_now = "delist"
            # ---- decision
            entered = None
            if exit_now is None:
                cy, cx = Y.C(d), X.C(d)
                if st.holding != 0:
                    if st.pending_exit or st.counter > p.hold:
                        exit_now = "time"
                    elif cy is None or cx is None:
                        cnt["skipped_days"] += 1
                    else:
                        st.counter += 1
                elif cy is None or cx is None:
                    if day_ms(d) > Y.first_t + DAY and day_ms(d) > X.first_t + DAY and day_ms(d) < Y.last_close_t:
                        cnt["skipped_days"] += 1
                else:
                    if (not st.trained) or p.refit_daily:
                        ys, xs, ok = [], [], True
                        for k in range(p.train, 0, -1):
                            dd = d - dt.timedelta(days=k)
                            a_, b_ = Y.C(dd), X.C(dd)
                            if a_ is None or b_ is None:
                                ok = False; break
                            ys.append(a_); xs.append(b_)
                        if ok:
                            cnt["fits"] += 1
                            res = ols(np.log(np.array(ys)), np.log(np.array(xs)))
                            if res is not None and res[2] > p.r2:
                                cnt["fits_ok"] += 1
                                st.trained = True
                                st.a, st.b, st.r2, st.sigma = res
                            elif p.refit_daily:
                                st.trained = False
                        elif p.refit_daily:
                            st.trained = False
                    if st.trained:
                        f = st.a + st.b * math.log(cx)
                        ly = math.log(cy)
                        s = 1 if ly > f + p.k * st.sigma else (-1 if ly < f - p.k * st.sigma else 0)
                        if s != 0:
                            fy = _fill(Y, d, p)
                            fx = _fill(X, d, p) if p.hedged else (1.0, 0, False)
                            if fy is None or fx is None:
                                cnt["skipped_entries"] += 1
                            else:
                                entered = (s, fy, fx)
            if last_day and st.holding != 0 and exit_now is None:
                exit_now = "end"
            # ---- open legs: mark / funding / exit
            if st.trade is not None:
                fills = {}
                if exit_now == "delist":
                    lc = Y.last_close_before(Y.last_close_t + 1)
                    tf = lc[1]
                    fills[Y.name] = (lc[0], tf, False)
                    if p.hedged:
                        fills[X.name] = (X.price_at(tf) if X.price_at(tf) is not None else X.last_close_before(tf)[0], tf, False)
                elif exit_now in ("time", "end"):
                    fy = _fill(Y, d, p)
                    fx = _fill(X, d, p) if p.hedged else (1.0, 0, False)
                    if fy is None or fx is None:
                        if exit_now == "end":
                            fy = fy or (st.trade["legs"][0].mark, t_mark, True)
                            fx = fx or ((st.trade["legs"][1].mark if p.hedged else 1.0), t_mark, True)
                            fills[Y.name] = fy
                            if p.hedged:
                                fills[X.name] = fx
                        else:
                            st.pending_exit = True; cnt["pending_exits"] += 1
                            exit_now = None
                    else:
                        fills[Y.name] = fy
                        if p.hedged:
                            fills[X.name] = fx
                for leg in st.trade["legs"]:
                    if exit_now is not None:
                        px, tx, fb = fills[leg.coin.name]
                        if fb:
                            cnt["fallback_fills"] += 1
                        pnl += leg.units * (px - leg.mark)
                        if p.funding:
                            for s_, r_ in leg.coin.funding_between(max(leg.entry_t, t_prev), tx):
                                ps = leg.coin.price_at(s_)
                                cf = -leg.units * ps * r_
                                leg.fund += cf; pnl += cf
                        c_ = cost * abs(leg.units) * px
                        leg.cost += c_; pnl -= c_
                        leg.exit_px, leg.exit_t, leg.mark = px, tx, px
                    else:
                        m = leg.coin.P01(d) if p.fill == "p01" else leg.coin.C(d)
                        if m is not None:
                            pnl += leg.units * (m - leg.mark); leg.mark = m
                        if p.funding:
                            for s_, r_ in leg.coin.funding_between(max(leg.entry_t, t_prev), t_mark + 1):
                                ps = leg.coin.price_at(s_)
                                cf = -leg.units * ps * r_
                                leg.fund += cf; pnl += cf
                if exit_now is not None:
                    if exit_now == "end":
                        cnt["forced_end"] += 1
                    if exit_now == "delist":
                        cnt["forced_delist"] += 1
                    close_trade(st, d, exit_now)
                    st.holding, st.trained, st.counter, st.pending_exit = 0, False, 0, False
            # ---- new entry
            if entered is not None:
                s, fy, fx = entered
                N = E_prev / n_alts
                legs = []
                uy = s * N / fy[0]
                ly_ = Leg(Y, uy, fy[0], fy[1], fy[2]); legs.append(ly_)
                if p.hedged:
                    ux = -s * st.b * N / fx[0]
                    legs.append(Leg(X, ux, fx[0], fx[1], fx[2]))
                for leg in legs:
                    if leg.fallback:
                        cnt["fallback_fills"] += 1
                    c_ = cost * abs(leg.units) * leg.entry_px
                    leg.cost += c_; pnl -= c_
                st.trade = {"alt": Y.name, "side": s, "entry_date": d, "N": N, "a": st.a, "b": st.b, "r2": st.r2,
                            "sigma": st.sigma, "legs": legs}
                st.holding, st.counter = s, 0
                if last_day:  # entered on the last day: closed at once at the same prices (costs only)
                    for leg in legs:
                        c_ = cost * abs(leg.units) * leg.entry_px
                        leg.cost += c_; pnl -= c_
                        leg.exit_px, leg.exit_t = leg.entry_px, leg.entry_t
                    cnt["forced_end"] += 1
                    close_trade(st, d, "end")
                    st.holding, st.trained, st.counter = 0, False, 0
        E = E_prev + pnl
        out_r.append(pnl / E_prev); out_pnl.append(pnl); out_E.append(E)
    return {"dates": days, "rets": np.array(out_r), "pnl": np.array(out_pnl), "equity": np.array(out_E), "trades": trades,
            "cnt": cnt}


# ------------------------------------------------------------------ metrics
def sharpe(r):
    r = np.asarray(r, float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(365))


def maxdd(r):
    eq = np.cumprod(1 + np.asarray(r))
    pk = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((eq / pk - 1).min())


def cagr(r):
    eq = float(np.prod(1 + np.asarray(r)))
    yrs = len(r) / 365.25
    return eq ** (1 / yrs) - 1 if eq > 0 else -1.0


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def week_bootstrap_trades(trades, start, end, draws=2000, seed=11):
    weeks = []
    w = monday(start)
    while w <= end:
        weeks.append(w); w += dt.timedelta(days=7)
    widx = {w: i for i, w in enumerate(weeks)}
    S = np.zeros(len(weeks)); Cn = np.zeros(len(weeks))
    for t in trades:
        i = widx[monday(t["entry_date"])]
        S[i] += t["net_bps"]; Cn[i] += 1
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(weeks), size=(draws, len(weeks)))
    ss, cc = S[idx].sum(1), Cn[idx].sum(1)
    means = np.where(cc > 0, ss / np.maximum(cc, 1), 0.0)
    return float((means <= 0).mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def week_bootstrap_sharpe(dates, rets, draws=2000, seed=11):
    wk = {}
    for d, r in zip(dates, rets):
        wk.setdefault(monday(d), []).append(r)
    blocks = [np.array(v) for _, v in sorted(wk.items())]
    rng = np.random.default_rng(seed)
    out = np.empty(draws)
    for k in range(draws):
        ii = rng.integers(0, len(blocks), size=len(blocks))
        x = np.concatenate([blocks[i] for i in ii])
        out[k] = x.mean() / x.std(ddof=1) * math.sqrt(365) if x.std(ddof=1) > 0 else 0.0
    return float((out <= 0).mean())


def sub_r(res, a, b):
    m = np.array([a <= d <= b for d in res["dates"]])
    return res["rets"][m]


def summarize(res, start, end, halves, alts_names, label=""):
    tr = res["trades"]
    net = np.array([t["net_bps"] for t in tr]) if tr else np.zeros(0)
    days = (end - start).days + 1
    out = {"label": label, "n_trades": len(tr), "trades_per_year": len(tr) / (days / 365.25),
           "mean_net_bps": float(net.mean()) if len(net) else float("nan"),
           "median_net_bps": float(np.median(net)) if len(net) else float("nan"),
           "hit": float((net > 0).mean()) if len(net) else float("nan"),
           "mean_gross_bps": float(np.mean([t["gross_bps"] for t in tr])) if tr else float("nan"),
           "mean_cost_bps": float(np.mean([t["cost_bps"] for t in tr])) if tr else float("nan"),
           "mean_fund_bps": float(np.mean([t["fund_bps"] for t in tr])) if tr else float("nan"),
           "mean_abs_b": float(np.mean([abs(t["b"]) for t in tr])) if tr else float("nan"),
           "sharpe": sharpe(res["rets"]), "cagr": cagr(res["rets"]), "maxdd": maxdd(res["rets"])}
    P, lo, hi = week_bootstrap_trades(tr, start, end)
    out["boot_P"], out["boot_ci"] = P, (lo, hi)
    hv = []
    for a, b in halves:
        x = [t["net_bps"] for t in tr if a <= t["entry_date"] <= b]
        hv.append((str(a), str(b), len(x), float(np.mean(x)) if x else float("nan")))
    out["halves"] = hv
    per = {}
    for nm in alts_names:
        x = [t["net_bps"] for t in tr if t["alt"] == nm]
        per[nm] = (len(x), float(np.mean(x)) if x else float("nan"))
    out["per_alt"] = per
    out["alts_pos"] = sum(1 for nm in alts_names if per[nm][0] > 0 and per[nm][1] > 0)
    sides = {}
    for s in (1, -1):
        x = [t["net_bps"] for t in tr if t["side"] == s]
        sides[s] = (len(x), float(np.mean(x)) if x else float("nan"))
    out["sides"] = sides
    yrs = {}
    for y in range(start.year, end.year + 1):
        r = sub_r(res, max(start, dt.date(y, 1, 1)), min(end, dt.date(y, 12, 31)))
        x = [t["net_bps"] for t in tr if t["entry_date"].year == y]
        yrs[y] = (float(np.prod(1 + r) - 1) if len(r) else float("nan"), len(x), float(np.mean(x)) if x else float("nan"))
    out["years"] = yrs
    gp = sum(t["gross"] for t in tr); fp = sum(t["fund"] for t in tr); cp = sum(t["cost"] for t in tr)
    out["sum_gross"], out["sum_fund"], out["sum_cost"] = gp, fp, cp
    out["cnt"] = res["cnt"]
    return out


def fmt(s):
    L = [f"== {s['label']}",
         f"  trades {s['n_trades']}  per year {s['trades_per_year']:.1f}  mean net {s['mean_net_bps']:+.1f} bps  median {s['median_net_bps']:+.1f}"
         f"  hit {s['hit']:.1%}  (gross {s['mean_gross_bps']:+.1f}, cost -{s['mean_cost_bps']:.1f}, funding {s['mean_fund_bps']:+.1f}; mean |b| {s['mean_abs_b']:.2f})",
         f"  week-cluster bootstrap (2000, rng 11): one-sided P(mean<=0) = {s['boot_P']:.4f}; 95% CI {s['boot_ci'][0]:+.1f}..{s['boot_ci'][1]:+.1f} bps",
         f"  daily: Sharpe {s['sharpe']:.3f}  CAGR {s['cagr']:+.2%}  maxDD {s['maxdd']:.2%}",
         "  halves: " + "; ".join(f"{a}..{b}: n {n}, mean {m:+.1f}" for a, b, n, m in s["halves"]),
         "  per alt: " + ", ".join(f"{k} {n}/{m:+.0f}" for k, (n, m) in s["per_alt"].items()) + f"  -> alts with mean > 0: {s['alts_pos']}",
         "  sides: " + ", ".join(f"{'long-alt' if k == 1 else 'short-alt'} n {n} mean {m:+.1f}" for k, (n, m) in s["sides"].items()),
         "  years (book return, trades, mean net bps): " + "; ".join(f"{y} {r:+.1%} {n} {m:+.0f}" for y, (r, n, m) in s["years"].items()),
         f"  sums (equity units): gross {s['sum_gross']:+.4f} funding {s['sum_fund']:+.4f} cost -{s['sum_cost']:.4f}",
         f"  counters: {s['cnt']}"]
    return "\n".join(L)
