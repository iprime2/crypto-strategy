"""Out-of-sample test of one pre-registered rule, fixed before looking at this period:
sell a ±3% strangle (and, separately, a 3% OTM put) 24 h before expiry only when the
ATM straddle's implied move > 1.5 × the trailing 7-day mean realised daily move.
Spread cost 5% of mark per leg, Delta fees + GST. Also reports the unconditional baseline."""
import json, math, statistics as st, datetime as dt, collections
import backtest as B
p = json.load(open("expired_options.json"))
by = {}
for c in p:
    if c["settlement_time"].endswith("12:00:00Z"):
        by.setdefault((c["underlying"], B.ts(c["settlement_time"])), []).append(c)
keys = sorted(k for k in by if B.SINCE <= k[1] < B.UNTIL and any(c["launch_time"] and B.ts(c["launch_time"]) <= k[1] - 86400 for c in by[k]))
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as ex:
    days = [d for d in ex.map(lambda k: B.day_data(k[0], k[1], by[k]), keys) if d]
def summ(rows):
    if len(rows) < 5: return f"n={len(rows):3d} (too few)"
    x = [r["pnl_bps"] for r in rows]; sd = st.stdev(x)
    return f"n={len(x):3d} win {sum(v>0 for v in x)/len(x):4.0%} mean {st.mean(x):+6.1f} bps t {st.mean(x)/(sd/math.sqrt(len(x))):+5.2f} worst {min(x):+6.0f} total {sum(x):+6.0f}"
for u in ("BTC", "ETH"):
    ud = sorted((d for d in days if d["underlying"] == u), key=lambda d: d["expiry"])
    if not ud: continue
    first, last = (dt.datetime.fromtimestamp(ud[i]["expiry"], dt.timezone.utc).date() for i in (0, -1))
    s = [r for d in ud if (r := B.structure(d, "straddle", 0.0))]
    print(f"\n=== {u} out-of-sample {first} → {last}: {len(ud)} expiries; implied {st.mean(r['credit_bps'] for r in s):.0f} vs realised {st.mean(abs(r['move_pct'])*100 for r in s):.0f} bps")
    implied = [(B.structure(d, "straddle", 0.0) or {}).get("credit_bps") for d in ud]
    realised = [abs(d["settle"] / d["s0"] - 1) * 1e4 for d in ud]
    sel = [d for i, d in enumerate(ud) if i >= 7 and implied[i] and implied[i] > 1.5 * st.mean(realised[i-7:i])]
    for name in ("strangle_3", "put_3"):
        print(f"  {name} every day      : {summ([r for d in ud if (r := B.structure(d, name, 0.05))])}")
        print(f"  {name} rule (k=1.5)    : {summ([r for d in sel if (r := B.structure(d, name, 0.05))])}")
