"""Bar loaders for panels A, B, C (implementation Y; final copy with fix B1 in load_panel_B).

Every loader returns a dict with sorted, de-duplicated int64 open times in ms (`t`) and float64 arrays
`o`, `h`, `l`, `c`, plus `bar_ms`. Timestamps > 1e14 are treated as microseconds (plan section 1).
"""
import glob
import json
import os

import numpy as np
import pandas as pd

SCR = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
NINE = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
EXTRA16 = ["ATOM", "BAT", "DASH", "EOS", "ETC", "IOST", "IOTA", "NEO", "ONT", "QTUM",
           "TRX", "VET", "XLM", "XMR", "XTZ", "ZEC"]


def _to_ms(t):
    t = np.asarray(t, dtype=np.int64)
    return np.where(t > 10**14, t // 1000, t)


def _finish(t, o, h, l, c, bar_ms, cap_ms=None):
    t = _to_ms(t)
    df = pd.DataFrame({"t": t, "o": o, "h": h, "l": l, "c": c})
    df = df.drop_duplicates("t", keep="first").sort_values("t")
    if cap_ms is not None:
        df = df[df.t < cap_ms]
    out = {k: df[k].to_numpy(np.float64) for k in "ohlc"}
    out["t"] = df.t.to_numpy(np.int64)
    out["bar_ms"] = bar_ms
    out["n_dupes"] = int(len(t) - len(np.unique(t)))
    return out


def _read_binance_csv(path):
    """Binance kline CSV with or without a header row (first character a digit means no header)."""
    with open(path) as fh:
        first = fh.read(1)
    df = pd.read_csv(path, header=None if first.isdigit() else 0)
    a = df.iloc[:, :5]
    return (a.iloc[:, 0].to_numpy(np.int64), a.iloc[:, 1].to_numpy(np.float64), a.iloc[:, 2].to_numpy(np.float64),
            a.iloc[:, 3].to_numpy(np.float64), a.iloc[:, 4].to_numpy(np.float64))


def _concat_monthly(pattern, bar_ms, cap_ms):
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(pattern)
    parts = [_read_binance_csv(f) for f in files]
    cols = [np.concatenate([p[i] for p in parts]) for i in range(5)]
    d = _finish(*cols, bar_ms=bar_ms, cap_ms=cap_ms)
    d["n_files"] = len(files)
    return d


def load_panel_A(sym, cap_ms):
    return _concat_monthly(os.path.join(SCR, "universe/klines5m", f"binance-{sym}USDT-5m-*.csv"), 300_000, cap_ms)


# FIX B1 (final/fixes.md): Binance's monthly 1 h files miss 2022-02-26..28 and 2022-04-01..02 for seven panel-B coins.
# The rows come from Binance's checksum-verified daily 1 h zips (tools/fetch_daily_1h.py), the same repair panel A's
# 5 m files got before the study ran. Patch rows may only fill open times the local file lacks.
PATCH_B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_patch", "patch_B_holes.csv")


def _patch_rows(sym):
    p = pd.read_csv(PATCH_B)
    return p[p.coin == sym]


def _apply_patch(d, p, cap_ms):
    if p.empty:
        d["n_patched"] = 0
        return d
    pt = p.open_time_ms.to_numpy(np.int64)
    assert not np.isin(pt, d["t"]).any(), "patch rows overlap existing bars"
    assert (pt % d["bar_ms"] == 0).all() and len(np.unique(pt)) == len(pt)
    if cap_ms is not None:
        assert (pt < cap_ms).all()
    t = np.r_[d["t"], pt]
    order = np.argsort(t, kind="stable")
    out = dict(d)
    out["t"] = t[order]
    for k, col in zip("ohlc", ("open", "high", "low", "close")):
        out[k] = np.r_[d[k], p[col].to_numpy(np.float64)][order]
    out["n_patched"] = int(len(pt))
    return out


def load_panel_B(sym, cap_ms):
    if sym in NINE:
        df = pd.read_csv(os.path.join(SCR, "hourly", f"{sym}USDT-1h.csv"))
        d = _finish(df.open_time_ms.to_numpy(np.int64), df.open.to_numpy(float), df.high.to_numpy(float),
                    df.low.to_numpy(float), df.close.to_numpy(float), 3_600_000, cap_ms)
        d["n_files"] = 1
    else:
        d = _concat_monthly(os.path.join(SCR, "universe/hourly_extra", f"binance-{sym}USDT-1h-*.csv"), 3_600_000,
                            cap_ms)
    return _apply_patch(d, _patch_rows(sym), cap_ms)


def load_panel_C(sym, cap_ms=None):
    with open(os.path.join(SCR, "research2/delta_data", f"hourly_{sym}USD.json")) as fh:
        rows = json.load(fh)
    t = np.array([r["time"] for r in rows], dtype=np.int64) * 1000  # seconds -> ms
    d = _finish(t, np.array([r["open"] for r in rows], float), np.array([r["high"] for r in rows], float),
                np.array([r["low"] for r in rows], float), np.array([r["close"] for r in rows], float),
                3_600_000, cap_ms)
    d["n_files"] = 1
    return d
