#!/usr/bin/env python3
"""Prop-firm challenge Monte Carlo on an hourly strategy return series.

Rules modelled: profit target per phase (1 or 2 phases), daily loss limit vs start-of-day (00:00 UTC) equity,
max drawdown (static from initial balance, or trailing on the equity high-water mark), time limit, and a
funded phase with 30-day payouts at a profit split. Leverage multiplier k scales every hourly return by k.

Paths: stationary block bootstrap of the hourly series (mean block --block days), plus --historical which
starts a challenge on every actual day in the series. Hourly granularity understates intra-hour breaches. The daily reference is the equity at 00:00 UTC before that hour's return (an earlier version used the 01:00 equity, which is about $300 of EV more lenient on a $100k Breakout account).

  python3 scripts/prop_sim.py --returns hourly.csv --target 0.08 --target2 0.05 --daily-dd 0.05 --max-dd 0.10 --max-dd-type static
      --time-limit 0 --lev 1,2,3,4,5,6 --paths 4000 --fee 500 --account 100000 --split 0.8 --months 12
  python3 scripts/prop_sim.py --selftest
"""
from __future__ import annotations
import argparse, csv, math
import numpy as np

def load(path: str):
    rows = list(csv.DictReader(open(path)))
    return np.array([float(r["ret"]) for r in rows]), np.array([float(r.get("gross", 1.0)) for r in rows])

def boot_paths(r: np.ndarray, n: int, length: int, block_h: int, rng) -> np.ndarray:
    """Stationary bootstrap (Politis-Romano): blocks start anywhere, length geometric with mean block_h, aligned to 00:00."""
    starts0 = np.arange(0, len(r) - block_h * 4, 24)  # block starts on day boundaries so 00:00 checks stay aligned
    out = np.empty((n, length), dtype=int)
    idx = np.arange(len(r))
    for i in range(n):
        pos = 0
        while pos < length:
            L = max(24, int(rng.geometric(1 / block_h) // 24 * 24))
            s = rng.choice(starts0)
            seg = idx[s:s + L]
            take = min(len(seg), length - pos)
            out[i, pos:pos + take] = seg[:take]; pos += take
    return out

def run_rules(paths: np.ndarray, k: float, a, funded: bool = False, gross: np.ndarray | None = None):
    """Vectorised hour loop. Returns dict of outcome arrays. --day-stop flattens for the rest of the UTC day once
    the day's loss exceeds that fraction (charged taker+slippage on gross exposure)."""
    n, T = paths.shape
    eq = np.ones(n); hwm = np.ones(n); day0 = np.ones(n); stopped = np.zeros(n, dtype=bool)
    phase = np.ones(n, dtype=int); done = np.zeros(n, dtype=int)  # 0 running, 1 pass, 2 daily breach, 3 max breach, 4 timeout
    t_done = np.full(n, T); payout = np.zeros(n); cycle_start = np.ones(n)
    targets = [a.target] + ([a.target2] if a.target2 > 0 else [])
    for t in range(T):
        live = done == 0
        if not live.any():
            break
        if t % 24 == 0:  # 00:00 UTC: payout (funded phase), then fix the day's reference equity BEFORE hour 0's return
            stopped[:] = False
            if funded and t > 0 and t % (24 * 30) == 0:
                profit = eq - cycle_start
                pay = np.where(live & (profit > 0), a.split * profit, 0.0)
                payout += pay; eq = eq - pay; cycle_start = np.where(live, eq, cycle_start)  # withdraw the split, keep the rest
                hwm = np.where(live, np.maximum(hwm, eq), hwm)
            day0 = np.where(live, eq, day0)
        step = np.where(stopped, 0.0, k * paths[:, t])
        eq = np.where(live, eq * (1 + step), eq)
        hwm = np.maximum(hwm, eq)
        if a.day_stop > 0 and gross is not None:
            trip = live & ~stopped & (eq < day0 * (1 - a.day_stop))
            eq = np.where(trip, eq * (1 - k * gross[:, t] * a.flat_cost), eq)
            stopped |= trip
        if a.daily_dd > 0:
            br = live & (eq < day0 * (1 - a.daily_dd))
            done[br] = 2; t_done[br] = t
        if a.max_dd > 0:
            floor = (1 - a.max_dd) if a.max_dd_type == "static" else hwm * (1 - a.max_dd)
            if funded and a.max_dd_type == "trailing":
                floor = np.minimum(floor, 1 - a.max_dd) if a.trail_locks else floor
            br = live & (done == 0) & (eq < floor)
            done[br] = 3; t_done[br] = t
        if not funded:
            for ph, tg in enumerate(targets, start=1):
                hit = live & (done == 0) & (phase == ph) & (eq >= 1 + tg) & (t >= 24 * a.min_days)
                if ph < len(targets):
                    phase[hit] = ph + 1; eq[hit] = 1.0; hwm[hit] = 1.0; day0[hit] = 1.0
                else:
                    done[hit] = 1; t_done[hit] = t
        if a.time_limit > 0 and not funded:
            to = live & (done == 0) & (t >= 24 * a.time_limit * len(targets))
            done[to] = 4; t_done[to] = t
    if funded:
        done[done == 0] = 1  # survived the whole funded horizon
    return dict(done=done, t=t_done, payout=payout)

def selftest() -> None:
    """Deterministic checks of the rule engine (no bootstrap)."""
    class A:  # minimal args namespace
        target = 0.10; target2 = 0.0; daily_dd = 0.03; max_dd = 0.06; max_dd_type = "static"; trail_locks = False
        time_limit = 0; min_days = 0; day_stop = 0.0; flat_cost = 7.31e-4; split = 0.8
    a = A()
    # 1) steady +0.05%/h passes the 10% target: 1.0005^n >= 1.10 -> n = 191 steps, hour index 190
    steady = np.full((1, 24 * 30), 0.0005)
    o = run_rules(steady, 1.0, a)
    assert o["done"][0] == 1 and o["t"][0] == 190, (o["done"], o["t"])
    # 2) a -4% hour on day 3 breaches the 3% daily limit, not the 6% max DD
    path = np.zeros((1, 24 * 5)); path[0, 24 * 2 + 5] = -0.04
    o = run_rules(path, 1.0, a)
    assert o["done"][0] == 2 and o["t"][0] == 24 * 2 + 5, (o["done"], o["t"])
    # 2b) a -4% return in hour 0 of day 2 trips the daily limit at that hour (the first version measured from the 01:00 equity)
    path = np.zeros((1, 24 * 5)); path[0, 24] = -0.04
    o = run_rules(path, 1.0, a)
    assert o["done"][0] == 2 and o["t"][0] == 24, (o["done"], o["t"])
    # 3) -2.5% a day for three days passes the daily limit but breaches the static 6% max DD
    path = np.zeros((1, 24 * 5)); path[0, [12, 36, 60]] = -0.025
    o = run_rules(path, 1.0, a)
    assert o["done"][0] == 3, o["done"]
    # 4) the day stop flattens the rest of the day: -2% then -2% in the same day survives with a 1.5% stop
    path = np.zeros((1, 24 * 3)); path[0, 5] = -0.02; path[0, 6] = -0.02
    a.day_stop = 0.015
    o = run_rules(path, 1.0, a, gross=np.full_like(path, 0.2))
    assert o["done"][0] == 0, o["done"]
    a.day_stop = 0.0
    o = run_rules(path, 1.0, a, gross=np.full_like(path, 0.2))
    assert o["done"][0] == 2, o["done"]
    # 5) leverage 2x doubles the hourly step: 1.001^n >= 1.10 -> n = 96 steps, hour index 95
    o = run_rules(steady, 2.0, a)
    assert o["t"][0] == 95, o["t"]
    # 6) funded phase: a payout of 80% of the profit at t = 720, before that hour's return (720 steps)
    f = run_rules(np.full((1, 24 * 31), 0.0005), 1.0, a, funded=True)
    assert abs(f["payout"][0] - 0.8 * (1.0005 ** 720 - 1)) < 1e-9, f["payout"]
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--returns", default=None); ap.add_argument("--target", type=float, default=0.08); ap.add_argument("--target2", type=float, default=0.0)
    ap.add_argument("--daily-dd", type=float, default=0.05); ap.add_argument("--max-dd", type=float, default=0.10)
    ap.add_argument("--max-dd-type", choices=["static", "trailing"], default="static"); ap.add_argument("--trail-locks", action="store_true", help="trailing floor locks at the initial balance once above it")
    ap.add_argument("--time-limit", type=int, default=0, help="days per phase, 0 = none"); ap.add_argument("--min-days", type=int, default=0)
    ap.add_argument("--lev", default="1,2,3,4,5,6"); ap.add_argument("--paths", type=int, default=3000); ap.add_argument("--block", type=int, default=20, help="mean bootstrap block, days")
    ap.add_argument("--horizon", type=int, default=365, help="max challenge days when no time limit")
    ap.add_argument("--fee", type=float, default=0.0); ap.add_argument("--account", type=float, default=100000); ap.add_argument("--split", type=float, default=0.8); ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--historical", action="store_true"); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--day-stop", type=float, default=0.0, help="flatten for the rest of the day at this loss vs 00:00 equity (e.g. 0.03)")
    ap.add_argument("--flat-cost", type=float, default=7.31e-4, help="taker+slippage charged on gross when the day stop trips")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.returns:
        ap.error("--returns is required (or --selftest)")
    r, g = load(a.returns); rng = np.random.default_rng(a.seed)
    phases = 2 if a.target2 > 0 else 1
    T = 24 * (a.time_limit * phases if a.time_limit > 0 else a.horizon)
    if a.historical:
        starts = np.arange(0, len(r) - T, 24)
        ipaths = np.stack([np.arange(s, s + T) for s in starts])
        print(f"historical windows: {len(starts)} starts, {T // 24} days each")
    else:
        ipaths = boot_paths(r, a.paths, T, a.block * 24, rng)
        print(f"bootstrap: {a.paths} paths x {T // 24} days, mean block {a.block} d, series {len(r) // 24} days, "
              f"base Sharpe {r.mean() / r.std() * math.sqrt(24 * 365):.2f} base vol {r.std() * math.sqrt(24 * 365):.0%}")
    print(f"rules: target {a.target:.0%}" + (f" then {a.target2:.0%}" if phases == 2 else "") + f", daily DD {a.daily_dd:.0%} vs 00:00 equity, "
          f"max DD {a.max_dd:.0%} {a.max_dd_type}, time limit {a.time_limit or 'none'} d/phase, min days {a.min_days}, day stop {a.day_stop or 'none'}")
    paths, gpaths = r[ipaths], g[ipaths]
    fund_T = 24 * 30 * a.months
    fi = boot_paths(r, min(a.paths, 2000), fund_T, a.block * 24, rng); fpaths, fg = r[fi], g[fi]
    print(f"{'lev':>4} {'vol':>5} | {'pass':>6} {'pass<=180d':>10} {'dailyDD':>8} {'maxDD':>6} {'timeout':>8} {'open':>6} | {'med days':>8} {'p90 days':>8} | {'funded surv':>11} {'E[payout]/acct':>14} {'EV per challenge':>16}")
    for k in [float(x) for x in a.lev.split(",")]:
        o = run_rules(paths, k, a, gross=gpaths)
        n = len(o["done"]); p = (o["done"] == 1).mean()
        days = o["t"][o["done"] == 1] / 24
        f = run_rules(fpaths, k, a, funded=True, gross=fg)
        surv = (f["done"] == 1).mean(); epay = f["payout"].mean()
        ev = p * epay * a.account - a.fee
        p180 = ((o["done"] == 1) & (o["t"] <= 24 * 180)).mean()
        print(f"{k:4.2f} {r.std() * math.sqrt(24 * 365) * k:5.0%} | {p:6.1%} {p180:10.1%} {(o['done'] == 2).mean():8.1%} {(o['done'] == 3).mean():6.1%} {(o['done'] == 4).mean():8.1%} {(o['done'] == 0).mean():6.1%} | "
              f"{np.median(days) if len(days) else float('nan'):8.0f} {np.percentile(days, 90) if len(days) else float('nan'):8.0f} | "
              f"{surv:11.1%} {epay:14.2%} {ev:16,.0f}")

if __name__ == "__main__":
    main()
