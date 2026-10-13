#!/usr/bin/env python3
"""Hourly mark-to-market of the daily trend rule in cex-mm/scripts/trend_backtest.py (Binance USDT-M perp data).

Weights are decided at the 00:00 UTC daily close exactly as in trend_backtest.target_weights and held for the
next 24 hourly bars. Costs (taker + slippage) are charged in the first hour; funding (daily fraction from the
Binance archive) is charged in thirds at 00:00, 08:00 and 16:00. Writes an hourly return series for prop_sim.py.

  python3 trend_hourly.py --cache <trend-cache> --hourly <dir of SYM-1h.csv> --out hourly_returns.csv [--target-vol 0.40]
      [--long-short] [--looks 20,60,120] [--start 2020-05-01] [--end 2026-09-30] [--vol-filter PCT] [--btc-filter]
"""
from __future__ import annotations
import argparse, csv, datetime as dt, math, os, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "home", "user"))  # no-op guard
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402

def load_hourly(d: str) -> dict[str, dict[dt.datetime, float]]:
    out = {}
    for c in tb.COINS:
        p = os.path.join(d, f"{c}USDT-1h.csv")
        if not os.path.exists(p):
            continue
        m = {}
        for r in csv.DictReader(open(p)):
            ts = int(r["open_time_ms"]); ts = ts / 1000 if ts < 1e14 else ts / 1e6
            m[dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(tzinfo=None)] = float(r["close"])
        out[c] = m
    return out

def realized_vol(close: dict, d: dt.date, win: int) -> float | None:
    hist = [close.get(d - dt.timedelta(k)) for k in range(win + 1)]
    if any(h is None for h in hist):
        return None
    r = [math.log(hist[k] / hist[k + 1]) for k in range(win)]
    return math.sqrt(sum(x * x for x in r) / win * 365)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True); ap.add_argument("--hourly", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--target-vol", type=float, default=tb.TARGET_VOL)
    ap.add_argument("--looks", default="20,60,120"); ap.add_argument("--long-short", action="store_true")
    ap.add_argument("--start", default="2020-05-01"); ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--vol-filter", type=float, default=None, help="scale exposure to 0 when BTC 30d realized vol is above this annualized level (e.g. 0.90)")
    ap.add_argument("--btc-filter", action="store_true", help="long-only variant: no longs when BTC is below its 200-day mean")
    a = ap.parse_args()
    looks = tuple(int(x) for x in a.looks.split(","))
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    close, fund = tb.load_binance(a.cache, end)
    hourly = load_hourly(a.hourly)
    days = sorted(set().union(*[set(v) for v in close.values()]))
    cost = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
    eq, units = 1.0, {}
    rows, drets, dcur, fees, fpaid = [], [], 1.0, 0.0, 0.0
    skipped = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        w = tb.target_weights(close, d, looks, tb.VOL_WIN, a.target_vol, not a.long_short)
        scale = 1.0
        if a.vol_filter is not None:
            v = realized_vol(close["BTC"], d, 30)
            if v is not None and v > a.vol_filter:
                scale = 0.0
        if a.btc_filter:
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
        ok = True
        for h in range(24):
            t = dt.datetime(nxt.year, nxt.month, nxt.day, h)
            pnl = 0.0
            for c, u in new.items():
                px = hourly[c].get(t)
                if px is None:
                    px = prev[c]
                pnl += u * (px - prev[c]); prev[c] = px
            charge = traded * cost if h == 0 else 0.0
            fp = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items()) / 3 if h in (0, 8, 16) else 0.0
            r = (pnl - fp - charge) / eq
            fees += charge / eq; fpaid += fp / eq
            eq *= 1 + r
            rows.append((t, r, sum(abs(u) * prev[c] for c, u in new.items()) / eq))
        # re-anchor to the daily close so hourly drift never diverges from the daily series
        drets.append(eq / day_eq0 - 1)
        units = new
    with open(a.out, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["ts_utc", "ret", "gross"])
        for t, r, g in rows:
            wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}"])
    n = len(drets); mu = sum(drets) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in drets) / (n - 1))
    tot = math.prod(1 + x for x in drets); yrs = n / 365
    peak, mdd, e = 1.0, 0.0, 1.0
    for x in drets:
        e *= 1 + x; peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    hr = [r for _, r, _ in rows]; hpeak, hmdd, he = 1.0, 0.0, 1.0
    for x in hr:
        he *= 1 + x; hpeak = max(hpeak, he); hmdd = min(hmdd, he / hpeak - 1)
    print(f"{a.start}..{a.end} looks={looks} tv={a.target_vol} {'L/S' if a.long_short else 'long-only'} volfilter={a.vol_filter} btcfilter={a.btc_filter}")
    print(f"  days {n}  CAGR {tot ** (1 / yrs) - 1:+.1%}  vol {sd * math.sqrt(365):.0%}  Sharpe {mu / sd * math.sqrt(365):.2f}  "
          f"maxDD(daily) {mdd:.1%}  maxDD(hourly) {hmdd:.1%}  fees/yr {fees / yrs:.1%}  funding/yr {fpaid / yrs:+.1%}  hours {len(rows)}")
    yearly = collections.defaultdict(lambda: 1.0)
    for (t, r, _) in rows:
        yearly[t.year] *= 1 + r
    print("  by year: " + "  ".join(f"{y}:{v - 1:+.0%}" for y, v in sorted(yearly.items())))

if __name__ == "__main__":
    main()
