"""C1: my events vs the run's event files (row by row), and the four gating numbers from my events vs results.json."""
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
    ev, wk = res[(panel, "base")]
    ok = ev[ev.status == "ok"].copy()
    used = set(zip(wk.coin[wk.used], wk.W[wk.used]))
    # P3 primary sample: touch inside a used Monday coin-week of the same coin
    isp3 = ok.control == "P3"
    inu = np.array([(c, int(m)) in used for c, m in zip(ok.coin, ok.mw)])
    ok = ok[~isp3 | inu]
    theirs = pd.read_csv(f"{A.RUN}/events_{panel}.csv.gz", float_precision="round_trip")
    theirs["te"] = (pd.to_datetime(theirs.entry_time) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)
    ok["level_kind"] = ok.kind
    key = ["coin", "level_kind", "horizon", "te"]
    ok["te"] = ok.t0
    m = theirs.merge(ok[key + ["gross", "L", "px"]], on=key, how="outer", indicator=True)
    both = m[m._merge == "both"]
    o = {"rows_theirs": int(len(theirs)), "rows_mine": int(len(ok)),
         "only_theirs": int((m._merge == "left_only").sum()), "only_mine": int((m._merge == "right_only").sum()),
         "max_abs_gross_diff": float((both.gross_bps - both.gross).abs().max()),
         "max_rel_level_diff": float((both.level_px / both.L - 1).abs().max()),
         "max_abs_exit_diff_rel": float((both.exit_px / both.px - 1).abs().max())}
    if o["only_theirs"] or o["only_mine"]:
        o["examples_only"] = m[m._merge != "both"].head(10)[key + ["_merge"]].astype(str).values.tolist()
    # drops by status
    o["drops"] = ev[ev.status != "ok"].groupby(["control", "horizon", "status"]).size().astype(int).to_dict()
    o["drops"] = {"|".join(k): v for k, v in o["drops"].items()}
    # gates from my events
    weeks = sorted(wk.W[wk.used].unique())
    r4 = ok[(ok.control == "real") & (ok.horizon == "4h")]
    p4 = ok[(ok.control == "P1") & (ok.horizon == "4h")]
    g = A.gates(r4, p4, weeks, COINS[panel], HALF[panel])
    gr = R[panel]["gating_4h"]
    ref = dict(net=gr["1_net"]["real_net_base"], p_net=gr["1_net"]["p_net_le0"], diff=gr["2_diff_P1"]["diff_gross"],
               p_diff=gr["2_diff_P1"]["p_diff_le0"], h1=gr["3_halves"]["H1_net_base"],
               h2=gr["3_halves"]["H2_net_base"], coins_pos=gr["4_coins"]["coins_pos_net_base"],
               n=R[panel]["cells"]["4h"]["real"]["n"], n_p1=R[panel]["cells"]["4h"]["P1"]["n"])
    o["gates_mine"] = g
    o["gates_results_json"] = ref
    o["max_abs_delta_gating"] = max(abs(g[k] - ref[k]) for k in ref)
    out[panel] = o
    print(panel, json.dumps({k: v for k, v in o.items() if k not in ("gates_mine", "gates_results_json")}, default=str))
    print("  mine:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()})
    print("  ref :", ref)
json.dump(out, open(f"{D}/c1_reproduce.json", "w"), indent=1, default=str)
