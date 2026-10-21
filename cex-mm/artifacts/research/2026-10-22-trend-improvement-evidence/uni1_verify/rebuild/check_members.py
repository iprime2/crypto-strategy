import sys
sys.path.insert(0, ".")
from run_primary import *
cfg = dict(rank_pop="eligible", start_elig="any", nmode="valid", reset_mode="calendar")
r, mask, log = go(cfg, DAILY)
T, N = p.C.shape
yrs = np.array([d.year for d in p.dates])
mem = np.where(mask.any(0))[0]
print("ever-members:", [p.coins[j] for j in mem])
for j in mem:
    c = p.coins[j]
    m = mask[:, j]
    F = p.F[:, j]
    fin = np.isfinite(p.C[:, j])
    # funding coverage while member: share of member days with F != 0
    cov = (F[m] != 0).mean()
    ann = F[m].mean() * 365
    # same-period funding for BTC as reference
    fb = p.F[m, p.ci["BTC"]].mean() * 365
    rr = np.diff(np.log(p.C[:, j]))[m[1:]]
    rr = rr[np.isfinite(rr)]
    print(f"{c:9s} member days {m.sum():5d} first {p.dates[np.argmax(m)]} last {p.dates[len(m)-1-np.argmax(m[::-1])]} funding nonzero share {cov:.3f} ann {ann:+.3f} (BTC same days {fb:+.3f}) max|logret| {np.abs(rr).max():.3f} zero-q member days {int((m & ~qpos[:, j]).sum())}")
# coins in the whole pool with no funding at all
nof = [p.coins[j] for j in range(N) if (p.F[:, j] != 0).sum() == 0 and np.isfinite(p.C[:, j]).sum() > 0]
print("pool coins with zero funding everywhere:", len(nof))
