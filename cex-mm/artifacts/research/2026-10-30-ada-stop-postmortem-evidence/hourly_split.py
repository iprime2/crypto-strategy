#!/usr/bin/env python3
"""Exploratory: the live run's mark-to-market PnL per clock hour, split by that hour's own realized vol (1-min returns)
against the median hour of 27-30 Oct. The hour's vol is known only at its end: a description, not a trading rule.
  python3 -I hourly_split.py DATA_DIR   (series.json from make_series.py, live_fills.json)"""
import bisect, datetime as dt, json, math, os, statistics, sys
D = sys.argv[1]
S = json.load(open(os.path.join(D, "series.json"))); TS, MID = S["ts"], S["mid"]; off = S["recv_minus_exch_ms"]
def at(t): i = bisect.bisect_right(TS, t) - 1; return MID[max(i, 0)]
m = {}
for t, x in zip(TS, MID): m[int(t // 60000)] = x
keys = sorted(m); hours = {}
for a, b in zip(keys, keys[1:]):
    if b == a + 1: hours.setdefault(b // 60, []).append(math.log(m[b] / m[a]))
vol = {h: statistics.pstdev(v) * math.sqrt(60) * 1e4 for h, v in hours.items() if len(v) >= 50}
med = statistics.median(vol.values())
def ms(x): return dt.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000
T0, T1 = ms("2026-10-28T16:43:52Z"), ms("2026-10-30T02:03:12Z")
rows = sorted([r for r in json.load(open(os.path.join(D, "live_fills.json"))) if r.get("product_symbol") == "ADAUSD" and T0 <= ms(r["created_at"]) <= T1], key=lambda r: r["created_at"])
fl = [(ms(r["created_at"]) + off, 1 if r["side"] == "buy" else -1, float(r["size"]), float(r["price"]), float(r["commission"])) for r in rows]
edges = [T0 + off] + [h * 3_600_000 for h in range(int((T0 + off) // 3_600_000) + 1, int((T1 + off) // 3_600_000) + 1)] + [T1 + off]
inv = 0.0; i = 0; agg = {"calm": [0.0, 0.0, 0], "vol>2x": [0.0, 0.0, 0]}
for a, b in zip(edges, edges[1:]):
    inv0 = inv; cash = fee = notl = 0.0; n = 0
    while i < len(fl) and fl[i][0] < b:
        t, s, q, p, c = fl[i]; cash -= s * q * p; fee += c; notl += q * p; inv += s * q; n += 1; i += 1
    pnl = cash - fee + inv * at(b) - inv0 * at(a)
    v = vol.get(int(a // 3_600_000)); k = "vol>2x" if v and v > 2 * med else "calm"
    agg[k][0] += pnl; agg[k][1] += notl; agg[k][2] += n
for k, (p, n_, c) in agg.items(): print(f"{k:7s} PnL {p:+7.2f}  fills {c:5d}  notional ${n_:8,.0f}  {p / n_ * 1e4:+.2f} bp/$")
print(f"median hourly vol {med:.0f} bps; flatten not included (run ends at 02:03:12Z)")
