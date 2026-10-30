#!/usr/bin/env python3
"""Exploratory (not pre-registered): the leg that reproduced the live run (1000 ms, touch, Scalper Offer 15 min fifo)
over the whole 27-30 Oct window, for cap shapes and half-spreads. Informs the next pre-registration only.
  python3 explore_sweep.py DATA_DIR REPO_SCRIPTS_DIR"""
import glob, os, sys
D, SCRIPTS = sys.argv[1], sys.argv[2]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402
T0, T1 = sim.utc_ms("2026-10-26T18:30:00Z"), sim.utc_ms("2026-10-30T02:03:00Z")
samples = [s for s in sim.load_metrics([os.path.join(D, "ada_metrics.log.gz")])["ADAUSDT"] if T0 <= s.ts <= T1]
tape = [t for t in sim.load_trades(sorted(glob.glob(os.path.join(D, "delta_mainnet_public_*.jsonl"))))["ADAUSD"] if T0 <= t.ts <= T1]
mids = sim.MidSeries(samples); ref = samples[len(samples) // 2].fair
W = {"W1": (sim.utc_ms("2026-10-29T19:30:00Z"), sim.utc_ms("2026-10-29T21:30:00Z")),
     "W2": (sim.utc_ms("2026-10-29T23:30:00Z"), sim.utc_ms("2026-10-30T01:30:00Z"))}
def wpnl(res, w0, w1):
    inv = cash = fees = 0.0; inv0 = None
    for f in res.fills:
        if f.ts >= w0 and inv0 is None: inv0 = inv
        if f.ts > w1: break
        if f.ts >= w0: cash -= f.side * f.qty * f.price; fees += f.fee_offer
        inv += f.side * f.qty
    inv0 = inv if inv0 is None else inv0
    return cash - fees + inv * mids.at(w1) - inv0 * mids.at(w0)
print(f"{'quote/cap':10s} {'half':>6s} {'fills':>6s} {'notional':>9s} {'capt':>5s} {'mo60':>6s} {'ofee':>5s} {'onet60':>6s} {'oPnL$':>7s} {'oPnLbp':>6s} {'W1$':>6s} {'W2$':>6s}")
for quote, orders in ((200, 3), (200, 2), (200, 1), (100, 2)):
    for half in (None, 5, 6, 7, 8):
        cfg = sim.SimConfig(latency_ms=1000, half_spread_bps=half, rule="touch", quote_usd=quote * ref, max_inv_orders=orders,
                            fee_bps=2.12, requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400, scalper_window_min=15)
        res = sim.simulate(samples, tape, 0.00001, 1.0, cfg); s = sim.summarize(res, mids, 1.0)
        n = sum(f.notional for f in res.fills) or 1
        print(f"{quote:4d}/{quote * orders:<5d} {('bot' if half is None else f'+/-{half}'):>6s} {s['fills']:6d} {n:9,.0f} {s['capture']:5.2f} "
              f"{s['mo'][60]:6.2f} {s['fee_offer']:5.2f} {s['net60_offer']:6.2f} {s['pnl_total_offer']:7.2f} {s['pnl_total_offer'] / n * 1e4:6.2f} "
              f"{wpnl(res, *W['W1']):6.2f} {wpnl(res, *W['W2']):6.2f}", flush=True)
