"""Dump 400 real (pair, Monday) formation windows of the nine with this engine's EG p, for a statsmodels cross-check."""
import datetime as dt, sys, time
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1")
import numpy as np, engine as E
t0 = time.time()
mk = E.load_market(E.NINE)
print("loaded", len(mk.days), mk.days[0], mk.days[-1], f"{time.time()-t0:.1f}s", mk.hourly_rows)
pairs = [(i, j) for i in range(9) for j in range(i + 1, 9)]
mondays = [d for d in mk.days if d.weekday() == 0 and d >= dt.date(2020, 6, 29) and d <= dt.date(2026, 9, 28)]
rng = np.random.default_rng(5)
Y, X, P, T = [], [], [], []
t1 = time.time(); n = 0
while len(P) < 400:
    pair = pairs[rng.integers(len(pairs))]; M = mondays[rng.integers(len(mondays))]
    i = mk.di(M); xi, yi = pair
    ly, lx = mk.CL[i-179:i+1, yi], mk.CL[i-179:i+1, xi]
    if not (np.isfinite(ly).all() and np.isfinite(lx).all()):
        continue
    f = E.formation(ly, lx)
    Y.append(ly); X.append(lx); P.append(f.p); T.append(f.b)
np.savez(sys.argv[1], Y=np.array(Y), X=np.array(X), P=np.array(P), B=np.array(T))
print("dumped", len(P), "share p<0.05:", float(np.mean(np.array(P) < 0.05)))
