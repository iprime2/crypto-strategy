import sys
sys.path.insert(0, ".")
from run_primary import *
for c in ["LTC", "SOL", "XRP"]:
    j = p.ci[c]
    bad = [p.dates[t] for t in range(len(p.dates)) if p.dates[t] >= dt.date(2020, 4, 30) and not qpos[t, j] and t <= last[j]]
    print(c, "non-candidate days inside life:", bad[:20], [(p0.C[p.idx[d], j], p0.Q[p.idx[d], j]) for d in bad[:6]])
for c in ["SOL", "BNB", "XRP", "BCH"]:
    j = p.ci[c]
    lr = np.log(p.C[1:, j] / p.C[:-1, j])
    t = np.nanargmax(np.abs(lr)) + 1
    print(c, "max |logret| on", p.dates[t], p.C[t - 1, j], "->", p.C[t, j])
# funding of BNB by year: share nonzero
j = p.ci["BNB"]
for y in range(2020, 2027):
    m = np.array([d.year == y for d in p.dates]) & np.isfinite(p.C[:, j])
    print("BNB", y, "funding nonzero share", round((p.F[m, j] != 0).mean(), 3), "ann", round(p.F[m, j].mean() * 365, 4))
j = p.ci["SOL"]
for y in range(2021, 2027):
    m = np.array([d.year == y for d in p.dates]) & np.isfinite(p.C[:, j])
    print("SOL", y, "funding nonzero share", round((p.F[m, j] != 0).mean(), 3), "ann", round(p.F[m, j].mean() * 365, 4))
