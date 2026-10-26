"""Reconcile test: the S rule with 1 h closes exactly equal to L (the only X/Y event-level disagreement).

Chosen reading (plan section 3, S): a close exactly at L is neither 'inside L' nor 'beyond L'; the scan continues.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

H = E.HOUR
W0 = (1_600_000_000_000 // H) * H


def mk(n):
    t = W0 + np.arange(n, dtype=np.int64) * H
    o = np.full(n, 100.0)
    return {"t": t, "o": o.copy(), "h": o.copy(), "l": o.copy(), "c": o.copy(), "bar_ms": H}


def run(closes_after_touch):
    b = mk(504)
    W2 = W0 + 336 * H
    b["h"][200] = 110.0                    # PWH = 110
    b["l"][250] = 90.0                     # PWL = 90
    i = 346                                # touch bar at W2 + 10 h
    b["h"][i] = 111.0
    for k, c in enumerate(closes_after_touch):
        b["c"][i + k] = c
        b["o"][i + k] = c
        b["h"][i + k] = max(b["h"][i + k], c)
        b["l"][i + k] = min(b["l"][i + k], c)
    b["h"][i] = 111.0
    end = int(b["t"][-1]) + H
    ev, winfo, rr, diag = E.coin_events(b, [W2], end, reel=False)
    s = [e for e in ev if e[1] == "PWH" and e[5] == "S" and e[6] == "1h"]
    return s, diag, W2


# touch-bar close == L, next close inside -> S enters one hour later at 109
s, diag, W2 = run([110.0, 109.0, 108.0, 107.0, 106.0])
assert len(s) == 1 and s[0][7] == W2 + 12 * H and s[0][8] == 109.0, s
assert diag.get("s_equal_closes") == 1
# touch-bar close == L, next close beyond -> no S
s, diag, _ = run([110.0, 110.5, 108.0, 107.0, 106.0])
assert s == [], s
# four closes == L within 4 h -> no S
s, diag, _ = run([110.0, 110.0, 110.0, 110.0, 109.0])
assert s == [], s
# a strict inside close at the touch bar -> S at the touch-bar close (unchanged behaviour)
s, diag, W2 = run([109.5, 108.0, 108.0, 108.0, 108.0])
assert len(s) == 1 and s[0][7] == W2 + 11 * H and s[0][8] == 109.5, s
print("S tie-rule tests: OK (4 cases)")
