#!/usr/bin/env python3
"""Hourly mark-to-market of the daily trend rule in scripts/trend_backtest.py (Binance USDT-M perp data).

Weights are decided at the 00:00 UTC daily close exactly as in trend_backtest.target_weights and held for the
next 24 hourly bars. Costs (taker + slippage) are charged in the first hour; funding (daily fraction from the
Binance archive) is charged in thirds at 00:00, 08:00 and 16:00. Writes an hourly return series for prop_sim.py.
Exposure is scaled by --lev (1.0 = the native target vol); --vol-filter and --btc-filter are optional overlays.

  python3 scripts/trend_hourly.py --cache <trend-cache> --hourly <dir of SYMUSDT-1h.csv> --out hourly_returns.csv
      [--target-vol 0.40] [--lev 1.0] [--long-short] [--looks 20,60,120] [--start 2020-05-01] [--end 2026-09-30]
      [--vol-filter 0.90] [--btc-filter]
  python3 scripts/trend_hourly.py --selftest

Hourly files: data.binance.vision futures/um klines at 1h, columns open_time_ms,open,high,low,close,volume,close_time_ms.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trend_backtest as tb  # noqa: E402


def load_hourly(d: str) -> dict[str, dict[dt.datetime, float]]:
    out = {}
    for c in tb.COINS:
        p = os.path.join(d, f"{c}USDT-1h.csv")
        if not os.path.exists(p):
            continue
        m = {}
        for r in csv.DictReader(open(p)):
            ts = int(r["open_time_ms"])
            ts = ts / 1000 if ts < 1e14 else ts / 1e6
            m[dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(tzinfo=None)] = float(r["close"])
        out[c] = m
    return out


def realized_vol(close: dict, d: dt.date, win: int) -> float | None:
    hist = [close.get(d - dt.timedelta(k)) for k in range(win + 1)]
    if any(h is None for h in hist):
        return None
    r = [math.log(hist[k] / hist[k + 1]) for k in range(win)]
    return math.sqrt(sum(x * x for x in r) / win * 365)


def run(close, fund, hourly, start: dt.date, end: dt.date, *, looks=tb.LOOKS, target_vol=tb.TARGET_VOL, lev=1.0,
        long_only=True, vol_filter=None, btc_filter=False) -> dict:
    """Returns hourly rows (t, ret, gross), daily returns, and cost totals."""
    days = sorted(set().union(*[set(v) for v in close.values()]))
    cost = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
    eq, units = 1.0, {}
    rows, drets, fees, fpaid = [], [], 0.0, 0.0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        w = tb.target_weights(close, d, looks, tb.VOL_WIN, target_vol, long_only)
        scale = lev
        if vol_filter is not None:
            v = realized_vol(close["BTC"], d, 30)
            if v is not None and v > vol_filter:
                scale = 0.0
        if btc_filter:
            hist = [close["BTC"].get(d - dt.timedelta(k)) for k in range(200)]
            if all(h is not None for h in hist) and close["BTC"][d] < sum(hist) / 200:
                scale = 0.0
        new = {}
        for c, x in w.items():
            u = x * scale * eq / close[c][d]
            if u and nxt in close[c] and c in hourly:
                new[c] = u
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        day_eq0 = eq
        prev = {c: close[c][d] for c in new}
        for h in range(24):
            t = dt.datetime(nxt.year, nxt.month, nxt.day, h)
            pnl = 0.0
            for c, u in new.items():
                px = hourly[c].get(t, prev[c])
                pnl += u * (px - prev[c])
                prev[c] = px
            charge = traded * cost if h == 0 else 0.0
            fp = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items()) / 3 if h in (0, 8, 16) else 0.0
            r = (pnl - fp - charge) / eq
            fees += charge / eq
            fpaid += fp / eq
            eq *= 1 + r
            rows.append((t, r, sum(abs(u) * prev[c] for c, u in new.items()) / eq))
        drets.append(eq / day_eq0 - 1)
        units = new
    return dict(rows=rows, drets=drets, fees=fees, funding=fpaid)


def stats(res: dict) -> dict:
    drets, rows = res["drets"], res["rows"]
    n = len(drets)
    mu = sum(drets) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in drets) / (n - 1))
    tot = math.prod(1 + x for x in drets)
    yrs = n / 365
    peak, mdd, e = 1.0, 0.0, 1.0
    for x in drets:
        e *= 1 + x
        peak, mdd = max(peak, e), min(mdd, e / peak - 1)
    hpeak, hmdd, he = 1.0, 0.0, 1.0
    for _, x, _ in rows:
        he *= 1 + x
        hpeak, hmdd = max(hpeak, he), min(hmdd, he / hpeak - 1)
    yearly = collections.defaultdict(lambda: 1.0)
    for t, r, _ in rows:
        yearly[t.year] *= 1 + r
    return dict(days=n, cagr=tot ** (1 / yrs) - 1, vol=sd * math.sqrt(365), sharpe=mu / sd * math.sqrt(365) if sd else 0.0,
                mdd=mdd, hmdd=hmdd, fees_yr=res["fees"] / yrs, funding_yr=res["funding"] / yrs,
                yearly={y: v - 1 for y, v in sorted(yearly.items())})


def selftest() -> None:
    """On a synthetic series whose 23:00 hourly close equals the daily close, the hourly path must reproduce
    trend_backtest.backtest day by day (the only difference is intra-day compounding, which is tiny)."""
    d0 = dt.date(2024, 1, 1)
    days = [d0 + dt.timedelta(i) for i in range(260)]
    close = {"BTC": {}, "ETH": {}}
    hourly = {"BTC": {}, "ETH": {}}
    for i, d in enumerate(days):
        for c, drift, amp in (("BTC", 1.004, 0.03), ("ETH", 0.998, 0.05)):
            px = 100 * drift ** i * (1 + amp * math.sin(i / 3))
            close[c][d] = px
            prev = close[c].get(days[i - 1], px) if i else px
            for h in range(24):  # straight line from the previous close to this close, with a wiggle
                frac = (h + 1) / 24
                hourly[c][dt.datetime(d.year, d.month, d.day, h)] = prev + (px - prev) * frac + (0.2 * math.sin(h) if h < 23 else 0.0)
    fund = {"BTC": {d: 0.0001 for d in days}, "ETH": {d: -0.00005 for d in days}}
    start, end = days[125], days[-1]
    res = run(close, fund, hourly, start, end)
    ref = tb.backtest(close, fund, start, end)["rets"]
    assert len(res["drets"]) == len(ref), (len(res["drets"]), len(ref))
    worst = max(abs(a - b) for a, b in zip(res["drets"], ref))
    assert worst < 2e-4, worst
    tot_h = math.prod(1 + x for x in res["drets"])
    tot_d = math.prod(1 + x for x in ref)
    assert abs(tot_h / tot_d - 1) < 2e-3, (tot_h, tot_d)
    assert len(res["rows"]) == 24 * len(ref)
    half = run(close, fund, hourly, start, end, lev=0.5)
    assert abs(sum(half["drets"]) / sum(res["drets"]) - 0.5) < 0.05  # exposure scales linearly to first order
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/cex-mm/trend"))
    ap.add_argument("--hourly", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--target-vol", type=float, default=tb.TARGET_VOL)
    ap.add_argument("--lev", type=float, default=1.0, help="exposure multiplier on the native rule (0.5 = half)")
    ap.add_argument("--looks", default="20,60,120")
    ap.add_argument("--long-short", action="store_true")
    ap.add_argument("--start", default="2020-05-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--vol-filter", type=float, default=None, help="no exposure when BTC 30d realized vol is above this (e.g. 0.90)")
    ap.add_argument("--btc-filter", action="store_true", help="no exposure when BTC is below its 200-day mean")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not (a.hourly and a.out):
        ap.error("--hourly and --out are required (or --selftest)")
    looks = tuple(int(x) for x in a.looks.split(","))
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    close, fund = tb.load_binance(a.cache, end)
    hourly = load_hourly(a.hourly)
    res = run(close, fund, hourly, start, end, looks=looks, target_vol=a.target_vol, lev=a.lev,
              long_only=not a.long_short, vol_filter=a.vol_filter, btc_filter=a.btc_filter)
    with open(a.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["ts_utc", "ret", "gross"])
        for t, r, g in res["rows"]:
            wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}"])
    s = stats(res)
    print(f"{a.start}..{a.end} looks={looks} tv={a.target_vol} lev={a.lev} {'L/S' if a.long_short else 'long-only'} "
          f"volfilter={a.vol_filter} btcfilter={a.btc_filter}")
    print(f"  days {s['days']}  CAGR {s['cagr']:+.1%}  vol {s['vol']:.0%}  Sharpe {s['sharpe']:.2f}  maxDD(daily) {s['mdd']:.1%}  "
          f"maxDD(hourly) {s['hmdd']:.1%}  fees/yr {s['fees_yr']:.1%}  funding/yr {s['funding_yr']:+.1%}  hours {len(res['rows'])}")
    print("  by year: " + "  ".join(f"{y}:{v:+.0%}" for y, v in s["yearly"].items()))


if __name__ == "__main__":
    main()
