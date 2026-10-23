#!/usr/bin/env python3
"""Read-only microprice study for ADA on recorded MM_METRICS (binance_bid/ask and their sizes, logged every loop).

Part 1 (predictive power, any log): queue imbalance I = bid_qty / (bid_qty + ask_qty) at Binance's best levels.
  For each sample, the direction of the NEXT Binance mid change and how soon it comes. Bucketed by I.
Part 2 (pick-offs, live logs only, needs fills.json): for real fills that came right after a Binance move of
  >= 3 bps toward our price, what I said just before that move started, i.e. whether a microprice fair would have
  leaned our quote away in time.

  python3 microprice.py LOG [LIVE_RUN_DIR ...]
"""
import bisect, glob, json, sys
from pathlib import Path


def rows_of(path):
    out = []
    for line in open(path, errors="replace"):
        if "MM_METRICS" not in line or '"symbol":"ADAUSDT"' not in line:
            continue
        try:
            r = json.loads(line[line.index("{"):])
        except ValueError:
            continue
        b, a, bq, aq = r.get("binance_bid"), r.get("binance_ask"), r.get("binance_bid_qty"), r.get("binance_ask_qty")
        if b and a and bq and aq and a > b:
            out.append((r["ts_ms"], b, a, bq, aq))
    return out


rows = rows_of(sys.argv[1])
print(f"{sys.argv[1]}: {len(rows)} samples with Binance sizes over {(rows[-1][0] - rows[0][0]) / 3.6e6:.1f} h")
spreads = sorted(round((a - b) / ((a + b) / 2) * 1e4, 1) for _, b, a, _, _ in rows)
print(f"Binance spread bps p10 {spreads[len(spreads) // 10]} p50 {spreads[len(spreads) // 2]} p90 {spreads[9 * len(spreads) // 10]}")

# Part 1: next mid change direction by imbalance bucket
mids = [(b + a) / 2 for _, b, a, _, _ in rows]
nxt_dir, nxt_dt = [None] * len(rows), [None] * len(rows)
nd, ndt = None, None
for i in range(len(rows) - 1, -1, -1):
    if i + 1 < len(rows) and mids[i + 1] != mids[i]:
        nd, ndt = (1 if mids[i + 1] > mids[i] else -1), rows[i + 1][0]
    nxt_dir[i] = nd
    nxt_dt[i] = (ndt - rows[i][0]) / 1000 if ndt else None
buckets = [(0, .1), (.1, .2), (.2, .35), (.35, .5), (.5, .65), (.65, .8), (.8, .9), (.9, 1.01)]
print("\nimbalance I = bid_qty/(bid_qty+ask_qty)   samples   next move up   median s to next move")
for lo, hi in buckets:
    sel = [i for i, (_, b, a, bq, aq) in enumerate(rows) if lo <= bq / (bq + aq) < hi and nxt_dir[i] is not None]
    if not sel:
        continue
    up = sum(1 for i in sel if nxt_dir[i] == 1) / len(sel)
    dts = sorted(nxt_dt[i] for i in sel)
    print(f"  {lo:4.2f}-{min(hi, 1):4.2f}                           {len(sel):7d}      {up:6.1%}        {dts[len(dts) // 2]:6.1f}")
# Only the samples right before a move (within 1 s): the signal where it matters
print("\nsamples within 1 s before the next move:")
for lo, hi in buckets:
    sel = [i for i, (_, b, a, bq, aq) in enumerate(rows) if lo <= bq / (bq + aq) < hi and nxt_dir[i] is not None and nxt_dt[i] <= 1.0]
    if sel:
        print(f"  {lo:4.2f}-{min(hi, 1):4.2f}   n={len(sel):6d}   next move up {sum(1 for i in sel if nxt_dir[i] == 1) / len(sel):6.1%}")

# Part 2: pick-off fills on live runs
for run in sys.argv[2:]:
    run = Path(run)
    sys.path.insert(0, str(run.parents[2] / "scripts"))
    import live_vs_shadow as lvs, shadow_fill_sim as sim
    lrows = rows_of(run / "bot.log")
    ts = [r[0] for r in lrows]
    lm = [(r[1] + r[2]) / 2 for r in lrows]
    _, cv = sim.product_meta("ADAUSD")
    span = (ts[0], ts[-1])
    sdirs = lvs.shadow_runs_for(run.parents[1] / "shadow", span[0] - 600_000, span[1])
    tp = [p for d in sdirs for p in sorted(glob.glob(str(d / "delta_mainnet_public_*.jsonl")))]
    off = lvs.clock_offset_ms(tp, "ADAUSD", span[0], span[1])
    rec = []
    for r in json.loads((run / "fills.json").read_text()):
        if r.get("product_symbol") != "ADAUSD":
            continue
        f = lvs.parse_fill(r, cv)
        if not f or f.fill_type != "normal":
            continue
        t = f.ts + off
        i = bisect.bisect_right(ts, t) - 1
        j = bisect.bisect_right(ts, t - 2000) - 1
        if i < 1 or j < 1:
            continue
        move = f.side * (lm[i] - lm[j]) / lm[j] * 1e4
        if move > -3:
            continue  # not a fill after a >= 3 bps move toward our price
        # the last sample before the mid first moved inside the 2 s window
        k = j
        while k < i and lm[k + 1] == lm[j]:
            k += 1
        _, b, a, bq, aq = lrows[k]
        imb = bq / (bq + aq)
        # a bid pick-off follows a fall: did I say "down" (low I) before it? an ask pick-off: high I
        warned = imb < 0.35 if f.side == 1 else imb > 0.65
        rec.append((f.side, imb, warned))
    if rec:
        w = sum(1 for _, _, x in rec if x)
        print(f"\n{run.name}: {len(rec)} pick-off fills (>= 3 bps Binance move toward us in the 2 s before); "
              f"imbalance pointed the right way before the move in {w} ({w / len(rec):.0%})")
        for side, name in ((1, "bid fills (Binance fell)"), (-1, "ask fills (Binance rose)")):
            xs = sorted(imb for s, imb, _ in rec if s == side)
            if xs:
                print(f"  {name:26s} n={len(xs):3d}  I before the move p25 {xs[len(xs) // 4]:.2f} p50 {xs[len(xs) // 2]:.2f} p75 {xs[3 * len(xs) // 4]:.2f}")
