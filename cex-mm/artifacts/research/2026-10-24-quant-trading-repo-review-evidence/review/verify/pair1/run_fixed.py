import sys, json, importlib.util, datetime as dt
V = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/verify/pair1"
S = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1"
which = sys.argv[1]
spec = importlib.util.spec_from_file_location("engine", f"{V}/engine_fixed.py" if which == "fixed" else f"{S}/engine.py")
E = importlib.util.module_from_spec(spec); sys.modules["engine"] = E; spec.loader.exec_module(E)
spec2 = importlib.util.spec_from_file_location("run", f"{S}/run.py")
R = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(R)
import numpy as np
mk = E.load_market(E.NINE)
pairs = [(i, j) for i in range(9) for j in range(i + 1, 9)]
out = {}
for lab, prm in [("base", E.Params()), ("stress", E.Params(cost_bps=15.31))]:
    s = E.Sim(mk, pairs, prm, R.START, R.END, {}).run()
    o, tt = R.scorecard(s, lab)
    out[lab] = {k: o.get(k) for k in ("n_trades", "mean_net_bps", "boot_P_mean_le0", "boot_ci95", "H1_mean_net_bps", "H2_mean_net_bps",
                                     "coins_positive", "sharpe", "sharpe_2020-05..2023-12", "sharpe_2024-01..2026-09", "F5_P_sharpe_le0", "final_equity")}
    out[lab]["verdict"] = R.verdict(o)
print(which, json.dumps(out, indent=1, default=str))
