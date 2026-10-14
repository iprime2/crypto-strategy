#!/usr/bin/env python3
"""Adversarial (fix of av_lows): per day and k, walk hours; while not stopped, the intra-hour LOW path (all coins at their hourly low)
can breach the 3% Breakout daily limit before the 1.5% stop (checked at hourly closes) trips. Also the stop's realised fill level."""
import sys, csv, datetime as dt
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
close, fund = tb.load_binance(f"{SP}/trend-cache", dt.date(2026, 9, 30))
H = {}
for c in tb.COINS:
    m = {}
    for r in csv.DictReader(open(f"{SP}/hourly/{c}USDT-1h.csv")):
        t = dt.datetime.fromtimestamp(int(r["open_time_ms"]) / 1000, dt.timezone.utc).replace(tzinfo=None)
        m[t] = (float(r["close"]), float(r["low"]))
    H[c] = m
days = sorted(set().union(*[set(v) for v in close.values()]))
start, end = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
eq = 1.0; daypaths = []
for d, nxt in zip(days, days[1:]):
    if not (start <= nxt <= end): continue
    w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, tb.TARGET_VOL, True)
    new = {c: x * eq / close[c][d] for c, x in w.items() if x and nxt in close[c]}
    prev = {c: close[c][d] for c in new}; e = eq; pc_list = []; pl_list = []
    for h in range(24):
        t = dt.datetime(nxt.year, nxt.month, nxt.day, h)
        pc = sum(u * (H[c].get(t, (prev[c], prev[c]))[0] - prev[c]) for c, u in new.items()) / eq
        pl = sum(u * (H[c].get(t, (prev[c], prev[c]))[1] - prev[c]) for c, u in new.items()) / eq
        pc_list.append(pc); pl_list.append(pl)
        for c in new: prev[c] = H[c].get(t, (prev[c], prev[c]))[0]
    daypaths.append((nxt, pc_list, pl_list))
    eq *= 1 + sum(pc_list)
print(f"{len(daypaths)} days, native TV 0.40 daily rule; Breakout 3% daily limit, 1.5% stop checked at hourly closes, intra-hour LOW path = every coin at its hourly low")
for k in (0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.75):
    breach_low = []; breach_close = []; trips = 0; fills = []
    for nxt, pcs, pls in daypaths:
        cum = 0.0; stopped = False
        for h in range(24):
            if stopped: break
            low = cum + pls[h] * k
            if low < -0.03: breach_low.append((nxt, h, low)); break
            cum += pcs[h] * k
            if cum < -0.03: breach_close.append((nxt, h, cum)); break
            if cum < -0.015: stopped = True; trips += 1; fills.append(cum)
    print(f"  k={k:4.2f}: 3% breach days at hourly-CLOSE resolution {len(breach_close):2d} | with intra-hour LOWS {len(breach_low):2d} | stop trips {trips:3d} ({trips/6.42:.1f}/yr), mean fill {sum(fills)/len(fills) if fills else 0:+.2%}, worst fill {min(fills) if fills else 0:+.2%}")
    if breach_low: print("      low-path breach days: " + ", ".join(f"{d} h{h} {v:+.2%}" for d, h, v in breach_low[:10]))
