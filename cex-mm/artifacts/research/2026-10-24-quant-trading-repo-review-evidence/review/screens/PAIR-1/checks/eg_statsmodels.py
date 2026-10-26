"""Run statsmodels 0.14.4 coint on the dumped windows (PYTHONPATH=_pkgs/lib) and compare with the engine's p."""
import sys, warnings
warnings.simplefilter("ignore")
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1/_pkgs/lib")
import numpy as np
from statsmodels.tsa.stattools import coint
z = np.load(sys.argv[1])
ps = np.array([coint(y, x, trend="c", maxlag=10, autolag="aic")[1] for y, x in zip(z["Y"], z["X"])])
d = np.abs(ps - z["P"])
print(f"n {len(ps)}  max|dp| {d.max():.3e}  mean|dp| {d.mean():.3e}  agree on p<0.05: {np.mean((ps<0.05)==(z['P']<0.05)):.4f}  agree on p<=0.20: {np.mean((ps<=0.2)==(z['P']<=0.2)):.4f}")
