"""OPT-W1 analysis: weekly short ATM straddle P&L, stats and the pre-registered pass rule (../spec.md).
Usage: python3 -I analyze.py <screen_dir>"""
import json, math, os, sys
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np

DIR = sys.argv[1] if len(sys.argv) > 1 else "."
FEE_RATE, FEE_CAP, GST = 0.0001, 0.035, 1.18
SPLIT = int(datetime(2025, 9, 29, tzinfo=timezone.utc).timestamp())
DAY = 86400
H = (0.0, 0.02, 0.05, 0.10)
PRIMARY = 0.05


def d(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")


def leg(price, K, ST, S0, typ):
    intr = max(ST - K, 0.0) if typ == "C" else max(K - ST, 0.0)
    f_open = min(FEE_RATE * S0, FEE_CAP * price) * GST
    f_set = FEE_RATE * ST * GST if intr > 0 else 0.0
    return price - intr - f_open - f_set, intr, f_open, f_set


def straddle(r, h):
    S0, ST, K = r["s0"], r["settle"], r["K"]
    pc, pp = r["mc"] * (1 - h), r["mp"] * (1 - h)
    a = leg(pc, K, ST, S0, "C")
    b = leg(pp, K, ST, S0, "P")
    return {"pnl": (a[0] + b[0]) / S0 * 1e4, "credit": (pc + pp) / S0 * 1e4,
            "fees": (a[2] + a[3] + b[2] + b[3]) / S0 * 1e4, "intr": (a[1] + b[1]) / S0 * 1e4,
            "fo": a[2] + b[2], "fs": a[3] + b[3], "price": pc + pp, "intr_px": a[1] + b[1]}


def strangle(r, h):
    nb = r.get("strangle") or {}
    c, p = nb.get("C"), nb.get("P")
    if not c or not p:
        return None
    S0, ST = r["s0"], r["settle"]
    a = leg(c["mark"] * (1 - h), c["K"], ST, S0, "C")
    b = leg(p["mark"] * (1 - h), p["K"], ST, S0, "P")
    return {"pnl": (a[0] + b[0]) / S0 * 1e4, "credit": (c["mark"] + p["mark"]) * (1 - h) / S0 * 1e4,
            "Kc": c["K"], "Kp": p["K"]}


def stats(x):
    x = np.asarray(x, float)
    n = len(x)
    if n == 0:
        return {"n": 0}
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    cum = np.cumsum(x)
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return {"n": n, "mean": float(x.mean()), "sd": sd, "t": float(x.mean() / (sd / math.sqrt(n))) if sd > 0 else float("nan"),
            "win": float((x > 0).mean()), "worst": float(x.min()), "best": float(x.max()), "total": float(x.sum()),
            "max_dd": float(min(0.0, (cum - peak).min())), "median": float(np.median(x))}


def fmt(s):
    if not s.get("n"):
        return "n=0"
    return (f"n={s['n']:3d} mean {s['mean']:+7.1f} sd {s['sd']:6.1f} t {s['t']:+5.2f} win {s['win']:4.0%} "
            f"median {s['median']:+6.1f} worst {s['worst']:+7.0f} best {s['best']:+6.0f} total {s['total']:+7.0f} maxDD {s['max_dd']:+7.0f}")


def main():
    weeks = json.load(open(os.path.join(DIR, "out", "weeks.json")))
    step0 = json.load(open(os.path.join(DIR, "out", "step0.json")))
    lines = []
    P = lambda *a: lines.append(" ".join(str(x) for x in a))
    P("OPT-W1 weekly short ATM straddle, Delta India BTC/ETH. Spec sha256:", open(os.path.join(DIR, "spec_sha256.txt")).read().split()[0])
    P("\n== Step 0 (Friday 12:00 UTC expiries 2023-12-01..2026-10-23)")
    for u in ("BTC", "ETH"):
        P(f"  {u}: {step0[u]}")
    P("  Fridays listed but with no contract live 168 h before:", {u: len(v) for u, v in step0["fridays_without_168h_contract"].items()},
      step0["fridays_without_168h_contract"])
    ok = [r for r in weeks if not r.get("skip")]
    skipped = [r for r in weeks if r.get("skip")]
    P("\n== Coin-weeks: total", len(weeks), "valid", len(ok), "skipped", len(skipped))
    reasons = defaultdict(list)
    for r in skipped:
        reasons[(r["underlying"], r["skip"])].append(d(r["expiry"]))
    for k, v in sorted(reasons.items()):
        P(f"  skip {k}: {len(v)} {v[:12]}{' ...' if len(v) > 12 else ''}")
    # strike distance check
    for u in ("BTC", "ETH"):
        ur = [r for r in ok if r["underlying"] == u]
        dist = [abs(r["K"] / r["s0"] - 1) * 1e4 for r in ur]
        fall = sum(1 for r in ur if len(r["tried"]) > 1)
        nonnear = sum(1 for r in ur if r["tried"][0]["K"] != r["K"])
        P(f"  {u}: |K/S0-1| bps mean {np.mean(dist):.1f} max {np.max(dist):.1f}; weeks where nearest strike lacked marks (fallback) {nonnear}")

    res = {}
    for h in H:
        for r in ok:
            r.setdefault("st", {})[h] = straddle(r, h)
    by_coin = {u: [r for r in ok if r["underlying"] == u] for u in ("BTC", "ETH")}

    def pooled_series(h, rows=ok, f=lambda r, h: r["st"][h]["pnl"]):
        g = defaultdict(list)
        for r in rows:
            v = f(r, h)
            if v is not None:
                g[r["expiry"]].append(v)
        ks = sorted(g)
        return ks, [float(np.mean(g[k])) for k in ks]

    P("\n== Weekly P&L, bps of underlying notional per straddle")
    for h in H:
        P(f"-- haircut {h:.2f}" + ("  (PRIMARY)" if h == PRIMARY else "  (sensitivity, not selectable)" if h else "  (no haircut, reference only)"))
        for u in ("BTC", "ETH"):
            s = stats([r["st"][h]["pnl"] for r in by_coin[u]])
            res[(u, h)] = s
            P(f"  {u:6s} {fmt(s)}")
        ks, ps = pooled_series(h)
        s = stats(ps)
        res[("POOL", h)] = s
        P(f"  POOLED {fmt(s)}")

    h = PRIMARY
    P(f"\n== Calendar years (haircut {h}), by expiry year")
    ks, ps = pooled_series(h)
    years = {}
    for y in (2023, 2024, 2025, 2026):
        row = [f"  {y}:"]
        for u in ("BTC", "ETH"):
            x = [r["st"][h]["pnl"] for r in by_coin[u] if datetime.fromtimestamp(r["expiry"], timezone.utc).year == y]
            s = stats(x)
            row.append(f"{u} n={s['n']} mean {s.get('mean', float('nan')):+.1f} t {s.get('t', float('nan')):+.2f} total {s.get('total', 0):+.0f};")
        x = [p for k, p in zip(ks, ps) if datetime.fromtimestamp(k, timezone.utc).year == y]
        s = stats(x)
        years[y] = s
        row.append(f"POOLED n={s['n']} mean {s.get('mean', float('nan')):+.1f} t {s.get('t', float('nan')):+.2f} total {s.get('total', 0):+.0f} worst {s.get('worst', float('nan')):+.0f}")
        P(" ".join(row))

    P("\n== Mean ATM credit vs mean realised |S_T/S0 - 1| (bps), A = 2023-12..2025-09-28, B = 2025-09-29..2026-10-23")
    vrp = {}
    for u in ("BTC", "ETH"):
        for lab, rows in (("A", [r for r in by_coin[u] if r["expiry"] < SPLIT]), ("B", [r for r in by_coin[u] if r["expiry"] >= SPLIT]), ("ALL", by_coin[u])):
            c0 = np.mean([r["st"][0.0]["credit"] for r in rows])
            c5 = np.mean([r["st"][0.05]["credit"] for r in rows])
            mv = np.mean([abs(r["settle"] / r["s0"] - 1) * 1e4 for r in rows])
            pay = np.mean([r["st"][0.0]["intr"] for r in rows])
            fe = np.mean([r["st"][0.05]["fees"] for r in rows])
            vrp[(u, lab)] = (c5, mv)
            P(f"  {u} {lab:3s} n={len(rows):3d} credit@0 {c0:6.1f} credit@0.05 {c5:6.1f} realised|move| {mv:6.1f} mean payout |S_T-K| {pay:6.1f} fees@0.05 {fe:4.1f}  credit@0.05 - move {c5 - mv:+6.1f}")
    for lab in ("A", "B"):
        rows = [r for r in ok if (r["expiry"] < SPLIT) == (lab == "A")]
        c5 = np.mean([r["st"][0.05]["credit"] for r in rows]); mv = np.mean([abs(r["settle"] / r["s0"] - 1) * 1e4 for r in rows])
        P(f"  BOTH {lab} (pooled coin-weeks, info) n={len(rows)} credit@0.05 {c5:6.1f} realised {mv:6.1f}")

    P(f"\n== Sub-periods (haircut {h})")
    half = {}
    for lab, cond in (("A", lambda r: r["expiry"] < SPLIT), ("B", lambda r: r["expiry"] >= SPLIT)):
        rows = [r for r in ok if cond(r)]
        s_tr = stats([r["st"][h]["pnl"] for r in rows])
        half[lab] = s_tr
        k2, p2 = pooled_series(h, rows)
        P(f"  {lab} per-trade {fmt(s_tr)}")
        P(f"  {lab} pooled    {fmt(stats(p2))}")
        for u in ("BTC", "ETH"):
            P(f"  {lab} {u:5s}     {fmt(stats([r['st'][h]['pnl'] for r in rows if r['underlying'] == u]))}")

    P("\n== 2025-10-10 weeks on their own (haircut 0.05)")
    for tgt in ("2025-10-10", "2025-10-17"):
        for r in ok:
            if d(r["expiry"]) == tgt:
                s = r["st"][h]
                P(f"  expiry {tgt} {r['underlying']}: entry {d(r['entry'])} S0 {r['s0']:.2f} K {r['K']:.0f} S_T {r['settle']:.2f} move {(r['settle'] / r['s0'] - 1) * 1e4:+.0f} bps credit {s['credit']:.1f} payout {s['intr']:.1f} fees {s['fees']:.1f} pnl {s['pnl']:+.1f}")
        k2, p2 = pooled_series(h)
        for k, p in zip(k2, p2):
            if d(k) == tgt:
                P(f"  expiry {tgt} POOLED pnl {p:+.1f}")
    # worst weeks
    P("\n== Five worst pooled weeks (haircut 0.05)")
    for k, p in sorted(zip(ks, ps), key=lambda z: z[1])[:5]:
        P(f"  {d(k)} {p:+.1f}")

    # template: per-trade bootstrap clustered by week
    trades = [(r["expiry"], r["st"][h]["pnl"]) for r in ok]
    wk = sorted({t for t, _ in trades})
    wi = {t: i for i, t in enumerate(wk)}
    sums = np.zeros(len(wk)); cnts = np.zeros(len(wk))
    for t, p in trades:
        sums[wi[t]] += p; cnts[wi[t]] += 1
    rng = np.random.default_rng(11)
    idx = rng.integers(0, len(wk), size=(2000, len(wk)))
    boot = sums[idx].sum(1) / cnts[idx].sum(1)
    p_one = float((boot <= 0).mean())
    tr_mean = float(sums.sum() / cnts.sum())
    P(f"\n== Template metrics (haircut {h})")
    P(f"  per-trade mean {tr_mean:+.2f} bps over {int(cnts.sum())} trades in {len(wk)} week clusters; bootstrap 2000 draws rng(11): "
      f"P(mean<=0) = {p_one:.4f}; 95% interval {np.percentile(boot, 2.5):+.1f} .. {np.percentile(boot, 97.5):+.1f}")
    span_years = (max(r["expiry"] for r in ok) - min(r["entry"] for r in ok)) / (365.25 * DAY)
    for u in ("BTC", "ETH"):
        P(f"  trades/year {u}: {len(by_coin[u]) / span_years:.1f} straddles ({2 * len(by_coin[u]) / span_years:.1f} option legs opened)")

    # daily MTM P&L
    daily = defaultdict(dict)  # day_end_ts -> {coin: pnl_bps}
    carry_used = 0
    for r in ok:
        s = r["st"][h]
        S0 = r["s0"]
        L_prev = r["mc"] + r["mp"]
        L_prev_c, L_prev_p = r["mc"], r["mp"]
        val = s["price"] - s["fo"]  # cash received net of opening fees
        pnl_days = []
        for k, dm in enumerate(r["daily"], start=1):
            mc = dm["mc"] if dm["mc"] is not None else L_prev_c
            mp = dm["mp"] if dm["mp"] is not None else L_prev_p
            carry_used += (dm["mc"] is None) + (dm["mp"] is None)
            L = mc + mp
            pnl_days.append(((val - L) if k == 1 else (L_prev - L)) / S0 * 1e4)
            L_prev, L_prev_c, L_prev_p = L, mc, mp
        pnl_days.append((L_prev - s["intr_px"] - s["fs"]) / S0 * 1e4)
        assert abs(sum(pnl_days) - s["pnl"]) < 1e-6, (sum(pnl_days), s["pnl"])
        for k, p in enumerate(pnl_days, start=1):
            daily[r["entry"] + k * DAY][r["underlying"]] = p
    days = sorted(daily)
    for u in ("BTC", "ETH"):
        x = np.array([daily[t].get(u, 0.0) for t in days])
        P(f"  daily MTM Sharpe {u}: {x.mean() / x.std(ddof=1) * math.sqrt(365):+.2f} (n days {len(x)}, flat days count as 0)")
    xp = np.array([np.mean(list(daily[t].values())) for t in days])
    P(f"  daily MTM Sharpe POOLED: {xp.mean() / xp.std(ddof=1) * math.sqrt(365):+.2f} (n days {len(xp)}); worst day {xp.min():+.1f} bps; daily marks carried forward {carry_used}")
    sp = res[("POOL", h)]
    P(f"  weekly Sharpe POOLED (x sqrt 52, info): {sp['mean'] / sp['sd'] * math.sqrt(52):+.2f}")

    P("\n== Labelled neighbour (not selectable): strangle at S0 +/- (ATM credit@0)/2, haircut 0.05")
    for u in ("BTC", "ETH"):
        x = [z for r in by_coin[u] if (z := strangle(r, h))]
        P(f"  {u:6s} {fmt(stats([z['pnl'] for z in x]))} credit {np.mean([z['credit'] for z in x]):.1f}")
    k2, p2 = pooled_series(h, ok, lambda r, h: (strangle(r, h) or {}).get("pnl"))
    P(f"  POOLED {fmt(stats(p2))}")

    # ---------------- pass rule
    P("\n== Pass rule (haircut 0.05)")
    c = {}
    c["1 mean>0 BTC"] = res[("BTC", h)]["mean"] > 0
    c["1 mean>0 ETH"] = res[("ETH", h)]["mean"] > 0
    c["2 pooled t>=2.0"] = res[("POOL", h)]["t"] >= 2.0
    for u in ("BTC", "ETH"):
        for lab in ("A", "B"):
            c5, mv = vrp[(u, lab)]
            c[f"3 credit>move {u} {lab}"] = c5 > mv
    pos_years = sum(1 for y in (2024, 2025, 2026) if years[y].get("n") and years[y]["total"] > 0)
    c["4 positive in >=2 of 2024/25/26"] = pos_years >= 2
    pm, pw = res[("POOL", h)]["mean"], res[("POOL", h)]["worst"]
    c["5 pooled mean>0 and |worst|<=52*mean"] = pm > 0 and abs(min(pw, 0.0)) <= 52 * pm
    c["6 per-trade mean>0, bootstrap P<=0.01"] = tr_mean > 0 and p_one <= 0.01
    c["7 per-trade mean>0 in A and B"] = half["A"]["mean"] > 0 and half["B"]["mean"] > 0
    c["8 positive on 2 of 2 coins"] = res[("BTC", h)]["mean"] > 0 and res[("ETH", h)]["mean"] > 0
    for k, v in c.items():
        P(f"  {'PASS' if v else 'FAIL'}  {k}")
    P(f"  detail: pooled mean {pm:+.2f}, t {res[('POOL', h)]['t']:+.2f}, worst {pw:+.0f} (52 x mean = {52 * pm:+.0f}); positive years {pos_years}/3; P {p_one:.4f}")
    verdict = all(c.values())
    P(f"\n  IN-SAMPLE: {'PASS' if verdict else 'FAIL'} ({sum(c.values())}/{len(c)} clauses)")
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(DIR, "out", "results.txt"), "w").write(txt + "\n")
    json.dump({"pass": bool(verdict), "clauses": {k: bool(v) for k, v in c.items()}, "pooled": res[("POOL", h)], "btc": res[("BTC", h)], "eth": res[("ETH", h)],
               "bootstrap_p": p_one, "per_trade_mean": tr_mean}, open(os.path.join(DIR, "out", "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
