"""C6 (sensitivity only, not the plan's panel): OT gates with the Phase 1 coins that also had continuous Binance spot
USDT history before 2020-04 but are not in the plan's enumerated 13 (ONT IOTA QTUM VET IOST BAT ZEC XMR DASH ATOM XTZ
BCH). Same engine and rules as the base OT run (first full prior week, 99 % coverage, through week 2020-04-20)."""
import glob
import json
import pickle
import sys

import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv"
sys.path.insert(0, D)
import adv_lib as A  # noqa: E402

EXTRA = ["ONT", "IOTA", "QTUM", "VET", "IOST", "BAT", "ZEC", "XMR", "DASH", "ATOM", "XTZ", "BCH"]
EXTRA_2018 = ["ONT", "IOTA", "QTUM", "VET"]


def load_extra(sym):
    files = sorted(glob.glob(f"{D}/dl_spot/{sym}/{sym}USDT-5m-*.csv"))
    parts = [A._read(f) for f in files]
    t = np.concatenate([p[0] for p in parts])
    x = np.concatenate([p[1] for p in parts])
    n = np.concatenate([p[2] for p in parts])
    off = int((t % A.BAR != 0).sum())
    k = t % A.BAR == 0
    t, x, n = t[k], x[k], n[k]
    order = np.argsort(t, kind="stable")
    t, x, n = t[order], x[order], n[order]
    keep = np.r_[True, t[1:] != t[:-1]]
    t, x, n = t[keep], x[keep], n[keep]
    k = t < A.ts("2020-05-01")
    t, x, n = t[k], x[k], n[k]
    return dict(t=t, o=x[:, 0], h=x[:, 1], l=x[:, 2], c=x[:, 3], v=x[:, 4], n=n, end=int(t[-1]) + A.BAR,
                eff_end=None, off_grid=off)


def weeks_OT(c, b):
    first = int(A.monday(b["t"][0] - 1)) + 2 * A.WK
    return list(range(first, A.ts("2020-04-20") + 1, A.WK))


bars = {c: A.load("OT", c) for c in A.OT_COINS}
for c in EXTRA:
    bars[c] = load_extra(c)
print("off-grid rows dropped:", {c: bars[c]["off_grid"] for c in EXTRA})
out = {}
for name, coins in (("OT13_plan", A.OT_COINS), ("OT13+4_2018", A.OT_COINS + EXTRA_2018),
                    ("OT13+12_all", A.OT_COINS + EXTRA), ("extra12_only", EXTRA)):
    ev, wk = A.build("OT", coins, bars, weeks_fn=weeks_OT)
    ev = A.attach(ev, bars)
    e = ev[(ev.status == "ok") & (ev.horizon == "4h")]
    weeks = sorted(wk.W[wk.used].unique())
    g = A.gates(e[e.control == "real"], e[e.control == "P1"], weeks, coins, A.ts("2019-01-01"))
    g["coin_weeks_used"] = int(wk.used.sum())
    r = e[e.control == "real"]
    g["per_coin_net"] = {c: round(float(v), 2) for c, v in (r.groupby("coin").gross.mean() - 14.62).items()}
    out[name] = g
    print(f"{name:14s} coins {len(coins)} | net {g['net']:6.2f} P {g['p_net']:.4f} | diff {g['diff']:6.2f} "
          f"P {g['p_diff']:.4f} | H1 {g['h1']:6.2f} H2 {g['h2']:6.2f} | coins {g['coins_pos']}/{g['need']} | n {g['n']} "
          f"| cw {g['coin_weeks_used']} | all {g['all']}")
print("extra coins per-coin net:", {c: v for c, v in out["OT13+12_all"]["per_coin_net"].items() if c in EXTRA})
json.dump(out, open(f"{D}/c6_ot_extended.json", "w"), indent=1, default=float)
