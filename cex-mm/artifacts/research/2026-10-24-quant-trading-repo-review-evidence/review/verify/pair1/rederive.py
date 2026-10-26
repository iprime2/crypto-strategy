"""Re-derive PAIR-1 trades by hand from raw Binance 5m klines (independent of engine.py)."""
import sys, math, datetime as dt
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/verify")
import numpy as np
from raw5m import load5m, close00, p01, ms, funding

TR = [  # pair X-Y, side, entry, exit, reason, reported gross, fund, cost, net, b
    ("BTC", "ETH", -1, "2020-07-25", "2020-07-27", "retest", -603.594, 16.7455, 30.4172, -617.265, 1.17074),
    ("BNB", "DOGE", 1, "2021-02-17", "2021-02-19", "stop", -8074.92, 77.3405, 35.5765, -8033.16, 2.32667),
    ("BTC", "BCH", -1, "2024-03-02", "2024-03-03", "stop", -7258.58, 52.8456, 34.4848, -7240.22, 0.295946),
    ("LINK", "BCH", -1, "2024-11-22", "2024-12-03", "target", 4329.01, -34.6968, 34.3015, 4260.02, 0.718074),
    ("XRP", "LINK", 1, "2025-01-12", "2025-01-22", "target", 2715.01, -21.4818, 33.824, 2659.7, 0.497595),
    ("LINK", "DOGE", 1, "2025-07-18", "2025-07-19", "target", 1006.42, 0.333941, 29.339, 977.411, 1.20077),
    ("ADA", "LTC", 0, "2023-06-22", None, None, None, None, None, -3214.34, None),
]
D = dt.date.fromisoformat
cache = {}
def bars(s):
    if s not in cache:
        cache[s] = load5m(s)
    return cache[s]

def adf_t_n(x, maxlag=10):
    dx = np.diff(x); nd = len(dx)
    def design(lag, start):
        n = nd - start
        cols = [x[start:start + n]] + [dx[start - i:start - i + n] for i in range(1, lag + 1)]
        return dx[start:], np.column_stack(cols)
    best = None
    for lag in range(0, maxlag + 1):
        y, X = design(lag, maxlag)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ beta; n = len(y)
        aic = n * math.log(r @ r / n) + 2 * X.shape[1]  # constant terms drop out
        if best is None or aic < best[0] - 1e-12:
            best = (aic, lag)
    lag = best[1]
    y, X = design(lag, lag)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ beta
    s2 = r @ r / (len(y) - X.shape[1])
    return beta[0] / math.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0]), lag

def mackp(t):
    from math import erfc, sqrt
    if t > 0.92: return 1.0
    if t < -18.86: return 0.0
    c = (2.92, 1.5012, 3.9796e-2) if t <= -2.62 else (2.1945, 0.64695, -0.29198, -0.042377)
    z = sum(ci * t ** i for i, ci in enumerate(c))
    return 0.5 * erfc(-z / sqrt(2))

def form(X, Y, M):
    days = [M - dt.timedelta(days=k) for k in range(179, -1, -1)]
    lx = np.log([close00(bars(X), d) for d in days]); ly = np.log([close00(bars(Y), d) for d in days])
    A = np.column_stack([np.ones(180), lx]); coef, *_ = np.linalg.lstsq(A, ly, rcond=None)
    e = ly - A @ coef
    t, lag = adf_t_n(e)
    de = np.diff(e); cc, *_ = np.linalg.lstsq(np.column_stack([np.ones(179), e[:-1]]), de, rcond=None)
    h = -math.log(2) / math.log(1 + cc[1]) if -1 < cc[1] < 0 else float('nan')
    sig = de.std(ddof=1) * math.sqrt(365)
    return dict(a=coef[0], b=coef[1], m=e.mean(), s=e.std(ddof=1), p=mackp(t), h=h, sig=sig, lag=lag)

def z(f, X, Y, d):
    return (math.log(close00(bars(Y), d)) - f["b"] * math.log(close00(bars(X), d)) - f["a"] - f["m"]) / f["s"]

for X, Y, side, de_, dx_, reason, g0, f0, c0, n0, b0 in TR:
    de = D(de_)
    M = de - dt.timedelta(days=de.weekday())
    f = form(X, Y, M)
    ze = z(f, X, Y, de)
    print(f"\n{X}-{Y} entry {de} (Monday {M}): my b {f['b']:.6f} (rep {b0}), p {f['p']:.5f}, h {f['h']:.3f}, z_entry {ze:+.4f}")
    if side == 0:
        side = -1 if ze >= 2 else 1
    # walk exits
    d = de + dt.timedelta(days=1); why = None
    while why is None:
        zz = z(f, X, Y, d)
        held = (d - de).days
        if (side == -1 and zz >= 4) or (side == 1 and zz <= -4): why = "stop"
        elif (side == -1 and zz <= 0.5) or (side == 1 and zz >= -0.5): why = "target"
        elif d.weekday() == 0:
            g = form(X, Y, d)
            if g["p"] > 0.20: why = "retest"
        if why is None and held > min(2 * f["h"], 30): why = "time"
        if why is None: d += dt.timedelta(days=1)
    print(f"  my exit {d} {why} (rep {dx_} {reason}), z_exit {zz:+.3f}")
    pye, pxe = p01(bars(Y), de), p01(bars(X), de)
    pyx, pxx = p01(bars(Y), d), p01(bars(X), d)
    b = f["b"]; L = (1 + b) / 2
    gross = side * ((pyx / pye - 1) - b * (pxx / pxe - 1))
    cost = 7.31e-4 * ((1 + b) + pyx / pye + b * pxx / pxe)
    t0, t1 = ms(de, 1), ms(d, 1)
    fu = 0.0
    for sym, w, sgn, p0 in ((Y, 1.0, side, pye), (X, b, -side, pxe)):
        for t, r in funding(sym):
            if t0 < t < t1:
                k = (t // 300000) * 300000; k -= k % 3600000
                px = bars(sym)[k][0]
                fu -= sgn * w * px / p0 * r
    print(f"  fills: Y {pye} -> {pyx}, X {pxe} -> {pxx}")
    print(f"  my gross {1e4*gross/L:.2f} fund {1e4*fu/L:.2f} cost {1e4*cost/L:.2f} net {1e4*(gross+fu-cost)/L:.2f} | rep {g0} {f0} {c0} {n0}")
