import json, os, math, numpy as np
from collections import defaultdict
O = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/OPT-W1 weekly short ATM straddle on Delta BTC/ETH"
W = [w for w in json.load(open(os.path.join(O, "out", "weeks.json"))) if not w.get("skip")]
def pnl(w, h=0.05):
    s0, ST, K = w["s0"], w["settle"], w["K"]; tot = 0
    for m, intr in ((w["mc"], max(ST - K, 0)), (w["mp"], max(K - ST, 0))):
        p = m * (1 - h); tot += p - intr - min(1e-4 * s0, 0.035 * p) * 1.18 - (1e-4 * ST * 1.18 if intr > 0 else 0)
    return tot / s0 * 1e4
g = defaultdict(list)
for w in W: g[w["expiry"]].append(pnl(w))
ks = sorted(g); pool = np.array([np.mean(g[k]) for k in ks])
print("n weeks", len(ks), "pooled mean %.2f t %.2f" % (pool.mean(), pool.mean() / (pool.std(ddof=1) / math.sqrt(len(pool)))))
S = np.array([sum(g[k]) for k in ks]); C = np.array([len(g[k]) for k in ks])
idx = np.random.default_rng(11).integers(0, len(ks), size=(2000, len(ks)))
b = S[idx].sum(1) / C[idx].sum(1)
print("per-trade mean %.2f P %.4f" % (S.sum() / C.sum(), (b <= 0).mean()))
gaps = sorted(set((ks[i + 1] - ks[i]) // 86400 for i in range(len(ks) - 1))); print("gaps between expiries (days)", gaps)
for u in ("BTC", "ETH"):
    x = [pnl(w) for w in W if w["underlying"] == u]; print(u, len(x), "mean %.2f" % np.mean(x))
