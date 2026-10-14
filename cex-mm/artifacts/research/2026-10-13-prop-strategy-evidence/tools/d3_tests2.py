#!/usr/bin/env python3
"""D3 round 2 (POST HOC, declared as such): after d3_tests.py showed (a) BTC-only daily (B1) and 9-coin weekly (B6) both pass
the pre-declared thresholds and (b) BTC+ETH weekly (B7) narrowly fails, this script runs the follow-ups that round 1 did not
pre-declare. Everything run is printed.

 R2a  B1 (BTC only, daily) on Delta 2024-08-10..2026-10-12, same-day correlation with the Binance run.
 R2b  Weekly-rebalance weekday-offset robustness (offset 0..6 from 2020-05-01) for BTC-only, BTC+ETH and 9 coins:
      Binance full period Sharpe / 2022..2026 Sharpe / maxDD, and Delta 2024-08..2026-10 Sharpe for the same offset.
 R2c  Hourly mark-to-market of the candidate (BTC only, weekly, offset 0) and of BTC-only daily, written to d3_runs/*.csv,
      with the own-account effect of an intraday day stop (1.5 / 2 / 3%) on each.
 R2d  prop_sim.py on the candidate series: Breakout Classic 10/3/6 static (day stop 1.5%), HyroTrader 10/4/6 trailing
      (day stop 2%), CFT 10/4/6 trailing (day stop 2%); bootstrap full sample, historical windows, and 2025-01..2026-10 bootstrap.
"""
from __future__ import annotations
import sys, os, math, csv, datetime as dt, collections, subprocess
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools")
import trend_backtest as tb  # noqa: E402
import d3_tests as t1  # noqa: E402
import trend_hourly as th  # noqa: E402

CACHE = f"{SP}/trend-cache"; OUT = f"{SP}/d3_runs"; os.makedirs(OUT, exist_ok=True)
END = dt.date(2026, 10, 12); START = dt.date(2020, 5, 1); DS = dt.date(2024, 8, 10)
COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4


def run_offset(close, fund, coins, rebal_days, offset, start, end):
    """t1.run with the weekly clock shifted by `offset` days: the first rebalance happens on day index == offset."""
    days = sorted(set().union(*[set(close[c]) for c in coins if c in close]))
    eq, units, out = 1.0, {}, collections.OrderedDict(); i = 0; fees = 0.0; gross = []; trades = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        if (i - offset) % rebal_days == 0:
            w = t1.sig_weights(close, d, coins, tb.LOOKS, tb.TARGET_VOL, True)
            new = {c: x * eq / close[c][d] for c, x in w.items() if x and nxt in close[c]}
        else:
            new = {c: u for c, u in units.items() if nxt in close[c]}
        i += 1
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        trades += sum(1 for c in set(new) | set(units) if abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] > 1e-9)
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * COST) / eq; fees += traded * COST / eq
        gross.append(sum(abs(u) * close[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r; out[nxt] = r; units = new
    yrs = len(out) / 365
    return dict(rets=out, fees=fees / yrs, funding=0.0, gross=sum(gross) / len(gross), trades=trades / yrs)


def hourly_mtm(close, fund, hourly, coins, rebal_days, offset, start, end, path):
    """Mirror of tools/trend_hourly.py: weights decided at the 00:00 UTC close, costs in hour 0, funding in thirds at 0/8/16."""
    days = sorted(set().union(*[set(close[c]) for c in coins if c in close]))
    eq, units, rows = 1.0, {}, []; i = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        if (i - offset) % rebal_days == 0:
            w = t1.sig_weights(close, d, coins, tb.LOOKS, tb.TARGET_VOL, True)
            new = {c: x * eq / close[c][d] for c, x in w.items() if x and nxt in close[c] and c in hourly}
        else:
            new = {c: u for c, u in units.items() if nxt in close[c]}
        i += 1
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        prev = {c: close[c][d] for c in new}
        for h in range(24):
            t = dt.datetime(nxt.year, nxt.month, nxt.day, h); pnl = 0.0
            for c, u in new.items():
                px = hourly[c].get(t)
                if px is None:
                    px = prev[c]
                pnl += u * (px - prev[c]); prev[c] = px
            charge = traded * COST if h == 0 else 0.0
            fp = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items()) / 3 if h in (0, 8, 16) else 0.0
            r = (pnl - fp - charge) / eq
            eq *= 1 + r
            rows.append((t, r, sum(abs(u) * prev[c] for c, u in new.items()) / eq))
        units = new
    with open(path, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["ts_utc", "ret", "gross"])
        for t, r, g in rows:
            wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}"])
    return rows


def daystop_stats(rows, stop):
    """Daily returns from the hourly rows with an intraday day stop: flatten for the rest of the UTC day when the day's
    cumulative return < -stop, charging taker+slippage on gross once."""
    by_day = collections.OrderedDict()
    for t, r, g in rows:
        by_day.setdefault(t.date(), []).append((r, g))
    drets = []; stops = 0
    for d, hs in by_day.items():
        e = 1.0; stopped = False
        for r, g in hs:
            if stopped:
                continue
            e *= 1 + r
            if stop and e - 1 < -stop:
                e *= 1 - g * COST; stopped = True; stops += 1
        drets.append(e - 1)
    s = t1.stats(drets)
    return s, stops


def fmt(label, s, extra=""):
    return (f"{label:46s} CAGR {s['cagr']:+6.1%} vol {s['vol']:4.0%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} "
            f"CAGR/DD {s['calmar']:4.2f} worst {s['worst']:+6.2%} {extra}")


def main():
    close, fund = tb.load_binance(CACHE, END)
    dclose, dfund = tb.load_delta(CACHE, END)
    print("=== R2a. B1 BTC-only daily on Delta 2024-08-10..2026-10-12 ===")
    dbtc = t1.bh(dclose, ["BTC"], DS, END)["rets"]
    rd = t1.run(dclose, dfund, ["BTC"], start=DS, end=END); rb = t1.run(close, fund, ["BTC"], start=DS, end=END)
    t1.row("B1 BTC only on Delta", rd, dbtc)
    t1.row("B1 BTC only on Binance, same window", rb, dbtc)
    ks = [k for k in rd["rets"] if k in rb["rets"]]; a = [rd["rets"][k] for k in ks]; b = [rb["rets"][k] for k in ks]
    n = len(ks); ma, mb = sum(a) / n, sum(b) / n
    print(f"    same-day correlation Delta vs Binance over {n} days: "
          f"{sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)):.3f}")

    print("\n=== R2b. Weekly rebalance, weekday-offset robustness (all 7 offsets, three universes) ===")
    for name, coins in (("BTC only", ["BTC"]), ("BTC+ETH", ["BTC", "ETH"]), ("9 coins", tb.COINS)):
        print(f"-- {name}")
        for off in range(7):
            r = run_offset(close, fund, coins, 7, off, START, END)
            s = t1.stats(list(r["rets"].values()))
            s22 = t1.stats([x for d, x in r["rets"].items() if d >= dt.date(2022, 1, 1)])
            s25 = t1.stats([x for d, x in r["rets"].items() if d >= dt.date(2025, 1, 1)])
            rdlt = run_offset(dclose, dfund, coins, 7, off, DS, END); sd = t1.stats(list(rdlt["rets"].values()))
            first = next(iter(r["rets"]))
            wd = (first + dt.timedelta(days=off - 1)).strftime("%a")  # weekday of the decision close for this offset
            print(f"  offset {off} (decision close on a {wd}): full Sharpe {s['sharpe']:.2f} CAGR {s['cagr']:+.1%} maxDD {s['mdd']:.1%} | "
                  f"2022-26 Sharpe {s22['sharpe']:.2f} | 2025-26 Sharpe {s25['sharpe']:.2f} CAGR {s25['cagr']:+.1%} | "
                  f"Delta 2024-08.. Sharpe {sd['sharpe']:.2f} CAGR {sd['cagr']:+.1%} maxDD {sd['mdd']:.1%} | trades/yr {r['trades']:.0f} fees/yr {r['fees']:.1%}")

    print("\n=== R2c. Hourly mark-to-market, BTC only: weekly (offset 0) and daily; own-account effect of a day stop ===")
    hourly = th.load_hourly(f"{SP}/hourly")
    series = {}
    for name, rb_days in (("btc_weekly", 7), ("btc_daily", 1)):
        rows = hourly_mtm(close, fund, hourly, ["BTC"], rb_days, 0, START, END, f"{OUT}/hourly_{name}.csv")
        series[name] = rows
        for stop in (0.0, 0.015, 0.02, 0.03):
            s, n = daystop_stats(rows, stop)
            print(fmt(f"{name} day stop {stop or 'none'}", s, f"stop days {n}"))
        # sub-period file for prop_sim (2025-01-01..)
        with open(f"{OUT}/hourly_{name}_2025on.csv", "w", newline="") as f:
            wr = csv.writer(f); wr.writerow(["ts_utc", "ret", "gross"])
            for t, r, g in rows:
                if t >= dt.datetime(2025, 1, 1):
                    wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}"])
    # daily tail of the weekly BTC series at native vol
    s, _ = daystop_stats(series["btc_weekly"], 0.0)
    by_day = collections.OrderedDict()
    for t, r, g in series["btc_weekly"]:
        by_day.setdefault(t.date(), []).append(r)
    drets = {d: math.prod(1 + x for x in v) - 1 for d, v in by_day.items()}
    lows = {d: min(math.prod(1 + x for x in v[:k + 1]) for k in range(len(v))) - 1 for d, v in by_day.items()}
    worst = sorted(drets.items(), key=lambda kv: kv[1])[:6]
    print("  btc_weekly native-vol daily tail: worst closes " + ", ".join(f"{d} {x:+.1%}" for d, x in worst))
    for thr in (0.02, 0.03, 0.04, 0.05):
        print(f"    close < -{thr:.0%}: {sum(1 for x in drets.values() if x < -thr)} days; intraday low < -{thr:.0%}: {sum(1 for x in lows.values() if x < -thr)} days")

    print("\n=== R2d. prop_sim.py on the BTC-only weekly series ===")
    sim = f"{SP}/tools/prop_sim.py"
    runs = [
        ("Breakout Classic 10/3/6 static, day stop 1.5%, bootstrap full", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.3,0.4,0.5,0.6,0.75 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, day stop 1.5%, HISTORICAL windows", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.3,0.4,0.5,0.6 --historical --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, day stop 1.5%, bootstrap 2025-01..2026-10 only", f"{OUT}/hourly_btc_weekly_2025on.csv",
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 --lev 0.3,0.4,0.5,0.6 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("Breakout Classic, NO day stop, bootstrap full", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --lev 0.3,0.4,0.5 --paths 3000 --fee 999 --account 100000 --split 0.8"),
        ("HyroTrader 1-step 10/4/6 trailing, day stop 2%, bootstrap full", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type trailing --day-stop 0.02 --lev 0.3,0.4,0.5 --paths 3000 --fee 749 --account 100000 --split 0.7"),
        ("HyroTrader if max DD is STATIC (unconfirmed), day stop 2%, bootstrap full", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type static --day-stop 0.02 --lev 0.3,0.4,0.5 --paths 3000 --fee 749 --account 100000 --split 0.7"),
        ("CFT 1-step 10/4/6 trailing (locks at +6%), day stop 2%, bootstrap full", f"{OUT}/hourly_btc_weekly.csv",
         "--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type trailing --trail-locks --day-stop 0.02 --lev 0.3,0.4,0.5 --paths 3000 --fee 599 --account 100000 --split 0.8"),
    ]
    for label, path, args in runs:
        print(f"\n--- {label}")
        out = subprocess.run([sys.executable, sim, "--returns", path] + args.split(), capture_output=True, text=True)
        print(out.stdout.strip()); print(out.stderr.strip()[-500:] if out.returncode else "", end="")


if __name__ == "__main__":
    main()
