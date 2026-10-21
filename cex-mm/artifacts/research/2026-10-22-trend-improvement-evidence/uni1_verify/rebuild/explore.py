import sys, json, datetime as dt
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools2")
import numpy as np, data
SP = data.SP
pool = json.load(open(f"{SP}/universe/pool_all.json"))
p = data.load_binance(coins=pool)
print(len(p.dates), p.dates[0], p.dates[-1], len(p.coins))
C, Q = p.C, p.Q
fin = np.isfinite(C)
print("Q finite where C finite:", np.isfinite(Q[fin]).mean(), "Q==0 share", (Q[fin]==0).mean())
# zombies: rows with C finite and Q==0
z = fin & (Q == 0)
zc = z.sum(0)
order = np.argsort(-zc)
print("coins with zero-volume rows:", [(p.coins[j], int(zc[j])) for j in order[:30] if zc[j] > 0])
# last day with q>0 vs last finite close
for c in ["FTT","SC","RAY","FTM","LUNA","EOS","XMR","MATIC","SRM","BTS","ANT","WAVES","OMG"]:
    if c not in p.ci: print(c, "missing"); continue
    j = p.ci[c]
    iq = np.where(np.isfinite(Q[:, j]) & (Q[:, j] > 0))[0]; ic = np.where(fin[:, j])[0]
    print(c, "first", p.dates[ic[0]], "last close", p.dates[ic[-1]], "last q>0", p.dates[iq[-1]] if len(iq) else None, "close at lastq", C[iq[-1], j] if len(iq) else None, "interior zero-q days", int(((Q[ic[0]:iq[-1]+1, j] == 0) & fin[ic[0]:iq[-1]+1, j]).sum()) if len(iq) else None)
