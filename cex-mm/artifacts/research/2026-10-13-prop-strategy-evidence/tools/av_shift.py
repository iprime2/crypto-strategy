#!/usr/bin/env python3
"""Adversarial: make drift-shifted copies of an hourly series so the DAILY Sharpe equals a target (0.9/0.7/0.5/0.0),
keeping vol, tails and autocorrelation. Writes qd-style CSVs for prop_sim2.py."""
import csv, math, sys, collections
import numpy as np
src, out_prefix = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(src)))
r = np.array([float(x["ret"]) for x in rows]); ts = [x["ts_utc"] for x in rows]
by = collections.OrderedDict()
for t, v in zip(ts, r): by[t[:10]] = by.get(t[:10], 1.0) * (1 + v)
d = np.array([v - 1 for v in by.values()]); sd = d.std(ddof=1); mu = d.mean()
print(f"source daily Sharpe {mu/sd*math.sqrt(365):.2f} vol {sd*math.sqrt(365):.1%}")
for tgt in [float(x) for x in sys.argv[3].split(",")]:
    shift_daily = tgt * sd / math.sqrt(365) - mu
    rr = r + shift_daily / 24
    by2 = collections.OrderedDict()
    for t, v in zip(ts, rr): by2[t[:10]] = by2.get(t[:10], 1.0) * (1 + v)
    d2 = np.array([v - 1 for v in by2.values()])
    p = f"{out_prefix}_sh{tgt:.1f}.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts_utc", "ret", "gross", "unreal"])
        for x, v in zip(rows, rr): w.writerow([x["ts_utc"], f"{v:.10f}", x["gross"], x.get("unreal", "0")])
    print(f"  target {tgt}: daily Sharpe {d2.mean()/d2.std(ddof=1)*math.sqrt(365):.2f} -> {p}")
