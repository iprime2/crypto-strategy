"""Independent re-implementation of RESID-1 (spec.md) from raw 5m CSVs; computes per-trade net bps (sizing-free) and the screen stats."""
import sys, glob, math, csv, datetime as dt, json
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
DAY, H, B5 = 86400000, 3600000, 300000
EP = dt.date(1970, 1, 1)
def dms(d): return (d - EP).days * DAY

def load(pattern):
    keep = {}
    for fn in sorted(glob.glob(pattern)):
        with open(fn) as f:
            for line in f:
                if not line[0].isdigit(): continue
                p = line.split(",", 6)
                t = int(p[0]); t = t // 1000 if t > 10**14 else t
                m = t % DAY
                if m % H == 0 or m >= DAY - H or m == H - B5:
                    keep.setdefault(t, (float(p[1]), float(p[4])))
    return keep

def fund(sym):
    rows = {}
    for cache in [f"{SP}/trend-cache", f"{SP}/av_cache", f"{SP}/universe/cache", f"{SP}/universe/cache_all"]:
        for fn in sorted(glob.glob(f"{cache}/binance-{sym}-fundingRate-*.csv")):
            mon = fn[-11:-4]
            if mon in rows: continue
            r = []
            with open(fn) as f:
                for row in csv.reader(f):
                    if row and row[0].isdigit(): r.append((int(row[0]), float(row[2])))
            rows[mon] = r
    out = sorted(x for v in rows.values() for x in v)
    return out

class C:
    def __init__(self, sym, pattern, with_f=True):
        self.b = load(pattern); self.f = fund(sym) if with_f else []
        self.ft = np.array([x[0] for x in self.f], dtype=np.int64)
    def close(self, d):
        D = dms(d)
        v = self.b.get(D - B5)
        if v: return v[1]
        for k in range(2, 13):
            v = self.b.get(D - k * B5)
            if v: return v[1]
        return None
    def p01(self, d):
        v = self.b.get(dms(d) + H - B5)
        return v[1] if v else None
    def px(self, s):
        v = self.b.get((s // H) * H)  # stamps on the hour
        return v[0] if v else None
    def fund_bps(self, t0, t1, p0, sgn):
        a = np.searchsorted(self.ft, t0, side="right"); b = np.searchsorted(self.ft, t1, side="left")
        tot, miss = 0.0, 0
        for s, r in self.f[a:b]:
            ps = self.px(s)
            if ps is None: miss += 1; continue
            tot += -sgn * ps / p0 * r
        return tot, miss

def run(alts, X, start, end, cost=7.31e-4, hold=10, train=50, r2c=0.7, k=2.0, with_f=True):
    trades = []
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    for nm, Y in alts.items():
        holding, trained, counter, mdl, tr = 0, False, 0, None, None
        for d in days:
            cy, cx = Y.close(d), X.close(d)
            if holding != 0:
                if counter > hold or d == end:
                    tr["exit"] = d; tr["how"] = "time" if counter > hold else "end"; trades.append(tr)
                    holding, trained, counter = 0, False, 0
                    continue
                if cy is None or cx is None: continue
                counter += 1; continue
            if cy is None or cx is None: continue
            if not trained:
                ys, xs = [], []
                for j in range(train, 0, -1):
                    dd = d - dt.timedelta(days=j); a_, b_ = Y.close(dd), X.close(dd)
                    if a_ is None or b_ is None: ys = None; break
                    ys.append(math.log(a_)); xs.append(math.log(b_))
                if ys is not None:
                    A = np.column_stack([np.ones(train), xs]); coef, *_ = np.linalg.lstsq(A, np.array(ys), rcond=None)
                    e = np.array(ys) - A @ coef; yy = np.array(ys)
                    r2 = 1 - (e @ e) / ((yy - yy.mean()) @ (yy - yy.mean()))
                    if r2 > r2c:
                        trained, mdl = True, (coef[0], coef[1], float(np.sqrt(np.mean((e - e.mean()) ** 2))))
            if trained:
                a, b, sg = mdl
                f = a + b * math.log(cx); ly = math.log(cy)
                s = 1 if ly > f + k * sg else (-1 if ly < f - k * sg else 0)
                if s:
                    holding, counter = s, 0
                    tr = dict(alt=nm, side=s, entry=d, b=b)
                    if d == end:
                        tr["exit"] = d; tr["how"] = "end"; trades.append(tr); holding, trained = 0, False
    out = []
    for tr in trades:
        Y = alts[tr["alt"]]; s, b = tr["side"], tr["b"]
        py0, px0, py1, px1 = Y.p01(tr["entry"]), X.p01(tr["entry"]), Y.p01(tr["exit"]), X.p01(tr["exit"])
        gross = s * ((py1 / py0 - 1) - b * (px1 / px0 - 1))
        cst = cost * ((1 + abs(b)) + py1 / py0 + abs(b) * px1 / px0)
        t0, t1 = dms(tr["entry"]) + H, dms(tr["exit"]) + H
        fy, my = Y.fund_bps(t0, t1, py0, s) if with_f else (0, 0)
        fx, mx = X.fund_bps(t0, t1, px0, -s * b) if with_f else (0, 0)
        tr.update(gross=1e4 * gross, cost=1e4 * cst, fund=1e4 * (fy + fx), net=1e4 * (gross - cst + fy + fx), fmiss=my + mx,
                  py0=py0, px0=px0, py1=py1, px1=px1)
        out.append(tr)
    return out

def boot(trades, start, end, seed=11, n=2000):
    w0 = start - dt.timedelta(days=start.weekday())
    nw = (end - w0).days // 7 + 1
    S = np.zeros(nw); Cn = np.zeros(nw)
    for t in trades:
        i = (t["entry"] - w0).days // 7; S[i] += t["net"]; Cn[i] += 1
    idx = np.random.default_rng(seed).integers(0, nw, size=(n, nw))
    ss, cc = S[idx].sum(1), Cn[idx].sum(1)
    m = np.where(cc > 0, ss / np.maximum(cc, 1), 0.0)
    return float((m <= 0).mean()), int((m <= 0).sum()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))

def stats(trades, start, end, mid, names):
    net = np.array([t["net"] for t in trades])
    P = boot(trades, start, end)
    h1 = [t["net"] for t in trades if t["entry"] <= mid]; h2 = [t["net"] for t in trades if t["entry"] > mid]
    per = {nm: (len([t for t in trades if t["alt"] == nm]), float(np.mean([t["net"] for t in trades if t["alt"] == nm])) if any(t["alt"] == nm for t in trades) else float("nan")) for nm in names}
    return dict(n=len(trades), mean=float(net.mean()), median=float(np.median(net)), P=P, h1=(len(h1), float(np.mean(h1))), h2=(len(h2), float(np.mean(h2))),
                per=per, pos=sum(1 for v in per.values() if v[0] and v[1] > 0), fmiss=sum(t["fmiss"] for t in trades))

if __name__ == "__main__":
    NINE = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
    co = {c: C(f"{c}USDT", f"{SP}/universe/klines5m/binance-{c}USDT-5m-*.csv") for c in NINE}
    X = co.pop("BTC")
    S0, E0 = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
    tr = run(co, X, S0, E0)
    st = stats(tr, S0, E0, dt.date(2023, 6, 30), NINE[1:])
    print(json.dumps(st, indent=0, default=str))
    with open(sys.argv[1], "w") as f:
        w = csv.writer(f); w.writerow(["alt", "side", "entry", "exit", "how", "b", "gross", "cost", "fund", "net", "py0", "px0", "py1", "px1"])
        for t in tr: w.writerow([t["alt"], t["side"], t["entry"], t["exit"], t["how"], f"{t['b']:.6f}", f"{t['gross']:.4f}", f"{t['cost']:.4f}", f"{t['fund']:.4f}", f"{t['net']:.4f}", t["py0"], t["px0"], t["py1"], t["px1"]])
