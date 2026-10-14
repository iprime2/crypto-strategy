#!/usr/bin/env python3
"""Prop-rules verifier: tools/prop_sim2.py with the funded-phase payout rule made explicit, plus inactivity and
consistency checks. Same bootstrap paths (same seed/block code) as prop_sim2 so differences are attributable.

  --payout-rule reset  : prop_sim2 behaviour. Every 30 d pay split x (eq - cycle_start) if > 0, then cycle_start = eq
                         EVEN AFTER A LOSING CYCLE (a loss month lowers the base; the next gain is paid in full).
  --payout-rule hwm    : pay split x (eq - 1.0) only when eq > initial balance (profit above the starting balance,
                         losses must be recovered first); the firm's share stays in the account.
  --payout-rule sweep  : as hwm, but after the payout the balance is reset to the initial balance (firm sweeps its share).
  --payout-cap F       : max payout per cycle = F x initial balance (HyroTrader 5%).
  --inactivity N       : evaluation terminated if the series' gross exposure is 0 for N consecutive days (FTMO-style rule).
  --consistency C      : report the share of passes whose best single-day profit exceeds C x total profit at the pass.
  --refund             : fee refunded with the first payout (HyroTrader): EV += fee x P(pass) x P(>=1 payout | funded).
  --nonpay Q           : counterparty haircut: EV_h = P(pass) x E[payout] x (1-Q) x acct - fee.
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
    done = np.zeros(n, dtype=int); t_done = np.full(n, T); payout = np.zeros(n); cycle_start = np.ones(n)
    npay = np.zeros(n, dtype=int); trips = np.zeros(n, dtype=int)
    flat_days = np.zeros(n, dtype=int); best_day = np.zeros(n); day_start_eq = np.ones(n); cons_viol = np.zeros(n, dtype=bool)
    floor_s = 1 - a.max_dd
    for t in range(T):
        live = done == 0
        if not live.any():
            break
        if t % 24 == 0:
            if t > 0:
                dprof = eq - day_start_eq
                best_day = np.where(live, np.maximum(best_day, dprof), best_day)
            day_start_eq = np.where(live, eq, day_start_eq)
            stopped[:] = False
            if funded and t > 0 and t % (24 * 30) == 0:
                if a.payout_rule == "reset":
                    profit = eq - cycle_start; pay = np.where(live & (profit > 0), a.split * profit, 0.0)
                    if a.payout_cap > 0: pay = np.minimum(pay, a.payout_cap)
                    payout += pay; eq = eq - pay; cycle_start = np.where(live, eq, cycle_start)
                else:
                    profit = eq - 1.0; pay = np.where(live & (profit > 0), a.split * profit, 0.0)
                    if a.payout_cap > 0: pay = np.minimum(pay, a.payout_cap)
                    payout += pay
                    if a.payout_rule == "hwm":
                        eq = eq - pay
                    else:  # sweep: balance back to the initial balance after a payout
                        eq = np.where(pay > 0, 1.0, eq)
                npay += (pay > 0)
                hwm = np.where(live, np.maximum(hwm, eq), hwm)
            ref = eq
            if a.balance_ref and unreal is not None:
                ref = eq * (1 - k * unreal[:, t])
            day0 = np.where(live, ref, day0); dayhi = np.where(live, eq, dayhi)
            if a.inactivity > 0 and gross is not None and not funded:
                dayflat = (gross[:, t:t + 24] == 0).all(axis=1)
                flat_days = np.where(dayflat, flat_days + 1, 0)
                term = live & (flat_days >= a.inactivity)
                done[term] = 5; t_done[term] = t
                live = done == 0
        fac = np.ones(n)
        if a.delever > 0 and (funded or a.delever_eval):
            fac = np.clip((eq - floor_s) / a.max_dd, a.delever, 1.0)
        off = stopped
        step = np.where(off, 0.0, k * fac * paths[:, t])
        eq = np.where(live, eq * (1 + step), eq)
        hwm = np.maximum(hwm, eq); dayhi = np.maximum(dayhi, eq)
        dref = dayhi if a.trailing_daily else day0
        if a.day_stop > 0 and gross is not None:
            level = dref * (1 - a.day_stop)
            trip = live & ~stopped & (eq < level)
            eq = np.where(trip, eq * (1 - k * fac * gross[:, t] * a.flat_cost), eq); stopped |= trip; trips += trip
        if a.daily_dd > 0:
            br = live & (eq < dref * (1 - a.daily_dd)); done[br] = 2; t_done[br] = t
        if a.max_dd > 0:
            floor = floor_s if a.max_dd_type == "static" else hwm * (1 - a.max_dd)
            if funded and a.max_dd_type == "trailing" and a.trail_locks:
                floor = np.minimum(floor, floor_s)
            br = live & (done == 0) & (eq < floor); done[br] = 3; t_done[br] = t
        if not funded:
            hit = live & (done == 0) & (eq >= 1 + a.target) & (t >= 24 * a.min_days)
            if a.consistency > 0:
                bd = np.maximum(best_day, eq - day_start_eq)
                cons_viol[hit] = bd[hit] > a.consistency * (eq[hit] - 1.0)
            done[hit] = 1; t_done[hit] = t
    if funded:
        done[done == 0] = 1
    return dict(done=done, t=t_done, payout=payout, trips=trips, npay=npay, cons_viol=cons_viol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--returns", required=True); ap.add_argument("--target", type=float, default=0.10)
    ap.add_argument("--daily-dd", type=float, default=0.03); ap.add_argument("--max-dd", type=float, default=0.06)
    ap.add_argument("--max-dd-type", choices=["static", "trailing"], default="static"); ap.add_argument("--trail-locks", action="store_true")
    ap.add_argument("--min-days", type=int, default=0)
    ap.add_argument("--lev", default="0.5"); ap.add_argument("--paths", type=int, default=3000); ap.add_argument("--block", type=int, default=20)
    ap.add_argument("--horizon", type=int, default=365); ap.add_argument("--fee", type=float, default=999); ap.add_argument("--account", type=float, default=100000)
    ap.add_argument("--split", type=float, default=0.8); ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--historical", action="store_true"); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--day-stop", type=float, default=0.015); ap.add_argument("--flat-cost", type=float, default=7.31e-4)
    ap.add_argument("--delever", type=float, default=0.0); ap.add_argument("--delever-eval", action="store_true")
    ap.add_argument("--trailing-daily", action="store_true"); ap.add_argument("--balance-ref", action="store_true")
    ap.add_argument("--payout-rule", choices=["reset", "hwm", "sweep"], default="reset"); ap.add_argument("--payout-cap", type=float, default=0.0)
    ap.add_argument("--inactivity", type=int, default=0); ap.add_argument("--consistency", type=float, default=0.0)
    ap.add_argument("--refund", action="store_true"); ap.add_argument("--nonpay", type=float, default=0.0)
    a = ap.parse_args()
    r, g, u = load(a.returns); rng = np.random.default_rng(a.seed)
    T = 24 * a.horizon
    if a.historical:
        starts = np.arange(0, len(r) - T, 24); ip = np.stack([np.arange(s, s + T) for s in starts])
        print(f"historical windows: {len(starts)} starts, {T // 24} days each")
    else:
        ip = boot_paths(r, a.paths, T, a.block * 24, rng)
        print(f"bootstrap: {a.paths} paths x {T // 24} days, mean block {a.block} d, series {len(r) // 24} days, "
              f"base Sharpe {r.mean() / r.std() * math.sqrt(24 * 365):.2f} base vol {r.std() * math.sqrt(24 * 365):.0%}")
    print(f"rules: target {a.target:.0%}, daily DD {a.daily_dd:.0%}, max DD {a.max_dd:.0%} {a.max_dd_type}, day stop {a.day_stop or 'none'}, "
          f"fee ${a.fee:,.0f} acct ${a.account:,.0f} split {a.split:.0%}; payout rule {a.payout_rule}; cap {a.payout_cap or 'none'}; "
          f"inactivity {a.inactivity or 'none'} d; consistency {a.consistency or 'none'}; refund {a.refund}; nonpay {a.nonpay}; "
          f"balance-ref {a.balance_ref}; trailing-daily {a.trailing_daily}; delever {a.delever}")
    paths, gp, up = r[ip], g[ip], u[ip]
    fi = boot_paths(r, min(a.paths, 2000), 24 * 30 * a.months, a.block * 24, rng); fp_, fg, fu = r[fi], g[fi], u[fi]
    print(f"{'lev':>4} {'vol':>5} | {'pass':>6} {'<=180d':>6} {'dailyDD':>7} {'maxDD':>6} {'inact':>6} {'open':>6} | {'med d':>5} {'p90 d':>5} | "
          f"{'surv12m':>7} {'P(>=1 pay)':>10} {'E[pay]':>7} {'med pay':>7} {'EV':>8} {'EV refund':>9} {'EV nonpay':>9} | {'cons viol':>9}")
    for k in [float(x) for x in a.lev.split(",")]:
        o = run_rules(paths, k, a, gross=gp, unreal=up); p = (o["done"] == 1).mean(); days = o["t"][o["done"] == 1] / 24
        f = run_rules(fp_, k, a, funded=True, gross=fg, unreal=fu); surv = (f["done"] == 1).mean(); epay = f["payout"].mean()
        ppay = (f["npay"] > 0).mean(); mpay = np.median(f["payout"])
        ev = p * epay * a.account - a.fee
        ev_ref = ev + (a.fee * p * ppay if a.refund else 0.0)
        ev_np = p * epay * (1 - a.nonpay) * a.account - a.fee
        p180 = ((o["done"] == 1) & (o["t"] <= 24 * 180)).mean()
        cv = o["cons_viol"][o["done"] == 1].mean() if (o["done"] == 1).any() else float("nan")
        print(f"{k:4.2f} {r.std() * math.sqrt(24 * 365) * k:5.0%} | {p:6.1%} {p180:6.1%} {(o['done'] == 2).mean():7.1%} {(o['done'] == 3).mean():6.1%} "
              f"{(o['done'] == 5).mean():6.1%} {(o['done'] == 0).mean():6.1%} | {np.median(days) if len(days) else float('nan'):5.0f} "
              f"{np.percentile(days, 90) if len(days) else float('nan'):5.0f} | {surv:7.1%} {ppay:10.1%} {epay:7.2%} {mpay:7.2%} {ev:8,.0f} {ev_ref:9,.0f} {ev_np:9,.0f} | {cv:9.1%}")


if __name__ == "__main__":
    main()
