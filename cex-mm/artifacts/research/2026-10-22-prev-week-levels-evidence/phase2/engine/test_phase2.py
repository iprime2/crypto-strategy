"""Phase 2 checks of the extensions (run: python3 -I -B test_phase2.py).

1. T rows are the exact negation of F rows, same entry (touch-bar open, L) and exit.
2. P3 (Thursday 12:00 anchor): levels are the max high / min low of the 168 h before the anchor, the first touch is
   searched in [A, A + 168 h), and the 99 % coverage rule applies to both windows.
3. monday_of maps any time to the Monday 00:00 UTC that starts its week.
4. OX loader: the series is cut after the last bar with volume > 0; the cut equals data_ox/coin_windows.csv.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine as E  # noqa: E402
import loaders as LD  # noqa: E402
import run as R  # noqa: E402

H = E.HOUR
MON = R.ms("2020-09-07")  # a Monday


def mk(n, bar, start, base=100.0):
    t = start + np.arange(n, dtype=np.int64) * bar
    o = np.full(n, base)
    return {"t": t, "o": o.copy(), "h": o.copy(), "l": o.copy(), "c": o.copy(), "bar_ms": bar}


def test_T_equals_minus_F():
    b = mk(504, H, MON - 2 * E.WEEK)
    W2 = MON
    b["h"][200] = 110.0           # PWH 110 (week W2 - 1 = bars 168..335)
    b["l"][250] = 90.0            # PWL 90
    b["h"][346], b["c"][346] = 111.0, 109.0   # touch of PWH at W2 + 10 h
    b["c"][349] = 113.0
    b["l"][400], b["c"][400] = 89.0, 88.0     # touch of PWL at W2 + 64 h
    end = int(b["t"][-1]) + H
    ev, _, _, _ = E.coin_events(b, [W2], end, reel=False)
    F = {(e[1], e[6]): e for e in ev if e[5] == "F"}
    T = {(e[1], e[6]): e for e in ev if e[5] == "T"}
    assert set(F) == set(T) and len(T) > 0
    for k in F:
        f, t = F[k], T[k]
        assert f[7:11] == t[7:11], (f, t)          # same entry time, entry px, exit time, exit px
        assert t[11] == -f[11]                     # exact negation
    # breakout direction: long at PWH, short at PWL
    t1 = T[("PWH", "1h")]
    assert t1[8] == 110.0 and abs(t1[11] - (109.0 / 110.0 - 1) * 1e4) < 1e-9
    t4 = T[("PWH", "4h")]
    assert abs(t4[11] - (113.0 / 110.0 - 1) * 1e4) < 1e-9
    tl = T[("PWL", "1h")]
    assert abs(tl[11] - (-(88.0 / 90.0 - 1) * 1e4)) < 1e-9
    print("T = -F: OK", len(T), "T rows")


def test_P3():
    bar = 300_000
    start = MON - 2 * E.WEEK
    b = mk(4 * 2016, bar, start)
    A = MON + R.P3_OFF                               # Thursday 12:00 of the week of MON
    ia = int((A - start) // bar)
    b["h"][ia - 10] = 105.0                          # inside [A - 168 h, A): P3H = 105
    b["l"][ia - 2016 + 5] = 96.0                     # inside the window: P3L = 96
    b["h"][ia - 2016 - 3] = 120.0                    # before the window: must not count
    b["h"][ia + 100], b["c"][ia + 100] = 105.2, 105.1   # first touch of P3H (105 * 1.00005 = 105.00525)
    end = int(b["t"][-1]) + bar
    ev, info, rows, diag = E.coin_events_p3(b, [A], end)
    assert info[0]["used"] and info[0]["pwh"] == 105.0 and info[0]["pwl"] == 96.0, info
    T = [e for e in ev if e[5] == "T" and e[1] == "P3H"]
    assert {e[6] for e in T} == {"1h", "4h", "24h"}
    for e in T:
        assert e[0] == A and e[7] == A + 100 * bar and e[8] == 105.0 and e[3] == "P3"
    assert not any(e[1] == "P3L" for e in ev)     # P3L 96 never touched
    assert int(R.monday_of(T[0][7])) == MON        # touch assigned to the Monday week MON
    # a touch just before A is outside the P3 week: move the touch to A - 5 min, no event on it
    b2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in b.items()}
    b2["h"][ia + 100], b2["c"][ia + 100] = 100.0, 100.0
    b2["h"][ia - 1] = 104.0
    ev2, info2, _, _ = E.coin_events_p3(b2, [A], end)
    assert not [e for e in ev2 if e[1] == "P3H"]
    # coverage: remove 21 bars (> 1 % of 2,016) from the prior 168 h -> P3 week not used
    keep = np.ones(len(b["t"]), bool)
    keep[ia - 500: ia - 479] = False
    b3 = {k: (v[keep] if isinstance(v, np.ndarray) else v) for k, v in b.items()}
    ev3, info3, _, _ = E.coin_events_p3(b3, [A], end)
    assert not info3[0]["used"] and ev3 == []
    keep[ia - 479] = True                           # 20 missing bars: still >= 99 % (1,996 of 2,016)
    keep[ia - 500] = True
    keep[ia - 499: ia - 479] = False
    b4 = {k: (v[keep] if isinstance(v, np.ndarray) else v) for k, v in b.items()}
    _, info4, _, _ = E.coin_events_p3(b4, [A], end)
    assert info4[0]["used"] and info4[0]["n_prev"] == 1996
    print("P3: OK")


def test_monday():
    for s, m in (("2020-05-04 00:00", "2020-05-04"), ("2020-05-10 23:59:59", "2020-05-04"),
                 ("2020-05-07 12:00", "2020-05-04"), ("2017-08-17 04:00", "2017-08-14"),
                 ("2026-09-27 23:55", "2026-09-21")):
        assert int(R.monday_of(R.ms(s))) == R.ms(m), s
    assert pd.Timestamp(R.ms("2020-05-04"), unit="ms").dayofweek == 0
    a = pd.Timestamp(R.ms("2020-05-04") + R.P3_OFF, unit="ms")
    assert a.dayofweek == 3 and a.hour == 12
    print("monday_of / Thursday 12:00: OK")


def test_ox_cut():
    cw = pd.read_csv(os.path.join(LD.SCR, "research3/p2/data_ox/coin_windows.csv"))
    cap = R.ms("2026-10-01")
    for sym in ("LUNA", "FTM", "MATIC", "LRC", "SOL"):
        d = LD.load_panel_OX(sym, cap)
        row = cw[cw.symbol == sym + "USDT"].iloc[0]
        exp = R.ms(row.effective_data_end_utc)
        assert d["effective_end_ms"] == exp, (sym, d["effective_end_ms"], exp)
        assert int(d["t"][-1]) + 300_000 == exp, sym
        assert int(d["t"][0]) == R.ms(row.first_bar_on_disk), sym
        assert (np.diff(d["t"]) == 300_000).all(), (sym, "gap")
    print("OX cut after the last traded bar: OK (LUNA, FTM, MATIC, LRC, SOL)")


if __name__ == "__main__":
    test_T_equals_minus_F()
    test_P3()
    test_monday()
    test_ox_cut()
