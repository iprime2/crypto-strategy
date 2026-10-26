"""Event engine for the previous-week-level study (implementation Y, written from plan.md alone).

One call of `coin_events(bars, weeks, data_end_ms, reel)` scans one coin over a list of candidate week starts and
returns (events, weekinfo, reelrows, diag).
"""
import math

import numpy as np

HOUR = 3_600_000
DAY = 24 * HOUR
WEEK = 7 * DAY
TOUCH_TOL = 0.5e-4          # 0.5 bp
R_REEL = 10e-4              # r = 10 bps
HORIZONS = (("1h", HOUR), ("4h", 4 * HOUR), ("24h", DAY))
MULTS = (0.5, 0.75, 1.25, 1.5)
P2_LAG = 84 * HOUR          # P2 window ends 84 h before week start
P2_LEN = 7 * DAY
P2_MIN_DIFF = 10e-4         # P2 level must differ from PWH/PWL by >= 10 bps
COVERAGE = 0.99
S_WINDOW = 4 * HOUR


def mult_tag(m):
    return ("%g" % m)


def build_hourly(bars):
    """Hourly closes aligned on the hour. Returns (close_times_ms, close_px).

    1 h bars: close time = open + 1 h. 5 m bars: the 1 h close is the close of the HH:55 bar (close time HH+1:00);
    an hour whose HH:55 bar is missing has no close (never happens on panel A, which has no gaps)."""
    t, c, bar = bars["t"], bars["c"], bars["bar_ms"]
    if bar == HOUR:
        return t + HOUR, c.copy()
    m = (t % HOUR) == (HOUR - bar)
    return t[m] + bar, c[m]


class Coin:
    def __init__(self, bars, data_end_ms):
        self.t = bars["t"]
        self.o, self.h, self.l, self.c = bars["o"], bars["h"], bars["l"], bars["c"]
        self.bar = bars["bar_ms"]
        self.hT, self.hC = build_hourly(bars)
        self.data_end = data_end_ms  # exits with close time > data_end are dropped

    def idx(self, ms):
        return int(np.searchsorted(self.t, ms, side="left"))

    def close_at(self, close_time):
        """Close of the bar that ends exactly at close_time (exact match), else None."""
        if close_time > self.data_end:
            return None, "after_end"
        target = close_time - self.bar
        i = self.idx(target)
        if i < len(self.t) and self.t[i] == target:
            return float(self.c[i]), "ok"
        return None, "missing_bar"


def week_levels(cn, W):
    """Levels for the week starting at W (ms). Returns (info, levels). levels: list of (kind, side, px, control)."""
    a0, a1, b1 = cn.idx(W - WEEK), cn.idx(W), cn.idx(W + WEEK)
    nprev, ncur = a1 - a0, b1 - a1
    nexp = WEEK // cn.bar
    info = {"n_prev": nprev, "n_cur": ncur, "used": (nprev >= COVERAGE * nexp) and (ncur >= COVERAGE * nexp)}
    if not info["used"]:
        return info, []
    pwh = float(cn.h[a0:a1].max())
    pwl = float(cn.l[a0:a1].min())
    O = float(cn.o[a1])
    info.update(pwh=pwh, pwl=pwl, O=O, first_bar=int(cn.t[a1]))
    levels = [("PWH", "H", pwh, "real"), ("PWL", "L", pwl, "real")]
    dh = math.log(pwh / O)
    dl = math.log(O / pwl)
    info["dh"], info["dl"] = dh, dl
    # P1: price-shifted placebos on the same side, only when the real level is on its proper side of O
    if dh > 0:
        for m in MULTS:
            levels.append(("P1H_" + mult_tag(m), "H", O * math.exp(m * dh), "P1"))
    if dl > 0:
        for m in MULTS:
            levels.append(("P1L_" + mult_tag(m), "L", O * math.exp(-m * dl), "P1"))
    # P2: window [W-84h-168h, W-84h); unbroken from window end to W; differs from PWH/PWL by >= 10 bps
    w0, w1 = cn.idx(W - P2_LAG - P2_LEN), cn.idx(W - P2_LAG)
    info["p2_window_bars"] = w1 - w0
    if w1 > w0:
        p2h = float(cn.h[w0:w1].max())
        p2l = float(cn.l[w0:w1].min())
        post_h = float(cn.h[w1:a1].max()) if a1 > w1 else -np.inf
        post_l = float(cn.l[w1:a1].min()) if a1 > w1 else np.inf
        if post_h <= p2h and abs(p2h / pwh - 1.0) >= P2_MIN_DIFF:
            levels.append(("P2H", "H", p2h, "P2"))
        if post_l >= p2l and abs(p2l / pwl - 1.0) >= P2_MIN_DIFF:
            levels.append(("P2L", "L", p2l, "P2"))
        info["p2h_raw"], info["p2l_raw"] = p2h, p2l
    return info, levels


def first_touch(cn, W, side, L):
    a1, b1 = cn.idx(W), cn.idx(W + WEEK)
    if side == "H":
        m = cn.h[a1:b1] > L * (1 + TOUCH_TOL)
    else:
        m = cn.l[a1:b1] < L * (1 - TOUCH_TOL)
    if not m.any():
        return None
    return a1 + int(np.argmax(m))


def level_events(cn, W, kind, side, L, control, reel, diag):
    """All scored trades for one level in one coin-week, plus reel-style descriptive flags."""
    k = first_touch(cn, W, side, L)
    rows = []
    rinfo = {"touched": k is not None}
    if k is None:
        return rows, rinfo
    t0 = int(cn.t[k])
    up = side == "H"
    # F: fade at L, exit at close of bar ending t0 + h
    sgn_f = -1.0 if up else 1.0
    for hname, hms in HORIZONS:
        px, st = cn.close_at(t0 + hms)
        if px is None:
            diag["drop_" + st] = diag.get("drop_" + st, 0) + 1
            continue
        rows.append(("F", hname, t0, L, t0 + hms, px, sgn_f * (px / L - 1.0) * 1e4))
    # hourly closes at or after the touch: close time >= end of the touch bar
    j0 = int(np.searchsorted(cn.hT, t0 + cn.bar, side="left"))
    hT, hC = cn.hT, cn.hC
    # B: first hourly close beyond L at/after the touch, hourly bar inside week w (close time <= W + WEEK)
    jend = int(np.searchsorted(hT, W + WEEK, side="right"))
    seg = hC[j0:jend]
    beyond = (seg > L) if up else (seg < L)
    jb = j0 + int(np.argmax(beyond)) if beyond.any() else None
    if jb is not None:
        te, pe = int(hT[jb]), float(hC[jb])
        sgn_b = 1.0 if up else -1.0
        for hname, hms in HORIZONS:
            px, st = cn.close_at(te + hms)
            if px is None:
                diag["drop_" + st] = diag.get("drop_" + st, 0) + 1
                continue
            rows.append(("B", hname, te, pe, te + hms, px, sgn_b * (px / pe - 1.0) * 1e4))
    # S: scan hourly closes with close time in [t0 + bar, t0 + 4h]; first strict-inside close before any strict-beyond close
    js_end = int(np.searchsorted(hT, t0 + S_WINDOW, side="right"))
    js = None
    n_equal = 0
    for j in range(j0, js_end):
        x = hC[j]
        if (x > L) if up else (x < L):
            break
        if (x < L) if up else (x > L):
            js = j
            break
        n_equal += 1
    if n_equal:
        diag["s_equal_closes"] = diag.get("s_equal_closes", 0) + n_equal
    if js is not None:
        te, pe = int(hT[js]), float(hC[js])
        sgn_s = -1.0 if up else 1.0
        for hname, hms in HORIZONS:
            px, st = cn.close_at(te + hms)
            if px is None:
                diag["drop_" + st] = diag.get("drop_" + st, 0) + 1
                continue
            rows.append(("S", hname, te, pe, te + hms, px, sgn_s * (px / pe - 1.0) * 1e4))
    if reel:
        # rejected within 60 min: closes of bars opening in [t0, t0 + 60 min)
        i1 = cn.idx(t0 + HOUR)
        cl = cn.c[k:i1]
        if up:
            ins, bey = cl <= L * (1 - R_REEL), cl >= L * (1 + R_REEL)
        else:
            ins, bey = cl >= L * (1 + R_REEL), cl <= L * (1 - R_REEL)
        fi = int(np.argmax(ins)) if ins.any() else None
        fb = int(np.argmax(bey)) if bey.any() else None
        rinfo["reject60"] = (fi is not None) and (fb is None or fi < fb)
        # continued: after confirmation, a further r beyond the confirming close before trading back to L, within 24 h
        if jb is not None:
            te, pe = int(hT[jb]), float(hC[jb])
            if te + DAY <= cn.data_end:
                c0, c1 = cn.idx(te), cn.idx(te + DAY)
                if up:
                    go = cn.h[c0:c1] >= pe * (1 + R_REEL)
                    back = cn.l[c0:c1] <= L
                else:
                    go = cn.l[c0:c1] <= pe * (1 - R_REEL)
                    back = cn.h[c0:c1] >= L
                fg = int(np.argmax(go)) if go.any() else None
                fbk = int(np.argmax(back)) if back.any() else None
                tie = fg is not None and fbk is not None and fg == fbk
                if tie:
                    diag["continued_same_bar_ties"] = diag.get("continued_same_bar_ties", 0) + 1
                rinfo["continued_tie"] = tie
                # a 5 m bar that reaches both C(1 +/- r) and L has no known order: counted as NOT continued
                rinfo["continued"] = (fg is not None) and (fbk is None or fg < fbk)
            else:
                diag["continued_window_after_end"] = diag.get("continued_window_after_end", 0) + 1
    return rows, rinfo


def coin_events(bars, weeks, data_end_ms, reel=False):
    cn = Coin(bars, data_end_ms)
    events, winfo, reelrows = [], [], []
    diag = {}
    for W in weeks:
        info, levels = week_levels(cn, W)
        info["W"] = W
        winfo.append(info)
        if not info["used"]:
            continue
        for kind, side, L, control in levels:
            rows, rinfo = level_events(cn, W, kind, side, L, control, reel, diag)
            for (pat, hname, te, pe, tx, px, g) in rows:
                events.append((W, kind, side, control, L, pat, hname, te, pe, tx, px, g))
            rinfo.update(W=W, kind=kind, side=side, control=control)
            reelrows.append(rinfo)
    return events, winfo, reelrows, diag
