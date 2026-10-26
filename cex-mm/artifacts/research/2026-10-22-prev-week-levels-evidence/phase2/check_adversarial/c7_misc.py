"""C7: (a) halves assigned by touch time instead of week start; (b) real - P3 at 4 h from my events vs results.json;
(c) OT by side (the PWL short leg was not tradable on Binance spot before margin, 2019-07); (d) weekly correlation of
real 4 h net between OX and Phase 1 panel A (same calendar, different coins); (e) daily Sharpe check."""
import json
import pickle
import sys

import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv"
sys.path.insert(0, D)
import adv_lib as A  # noqa: E402

R = json.load(open(f"{A.RUN}/results.json"))
res = pickle.load(open(f"{D}/events_adv.pkl", "rb"))
HALF = {"OT": A.ts("2019-01-01"), "OX": A.ts("2024-05-01")}
COINS = {"OT": A.OT_COINS, "OX": A.OX_COINS}
out = {}
for panel in ("OT", "OX"):
    o = {}
    ev, wk = res[(panel, "base")]
    weeks = sorted(wk.W[wk.used].unique())
    used = set(zip(wk.coin[wk.used], wk.W[wk.used]))
    ok = ev[(ev.status == "ok") & (ev.horizon == "4h")].copy()
    r, p1 = ok[ok.control == "real"], ok[ok.control == "P1"]
    p3 = ok[ok.control == "P3"]
    p3 = p3[[(c, int(m)) in used for c, m in zip(p3.coin, p3.mw)]]
    # (a) halves by touch time
    h1 = r[r.t0 < HALF[panel]].gross.mean() - 14.62
    h2 = r[r.t0 >= HALF[panel]].gross.mean() - 14.62
    o["halves_by_touch_time"] = {"H1": float(h1), "H2": float(h2), "n1": int((r.t0 < HALF[panel]).sum()),
                                 "n2": int((r.t0 >= HALF[panel]).sum()),
                                 "results_json_by_week_start": [R[panel]["gating_4h"]["3_halves"]["H1_net_base"],
                                                                R[panel]["gating_4h"]["3_halves"]["H2_net_base"]]}
    # (b) real - P3
    Wt = A.boot_W(len(weeks))
    g = A.gates(r, p3, weeks, COINS[panel], HALF[panel], Wt=Wt)
    o["real_minus_P3"] = {"mine": g["diff"], "p_mine": g["p_diff"], "n_P3": int(len(p3)),
                          "results_json": R[panel]["tests"]["4h"]["diff"]["P3"]["diff_gross"],
                          "results_json_p": R[panel]["tests"]["4h"]["diff"]["P3"]["p_diff_le0"]}
    # (c) by side
    o["by_side_net"] = {s: {"n": int((r.side == s).sum()), "net": float(r[r.side == s].gross.mean() - 14.62),
                            "diff_vs_P1_same_side": float(r[r.side == s].gross.mean() - p1[p1.side == s].gross.mean())}
                        for s in ("H", "L")}
    if panel == "OT":
        pre = r[(r.side == "L") & (r.t0 < A.ts("2019-07-11"))]
        o["OT_PWL_shorts_before_margin_2019-07-11"] = {"n": int(len(pre)), "net": float(pre.gross.mean() - 14.62)}
        gH = A.gates(r[r.side == "H"], p1[p1.side == "H"], weeks, COINS[panel], HALF[panel], Wt=Wt)
        o["OT_long_only_gates"] = gH
    # (e) daily Sharpe (base), Phase 1 convention
    d0 = pd.to_datetime(int(wk.W.min()), unit="ms").normalize()
    d1 = pd.to_datetime(int(wk.W.max()) + 8 * A.D, unit="ms").normalize()
    cal = pd.date_range(d0, d1, freq="D")
    day = pd.to_datetime(r.t0 + A.HZ["4h"], unit="ms").dt.normalize()
    ser = (r.gross - 14.62).groupby(day.values).sum().reindex(cal, fill_value=0.0)
    o["daily_sharpe_4h_base"] = {"mine": float(ser.mean() / ser.std(ddof=1) * np.sqrt(365)),
                                 "results_json": R[panel]["daily_sharpe"]["4h"]["base"]}
    out[panel] = o
    print(panel, json.dumps({k: v for k, v in o.items() if k != "OT_long_only_gates"}, default=float))
    if panel == "OT":
        gH = o["OT_long_only_gates"]
        print("  OT long-only (PWH side): net %.2f P %.4f diff %.2f P %.4f H1 %.2f H2 %.2f coins %d/%d all %s" % (
            gH["net"], gH["p_net"], gH["diff"], gH["p_diff"], gH["h1"], gH["h2"], gH["coins_pos"], gH["need"], gH["all"]))
# (d) OX vs A weekly correlation
ea = pd.read_csv(f"{A.RUN}/events_A.csv.gz")
ea = ea[(ea.level_kind.isin(["PWH", "PWL"])) & (ea.horizon == "4h")]
wa = ea.groupby("week_start").net_base.sum()
ev, wk = res[("OX", "base")]
rx = ev[(ev.status == "ok") & (ev.horizon == "4h") & (ev.control == "real")].copy()
rx["week_start"] = pd.to_datetime(rx.W, unit="ms").dt.strftime("%Y-%m-%d")
wx = (rx.gross - 14.62).groupby(rx.week_start).sum()
j = pd.concat([wa.rename("A"), wx.rename("OX")], axis=1).dropna()
out["OX_vs_A_weekly_net_corr"] = {"n_weeks": int(len(j)), "pearson": float(j.corr().iloc[0, 1]),
                                  "spearman": float(j.corr(method="spearman").iloc[0, 1]),
                                  "A_top5_weeks": wa.sort_values().tail(5).index.tolist(),
                                  "OX_top5_weeks": wx.sort_values().tail(5).index.tolist()}
print("OX vs A:", out["OX_vs_A_weekly_net_corr"])
json.dump(out, open(f"{D}/c7_misc.json", "w"), indent=1, default=float)
