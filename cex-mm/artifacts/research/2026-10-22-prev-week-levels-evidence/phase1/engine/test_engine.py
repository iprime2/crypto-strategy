"""Hand-computed synthetic checks of engine.py (run: python3 -I test_engine.py)."""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

H = E.HOUR
W0 = 1_600_041_600_000 - 3 * 86_400_000  # 2020-09-11? only spacing matters; aligned to the hour
W0 = (W0 // H) * H


def mk(n, bar, base=100.0):
    t = W0 + np.arange(n, dtype=np.int64) * bar
    o = np.full(n, base)
    return {"t": t, "o": o.copy(), "h": o.copy(), "l": o.copy(), "c": o.copy(), "bar_ms": bar}


def setbar(b, i, o=None, h=None, l=None, c=None):
    for k, v in (("o", o), ("h", h), ("l", l), ("c", c)):
        if v is not None:
            b[k][i] = v


def approx(a, b, tol=1e-9):
    assert abs(a - b) < tol, (a, b)


def test_hourly_panel():
    b = mk(504, H)
    W2 = W0 + 336 * H
    setbar(b, 200, h=110)            # PWH = 110 (week w-1 = bars 168..335)
    setbar(b, 250, l=90)             # PWL = 90
    setbar(b, 120, h=115)            # P2H = 115 (window bars 84..251, unbroken after)
    setbar(b, 100, l=85)             # P2L = 85
    setbar(b, 346, h=111, c=109)     # touch of PWH at W2+10h, closes inside (109 < 110)
    setbar(b, 347, h=108, l=108, c=108, o=108)
    setbar(b, 349, h=107, l=107, c=107, o=107)
    setbar(b, 360, h=113, c=112)     # first close beyond 110 at W2+25h
    setbar(b, 361, h=113, l=113, c=113, o=113)
    end = int(b["t"][-1]) + H
    ev, winfo, rr, diag = E.coin_events(b, [W2], end, reel=False)
    info = winfo[0]
    assert info["used"] and info["pwh"] == 110 and info["pwl"] == 90 and info["O"] == 100
    kinds = {r["kind"]: r for r in rr}
    assert set(kinds) == {"PWH", "PWL", "P1H_0.5", "P1H_0.75", "P1H_1.25", "P1H_1.5",
                          "P1L_0.5", "P1L_0.75", "P1L_1.25", "P1L_1.5", "P2H", "P2L"}, set(kinds)
    assert kinds["PWH"]["touched"] and not kinds["PWL"]["touched"] and not kinds["P1H_1.5"]["touched"]
    assert kinds["P1H_1.25"]["touched"]
    d = {(e[1], e[5], e[6]): e for e in ev}
    # F at PWH: sell at 110; 1 h exit = close of the touch bar (109); 4 h exit = close of bar 349 (107)
    approx(d[("PWH", "F", "1h")][11], -(109 / 110 - 1) * 1e4)
    approx(d[("PWH", "F", "4h")][11], -(107 / 110 - 1) * 1e4)
    assert d[("PWH", "F", "1h")][9] == W2 + 11 * H
    # S at PWH: short at the touch bar close 109 (time W2+11h); 1 h exit 108; 4 h exit = close at W2+15h = 100
    s1 = d[("PWH", "S", "1h")]
    assert s1[7] == W2 + 11 * H and s1[8] == 109
    approx(s1[11], -(108 / 109 - 1) * 1e4)
    approx(d[("PWH", "S", "4h")][11], -(100 / 109 - 1) * 1e4)
    # B at PWH: long at 112 at W2+25h; 1 h exit 113
    b1 = d[("PWH", "B", "1h")]
    assert b1[7] == W2 + 25 * H and b1[8] == 112
    approx(b1[11], (113 / 112 - 1) * 1e4)
    # P1H_1.25 = 100*exp(1.25*ln 1.1) = 112.6827..., touched by bar 360 (high 113); its touch-bar close 112 is
    # inside -> S at 112 short; next close 113 -> -89.29 bps at 1 h
    lv = 100 * math.exp(1.25 * math.log(1.1))
    approx(kinds["P1H_1.25"].get("touched") and lv, lv)
    s = d[("P1H_1.25", "S", "1h")]
    approx(s[4], lv)
    approx(s[11], -(113 / 112 - 1) * 1e4)
    # bar 361 closes at 113 > 112.68 -> B long at 113 at W2+26h; 1 h exit = bar 362 close (100)
    bb = d[("P1H_1.25", "B", "1h")]
    assert bb[7] == W2 + 26 * H and bb[8] == 113
    approx(bb[11], (100 / 113 - 1) * 1e4)
    # P2H = 115 and P2L = 85 used; not touched
    assert kinds["P2H"]["touched"] is False and kinds["P2L"]["touched"] is False
    print("hourly panel synthetic: OK", len(ev), "trades")


def test_5m_panel():
    bar = 300_000
    b = mk(3 * 2016, bar)
    W2 = W0 + 2 * 2016 * bar
    setbar(b, 2016 + 500, h=110)     # PWH 110
    setbar(b, 2016 + 600, l=90)      # PWL 90
    i = 2 * 2016 + 12 * 10 + 7       # touch at W2 + 10h35m
    setbar(b, i, h=110.5, c=110.05)  # touch, close 4.5 bps beyond L (neither inside nor beyond by r)
    setbar(b, i + 1, h=110.3, l=109.0, c=109.8)   # close 109.8: 18 bps inside (<= 110*(1-0.001)=109.89)
    # hourly close at W2+11h is the close of bar W2+10h55 = index 2*2016+131 -> default 100 (inside) -> S at 11:00
    end = int(b["t"][-1]) + bar
    ev, winfo, rr, diag = E.coin_events(b, [W2], end, reel=True)
    kinds = {r["kind"]: r for r in rr}
    assert kinds["PWH"]["touched"] and kinds["PWH"]["reject60"] is True
    d = {(e[1], e[5], e[6]): e for e in ev}
    f1 = d[("PWH", "F", "1h")]
    assert f1[7] == W2 + 10 * H + 35 * 60_000 and f1[9] == W2 + 11 * H + 35 * 60_000
    s1 = d[("PWH", "S", "1h")]
    assert s1[7] == W2 + 11 * H and s1[8] == 100.0
    hT, hC = E.build_hourly(b)
    assert hT[0] == W0 + H and len(hT) == 3 * 168
    # reject60 with the beyond close first: make the touch-bar close 110.2 >= 110.11 (beyond) and the next
    # close inside -> beyond came first -> not rejected
    setbar(b, i, c=110.2)
    setbar(b, i + 1, c=110.0)        # neither (within +-10 bps)
    setbar(b, i, c=110.12)           # beyond by 10.9 bps
    setbar(b, i + 2, l=109.0, c=109.5)  # inside by 45 bps, after the beyond close -> not rejected
    ev, winfo, rr, diag = E.coin_events(b, [W2], end, reel=True)
    kinds = {r["kind"]: r for r in rr}
    assert kinds["PWH"]["reject60"] is False
    print("5 m panel synthetic: OK")


if __name__ == "__main__":
    test_hourly_panel()
    test_5m_panel()
