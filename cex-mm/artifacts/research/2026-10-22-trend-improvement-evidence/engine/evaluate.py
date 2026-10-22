#!/usr/bin/env python3
"""Evaluation harness for phase 2: every variant is a function panel -> (W, kwargs for simulate) registered in VARIANTS.

Protocol (fixed before any variant is run, see research2/phase1_plan.md):
  datasets  A = Binance 9 coins 2020-05-01..2026-09-30; B = Binance 24 ex-ante perps (listed by 2020-02-20), same window;
            C = Delta India 9 coins 2024-08-10..2026-10-12 (close only: OHLC-based variants fall back to close-to-close there)
  cadences  daily (TV 0.40, gross cap 2x) and weekly (Sunday candle = Monday 00:00 UTC decision, TV 0.25, band 10%, cap 1x)
  primary   Sharpe on B, daily and weekly, 2022-01-01..2026-09-30, versus the baseline on the same days
  secondary full-sample Sharpe, maxDD, worst year, turnover, fees; halves 2020-05..2023-12 and 2024-01..2026-09; A and C
  test      paired block bootstrap (20-day blocks, 1000 draws) of Sharpe(variant) - Sharpe(baseline) on B 2022-26;
            Bailey-Lopez de Prado expected max null Sharpe for the number of variants run, reported next to the gains.
Usage: python3 evaluate.py [variant ...]   (no args = all); writes research2/phase2/<variant>.json and a summary table.
"""
from __future__ import annotations
import datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import data, sim, rules
from registry import VARIANTS, variant

OUT = f"{data.SP}/research2/phase2"
A0, A1 = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
C0, C1 = dt.date(2024, 8, 10), dt.date(2026, 10, 12)
POST = dt.date(2022, 1, 1)
H1 = (dt.date(2020, 5, 1), dt.date(2023, 12, 31)); H2 = (dt.date(2024, 1, 1), dt.date(2026, 9, 30))

DAILY = dict(tv=0.40, max_gross=2.0, band=0.0, weekly=False)
WEEKLY = dict(tv=0.25, max_gross=1.0, band=0.10, weekly=True)


def baseline(p, cad):
    return rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"]), {}


VARIANTS["baseline"] = baseline


def run(p, fn, cad, start, end, capital=None):
    """extra may carry simulate kwargs, plus 'tranches': K (weekly cadence only) to split the book into K equal tranches
    rebalanced on K different weekdays (Hoffstein tranching); their daily returns are averaged (continuous rebalancing
    between tranches, which is the limit the literature models). 'weekdays' lists the decision weekdays explicitly."""
    W, extra = fn(p, cad)
    extra = dict(extra)
    K = extra.pop("tranches", 1); wds = extra.pop("weekdays", None)
    kw = dict(decide=rules.decide_weekly(p.dates, 6) if cad["weekly"] else None, band=cad["band"], start=start, end=end, capital=capital)
    kw.update(extra)
    if not cad["weekly"] or (K == 1 and wds is None):
        return sim.simulate(p, W, **kw)
    wds = wds or [(6 - k * (7 // K)) % 7 for k in range(K)]
    runs = [sim.simulate(p, W, **{**kw, "decide": rules.decide_weekly(p.dates, wd)}) for wd in wds]
    out = dict(runs[0])
    for key in ("rets", "gross", "traded"):
        out[key] = np.mean([r[key] for r in runs], axis=0)
    out["fees"] = float(np.mean([r["fees"] for r in runs])); out["funding"] = float(np.mean([r["funding"] for r in runs]))
    out["trades"] = int(np.mean([r["trades"] for r in runs])); out["final"] = float(np.prod(1 + out["rets"]))
    return out


_panels = {}


def panels():
    if not _panels:
        P = data.load_binance()
        _panels["A"] = (P.sub(data.NINE), A0, A1)
        _panels["B"] = (P.sub(data.EXANTE24), A0, A1)
        _panels["C"] = (data.load_delta().sub(data.NINE), C0, C1)
    return _panels


def evaluate(name, fn, base_cache):
    rows = {}
    for ds, (p, a, b) in panels().items():
        for cname, cad in (("daily", DAILY), ("weekly", WEEKLY)):
            key = f"{ds}-{cname}"
            r = run(p, fn, cad, a, b)
            base = base_cache[key]
            s = sim.stats(r); sp = sim.stats(r, POST); s1 = sim.stats(r, *H1); s2 = sim.stats(r, *H2)
            bs = sim.stats(base); bp = sim.stats(base, POST)
            rec = dict(full=s, post=sp, h1=s1, h2=s2, base_full_sharpe=bs["sharpe"], base_post_sharpe=bp["sharpe"], base_full_mdd=bs["mdd"])
            if ds != "C":
                d = np.array(r["dates"]); m = d >= POST
                rec["boot_post"] = sim.block_bootstrap_diff(r["rets"][m], base["rets"][m])
                rec["boot_full"] = sim.block_bootstrap_diff(r["rets"], base["rets"])
            else:
                rec["boot_post"] = sim.block_bootstrap_diff(r["rets"], base["rets"])
                rec["boot_full"] = rec["boot_post"]
            rows[key] = rec
    return rows


def table(results):
    """One line per variant per cadence with the decision inputs."""
    out = []
    hdr = f"{'variant':34s} {'cad':6s} | {'B post':>7s} {'Δ':>6s} {'[95% CI]':>15s} | {'B full':>7s} {'DD':>7s} | {'A post':>7s} {'A full':>7s} | {'C':>6s} | {'h1':>6s} {'h2':>6s} | {'turn':>5s}"
    out.append(hdr); out.append("-" * len(hdr))
    for name, rows in results.items():
        for cname in ("daily", "weekly"):
            B = rows[f"B-{cname}"]; A = rows[f"A-{cname}"]; C = rows[f"C-{cname}"]
            d, lo, hi, _ = B["boot_post"]
            out.append(f"{name:34s} {cname:6s} | {B['post']['sharpe']:7.2f} {d:+6.2f} [{lo:+5.2f},{hi:+5.2f}] | {B['full']['sharpe']:7.2f} {B['full']['mdd']:7.1%} | "
                       f"{A['post']['sharpe']:7.2f} {A['full']['sharpe']:7.2f} | {C['full']['sharpe']:6.2f} | {B['h1']['sharpe']:6.2f} {B['h2']['sharpe']:6.2f} | {B['full']['turnover']:5.1f}")
    n = len([k for k in results if k != "baseline"])
    out.append(f"trials so far: {n}; E[max null Sharpe gain] for {n} trials at sd 0.10/0.15: "
               f"{sim.expected_max_sharpe(n, 0.10):+.2f}/{sim.expected_max_sharpe(n, 0.15):+.2f}")
    return "\n".join(out)


def main(names):
    os.makedirs(OUT, exist_ok=True)
    import variants  # noqa: F401  registers the plan's variants
    names = names or list(VARIANTS)
    base_cache = {}
    for ds, (p, a, b) in panels().items():
        for cname, cad in (("daily", DAILY), ("weekly", WEEKLY)):
            base_cache[f"{ds}-{cname}"] = run(p, baseline, cad, a, b)
    results = {}
    for n in names:
        t0 = time.time()
        results[n] = evaluate(n, VARIANTS[n], base_cache)
        json.dump(results[n], open(f"{OUT}/{n}.json", "w"), default=str)
        print(f"{n}: {time.time() - t0:.1f}s", file=sys.stderr)
    print(table(results))
    return results


if __name__ == "__main__":
    main(sys.argv[1:])
