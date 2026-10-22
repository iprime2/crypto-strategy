#!/usr/bin/env python3
"""Plan-literal A6 Delta-funding stress line (phase1_plan.md amendment A6), run after the review of PR 58 found the harness
implemented a different floor. Plan text: "per-coin-day funding = max(Binance, 0.01 %/8 h x 3) for BTC, ETH, BNB, LTC, BCH and
Binance x the 2025-26 Delta/Binance mean ratio for the other coins (from research2/funding_summary.json)".
Interpretation (fixed before running, recorded in notes.md):
  - majors: F' = max(F_binance, 0.0003 per day) on days with a close;
  - XRP, ADA, LINK, DOGE: r_c = Delta mean daily funding ('<c>USD|all' ann / 100 / 365) / Binance mean daily funding of the same coin
    over 2025-01-01..2026-09-30 (the panel's last date); F' = F_binance x r_c;
  - coins with no Delta record (the 16 other ex-ante perps, GOLD): pooled r = sum of the four Delta means / sum of their Binance means;
  - literal line as above; a stress-only reading clips every ratio at >= 1 (never milder than Binance), reported next to it.
Reports, for the baseline and the three cells A6 gates (SIG-3a, SIG-10, UNI-2): POST Sharpe on Binance funding, on the as-run harness
stress, on the plan-literal stress and on the stress-only reading; and the condition-2 check (stress A POST var - base >= -0.03).
Writes only into this folder."""
import datetime as dt, glob, importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools2")
sys.path.insert(0, TOOLS)
import numpy as np
import data, sim, harness
from registry import VARIANTS
import variants  # noqa: F401
for f in sorted(glob.glob(os.path.join(TOOLS, "variants_*.py"))):
    importlib.import_module(os.path.basename(f)[:-3])

fs = json.load(open(f"{data.SP}/research2/funding_summary.json"))
R0, R1 = dt.date(2025, 1, 1), dt.date(2026, 9, 30)
NONMAJ = ["XRP", "ADA", "LINK", "DOGE"]
P25 = data.load_binance()
d = np.array(P25.dates); m = (d >= R0) & (d <= R1)
bmean = {c: float(np.nanmean(P25.F[m, P25.coins.index(c)])) for c in data.NINE}
dmean = {c: float(fs[f"{c}USD|all"]["ann"]) / 100 / 365 for c in data.NINE}
ratio = {c: dmean[c] / bmean[c] for c in NONMAJ}
pooled = sum(dmean[c] for c in NONMAJ) / sum(bmean[c] for c in NONMAJ)
info = dict(binance_ann_pct={c: round(bmean[c] * 365 * 100, 2) for c in data.NINE}, delta_ann_pct={c: round(dmean[c] * 365 * 100, 2) for c in data.NINE},
            ratio={c: round(v, 3) for c, v in ratio.items()}, pooled_ratio=round(pooled, 3))


def stress_plan(p, clip):
    F = p.F.copy()
    for j, c in enumerate(p.coins):
        ok = np.isfinite(p.C[:, j])
        if c in harness.CAPPED_MAJORS:
            F[:, j] = np.where(ok, np.maximum(F[:, j], 0.0003), 0.0)
        else:
            r = ratio.get(c, pooled)
            if clip:
                r = max(r, 1.0)
            F[:, j] = np.where(ok, F[:, j] * r, 0.0)
    return data.Panel(p.dates, p.coins, p.O, p.H, p.L, p.C, p.V, F, p.Q)


def line(name, ds, cname):
    p, a, b = harness.panels()[ds]
    cad = harness.CADS[cname]
    fn = VARIANTS[name]; base_fn = VARIANTS["baseline"]
    bc = fn(p, cad)[1].get("base_coins"); pb = p.sub(bc) if bc else p
    out = {}
    for tag, mk in (("binance", None), ("as_run", lambda q: harness.delta_funding_stress(q)[0]),
                    ("plan", lambda q: stress_plan(q, False)), ("plan_clip1", lambda q: stress_plan(q, True))):
        q = mk(p) if mk else None; qb = mk(pb) if mk else None
        rv = harness.run(p, fn, cad, a, b, funding_panel=q); rb = harness.run(pb, base_fn, cad, a, b, funding_panel=qb)
        sv, sb = sim.stats(rv, harness.POST), sim.stats(rb, harness.POST)
        out[tag] = dict(var=round(sv["sharpe"], 4), base=round(sb["sharpe"], 4), delta=round(sv["sharpe"] - sb["sharpe"], 4),
                        var_fund=round(sv["funding_yr"], 4), base_fund=round(sb["funding_yr"], 4), var_cagr=round(sv["cagr"], 4), base_cagr=round(sb["cagr"], 4))
    return out


res = {"info": info}
for name, pans in (("baseline", ("A", "B")), ("SIG-3a", ("A", "B")), ("SIG-10", ("A", "B")), ("UNI-2", ("A10", "B25G"))):
    for ds in pans:
        for cname in ("daily", "weekly"):
            res[f"{name}|{ds}-{cname}"] = line(name, ds, cname)
            print(name, ds, cname, json.dumps(res[f"{name}|{ds}-{cname}"]), flush=True)
json.dump(res, open(os.path.join(HERE, "plan_a6.json"), "w"), indent=1)
print(json.dumps(info, indent=1))
