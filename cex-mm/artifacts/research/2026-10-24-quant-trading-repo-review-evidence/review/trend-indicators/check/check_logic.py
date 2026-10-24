"""Re-typed checks of four je-suis-tm/quant-trading scripts (nothing imported from that repo).

Synthetic data only: these checks test code mechanics, not market edge.
A. pandas 3 chained assignment (MACD l.47, Awesome l.45, Heikin-Ashi l.52, SAR l.46-50 use it).
B. Awesome Oscillator: is the saucer block dead code once the MA block runs (l.75-123)?
C. Parabolic SAR: the script's recursion vs textbook Wilder (reset to prior EP on reversal).
D. Weekday counts behind the plotting/portfolio slicers.
"""
import warnings

import numpy as np
import pandas as pd


def synth_ohlc(n, seed, vol=0.035):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, vol, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.r_[100.0, close[:-1]] * np.exp(rng.normal(0, vol / 4, n))
    hi = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, vol / 2, n)))
    lo = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, vol / 2, n)))
    return pd.DataFrame({"Open": open_, "High": hi, "Low": lo, "Close": close})


# ---------- A ----------
def check_chained():
    df = pd.DataFrame({"Close": np.arange(10.0)})
    df["positions"] = 0
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            df["positions"][3:] = 1
            err = None
        except Exception as e:  # noqa: BLE001
            err = repr(e)
    return df["positions"].sum(), err, [str(x.category.__name__) for x in w]


# ---------- B ----------
def ao_signals(df, with_saucer=True):
    O, C = df["Open"].to_numpy(), df["Close"].to_numpy()
    mid = (df["High"] + df["Low"]) / 2
    m1 = mid.rolling(5).mean().to_numpy()
    m2 = mid.rolling(34).mean().to_numpy()
    ao = m1 - m2
    n = len(df)
    s = np.zeros(n)
    for i in range(2, n):
        if with_saucer:
            if (O[i] > C[i] and O[i - 1] < C[i - 1] and O[i - 2] < C[i - 2]
                    and ao[i - 1] > ao[i - 2] and ao[i - 1] < 0 and ao[i] < 0):
                s[i] = 1
            if (O[i] < C[i] and O[i - 1] > C[i - 1] and O[i - 2] > C[i - 2]
                    and ao[i - 1] < ao[i - 2] and ao[i - 1] > 0 and ao[i] > 0):
                s[i] = -1
        if m1[i] > m2[i]:
            s[i] = 1
            if s[: i + 1].sum() > 1:
                s[i] = 0
        if m1[i] < m2[i]:
            s[i] = -1
            if s[: i + 1].sum() < 0:
                s[i] = 0
    return s, m1, m2


def crossover_state(m1, m2):
    pos = np.zeros(len(m1))
    p = 0
    for i in range(len(m1)):
        if m1[i] > m2[i]:
            p = 1
        elif m1[i] < m2[i]:
            p = 0
        pos[i] = p
    return np.diff(np.r_[0, pos])


def check_ao(seeds=20, n=1500):
    diff_saucer, diff_xover, saucer_hits = 0, 0, 0
    for sd in range(seeds):
        df = synth_ohlc(n, sd)
        a, m1, m2 = ao_signals(df, True)
        b, _, _ = ao_signals(df, False)
        diff_saucer += int((a != b).sum())
        diff_xover += int((a != crossover_state(m1, m2)).sum())
        # how often a saucer pattern itself fires (before being overwritten)
        O, C = df["Open"].to_numpy(), df["Close"].to_numpy()
        ao = m1 - m2
        for i in range(2, n):
            if (O[i] > C[i] and O[i - 1] < C[i - 1] and O[i - 2] < C[i - 2]
                    and ao[i - 1] > ao[i - 2] and ao[i - 1] < 0 and ao[i] < 0):
                saucer_hits += 1
            if (O[i] < C[i] and O[i - 1] > C[i - 1] and O[i - 2] > C[i - 2]
                    and ao[i - 1] < ao[i - 2] and ao[i - 1] > 0 and ao[i] > 0):
                saucer_hits += 1
    return seeds * n, saucer_hits, diff_saucer, diff_xover


# ---------- C ----------
def sar_script(df, a0=0.02, step=0.02, amax=0.2):
    H, L, C = df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    n = len(df)
    trend = np.zeros(n); sar = np.zeros(n); real = np.zeros(n); ep = np.zeros(n); af = np.zeros(n)
    trend[1] = 1 if C[1] > C[0] else -1
    sar[1] = H[0] if trend[1] > 0 else L[0]
    real[1] = sar[1]
    ep[1] = H[1] if trend[1] > 0 else L[1]
    af[1] = a0
    for i in range(2, n):
        temp = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
        if trend[i - 1] < 0:
            sar[i] = max(temp, H[i - 1], H[i - 2])
            t = 1 if sar[i] < H[i] else trend[i - 1] - 1
        else:
            sar[i] = min(temp, L[i - 1], L[i - 2])
            t = -1 if sar[i] > L[i] else trend[i - 1] + 1
        trend[i] = t
        if trend[i] < 0:
            ep[i] = min(L[i], ep[i - 1]) if trend[i] != -1 else L[i]
        else:
            ep[i] = max(H[i], ep[i - 1]) if trend[i] != 1 else H[i]
        if abs(trend[i]) == 1:
            real[i] = ep[i - 1]; af[i] = a0
        else:
            real[i] = sar[i]
            af[i] = af[i - 1] if ep[i] == ep[i - 1] else min(amax, af[i - 1] + step)
    return real, trend


def sar_wilder(df, a0=0.02, step=0.02, amax=0.2):
    H, L, C = df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    n = len(df)
    out = np.zeros(n); up_arr = np.zeros(n, dtype=bool)
    up = C[1] > C[0]
    sar = L[0] if up else H[0]
    ep = H[1] if up else L[1]
    af = a0
    out[1] = sar; up_arr[1] = up
    for i in range(2, n):
        nxt = sar + af * (ep - sar)
        if up:
            nxt = min(nxt, L[i - 1], L[i - 2])
            if L[i] < nxt:
                up, nxt, ep, af = False, ep, L[i], a0
            elif H[i] > ep:
                ep, af = H[i], min(amax, af + step)
        else:
            nxt = max(nxt, H[i - 1], H[i - 2])
            if H[i] > nxt:
                up, nxt, ep, af = True, ep, H[i], a0
            elif L[i] < ep:
                ep, af = L[i], min(amax, af + step)
        sar = nxt
        out[i] = sar; up_arr[i] = up
    return out, up_arr


def check_sar(seeds=20, n=2000):
    rev_s, rev_w, pos_diff, dist_s, dist_w = 0, 0, 0, [], []
    for sd in range(seeds):
        df = synth_ohlc(n, 100 + sd)
        C = df["Close"].to_numpy()
        rs, tr = sar_script(df)
        rw, upw = sar_wilder(df)
        rev_s += int((np.abs(tr[2:]) == 1).sum())
        rev_w += int((upw[3:] != upw[2:-1]).sum())
        ps = (rs < C).astype(int)[50:]
        pw = (rw < C).astype(int)[50:]
        pos_diff += int((ps != pw).sum())
        # SAR distance from close on the day after a script reversal (first full day of new trend)
        idx = np.where(np.abs(tr) == 1)[0]
        idx = idx[(idx > 50) & (idx < n - 1)] + 1
        dist_s += list(np.abs(rs[idx] / C[idx] - 1))
        idxw = np.where(upw[3:] != upw[2:-1])[0] + 3
        idxw = idxw[(idxw > 50) & (idxw < n - 1)] + 1
        dist_w += list(np.abs(rw[idxw] / C[idxw] - 1))
    bars = seeds * (n - 50)
    return (seeds * n, rev_s, rev_w, pos_diff, bars,
            float(np.median(dist_s)), float(np.median(dist_w)))


if __name__ == "__main__":
    print("pandas", pd.__version__, "numpy", np.__version__)
    s, err, w = check_chained()
    print(f"A chained assignment: positions sum after df['positions'][3:]=1 -> {s} (expect 7 if it worked); error={err}; warnings={w}")
    bars, hits, d1, d2 = check_ao()
    print(f"B AO: {bars} synthetic bars, saucer patterns fired {hits} times; bars where output differs with vs without saucer: {d1}; "
          f"bars where output differs from a plain SMA5/SMA34(HL2) long/flat crossover: {d2}")
    tot, rs, rw, pdiff, pbars, ds, dw = check_sar()
    print(f"C SAR: {tot} synthetic bars (daily vol 3.5%); reversals script={rs} wilder={rw}; "
          f"long/flat position differs on {pdiff} of {pbars} bars ({pdiff / pbars:.1%}); "
          f"median |SAR/close-1| on day after reversal: script={ds:.2%} wilder={dw:.2%}")
    print("D weekdays 2015-04-01..2018-02-15 (Heikin-Ashi NVDA):", np.busday_count("2015-04-01", "2018-02-15"))
    print("D weekdays 2016-01-01..2018-01-01 (SAR EA):", np.busday_count("2016-01-01", "2018-01-01"))
