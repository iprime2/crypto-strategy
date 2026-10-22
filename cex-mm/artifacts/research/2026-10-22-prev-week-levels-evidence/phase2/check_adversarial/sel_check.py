"""Independent recompute of the OX selection from raw 1d files (cache_all + cache), and the literal cache_all-only variant."""
import os, re, json
import numpy as np, pandas as pd
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
P1 = set((c + "USDT") for c in "BTC ETH XRP BNB ADA LTC LINK DOGE BCH EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST".split())
files = {}
for d in ("cache_all", "cache"):
    for fn in os.listdir(f"{SP}/universe/{d}"):
        m = re.match(r"^binance-(.+)-1d-(\d{4}-\d{2})\.csv$", fn)
        if m:
            files.setdefault(m.group(1), {}).setdefault(m.group(2), f"{SP}/universe/{d}/{fn}")
def rd(p):
    with open(p) as f:
        first = f.readline()
    hdr = 0 if not first[0].isdigit() else None
    df = pd.read_csv(p, header=hdr).iloc[:, :8]
    df.columns = range(8)
    t = pd.to_numeric(df[0]).astype("int64").to_numpy()
    t = np.where(t > 10**14, t // 1000, t)
    return t, pd.to_numeric(df[7]).to_numpy(float)
lo = int(pd.Timestamp("2021-10-01", tz="UTC").value // 10**6); hi = int(pd.Timestamp("2021-12-31", tz="UTC").value // 10**6)
cut = int(pd.Timestamp("2021-10-01", tz="UTC").value // 10**6)
rows = []
for s, ym in files.items():
    if not s.endswith("USDT") or s in P1 or s in ("DEFIUSDT", "BTCDOMUSDT") or s.endswith("INDEX"):
        continue
    first = min(ym)
    t, _ = rd(ym[first])
    if t.min() >= cut:
        continue
    ts, vs = [], []
    for m in ("2021-10", "2021-11", "2021-12"):
        if m in ym:
            a, b = rd(ym[m]); ts.append(a); vs.append(b)
    if not ts:
        continue
    t = np.concatenate(ts); v = np.concatenate(vs)
    _, iu = np.unique(t, return_index=True); t, v = t[iu], v[iu]
    k = (t >= lo) & (t <= hi)
    if k.sum() == 0:
        continue
    src = "cache_all" if any("cache_all" in p for p in ym.values()) else "cache"
    rows.append((s, float(np.median(v[k])), int(k.sum()), src))
df = pd.DataFrame(rows, columns=["sym", "med", "nd", "src"]).sort_values("med", ascending=False).reset_index(drop=True)
top = df.head(15).sym.tolist()
sel = pd.read_csv(f"{SP}/research3/p2/data_ox/selection.csv")
theirs = sel[sel.selected == 1].sort_values("rank").symbol.tolist()
out = {"n_eligible": len(df), "top15": top, "match_selection_csv": top == theirs,
       "rank15_16_gap": [df.sym[14], df.med[14], df.sym[15], df.med[15]],
       "top20": df.head(20).values.tolist(),
       "cache_all_only_top15": df[df.src == "cache_all"].head(15).sym.tolist()}
json.dump(out, open("sel_check.json", "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ("n_eligible", "top15", "match_selection_csv", "rank15_16_gap", "cache_all_only_top15")}, indent=1, default=str))
