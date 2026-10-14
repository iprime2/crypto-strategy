#!/usr/bin/env python3
"""Adversarial: historical-window pass rate by START-YEAR cohort (the 1,979 overlapping windows are ~6 independent observations).
Reuses prop_sim2.run_rules read-only. Breakout 10/3/6 static, k=0.5, day stop 1.5%, $100k, $999."""
import sys, math, argparse
import numpy as np
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools")
import prop_sim2 as ps
src = sys.argv[1]; k = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
r, g, u = ps.load(src)
import csv
ts = [x["ts_utc"] for x in csv.DictReader(open(src))]
a = argparse.Namespace(target=0.10, target2=0.0, daily_dd=0.03, max_dd=0.06, max_dd_type="static", trail_locks=False, time_limit=0, min_days=0,
                       day_stop=0.015, flat_cost=7.31e-4, delever=0.0, delever_eval=False, buffer=0.0, reentry_room=0.0, chop=None, chop_n=0, chop_w=0, chop_d=0,
                       trailing_daily=False, balance_ref=False, split=0.8, horizon=365)
T = 24 * 365
starts = np.arange(0, len(r) - T, 24)
ipaths = np.stack([np.arange(s, s + T) for s in starts])
o = ps.run_rules(r[ipaths], k, a, gross=g[ipaths], unreal=u[ipaths])
years = np.array([int(ts[s][:4]) for s in starts]); halves = np.array([ts[s][:4] + ("H1" if int(ts[s][5:7]) <= 6 else "H2") for s in starts])
print(f"{src.split('/')[-1]} k={k}: {len(starts)} windows; overall pass {(o['done']==1).mean():.1%} dailyDD {(o['done']==2).mean():.1%} maxDD {(o['done']==3).mean():.1%} open {(o['done']==0).mean():.1%}")
for y in sorted(set(halves)):
    m = halves == y; d = o["done"][m]
    print(f"  start {y}: n={m.sum():3d} pass {(d==1).mean():5.1%} maxDD-bust {(d==3).mean():5.1%} dailyDD {(d==2).mean():4.1%} open@365d {(d==0).mean():5.1%}")
# runs of consecutive pass/fail to show dependence
d = o["done"]; p = (d == 1).astype(int); changes = (np.diff(p) != 0).sum() + 1
print(f"  pass indicator switches {changes} times across {len(p)} consecutive start days -> effective independent windows ~{changes}")
