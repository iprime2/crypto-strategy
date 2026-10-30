#!/usr/bin/env python3
"""Test 2 of PREREG.md: shadow_fill_sim (classic engine, the shadow's logged ADA quotes) for each size/cap variant.

  python3 sim_variants.py DATA_DIR REPO_SCRIPTS_DIR   ->  prints the table, writes DATA_DIR/test2.json
Window: quotes and trades received 2026-10-26T18:30:00Z .. 2026-10-30T02:03:00Z. Legs: 300 ms strict, 1000 ms strict,
300 ms touch. PnLbp = pnl_total / fill notional * 1e4 (cash + final inventory at the last mid - fees).
"""
import datetime as dt, glob, json, os, sys

D, SCRIPTS = sys.argv[1], sys.argv[2]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402

T0, T1 = sim.utc_ms("2026-10-26T18:30:00Z"), sim.utc_ms("2026-10-30T02:03:00Z")
WINDOWS = {"W1": ("2026-10-29T19:30:00Z", "2026-10-29T21:30:00Z"),
           "W2": ("2026-10-29T23:30:00Z", "2026-10-30T01:30:00Z")}
VARIANTS = [("A", 200, 600), ("B", 200, 400), ("C", 200, 200), ("D", 150, 300), ("E", 100, 300), ("F", 100, 200)]
LEGS = [("300 strict", 300, "strict"), ("1000 strict", 1000, "strict"), ("300 touch", 300, "touch")]

samples = [s for s in sim.load_metrics([os.path.join(D, "ada_metrics.log.gz")])["ADAUSDT"] if T0 <= s.ts <= T1]
tape = [t for t in sim.load_trades(sorted(glob.glob(os.path.join(D, "delta_mainnet_public_*.jsonl"))))["ADAUSD"]
        if T0 <= t.ts <= T1]
tick, cv = 0.00001, 1.0  # ADAUSD (product_meta needs the network; values as on Delta)
mids = sim.MidSeries(samples)
ref_px = samples[len(samples) // 2].fair  # the simulator sizes quotes from this sample's fair
print(f"{len(samples)} samples, {len(tape)} ADAUSD trades, {(samples[-1].ts - samples[0].ts) / 3.6e6:.1f} h; "
      f"ref fair {ref_px:.5f}")


def window_pnl(res, w0, w1):
    inv, cash, fees, inv0 = 0.0, 0.0, 0.0, None
    for f in res.fills:
        if f.ts >= w0 and inv0 is None:
            inv0 = inv
        if f.ts > w1:
            break
        if f.ts >= w0:
            cash -= f.side * f.qty * cv * f.price; fees += f.fee
        inv += f.side * f.qty
    inv0 = inv if inv0 is None else inv0
    return cash - fees + inv * cv * mids.at(w1) - inv0 * cv * mids.at(w0)


out = {}
print(f"{'var':3s} {'leg':12s} {'fills':>6s} {'notional':>9s} {'net60':>6s} {'PnL$':>7s} {'spr$':>7s} {'inv$':>7s} "
      f"{'fee$':>7s} {'PnLbp':>6s} {'W1$':>6s} {'W2$':>6s} {'fin':>5s}  gate")
for vid, quote, cap in VARIANTS:
    orders = cap // quote
    assert orders * quote == cap
    for leg, lat, rule in LEGS:
        cfg = sim.SimConfig(latency_ms=lat, half_spread_bps=None, rule=rule, quote_usd=quote * ref_px * cv,
                            max_inv_orders=orders, fee_bps=2.12, requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400)
        assert max(1.0, round(cfg.quote_usd / (ref_px * cv))) == quote
        res = sim.simulate(samples, tape, tick, cv, cfg)
        s = sim.summarize(res, mids, cv)
        notl = sum(f.notional for f in res.fills)
        bp = s["pnl_total"] / notl * 1e4 if notl else 0.0
        ws = {k: window_pnl(res, sim.utc_ms(a), sim.utc_ms(b)) for k, (a, b) in WINDOWS.items()}
        ok = bp >= 1.0 and s["fills"] >= 300
        out[f"{vid} {leg}"] = dict(fills=s["fills"], notional=notl, net60=s["net60"], pnl=s["pnl_total"],
                                   spread=s["pnl_spread"], inventory=s["pnl_inventory"], fees=s["pnl_fees"], bp=bp,
                                   windows=ws, final_inv=s["final_inv"], ok=ok)
        print(f"{vid:3s} {leg:12s} {s['fills']:6d} {notl:9,.0f} {s['net60']:6.2f} {s['pnl_total']:7.2f} "
              f"{s['pnl_spread']:7.2f} {s['pnl_inventory']:7.2f} {s['pnl_fees']:7.2f} {bp:6.2f} {ws['W1']:6.2f} "
              f"{ws['W2']:6.2f} {s['final_inv']:5.0f}  {'pass' if ok else 'fail'}", flush=True)
    t2 = all(out[f"{vid} {leg}"]["ok"] for leg, _, _ in LEGS)
    print(f"{vid}: T2 {'PASS' if t2 else 'FAIL'}", flush=True)
json.dump(out, open(os.path.join(D, "test2.json"), "w"), indent=1)
