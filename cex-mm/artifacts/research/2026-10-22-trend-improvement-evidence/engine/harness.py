#!/usr/bin/env python3
"""Phase-2 harness (supersedes evaluate.py for the pre-registered runs; evaluate.py stays as the smoke-run provenance).

A cell = a variant id registered in registry.VARIANTS (via variants*.py) with fn(panel, cad) -> (W, extra). The harness runs it on the
panels and cadences the plan names, unrounded and at the capitals requested, and writes phase2/<id>.json + a summary line with the
class verdict inputs. See research2/phase1_plan.md sections 2-5 and amendment A-2026-10-21.

CLI: python3 harness.py <id> [<id> ...] [--panels A,B,C] [--cadences daily,weekly] [--capitals 1000,2500,5000] [--vs baseline|W]
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import data, sim, rules
from registry import VARIANTS

OUT = f"{data.SP}/research2/phase2"
A0, A1 = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
C0, C1 = dt.date(2024, 8, 10), dt.date(2026, 10, 12)
POST = dt.date(2022, 1, 1)
H1 = (dt.date(2020, 5, 1), dt.date(2023, 12, 31)); H2 = (dt.date(2024, 1, 1), dt.date(2026, 9, 30)); CH2 = (dt.date(2025, 1, 1), C1)
DAILY = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)
WEEKLY = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)
TRANCHE = dict(name="tranche", tv=0.25, max_gross=1.0, band=0.10, weekly=False)  # daily-executed TV 0.25 book (TIME-1's target T)
CADS = {"daily": DAILY, "weekly": WEEKLY, "tranche": TRANCHE}
N_PRIMARY, N_EFF = 26, 90
MULT_N = sim.expected_max_sharpe(N_PRIMARY, 1.0); MULT_EFF = sim.expected_max_sharpe(N_EFF, 1.0)
CAPPED_MAJORS = {"BTC", "ETH", "BNB", "LTC", "BCH"}


def baseline(p, cad):
    return rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"]), {}


VARIANTS.setdefault("baseline", baseline)

_panels = {}


def panels():
    """A, B (24 ex-ante), B25 (with DOGE), C (Delta), A10 (nine + gold), B25G (25 + gold), Bw (survivorship-free pool)."""
    if not _panels:
        P25 = data.load_binance()
        _panels["A"] = (P25.sub(data.NINE), A0, A1)
        _panels["B"] = (P25.sub(data.EXANTE24), A0, A1)
        _panels["B25"] = (P25, A0, A1)
        _panels["C"] = (data.load_delta().sub(data.NINE), C0, C1)
        G = data.load_binance(coins=data.ALL25 + ["GOLD"])
        _panels["A10"] = (G.sub(data.NINE + ["GOLD"]), A0, A1)
        _panels["B25G"] = (G, A0, A1)
    return _panels


def panel_bw():
    pool = json.load(open(f"{data.SP}/universe/pool_all.json"))
    return data.load_binance(coins=pool), A0, A1


def delta_funding_stress(p):
    """A6: per-coin-day funding = max(Binance archive, Delta's 2025-26 mean daily fraction) for the nine (research2/funding_summary.json
    '<sym>|all' -> 'ann' = annualized % paid by longs); other coins keep the Binance archive. Returns (panel, info)."""
    try:
        fs = json.load(open(f"{data.SP}/research2/funding_summary.json"))
    except FileNotFoundError:
        fs = {}
    F = p.F.copy(); info = {}
    for j, c in enumerate(p.coins):
        rec = fs.get(f"{c}USD|all") or fs.get(f"{c}USD|2025")
        if rec and "ann" in rec:
            floor = float(rec["ann"]) / 100.0 / 365.0
            F[:, j] = np.where(np.isfinite(p.C[:, j]), np.maximum(F[:, j], floor), 0.0)
            info[c] = round(float(rec["ann"]), 2)
    q = data.Panel(p.dates, p.coins, p.O, p.H, p.L, p.C, p.V, F, p.Q)
    return q, info


def run(p, fn, cad, start, end, capital=None, funding_panel=None):
    """extra kwargs: tranches/weekdays (weekly only), buffer, band override, 'W_override' is not allowed."""
    W, extra = fn(p, cad)
    extra = dict(extra)
    K = extra.pop("tranches", 1); wds = extra.pop("weekdays", None)
    extra.pop("base_coins", None); custom = extra.pop("custom_sim", None)
    kw = dict(decide=rules.decide_weekly(p.dates, 6) if cad["weekly"] else None, band=cad["band"], start=start, end=end, capital=capital)
    kw.update(extra)
    pp = funding_panel or p
    if custom is not None:  # a variant with its own trade logic (e.g. TIME-4 half-gap sessions, SZ-13 eligibility): custom(panel, W, kwargs) -> result
        return custom(pp, W, kw)
    if not cad["weekly"] or (K == 1 and wds is None):
        return sim.simulate(pp, W, **kw)
    wds = wds or [(6 - k * (7 // K)) % 7 for k in range(K)]
    runs = [sim.simulate(pp, W, **{**kw, "decide": rules.decide_weekly(p.dates, wd)}) for wd in wds]
    out = dict(runs[0])
    for key in ("rets", "gross", "traded", "coin_pnl", "realized_gain", "realized_loss"):
        if key in runs[0]:
            out[key] = np.mean([r[key] for r in runs], axis=0)
    for key in ("fees", "funding", "trades", "orders"):
        out[key] = float(np.mean([r[key] for r in runs]))
    out["final"] = float(np.prod(1 + out["rets"]))
    return out


def windows(ds):
    if ds == "C":
        return {"full": (None, None), "post": (None, None), "h1": (None, None), "h2": CH2}
    return {"full": (None, None), "post": (POST, None), "h1": H1, "h2": H2}


def after_tax(res, a=None, b=None):
    """A1: (a) per-coin realized-segment VDA, (b) per-coin-day VDA, (c) slab 30 % on net; returns CAGR under each, over the window."""
    d = np.array(res["dates"]); m = np.ones(len(d), bool)
    if a: m &= d >= a
    if b: m &= d <= b
    yrs = np.array([x.year for x in d[m]])
    out = {}
    net = res["rets"][m]
    cp = res["coin_pnl"][m]  # (T, N) fractions of equity per coin-day (price pnl net of funding), costs excluded
    costs = res["cost_frac"][m]
    seg_g, seg_l = res["realized_gain"][m], res["realized_loss"][m]
    def cagr_from_yearly(y):
        tot = np.prod([1 + v for v in y.values()]); n = len(net)
        return float(tot ** (365 / max(n, 1)) - 1)
    for key in ("segment", "coinday", "slab"):
        yearly = {}
        for y in sorted(set(yrs)):
            k = yrs == y
            pre = float(np.prod(1 + net[k]) - 1)
            if key == "slab":
                tax = 0.30 * max(pre, 0.0)
            elif key == "coinday":
                tax = 0.30 * float(np.where(cp[k] > 0, cp[k], 0.0).sum())
            else:
                tax = 0.30 * float(seg_g[k].sum())
            yearly[int(y)] = pre - tax
        out[key] = dict(cagr=cagr_from_yearly(yearly), yearly=yearly)
    return out


def intraday_lows(p, res, hourly_lows):
    """A5: worst intraday equity using positions x hourly lows; hourly_lows[c] = {datetime: low}. Returns dict."""
    # positions are implied by W at each date: the simulator returns units history only indirectly; we rebuild from gross and weights
    return {}


def cell(name, fn, cads, capitals, panels_sel, vs="baseline"):
    rows = {}
    base_fn = VARIANTS["baseline"]
    for ds in panels_sel:
        p, a, b = panels()[ds] if ds != "Bw" else panel_bw()
        for cname in cads:
            cad = CADS[cname]
            base_cad = WEEKLY if (vs == "W") else cad
            key = f"{ds}-{cname}"
            r = run(p, fn, cad, a, b)
            bc = fn(p, cad)[1].get("base_coins")
            pb = p.sub(bc) if bc else p
            base = run(pb, base_fn, base_cad, a, b)
            rec = {"vs": vs, "base_cadence": base_cad["name"]}
            for wname, (wa, wb) in windows(ds).items():
                s = sim.stats(r, wa, wb); bs = sim.stats(base, wa, wb)
                d = np.array(r["dates"]); m = np.ones(len(d), bool)
                if wa: m &= d >= wa
                if wb: m &= d <= wb
                boot = sim.block_bootstrap_diff(r["rets"][m], base["rets"][m]) if m.sum() > 60 else (0.0, 0.0, 0.0, 1.0)
                rec[wname] = dict(var=s, base=bs, delta=boot[0], ci=[boot[1], boot[2]], p_le0=boot[3],
                                  sd_delta=float((boot[2] - boot[1]) / 3.92) if boot[2] > boot[1] else 0.0,
                                  tax=after_tax(r, wa, wb), base_tax=after_tax(base, wa, wb))
            # matched-vol re-run when realized vol differs by > 5 %
            vv, vb = rec["full"]["var"]["vol"], rec["full"]["base"]["vol"]
            if vb > 0 and abs(vv / vb - 1) > 0.05:
                cad_m = dict(cad); cad_m["tv"] = cad["tv"] * vb / max(vv, 1e-9)
                rm = run(p, fn, cad_m, a, b)
                sm = sim.stats(rm); rec["matched_vol"] = dict(tv=cad_m["tv"], sharpe=sm["sharpe"], mdd=sm["mdd"], worst7=sm["worst7"], vol=sm["vol"])
            # Delta-funding stress line (A6) on A and B panels
            if ds in ("A", "B", "B25", "A10", "B25G"):
                q, ratio = delta_funding_stress(p)
                qb, _ = delta_funding_stress(pb)
                rs = run(p, fn, cad, a, b, funding_panel=q); bsr = run(pb, base_fn, base_cad, a, b, funding_panel=qb)
                ss, sb = sim.stats(rs, POST), sim.stats(bsr, POST)
                rec["delta_funding_stress"] = dict(delta_ann_pct=ratio, sharpe_post=ss["sharpe"], base_sharpe_post=sb["sharpe"], funding_yr=rs["funding"] / max(len(rs["rets"]) / 365, 1e-9),
                                                   base_funding_yr=bsr["funding"] / max(len(bsr["rets"]) / 365, 1e-9), cagr_post=ss["cagr"], base_cagr_post=sb["cagr"])
            # whole-contract lines
            if capitals and ds in ("A", "C", "A10"):
                rec["capital"] = {}
                for cap in capitals:
                    rc = run(p, fn, cad, a, b, capital=cap); bc = run(pb, base_fn, base_cad, a, b, capital=cap)
                    sc, sbc = sim.stats(rc), sim.stats(bc)
                    boot = sim.block_bootstrap_diff(rc["rets"], bc["rets"])
                    rec["capital"][str(cap)] = dict(var=sc, base=sbc, delta=boot[0], ci=[boot[1], boot[2]], orders_yr=rc["orders"] / (len(rc["rets"]) / 365),
                                                   base_orders_yr=bc["orders"] / (len(bc["rets"]) / 365), fees_yr=rc["fees"] / (len(rc["rets"]) / 365), base_fees_yr=bc["fees"] / (len(bc["rets"]) / 365),
                                                   funding_yr=rc["funding"] / (len(rc["rets"]) / 365), base_funding_yr=bc["funding"] / (len(bc["rets"]) / 365))
            rows[key] = rec
    return rows


def summary_line(name, rows, cad):
    B = rows.get(f"B-{cad}") or rows.get(f"B25-{cad}") or rows.get(f"B25G-{cad}")
    A = rows.get(f"A-{cad}") or rows.get(f"A10-{cad}"); C = rows.get(f"C-{cad}")
    if not B:
        return f"{name:16s} {cad:7s} | (no B panel)"
    d = B["post"]["delta"]; sd = B["post"]["sd_delta"]; lo, hi = B["post"]["ci"]
    parts = [f"{name:16s} {cad:7s} | B post Δ {d:+.3f} [{lo:+.2f},{hi:+.2f}] P≤0 {B['post']['p_le0']:.2f} sd {sd:.3f} hurdle {max(0.05, MULT_EFF * sd):.3f}",
             f"B full {B['full']['var']['sharpe']:.2f} vs {B['full']['base']['sharpe']:.2f} DD {B['full']['var']['mdd']:.1%}/{B['full']['base']['mdd']:.1%}",
             f"h1 {B['h1']['delta']:+.2f} h2 {B['h2']['delta']:+.2f}"]
    if A:
        parts.append(f"A post {A['post']['delta']:+.2f} full {A['full']['delta']:+.2f}")
    if C:
        parts.append(f"C {C['full']['delta']:+.2f}")
    parts.append(f"turn {B['full']['var']['turnover']:.1f}x fund {B['full']['var'].get('funding_yr', 0):.2%} tax(seg) {B['full']['tax']['segment']['cagr']:+.1%} vs {B['full']['base_tax']['segment']['cagr']:+.1%}")
    return " | ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+"); ap.add_argument("--panels", default="A,B,C"); ap.add_argument("--cadences", default="daily,weekly")
    ap.add_argument("--capitals", default=""); ap.add_argument("--vs", default="baseline"); ap.add_argument("--tag", default="")
    args = ap.parse_args()
    import glob, importlib
    import variants  # noqa: F401
    for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "variants_*.py"))):
        importlib.import_module(os.path.basename(f)[:-3])
    os.makedirs(OUT, exist_ok=True)
    caps = [float(x) for x in args.capitals.split(",") if x]
    cads = args.cadences.split(","); pans = args.panels.split(",")
    for vid in args.ids:
        t0 = time.time()
        rows = cell(vid, VARIANTS[vid], cads, caps, pans, vs=args.vs)
        json.dump(rows, open(f"{OUT}/{vid}{args.tag}.json", "w"), default=float)
        with open(f"{OUT}/summary.md", "a") as f:
            for cad in cads:
                f.write(summary_line(vid + args.tag, rows, cad) + "\n")
        for cad in cads:
            print(summary_line(vid + args.tag, rows, cad))
        print(f"  [{vid}{args.tag}: {time.time() - t0:.0f}s]", file=sys.stderr)


if __name__ == "__main__":
    main()
