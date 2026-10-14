#!/usr/bin/env python3
"""prop_sim.py extended with the judges' grafts (everything else identical to tools/prop_sim.py):
  --delever F         funded phase: effective k = k * clip((eq - 0.94)/0.06, F, 1)   (D1 graft; --delever-eval applies it in the evaluation too)
  --buffer B          internal stop level S = max(day0*(1-day_stop), 0.94 + B); and open nothing on a day whose 00:00 room to the 6% floor < B
  --reentry-room R    after a day-stop trip re-enter at the next 00:00 only if eq - 0.94 >= R, else stay flat to the next 7-day boundary
  --chop N W D        N day-stop trips within W days -> k halved for D days
  --trailing-daily    daily limit and day stop measured from the day's running equity high (HyroTrader default per the addendum)
  --balance-ref       daily reference = 00:00 equity minus unrealized PnL of open positions (Breakout 'balance excluding open positions'),
                      using the engine's unreal column scaled by k
Reports also the share of paths with >= 1 stop trip and trips per year.
"""
from __future__ import annotations
import argparse, csv, math
import numpy as np


def load(path):
    rows = list(csv.DictReader(open(path)))
    r = np.array([float(x["ret"]) for x in rows]); g = np.array([float(x.get("gross", 1.0)) for x in rows])
    u = np.array([float(x.get("unreal", 0.0)) for x in rows])
    return r, g, u


def boot_paths(r, n, length, block_h, rng):
    starts0 = np.arange(0, len(r) - block_h * 4, 24)
    out = np.empty((n, length), dtype=int); idx = np.arange(len(r))
    for i in range(n):
        pos = 0
        while pos < length:
            L = max(24, int(rng.geometric(1 / block_h) // 24 * 24)); s = rng.choice(starts0)
            seg = idx[s:s + L]; take = min(len(seg), length - pos)
            out[i, pos:pos + take] = seg[:take]; pos += take
    return out


def run_rules(paths, k, a, funded=False, gross=None, unreal=None):
    n, T = paths.shape
    eq = np.ones(n); hwm = np.ones(n); day0 = np.ones(n); dayhi = np.ones(n); stopped = np.zeros(n, dtype=bool)
    flat_day = np.zeros(n, dtype=bool); flat_week = np.zeros(n, dtype=bool)
    phase = np.ones(n, dtype=int); done = np.zeros(n, dtype=int); t_done = np.full(n, T); payout = np.zeros(n); cycle_start = np.ones(n)
    trips = np.zeros(n, dtype=int); chop_until = np.full(n, -1); trip_hist = np.full((n, max(a.chop_n, 1)), -10 ** 9)
    targets = [a.target] + ([a.target2] if a.target2 > 0 else [])
    floor_s = 1 - a.max_dd
    for t in range(T):
        live = done == 0
        if not live.any():
            break
        if t % 24 == 0:
            # re-entry rule after a trip: need room >= R at the reset, else flat until the next 7-day boundary
            if a.reentry_room > 0:
                need = stopped & (eq - floor_s < a.reentry_room)
                flat_week = np.where(need, True, flat_week)
                if t % (24 * 7) == 0:
                    flat_week[:] = False
            stopped[:] = False
            if funded and t > 0 and t % (24 * 30) == 0:
                profit = eq - cycle_start; pay = np.where(live & (profit > 0), a.split * profit, 0.0)
                payout += pay; eq = eq - pay; cycle_start = np.where(live, eq, cycle_start); hwm = np.where(live, np.maximum(hwm, eq), hwm)
            ref = eq
            if a.balance_ref and unreal is not None:
                ref = eq * (1 - k * unreal[:, t])
            day0 = np.where(live, ref, day0); dayhi = np.where(live, eq, dayhi)
            flat_day = (eq - floor_s < a.buffer) if a.buffer > 0 else np.zeros(n, dtype=bool)
        fac = np.ones(n)
        if a.delever > 0 and (funded or a.delever_eval):
            fac = np.clip((eq - floor_s) / a.max_dd, a.delever, 1.0)
        if a.chop_n > 0:
            fac = np.where(chop_until > t, fac * 0.5, fac)
        off = stopped | flat_day | flat_week
        step = np.where(off, 0.0, k * fac * paths[:, t])
        eq = np.where(live, eq * (1 + step), eq)
        hwm = np.maximum(hwm, eq); dayhi = np.maximum(dayhi, eq)
        dref = dayhi if a.trailing_daily else day0
        if a.day_stop > 0 and gross is not None:
            level = dref * (1 - a.day_stop)
            if a.buffer > 0:
                level = np.maximum(level, floor_s + a.buffer)
            trip = live & ~stopped & ~flat_day & ~flat_week & (eq < level)
            eq = np.where(trip, eq * (1 - k * fac * gross[:, t] * a.flat_cost), eq); stopped |= trip
            trips += trip
            if a.chop_n > 0 and trip.any():
                trip_hist[trip] = np.roll(trip_hist[trip], -1, axis=1); trip_hist[trip, -1] = t
                recent = trip & (trip_hist[:, 0] >= t - a.chop_w * 24)
                chop_until = np.where(recent, t + a.chop_d * 24, chop_until)
        if a.daily_dd > 0:
            br = live & (eq < dref * (1 - a.daily_dd)); done[br] = 2; t_done[br] = t
        if a.max_dd > 0:
            floor = floor_s if a.max_dd_type == "static" else hwm * (1 - a.max_dd)
            if funded and a.max_dd_type == "trailing" and a.trail_locks:
                floor = np.minimum(floor, floor_s)
            br = live & (done == 0) & (eq < floor); done[br] = 3; t_done[br] = t
        if not funded:
            for ph, tg in enumerate(targets, start=1):
                hit = live & (done == 0) & (phase == ph) & (eq >= 1 + tg) & (t >= 24 * a.min_days)
                if ph < len(targets):
                    phase[hit] = ph + 1; eq[hit] = 1.0; hwm[hit] = 1.0; day0[hit] = 1.0
                else:
                    done[hit] = 1; t_done[hit] = t
        if a.time_limit > 0 and not funded:
            to = live & (done == 0) & (t >= 24 * a.time_limit * len(targets)); done[to] = 4; t_done[to] = t
    if funded:
        done[done == 0] = 1
    return dict(done=done, t=t_done, payout=payout, trips=trips)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--returns", required=True); ap.add_argument("--target", type=float, default=0.10); ap.add_argument("--target2", type=float, default=0.0)
    ap.add_argument("--daily-dd", type=float, default=0.03); ap.add_argument("--max-dd", type=float, default=0.06)
    ap.add_argument("--max-dd-type", choices=["static", "trailing"], default="static"); ap.add_argument("--trail-locks", action="store_true")
    ap.add_argument("--time-limit", type=int, default=0); ap.add_argument("--min-days", type=int, default=0)
    ap.add_argument("--lev", default="0.5"); ap.add_argument("--paths", type=int, default=3000); ap.add_argument("--block", type=int, default=20)
    ap.add_argument("--horizon", type=int, default=365); ap.add_argument("--fee", type=float, default=999); ap.add_argument("--account", type=float, default=100000)
    ap.add_argument("--split", type=float, default=0.8); ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--historical", action="store_true"); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--day-stop", type=float, default=0.015); ap.add_argument("--flat-cost", type=float, default=7.31e-4)
    ap.add_argument("--delever", type=float, default=0.0); ap.add_argument("--delever-eval", action="store_true")
    ap.add_argument("--buffer", type=float, default=0.0); ap.add_argument("--reentry-room", type=float, default=0.0)
    ap.add_argument("--chop", nargs=3, type=int, default=None, metavar=("N", "W", "D"))
    ap.add_argument("--trailing-daily", action="store_true"); ap.add_argument("--balance-ref", action="store_true")
    a = ap.parse_args()
    a.chop_n, a.chop_w, a.chop_d = a.chop if a.chop else (0, 0, 0)
    r, g, u = load(a.returns); rng = np.random.default_rng(a.seed)
    phases = 2 if a.target2 > 0 else 1
    T = 24 * (a.time_limit * phases if a.time_limit > 0 else a.horizon)
    if a.historical:
        starts = np.arange(0, len(r) - T, 24); ip = np.stack([np.arange(s, s + T) for s in starts])
        print(f"historical windows: {len(starts)} starts, {T // 24} days each")
    else:
        ip = boot_paths(r, a.paths, T, a.block * 24, rng)
        print(f"bootstrap: {a.paths} paths x {T // 24} days, mean block {a.block} d, series {len(r) // 24} days, "
              f"base Sharpe {r.mean() / r.std() * math.sqrt(24 * 365):.2f} base vol {r.std() * math.sqrt(24 * 365):.0%}")
    grafts = []
    if a.delever: grafts.append(f"delever min {a.delever}" + (" (eval too)" if a.delever_eval else " (funded only)"))
    if a.buffer: grafts.append(f"buffer {a.buffer}")
    if a.reentry_room: grafts.append(f"re-entry room {a.reentry_room}")
    if a.chop_n: grafts.append(f"chop {a.chop_n} trips/{a.chop_w} d -> k/2 for {a.chop_d} d")
    if a.trailing_daily: grafts.append("trailing intraday daily ref")
    if a.balance_ref: grafts.append("balance-based daily ref (eq - unrealized)")
    print(f"rules: target {a.target:.0%}, daily DD {a.daily_dd:.0%}, max DD {a.max_dd:.0%} {a.max_dd_type}, time limit {a.time_limit or 'none'}, "
          f"day stop {a.day_stop or 'none'}, fee ${a.fee:,.0f} acct ${a.account:,.0f} split {a.split:.0%}; grafts: {', '.join(grafts) or 'none'}")
    paths, gp, up = r[ip], g[ip], u[ip]
    fi = boot_paths(r, min(a.paths, 2000), 24 * 30 * a.months, a.block * 24, rng); fp_, fg, fu = r[fi], g[fi], u[fi]
    print(f"{'lev':>4} {'vol':>5} | {'pass':>6} {'pass<=180d':>10} {'dailyDD':>8} {'maxDD':>6} {'timeout':>8} {'open':>6} | {'med d':>5} {'p90 d':>5} | "
          f"{'funded surv':>11} {'E[pay]/acct':>11} {'EV/challenge':>12} | {'paths>=1 trip':>13} {'trips/yr':>8}")
    for k in [float(x) for x in a.lev.split(",")]:
        o = run_rules(paths, k, a, gross=gp, unreal=up); p = (o["done"] == 1).mean(); days = o["t"][o["done"] == 1] / 24
        f = run_rules(fp_, k, a, funded=True, gross=fg, unreal=fu); surv = (f["done"] == 1).mean(); epay = f["payout"].mean()
        ev = p * epay * a.account - a.fee; p180 = ((o["done"] == 1) & (o["t"] <= 24 * 180)).mean()
        yrs = (o["t"] / 24 / 365).mean()
        print(f"{k:4.2f} {r.std() * math.sqrt(24 * 365) * k:5.0%} | {p:6.1%} {p180:10.1%} {(o['done'] == 2).mean():8.1%} {(o['done'] == 3).mean():6.1%} "
              f"{(o['done'] == 4).mean():8.1%} {(o['done'] == 0).mean():6.1%} | {np.median(days) if len(days) else float('nan'):5.0f} "
              f"{np.percentile(days, 90) if len(days) else float('nan'):5.0f} | {surv:11.1%} {epay:11.2%} {ev:12,.0f} | "
              f"{(o['trips'] > 0).mean():13.1%} {o['trips'].mean() / max(yrs, 1e-9):8.1f}")


if __name__ == "__main__":
    main()
