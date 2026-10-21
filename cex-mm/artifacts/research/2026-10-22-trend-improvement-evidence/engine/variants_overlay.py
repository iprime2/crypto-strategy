#!/usr/bin/env python3
"""Overlay-family cells of research2/phase1_plan.md (FROZEN 2026-10-21, sha256 9ad0a829...c095), section 6.5.

Cells: OVL-2 (funding tail cut-out) with its declared secondary and neighbor, and OVL-3 (fast-exit veto). OVL-3 is registered because
phase2/diagnostics.md says "OVL-3 runs = True" (D-1: the Correction state's next-7-day log return on the 24 ex-ante coins is -0.306 %
(t -1.17) on 2020-05..2026-09 and -0.790 % (t -3.10) on 2022-01..2026-09, i.e. <= 0 with t < 0 in both windows).

Both overlays sit on top of the unchanged baseline target (rules.baseline_weights: sign ensemble (20, 60, 120) floored at 0, CC60 vol
floored at 0.05, w = sig (TV/N)/vol with N = coins with 121 closes, gross cap) and only ever set a coin's weight to 0, AFTER the gross
cap, so no other weight is raised and N is unchanged ("never raises a weight"). Band, cadence and costs come from the cadence dict
via the harness. No look-ahead: every quantity at row t uses rows <= t (checked by the module self-test, python3 variants_overlay.py,
which truncates the panel and compares W row by row).

Registered ids
  OVL-2            F_i(d) = 365 x mean of the daily funding fraction over the last 30 calendar days; F_i > 0.30 -> w_i = 0
  OVL-2__14d40     declared secondary cell (reported, never chosen): 14 days, 40 %/yr
  OVL-2__30d40     neighbor: 30 days, 40 %/yr
  OVL-3            w_i = 0 when P_t/P_{t-20} <= 1 and the rule would otherwise hold 1/3 (Correction state); no neighbors by design

Interpretations (each is the reading closest to the plan text / cited source, verify_overlay.md and research2/sim/sim_costs.py)
 I1  OVL-2 funding series = the panel's own F, i.e. the funding the simulator charges: Binance archive daily sums of the 8 h fractions
     on A/B for the whole window (the A/B panels carry no Delta funding; the plan's "Binance before 2024-04, Delta after" describes the
     live/paper feed), Delta's daily mean hourly FUNDING rate x 3 / 100 on C (C starts 2024-08-10, after 2024-04, so C is "Delta
     after" throughout). Row d's funding = the settlements of calendar day d (00/08/16 UTC), all known at the d close (00:00 UTC d+1).
 I2  "Mean over the last 30 calendar days" = sum of F over the calendar days d-29..d inclusive (the decision day included, as
     sim_costs.trailing_funding's range(n)) divided by 30 (14 for the secondary); computed by calendar date, not by row count (the
     panels have no date gaps, so the two agree). A day without a record counts as 0 paid (the panel stores missing as 0 and the
     simulator charges 0 there); the source skips missing records instead, but the only exact-zero days with a close on B are genuine
     zero-rate records (BNB's zero interest-rate days, LTC/LINK/QTUM in 2020), so the two readings coincide on the panels used. Before
     a coin has a full window of calendar rows in the panel F_i is NaN and the rule does not fire (irrelevant: holding needs 121 closes).
 I3  Threshold strict: w_i = 0 iff F_i(d) > 0.30 (> 0.40 for the secondary and the neighbor), as written ("If F_i(d) > 0.30").
 I4  "For the next holding period": the mask is applied to W[t], the target decided at the close of t; on the daily book it covers
     t -> t+1; on the weekly book W is read only on the Sunday-candle rows (Monday 00:00 UTC decision), so F_i is read at that decision
     and the coin stays flat for the week (a mid-week funding spike does nothing until the next Monday), as the plan states.
 I5  A6 Delta-funding-stress line: the plan defines F_i on "the daily funding fraction paid by longs", so on the stress re-run the rule
     reads the stressed funding the book is charged there. The harness calls fn on the archive panel and passes the stressed panel only
     to the simulator, so each OVL-2 cell returns a custom_sim that recomputes the mask from the panel it is handed (pp.F) and then calls
     sim.simulate unchanged; on every other run pp is the same panel and the result is identical to the standard path (self-test
     checks bit-equality). Contrast: SIG-13 (variants_signal I11) reads archive funding on the stress line; the difference is
     reporting-only (A6 binds a decision only for variants that RAISE exposure by > 10 %; OVL-2 lowers it), and the stress floors in
     research2/funding_summary.json are all below 12 %/yr, far under the 30 %/yr threshold.
 I6  OVL-3 literal: veto iff P_t/P_{t-20} <= 1 (rules.lag_return(C, 20) <= 0; NaN -> no veto) AND the baseline signal equals 1/3
     (isclose). Given r20 <= 0 a signal of 1/3 means r60 > 0 and r120 > 0 (the D-1 Correction state with the 60-day sleeve on); the
     measure-zero r20 == 0 case gives a signal of 2/3, not 1/3, and is not vetoed. Entries, the 60/120 sleeves, vol, N and every
     other weight are unchanged.
 I7  OVL-2 binding episode (the plan's extra condition, ">= 8 distinct binding episodes (coin x contiguous run >= 3 days) outside
     2021 on B"): a coin-day BINDS when the baseline would hold the coin (baseline W > 0, next close exists) and F_i > threshold, i.e. the
     rule actually changes the target (F above the threshold while the signal is already 0 is not binding). Counted on panel B (24
     ex-ante, the harness window 2020-05-01..2026-09-30, decision rows t with dates[t+1] in the window), on the DAILY book's coin-day
     series (the primary count; binding does not depend on TV); 2021 days are removed first and the remaining contiguous runs of
     binding calendar days >= 3 per coin are counted (an episode crossing a year boundary is truncated at 2021). Reported alongside:
     the weekly book's count (a binding Monday decision covers the 7 holding days; consecutive binding decisions form one run) and the
     25-coin B (with DOGE) count. The count is printed by this module's self-test (binding_episodes / episode_report).
 I8  OVL-3 flips/yr (the plan's "flips/yr and fees/yr reported"): entries + exits of the TARGET (W > 0 vs W == 0 changes between
     consecutive decision rows, a coin without a next close counted as flat) per coin per year within the panel window; fees/yr is the
     harness's stats line (turnover x 7.31 bps). The harness has no flips field, so flips/yr is printed by the self-test
     (flip_report) and reported in the result notes.

Deviations forced by the harness: none in the rules. Reporting only: the episode count (OVL-2) and flips/yr (OVL-3) are not fields the
harness writes into phase2/<id>.json, so they live in this module's self-test output and in the result notes.

Flag for the lead engineer (not acted on; the contract says run OVL-3 iff diagnostics.md says "OVL-3 runs = True", which it does)
 G1  diagnostics.md decided the OVL-3 gate on the UNCONDITIONAL Correction column (-0.306 % t -1.17; -0.790 % t -3.10). The cited
     source (verify_overlay.md, OVL-3 refined rule) words the gate as "the Correction-state forward return WITH THE SIGNAL ON is <= 0
     (t < 0)", and the plan's 6.0/6.5 text does not name the column. The signal-on column is +0.605 % (t +1.63) on 2020-26 and +0.092 %
     (t +0.26) on 2022-26, i.e. positive in both windows, and with r20 < 0 & r120 > 0 & sig > 0 that column is EXACTLY the set of
     coin-days OVL-3 zeroes (sig = 1/3 requires r60 > 0). Under the source's wording OVL-3 would not run. The cell is implemented and
     self-tested as instructed; whether its result counts is the lead engineer's call.

Self-test (2026-10-21; python3 variants_overlay.py -> SELFTEST OK: truncation no-look-ahead on 4 cuts, never-raises / zero-only checks,
custom_sim bit-equal to sim.simulate daily and weekly, calendar-window mean == rules.funding_annualized on the contiguous panel;
harness.py <4 ids> --panels A --cadences daily --tag _selftest, json files deleted afterwards)
 A daily FULL Sharpe (var / base 1.250), delta [95 % CI] P<=0; POST delta; CAGR, vol, maxDD, funding/yr
   OVL-2         1.374  +0.124 [-0.34,+0.53] P 0.30; POST +0.122 [-0.01,+0.38] P 0.07; CAGR 21.6 % (24.2), vol 15.1 % (18.7),
                 maxDD -14.0 % (-21.9), funding 1.70 %/yr (3.43); matched vol (TV 0.497): DD -17.3 %, worst7 -11.3 % (base -9.5 %)
                 -> reproduces the verifier's in-sample 9-coin numbers exactly (CAGR 24.2 -> 21.6, vol 18.7 -> 15.1, DD -21.9 -> -14.0)
   OVL-2__14d40  1.413  +0.163 [-0.22,+0.52] P 0.19; POST +0.118; DD -16.3 %; funding 1.85 %/yr
   OVL-2__30d40  1.224  -0.026 [-0.44,+0.28] P 0.56; POST +0.071; DD -16.7 %; funding 2.05 %/yr
   OVL-3         1.197  -0.053 [-0.17,+0.05] P 0.86; POST -0.095 [-0.24,+0.03] P 0.94; turnover 16.9x (15.7), fees 1.24 %/yr (1.14)
 A6 stress line (A, POST Sharpe var / base 0.787): OVL-2 0.907, 14d40 0.903, 30d40 0.857, OVL-3 0.695; the stress funding changes the
   30d/30 % mask on 183 coin-days of A.
 OVL-2 binding episodes (I7), panel B (24 ex-ante), coin x contiguous run >= 3 days, 2021 removed:
   30 d / 30 % (primary)  daily 88 (2020: 58, 2023: 2, 2024: 26, 2025: 1, 2026: 1; 30 from 2022 on), weekly 72 (27 from 2022);
                          all 24 coins; 7 calendar clusters (2020-07/09, 2020-11/12, 2023-12/2024-01, 2024-03/04, 2024-11/2025-01,
                          2025-11, 2026-09), 5 of them from 2022; the 30 episodes from 2022 are 23 coin-runs in the 2024-03/04
                          cluster + 4 around 2024-01-01 (ETC, IOTA, QTUM, IOST) + XMR x3 (2024-11, 2025-11, 2026-09);
                          binds on 21.98 % of held coin-days (all years, daily)
   14 d / 40 % (secondary) daily 79 (29 from 2022), weekly 71; 12 clusters (8 from 2022)
   30 d / 40 % (neighbor)  daily 54 (20 from 2022), weekly 45; 4 clusters (2 from 2022)
   B25: 90 / 81 / 55 daily. A (nine): 26 / 28 / 17 daily (8 / 9 / 6 from 2022). C (Delta): 13 / 7 / 3 daily.
   The >= 8 condition holds on B for every cell, but the 2022+ count rests on one market-wide spike (2024-03/04) plus XMR.
 OVL-3 flips/yr of the target (I8), var vs base: A daily 281.5 vs 217.1, weekly 104.3 vs 80.7; B daily 702.7 vs 569.8, weekly 260.2
   vs 208.2; C daily 267.5 vs 210.5, weekly 101.1 vs 82.3. Vetoed share of held coin-days: A 22.97 %, B 22.39 %, C 20.57 %.
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import rules, sim
from registry import variant

SPAN = 121
THIRD = 1.0 / 3.0


# ---------------------------------------------------------------- shared pieces

def _base_W(p, cad):
    """The baseline target (repo rule, gross-capped); overlays only zero entries of this."""
    return rules.baseline_weights(p.C, tv=cad["tv"], max_gross=cad["max_gross"])


def funding_ann_calendar(F, dates, win):
    """F_i(d) = 365 x (sum of the daily funding fraction over calendar days d-win+1..d) / win; NaN until the panel holds win days."""
    F0 = np.where(np.isfinite(F), F, 0.0)
    ords = np.array([d.toordinal() for d in dates])
    cs = np.vstack([np.zeros((1, F0.shape[1])), np.cumsum(F0, axis=0)])
    lo = np.searchsorted(ords, ords - win + 1, side="left")  # first row inside the calendar window
    t = np.arange(len(dates))
    out = (cs[t + 1] - cs[lo]) / win * 365.0
    full = (ords - win + 1) >= ords[0]
    out[~full] = np.nan
    return out


def ovl2_mask(p, win, thr):
    """True where the funding tail cut-out sets the weight to 0 (F_i(d) > thr)."""
    fa = funding_ann_calendar(p.F, p.dates, win)
    return np.where(np.isfinite(fa), fa > thr, False)


def _ovl2(p, cad, win, thr):
    W0 = _base_W(p, cad)
    W = np.where(ovl2_mask(p, win, thr), 0.0, W0)

    def stress_aware_sim(pp, _W, kw):
        # I5: recompute the mask from the funding panel actually charged (identical to W when pp carries p's funding)
        Wp = np.where(ovl2_mask(pp, win, thr), 0.0, W0)
        return sim.simulate(pp, Wp, **kw)

    return W, {"custom_sim": stress_aware_sim}


def ovl3_mask(p):
    """True where the fast-exit veto sets the weight to 0: P_t/P_{t-20} <= 1 and the baseline signal is exactly 1/3."""
    sig = np.maximum(np.nan_to_num(rules.sig_sign_mean(p.C)), 0.0)
    r20 = rules.lag_return(p.C, 20)
    down = np.where(np.isfinite(r20), r20 <= 0, False)
    return down & np.isclose(sig, THIRD, rtol=0, atol=1e-12)


# ---------------------------------------------------------------- OVL-2 funding tail cut-out

@variant("OVL-2")
def ovl2(p, cad):
    return _ovl2(p, cad, 30, 0.30)


@variant("OVL-2__14d40")
def ovl2_14d40(p, cad):
    """Declared secondary cell (reported, never chosen); also a neighbor."""
    return _ovl2(p, cad, 14, 0.40)


@variant("OVL-2__30d40")
def ovl2_30d40(p, cad):
    return _ovl2(p, cad, 30, 0.40)


# ---------------------------------------------------------------- OVL-3 fast-exit veto (conditional on D-1: runs = True)

@variant("OVL-3")
def ovl3(p, cad):
    W0 = _base_W(p, cad)
    return np.where(ovl3_mask(p), 0.0, W0), {}


# ---------------------------------------------------------------- reporting helpers (episode count, flips/yr)

def _decision_rows(p, weekly, start, end):
    """Rows t that decide a holding inside [start, end] (dates[t+1] in the window) and, weekly, are Sunday-candle rows."""
    T = len(p.dates)
    ok = np.zeros(T, bool)
    for t in range(T - 1):
        nxt = p.dates[t + 1]
        ok[t] = (start is None or nxt >= start) and (end is None or nxt <= end)
    if weekly:
        ok &= rules.decide_weekly(p.dates, 6)
    return ok


def binding_days(p, win, thr, weekly=False, start=None, end=None):
    """(T, N) bool: calendar days on which the cut-out changes the held target (I7). Daily: decision rows where the baseline would hold
    and F > thr. Weekly: a binding Sunday-candle decision marks its 7 holding days (rows t..t+6)."""
    cad = dict(tv=0.25, max_gross=1.0)  # binding does not depend on TV (W0 > 0 iff sig > 0 on a valid row)
    W0 = _base_W(p, cad)
    nxt_ok = np.vstack([np.isfinite(p.C[1:]), np.zeros((1, p.C.shape[1]), bool)])
    b = (W0 > 0) & ovl2_mask(p, win, thr) & nxt_ok & _decision_rows(p, weekly, start, end)[:, None]
    if not weekly:
        return b
    out = np.zeros_like(b)
    T = len(p.dates)
    for t in np.where(b.any(axis=1))[0]:
        out[t:min(t + 7, T)] |= b[t]
    return out


def count_runs(days_bool, dates, min_run=3, exclude_year=2021):
    """Per-coin contiguous runs (calendar days) of True of length >= min_run after removing exclude_year's days.
    Returns list of (coin_index, first_date, last_date, length)."""
    keep = np.array([d.year != exclude_year for d in dates]) if exclude_year else np.ones(len(dates), bool)
    x = days_bool & keep[:, None]
    ords = np.array([d.toordinal() for d in dates])
    eps = []
    for j in range(x.shape[1]):
        idx = np.where(x[:, j])[0]
        if not len(idx):
            continue
        s = prev = idx[0]
        for i in list(idx[1:]) + [None]:
            if i is not None and ords[i] == ords[prev] + 1:
                prev = i; continue
            n = ords[prev] - ords[s] + 1
            if n >= min_run:
                eps.append((j, dates[s], dates[prev], int(n)))
            if i is not None:
                s = prev = i
    return eps


def episode_report(p, win, thr, weekly=False, start=None, end=None):
    b = binding_days(p, win, thr, weekly, start, end)
    eps_out = count_runs(b, p.dates, 3, 2021)
    eps_all = count_runs(b, p.dates, 3, None)
    by_year = {}
    for j, a, z, n in eps_out:
        by_year[a.year] = by_year.get(a.year, 0) + 1
    held = (_base_W(p, dict(tv=0.25, max_gross=1.0)) > 0) & _decision_rows(p, False, start, end)[:, None]
    share = float(binding_days(p, win, thr, False, start, end).sum() / max(held.sum(), 1))  # daily series, all years
    post = [e for e in eps_out if e[1].year >= 2022]
    # calendar clusters: runs >= 3 days of the union over coins (a market-wide funding spike is one cluster, many coin episodes)
    clusters = count_runs(b.any(axis=1)[:, None], p.dates, 3, 2021)
    return dict(n_outside_2021=len(eps_out), n_all=len(eps_all), n_post2021=len(post), by_year=by_year,
                coins=sorted({str(p.coins[j]) for j, *_ in eps_out}),
                episodes=[(str(p.coins[j]), str(a), str(z), n) for j, a, z, n in eps_out], binding_share_of_held_coin_days=share,
                binding_days_outside_2021=int(sum(n for *_, n in eps_out)),
                clusters=[(str(a), str(z), n) for _, a, z, n in clusters])


def flip_report(p, W, weekly, start, end):
    """Entries + exits of the target per year on decision rows (I8)."""
    rows = np.where(_decision_rows(p, weekly, start, end))[0]
    nxt_ok = np.vstack([np.isfinite(p.C[1:]), np.zeros((1, p.C.shape[1]), bool)])
    on = (W > 0) & nxt_ok
    flips, prev = 0, None
    for t in rows:
        if prev is not None:
            flips += int((on[t] != on[prev]).sum())
        prev = t
    days = sum(1 for d in p.dates[1:] if (start is None or d >= start) and (end is None or d <= end))
    return flips / max(days / 365.0, 1e-9)


# ---------------------------------------------------------------- self-test

def _selftest():
    import harness, data
    P = harness.panels()
    pa, a0, a1 = P["A"]
    ok = True
    # 1. no look-ahead: W rows computed on a truncated panel equal the full-panel rows
    for name, fn in (("OVL-2", ovl2), ("OVL-2__14d40", ovl2_14d40), ("OVL-2__30d40", ovl2_30d40), ("OVL-3", ovl3)):
        Wf, _ = fn(pa, harness.DAILY)
        for cut in (400, 900, 1500, 2100):
            q = data.Panel(pa.dates[:cut], pa.coins, pa.O[:cut], pa.H[:cut], pa.L[:cut], pa.C[:cut], pa.V[:cut], pa.F[:cut], pa.Q[:cut])
            Wt, _ = fn(q, harness.DAILY)
            if not np.allclose(Wt, Wf[:cut], atol=1e-15, equal_nan=True):
                print(f"LOOKAHEAD FAIL {name} cut {cut}"); ok = False
        W0 = _base_W(pa, harness.DAILY)
        if np.any(Wf > W0 + 1e-15):
            print(f"RAISE FAIL {name}"); ok = False
        if np.any((Wf != W0) & (Wf != 0)):
            print(f"NON-ZERO CHANGE FAIL {name}"); ok = False
    # 2. custom_sim path == standard path when the funding panel is the same panel
    for cad in (harness.DAILY, harness.WEEKLY):
        W, ex = ovl2(pa, cad)
        kw = dict(decide=rules.decide_weekly(pa.dates, 6) if cad["weekly"] else None, band=cad["band"], start=a0, end=a1, capital=None)
        r1 = ex["custom_sim"](pa, W, kw); r2 = sim.simulate(pa, W, **kw)
        if not np.array_equal(r1["rets"], r2["rets"]):
            print(f"CUSTOM PATH FAIL {cad['name']}"); ok = False
        q, _ = harness.delta_funding_stress(pa)
        r3 = ex["custom_sim"](q, W, kw)
        print(f"  A {cad['name']}: stress-line mask rows changed vs archive mask: "
              f"{int((ovl2_mask(q, 30, 0.30) != ovl2_mask(pa, 30, 0.30)).sum())} coin-days; stress Sharpe {sim.sharpe(r3['rets']):.3f}")
    # 3. calendar-window funding mean equals the row-rolling mean on the contiguous panels
    fr = rules.funding_annualized(pa.F, 30); fc = funding_ann_calendar(pa.F, pa.dates, 30)
    m = np.isfinite(fr) & np.isfinite(fc)
    if not np.allclose(fr[m], fc[m], atol=1e-12):
        print("CALENDAR MEAN FAIL"); ok = False
    # 4. OVL-2 binding episodes on B (the plan's extra condition) and B25 / A / C for the record
    for ds in ("B", "B25", "A", "C"):
        p, s, e = P[ds]
        for win, thr in ((30, 0.30), (14, 0.40), (30, 0.40)):
            for weekly in (False, True):
                rep = episode_report(p, win, thr, weekly, s, e)
                print(f"EPISODES {ds} {win}d>{thr:.0%} {'weekly' if weekly else 'daily '}: outside-2021 {rep['n_outside_2021']} "
                      f"(2022+ {rep['n_post2021']}; all years {rep['n_all']}) by_year {dict(sorted(rep['by_year'].items()))} "
                      f"calendar clusters {len(rep['clusters'])} ({sum(1 for c in rep['clusters'] if c[0] >= '2022')} from 2022) "
                      f"coins {len(rep['coins'])}; binding share of held coin-days (daily series) {rep['binding_share_of_held_coin_days']:.2%}")
                if ds == "B" and win == 30 and thr == 0.30 and not weekly:
                    print("    clusters:", rep["clusters"])
                    print("    2022+ episodes:", [e for e in rep["episodes"] if e[1] >= "2022"])
    # 5. OVL-3 flips/yr and veto share
    for ds in ("A", "B", "C"):
        p, s, e = P[ds]
        for cad in (harness.DAILY, harness.WEEKLY):
            Wv, _ = ovl3(p, cad); W0 = _base_W(p, cad)
            rows = _decision_rows(p, False, s, e)[:, None]
            held = ((W0 > 0) & rows).sum(); vet = (ovl3_mask(p) & (W0 > 0) & rows).sum()
            print(f"OVL-3 {ds} {cad['name']}: flips/yr {flip_report(p, Wv, cad['weekly'], s, e):.1f} vs base {flip_report(p, W0, cad['weekly'], s, e):.1f}; "
                  f"vetoed share of held coin-days {vet / max(held, 1):.2%}")
    print("SELFTEST", "OK" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    _selftest()
