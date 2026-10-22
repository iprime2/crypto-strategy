import sys, json, datetime as dt
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools2")
import numpy as np, data
SP = data.SP
pool = json.load(open(f"{SP}/universe/pool_all.json"))
p = data.load_binance(coins=pool)
C, Q = p.C, p.Q
T, N = C.shape
qpos = np.isfinite(Q) & (Q > 0) & np.isfinite(C)
# first / last q>0
first = np.array([np.argmax(qpos[:, j]) if qpos[:, j].any() else T for j in range(N)])
last = np.array([T - 1 - np.argmax(qpos[::-1, j]) if qpos[:, j].any() else -1 for j in range(N)])
age = np.cumsum(np.isfinite(C), axis=0)
def med30(t, use_zero=True):
    w = Q[t-29:t+1].copy()
    return np.nanmedian(w, axis=0)
for d in [dt.date(2020,4,30), dt.date(2021,1,1), dt.date(2022,1,1), dt.date(2023,1,1), dt.date(2024,1,1), dt.date(2025,1,1), dt.date(2026,1,1)]:
    t = p.idx[d]
    m = med30(t)
    cand = qpos[t]
    order = np.argsort(-np.where(cand & np.isfinite(m), m, -1))
    print(d, "top-25 any age:", [(p.coins[j], int(age[t, j]), (round(m[j]/1e6) if np.isfinite(m[j]) else None)) for j in order[:25]])
    el = cand & (age[t] >= (121 if d.year == 2020 else 365))
    order = np.argsort(-np.where(el & np.isfinite(m), m, -1))
    print("   eligible top-20:", [(p.coins[j], (round(m[j]/1e6) if np.isfinite(m[j]) else None)) for j in order[:20]])
