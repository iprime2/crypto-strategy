"""Run the frozen previous-week-level study on panels A, B, C (implementation Y; final copy with fix B1).

Usage: python3 -I run.py [A B C]
Writes results.json, events_<panel>.csv.gz, extras.json, run_log.txt into this folder.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine as E  # noqa: E402
import loaders as LD  # noqa: E402

COST = {"F": 2.12 + 7.31, "B": 14.62, "S": 14.62}
PATTERNS = ("F", "B", "S")
HNAMES = ("1h", "4h", "24h")
CONTROLS = ("real", "P1", "P2")
N_BOOT = 2000
SEED = 11


def ms(s):
    return int(pd.Timestamp(s, tz="UTC").value // 10**6)


HALF_SPLIT = ms("2023-07-01")
PANELS = {
    # candidate weeks: Mondays whose whole week lies inside the window (A, B) / full weeks of data (C)
    "A": dict(coins=LD.NINE, first=ms("2020-05-04"), last=ms("2026-09-21"), cap=ms("2026-10-01"), reel=True),
    "B": dict(coins=LD.NINE + LD.EXTRA16, first=ms("2020-05-04"), last=ms("2026-09-21"), cap=ms("2026-10-01"),
              reel=False),
    "C": dict(coins=LD.NINE, first=ms("2025-01-13"), last=None, cap=None, reel=False),
}


def iso(x):
    return pd.to_datetime(np.asarray(x, dtype=np.int64), unit="ms", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_coin(args):
    panel, sym = args
    cfg = PANELS[panel]
    loader = {"A": LD.load_panel_A, "B": LD.load_panel_B, "C": LD.load_panel_C}[panel]
    bars = loader(sym, cfg["cap"])
    data_end = int(bars["t"][-1]) + bars["bar_ms"]
    last = cfg["last"]
    if last is None:  # panel C: last Monday whose week ends at or before the data end (full weeks only)
        last = cfg["first"]
        while last + 2 * E.WEEK <= data_end:
            last += E.WEEK
    weeks = list(range(cfg["first"], last + 1, E.WEEK))
    ev, winfo, reelrows, diag = E.coin_events(bars, weeks, data_end, reel=cfg["reel"])
    # FIX B1 (reporting): why a coin-week was skipped. listing = the coin's first bar is after the start of the prior
    # week; delisting = the coin's data ends before week w ends; data_loss = both weeks lie inside the coin's data span
    # but fewer than 99 % of their bars are present.
    first_bar = int(bars["t"][0])
    for info in winfo:
        if info["used"]:
            info["skip_reason"] = None
        elif first_bar > info["W"] - E.WEEK:
            info["skip_reason"] = "listing"
        elif data_end < info["W"] + E.WEEK:
            info["skip_reason"] = "delisting"
        else:
            info["skip_reason"] = "data_loss"
    meta = dict(sym=sym, n_bars=len(bars["t"]), first_bar=int(bars["t"][0]), last_bar=int(bars["t"][-1]),
                data_end=data_end, n_dupes=bars["n_dupes"], n_files=bars["n_files"],
                n_patched=bars.get("n_patched", 0), weeks=weeks)
    return sym, ev, winfo, reelrows, diag, meta


def boot_weights(n_weeks, rng):
    idx = rng.integers(0, n_weeks, size=(N_BOOT, n_weeks))
    Wt = np.zeros((N_BOOT, n_weeks), dtype=np.float64)
    for b in range(N_BOOT):
        Wt[b] = np.bincount(idx[b], minlength=n_weeks)
    return Wt


def fnum(x):
    if x is None:
        return None
    x = float(x)
    return None if not np.isfinite(x) else x


def panel_stats(panel, ev, wk, rr, coins):
    cfg = PANELS[panel]
    out = {}
    used = wk[wk.used]
    out["coin_weeks_used"] = int(wk.used.sum())
    out["coin_weeks_skipped"] = int((~wk.used).sum())
    skipped = wk[~wk.used]
    out["coin_weeks_skipped_by_reason"] = {r: int((skipped.skip_reason == r).sum())
                                           for r in ("listing", "delisting", "data_loss")}
    assert sum(out["coin_weeks_skipped_by_reason"].values()) == out["coin_weeks_skipped"]
    extras = {"skipped_weeks_by_reason": {
        r: {c: [str(pd.to_datetime(int(w), unit="ms").date()) for w in g.W]
            for c, g in skipped[skipped.skip_reason == r].groupby("coin")}
        for r in ("listing", "delisting", "data_loss")}}
    # touch rates (real levels) per used coin-week
    real = rr[rr.control == "real"]
    pv = real.pivot_table(index=["coin", "W"], columns="kind", values="touched", aggfunc="first")
    pv = pv.reindex(pd.MultiIndex.from_frame(used[["coin", "W"]]))
    pwh = pv["PWH"].fillna(False).astype(bool)
    pwl = pv["PWL"].fillna(False).astype(bool)
    out["touch_rates"] = {"any": float((pwh | pwl).mean()), "pwh": float(pwh.mean()), "pwl": float(pwl.mean())}
    extras["touch_counts"] = {"any": int((pwh | pwl).sum()), "pwh": int(pwh.sum()), "pwl": int(pwl.sum())}
    # reel-style rates
    if cfg["reel"]:
        reel, reel_side = {}, {}
        for ctl in CONTROLS:
            sub = rr[(rr.control == ctl) & rr.touched]
            rj = sub["reject60"].dropna().astype(bool)
            co = sub["continued"].dropna().astype(bool) if "continued" in sub else pd.Series([], dtype=bool)
            reel[ctl] = {"reject60": float(rj.mean()), "continued": float(co.mean())}
            reel_side[ctl] = {}
            for sd in ("H", "L"):
                s2 = sub[sub.side == sd]
                rj2 = s2["reject60"].dropna().astype(bool)
                co2 = s2["continued"].dropna().astype(bool)
                reel_side[ctl][sd] = {"reject60": float(rj2.mean()), "n_touch": int(len(rj2)),
                                      "continued": float(co2.mean()), "n_confirmed": int(len(co2))}
            reel_side[ctl]["pooled_n"] = {"n_touch": int(len(rj)), "n_confirmed": int(len(co))}
            if "continued_tie" in sub:
                ok = sub["continued"].notna()
                tie = sub.loc[ok, "continued_tie"].astype(bool)
                c2 = sub.loc[ok, "continued"].astype(bool)
                reel_side[ctl]["continued_tie_sensitivity"] = {
                    "n_ties": int(tie.sum()),
                    "ties_as_not_continued (reported)": float(c2.mean()),
                    "ties_as_continued": float((c2 | tie).mean()),
                    "ties_excluded": float(c2[~tie].mean())}
        out["reel"] = reel
        extras["reel_by_side"] = reel_side
    else:
        out["reel"] = None
    # cells
    cells = []
    for pat in PATTERNS:
        for side in ("pooled", "H", "L"):
            for hn in HNAMES:
                for ctl in CONTROLS:
                    s = ev[(ev.pattern == pat) & (ev.horizon == hn) & (ev.control == ctl)]
                    if side != "pooled":
                        s = s[s.side == side]
                    n = len(s)
                    cells.append({"pattern": pat, "side": side, "horizon": hn, "control": ctl, "n": int(n),
                                  "gross_bps": fnum(s.gross.mean()) if n else None,
                                  "net_bps": fnum(s.net.mean()) if n else None,
                                  "hit": fnum((s.net > 0).mean()) if n else None})
    out["cells"] = cells
    # week-cluster bootstrap: one shared set of 2,000 week resamples per panel
    weeks = np.array(sorted(used.W.unique()), dtype=np.int64)
    wpos = {w: i for i, w in enumerate(weeks)}
    rng = np.random.default_rng(SEED)
    Wt = boot_weights(len(weeks), rng)
    ev = ev.assign(wi=ev.W.map(wpos).astype(int))

    def week_vec(s, col):
        return (np.bincount(s.wi, weights=s[col], minlength=len(weeks)),
                np.bincount(s.wi, minlength=len(weeks)).astype(float))

    tests = []
    nan_draws = 0
    extras["coins_pos_diff_vs_own_control"] = []
    for pat in PATTERNS:
        for hn in HNAMES:
            r = ev[(ev.pattern == pat) & (ev.horizon == hn) & (ev.control == "real")]
            rg, rn = week_vec(r, "gross")
            rnet, _ = week_vec(r, "net")
            br_g = (Wt @ rg) / (Wt @ rn)
            br_n = (Wt @ rnet) / (Wt @ rn)
            for ctl in ("P1", "P2"):
                p = ev[(ev.pattern == pat) & (ev.horizon == hn) & (ev.control == ctl)]
                pg, pn = week_vec(p, "gross")
                bp_g = (Wt @ pg) / (Wt @ pn)
                d_b = br_g - bp_g
                ok = np.isfinite(d_b)
                nan_draws += int((~ok).sum())
                diff = r.gross.mean() - p.gross.mean()
                row = {"pattern": pat, "horizon": hn, "control": ctl, "diff_bps": fnum(diff),
                       "ci_lo": fnum(np.percentile(d_b[ok], 2.5)), "ci_hi": fnum(np.percentile(d_b[ok], 97.5)),
                       "p_one_sided": fnum((d_b[ok] <= 0).mean()),
                       "real_net_bps": fnum(r.net.mean()),
                       "real_net_p": fnum((br_n[np.isfinite(br_n)] <= 0).mean())}
                if panel in ("A", "B"):
                    halves = {}
                    for hname, m_r, m_p in (("H1", r.W < HALF_SPLIT, p.W < HALF_SPLIT),
                                            ("H2", r.W >= HALF_SPLIT, p.W >= HALF_SPLIT)):
                        halves[hname] = {"diff_bps": fnum(r[m_r].gross.mean() - p[m_p].gross.mean()),
                                         "real_net_bps": fnum(r[m_r].net.mean()), "n": int(m_r.sum())}
                    row["halves"] = halves
                else:
                    row["halves"] = None
                if panel == "A":
                    p1 = ev[(ev.pattern == pat) & (ev.horizon == hn) & (ev.control == "P1")]
                    rc = r.groupby("coin").gross.mean()
                    pc = p1.groupby("coin").gross.mean()
                    nc = r.groupby("coin").net.mean()
                    dc = (rc - pc).reindex(LD.NINE)
                    row["coins_pos_diff"] = int((dc > 0).sum())
                    row["coins_pos_net"] = int((nc.reindex(LD.NINE) > 0).sum())
                    own = (rc - p.groupby("coin").gross.mean()).reindex(LD.NINE)
                    extras["coins_pos_diff_vs_own_control"].append(
                        {"pattern": pat, "horizon": hn, "control": ctl, "coins_pos_diff": int((own > 0).sum()),
                         "per_coin_diff_bps": {k: fnum(v) for k, v in own.items()},
                         "per_coin_real_net_bps": {k: fnum(v) for k, v in nc.reindex(LD.NINE).items()}})
                else:
                    row["coins_pos_diff"] = None
                    row["coins_pos_net"] = None
                tests.append(row)
    out["tests"] = tests
    extras["bootstrap"] = {"n_weeks": int(len(weeks)), "nan_diff_draws": nan_draws,
                           "first_week": str(pd.to_datetime(weeks[0], unit="ms").date()),
                           "last_week": str(pd.to_datetime(weeks[-1], unit="ms").date())}
    # daily Sharpe of real events, net bps summed per exit day, zero on days without exits
    d0 = pd.to_datetime(int(wk.W.min()), unit="ms").normalize()
    d1 = pd.to_datetime(int(wk.W.max()) + 8 * E.DAY, unit="ms").normalize()
    cal = pd.date_range(d0, d1, freq="D")
    ds = {}
    for pat in PATTERNS:
        ds[pat] = {}
        for hn in HNAMES:
            r = ev[(ev.pattern == pat) & (ev.horizon == hn) & (ev.control == "real")]
            day = pd.to_datetime(r.tx, unit="ms").dt.normalize()
            ser = r.net.groupby(day.values).sum().reindex(cal, fill_value=0.0)
            sd = ser.std(ddof=1)
            ds[pat][hn] = fnum(ser.mean() / sd * np.sqrt(365.0)) if sd > 0 else None
    out["daily_sharpe"] = ds
    extras["daily_sharpe_calendar"] = [str(d0.date()), str(d1.date()), int(len(cal))]
    return out, extras


def run_panel(panel):
    t_start = time.time()
    cfg = PANELS[panel]
    with ProcessPoolExecutor(max_workers=4) as px:
        res = list(px.map(run_coin, [(panel, s) for s in cfg["coins"]]))
    evs, wks, rrs, diags, metas = [], [], [], {}, {}
    cols = ["W", "kind", "side", "control", "L", "pattern", "horizon", "te", "pe", "tx", "px", "gross"]
    for sym, ev, winfo, reelrows, diag, meta in res:
        e = pd.DataFrame(ev, columns=cols)
        e.insert(0, "coin", sym)
        evs.append(e)
        w = pd.DataFrame(winfo)
        w.insert(0, "coin", sym)
        wks.append(w)
        rdf = pd.DataFrame(reelrows)
        rdf.insert(0, "coin", sym)
        rrs.append(rdf)
        diags[sym] = diag
        meta = dict(meta)
        meta["weeks"] = [str(pd.to_datetime(meta["weeks"][0], unit="ms").date()),
                         str(pd.to_datetime(meta["weeks"][-1], unit="ms").date()), len(meta["weeks"])]
        for k in ("first_bar", "last_bar", "data_end"):
            meta[k] = str(pd.to_datetime(meta[k], unit="ms"))
        metas[sym] = meta
    ev = pd.concat(evs, ignore_index=True)
    wk = pd.concat(wks, ignore_index=True)
    rr = pd.concat(rrs, ignore_index=True)
    for col in ("reject60", "continued"):
        if col not in rr:
            rr[col] = np.nan
    ev["net"] = ev.gross - ev.pattern.map(COST)
    t_events = time.time() - t_start
    out, extras = panel_stats(panel, ev, wk, rr, cfg["coins"])
    # diagnostics
    u = wk[wk.used]
    extras["coins"] = metas
    extras["diag_per_coin"] = diags
    extras["weeks_used_per_coin"] = u.groupby("coin").size().to_dict()
    extras["weeks_skipped_per_coin"] = wk[~wk.used].groupby("coin").size().to_dict()
    extras["dh_nonpos"] = int((u.dh <= 0).sum())
    extras["dl_nonpos"] = int((u.dl <= 0).sum())
    nexp = E.WEEK // (300_000 if panel == "A" else E.HOUR)
    extras["p2_window_below_99pct_coinweeks"] = int((u.p2_window_bars < 0.99 * nexp).sum())
    lv = rr[rr.control == "P2"]
    extras["p2_levels"] = {"P2H": int((lv.kind == "P2H").sum()), "P2L": int((lv.kind == "P2L").sum()),
                           "coin_weeks_used": int(len(u))}
    extras["n_events_by_control_pattern"] = ev.groupby(["control", "pattern", "horizon"]).size().rename(
        lambda x: x).reset_index().astype(str).values.tolist()
    extras["runtime_s"] = {"events": round(t_events, 1), "total": round(time.time() - t_start, 1)}
    # events csv (contract columns)
    csv = pd.DataFrame({
        "coin": ev.coin,
        "week_start": pd.to_datetime(ev.W, unit="ms").dt.strftime("%Y-%m-%d"),
        "level_kind": ev.kind, "level_px": ev.L, "pattern": ev.pattern, "horizon": ev.horizon,
        "entry_time": iso(ev.te), "entry_px": ev.pe, "exit_time": iso(ev.tx), "exit_px": ev.px,
        "gross_bps": ev.gross})
    csv = csv.sort_values(["coin", "week_start", "level_kind", "pattern", "horizon"], kind="stable")
    csv.to_csv(os.path.join(HERE, f"events_{panel}.csv.gz"), index=False, compression="gzip")
    return out, extras


def main():
    panels = sys.argv[1:] or ["A", "B", "C"]
    rpath = os.path.join(HERE, "results.json")
    xpath = os.path.join(HERE, "extras.json")
    results = json.load(open(rpath)) if os.path.exists(rpath) else {}
    extras = json.load(open(xpath)) if os.path.exists(xpath) else {}
    for p in panels:
        t0 = time.time()
        out, ex = run_panel(p)
        results[p] = out
        extras[p] = ex
        print(f"panel {p}: {out['coin_weeks_used']} used, {out['coin_weeks_skipped']} skipped, "
              f"{time.time() - t0:.1f}s", flush=True)
    results = {k: results[k] for k in ("A", "B", "C") if k in results}
    with open(rpath, "w") as fh:
        json.dump(results, fh, indent=1)
    with open(xpath, "w") as fh:
        json.dump(extras, fh, indent=1, default=str)


# =====================================================================================================================
# PHASE2 (research3/phase2_plan.md, sha256 940a391b...c40f2): T outcome on panels A (reference), OT, OX; controls real,
# P1 (pooled and split by m), P3 (Thursday 12:00 anchor). Everything above this line is the Phase 1 code, unchanged
# except that the entry point now runs main2(). Usage: python3 -I run.py [A OT OX]
import math  # noqa: E402

COST_T = {"base": 14.62, "stress": 30.62}   # 2 x (5.31 + 2) and 2 x (5.31 + 10) bps round trip, both sides taker
MON0 = 4 * E.DAY                            # 1970-01-05 00:00 UTC is a Monday
P3_OFF = 84 * E.HOUR                        # Thursday 12:00 UTC = Monday 00:00 + 84 h
HMS = dict(E.HORIZONS)
P1_FINAL = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/final"

PANELS2 = {
    # A exactly as Phase 1 (reference); OT per coin from its first full prior week through the week of 2020-04-20;
    # OX weeks 2022-01-03..2026-09-21. half = first week start of the second half (halves by week start).
    "A": dict(coins=LD.NINE, loader="load_panel_A", first=ms("2020-05-04"), last=ms("2026-09-21"),
              cap=ms("2026-10-01"), half=ms("2023-07-01"), halves=("2020-05..2023-06", "2023-07..2026-09")),
    "OT": dict(coins=LD.OT_COINS, loader="load_panel_OT", first=None, last=ms("2020-04-20"), cap=ms("2020-05-01"),
               half=ms("2019-01-01"), halves=("2017-08..2018-12", "2019-01..2020-04")),
    "OX": dict(coins=LD.OX_COINS, loader="load_panel_OX", first=ms("2022-01-03"), last=ms("2026-09-21"),
               cap=ms("2026-10-01"), half=ms("2024-05-01"), halves=("2022-01..2024-04", "2024-05..2026-09")),
}


def monday_of(t):
    t = np.asarray(t, dtype=np.int64)
    return (t - MON0) // E.WEEK * E.WEEK + MON0


def run_coin2(args):
    panel, sym = args
    cfg = PANELS2[panel]
    bars = getattr(LD, cfg["loader"])(sym, cfg["cap"])
    data_end = int(bars["t"][-1]) + bars["bar_ms"]
    first_bar = int(bars["t"][0])
    first = cfg["first"]
    if first is None:  # OT: first Monday week starting at or after the first bar is the first full week; +1 week
        first = int(monday_of(first_bar - 1)) + 2 * E.WEEK
    weeks = list(range(first, cfg["last"] + 1, E.WEEK))
    ev, winfo, rrows, diag = E.coin_events(bars, weeks, data_end, reel=False)
    for info in winfo:  # Phase 1 skip classifier (fix B1), unchanged
        if info["used"]:
            info["skip_reason"] = None
        elif first_bar > info["W"] - E.WEEK:
            info["skip_reason"] = "listing"
        elif data_end < info["W"] + E.WEEK:
            info["skip_reason"] = "delisting"
        else:
            info["skip_reason"] = "data_loss"
    # P3 anchors: every Thursday 12:00 from the one before the first candidate Monday to the one inside the last
    anchors = list(range(weeks[0] - E.WEEK + P3_OFF, weeks[-1] + P3_OFF + 1, E.WEEK))
    ev3, p3info, p3rows, diag3 = E.coin_events_p3(bars, anchors, data_end)
    meta = dict(sym=sym, n_bars=len(bars["t"]), first_bar=first_bar, last_bar=int(bars["t"][-1]), data_end=data_end,
                n_dupes=bars["n_dupes"], n_files=bars["n_files"], n_patched=bars.get("n_patched", 0),
                effective_end=bars.get("effective_end_ms"), n_cut_after_last_trade=bars.get("n_cut_after_last_trade"),
                weeks=[weeks[0], weeks[-1], len(weeks)], anchors=[anchors[0], anchors[-1], len(anchors)])
    return sym, ev, winfo, rrows, ev3, p3info, p3rows, diag, diag3, meta


EVCOLS = ["W", "kind", "side", "control", "L", "pattern", "horizon", "te", "pe", "tx", "px", "gross"]


def _mean(x):
    return fnum(x.mean()) if len(x) else None


def cell(s):
    n = len(s)
    return {"n": int(n), "gross": _mean(s.gross), "net_base": _mean(s.net_base), "net_stress": _mean(s.net_stress),
            "hit": _mean(s.net_base > 0), "hit_stress": _mean(s.net_stress > 0)}


def stats2(panel, groups, wk, coins):
    """groups: {control: T-event frame (all horizons)}; control in real, P1, P1_in, P1_out, P3, P3_owncov."""
    cfg = PANELS2[panel]
    out = {}
    hn_list = list(HNAMES)
    # cells, pooled and by side
    out["cells"] = {hn: {g: cell(f[f.horizon == hn]) for g, f in groups.items()} for hn in hn_list}
    out["cells_by_side"] = {hn: {g: {sd: cell(f[(f.horizon == hn) & (f.side == sd)]) for sd in ("H", "L")}
                                 for g, f in groups.items()} for hn in hn_list}
    # week-cluster bootstrap exactly as Phase 1: Monday weeks with >= 1 used coin-week, one shared set of 2,000
    # resamples per panel from default_rng(11); P3 events carry the Monday week containing their touch.
    used = wk[wk.used]
    weeks = np.array(sorted(used.W.unique()), dtype=np.int64)
    wpos = {int(w): i for i, w in enumerate(weeks)}
    rng = np.random.default_rng(SEED)
    Wt = boot_weights(len(weeks), rng)
    nW = len(weeks)

    def bvec(s, col):
        wi = s.mw.map(wpos)
        assert wi.notna().all(), "event outside the bootstrap weeks"
        wi = wi.astype(int).to_numpy()
        return np.bincount(wi, weights=s[col].to_numpy(), minlength=nW), np.bincount(wi, minlength=nW).astype(float)

    def bmean(s, col):
        a, n = bvec(s, col)
        return (Wt @ a) / (Wt @ n)

    def fin(x):
        return x[np.isfinite(x)]

    tests, nan_draws = {}, 0
    for hn in hn_list:
        r = groups["real"][groups["real"].horizon == hn]
        bg, bb, bs = bmean(r, "gross"), bmean(r, "net_base"), bmean(r, "net_stress")
        t = {"real": {"n": int(len(r)), "gross": _mean(r.gross),
                      "gross_ci": [fnum(np.percentile(fin(bg), 2.5)), fnum(np.percentile(fin(bg), 97.5))],
                      "net_base": _mean(r.net_base), "p_net_base_le0": fnum((fin(bb) <= 0).mean()),
                      "net_base_ci": [fnum(np.percentile(fin(bb), 2.5)), fnum(np.percentile(fin(bb), 97.5))],
                      "net_stress": _mean(r.net_stress), "p_net_stress_le0": fnum((fin(bs) <= 0).mean()),
                      "net_stress_ci": [fnum(np.percentile(fin(bs), 2.5)), fnum(np.percentile(fin(bs), 97.5))]},
             "diff": {}}
        for g in ("P1", "P1_in", "P1_out", "P3", "P3_owncov"):
            p = groups[g][groups[g].horizon == hn]
            d = bg - bmean(p, "gross")
            ok = np.isfinite(d)
            nan_draws += int((~ok).sum())
            t["diff"][g] = {"diff_gross": fnum(r.gross.mean() - p.gross.mean()) if len(p) else None,
                            "ci_lo": fnum(np.percentile(d[ok], 2.5)), "ci_hi": fnum(np.percentile(d[ok], 97.5)),
                            "p_diff_le0": fnum((d[ok] <= 0).mean()), "n_control": int(len(p)),
                            "nan_draws": int((~ok).sum())}
        tests[hn] = t
    out["tests"] = tests
    out["bootstrap"] = {"n_draws": N_BOOT, "seed": SEED, "n_weeks": int(nW), "nan_draws_total": nan_draws,
                        "first_week": str(pd.to_datetime(int(weeks[0]), unit="ms").date()),
                        "last_week": str(pd.to_datetime(int(weeks[-1]), unit="ms").date())}
    # halves (by Monday week start)
    halves = {}
    for hn in hn_list:
        halves[hn] = {}
        for hname, lo, hi in (("H1", -np.inf, cfg["half"]), ("H2", cfg["half"], np.inf)):
            def part(g):
                f = groups[g]
                return f[(f.horizon == hn) & (f.mw >= lo) & (f.mw < hi)]
            r, p1, p3 = part("real"), part("P1"), part("P3")
            halves[hn][hname] = {"n": int(len(r)), "gross": _mean(r.gross), "net_base": _mean(r.net_base),
                                 "net_stress": _mean(r.net_stress), "P1_n": int(len(p1)), "P1_gross": _mean(p1.gross),
                                 "diff_P1": fnum(r.gross.mean() - p1.gross.mean()) if len(r) and len(p1) else None,
                                 "P3_n": int(len(p3)),
                                 "diff_P3": fnum(r.gross.mean() - p3.gross.mean()) if len(r) and len(p3) else None,
                                 "label": cfg["halves"][0 if hname == "H1" else 1]}
    out["halves"] = halves
    # per coin
    pc = {}
    for hn in hn_list:
        r = groups["real"][groups["real"].horizon == hn]
        p1 = groups["P1"][groups["P1"].horizon == hn]
        rows = {}
        for c in coins:
            rc, pcc = r[r.coin == c], p1[p1.coin == c]
            rows[c] = {"n": int(len(rc)), "gross": _mean(rc.gross), "net_base": _mean(rc.net_base),
                       "net_stress": _mean(rc.net_stress), "P1_gross": _mean(pcc.gross),
                       "diff_P1": fnum(rc.gross.mean() - pcc.gross.mean()) if len(rc) and len(pcc) else None}
        pc[hn] = {"coins": rows,
                  "coins_pos_net_base": int(sum(1 for v in rows.values() if v["net_base"] is not None and v["net_base"] > 0)),
                  "coins_pos_net_stress": int(sum(1 for v in rows.values() if v["net_stress"] is not None and v["net_stress"] > 0)),
                  "coins_pos_diff_P1": int(sum(1 for v in rows.values() if v["diff_P1"] is not None and v["diff_P1"] > 0)),
                  "n_coins": len(coins)}
    out["per_coin"] = pc
    # daily Sharpe (Phase 1 convention): real events, net summed per exit day (UTC), zero on days without exits,
    # calendar from the first candidate Monday to the last candidate Monday + 8 days, annualised with sqrt(365)
    d0 = pd.to_datetime(int(wk.W.min()), unit="ms").normalize()
    d1 = pd.to_datetime(int(wk.W.max()) + 8 * E.DAY, unit="ms").normalize()
    cal = pd.date_range(d0, d1, freq="D")
    ds = {}
    for hn in hn_list:
        r = groups["real"][groups["real"].horizon == hn]
        day = pd.to_datetime(r.tx, unit="ms").dt.normalize()
        ds[hn] = {}
        for col, key in (("net_base", "base"), ("net_stress", "stress")):
            ser = r[col].groupby(day.values).sum().reindex(cal, fill_value=0.0)
            assert abs(ser.sum() - r[col].sum()) < 1e-6 * max(1.0, abs(r[col].sum())), "exit day outside calendar"
            sd = ser.std(ddof=1)
            ds[hn][key] = fnum(ser.mean() / sd * np.sqrt(365.0)) if sd > 0 else None
    out["daily_sharpe"] = ds
    out["daily_sharpe_calendar"] = [str(d0.date()), str(d1.date()), int(len(cal))]
    # per-year means (calendar year of the Monday week start)
    py = {}
    for hn in hn_list:
        r = groups["real"][groups["real"].horizon == hn]
        p1 = groups["P1"][groups["P1"].horizon == hn]
        ry = pd.to_datetime(r.mw, unit="ms").dt.year
        p1y = pd.to_datetime(p1.mw, unit="ms").dt.year
        py[hn] = {}
        for y in sorted(set(ry.unique()) | set(p1y.unique())):
            a, b = r[ry.values == y], p1[p1y.values == y]
            py[hn][str(int(y))] = {"n": int(len(a)), "gross": _mean(a.gross), "net_base": _mean(a.net_base),
                                   "net_stress": _mean(a.net_stress), "P1_n": int(len(b)), "P1_gross": _mean(b.gross),
                                   "diff_P1": fnum(a.gross.mean() - b.gross.mean()) if len(a) and len(b) else None}
    out["per_year"] = py
    # pass rule, section 4, at h = 4 h
    t4, h4, c4 = tests["4h"], halves["4h"], pc["4h"]
    need = int(math.ceil(2 * len(coins) / 3))
    g1 = {"real_net_base": t4["real"]["net_base"], "p_net_le0": t4["real"]["p_net_base_le0"],
          "rule": "net > 0 and P(net <= 0) <= 0.01"}
    g1["pass"] = bool(g1["real_net_base"] > 0 and g1["p_net_le0"] <= 0.01)
    d1_ = t4["diff"]["P1"]
    g2 = {"diff_gross": d1_["diff_gross"], "ci": [d1_["ci_lo"], d1_["ci_hi"]], "p_diff_le0": d1_["p_diff_le0"],
          "rule": "real - P1 gross > 0 and P(diff <= 0) <= 0.01"}
    g2["pass"] = bool(g2["diff_gross"] > 0 and g2["p_diff_le0"] <= 0.01)
    g3 = {"H1_net_base": h4["H1"]["net_base"], "H2_net_base": h4["H2"]["net_base"],
          "H1_diff_P1": h4["H1"]["diff_P1"], "H2_diff_P1": h4["H2"]["diff_P1"], "rule": "real net > 0 in both halves"}
    g3["pass"] = bool(g3["H1_net_base"] is not None and g3["H2_net_base"] is not None and g3["H1_net_base"] > 0
                      and g3["H2_net_base"] > 0)
    g4 = {"coins_pos_net_base": c4["coins_pos_net_base"], "n_coins": len(coins), "needed": need,
          "rule": f"real net > 0 on >= {need} of {len(coins)} coins"}
    g4["pass"] = bool(g4["coins_pos_net_base"] >= need)
    out["gating_4h"] = {"1_net": g1, "2_diff_P1": g2, "3_halves": g3, "4_coins": g4,
                        "all_pass": bool(g1["pass"] and g2["pass"] and g3["pass"] and g4["pass"])}
    return out


def phase1_check(ev_all):
    """Panel A: (a) our F rows equal final/events_A.csv.gz F rows (real and P1); (b) T gross = -F gross row by row;
    (c) T 4 h pooled means equal minus the Phase 1 F means in final/results.json, to 0.01 bps."""
    res = {}
    old = pd.read_csv(os.path.join(P1_FINAL, "events_A.csv.gz"), float_precision="round_trip")
    old = old[(old.pattern == "F") & ~old.level_kind.str.startswith("P2")]
    ours = ev_all[(ev_all.pattern == "F") & ev_all.control.isin(["real", "P1"])].copy()
    ours["week_start"] = pd.to_datetime(ours.W, unit="ms").dt.strftime("%Y-%m-%d")
    key = ["coin", "week_start", "level_kind", "horizon"]
    o2 = ours.rename(columns={"kind": "level_kind"})[key + ["gross", "te", "tx", "L", "px"]]
    m = old.merge(o2, on=key, how="outer", indicator=True)
    both = m[m._merge == "both"]
    res["F_rows_phase1"] = int(len(old))
    res["F_rows_here"] = int(len(o2))
    res["F_rows_only_phase1"] = int((m._merge == "left_only").sum())
    res["F_rows_only_here"] = int((m._merge == "right_only").sum())
    res["F_max_abs_gross_diff_bps"] = fnum((both.gross_bps - both.gross).abs().max())
    res["F_max_abs_level_px_diff"] = fnum((both.level_px - both.L).abs().max())
    res["F_max_abs_exit_px_diff"] = fnum((both.exit_px - both.px).abs().max())
    res["F_entry_exit_times_identical"] = bool((both.entry_time == iso(both.te)).all()
                                               and (both.exit_time == iso(both.tx)).all())
    # T vs F, row by row (all controls kept here: real, P1, P3)
    f = ev_all[ev_all.pattern == "F"].set_index(["coin", "W", "kind", "horizon"]).gross
    t = ev_all[ev_all.pattern == "T"].set_index(["coin", "W", "kind", "horizon"]).gross
    assert f.index.equals(t.index) or set(f.index) == set(t.index)
    t = t.reindex(f.index)
    res["T_rows"] = int(len(t))
    res["T_equals_minus_F_exactly_rows"] = int((t.to_numpy() == -f.to_numpy()).sum())
    res["T_plus_F_max_abs_bps"] = fnum(np.abs(t.to_numpy() + f.to_numpy()).max())
    # means vs Phase 1 results.json
    p1r = json.load(open(os.path.join(P1_FINAL, "results.json")))["A"]["cells"]
    cmp = {}
    for hn in HNAMES:
        for ctl in ("real", "P1"):
            ph1 = [c for c in p1r if c["pattern"] == "F" and c["side"] == "pooled" and c["horizon"] == hn
                   and c["control"] == ctl][0]
            s = ev_all[(ev_all.pattern == "T") & (ev_all.horizon == hn) & (ev_all.control == ctl)]
            cmp[f"{hn}|{ctl}"] = {"phase1_F_gross": ph1["gross_bps"], "phase1_F_n": ph1["n"],
                                  "T_gross": fnum(s.gross.mean()), "T_n": int(len(s)),
                                  "abs_T_plus_F": fnum(abs(s.gross.mean() + ph1["gross_bps"])),
                                  "within_0.01bps": bool(abs(s.gross.mean() + ph1["gross_bps"]) <= 0.01
                                                         and len(s) == ph1["n"])}
    res["means_vs_phase1_results"] = cmp
    res["pass"] = bool(all(v["within_0.01bps"] for v in cmp.values()) and res["F_rows_only_phase1"] == 0
                       and res["F_rows_only_here"] == 0 and res["T_plus_F_max_abs_bps"] == 0.0)
    return res


def drops_by_reason(touch, tev, data_end):
    """T exits dropped per control and horizon: touched levels without a T row, by reason (after data end or a
    missing exit bar inside the data, e.g. an exchange outage)."""
    out = {}
    have = set(zip(tev.coin, tev.W, tev.kind, tev.horizon))
    for ctl, g in touch.groupby("control"):
        out[ctl] = {}
        for hn in HNAMES:
            n_after = n_missing = 0
            for c, W, k, t0 in zip(g.coin, g.W, g.kind, g.t0):
                if (c, W, k, hn) in have:
                    continue
                if t0 + HMS[hn] > data_end[c]:
                    n_after += 1
                else:
                    n_missing += 1
            out[ctl][hn] = {"touched": int(len(g)), "after_end": n_after, "missing_bar": n_missing}
    return out


def run_panel2(panel):
    t_start = time.time()
    cfg = PANELS2[panel]
    with ProcessPoolExecutor(max_workers=4) as px:
        res = list(px.map(run_coin2, [(panel, s) for s in cfg["coins"]]))
    evs, wks, p3ws, touches, metas, diags, data_end = [], [], [], [], {}, {}, {}
    for sym, ev, winfo, rrows, ev3, p3info, p3rows, diag, diag3, meta in res:
        for rows in (ev, ev3):
            e = pd.DataFrame(rows, columns=EVCOLS)
            e.insert(0, "coin", sym)
            evs.append(e[e.pattern.isin(["F", "T"]) & e.control.isin(["real", "P1", "P3"])])
        w = pd.DataFrame(winfo)
        w.insert(0, "coin", sym)
        wks.append(w)
        w3 = pd.DataFrame(p3info)
        w3.insert(0, "coin", sym)
        p3ws.append(w3)
        tr = pd.DataFrame(rrows + p3rows)
        tr.insert(0, "coin", sym)
        touches.append(tr[tr.touched & tr.control.isin(["real", "P1", "P3"])])
        diags[sym] = {"monday": diag, "p3": diag3}
        data_end[sym] = meta["data_end"]
        m2 = dict(meta)
        for k in ("first_bar", "last_bar", "data_end", "effective_end"):
            if m2[k] is not None:
                m2[k] = str(pd.to_datetime(m2[k], unit="ms"))
        m2["weeks"] = [str(pd.to_datetime(m2["weeks"][0], unit="ms").date()),
                       str(pd.to_datetime(m2["weeks"][1], unit="ms").date()), m2["weeks"][2]]
        m2["anchors"] = [str(pd.to_datetime(m2["anchors"][0], unit="ms")),
                         str(pd.to_datetime(m2["anchors"][1], unit="ms")), m2["anchors"][2]]
        metas[sym] = m2
    ev = pd.concat(evs, ignore_index=True)
    wk = pd.concat(wks, ignore_index=True)
    p3w = pd.concat(p3ws, ignore_index=True)
    touch = pd.concat(touches, ignore_index=True)
    out = {"panel": panel, "coins": cfg["coins"]}
    if panel == "A":
        out["phase1_check"] = phase1_check(ev)
    # T = -F on every row, all panels
    f = ev[ev.pattern == "F"].set_index(["coin", "W", "kind", "horizon"]).gross.sort_index()
    t = ev[ev.pattern == "T"].set_index(["coin", "W", "kind", "horizon"]).gross.sort_index()
    assert f.index.equals(t.index) and (t.to_numpy() == -f.to_numpy()).all(), "T != -F"
    T = ev[ev.pattern == "T"].copy()
    T["mw"] = monday_of(T.te.to_numpy())
    assert (T.loc[T.control != "P3", "mw"] == T.loc[T.control != "P3", "W"]).all()
    T["net_base"] = T.gross - COST_T["base"]
    T["net_stress"] = T.gross - COST_T["stress"]
    # coin-weeks
    out["coin_weeks_used"] = int(wk.used.sum())
    out["coin_weeks_skipped"] = int((~wk.used).sum())
    sk = wk[~wk.used]
    out["coin_weeks_skipped_by_reason"] = {r: int((sk.skip_reason == r).sum()) for r in ("listing", "delisting",
                                                                                         "data_loss")}
    assert sum(out["coin_weeks_skipped_by_reason"].values()) == out["coin_weeks_skipped"]
    out["coin_weeks_used_per_coin"] = {c: int(wk[(wk.coin == c) & wk.used].shape[0]) for c in cfg["coins"]}
    out["coin_weeks_skipped_per_coin"] = {c: int(wk[(wk.coin == c) & ~wk.used].shape[0]) for c in cfg["coins"]}
    out["skipped_weeks"] = {c: [f"{pd.to_datetime(int(W), unit='ms').date()}:{r}" for W, r in zip(g.W, g.skip_reason)]
                            for c, g in sk.groupby("coin")}
    out["coin_weeks_used_halves"] = {"H1": int(wk[wk.used & (wk.W < cfg["half"])].shape[0]),
                                     "H2": int(wk[wk.used & (wk.W >= cfg["half"])].shape[0])}
    # P3 samples. Primary: touch inside a Monday week that is a used coin-week of the same coin (the real levels'
    # sample). Sensitivity P3_owncov: P3 coverage only, touch inside any Monday week of the bootstrap set.
    usedset = set(zip(wk.coin[wk.used], wk.W[wk.used]))
    bweeks = set(wk.W[wk.used].astype(np.int64))
    is3 = T.control == "P3"
    in_used = np.array([(c, int(m)) in usedset for c, m in zip(T.coin, T.mw)])
    in_bw = T.mw.isin(bweeks).to_numpy()
    P3own = T[is3 & in_bw].copy()
    P3own["control"] = "P3_owncov"
    keep = ~is3 | (is3 & in_used)
    out["p3"] = {"anchor_weeks": int(len(p3w)), "anchor_weeks_used": int(p3w.used.sum()),
                 "anchor_weeks_skipped": int((~p3w.used).sum()),
                 "events_all_horizons_scored": int(is3.sum()),
                 "kept_primary (touch in a used Monday coin-week of the same coin)": int((is3 & in_used).sum()),
                 "kept_owncov (touch in any bootstrap Monday week)": int((is3 & in_bw).sum()),
                 "dropped_not_in_bootstrap_weeks": int((is3 & ~in_bw).sum())}
    for hn in HNAMES:
        h = T.horizon == hn
        out["p3"][f"{hn}_scored/primary/owncov"] = [int((is3 & h).sum()), int((is3 & h & in_used).sum()),
                                                     int((is3 & h & in_bw).sum())]
    Tm = T[keep]
    m = Tm.kind.str.extract(r"_(\d+(?:\.\d+)?)$")[0].astype(float)
    groups = {"real": Tm[Tm.control == "real"], "P1": Tm[Tm.control == "P1"],
              "P1_in": Tm[(Tm.control == "P1") & (m < 1).to_numpy()],
              "P1_out": Tm[(Tm.control == "P1") & (m > 1).to_numpy()],
              "P3": Tm[Tm.control == "P3"], "P3_owncov": P3own}
    assert len(groups["P1_in"]) + len(groups["P1_out"]) == len(groups["P1"])
    out.update(stats2(panel, groups, wk, cfg["coins"]))
    # dropped exits by reason, and the touch counts
    tt = touch.copy()
    tt["mw"] = monday_of(tt.t0.to_numpy())
    tt_keep = (tt.control != "P3") | np.array([(c, int(m_)) in usedset for c, m_ in zip(tt.coin, tt.mw)])
    out["dropped_exits"] = drops_by_reason(tt[tt_keep], T[keep], data_end)
    out["coins_meta"] = metas
    out["diag_per_coin"] = diags
    out["runtime_s"] = round(time.time() - t_start, 1)
    # event files: Phase 1 columns + net_base; T only; week_start = Monday week containing the touch
    def write(fr, name):
        csv = pd.DataFrame({
            "coin": fr.coin, "week_start": pd.to_datetime(fr.mw, unit="ms").dt.strftime("%Y-%m-%d"),
            "level_kind": fr.kind, "level_px": fr.L, "pattern": fr.pattern, "horizon": fr.horizon,
            "entry_time": iso(fr.te), "entry_px": fr.pe, "exit_time": iso(fr.tx), "exit_px": fr.px,
            "gross_bps": fr.gross, "net_base": fr.net_base})
        csv = csv.sort_values(["coin", "week_start", "level_kind", "pattern", "horizon"], kind="stable")
        csv.to_csv(os.path.join(HERE, name), index=False, compression="gzip")
        return int(len(csv))
    out["event_rows_written"] = {f"events_{panel}.csv.gz": write(Tm, f"events_{panel}.csv.gz"),
                                 f"events_{panel}_p3owncov.csv.gz": write(P3own, f"events_{panel}_p3owncov.csv.gz")}
    wk.to_csv(os.path.join(HERE, f"coin_weeks_{panel}.csv.gz"), index=False, compression="gzip")
    p3w.to_csv(os.path.join(HERE, f"p3_weeks_{panel}.csv.gz"), index=False, compression="gzip")
    return out


def main2():
    panels = sys.argv[1:] or ["A", "OT", "OX"]
    rpath = os.path.join(HERE, "results.json")
    results = json.load(open(rpath)) if os.path.exists(rpath) else {}
    for p in panels:
        t0 = time.time()
        out = run_panel2(p)
        results[p] = out
        g = out["gating_4h"]
        print(f"panel {p}: {out['coin_weeks_used']} used, {out['coin_weeks_skipped']} skipped, "
              f"T 4h real n={out['cells']['4h']['real']['n']} gross={out['cells']['4h']['real']['gross']:.2f} "
              f"net={out['cells']['4h']['real']['net_base']:.2f}; gates "
              f"{[g[k]['pass'] for k in ('1_net', '2_diff_P1', '3_halves', '4_coins')]}; {time.time() - t0:.1f}s",
              flush=True)
        if p == "A":
            print("  phase1_check pass:", out["phase1_check"]["pass"], flush=True)
    results = {k: results[k] for k in ("OT", "OX", "A") if k in results}
    import hashlib
    ref_sha = open(os.path.join(SCR_R3, "phase2_plan_sha256.txt")).read().split()[0]
    now_sha = hashlib.sha256(open(os.path.join(SCR_R3, "phase2_plan.md"), "rb").read()).hexdigest()
    gate = {p: results[p]["gating_4h"]["all_pass"] for p in ("OT", "OX") if p in results}
    results["_meta"] = {"plan": "research3/phase2_plan.md", "plan_sha256_reference": ref_sha,
                        "plan_sha256_now": now_sha, "plan_unchanged": now_sha == ref_sha,
                        "costs_round_trip_bps": COST_T, "horizons": list(HNAMES), "primary_horizon": "4h",
                        "pass_rule": "all four section-4 tests on BOTH OT and OX at 4 h",
                        "panel_pass": gate,
                        "overall_pass": bool(len(gate) == 2 and all(gate.values()))}
    with open(rpath, "w") as fh:
        json.dump(results, fh, indent=1, default=str)


SCR_R3 = os.path.join(LD.SCR, "research3")

if __name__ == "__main__":
    main2()
