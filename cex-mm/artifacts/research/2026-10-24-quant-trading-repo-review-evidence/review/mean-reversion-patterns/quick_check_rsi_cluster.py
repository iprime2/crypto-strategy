"""RSI14<30 long-only leg: date-clustered and per-year view, and trade-level net bps.
Held-day return r_{i,t+1} for coins with RSI_{i,t}<30; averaged across held coins per date (cluster by date);
'excess' subtracts the same day's equal-weight nine-coin return. Descriptive only."""
import sys, importlib.util
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("qc", sys.argv[1]); qc = importlib.util.module_from_spec(spec); spec.loader.exec_module(qc)
data = {c: qc.load(sys.argv[2], c) for c in qc.COINS}
R = pd.DataFrame({c: d.close.pct_change() for c, d in data.items()})
P = pd.DataFrame({c: qc.pos_rsi(d, True) for c, d in data.items()}).reindex(R.index).fillna(0.0)
H = P.shift(1).fillna(0.0)
bask = R.mean(axis=1)
held = (H > 0)
per_date = R.where(held).mean(axis=1).dropna()
excess = (R.sub(bask, axis=0)).where(held).mean(axis=1).dropna()
def tstat(x): return x.mean() / (x.std() / np.sqrt(len(x)))
for wn, a, b in (("FULL", qc.START, qc.END), ("2020-21", qc.START, "2021-12-31"), ("2022-26", qc.SPLIT, qc.END)):
    x = per_date.loc[a:b]; e = excess.loc[a:b]
    print(f"{wn:8s} dates held {len(x):4d}  mean held-coin next-day {x.mean()*1e4:6.1f} bps (date-clustered t {tstat(x):4.2f}); excess over basket {e.mean()*1e4:6.1f} bps (t {tstat(e):4.2f})")
print("by year (dates held, mean bps, excess bps):")
for y in range(2020, 2027):
    x = per_date[per_date.index.year == y].loc[qc.START:qc.END]; e = excess[excess.index.year == y].loc[qc.START:qc.END]
    if len(x): print(f"  {y}: {len(x):3d}  {x.mean()*1e4:7.1f}  {e.mean()*1e4:7.1f}")
# trade level
rows = []
for c, d in data.items():
    p = qc.pos_rsi(d, True).loc[:qc.END]
    cl = d.close.loc[:qc.END]
    ent = None
    for t in range(1, len(p)):
        if p.iloc[t] > 0 and p.iloc[t-1] == 0: ent = t
        if p.iloc[t] == 0 and p.iloc[t-1] > 0 and ent is not None:
            g = cl.iloc[t] / cl.iloc[ent] - 1
            rows.append((c, p.index[ent], t - ent, g, g - 2 * qc.SIDE_COST)); ent = None
T = pd.DataFrame(rows, columns=["coin", "date", "days", "gross", "net"])
T = T[(T.date >= qc.START)]
for wn, a, b in (("FULL", qc.START, qc.END), ("2022-26", qc.SPLIT, qc.END)):
    x = T[(T.date >= a) & (T.date <= b)]
    print(f"trades {wn:8s} n {len(x):3d}  median hold {x.days.median():.0f} d  mean net {x.net.mean()*1e4:7.1f} bps  median net {x.net.median()*1e4:7.1f} bps  win {100*(x.net>0).mean():4.1f}%  distinct entry dates {x.date.nunique()}")
x = T[T.date >= qc.SPLIT].copy(); x["month"] = x.date.dt.to_period("M")
m = x.groupby("month").net.agg(["count", "sum"]).sort_values("sum")
print("2022-26 months ranked by summed net (bottom 3, top 5):"); print((m.head(3)).to_string()); print((m.tail(5)).to_string())
tot = x.net.sum(); top5 = m.tail(5)["sum"].sum()
print(f"2022-26 summed trade net {tot*1e4:.0f} bps; top 5 months {top5*1e4:.0f} bps; ex top 5 months {(tot-top5)*1e4:.0f} bps")
