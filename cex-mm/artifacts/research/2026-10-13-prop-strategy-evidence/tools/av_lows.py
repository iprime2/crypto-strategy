#!/usr/bin/env python3
"""Adversarial: intra-hour granularity. Daily rule (native TV 0.40) marked with hourly CLOSES vs with hourly LOWS (every coin at its
hourly low simultaneously: an upper bound on the intra-hour equity low). Counts days where the intra-day equity low vs 00:00 breaches
-3%/-6% (native) = -1.5%/-3% at k=0.5 (Breakout daily limit), and days where the hourly-close path never trips the 1.5% stop
(k=0.5 => -3% native at hourly checks) but the low path breaches the 3% limit (-6% native)."""
import sys, csv, datetime as dt, math, collections
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
close, fund = tb.load_binance(f"{SP}/trend-cache", dt.date(2026, 9, 30))
H = {}
for c in tb.COINS:
    m = {}
    for r in csv.DictReader(open(f"{SP}/hourly/{c}USDT-1h.csv")):
        t = dt.datetime.fromtimestamp(int(r["open_time_ms"]) / 1000, dt.timezone.utc).replace(tzinfo=None)
        m[t] = (float(r["close"]), float(r["low"]), float(r["high"]))
    H[c] = m
days = sorted(set().union(*[set(v) for v in close.values()]))
start, end = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
eq, units = 1.0, {}
res = []  # (day, min close-path, min low-path, worst single hour close, gross)
for d, nxt in zip(days, days[1:]):
    if not (start <= nxt <= end): continue
    w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, tb.TARGET_VOL, True)
    new = {c: x * eq / close[c][d] for c, x in w.items() if x and nxt in close[c]}
    prev = {c: close[c][d] for c in new}; gross = sum(abs(u) * prev[c] for c, u in new.items()) / eq
    e = eq; mc = 0.0; ml = 0.0; worst_h = 0.0; path_c = []
    for h in range(24):
        t = dt.datetime(nxt.year, nxt.month, nxt.day, h)
        pc = sum(u * (H[c].get(t, (prev[c],) * 3)[0] - prev[c]) for c, u in new.items())
        pl = sum(u * (H[c].get(t, (prev[c],) * 3)[1] - prev[c]) for c, u in new.items())  # low of this hour vs previous close
        cum_before = e / eq - 1
        low_cum = cum_before + pl / eq
        ml = min(ml, low_cum)
        e += pc; worst_h = min(worst_h, pc / eq)
        for c in new: prev[c] = H[c].get(t, (prev[c],) * 3)[0]
        mc = min(mc, e / eq - 1); path_c.append(e / eq - 1)
    # did the hourly-close path trip a native -3% stop (k=0.5 x 1.5%) before the low path hit -6% (k=0.5 x 3%)?
    trip_h = next((i for i, v in enumerate(path_c) if v < -0.03), None)
    res.append((nxt, mc, ml, worst_h, gross, trip_h, path_c))
    eq = e
    units = new
n = len(res)
def cnt(f): return sum(1 for r in res if f(r))
print(f"days {n}; native TV 0.40 daily rule; thresholds at native = 2x the k=0.5 thresholds")
for thr in (0.03, 0.04, 0.05, 0.06, 0.08):
    print(f"  intraday min vs 00:00 < -{thr:.0%}: hourly-close path {cnt(lambda r: r[1] < -thr):3d} days | hourly-LOW path (all coins at low) {cnt(lambda r: r[2] < -thr):3d} days")
# Breakout at k=0.5: daily limit 3% => native 6%; day stop 1.5% => native 3% checked at hourly closes
breach_low_no_trip = [r for r in res if r[2] < -0.06 and r[5] is None]
breach_low_trip_late = []
for r in res:
    if r[5] is not None:
        # low path before the trip hour inclusive
        pass
print(f"  k=0.5 Breakout: days where the LOW path breaches -3% (native -6%) while the hourly-close path never tripped the 1.5% stop: {len(breach_low_no_trip)}")
for r in breach_low_no_trip: print("     ", r[0], f"close-min {r[1]:+.2%} low-min {r[2]:+.2%} gross {r[4]:.2f}x")
# single hours worse than -3% native (=-1.5% at k=0.5: a stop that trips late)
bad = sorted(res, key=lambda r: r[3])[:12]
print("  worst single hourly-close moves (native): " + ", ".join(f"{r[0]} {r[3]:+.2%}" for r in bad))
print(f"  hours worse than -2% native: {sum(1 for r in res for v in [r[3]] if v < -0.02)} days with such an hour; worse than -3%: {cnt(lambda r: r[3] < -0.03)}")
# low path at various k: days breaching 3% daily limit if stop at 1.5% trips only at hourly closes
for k in (0.4, 0.45, 0.5, 0.55, 0.6):
    br = 0; br_close = 0
    for r in res:
        pc = r[6]; trip = next((i for i, v in enumerate(pc) if v * k < -0.015), None)
        # low-path breach before or at the trip hour
        if trip is None:
            if r[2] * k < -0.03: br += 1
            if r[1] * k < -0.03: br_close += 1
    print(f"  k={k}: days where the 3% daily limit is breached before a 1.5% hourly-close stop trips: LOW path {br}, CLOSE path {br_close} (of {n})")
