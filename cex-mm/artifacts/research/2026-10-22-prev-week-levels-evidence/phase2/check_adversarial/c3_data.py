"""C3: data checks. Coverage-rule variants (OT outages), zero-volume / thin touch and exit bars, bad-print exits,
outage-window exits on OX, delisting tails, and the audit-flagged wick weeks. Sensitivity only."""
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
out = {}


def gl(g):
    return (f"net {g['net']:7.2f} P {g['p_net']:.4f} | diff {g['diff']:6.2f} P {g['p_diff']:.4f} | H1 {g['h1']:6.2f} "
            f"H2 {g['h2']:6.2f} | coins {g['coins_pos']}/{g['need']} | n {g['n']} weeks {g['n_weeks']} | all {g['all']}")


for panel in ("OT", "OX"):
    o = {}
    bars = {c: A.load(panel, c) for c in COINS[panel]}
    ev, wk = res[(panel, "base")]
    weeks = sorted(wk.W[wk.used].unique())
    Wt = A.boot_W(len(weeks))
    e = ev[(ev.status == "ok") & (ev.horizon == "4h") & ev.control.isin(["real", "P1"])].copy()
    r, p = e[e.control == "real"], e[e.control == "P1"]
    base = A.gates(r, p, weeks, COINS[panel], HALF[panel], Wt=Wt)
    print("=" * 20, panel, "\nbase", gl(base))
    # 1. coverage variants (OT only): the 99 % rule also conditions on the event week's own data (an outage inside it)
    if panel == "OT":
        cv = {}
        for vn in ("cov95", "cov90", "cov0"):
            ev2, wk2 = res[(panel, vn)]
            e2 = ev2[(ev2.status == "ok") & (ev2.horizon == "4h")]
            w2 = sorted(wk2.W[wk2.used].unique())
            g = A.gates(e2[e2.control == "real"], e2[e2.control == "P1"], w2, COINS[panel], HALF[panel])
            g["coin_weeks_used"] = int(wk2.used.sum())
            g["dropped_4h_real_missing_exit"] = int(((ev2.status != "ok") & (ev2.horizon == "4h")
                                                     & (ev2.control == "real")).sum())
            cv[vn] = g
            print(vn, gl(g), "coin-weeks", g["coin_weeks_used"], "dropped real 4h", g["dropped_4h_real_missing_exit"])
        o["coverage_variants"] = cv
    # 2. thin / zero-volume touch bars and exit bars
    th = {}
    for ctl, f in (("real", r), ("P1", p)):
        th[ctl] = {"touch_bar_zero_volume": int((f.tb_v == 0).sum()),
                   "touch_bar_trades_le_2": int((f.tb_n <= 2).sum()),
                   "touch_bar_trades_le_5": int((f.tb_n <= 5).sum()),
                   "exit_bar_zero_volume": int((f.ex_v == 0).sum()),
                   "gross_mean_touch_trades_le_5": float(f.gross[f.tb_n <= 5].mean()) if (f.tb_n <= 5).any() else None}
    o["thin_bars"] = th
    print("thin bars", th)
    keep_r = r[(r.tb_n > 5) & (r.ex_v > 0)]
    keep_p = p[(p.tb_n > 5) & (p.ex_v > 0)]
    g = A.gates(keep_r, keep_p, weeks, COINS[panel], HALF[panel], Wt=Wt)
    o["gates_without_thin_touch_or_zero_vol_exit"] = g
    print("no thin touch (<=5 trades) / zero-vol exit:", gl(g))
    # 3. bad-print exits: exit close more than 5 % away from both neighbouring closes
    bad = []
    for c, f in e.groupby("coin"):
        b = bars[c]
        j = f.j.to_numpy(int)
        cprev = b["c"][np.maximum(j - 1, 0)]
        cnext = b["c"][np.minimum(j + 1, len(b["c"]) - 1)]
        cx = b["c"][j]
        m = (np.abs(cx / cprev - 1) > 0.05) & (np.abs(cx / cnext - 1) > 0.05)
        for idx in f.index[m]:
            bad.append(idx)
    o["exits_bad_print_5pct"] = {"real": int(r.index.isin(bad).sum()), "P1": int(p.index.isin(bad).sum())}
    print("bad-print exits (>5 % from both neighbours):", o["exits_bad_print_5pct"])
    if bad:
        print(e.loc[bad, ["coin", "kind", "t0", "gross"]].assign(t0=lambda x: pd.to_datetime(x.t0, unit="ms")).to_string())
    # 4. extreme touch bars: excess beyond L > 5 % (sweep bars)
    s = np.where(e.side == "H", e.tb_h / e.L - 1, 1 - e.tb_l / e.L)
    e["excess"] = s
    xr = e[(e.control == "real") & (e.excess > 0.05)]
    o["real_touch_excess_gt_5pct"] = {"n": int(len(xr)), "gross_sum": float(xr.gross.sum()),
                                      "share_of_real_gross_sum": float(xr.gross.sum() / r.gross.sum()),
                                      "gross_mean": float(xr.gross.mean()) if len(xr) else None}
    g = A.gates(r[~r.index.isin(xr.index)], p[~(p.excess > 0.05) if "excess" in p else slice(None)] if False else
                e[(e.control == "P1") & (e.excess <= 0.05)], weeks, COINS[panel], HALF[panel], Wt=Wt)
    o["gates_without_touch_excess_gt_5pct"] = g
    print("touch excess > 5 % (real):", o["real_touch_excess_gt_5pct"])
    print("without excess > 5 % touches (real and P1):", gl(g))
    # 5. OX: exits inside the exchange-wide flat windows, and the delisting tails
    if panel == "OX":
        z = pd.read_csv(f"{A.SP}/research3/p2/data_ox/zero_volume_runs.csv")
        z = z[z.bars >= 3]
        zf = set()
        for _, row in z.iterrows():
            a = A.ts(row.first_bar)
            bb = A.ts(row.last_bar)
            zf.update((row.coin.replace("USDT", ""), t) for t in range(a, bb + 1, A.BAR))
        ex_t = (e.t0 + A.HZ["4h"] - A.BAR).to_numpy()
        inz = np.array([(c, int(t)) in zf for c, t in zip(e.coin, ex_t)])
        o["OX_exits_in_flat_runs_ge3"] = {"real": int((inz & (e.control == "real")).sum()),
                                          "P1": int((inz & (e.control == "P1")).sum())}
        print("exits in flat runs >= 3 bars:", o["OX_exits_in_flat_runs_ge3"])
        tails = {}
        for c in ("LUNA", "FTM", "MATIC", "LRC"):
            b = bars[c]
            wc = wk[(wk.coin == c) & wk.used]
            lastW = int(wc.W.max())
            a1, a2 = np.searchsorted(b["t"], lastW), np.searchsorted(b["t"], lastW + A.WK)
            rc = r[r.coin == c]
            tails[c] = {"last_used_week": str(pd.to_datetime(lastW, unit="ms").date()),
                        "effective_end": str(pd.to_datetime(b["end"], unit="ms")),
                        "last_week_traded_share": float((b["v"][a1:a2] > 0).mean()),
                        "last_week_bars": int(a2 - a1),
                        "real_4h_events_last_4_weeks": int((rc.W >= lastW - 3 * A.WK).sum()),
                        "real_4h_gross_mean_last_4_weeks": float(rc[rc.W >= lastW - 3 * A.WK].gross.mean())
                        if (rc.W >= lastW - 3 * A.WK).any() else None,
                        "real_4h_exit_after_eff_end": int((rc.t0 + A.HZ["4h"] > b["end"]).sum())}
        o["OX_delisting_tails"] = tails
        print("delisting tails", json.dumps(tails, indent=0))
    # 6. OT: the four audit-flagged wick coin-weeks and the two unreachable-PWL weeks
    if panel == "OT":
        flag = [("DOGE", "2020-02-03"), ("LTC", "2018-06-18"), ("NEO", "2017-12-18"), ("TRX", "2018-08-13")]
        fw = [(c, A.ts(w)) for c, w in flag]
        isf = np.array([(c, int(W)) in set(fw) for c, W in zip(e.coin, e.W)])
        g = A.gates(e[(e.control == "real") & ~isf], e[(e.control == "P1") & ~isf], weeks, COINS[panel], HALF[panel],
                    Wt=Wt)
        o["gates_without_audit_wick_weeks"] = g
        print("without the 4 audit wick coin-weeks (real and P1):", gl(g))
        # zero-volume share of the touch-to-exit window for DOGE / LINK (thin books)
        for c in ("DOGE", "LINK", "NEO"):
            b = bars[c]
            rc = r[r.coin == c]
            zs = []
            for t0 in rc.t0:
                i0, i1 = np.searchsorted(b["t"], t0), np.searchsorted(b["t"], t0 + A.HZ["4h"])
                zs.append(float((b["v"][i0:i1] == 0).mean()))
            o.setdefault("OT_zero_volume_share_touch_to_exit", {})[c] = {
                "mean": float(np.mean(zs)), "max": float(np.max(zs)), "n_events_gt_25pct": int(np.sum(np.array(zs) > 0.25))}
        print("zero-volume share in [touch, exit):", o["OT_zero_volume_share_touch_to_exit"])
    out[panel] = o
json.dump(out, open(f"{D}/c3_data.json", "w"), indent=1, default=float)
