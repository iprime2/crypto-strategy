import sys, math, datetime as dt
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1")
import numpy as np, engine as E
mk = E.load_market(E.NINE)
for j, c in enumerate(mk.coins):
    for i, d in enumerate(mk.days):
        if not np.isfinite(mk.CL[i, j]) or d < dt.date(2020, 1, 3): continue
        k = (E.d2ms(d) - mk.h0) // E.H - 1
        hc = mk.HC[k, j]
        if np.isfinite(hc) and abs(math.log(hc) - mk.CL[i, j]) > 1e-9:
            print(c, d, math.exp(mk.CL[i, j]), hc, "P01", mk.HC[k+1, j])
