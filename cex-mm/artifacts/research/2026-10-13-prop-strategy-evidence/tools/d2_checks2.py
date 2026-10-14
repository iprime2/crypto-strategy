#!/usr/bin/env python3
"""D2 checks, part 2 (read-only on the repo).
(a) Rebalance-hour robustness: run the fixed daily rule on closes taken at hour h UTC from the hourly Binance files.
    The funding archive is per calendar day, so funding is shifted by up to one day relative to the daily cache;
    at h=0 the result should match the daily backtest closely.
(b) Drawdown de-leveraging: size multiplier clip(1 - dd/dd_max, 0.25, 1) at target vol 0.25, several dd_max; all reported.
"""
import sys, csv, math, datetime as dt, collections, os
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402
sys.path.insert(0, os.path.dirname(__file__))
from d2_checks import stats, fmt, by_year, SP, CACHE, COST  # noqa: E402

end_b = dt.date(2026, 9, 30); start_b = dt.date(2020, 5, 1)
_, fund_b = tb.load_binance(CACHE, end_b)


def closes_at_hour(h: int):
    out = {}
    for c in tb.COINS:
        m = {}
        for r in csv.DictReader(open(f"{SP}/hourly/{c}USDT-1h.csv")):
            t = dt.datetime.fromtimestamp(int(r["open_time_ms"]) / 1000, dt.timezone.utc) + dt.timedelta(hours=1)  # bar close time
            if t.hour == h:
                m[t.date()] = float(r["close"])
        out[c] = m
    return out


def run_dd(close, fund, start, end, target_vol, dd_max=None, floor=0.25):
    days = sorted(set().union(*[set(v) for v in close.values()]))
    eq = peak = 1.0; units = {}; out = []
    mults = []
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, target_vol, True)
        m = 1.0
        if dd_max is not None:
            dd = 1 - eq / peak
            m = min(1.0, max(floor, 1 - dd / dd_max))
        mults.append(m)
        new = {c: x * m * eq / close[c][d] for c, x in w.items() if nxt in close[c] and x}
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * COST) / eq
        eq *= 1 + r; peak = max(peak, eq)
        out.append((nxt, r)); units = new
    return out, sum(mults) / len(mults)


print("=" * 100 + "\n(a) Rebalance hour (UTC) robustness, Binance 2020-05-01..2026-09-30, tv 0.40, long-only, fixed rule\n" + "=" * 100)
for h in (0, 4, 8, 12, 16, 20):
    close_h = closes_at_hour(h)
    out, _ = run_dd(close_h, fund_b, start_b, end_b, 0.40)
    s = stats([r for _, r in out])
    print(fmt(f"close/rebalance at {h:02d}:00 UTC ({(h + 5) % 24:02d}:{30 if True else 0} IST)", s))
    print("   by year: " + by_year(out))

print("\n" + "=" * 100 + "\n(b) Drawdown de-leveraging, Binance 2020-05-01..2026-09-30, tv 0.25, mult = clip(1 - dd/dd_max, 0.25, 1)\n" + "=" * 100)
close_b, _ = tb.load_binance(CACHE, end_b)
for dd_max in (None, 0.10, 0.15, 0.20, 0.30):
    out, avg_m = run_dd(close_b, fund_b, start_b, end_b, 0.25, dd_max)
    s = stats([r for _, r in out])
    print(fmt(f"dd_max {dd_max}", s, f"avg multiplier {avg_m:.2f}"))
    print("   by year: " + by_year(out))
