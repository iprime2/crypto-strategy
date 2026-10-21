#!/usr/bin/env python3
"""Pre-registered diagnostics (not trials): D-1 turning-point states (gates SIG-9 / OVL-3), D-3 decision-to-fill drift on 5 m klines,
D-4 MARK vs last-trade closes on Delta. Writes research2/phase2/diagnostics.md."""
import csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import data, rules

S = data.SP
OUT = f"{S}/research2/phase2/diagnostics.md"
lines = ["# Phase-2 diagnostics (pre-registered, not trials)\n"]


def nw_tstat(x, lag=6):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 20:
        return float("nan"), float("nan"), n
    m = x.mean(); e = x - m
    s2 = (e * e).sum() / n
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        s2 += 2 * w * (e[L:] * e[:-L]).sum() / n
    return float(m), float(m / np.sqrt(max(s2, 1e-18) / n)), n


# ---------------------------------------------------------------- D-1
def d1(panel, label, a, b):
    C = panel.C
    slow = np.sign(rules.lag_return(C, 120)); fast = np.sign(rules.lag_return(C, 20))
    sig = np.maximum(np.nan_to_num(rules.sig_sign_mean(C)), 0.0)
    fwd = np.full(C.shape, np.nan); fwd[:-7] = np.log(C[7:] / C[:-7])
    d = np.array(panel.dates); m = (d >= a) & (d <= b)
    res = {}
    for name, cond in (("Bull", (slow > 0) & (fast > 0)), ("Correction", (slow > 0) & (fast < 0)), ("Bear", (slow < 0) & (fast < 0)), ("Rebound", (slow < 0) & (fast > 0))):
        sel = cond & m[:, None]
        for tag, extra in (("all", np.ones_like(sel)), ("sig>0", sig > 0)):
            x = fwd[sel & extra]
            mu, t, n = nw_tstat(x)
            res[f"{name}/{tag}"] = (mu, t, n)
    lines.append(f"\n## D-1 states, {label}, {a}..{b} (next-7-day log return, NW t lag 6)\n")
    lines.append("| state | mean (all) | t | n | mean (sig>0) | t | n |\n|---|---|---|---|---|---|---|")
    for st in ("Bull", "Correction", "Bear", "Rebound"):
        a1 = res[f"{st}/all"]; a2 = res[f"{st}/sig>0"]
        lines.append(f"| {st} | {a1[0]*100:+.3f}% | {a1[1]:+.2f} | {a1[2]} | {a2[0]*100:+.3f}% | {a2[1]:+.2f} | {a2[2]} |")
    return res


P = data.load_binance()
gates = {}
for label, coins in (("nine", data.NINE), ("24 ex-ante", data.EXANTE24)):
    for a, b in ((dt.date(2020, 5, 1), dt.date(2026, 9, 30)), (dt.date(2022, 1, 1), dt.date(2026, 9, 30))):
        r = d1(P.sub(coins), label, a, b)
        gates[(label, a)] = r
sig9 = all(gates[("24 ex-ante", a)]["Correction/all"][0] >= gates[("24 ex-ante", a)]["Bull/all"][0] for a in (dt.date(2020, 5, 1), dt.date(2022, 1, 1)))
ovl3 = all(gates[("24 ex-ante", a)]["Correction/all"][0] <= 0 and gates[("24 ex-ante", a)]["Correction/all"][1] < 0 for a in (dt.date(2020, 5, 1), dt.date(2022, 1, 1)))
lines.append(f"\n**Gate:** SIG-9 runs = {sig9} (Correction >= Bull on the 24-coin panel in both windows); OVL-3 runs = {ovl3} (Correction <= 0 with t < 0 in both windows).\n")

# ---------------------------------------------------------------- D-3: 00:00 -> 00:05 drift conditional on the rule's trade direction
lines.append("\n## D-3 decision-to-fill drift (Binance 5 m, 2024-01..2026-09, signed 00:00 -> 00:05 UTC return by trade direction)\n")
p9 = P.sub(data.NINE)
W = rules.baseline_weights(p9.C, tv=0.40)
drift = {"buy": [], "sell": [], "none": []}
per_coin = {}
for j, c in enumerate(data.NINE):
    px5 = {}
    for fn in sorted(os.listdir(f"{S}/universe/klines5m")):
        if fn.startswith(f"binance-{c}USDT-5m-"):
            with open(f"{S}/universe/klines5m/{fn}") as f:
                for row in csv.reader(f):
                    if not row or not row[0].isdigit():
                        continue
                    ts = int(row[0]); ts = ts / 1e6 if ts > 1e14 else ts / 1000
                    t = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
                    if t.hour == 0 and t.minute in (0, 5):
                        px5[(t.date(), t.minute)] = (float(row[1]), float(row[4]))  # open, close of the bar
    prev_w = 0.0
    for t, d in enumerate(p9.dates):
        if d < dt.date(2024, 1, 1):
            prev_w = W[t, j]; continue
        nd = d + dt.timedelta(1)
        if (nd, 0) in px5 and (nd, 5) in px5:
            o00 = px5[(nd, 0)][0]; c05 = px5[(nd, 5)][1]  # 00:00 open (the decision close) -> 00:05 bar close (the fill)
            r = np.log(c05 / o00)
            dw = W[t, j] - prev_w
            key = "buy" if dw > 1e-9 else ("sell" if dw < -1e-9 else "none")
            drift[key].append(r); per_coin.setdefault(c, {"buy": [], "sell": []})
            if key != "none":
                per_coin[c][key].append(r)
        prev_w = W[t, j]
lines.append("| direction | mean bps | NW t | n |\n|---|---|---|---|")
for k in ("buy", "sell", "none"):
    mu, t, n = nw_tstat(drift[k])
    lines.append(f"| {k} | {mu*1e4:+.2f} | {t:+.2f} | {n} |")
lines.append("\nPer coin (buy / sell mean bps): " + ", ".join(f"{c} {nw_tstat(v['buy'])[0]*1e4:+.1f}/{nw_tstat(v['sell'])[0]*1e4:+.1f}" for c, v in per_coin.items()))
buy_mu = nw_tstat(drift["buy"])[0] * 1e4; sell_mu = nw_tstat(drift["sell"])[0] * 1e4
lines.append(f"\n**Gate:** re-run daily cost lines with drift = {'YES' if (abs(buy_mu) > 2 or abs(sell_mu) > 2) else 'NO'} (|mean| > 2 bps on buys or sells: buys {buy_mu:+.2f}, sells {sell_mu:+.2f}; a positive buy drift is a cost to the buyer, a negative sell drift a cost to the seller).\n")

# ---------------------------------------------------------------- D-4: MARK vs last-trade closes on Delta
lines.append("\n## D-4 Delta MARK vs last-trade daily closes (sign agreement per sleeve; Sharpe of the daily rule on each series)\n")
D = data.load_delta().sub(data.NINE)
Cm = np.full(D.C.shape, np.nan)
for j, c in enumerate(data.NINE):
    try:
        bars = json.load(open(f"{S}/universe/delta_mark/mark_{c}USD.json"))
    except FileNotFoundError:
        continue
    for bb in bars:
        d = dt.datetime.fromtimestamp(bb["time"], dt.timezone.utc).date()
        if d in D.idx:
            Cm[D.idx[d], j] = float(bb["close"])
agree = {}
for L in (20, 60, 120):
    s1 = np.sign(rules.lag_return(D.C, L)); s2 = np.sign(rules.lag_return(Cm, L))
    ok = np.isfinite(s1) & np.isfinite(s2)
    agree[L] = float((s1[ok] == s2[ok]).mean())
diff = np.log(Cm / D.C); diff = diff[np.isfinite(diff)]
lines.append(f"sign agreement 20/60/120: {agree[20]:.4f} / {agree[60]:.4f} / {agree[120]:.4f}; |MARK - last| median {np.median(np.abs(diff))*1e4:.1f} bps, 95th pct {np.percentile(np.abs(diff), 95)*1e4:.1f} bps, n = {len(diff)}")
import sim
Dm = data.Panel(D.dates, D.coins, Cm.copy(), Cm.copy(), Cm.copy(), Cm, D.V, D.F, D.Q)
a, b = dt.date(2024, 8, 10), dt.date(2026, 10, 12)
for label, pan in (("last-trade", D), ("MARK", Dm)):
    for cad, tv, mg, band, wk in (("daily", 0.40, 2.0, 0.0, False), ("weekly", 0.25, 1.0, 0.10, True)):
        Wd = rules.baseline_weights(pan.C, tv=tv, max_gross=mg)
        r = sim.simulate(pan, Wd, decide=rules.decide_weekly(pan.dates, 6) if wk else None, band=band, start=a, end=b)
        st = sim.stats(r)
        lines.append(f"- {label} {cad}: Sharpe {st['sharpe']:.3f} CAGR {st['cagr']:+.1%} maxDD {st['mdd']:.1%} turnover {st['turnover']:.1f}x")
open(OUT, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
