"""C2: stop-entry fill realism (sensitivity only). Touch-bar anatomy for real and P1 events at 4 h, and the four gates
when the fill is moved off L: gap-aware (the open when the bar opens beyond L), the touch-bar close, L + 10 / 20 bps
(adverse), L + 10 / 20 bps capped at the bar's extreme, and the plain stop trigger (high >= L instead of > L(1+0.5bp))."""
import json
import pickle
import sys

import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv"
sys.path.insert(0, D)
import adv_lib as A  # noqa: E402

res = pickle.load(open(f"{D}/events_adv.pkl", "rb"))
HALF = {"OT": A.ts("2019-01-01"), "OX": A.ts("2024-05-01")}
COINS = {"OT": A.OT_COINS, "OX": A.OX_COINS}


def q(x, ps=(0.1, 0.25, 0.5, 0.75, 0.9, 0.99)):
    return {f"p{int(p * 100)}": float(np.quantile(x, p)) for p in ps}


def fill_variants(e):
    s = e.s.to_numpy()
    L = e.L.to_numpy()
    o, h, l, c = e.tb_o.to_numpy(), e.tb_h.to_numpy(), e.tb_l.to_numpy(), e.tb_c.to_numpy()
    ext = np.where(s > 0, h, l)  # the bar's extreme on the breakout side
    gap = np.where(s > 0, np.maximum(L, o), np.minimum(L, o))
    v = {"L": L, "gap_aware_open": gap, "touch_close": c}
    for b in (10, 20):
        adv = L * (1 + s * b * 1e-4)
        v[f"L+{b}bp"] = adv
        v[f"L+{b}bp_capped_at_extreme"] = np.where(s > 0, np.minimum(adv, ext), np.maximum(adv, ext))
        v[f"gap_aware+{b}bp_capped"] = np.where(s > 0, np.minimum(gap * (1 + b * 1e-4), ext),
                                                np.maximum(gap * (1 - b * 1e-4), ext))
    return v


out = {}
for panel in ("OT", "OX"):
    ev, wk = res[(panel, "base")]
    weeks = sorted(wk.W[wk.used].unique())
    Wt = A.boot_W(len(weeks))
    e = ev[(ev.status == "ok") & (ev.horizon == "4h") & ev.control.isin(["real", "P1"])].copy()
    s = e.s
    e["excess_bps"] = np.where(s > 0, e.tb_h / e.L - 1, 1 - e.tb_l / e.L) * 1e4
    e["open_beyond_bps"] = np.where(s > 0, e.tb_o / e.L - 1, 1 - e.tb_o / e.L) * 1e4  # > 0: bar opened beyond L
    e["close_beyond_bps"] = np.where(s > 0, e.tb_c / e.L - 1, 1 - e.tb_c / e.L) * 1e4  # < 0: closed back inside
    o = {}
    for ctl in ("real", "P1"):
        f = e[e.control == ctl]
        gapped = f.open_beyond_bps > 0
        rev = f.close_beyond_bps < 0
        o[ctl] = {"n": int(len(f)),
                  "excess_beyond_L_bps": q(f.excess_bps),
                  "share_excess_gt_10bp": float((f.excess_bps > 10).mean()),
                  "share_excess_gt_50bp": float((f.excess_bps > 50).mean()),
                  "share_excess_gt_100bp": float((f.excess_bps > 100).mean()),
                  "share_open_beyond_L": float(gapped.mean()),
                  "open_beyond_L_bps_when_gapped": q(f.open_beyond_bps[gapped]) if gapped.any() else None,
                  "n_open_beyond_L_gt_10bp": int((f.open_beyond_bps > 10).sum()),
                  "n_open_beyond_L_gt_50bp": int((f.open_beyond_bps > 50).sum()),
                  "share_close_back_inside_L (single-bar reversal)": float(rev.mean()),
                  "close_beyond_L_bps": q(f.close_beyond_bps),
                  "gross_mean_reversal_bars": float(f.gross[rev].mean()),
                  "gross_mean_non_reversal_bars": float(f.gross[~rev].mean()),
                  "share_touch_bar_prev_bar_missing": float(f.prev_gap.mean()),
                  "gross_sum_share_from_gapped": float(f.gross[gapped].sum() / f.gross.sum())}
    # gates under fill variants (applied to real and P1 alike)
    fv = fill_variants(e)
    gv = {}
    for name, F in fv.items():
        e["g2"] = e.s * (e.px / F - 1.0) * 1e4
        r, p = e[e.control == "real"], e[e.control == "P1"]
        g = A.gates(r, p, weeks, COINS[panel], HALF[panel], col="g2", Wt=Wt)
        g["real_gross"] = float(r.g2.mean())
        g["p1_gross"] = float(p.g2.mean())
        gv[name] = g
    # real-only change (P1 left at L) for the two adverse cases, as the most hostile reading of the diff test
    for b in (10, 20):
        F = np.where(e.control == "real", fv[f"L+{b}bp"], fv["L"])
        e["g2"] = e.s * (e.px / F - 1.0) * 1e4
        r, p = e[e.control == "real"], e[e.control == "P1"]
        gv[f"L+{b}bp_real_only"] = A.gates(r, p, weeks, COINS[panel], HALF[panel], col="g2", Wt=Wt)
    o["gates_by_fill"] = gv
    # plain stop trigger: high >= L (no 0.5 bp tolerance), fill at L
    ev2, wk2 = res[(panel, "ge")]
    e2 = ev2[(ev2.status == "ok") & (ev2.horizon == "4h")]
    r2, p2 = e2[e2.control == "real"], e2[e2.control == "P1"]
    o["gates_trigger_ge"] = A.gates(r2, p2, weeks, COINS[panel], HALF[panel], Wt=Wt)
    # how often the plain trigger fires earlier than the plan's touch (a real stop at L would have filled earlier)
    key = ["coin", "W", "kind"]
    b1 = ev[(ev.horizon == "4h") & ev.control.isin(["real", "P1"])][key + ["t0", "control"]]
    b2 = ev2[(ev2.horizon == "4h")][key + ["t0"]].rename(columns={"t0": "t0_ge"})
    m = b2.merge(b1, on=key, how="left")
    o["trigger_ge_vs_tol"] = {
        "levels_touched_ge": int(len(m)), "levels_touched_tol": int(len(b1)),
        "ge_only (never exceeded by 0.5 bp)": int(m.t0.isna().sum()),
        "ge_earlier_than_tol": int((m.t0_ge < m.t0).sum()),
        "real_ge_earlier": int(((m.t0_ge < m.t0) & (m.control == "real")).sum()),
        "real_levels_tol": int((b1.control == "real").sum())}
    out[panel] = o
    print("=" * 30, panel)
    for ctl in ("real", "P1"):
        print(ctl, json.dumps(o[ctl], default=lambda x: round(x, 3)))
    for name, g in gv.items():
        print(f"{name:32s} net {g['net']:8.2f} P {g['p_net']:.4f} | diff {g['diff']:7.2f} P {g['p_diff']:.4f} | "
              f"H1 {g['h1']:7.2f} H2 {g['h2']:7.2f} | coins {g['coins_pos']}/{g['need']} | all {g['all']}")
    g = o["gates_trigger_ge"]
    print(f"{'trigger high>=L':32s} net {g['net']:8.2f} P {g['p_net']:.4f} | diff {g['diff']:7.2f} P {g['p_diff']:.4f} | "
          f"H1 {g['h1']:7.2f} H2 {g['h2']:7.2f} | coins {g['coins_pos']}/{g['need']} | all {g['all']} n {g['n']}")
    print(o["trigger_ge_vs_tol"])
json.dump(out, open(f"{D}/c2_fills.json", "w"), indent=1, default=float)
