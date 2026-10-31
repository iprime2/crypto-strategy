#!/usr/bin/env python3
"""Pre-registered shadow trial of SOPH, PARTI, RSR and OP (2026-10-31-coin-trial-prereg.md).

  python3 -I coin_trial_eval.py DATA_DIR REPO_SCRIPTS_DIR END_ISO
DATA_DIR holds metrics_<run>.log.gz (the coins' MM_METRICS lines) and <run>_delta_mainnet_public_*.jsonl for shadow run
20261031T172449Z and any later shadow run. The window from START to END is cut in half by time. First half: pick each
coin's half-spread from HALVES by calibrated-leg PnL per $ (at least MIN_SEL fills). Second half, that half-spread only:
PASS needs >= MIN_TEST fills on the calibrated leg, calibrated >= +2.4 bp/$, 1000 ms strict >= 0 and 300 ms strict >= 0
(list fee 2.12), and a calibrated worst dip (equity marked at each fill) no worse than MAX_DD. Quotes of QUOTE_USD,
cap 2 quotes. Calibrated leg: 1000 ms, touch, Scalper Offer 15 min fifo. Simulator: shadow_fill_sim.py md5 a93c1658.
"""
import datetime as dt, glob, os, re, sys

D, SCRIPTS, END = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402

START = "2026-10-31T17:30:00Z"
COINS = {"SOPHUSDT": ("SOPHUSD", 1e-06, 100.0), "PARTIUSDT": ("PARTIUSD", 1e-05, 100.0),
         "RSRUSDT": ("RSRUSD", 1e-06, 100.0), "OPUSDT": ("OPUSD", 0.0001, 0.1)}  # tick, contract value (Delta, 31 Oct)
HALVES = (6, 8, 10, 12, 15)
QUOTE_USD, ORDERS = 40.0, 2
MIN_SEL, MIN_TEST, HURDLE, MAX_DD = 100, 150, 2.4, -5.0
T0, T1 = sim.utc_ms(START), sim.utc_ms(END)
TM = (T0 + T1) / 2

runs = sorted(re.match(r"metrics_(.+)\.log\.gz", os.path.basename(p)).group(1) for p in glob.glob(os.path.join(D, "metrics_*.log.gz")))
per_s = [sim.load_metrics([os.path.join(D, f"metrics_{r}.log.gz")]) for r in runs]
per_t = [sim.load_trades(sorted(glob.glob(os.path.join(D, f"{r}_delta_mainnet_public_*.jsonl")))) for r in runs]


def joined(sym, dsym, a, b):
    s_all, t_all = [], []
    for i in range(len(runs)):
        s_cut = min((x.ts for x in per_s[i + 1].get(sym, [])[:1]), default=float("inf")) if i + 1 < len(runs) else float("inf")
        t_cut = min((x.ts for x in per_t[i + 1].get(dsym, [])[:1]), default=float("inf")) if i + 1 < len(runs) else float("inf")
        s_all += [x for x in per_s[i].get(sym, []) if a <= x.ts < b and x.ts < s_cut]
        t_all += [x for x in per_t[i].get(dsym, []) if a <= x.ts < b and x.ts < t_cut]
    return sorted(s_all, key=lambda x: x.ts), sorted(t_all, key=lambda x: x.ts)


def leg(samples, tape, tick, cv, half, lat, rule, offer):
    mids = sim.MidSeries(samples)
    ref = samples[len(samples) // 2].fair
    cfg = sim.SimConfig(latency_ms=lat, half_spread_bps=half, rule=rule, quote_usd=QUOTE_USD, max_inv_orders=ORDERS, fee_bps=2.12,
                        requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400, scalper_window_min=offer)
    res = sim.simulate(samples, tape, tick, cv, cfg); s = sim.summarize(res, mids, cv)
    n = sum(f.notional for f in res.fills) or 1.0
    pnl = s["pnl_total_offer"] if offer else s["pnl_total"]
    inv = cash = peak = dd = 0.0
    for f in res.fills:
        cash -= f.side * f.qty * cv * f.price + (f.fee_offer if offer else f.fee); inv += f.side * f.qty * cv
        eq = cash + inv * mids.at(f.ts); peak = max(peak, eq); dd = min(dd, eq - peak)
    return dict(fills=s["fills"], notional=n, pnl=pnl, bp=pnl / n * 1e4, dd=dd, qty=max(1.0, round(QUOTE_USD / (ref * cv))))


print(f"runs {runs}; window {START} .. {END}; selection half to {dt.datetime.fromtimestamp(TM / 1000, dt.timezone.utc):%Y-%m-%dT%H:%MZ}")
for sym, (dsym, tick, cv) in COINS.items():
    s1, t1 = joined(sym, dsym, T0, TM)
    s2, t2 = joined(sym, dsym, TM, T1 + 1)
    print(f"\n=== {sym}: selection {len(s1)} samples / {len(t1)} trades, test {len(s2)} samples / {len(t2)} trades")
    if len(s1) < 100 or len(s2) < 100:
        print(f"{sym}: NEED MORE DATA (too few quote samples)"); continue
    best = None
    for h in HALVES:
        r = leg(s1, t1, tick, cv, h, 1000, "touch", 15)
        print(f"  select +/-{h:>2} bps: {r['fills']:5d} fills {r['notional']:9,.0f} $ {r['pnl']:7.2f} PnL {r['bp']:6.2f} bp/$ dd {r['dd']:6.2f} (qty {r['qty']:.0f})")
        if r["fills"] >= MIN_SEL and (best is None or r["bp"] > best[1]["bp"]):
            best = (h, r)
    if best is None:
        print(f"{sym}: NEED MORE DATA (no half-spread with {MIN_SEL} fills in the selection half)"); continue
    h = best[0]
    cal = leg(s2, t2, tick, cv, h, 1000, "touch", 15)
    st1 = leg(s2, t2, tick, cv, h, 1000, "strict", 0)
    st3 = leg(s2, t2, tick, cv, h, 300, "strict", 0)
    for name, r in (("calibrated", cal), ("1000 strict", st1), ("300 strict", st3)):
        print(f"  test +/-{h} {name:12s}: {r['fills']:5d} fills {r['notional']:9,.0f} $ {r['pnl']:7.2f} PnL {r['bp']:6.2f} bp/$ dd {r['dd']:6.2f}")
    if cal["fills"] < MIN_TEST:
        print(f"{sym}: NEED MORE DATA ({cal['fills']} test fills, {MIN_TEST} needed)"); continue
    gates = [cal["bp"] >= HURDLE, st1["bp"] >= 0, st3["bp"] >= 0, cal["dd"] >= MAX_DD]
    print(f"{sym}: {'PASS' if all(gates) else 'FAIL'} at +/-{h} bps (calibrated {cal['bp']:+.2f}, 1000 strict {st1['bp']:+.2f}, "
          f"300 strict {st3['bp']:+.2f}, worst dip {cal['dd']:.2f})")
