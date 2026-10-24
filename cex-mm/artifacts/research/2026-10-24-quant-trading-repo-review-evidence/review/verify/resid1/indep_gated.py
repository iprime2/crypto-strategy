"""Independent RESID-1 gated panels (A spot, B 15 perps, G0 16 perps on 1h) from raw files; trade-level bps only."""
import sys, glob, math, csv, datetime as dt, json
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/verify/resid1")
import numpy as np
import indep as I
SP, DAY, H = I.SP, I.DAY, I.H

class CB(I.C):
    def __init__(self, sym, pattern, with_f=True, bar=300000):
        self.bar = bar
        keep = {}
        for fn in sorted(glob.glob(pattern)):
            with open(fn) as f:
                for line in f:
                    if not line[0].isdigit(): continue
                    p = line.split(",", 6); t = int(p[0]); t = t // 1000 if t > 10**14 else t
                    keep.setdefault(t, (float(p[1]), float(p[4])))
        self.b = keep; self.last_t = max(keep); self.first_t = min(keep)
        self.f = I.fund(sym) if with_f else []
        self.ft = np.array([x[0] for x in self.f], dtype=np.int64)
        self.ts = np.array(sorted(keep), dtype=np.int64)
    def close(self, d):
        D = I.dms(d)
        for k in range(1, H // self.bar + 1):
            v = self.b.get(D - k * self.bar)
            if v: return v[1]
        return None
    def p01(self, d):
        v = self.b.get(I.dms(d) + H - self.bar); return v[1] if v else None
    def px(self, s):
        v = self.b.get((s // self.bar) * self.bar)
        if v: return v[0]
        j = np.searchsorted(self.ts, s - self.bar, side="right") - 1
        return self.b[int(self.ts[j])][1]
    def fill(self, d):
        p = self.p01(d)
        if p is not None: return p, I.dms(d) + H, False
        D = I.dms(d)
        for t in range(D + H, D + DAY, self.bar):
            v = self.b.get(t)
            if v: return v[1], t + self.bar, True
        return None

def run(alts, X, start, end, cost=7.31e-4, with_f=True):
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    trades = []
    for nm, Y in alts.items():
        holding, trained, counter, mdl, tr, pend = 0, False, 0, None, None, False
        for d in days:
            if holding != 0 and Y.last_t + Y.bar < I.dms(d) + H and Y.fill(d) is None:
                t_last = Y.last_t + Y.bar
                tr.update(exit=d, how="delist", py1=Y.b[Y.last_t][1], px1=X.px(t_last), t1=t_last); trades.append(tr)
                holding, trained, counter, pend = 0, False, 0, False; continue
            cy, cx = Y.close(d), X.close(d)
            if holding != 0:
                if pend or counter > 10 or d == end:
                    fy, fx = Y.fill(d), X.fill(d)
                    if fy is None or fx is None:
                        if d == end:
                            fy = fy or (tr["lasty"], 0, True); fx = fx or (tr["lastx"], 0, True)
                        else:
                            pend = True; continue
                    tr.update(exit=d, how="end" if (d == end and counter <= 10 and not pend) else "time", py1=fy[0], px1=fx[0], t1=max(fy[1], fx[1]), fb=fy[2] or fx[2])
                    trades.append(tr); holding, trained, counter, pend = 0, False, 0, False; continue
                if Y.p01(d) is not None: tr["lasty"] = Y.p01(d)
                if X.p01(d) is not None: tr["lastx"] = X.p01(d)
                if cy is None or cx is None: continue
                counter += 1; continue
            if cy is None or cx is None: continue
            if not trained:
                ys, xs = [], []
                for j in range(50, 0, -1):
                    dd = d - dt.timedelta(days=j); a_, b_ = Y.close(dd), X.close(dd)
                    if a_ is None or b_ is None: ys = None; break
                    ys.append(math.log(a_)); xs.append(math.log(b_))
                if ys is not None:
                    yy = np.array(ys); A = np.column_stack([np.ones(50), xs]); coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
                    e = yy - A @ coef; r2 = 1 - (e @ e) / ((yy - yy.mean()) @ (yy - yy.mean()))
                    if r2 > 0.7: trained, mdl = True, (coef[0], coef[1], float(np.sqrt(np.mean((e - e.mean()) ** 2))))
            if trained:
                a, b, sg = mdl; f = a + b * math.log(cx); ly = math.log(cy)
                s = 1 if ly > f + 2 * sg else (-1 if ly < f - 2 * sg else 0)
                if s:
                    fy, fx = Y.fill(d), X.fill(d)
                    if fy is None or fx is None: continue
                    holding, counter = s, 0
                    tr = dict(alt=nm, side=s, entry=d, b=b, py0=fy[0], px0=fx[0], t0=max(fy[1], fx[1]), lasty=fy[0], lastx=fx[0])
                    if d == end:
                        tr.update(exit=d, how="end", py1=fy[0], px1=fx[0], t1=tr["t0"]); trades.append(tr); holding, trained = 0, False
    for tr in trades:
        s, b = tr["side"], tr["b"]; Y = alts[tr["alt"]]
        g = s * ((tr["py1"] / tr["py0"] - 1) - b * (tr["px1"] / tr["px0"] - 1))
        c = cost * ((1 + abs(b)) + tr["py1"] / tr["py0"] + abs(b) * tr["px1"] / tr["px0"]) if tr["t1"] != tr["t0"] or tr["exit"] != tr["entry"] else cost * 2 * (1 + abs(b))
        fy, _ = Y.fund_bps(tr["t0"], tr["t1"], tr["py0"], s) if with_f else (0, 0)
        fx, _ = X.fund_bps(tr["t0"], tr["t1"], tr["px0"], -s * b) if with_f else (0, 0)
        tr.update(gross=1e4 * g, cost=1e4 * c, fund=1e4 * (fy + fx), net=1e4 * (g - c + fy + fx), fmiss=0)
    return trades

def report(label, tr, S, E, mid, names, need):
    st = I.stats(tr, S, E, mid, names)
    ok = st["mean"] > 0 and st["P"][0] <= 0.01 and st["h1"][1] > 0 and st["h2"][1] > 0 and st["pos"] >= need
    print(label, json.dumps({k: st[k] for k in ("n", "mean", "median", "P", "h1", "h2", "pos")}, default=str), "PASS" if ok else "FAIL")
    print("   per alt", {k: (v[0], round(v[1], 1)) for k, v in st["per"].items()})

if __name__ == "__main__":
    which = sys.argv[1]
    if which == "A":
        sp = f"{SP}/universe/spot5m"
        X = CB("x", f"{sp}/binance-spot-BTCUSDT-5m-*.csv", with_f=False)
        names = "ETH XRP BNB ADA LTC LINK DOGE EOS ETC NEO TRX XLM".split()
        alts = {c: CB("x", f"{sp}/binance-spot-{c}USDT-5m-*.csv", with_f=False) for c in names}
        S, E = dt.date(2017, 8, 1), dt.date(2020, 4, 30)
        tr = run(alts, X, S, E, with_f=False); report("HOLDOUT A", tr, S, E, dt.date(2019, 1, 18), names, 8)
    elif which == "B":
        X = CB("BTCUSDT", f"{SP}/universe/klines5m/binance-BTCUSDT-5m-*.csv")
        names = "1000SHIB SOL SAND LUNA MANA DOT AVAX FTM MATIC GALA AXS DYDX FIL LRC CRV".split()
        alts = {c: CB(f"{c}USDT", f"{SP}/universe/ox5m/binance-{c}USDT-5m-*.csv") for c in names}
        S, E = dt.date(2022, 1, 1), dt.date(2026, 9, 30)
        tr = run(alts, X, S, E); report("HOLDOUT B", tr, S, E, dt.date(2024, 5, 26), names, 10)
        print("   LUNA", [(t["entry"], t["exit"], t["how"], round(t["net"], 1)) for t in tr if t["alt"] == "LUNA"])
    else:
        X = CB("BTCUSDT", f"{SP}/universe/klines5m/binance-BTCUSDT-5m-*.csv")
        names = "ATOM BAT DASH EOS ETC IOST IOTA NEO ONT QTUM TRX VET XLM XMR XTZ ZEC".split()
        alts = {c: CB(f"{c}USDT", f"{SP}/universe/hourly_extra/binance-{c}USDT-1h-*.csv", bar=3600000) for c in names}
        S, E = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
        tr = run(alts, X, S, E); report("G0", tr, S, E, dt.date(2023, 6, 30), names, 11)
    with open(f"/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/verify/resid1/indep_{which}.csv", "w") as f:
        w = csv.writer(f); w.writerow(["alt", "side", "entry", "exit", "how", "b", "gross", "cost", "fund", "net"])
        for t in tr: w.writerow([t["alt"], t["side"], t["entry"], t["exit"], t["how"], t["b"], t["gross"], t["cost"], t["fund"], t["net"]])
