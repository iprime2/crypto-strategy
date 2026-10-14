#!/usr/bin/env python3
"""Why do daily-DD breaches occur with a 1.5% day stop? Replay the sim's rules on bootstrap paths at one k and
print the hourly return and intra-day cumulative loss at the breach hour."""
import sys, math, numpy as np
sys.path.insert(0, "tools")
import prop_sim as ps
class A: pass
a = A(); a.target=0.10; a.target2=0.0; a.daily_dd=0.03; a.max_dd=0.06; a.max_dd_type="static"; a.time_limit=0; a.min_days=0
a.day_stop=0.015; a.flat_cost=7.31e-4; a.split=0.8; a.trail_locks=False
r, g = ps.load("hourly_lo_tv40.csv"); rng = np.random.default_rng(7)
ip = ps.boot_paths(r, 3000, 24*365, 20*24, rng)
k = float(sys.argv[1]); paths = r[ip]; gp = g[ip]
o = ps.run_rules(paths, k, a, gross=gp)
br = np.where(o["done"] == 2)[0]
print(f"k={k}: {len(br)} daily-DD breaches of 3000")
import collections; src = collections.Counter()
for i in br[:400]:
    t = o["t"][i]; d0 = t - t % 24
    cum = np.cumprod(1 + k * paths[i, d0+1:t+1]) - 1  # from hour 1 of the day (hour 0 sets day0)
    h = k * paths[i, t]
    src[ip[i, t]] += 1
    if i in br[:8]:
        print(f"  path {i} t={t} hour={t%24} hourly ret {h:+.2%} cum before hour {cum[-2] if len(cum)>1 else 0:+.2%} cum after {cum[-1]:+.2%}")
import csv
ts = [row["ts_utc"] for row in csv.DictReader(open("hourly_lo_tv40.csv"))]
print("  most common source hours of the breach:", [(ts[j], n) for j, n in src.most_common(6)])
