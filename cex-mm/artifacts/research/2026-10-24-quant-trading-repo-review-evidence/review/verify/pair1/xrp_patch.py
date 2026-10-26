import sys, math, datetime as dt, importlib.util
S = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1"
spec = importlib.util.spec_from_file_location("engine", f"{S}/engine.py"); E = importlib.util.module_from_spec(spec); sys.modules["engine"] = E; spec.loader.exec_module(E)
import numpy as np
mk = E.load_market(E.NINE)
pairs = [(i, j) for i in range(9) for j in range(i + 1, 9)]
base = E.Sim(mk, pairs, E.Params(), dt.date(2020, 5, 1), dt.date(2026, 9, 30), {}).run()
j = mk.coins.index("XRP")
mk.CL[mk.di(dt.date(2020, 1, 17)), j] = math.log(0.2290); mk.CL[mk.di(dt.date(2020, 1, 18)), j] = math.log(0.2393)
pat = E.Sim(mk, pairs, E.Params(), dt.date(2020, 5, 1), dt.date(2026, 9, 30), {}).run()
A = [(t.pair, t.d_entry, t.d_exit, round(t.pnl_px, 12)) for t in base.trades]; B = [(t.pair, t.d_entry, t.d_exit, round(t.pnl_px, 12)) for t in pat.trades]
print("trades", len(A), len(B), "identical", A == B)
print("selections differ on Mondays:", [(d, S1, S2) for (d, S1), (_, S2) in zip(base.formations_used, pat.formations_used) if S1 != S2])
