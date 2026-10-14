#!/usr/bin/env python3
"""D3 round 3 (POST HOC, declared): the candidate after rounds 1-2 is the pre-registered 9-coin rule executed WEEKLY.
The weekday is fixed by operations, not performance: the decision price is the Monday 00:00 UTC (05:30 IST) close,
i.e. the close of the Sunday UTC candle = offset 3 in d3_tests2.py (the WEAKEST 2022-26 offset, 0.66; kept on purpose).

 R3a  Hourly mark-to-market of 9-coin weekly (offset 3) at native TV 0.40; day-stop effect; daily tail; crash-day returns.
 R3b  prop_sim.py on that series: Breakout Classic (day stop 1.5%) bootstrap full / historical / 2025-on, no-day-stop control;
      HyroTrader trailing and static; CFT trailing-with-lock.
 R3c  Whole-Delta-contract rounding of the weekly rule on Delta prices 2024-08-10..2026-10-12 at TV 0.20 / 0.25 / 0.40 and
      capital $500 / $1,000 / $2,000 / $5,000 / $20,000 (contract values from the 2026-10-08 memo, not fetched).
"""
from __future__ import annotations
import sys, os, math, csv, datetime as dt, collections, subprocess
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools")
import trend_backtest as tb  # noqa: E402
import d3_tests as t1  # noqa: E402
import d3_tests2 as t2  # noqa: E402
import trend_hourly as th  # noqa: E402

CACHE = f"{SP}/trend-cache"; OUT = f"{SP}/d3_runs"
END = dt.date(2026, 10, 12); START = dt.date(2020, 5, 1); DS = dt.date(2024, 8, 10)
COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
CVALS = {"BTC": 0.001, "BNB": 0.1, "ETH": 0.01, "LTC": 0.1, "LINK": 1, "DOGE": 100, "BCH": 0.01, "XRP": 1, "ADA": 1}
OFFSET = 3
CRASH = [dt.date(2021, 5, 19), dt.date(2022, 5, 9), dt.date(2022, 5, 10), dt.date(2022, 5, 11), dt.date(2022, 5, 12),
         dt.date(2022, 11, 8), dt.date(2022, 11, 9), dt.date(2022, 11, 10), dt.date(2024, 8, 5), dt.date(2025, 10, 10),
         dt.date(2025, 10, 11), dt.date(2026, 2, 5), dt.date(2026, 2, 6)]


def run_rounded(close, fund, coins, tv, rebal_days, offset, start, end, capital):
    days = sorted(set().union(*[set(close[c]) for c in coins if c in close]))
    eq, units, out = capital, {}, collections.OrderedDict(); i = 0; fees = 0.0; gross = []; trades = 0; zero_days = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        if (i - offset) % rebal_days == 0:
            w = t1.sig_weights(close, d, coins, tb.LOOKS, tv, True)
            new = {}
            for c, x in w.items():
                u = round(x * eq / close[c][d] / CVALS[c]) * CVALS[c]
                if u and nxt in close[c]:
                    new[c] = u
            if sum(1 for x in w.values() if x > 0) and not new:
                zero_days += 1
        else:
            new = {c: u for c, u in units.items() if nxt in close[c]}
        i += 1
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        trades += sum(1 for c in set(new) | set(units) if abs(new.get(c, 0) - units.get(c, 0)) > 1e-12)
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * COST) / eq; fees += traded * COST / eq
        gross.append(sum(abs(u) * close[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r; out[nxt] = r; units = new
    yrs = len(out) / 365
    return dict(rets=out, fees=fees / yrs, gross=sum(gross) / len(gross), trades=trades / yrs, final=eq)


def main():
    close, fund = tb.load_binance(CACHE, END)
    dclose, dfund = tb.load_delta(CACHE, END)
    hourly = th.load_hourly(f"{SP}/hourly")
    print(f"=== R3a. 9-coin weekly, offset {OFFSET} (Monday 00:00 UTC decision price), hourly MTM, native TV 0.40 ===")
    rows = t2.hourly_mtm(close, fund, hourly, tb.COINS, 7, OFFSET, START, END, f"{OUT}/hourly_9c_weekly_off3.csv")
    for stop in (0.0, 0.015, 0.02, 0.03):
        s, n = t2.daystop_stats(rows, stop)
        print(t2.fmt(f"9c weekly off3 day stop {stop or 'none'}", s, f"stop days {n}"))
    with open(f"{OUT}/hourly_9c_weekly_off3_2025on.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["ts_utc", "ret", "gross"])
        for t, r, g in rows:
            if t >= dt.datetime(2025, 1, 1):
                wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}"])
    by_day = collections.OrderedDict()
    for t, r, g in rows:
        by_day.setdefault(t.date(), []).append(r)
    drets = {d: math.prod(1 + x for x in v) - 1 for d, v in by_day.items()}
    lows = {d: min(math.prod(1 + x for x in v[:k + 1]) for k in range(len(v))) - 1 for d, v in by_day.items()}
    yearly = collections.OrderedDict()
    for d, x in drets.items():
        yearly[d.year] = yearly.get(d.year, 1.0) * (1 + x)
    print("  by year (native): " + "  ".join(f"{y}:{v - 1:+.1%}" for y, v in yearly.items()))
    worst = sorted(drets.items(), key=lambda kv: kv[1])[:8]
    print("  native-vol daily tail: worst closes " + ", ".join(f"{d} {x:+.1%}" for d, x in worst))
    for thr in (0.02, 0.03, 0.04, 0.05):
        print(f"    close < -{thr:.0%}: {sum(1 for x in drets.values() if x < -thr)} days; intraday low < -{thr:.0%}: {sum(1 for x in lows.values() if x < -thr)} days")
    sd = t1.stats(list(drets.values()))
    print(f"  daily sd {sd['vol'] / math.sqrt(365):.2%}; at k=0.5 (TV 0.20) worst close {worst[0][1] * 0.5:+.1%}, at TV 0.25 {worst[0][1] * 0.625:+.1%}")
    print("  crash-day returns (native TV 0.40): " + "  ".join(f"{d} {drets[d]:+.1%}" for d in CRASH if d in drets))
    # exposure on those days
    gross_by_day = {}
    for t, r, g in rows:
        gross_by_day.setdefault(t.date(), g)
    print("  gross exposure entering those days: " + "  ".join(f"{d} {gross_by_day[d]:.2f}x" for d in CRASH if d in gross_by_day))

    print(f"\n=== R3b. prop_sim.py on the 9-coin weekly (offset {OFFSET}) series ===")
    sim = f"{SP}/tools/prop_sim.py"; src = f"{OUT}/hourly_9c_weekly_off3.csv"; src25 = f"{OUT}/hourly_9c_weekly_off3_2025on.csv"
    runs = [
        ("Breakout Classic 10/3/6 static, day stop 1.5%, bootstrap full", src,
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.35,0.5,0.6,0.75,1.0 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, day stop 1.5%, HISTORICAL windows", src,
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.35,0.5,0.6,0.75 --historical --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, day stop 1.5%, bootstrap 2025-01..2026-10 only", src25,
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.35,0.5,0.75 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, NO day stop, bootstrap full (control)", src,
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --lev 0.35,0.5,0.75 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("Breakout $25k account, $275 fee, day stop 1.5%, bootstrap full", src,
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.5 --paths 3000 --fee 275 --account 25000 --split 0.8"),
        ("HyroTrader 1-step 10/4/6 trailing, day stop 2%, bootstrap full", src,
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type trailing --day-stop 0.02 --lev 0.35,0.5,0.75 --paths 3000 --fee 749 --account 100000 --split 0.7"),
        ("HyroTrader if max DD is STATIC (unconfirmed), day stop 2%, bootstrap full", src,
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type static --day-stop 0.02 --lev 0.35,0.5,0.75 --paths 3000 --fee 749 --account 100000 --split 0.7"),
        ("CFT 1-step 10/4/6 trailing (locks at +6%), day stop 2%, bootstrap full", src,
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type trailing --trail-locks --day-stop 0.02 --lev 0.35,0.5,0.75 --paths 3000 --fee 599 --account 100000 --split 0.8"),
    ]
    for label, path, args in runs:
        print(f"\n--- {label}")
        out = subprocess.run([sys.executable, sim, "--returns", path] + args.split(), capture_output=True, text=True)
        print(out.stdout.strip()); print(out.stderr.strip()[-500:] if out.returncode else "", end="")

    print(f"\n=== R3c. Whole Delta contracts, weekly offset {OFFSET}, Delta 2024-08-10..2026-10-12 ===")
    for tv in (0.20, 0.25, 0.40):
        ref = t2.run_offset(dclose, dfund, tb.COINS, 7, OFFSET, DS, END) if tv == 0.40 else None
        for cap in (500, 1000, 2000, 5000, 20000):
            r = run_rounded(dclose, dfund, tb.COINS, tv, 7, OFFSET, DS, END, cap)
            s = t1.stats(list(r["rets"].values()))
            print(f"  TV {tv:.2f} capital ${cap:>6,}: CAGR {s['cagr']:+6.1%} vol {s['vol']:4.1%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} "
                  f"worst {s['worst']:+5.2%} gross {r['gross']:.2f}x trades/yr {r['trades']:4.0f} fees/yr {r['fees']:.1%} final ${r['final']:,.0f}")
    print("  unrounded reference, TV 0.40: " + t2.fmt("", t1.stats(list(ref["rets"].values()))))


if __name__ == "__main__":
    main()
