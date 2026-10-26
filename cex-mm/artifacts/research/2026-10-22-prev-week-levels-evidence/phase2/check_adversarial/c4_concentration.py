"""C4: concentration (sensitivity only). Top 1 % events, single weeks (crash weeks), single coins; gates recomputed with
the 5 largest weeks removed (by real 4 h net sum: largest positive, largest negative, largest absolute), and
leave-one-coin-out. Removing a week removes it from the bootstrap and drops its real and P1 events."""
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
CRASH = {"OT": ["2017-12-04", "2017-12-18", "2018-01-15", "2018-11-12", "2018-11-19", "2019-06-24", "2019-09-23",
                "2020-03-09", "2020-03-16"],
         "OX": ["2022-01-17", "2022-05-09", "2022-06-13", "2022-11-07", "2024-08-05", "2025-02-03", "2025-04-07",
                "2025-10-06"]}


def gl(g):
    return (f"net {g['net']:7.2f} P {g['p_net']:.4f} | diff {g['diff']:6.2f} P {g['p_diff']:.4f} | H1 {g['h1']:6.2f} "
            f"H2 {g['h2']:6.2f} | coins {g['coins_pos']}/{g['need']} | n {g['n']} | all {g['all']}")


def d(w):
    return str(pd.to_datetime(int(w), unit="ms").date())


out = {}
for panel in ("OT", "OX"):
    o = {}
    ev, wk = res[(panel, "base")]
    weeks = np.array(sorted(wk.W[wk.used].unique()), dtype=np.int64)
    e = ev[(ev.status == "ok") & (ev.horizon == "4h") & ev.control.isin(["real", "P1"])].copy()
    e["net"] = e.gross - 14.62
    r, p = e[e.control == "real"], e[e.control == "P1"]
    base = A.gates(r, p, weeks, COINS[panel], HALF[panel])
    print("=" * 20, panel, "\nbase", gl(base))
    # events
    n = len(r)
    k = max(1, int(round(0.01 * n)))
    srt = r.sort_values("net", ascending=False)
    o["top1pct"] = {"k": k, "net_sum_total": float(r.net.sum()), "net_sum_top_k": float(srt.net.head(k).sum()),
                    "share_of_net_sum_top_k": float(srt.net.head(k).sum() / r.net.sum()),
                    "net_mean_without_top_k": float(srt.net.iloc[k:].mean()),
                    "net_mean_without_top_and_bottom_k": float(srt.net.iloc[k:n - k].mean()),
                    "median_net": float(r.net.median())}
    # P1 trimmed the same way, for the diff
    ps = p.sort_values("gross", ascending=False)
    kp = max(1, int(round(0.01 * len(p))))
    o["top1pct"]["diff_trim_both_sides_1pct"] = float(srt.gross.iloc[k:n - k].mean() - ps.gross.iloc[kp:len(p) - kp].mean())
    print("top 1 %:", json.dumps(o["top1pct"]))
    # weeks
    ws = r.groupby("W").net.agg(["sum", "count"]).sort_values("sum")
    o["weeks_top5_positive"] = [(d(w), float(v), int(c)) for w, (v, c) in ws.tail(5)[::-1].iterrows()]
    o["weeks_top5_negative"] = [(d(w), float(v), int(c)) for w, (v, c) in ws.head(5).iterrows()]
    o["share_net_sum_top5_positive_weeks"] = float(ws["sum"].tail(5).sum() / r.net.sum())
    print("top 5 + weeks:", o["weeks_top5_positive"], "share of net sum", round(o["share_net_sum_top5_positive_weeks"], 3))
    print("top 5 - weeks:", o["weeks_top5_negative"])
    absw = ws.reindex(ws["sum"].abs().sort_values(ascending=False).index)
    sets = {"excl_5_largest_positive_weeks": ws.tail(5).index, "excl_5_largest_negative_weeks": ws.head(5).index,
            "excl_5_largest_abs_weeks": absw.head(5).index,
            "excl_5_largest_positive_and_5_negative": ws.tail(5).index.append(ws.head(5).index)}
    gx = {}
    for name, ix in sets.items():
        keepw = weeks[~np.isin(weeks, np.asarray(ix, dtype=np.int64))]
        g = A.gates(r[~r.W.isin(ix)], p[~p.W.isin(ix)], keepw, COINS[panel], HALF[panel])
        g["weeks_removed"] = [d(w) for w in ix]
        gx[name] = g
        print(f"{name:40s}", gl(g))
    o["gates_excluding_weeks"] = gx
    # crash weeks
    cw = {}
    for w in CRASH[panel]:
        W = A.ts(w)
        f = r[r.W == W]
        cw[w] = {"n": int(len(f)), "net_sum": float(f.net.sum()), "share_of_net_sum": float(f.net.sum() / r.net.sum())}
    o["crash_weeks"] = cw
    allc = [A.ts(w) for w in CRASH[panel]]
    keepw = weeks[~np.isin(weeks, allc)]
    g = A.gates(r[~r.W.isin(allc)], p[~p.W.isin(allc)], keepw, COINS[panel], HALF[panel])
    o["gates_excluding_crash_weeks"] = g
    print("crash weeks:", json.dumps(cw))
    print(f"{'excl all listed crash weeks':40s}", gl(g))
    # coins: leave one out
    loo = {}
    for c in COINS[panel]:
        cs = [x for x in COINS[panel] if x != c]
        g = A.gates(r[r.coin != c], p[p.coin != c], weeks, cs, HALF[panel])
        loo[c] = {k2: g[k2] for k2 in ("net", "p_net", "diff", "p_diff", "h1", "h2", "coins_pos", "need", "all")}
    o["leave_one_coin_out"] = loo
    print("leave one coin out net range", round(min(v["net"] for v in loo.values()), 2),
          round(max(v["net"] for v in loo.values()), 2), "| any change of all-pass:",
          [c for c, v in loo.items() if v["all"] != base["all"]])
    for c, v in loo.items():
        if v["all"] != base["all"] or abs(v["net"] - base["net"]) > 3:
            print("   ", c, {k2: (round(x, 3) if isinstance(x, float) else x) for k2, x in v.items()})
    # coin share of the net sum
    cs = r.groupby("coin").net.sum().sort_values(ascending=False)
    o["coin_net_sum_share"] = {c: float(v / r.net.sum()) for c, v in cs.items()}
    print("coin share of net sum:", {c: round(v, 3) for c, v in o["coin_net_sum_share"].items()})
    out[panel] = o
json.dump(out, open(f"{D}/c4_concentration.json", "w"), indent=1, default=float)
