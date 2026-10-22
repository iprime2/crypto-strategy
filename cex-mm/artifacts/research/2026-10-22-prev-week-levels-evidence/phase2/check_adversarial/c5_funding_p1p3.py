"""C5: (a) OX funding over each T hold (not in the plan's cost model; information), (b) P1 / P3 construction checks
against the plan text: P1 level = O * exp(+-m * D) of the same coin-week, same side; P3 level = max high / min low of
the 168 h before a Thursday 12:00 anchor, touch inside [A, A + 168 h); (c) weeks where the week open lies outside
[PWL, PWH] (the real level is then 'touched' on the first bar at a price the market had already passed)."""
import glob
import json
import os
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

# (a) funding on OX
ev, wk = res[("OX", "base")]
weeks = sorted(wk.W[wk.used].unique())
e = ev[(ev.status == "ok") & (ev.horizon == "4h") & ev.control.isin(["real", "P1"])].copy()
fund = {}
missing = {}
for c in A.OX_COINS:
    files = sorted(set(glob.glob(f"{A.SP}/universe/cache_all/binance-{c}USDT-fundingRate-*.csv"))
                   | set(glob.glob(f"{A.SP}/universe/cache/binance-{c}USDT-fundingRate-*.csv")))
    fr = pd.concat([pd.read_csv(f) for f in files])
    fr["t"] = (fr.calc_time // 1000 * 1000).astype(np.int64)  # calc_time is a few ms after the funding instant
    fr = fr.drop_duplicates("t").sort_values("t")
    fund[c] = (fr.t.to_numpy(), fr.last_funding_rate.to_numpy(float))
cost = np.zeros(len(e))
nf = np.zeros(len(e), dtype=int)
for i, (c, t0, s) in enumerate(zip(e.coin, e.t0, e.s)):
    t, rate = fund[c]
    a, b = np.searchsorted(t, t0, side="right"), np.searchsorted(t, t0 + A.HZ["4h"], side="right")
    # a long pays positive funding: P&L in bps = -s * rate * 1e4 for each funding instant inside (t0, t0 + 4 h]
    cost[i] = (-s * rate[a:b] * 1e4).sum()
    nf[i] = b - a
e["funding_bps"] = cost
e["g_f"] = e.gross + e.funding_bps
r, p = e[e.control == "real"], e[e.control == "P1"]
g0 = A.gates(r, p, weeks, A.OX_COINS, HALF["OX"])
g1 = A.gates(r, p, weeks, A.OX_COINS, HALF["OX"], col="g_f")
out["OX_funding"] = {"real_mean_funding_pnl_bps": float(r.funding_bps.mean()),
                     "P1_mean_funding_pnl_bps": float(p.funding_bps.mean()),
                     "real_share_crossing_a_funding_instant": float((nf[e.control.to_numpy() == "real"] > 0).mean()),
                     "real_funding_pnl_p1_p99": [float(np.quantile(r.funding_bps, 0.01)),
                                                 float(np.quantile(r.funding_bps, 0.99))],
                     "gates_without_funding": g0, "gates_with_funding": g1}
print("OX funding:", {k: v for k, v in out["OX_funding"].items() if not k.startswith("gates")})
print("  with funding: net %.2f P %.4f diff %.2f P %.4f H1 %.2f H2 %.2f coins %d all %s" % (
    g1["net"], g1["p_net"], g1["diff"], g1["p_diff"], g1["h1"], g1["h2"], g1["coins_pos"], g1["all"]))

# (b) P1 / P3 construction from the bars, independent of the event engine
for panel in ("OT", "OX"):
    bars = {c: A.load(panel, c) for c in COINS[panel]}
    ev, wk = res[(panel, "base")]
    e = ev[(ev.horizon == "4h")].copy()
    chk = {"P1_level_err_max": 0.0, "P1_wrong_side": 0, "P3_level_err_max": 0.0, "P3_touch_outside_window": 0,
           "real_touch_outside_week": 0, "exit_not_after_entry": 0, "P1_m_counts": {}}
    for c, g in e.groupby("coin"):
        b = bars[c]
        t = b["t"]
        for W, gw in g[g.control != "P3"].groupby("W"):
            a0, a1, a2 = np.searchsorted(t, [W - A.WK, W, W + A.WK])
            pwh, pwl, O = b["h"][a0:a1].max(), b["l"][a0:a1].min(), b["o"][a1]
            for _, row in gw.iterrows():
                if row.control == "P1":
                    m = float(row.kind.split("_")[1])
                    exp = O * np.exp(m * np.log(pwh / O)) if row.side == "H" else O * np.exp(-m * np.log(O / pwl))
                    chk["P1_level_err_max"] = max(chk["P1_level_err_max"], abs(row.L / exp - 1))
                    chk["P1_wrong_side"] += int((row.side == "H" and row.L <= O) or (row.side == "L" and row.L >= O))
                    chk["P1_m_counts"][row.kind] = chk["P1_m_counts"].get(row.kind, 0) + 1
                if not (W <= row.t0 < W + A.WK):
                    chk["real_touch_outside_week"] += 1
        for Aa, ga in g[g.control == "P3"].groupby("W"):
            a0, a1 = np.searchsorted(t, [Aa - A.WK, Aa])
            for _, row in ga.iterrows():
                exp = b["h"][a0:a1].max() if row.side == "H" else b["l"][a0:a1].min()
                chk["P3_level_err_max"] = max(chk["P3_level_err_max"], abs(row.L / exp - 1))
                chk["P3_touch_outside_window"] += int(not (Aa <= row.t0 < Aa + A.WK))
        assert ((g[g.control == "P3"].W - A.MON0) % A.WK == 84 * A.H).all(), "P3 anchor not Thursday 12:00"
    ok = ev[ev.status == "ok"]
    chk["exit_not_after_entry"] = int((A.HZ["4h"] <= 0))  # exits are t0 + h by construction; see c1 for row match
    # (c) week open outside [PWL, PWH]
    wo = 0
    wo_events = []
    for c in COINS[panel]:
        b = bars[c]
        t = b["t"]
        for W in wk[(wk.coin == c) & wk.used].W:
            a0, a1 = np.searchsorted(t, [W - A.WK, W])
            pwh, pwl, O = b["h"][a0:a1].max(), b["l"][a0:a1].min(), b["o"][a1]
            if O > pwh or O < pwl:
                wo += 1
                wo_events.append((c, str(pd.to_datetime(int(W), unit="ms").date()), float(O), float(pwh), float(pwl)))
    chk["weeks_open_outside_prior_range"] = wo
    chk["weeks_open_outside_examples"] = wo_events[:10]
    out[panel + "_construction"] = chk
    print(panel, json.dumps(chk, default=str))
json.dump(out, open(f"{D}/c5_funding_p1p3.json", "w"), indent=1, default=float)
