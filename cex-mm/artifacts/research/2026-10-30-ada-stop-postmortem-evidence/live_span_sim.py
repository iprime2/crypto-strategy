#!/usr/bin/env python3
"""Exploratory (not pre-registered): simulator vs the real run on the live span only, like-for-like references.
  python3 live_span_sim.py DATA_DIR REPO_SCRIPTS_DIR"""
import bisect, datetime as dt, glob, json, os, sys
D, SCRIPTS = sys.argv[1], sys.argv[2]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402
T0, T1 = sim.utc_ms("2026-10-28T16:43:52Z"), sim.utc_ms("2026-10-30T02:03:00Z")
samples = [s for s in sim.load_metrics([os.path.join(D, "ada_metrics.log.gz")])["ADAUSDT"] if T0 <= s.ts <= T1]
tape = [t for t in sim.load_trades(sorted(glob.glob(os.path.join(D, "delta_mainnet_public_*.jsonl"))))["ADAUSD"]
        if T0 <= t.ts <= T1]
mids = sim.MidSeries(samples)
ref = samples[len(samples) // 2].fair
print(f"live span: {len(samples)} samples, {len(tape)} trades ({sum(t.size for t in tape):,.0f} contracts), ref {ref:.5f}")
for leg, lat, rule, win in (("300 strict", 300, "strict", 15), ("300 touch", 300, "touch", 15), ("1000 touch", 1000, "touch", 15)):
    cfg = sim.SimConfig(latency_ms=lat, half_spread_bps=None, rule=rule, quote_usd=200 * ref, max_inv_orders=3, fee_bps=2.12,
                        requote_tol_bps=3.0, max_gap_ms=1500, loop_ms=400, scalper_window_min=win)
    res = sim.simulate(samples, tape, 0.00001, 1.0, cfg); s = sim.summarize(res, mids, 1.0)
    n = sum(f.notional for f in res.fills)
    print(f"sim A {leg:10s} fills {s['fills']:5d} ${n:8,.0f} capt {s['capture']:5.2f} mo60 {s['mo'][60]:6.2f} fee {s['fee']:4.2f} "
          f"net60 {s['net60']:5.2f} | PnL {s['pnl_total']:6.2f} ({s['pnl_total'] / n * 1e4:+.2f} bp) inv$ {s['pnl_inventory']:6.2f} | "
          f"Scalper fifo: fee {s['fee_offer']:4.2f} PnL {s['pnl_total_offer']:6.2f} ({s['pnl_total_offer'] / n * 1e4:+.2f} bp)")
# the real fills on the same references (Delta L1 mid logged by the shadow, receive clock)
S = json.load(open(os.path.join(D, "series.json"))); TS, MID = S["ts"], S["mid"]; off = S["recv_minus_exch_ms"]
def at(t):
    i = bisect.bisect_right(TS, t) - 1; return MID[max(i, 0)]
def ms(x): return dt.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000
rows = [r for r in json.load(open(os.path.join(D, "live_fills.json"))) if r.get("product_symbol") == "ADAUSD"
        and T0 <= ms(r["created_at"]) <= T1 + 12_000]
w = c = m = fee = 0.0
for r in rows:
    t = ms(r["created_at"]) + off; s = 1 if r["side"] == "buy" else -1; p = float(r["price"]); q = float(r["size"])
    mid = at(t); n = q * p; w += n
    c += n * s * (mid - p) / p * 1e4; m += n * s * (at(t + 60_000) - mid) / mid * 1e4; fee += float(r["commission"])
print(f"real       fills {len(rows):5d} ${w:8,.0f} capt {c / w:5.2f} mo60 {m / w:6.2f} fee {fee / w * 1e4:4.2f} (as charged; 2.12 list) "
      f"net60 {(c + m) / w - fee / w * 1e4:5.2f} as charged, {(c + m) / w - 2.12:5.2f} at 2.12")
