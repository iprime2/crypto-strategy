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


if __name__ == "__main__":
    main()
