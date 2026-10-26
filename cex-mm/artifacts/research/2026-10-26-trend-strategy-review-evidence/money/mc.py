#!/usr/bin/env python3
"""Monte Carlo of the trend books' dollar outcomes for the owner.

Forward assumptions come from resource/07-trend-rule-and-prop-trading-research.md:
  weekly book (TV 0.25): Sharpe 0.3 / 0.5 / 0.8 at ~12% realised vol  (+4..+9%/yr, max DD 15-25%)
  daily book  (TV 0.40): same Sharpe grid at ~19% realised vol (T1: the daily rule at TV 0.40 ran 18.7% vol;
                         the 2026-10-08 memo shows TV scales return and drawdown, not Sharpe)
Daily returns are Student-t with 4 degrees of freedom, scaled to the target vol, 365 trading days a year,
Sharpe = annualised arithmetic mean / annualised sd. 10,000 paths, 5 years, common random numbers across cells.
Tax readings (resource/07 T6b, 30% VDA on gross gains with no set-off; resource/08 "slab 30% on net"):
  gross gains per year are NOT modelled trade by trade. They are a linear fit of T6b's six full years
  (2020-2025) of gross gains against the year's net return, per segment and per coin-day; intercepts scale
  with the book's vol (19/12.4 for the daily book). Slab tax: 30% of positive net, losses carried forward.
Everything here is [SYNTHETIC]: a model of the memos' assumptions, not a forecast.
"""
import os, sys, json, math
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 20261026
NPATH, YEARS, DPY, NU = 10000, 5, 365, 4
CHUNK = 2000
CAPITALS = [1_000, 5_000, 25_000, 100_000]
HORIZONS = [1, 3, 5]
PAUSE_DDS = (0.20, 0.30)   # the memo's -20% pause (set for a 12% vol book) and its vol-equivalent for a 19% vol book

# resource/07 T6b, design line (weekly TV 0.25, ~12.4% vol), full years only, all in % of start-of-year equity
T6B = {  # year: (pre-tax net, seg gains, seg losses, coinday gains, coinday losses)
    2020: (26.9, 42.4, -15.5, 95.1, -68.2),   # May-Dec; treated as a year (conservative: gross understated)
    2021: (30.6, 57.7, -27.1, 127.2, -96.6),
    2022: (-6.8, 3.6, -10.4, 17.4, -24.1),
    2023: (13.8, 28.8, -15.0, 86.0, -72.2),
    2024: (22.4, 43.4, -21.0, 99.9, -77.5),
    2025: (2.8, 18.3, -15.5, 60.4, -57.7),
}
T6B_VOL = 12.4  # % vol of the design line (resource/07 T1)

def fit_gross():
    x = np.array([v[0] for v in T6B.values()])
    out = {}
    for name, idx in (("segment", 1), ("coinday", 3)):
        g = np.array([v[idx] for v in T6B.values()])
        b, a = np.polyfit(x, g, 1)
        resid = g - (a + b * x)
        out[name] = dict(a=float(a), b=float(b), rmse=float(np.sqrt(np.mean(resid ** 2))),
                         fitted=[(int(y), float(gi), float(a + b * xi)) for y, xi, gi in zip(T6B, x, g)])
    return out

GROSS = fit_gross()

def gross_gain(R, reading, vol):
    """Gross gains (fraction of start equity) for a year with net return R (fraction), under a VDA reading."""
    p = GROSS[reading]
    a = p["a"] / 100 * (vol * 100 / T6B_VOL)   # intercept scales with the book's vol
    g = a + p["b"] * R
    return np.maximum(g, np.maximum(R, 0.0))   # gross gains can't be below the net gain, nor negative

def after_tax_paths(Ry, vol, reading):
    """Ry: (n, YEARS) yearly pre-tax returns. Returns (n, YEARS) after-tax equity (start 1), tax paid from equity."""
    n = Ry.shape[0]
    E = np.ones(n); cf = np.zeros(n); path = np.zeros_like(Ry)
    for y in range(Ry.shape[1]):
        R = Ry[:, y]
        if reading == "none":
            tax = np.zeros(n)
        elif reading == "slab_cf":           # 30% on positive net, losses carried forward (speculative business)
            taxable = R * E - cf
            tax = np.where(taxable > 0, 0.30 * taxable, 0.0)
            cf = np.where(taxable > 0, 0.0, -taxable)
        elif reading == "slab_nocf":         # 30% on positive net, no carry-forward (worst slab case)
            tax = 0.30 * np.maximum(R, 0) * E
        else:                                 # VDA 30% on gross gains, no set-off
            tax = 0.30 * gross_gain(R, reading, vol) * E
        E = np.maximum(E * (1 + R) - tax, 0.0)
        path[:, y] = E
    return path

def simulate(cells, npath=NPATH, years=YEARS, seed=SEED):
    """cells: dict name -> (sharpe, vol). Returns dict name -> summary arrays (per path)."""
    n = years * DPY
    res = {k: dict(Ry=[], mdd={h: [] for h in HORIZONS}, hit_w={t: [] for t in PAUSE_DDS}, hit_d={t: [] for t in PAUSE_DDS}, obs_sharpe={}, ret_h={}) for k in cells}
    for k in cells:
        for m in (91, 182, 365):
            res[k]["obs_sharpe"][m] = []; res[k]["ret_h"][m] = []
    rng = np.random.default_rng(seed)
    tscale = 1 / math.sqrt(NU / (NU - 2))
    done = 0
    while done < npath:
        m = min(CHUNK, npath - done)
        z = rng.standard_t(NU, size=(m, n)) * tscale     # unit-variance fat-tailed shocks, shared across cells
        for k, (S, vol) in cells.items():
            r = S * vol / DPY + vol / math.sqrt(DPY) * z
            r = np.maximum(r, -0.95)
            cum = np.cumprod(1 + r, axis=1)
            ye = cum[:, DPY - 1::DPY]                      # year-end equity
            prev = np.hstack([np.ones((m, 1)), ye[:, :-1]])
            res[k]["Ry"].append(ye / prev - 1)
            runmax = np.maximum.accumulate(cum, axis=1)
            dd = cum / runmax - 1
            for h in HORIZONS:
                res[k]["mdd"][h].append(dd[:, :h * DPY].min(axis=1))
            # first time the -20% pause fires: at Monday checks (every 7th day, peak also on those marks) and daily
            wk = cum[:, 6::7]
            ddw = wk / np.maximum.accumulate(wk, axis=1) - 1
            for thr in PAUSE_DDS:
                hitw = np.argmax(ddw <= -thr, axis=1).astype(float)
                hitw[~(ddw <= -thr).any(axis=1)] = np.nan
                res[k]["hit_w"][thr].append((hitw * 7 + 7) / DPY)
                hitd = np.argmax(dd <= -thr, axis=1).astype(float)
                hitd[~(dd <= -thr).any(axis=1)] = np.nan
                res[k]["hit_d"][thr].append((hitd + 1) / DPY)
            for mdays in (91, 182, 365):
                seg = r[:, :mdays]
                res[k]["obs_sharpe"][mdays].append(seg.mean(axis=1) / seg.std(axis=1, ddof=1) * math.sqrt(DPY))
                res[k]["ret_h"][mdays].append(cum[:, mdays - 1] - 1)
        done += m
    for k in res:
        res[k]["Ry"] = np.vstack(res[k]["Ry"])
        for h in HORIZONS:
            res[k]["mdd"][h] = np.concatenate(res[k]["mdd"][h])
        for thr in PAUSE_DDS:
            res[k]["hit_w"][thr] = np.concatenate(res[k]["hit_w"][thr]); res[k]["hit_d"][thr] = np.concatenate(res[k]["hit_d"][thr])
        for mdays in (91, 182, 365):
            res[k]["obs_sharpe"][mdays] = np.concatenate(res[k]["obs_sharpe"][mdays])
            res[k]["ret_h"][mdays] = np.concatenate(res[k]["ret_h"][mdays])
    return res

def pct(x, q): return float(np.percentile(x, q))
def money(x): return f"{x:+,.0f}" if abs(x) >= 100 else f"{x:+,.1f}"

def main():
    cells = {
        "weekly S0.0": (0.0, 0.12), "weekly S0.3": (0.3, 0.12), "weekly S0.5": (0.5, 0.12),
        "weekly S0.7": (0.7, 0.12), "weekly S0.8": (0.8, 0.12),
        "daily S0.3": (0.3, 0.19), "daily S0.5": (0.5, 0.19), "daily S0.8": (0.8, 0.19),
        "BTC S0.5 vol57": (0.5, 0.57),
    }
    res = simulate(cells)
    L = []
    P = L.append
    P("MONTE CARLO OF THE TREND BOOKS' DOLLAR OUTCOMES  [SYNTHETIC]")
    P(f"paths {NPATH}, years {YEARS}, {DPY} d/yr, Student-t {NU} df daily returns scaled to the vol, seed {SEED}, common random numbers across cells")
    P("Sharpe = annualised arithmetic mean / sd (so expected arithmetic return = Sharpe x vol; compounding takes ~vol^2/2 off the median)")
    P("Forward ranges from resource/07 (Sharpe 0.3-0.8 at ~12% vol for the weekly TV 0.25 book); daily TV 0.40 book at 19% vol (T1 18.7%)")
    P("")
    # ---- (1) outcomes
    P("=" * 110)
    P("(1) DOLLAR OUTCOMES BEFORE TAX, per horizon.  Expected $ = mean; p10 / p50 / p90 of the final $ gain.")
    P("=" * 110)
    for k in ["weekly S0.3", "weekly S0.5", "weekly S0.8", "daily S0.3", "daily S0.5", "daily S0.8", "BTC S0.5 vol57"]:
        S, vol = cells[k]; Ry = res[k]["Ry"]
        cumE = np.cumprod(1 + Ry, axis=1)
        P(f"--- {k}: Sharpe {S}, vol {vol:.0%}; expected arithmetic return {S*vol:+.1%}/yr; "
          f"median CAGR (5y) {np.median(cumE[:, -1]) ** (1/5) - 1:+.2%}; P(a given year < 0) {np.mean(Ry < 0):.0%} "
          f"(year 1 {np.mean(Ry[:, 0] < 0):.0%}); P(5-year total < 0) {np.mean(cumE[:, -1] < 1):.0%}")
        for h in HORIZONS:
            g = cumE[:, h - 1] - 1
            P(f"  {h}y gain as % of capital: mean {g.mean():+.1%}  p10 {pct(g,10):+.1%}  p50 {pct(g,50):+.1%}  p90 {pct(g,90):+.1%}"
              f"   | max DD over {h}y: p50 {pct(res[k]['mdd'][h],50):.1%}  p90 {pct(res[k]['mdd'][h],90):.1%}  p99 {pct(res[k]['mdd'][h],99):.1%}")
            row = []
            for C in CAPITALS:
                row.append(f"${C/1000:>3.0f}k: E {money(g.mean()*C):>8} p10 {money(pct(g,10)*C):>8} p50 {money(pct(g,50)*C):>8} p90 {money(pct(g,90)*C):>8}")
            P("      " + " | ".join(row[:2])); P("      " + " | ".join(row[2:]))
        for thr in PAUSE_DDS:
            hw, hd = res[k]["hit_w"][thr], res[k]["hit_d"][thr]
            tag = "kill #1 as written" if thr == 0.20 else "vol-equivalent level for a 19% vol book (1.13x its ~26% backtest DD)"
            P(f"  P(-{thr:.0%} pause fires within 1y / 2y / 3y / 5y): Monday checks {np.mean(hw<=1):.0%} / {np.mean(hw<=2):.0%} / {np.mean(hw<=3):.0%} / {np.mean(hw<=5):.0%}"
              f";  daily marks {np.mean(hd<=1):.0%} / {np.mean(hd<=2):.0%} / {np.mean(hd<=3):.0%} / {np.mean(hd<=5):.0%}   [{tag}]")
        P("")
    P("Validation against resource/07 T6g (weekly book, -20% at a Monday check): memo says fires within 2y on 11% of paths at Sharpe 0.7, 18% at 0.5, 45% at zero edge; within 3y 21-32% at 0.5-0.7")
    for k in ["weekly S0.0", "weekly S0.5", "weekly S0.7"]:
        hw = res[k]["hit_w"][0.20]
        P(f"  this MC {k}: within 2y {np.mean(hw<=2):.0%}, within 3y {np.mean(hw<=3):.0%}  (daily marks: {np.mean(res[k]['hit_d'][0.20]<=2):.0%} / {np.mean(res[k]['hit_d'][0.20]<=3):.0%})")
    P("  The MC draws i.i.d. t(4) days with no volatility clustering, so it understates drawdown frequency relative to the memo's bootstrap: read its pause probabilities as lower bounds.")
    P("")
    # ---- (2) tax
    P("=" * 110)
    P("(2) AFTER TAX. Gross gains per year from a linear fit of resource/07 T6b (six full years, design line):")
    for name in ("segment", "coinday"):
        p = GROSS[name]
        P(f"  {name:8s}: gross gains % = {p['a']:.1f} + {p['b']:.2f} x net %   (rmse {p['rmse']:.1f} pp); fitted vs actual: " +
          ", ".join(f"{y} {g:.0f}->{f:.0f}" for y, g, f in p["fitted"]))
    P("  intercept scaled by vol/12.4% for the daily book; gross floored at max(net,0). Tax = 30% x gross gains, paid from equity at year end, no set-off.")
    P("  slab_cf = 30% on positive net with losses carried forward (speculative-business reading); slab_nocf = same without carry-forward.")
    P("  Cross-check (resource/08, panel B full window): weekly +8.7% pre-tax -> +5.8 slab / +3.9 segment / -12.0 coin-day; daily +13.6% -> +9.2 / +4.1 / -18.4")
    for k in ["weekly S0.3", "weekly S0.5", "weekly S0.8", "daily S0.3", "daily S0.5", "daily S0.8"]:
        S, vol = cells[k]; Ry = res[k]["Ry"]
        P(f"--- {k} (vol {vol:.0%})")
        hdr = f"  {'reading':10s} {'E[ann. gain]':>12s} {'median CAGR':>11s} {'P(5y<0)':>8s}  5-year $ gain (mean / p10 / p50 / p90) at $1k | $5k | $25k | $100k"
        P(hdr)
        for reading in ("none", "slab_cf", "slab_nocf", "segment", "coinday"):
            E = after_tax_paths(Ry, vol, reading)
            g5 = E[:, -1] - 1
            ann = g5.mean() / YEARS
            cagr = np.median(E[:, -1]) ** (1 / YEARS) - 1
            dollars = " | ".join(f"{money(g5.mean()*C)}/{money(pct(g5,10)*C)}/{money(pct(g5,50)*C)}/{money(pct(g5,90)*C)}" for C in CAPITALS)
            P(f"  {reading:10s} {ann:>+11.2%} {cagr:>+11.2%} {np.mean(g5<0):>8.0%}  {dollars}")
        # same check with the fitted model applied to T6b's own years (sanity)
    P("")
    P("  Sanity: the fitted readings applied to T6b's own pre-tax years (design line) vs T6b's after-tax figures:")
    for y, v in T6B.items():
        R = v[0] / 100
        seg = R - 0.3 * float(gross_gain(np.array([R]), "segment", 0.124)[0])
        cd = R - 0.3 * float(gross_gain(np.array([R]), "coinday", 0.124)[0])
        P(f"    {y}: pre-tax {v[0]:+.1f}%  segment fit {seg*100:+.1f}% (T6b {v[0]-0.3*v[1]:+.1f}%)  coin-day fit {cd*100:+.1f}% (T6b {v[0]-0.3*v[3]:+.1f}%)")
    P("")
    # ---- (4) real money
    P("=" * 110)
    P("(4) WHAT CAPITAL MAKES IT 'REAL MONEY' (>= $500/month = $6,000/yr expected)")
    P("=" * 110)
    for k in ["weekly S0.3", "weekly S0.5", "weekly S0.8", "daily S0.3", "daily S0.5", "daily S0.8"]:
        S, vol = cells[k]; Ry = res[k]["Ry"]
        pre_arith = S * vol
        pre_mc = (np.cumprod(1 + Ry, axis=1)[:, -1] - 1).mean() / YEARS
        rows = [f"pre-tax (S x vol) ${6000/pre_arith:,.0f}", f"pre-tax (MC 5y mean/5) ${6000/pre_mc:,.0f}"]
        for reading in ("slab_cf", "segment", "coinday"):
            E = after_tax_paths(Ry, vol, reading); ann = (E[:, -1] - 1).mean() / YEARS
            rows.append(f"{reading} " + (f"${6000/ann:,.0f}" if ann > 0 else f"never (E[ann] {ann:+.2%})"))
        P(f"  {k}: " + "; ".join(rows))
    P("  with resource/07's 30%-on-venue rule only 30% of that capital sits on Delta; the 70% in an FD earns its own interest (6.5-7% [UNVERIFIED]) which is not strategy edge.")
    P("")
    # ---- (5) time to know
    P("=" * 110)
    P("(5) TIME TO KNOW: distribution of the OBSERVED Sharpe and return at 3 / 6 / 12 months, by true Sharpe (weekly book, 12% vol)")
    P("=" * 110)
    for mdays, lab in ((91, "month 3"), (182, "month 6"), (365, "month 12")):
        P(f"  {lab} (T={mdays/365:.2f} yr; Sharpe SE ~ 1/sqrt(T) = {1/math.sqrt(mdays/365):.2f})")
        for k in ["weekly S0.0", "weekly S0.3", "weekly S0.5", "weekly S0.8"]:
            os_ = res[k]["obs_sharpe"][mdays]; rh = res[k]["ret_h"][mdays]
            P(f"    true {k[-4:]}: observed Sharpe p10 {pct(os_,10):+.2f} p50 {pct(os_,50):+.2f} p90 {pct(os_,90):+.2f}; "
              f"P(obs<0) {np.mean(os_<0):.0%}  P(obs>0.5) {np.mean(os_>0.5):.0%}  P(obs>1) {np.mean(os_>1):.0%}  P(obs>1.65) {np.mean(os_>1.65):.0%}; "
              f"return p10 {pct(rh,10):+.1%} p50 {pct(rh,50):+.1%} p90 {pct(rh,90):+.1%}, on $1k p10 {money(pct(rh,10)*1000)} p90 {money(pct(rh,90)*1000)}")
    P("  Likelihood ratio of 'observed Sharpe > 0.5 at 12 months' for S=0.5 vs S=0: "
      f"{np.mean(res['weekly S0.5']['obs_sharpe'][365]>0.5)/np.mean(res['weekly S0.0']['obs_sharpe'][365]>0.5):.2f}x; "
      f"of 'observed Sharpe > 0' at 6 months: {np.mean(res['weekly S0.5']['obs_sharpe'][182]>0)/np.mean(res['weekly S0.0']['obs_sharpe'][182]>0):.2f}x")
    text = "\n".join(L) + "\n"
    open(os.path.join(OUT, "mc_outcomes.txt"), "w").write(text)
    print(text)
    # machine-readable summary
    summ = {}
    for k in cells:
        Ry = res[k]["Ry"]; cumE = np.cumprod(1 + Ry, axis=1)
        summ[k] = dict(sharpe=cells[k][0], vol=cells[k][1],
                       gain={h: dict(mean=float((cumE[:, h-1]-1).mean()), p10=pct(cumE[:, h-1]-1, 10), p50=pct(cumE[:, h-1]-1, 50), p90=pct(cumE[:, h-1]-1, 90)) for h in HORIZONS},
                       mdd={h: dict(p50=pct(res[k]["mdd"][h], 50), p90=pct(res[k]["mdd"][h], 90), p99=pct(res[k]["mdd"][h], 99)) for h in HORIZONS},
                       p_losing_year=float(np.mean(Ry < 0)),
                       p_pause_monday={f"{thr:.2f}": {y: float(np.mean(res[k]["hit_w"][thr] <= y)) for y in (1, 2, 3, 5)} for thr in PAUSE_DDS},
                       p_pause_daily={f"{thr:.2f}": {y: float(np.mean(res[k]["hit_d"][thr] <= y)) for y in (1, 2, 3, 5)} for thr in PAUSE_DDS})
        if not k.startswith("BTC"):
            summ[k]["after_tax_ann_gain"] = {rd: float((after_tax_paths(Ry, cells[k][1], rd)[:, -1] - 1).mean() / YEARS) for rd in ("none", "slab_cf", "slab_nocf", "segment", "coinday")}
    summ["gross_fit"] = GROSS
    json.dump(summ, open(os.path.join(OUT, "mc_summary.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
