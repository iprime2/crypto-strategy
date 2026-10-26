"""Fix B1 loader test: the patched panel-B loader equals the reconciled loader except for the 840 added daily rows.

For all 25 coins: every bar of the old loader is present, unchanged, in the new one; the only extra bars are the patch
rows (120 for each of XRP, LTC, IOTA, TRX, VET, XLM, ZEC; 0 elsewhere); the new series has no duplicate and no gap
after the coin's first bar (EOS ends at its last bar). Panels A and C loaders are unchanged by construction.
"""
import importlib.util
import os
import sys

import numpy as np

sys.dont_write_bytecode = True  # never write a __pycache__ next to the read-only reconcile/final copy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loaders as NEW  # noqa: E402

OLD_PATH = os.path.join(HERE, "..", "reconcile", "final", "loaders.py")
spec = importlib.util.spec_from_file_location("old_loaders", OLD_PATH)
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

CAP = 1790812800000  # 2026-10-01 00:00 UTC
PATCHED = {"XRP", "LTC", "IOTA", "TRX", "VET", "XLM", "ZEC"}
H = 3_600_000
total = 0
for sym in NEW.NINE + NEW.EXTRA16:
    a, b = OLD.load_panel_B(sym, CAP), NEW.load_panel_B(sym, CAP)
    keep = np.isin(b["t"], a["t"])
    assert keep.sum() == len(a["t"]), sym
    for k in "tohlc":
        assert np.array_equal(b[k][keep], a[k]), (sym, k)
    n_add = int((~keep).sum())
    assert n_add == (120 if sym in PATCHED else 0) == b["n_patched"], (sym, n_add)
    assert (np.diff(b["t"]) == H).all(), (sym, "gap or duplicate after patch")
    if sym in PATCHED:
        added = b["t"][~keep]
        assert added.min() == 1645833600000 and added.max() == 1648940400000, sym  # 2022-02-26 00:00 .. 04-02 23:00
        assert (np.diff(a["t"]) > H).sum() == 2, (sym, "old loader should have exactly the two holes")
    total += n_add
assert total == 840, total
print(f"fix B1 loader test: OK ({total} rows added, 25 coins, no gaps or duplicates after the patch)")
