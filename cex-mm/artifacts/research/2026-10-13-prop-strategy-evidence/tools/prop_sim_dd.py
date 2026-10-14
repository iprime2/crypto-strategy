#!/usr/bin/env python3
"""prop_sim.py plus drawdown de-leveraging: effective k = k * clip((equity - floor) / max_dd, min_frac, 1),
floor = static max-DD floor (initial balance * (1 - max_dd)). Everything else identical to prop_sim.py."""
import sys, math, argparse, numpy as np
sys.path.insert(0, "tools"); import prop_sim as ps

def run_rules_dd(paths, k, a, funded=False, gross=None):
    n, T = paths.shape
    eq = np.ones(n); hwm = np.ones(n); day0 = np.ones(n); stopped = np.zeros(n, dtype=bool)
    phase = np.ones(n, dtype=int); done = np.zeros(n, dtype=int); t_done = np.full(n, T); payout = np.zeros(n); cycle_start = np.ones(n)
    targets = [a.target] + ([a.target2] if a.target2 > 0 else [])
    floor_static = 1 - a.max_dd
    for t in range(T):
        live = done == 0
        if not live.any(): break
        if t % 24 == 0: stopped[:] = False
        fac = np.clip((eq - floor_static) / a.max_dd, a.dd_delever, 1.0) if a.dd_delever > 0 else 1.0
        step = np.where(stopped, 0.0, k * fac * paths[:, t])
        eq = np.where(live, eq * (1 + step), eq); hwm = np.maximum(hwm, eq)
        if t % 24 == 0:
            if funded and t > 0 and t % (24 * 30) == 0:
                profit = eq - cycle_start; pay = np.where(live & (profit > 0), a.split * profit, 0.0)
                payout += pay; eq = eq - pay; cycle_start = np.where(live, eq, cycle_start); hwm = np.where(live, np.maximum(hwm, eq), hwm)
            day0 = np.where(live, eq, day0)
        if a.day_stop > 0 and gross is not None:
            trip = live & ~stopped & (eq < day0 * (1 - a.day_stop))
            eq = np.where(trip, eq * (1 - k * gross[:, t] * a.flat_cost), eq); stopped |= trip
        br = live & (eq < day0 * (1 - a.daily_dd)); done[br] = 2; t_done[br] = t
        br = live & (done == 0) & (eq < floor_static); done[br] = 3; t_done[br] = t
        if not funded:
            hit = live & (done == 0) & (eq >= 1 + targets[0]); done[hit] = 1; t_done[hit] = t
    if funded: done[done == 0] = 1
    return dict(done=done, t=t_done, payout=payout)

ap = argparse.ArgumentParser()
ap.add_argument("--returns", required=True); ap.add_argument("--lev", default="0.5,0.75"); ap.add_argument("--dd-delever", type=float, default=0.33)
ap.add_argument("--day-stop", type=float, default=0.015); ap.add_argument("--fee", type=float, default=999); ap.add_argument("--paths", type=int, default=3000)
ap.add_argument("--historical", action="store_true")
a = ap.parse_args(); a.target=0.10; a.target2=0.0; a.daily_dd=0.03; a.max_dd=0.06; a.flat_cost=7.31e-4; a.split=0.8; a.account=100000
r, g = ps.load(a.returns); rng = np.random.default_rng(7); T = 24 * 365
if a.historical:
    starts = np.arange(0, len(r) - T, 24); ip = np.stack([np.arange(s, s + T) for s in starts]); print(f"historical windows: {len(starts)}")
else:
    ip = ps.boot_paths(r, a.paths, T, 20 * 24, rng); print(f"bootstrap {a.paths} paths x 365 d")
fi = ps.boot_paths(r, min(a.paths, 2000), 24 * 360, 20 * 24, rng)
print(f"rules: Breakout 10%/3% daily/6% static, day stop {a.day_stop}, dd de-lever min frac {a.dd_delever} (0 = off)")
print(f"{'lev':>4} | {'pass':>6} {'p<=180d':>8} {'dailyDD':>8} {'maxDD':>6} {'open':>6} | {'med d':>5} {'p90 d':>5} | {'surv12m':>7} {'E[pay]/acct':>11} {'EV':>7}")
for k in [float(x) for x in a.lev.split(",")]:
    o = run_rules_dd(r[ip], k, a, gross=g[ip]); p = (o["done"] == 1).mean(); days = o["t"][o["done"] == 1] / 24
    f = run_rules_dd(r[fi], k, a, funded=True, gross=g[fi]); surv = (f["done"] == 1).mean(); epay = f["payout"].mean()
    print(f"{k:4.2f} | {p:6.1%} {((o['done']==1)&(o['t']<=24*180)).mean():8.1%} {(o['done']==2).mean():8.1%} {(o['done']==3).mean():6.1%} {(o['done']==0).mean():6.1%} | "
          f"{np.median(days) if len(days) else float('nan'):5.0f} {np.percentile(days,90) if len(days) else float('nan'):5.0f} | {surv:7.1%} {epay:11.2%} {p*epay*a.account-a.fee:7,.0f}")
