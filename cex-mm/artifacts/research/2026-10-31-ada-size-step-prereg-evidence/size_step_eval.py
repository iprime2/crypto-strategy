#!/usr/bin/env python3
"""Pre-registered replay for the ADA size step (2026-10-31-ada-size-step-prereg.md): quote 300, cap 600 (2 orders),
fair +/-6 bps, on shadow data received from 2026-10-31T12:00:00Z (shadow run 20261031T115906Z and any later run).

  python3 -I size_step_eval.py DATA_DIR REPO_SCRIPTS_DIR END_ISO
DATA_DIR holds ada_metrics_<run>.log.gz and <run>_delta_mainnet_public_*.jsonl for each shadow run in the window,
extracted as for the forward test. Where two runs overlap, the earlier run's rows stop at the later run's first row.
Gate 3 (all must hold): >= 72 h of data; >= 300 fills on the calibrated leg; calibrated leg (1000 ms, touch, Scalper
Offer 15 min fifo) PnL per $ >= +2.4 bp; 1000 ms strict at the list fee 2.12 PnL per $ >= 0; the calibrated leg's
deepest drawdown (equity marked at each fill) no worse than -$15. Also printed: the stress hours for gate 2
(realized vol of 1-min L1-mid log returns, >= 50 minutes in the hour, at or above 4 x 61 bps), and 200/400 for reference.
Uses shadow_fill_sim.py md5 a93c1658c2a81e0fabb84afedf589f94 (main at ca140f6).
"""
import datetime as dt, glob, math, os, re, statistics, sys

D, SCRIPTS, END = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402

START = "2026-10-31T12:00:00Z"
T0, T1 = sim.utc_ms(START), sim.utc_ms(END)
MEDIAN_VOL, STRESS_X = 61.0, 4.0
QUOTE, ORDERS, HALF = 300, 2, 6
HURDLE, MIN_FILLS, MIN_HOURS, MAX_DD = 2.4, 300, 72.0, -15.0

runs = sorted(re.match(r"ada_metrics_(.+)\.log\.gz", os.path.basename(p)).group(1)
              for p in glob.glob(os.path.join(D, "ada_metrics_*.log.gz")))
per_s = [sim.load_metrics([os.path.join(D, f"ada_metrics_{r}.log.gz")])["ADAUSDT"] for r in runs]
per_t = [sim.load_trades(sorted(glob.glob(os.path.join(D, f"{r}_delta_mainnet_public_*.jsonl"))))["ADAUSD"] for r in runs]
samples, tape = [], []
for i, r in enumerate(runs):
    s_cut = per_s[i + 1][0].ts if i + 1 < len(runs) and per_s[i + 1] else float("inf")
    t_cut = per_t[i + 1][0].ts if i + 1 < len(runs) and per_t[i + 1] else float("inf")
    s = [x for x in per_s[i] if T0 <= x.ts <= T1 and x.ts < s_cut]
    t = [x for x in per_t[i] if T0 <= x.ts <= T1 and x.ts < t_cut]
    print(f"{r}: {len(s)} samples, {len(t)} ADAUSD trades")
    samples += s; tape += t
samples.sort(key=lambda x: x.ts); tape.sort(key=lambda x: x.ts)
span_h = (samples[-1].ts - samples[0].ts) / 3.6e6
mids = sim.MidSeries(samples)
ref = samples[len(samples) // 2].fair
print(f"window {START} .. {END}: {span_h:.2f} h, {len(samples)} samples, {len(tape)} trades, ref fair {ref:.5f}")

m = {}
for s in samples:
    m[int(s.ts // 60000)] = (s.book_bid + s.book_ask) / 2
keys = sorted(m); hours = {}
for a, b in zip(keys, keys[1:]):
    if b == a + 1 and m[a] > 0 and m[b] > 0:
        hours.setdefault(b // 60, []).append(math.log(m[b] / m[a]))
vol = {h: statistics.pstdev(v) * math.sqrt(60) * 1e4 for h, v in hours.items() if len(v) >= 50}
stress = {h: v for h, v in vol.items() if v >= STRESS_X * MEDIAN_VOL}
print(f"hourly vol: {len(vol)} hours, median {statistics.median(vol.values()):.0f} bps, max {max(vol.values()):.0f} bps; "
      f"stress hours (>= {STRESS_X * MEDIAN_VOL:.0f} bps): "
      + (", ".join(f"{dt.datetime.utcfromtimestamp(h * 3600):%d %b %H}:00Z {v:.0f}" for h, v in sorted(stress.items())) or "none"))


def run(quote, lat, rule, offer):
    cfg = sim.SimConfig(latency_ms=lat, half_spread_bps=HALF, rule=rule, quote_usd=quote * ref, max_inv_orders=ORDERS,
                        fee_bps=2.12, requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400, scalper_window_min=offer)
    assert max(1.0, round(cfg.quote_usd / ref)) == quote
    res = sim.simulate(samples, tape, 0.00001, 1.0, cfg); s = sim.summarize(res, mids, 1.0)
    n = sum(f.notional for f in res.fills) or 1.0
    pnl = s["pnl_total_offer"] if offer else s["pnl_total"]
    inv = cash = peak = dd = 0.0
    for f in res.fills:
        cash -= f.side * f.qty * f.price + (f.fee_offer if offer else f.fee); inv += f.side * f.qty
        eq = cash + inv * mids.at(f.ts); peak = max(peak, eq); dd = min(dd, eq - peak)
    return dict(fills=s["fills"], notional=n, pnl=pnl, bp=pnl / n * 1e4, dd=dd)


print(f"{'leg':40s} {'fills':>6s} {'notional':>9s} {'PnL$':>7s} {'bp/$':>6s} {'worst dd$':>9s}")
out = {}
for quote in (QUOTE, 200):
    for name, lat, rule, offer in (("1000 touch offer15 (calibrated)", 1000, "touch", 15), ("1000 strict list fee", 1000, "strict", 0)):
        r = out[(quote, name)] = run(quote, lat, rule, offer)
        print(f"{quote}/{quote * ORDERS} {name:32s} {r['fills']:6d} {r['notional']:9,.0f} {r['pnl']:7.2f} {r['bp']:6.2f} {r['dd']:9.2f}", flush=True)
cal, strict = out[(QUOTE, "1000 touch offer15 (calibrated)")], out[(QUOTE, "1000 strict list fee")]
gates = [(f">= {MIN_HOURS:.0f} h of data", span_h >= MIN_HOURS, f"{span_h:.1f} h"),
         (f">= {MIN_FILLS} calibrated fills", cal["fills"] >= MIN_FILLS, f"{cal['fills']}"),
         (f"calibrated >= +{HURDLE} bp/$", cal["bp"] >= HURDLE, f"{cal['bp']:+.2f}"),
         ("1000 ms strict >= 0", strict["bp"] >= 0, f"{strict['bp']:+.2f}"),
         (f"calibrated worst drawdown >= {MAX_DD:.0f} $", cal["dd"] >= MAX_DD, f"{cal['dd']:.2f}")]
for k, ok, v in gates:
    print(f"gate 3: {k}: {'PASS' if ok else 'FAIL'} ({v})")
print("GATE 3:", "PASS" if all(g[1] for g in gates) else "FAIL", f"| stress hours for gate 2: {len(stress)}")
