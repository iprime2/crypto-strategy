#!/usr/bin/env python3
"""Forward test of FORWARD_PREREG.md (md5 9605df5c): ADA quote 200, cap 400 (2 orders), fair +/-6 bps, on shadow data
received after 2026-10-30T02:03:00Z from the three shadow runs (20261025T174640Z, 20261030T064228Z, 20261030T105549Z).

  python3 -I forward_eval.py DATA_DIR REPO_SCRIPTS_DIR END_ISO
DATA_DIR holds ada_metrics_<run>.log.gz and <run>_delta_mainnet_public_*.jsonl. Where two runs overlap, the earlier run's
rows stop at the later run's first row. Gates: (1) 1000 ms touch, Scalper Offer 15 min fifo, PnL per $ >= +2.4 bp;
(2) 1000 ms strict at the list fee 2.12 >= 0; (3) >= 300 fills over >= 24 h; (4) an hour with realized vol (1-min
L1-mid log returns, >= 50 minutes) above 2 x 61 bps. PnL per $ = pnl_total (or pnl_total_offer) / fill notional.
"""
import datetime as dt, glob, math, os, statistics, sys

D, SCRIPTS, END = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402

RUNS = ["20261025T174640Z", "20261030T064228Z", "20261030T105549Z"]
T0, T1 = sim.utc_ms("2026-10-30T02:03:00Z"), sim.utc_ms(END)
MEDIAN_VOL, HURDLE = 61.0, 2.4

per_run_s = [sim.load_metrics([os.path.join(D, f"ada_metrics_{r}.log.gz")])["ADAUSDT"] for r in RUNS]
per_run_t = [sim.load_trades(sorted(glob.glob(os.path.join(D, f"{r}_delta_mainnet_public_*.jsonl"))))["ADAUSD"] for r in RUNS]
samples, tape = [], []
for i, r in enumerate(RUNS):
    s_cut = per_run_s[i + 1][0].ts if i + 1 < len(RUNS) and per_run_s[i + 1] else float("inf")
    t_cut = per_run_t[i + 1][0].ts if i + 1 < len(RUNS) and per_run_t[i + 1] else float("inf")
    s = [x for x in per_run_s[i] if T0 <= x.ts <= T1 and x.ts < s_cut]
    t = [x for x in per_run_t[i] if T0 <= x.ts <= T1 and x.ts < t_cut]
    print(f"{r}: {len(s)} samples, {len(t)} ADAUSD trades" + (
        f", {dt.datetime.utcfromtimestamp(s[0].ts / 1000):%m-%d %H:%M:%S}Z..{dt.datetime.utcfromtimestamp(s[-1].ts / 1000):%m-%d %H:%M:%S}Z" if s else ""))
    samples += s; tape += t
samples.sort(key=lambda x: x.ts); tape.sort(key=lambda x: x.ts)
span_h = (samples[-1].ts - samples[0].ts) / 3.6e6
tick, cv = 0.00001, 1.0
mids = sim.MidSeries(samples)
ref = samples[len(samples) // 2].fair
print(f"window {span_h:.2f} h, {len(samples)} samples, {len(tape)} trades, ref fair {ref:.5f}")

# Gate 4: hourly realized vol of the Delta L1 mid
m = {}
for s in samples:
    m[int(s.ts // 60000)] = (s.book_bid + s.book_ask) / 2
keys = sorted(m); hours = {}
for a, b in zip(keys, keys[1:]):
    if b == a + 1 and m[a] > 0 and m[b] > 0:
        hours.setdefault(b // 60, []).append(math.log(m[b] / m[a]))
vol = {h: statistics.pstdev(v) * math.sqrt(60) * 1e4 for h, v in hours.items() if len(v) >= 50}
hot = {h: v for h, v in vol.items() if v > 2 * MEDIAN_VOL}
print(f"hourly vol: {len(vol)} hours, median {statistics.median(vol.values()):.0f} bps, max {max(vol.values()):.0f} bps; "
      f"hours above {2 * MEDIAN_VOL:.0f}: " + (", ".join(f"{dt.datetime.utcfromtimestamp(h * 3600):%d %H}:00Z {v:.0f}" for h, v in sorted(hot.items())) or "none"))

LEGS = [("1000 touch offer15 (calibrated)", 1000, "touch", 15), ("1000 strict list fee", 1000, "strict", 0),
        ("300 strict list fee", 300, "strict", 0), ("300 touch offer15", 300, "touch", 15)]
out = {}
print(f"{'leg':32s} {'fills':>6s} {'notional':>9s} {'PnL$':>7s} {'spr$':>7s} {'inv$':>7s} {'fee$':>7s} {'bp/$':>6s} {'net60':>6s} {'fin':>5s}")
for name, lat, rule, offer in LEGS:
    cfg = sim.SimConfig(latency_ms=lat, half_spread_bps=6, rule=rule, quote_usd=200 * ref * cv, max_inv_orders=2, fee_bps=2.12,
                        requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400, scalper_window_min=offer)
    assert max(1.0, round(cfg.quote_usd / (ref * cv))) == 200
    res = sim.simulate(samples, tape, tick, cv, cfg); s = sim.summarize(res, mids, cv)
    n = sum(f.notional for f in res.fills) or 1.0
    pnl = s["pnl_total_offer"] if offer else s["pnl_total"]
    fee = (s["pnl_fees"] - (s["pnl_total"] - s["pnl_total_offer"])) if offer else s["pnl_fees"]
    out[name] = dict(fills=s["fills"], notional=n, pnl=pnl, bp=pnl / n * 1e4)
    print(f"{name:32s} {s['fills']:6d} {n:9,.0f} {pnl:7.2f} {s['pnl_spread']:7.2f} {s['pnl_inventory']:7.2f} {fee:7.2f} "
          f"{pnl / n * 1e4:6.2f} {s['net60']:6.2f} {s['final_inv']:5.0f}", flush=True)

cal, strict = out[LEGS[0][0]], out[LEGS[1][0]]
g = [("1 calibrated leg >= +2.4 bp/$", cal["bp"] >= HURDLE, f"{cal['bp']:+.2f}"),
     ("2 1000 ms strict >= 0", strict["bp"] >= 0, f"{strict['bp']:+.2f}"),
     ("3 >= 300 fills over >= 24 h", cal["fills"] >= 300 and span_h >= 24, f"{cal['fills']} fills, {span_h:.1f} h"),
     ("4 an hour above 2x median vol", bool(hot), f"{len(hot)} hours")]
for k, ok, v in g:
    print(f"gate {k}: {'PASS' if ok else 'FAIL'} ({v})")
if not g[3][1] and all(x[1] for x in g[:3]):
    print("VERDICT: EXTEND (no volatile hour yet; up to 72 h)")
else:
    print("VERDICT:", "PASS" if all(x[1] for x in g) else "FAIL")
