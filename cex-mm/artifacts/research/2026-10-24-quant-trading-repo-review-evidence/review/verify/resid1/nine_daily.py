"""Independent G0 daily book returns from my own trade list and raw 1h/5m bars, then corr with the tools2 weekly TV 0.25 book (F6)."""
import sys, datetime as dt, math
V = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/verify/resid1"
sys.path.insert(0, V)
import numpy as np
import indep as I, indep_gated as G
SP, DAY, H = I.SP, I.DAY, I.H
X = G.CB("BTCUSDT", f"{SP}/universe/klines5m/binance-BTCUSDT-5m-*.csv")
names = "ETH XRP BNB ADA LTC LINK DOGE BCH".split()
alts = {c: G.CB(f"{c}USDT", f"{SP}/universe/klines5m/binance-{c}USDT-5m-*.csv") for c in names}
S, E = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
tr = G.run(alts, X, S, E)
by_entry, by_exit = {}, {}
for t in tr:
    by_entry.setdefault(t["entry"], []).append(t); by_exit.setdefault(t["exit"], []).append(t)
cost = 7.31e-4
eq, rets, dates, openl = 1.0, [], [], []
d = S
while d <= E:
    pnl = 0.0; tm = I.dms(d) + H; tp = tm - DAY
    still = []
    for t in openl:
        Y = alts[t["alt"]]
        exiting = t["exit"] == d
        for coin, k in ((Y, "y"), (X, "x")):
            u = t["u" + k]
            if exiting:
                px = t["py1"] if k == "y" else t["px1"]; hi = t["t1"]; incl = False
            else:
                px = coin.p01(d); hi = tm; incl = True
            if px is not None:
                pnl += u * (px - t["m" + k]); t["m" + k] = px
            lo = max(t["t0"], tp)
            for s_, r_ in coin.f[np.searchsorted(coin.ft, lo, side="right"):np.searchsorted(coin.ft, hi, side="right" if incl else "left")]:
                pnl += -u * coin.px(s_) * r_
            if exiting:
                pnl -= cost * abs(u) * px
        if not exiting: still.append(t)
    openl = still
    for t in by_entry.get(d, []):
        N = eq / 8
        t["uy"] = t["side"] * N / t["py0"]; t["ux"] = -t["side"] * t["b"] * N / t["px0"]
        t["my"], t["mx"] = t["py0"], t["px0"]
        pnl -= cost * (N + abs(t["b"]) * N)
        if t["exit"] == d:
            pnl -= cost * (N + abs(t["b"]) * N)
        else:
            openl.append(t)
    r = pnl / eq; eq += pnl; rets.append(r); dates.append(d); d += dt.timedelta(days=1)
rets = np.array(rets)
print("my G0 daily: Sharpe", rets.mean() / rets.std(ddof=1) * math.sqrt(365), "final eq", eq)
sys.path.insert(0, f"{SP}/tools2")
import data, rules, sim
P = data.load_binance().sub(["BTC"] + names)
Wk = rules.baseline_weights(P.C, tv=0.25, max_gross=1.0)
rk = sim.simulate(P, Wk, decide=rules.decide_weekly(P.dates, 6), band=0.10, start=S, end=E)
tb = {c + dt.timedelta(days=1): x for c, x in zip(rk["dates"], rk["rets"])}
a = np.array([(x, tb[dd]) for dd, x in zip(dates, rets) if dd in tb])
print("corr", np.corrcoef(a[:, 0], a[:, 1])[0, 1], "n", len(a))
for lag in (-1, 1):
    tb2 = {c + dt.timedelta(days=1 + lag): x for c, x in zip(rk["dates"], rk["rets"])}
    a2 = np.array([(x, tb2[dd]) for dd, x in zip(dates, rets) if dd in tb2])
    print(" lag", lag, "corr", np.corrcoef(a2[:, 0], a2[:, 1])[0, 1])
dd = np.array(dates)
def sh(x): return x.mean() / x.std(ddof=1) * math.sqrt(365)
print("F2 halves", sh(rets[dd <= dt.date(2023, 12, 31)]), sh(rets[dd >= dt.date(2024, 1, 1)]))
eqp = np.cumprod(1 + rets); print("CAGR", eqp[-1] ** (365.25 / len(rets)) - 1, "maxDD", (eqp / np.maximum.accumulate(eqp) - 1).min())
for y in range(2020, 2027):
    m = np.array([x.year == y for x in dates]); print(y, "%+.1f%%" % (100 * (np.prod(1 + rets[m]) - 1)))
