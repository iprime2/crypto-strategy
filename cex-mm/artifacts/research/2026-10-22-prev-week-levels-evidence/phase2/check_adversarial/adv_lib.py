"""Adversarial review helpers (separate code, written from phase2_plan.md + plan.md; nothing imported from p2/run).

Loads raw Binance 5 m CSVs read-only, rebuilds T events (real, P1, P3) with configurable trigger / coverage / fill,
and recomputes the four gating numbers with the Phase 1 week-cluster bootstrap (2,000 draws, default_rng(11)).
"""
import glob
import math
import os

import numpy as np
import pandas as pd

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
RUN = f"{SP}/research3/p2/run"
BAR = 300_000
H = 3_600_000
D = 24 * H
WK = 7 * D
MON0 = 4 * D  # 1970-01-05 is a Monday
HZ = {"1h": H, "4h": 4 * H, "24h": D}
MULTS = (0.5, 0.75, 1.25, 1.5)
OT_COINS = ["BTC", "ETH", "BNB", "LTC", "NEO", "XRP", "ADA", "EOS", "XLM", "TRX", "ETC", "LINK", "DOGE"]
OX_COINS = ["1000SHIB", "SOL", "SAND", "LUNA", "MANA", "DOT", "AVAX", "FTM", "MATIC", "GALA", "AXS", "DYDX", "FIL",
            "LRC", "CRV"]


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").value // 10**6)


def monday(t):
    t = np.asarray(t, dtype=np.int64)
    return (t - MON0) // WK * WK + MON0


def _read(path):
    with open(path) as fh:
        c0 = fh.read(1)
    df = pd.read_csv(path, header=None if c0.isdigit() else 0)
    a = df.iloc[:, [0, 1, 2, 3, 4, 5, 8]].to_numpy()
    t = a[:, 0].astype(np.int64)
    t = np.where(t > 10**14, t // 1000, t)
    return t, a[:, 1:6].astype(float), a[:, 6].astype(float)


def load(panel, sym):
    if panel == "OT":
        files = sorted(glob.glob(f"{SP}/universe/spot5m/binance-spot-{sym}USDT-5m-*.csv"))
        cap = ts("2020-05-01")
    else:
        files = sorted(glob.glob(f"{SP}/universe/ox5m/binance-{sym}USDT-5m-*.csv"))
        cap = ts("2026-10-01")
    parts = [_read(f) for f in files]
    t = np.concatenate([p[0] for p in parts])
    x = np.concatenate([p[1] for p in parts])
    n = np.concatenate([p[2] for p in parts])
    order = np.argsort(t, kind="stable")
    t, x, n = t[order], x[order], n[order]
    keep = np.r_[True, t[1:] != t[:-1]]
    t, x, n = t[keep], x[keep], n[keep]
    k = t < cap
    t, x, n = t[k], x[k], n[k]
    eff_end = None
    if panel == "OX":  # cut after the last traded bar (post-delisting flat placeholders are not data)
        last = t[x[:, 4] > 0].max()
        eff_end = int(last) + BAR
        k = t < eff_end
        t, x, n = t[k], x[k], n[k]
    return dict(t=t, o=x[:, 0], h=x[:, 1], l=x[:, 2], c=x[:, 3], v=x[:, 4], n=n, end=int(t[-1]) + BAR,
                eff_end=eff_end)


class Eng:
    """T events for one coin. trigger: 'tol' (high > L(1+0.5bp), the plan) or 'ge' (high >= L, plain stop trigger).
    cov: required share of 2,016 bars in the week and the prior week (plan 0.99)."""

    def __init__(self, b, cov=0.99, trigger="tol"):
        self.b = b
        self.cov = cov
        self.trigger = trigger
        self.t = b["t"]

    def ix(self, x):
        return int(np.searchsorted(self.t, x, side="left"))

    def week_ok(self, W):
        a0, a1, a2 = self.ix(W - WK), self.ix(W), self.ix(W + WK)
        need = max(self.cov * (WK // BAR), 1)
        return (a1 - a0) >= need and (a2 - a1) >= need, a0, a1, a2

    def touch(self, a1, a2, side, L):
        b = self.b
        if side == "H":
            m = b["h"][a1:a2] > L * (1 + 0.5e-4) if self.trigger == "tol" else b["h"][a1:a2] >= L
        else:
            m = b["l"][a1:a2] < L * (1 - 0.5e-4) if self.trigger == "tol" else b["l"][a1:a2] <= L
        if not m.any():
            return None
        return a1 + int(np.argmax(m))

    def exit_px(self, t0, hms):
        tx = t0 + hms
        if tx > self.b["end"]:
            return None, "after_end"
        j = self.ix(tx - BAR)
        if j < len(self.t) and self.t[j] == tx - BAR:
            return j, "ok"
        return None, "missing"

    def events_week(self, W, W_end=None, levels="monday"):
        """levels: 'monday' -> real + P1 for Monday week W; 'p3' -> real-level construction anchored at W."""
        ok, a0, a1, a2 = self.week_ok(W)
        if not ok:
            return None
        b = self.b
        pwh, pwl, O = float(b["h"][a0:a1].max()), float(b["l"][a0:a1].min()), float(b["o"][a1])
        lv = [("PWH", "H", pwh, "real"), ("PWL", "L", pwl, "real")]
        if levels == "monday":
            dh, dl = math.log(pwh / O), math.log(O / pwl)
            if dh > 0:
                lv += [(f"P1H_{m:g}", "H", O * math.exp(m * dh), "P1") for m in MULTS]
            if dl > 0:
                lv += [(f"P1L_{m:g}", "L", O * math.exp(-m * dl), "P1") for m in MULTS]
        else:
            lv = [("P3H", "H", pwh, "P3"), ("P3L", "L", pwl, "P3")]
        out = []
        for kind, side, L, ctl in lv:
            k = self.touch(a1, a2, side, L)
            if k is None:
                continue
            t0 = int(self.t[k])
            for hn, hms in HZ.items():
                j, st = self.exit_px(t0, hms)
                out.append(dict(W=W, kind=kind, side=side, control=ctl, L=L, k=k, t0=t0, horizon=hn,
                                j=j, status=st))
        return out


def build(panel, coins, bars, cov=0.99, trigger="tol", weeks_fn=None, p3=False):
    """Returns (events DataFrame with touch-bar and exit-bar fields, used coin-weeks DataFrame)."""
    rows, wk = [], []
    for c in coins:
        b = bars[c]
        e = Eng(b, cov=cov, trigger=trigger)
        weeks = weeks_fn(c, b)
        for W in weeks:
            ok = e.week_ok(W)[0]
            wk.append((c, W, ok))
            if not ok:
                continue
            for r in e.events_week(W):
                r["coin"] = c
                rows.append(r)
        if p3:
            anchors = range(weeks[0] - WK + 84 * H, weeks[-1] + 84 * H + 1, WK)
            for A in anchors:
                ev = e.events_week(A, levels="p3")
                if ev:
                    for r in ev:
                        r["coin"] = c
                        rows.append(r)
    ev = pd.DataFrame(rows)
    wk = pd.DataFrame(wk, columns=["coin", "W", "used"])
    return ev, wk


def attach(ev, bars):
    """Add touch-bar OHLCV, exit close and T gross (fill at L) to an event frame from build()."""
    ev = ev.copy()
    for col in ("o", "h", "l", "c", "v", "n"):
        ev["tb_" + col] = np.nan
    ev["px"] = np.nan
    ev["ex_v"] = np.nan
    ev["prev_gap"] = False
    for c, g in ev.groupby("coin"):
        b = bars[c]
        k = g.k.to_numpy(int)
        for col in ("o", "h", "l", "c", "v", "n"):
            ev.loc[g.index, "tb_" + col] = b[col][k]
        ok = g.j.notna().to_numpy()
        j = g.j.fillna(0).to_numpy(int)
        ev.loc[g.index, "px"] = np.where(ok, b["c"][j], np.nan)
        ev.loc[g.index, "ex_v"] = np.where(ok, b["v"][j], np.nan)
        prev_t = b["t"][np.maximum(k - 1, 0)]
        ev.loc[g.index, "prev_gap"] = (b["t"][k] - prev_t) != BAR
    ev["s"] = np.where(ev.side == "H", 1.0, -1.0)
    ev["gross"] = ev.s * (ev.px / ev.L - 1.0) * 1e4
    ev["mw"] = monday(ev.t0.to_numpy())
    return ev


def boot_W(n_weeks):
    rng = np.random.default_rng(11)
    idx = rng.integers(0, n_weeks, size=(2000, n_weeks))
    Wt = np.zeros((2000, n_weeks))
    for b in range(2000):
        Wt[b] = np.bincount(idx[b], minlength=n_weeks)
    return Wt


def gates(real, p1, weeks, coins, half, cost=14.62, col="gross", Wt=None):
    """Four section-4 tests at one horizon. real / p1: frames with columns coin, mw and `col` (gross bps).
    weeks: sorted Monday weeks of the bootstrap. Returns a dict."""
    weeks = np.asarray(weeks, dtype=np.int64)
    pos = pd.Series(np.arange(len(weeks)), index=weeks)
    if Wt is None:
        Wt = boot_W(len(weeks))

    def vec(f):
        wi = pos.reindex(f.mw.to_numpy()).to_numpy()
        assert not np.isnan(wi).any(), "event outside bootstrap weeks"
        wi = wi.astype(int)
        return (np.bincount(wi, weights=f[col].to_numpy(), minlength=len(weeks)),
                np.bincount(wi, minlength=len(weeks)).astype(float))

    sr, nr = vec(real)
    sp, npp = vec(p1)
    br = (Wt @ sr) / (Wt @ nr)
    bp = (Wt @ sp) / (Wt @ npp)
    net = real[col].mean() - cost
    diff = real[col].mean() - p1[col].mean()
    h1 = real[real.mw < half][col].mean() - cost
    h2 = real[real.mw >= half][col].mean() - cost
    pc = real.groupby("coin")[col].mean() - cost
    npos = int((pc > 0).sum())
    need = int(math.ceil(2 * len(coins) / 3))
    p_net = float(((br - cost) <= 0).mean())
    p_diff = float(((br - bp) <= 0).mean())
    out = dict(n=int(len(real)), n_p1=int(len(p1)), net=float(net), p_net=p_net, diff=float(diff), p_diff=p_diff,
               h1=float(h1), h2=float(h2), coins_pos=npos, need=need, n_weeks=int(len(weeks)))
    out["t1"] = bool(net > 0 and p_net <= 0.01)
    out["t2"] = bool(diff > 0 and p_diff <= 0.01)
    out["t3"] = bool(h1 > 0 and h2 > 0)
    out["t4"] = bool(npos >= need)
    out["all"] = bool(out["t1"] and out["t2"] and out["t3"] and out["t4"])
    return out
