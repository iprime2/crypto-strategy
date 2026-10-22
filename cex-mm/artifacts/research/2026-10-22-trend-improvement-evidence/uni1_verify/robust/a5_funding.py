"""(5) Delta-funding stress: per coin-day funding = max(Binance archive, Delta 2025-26 mean daily fraction) for coins with a Delta
record (research2/funding_summary.json '<SYM>USD|all' -> 'ann' %/yr); other coins Binance x 1.5 (S1: positive rows only, i.e. adverse
to longs; S2: all rows x 1.5). S0 = harness A6 (floor on the Delta coins only, others unchanged). Applied identically to UNI-1 and static-24."""
from common import *
c = ctx()
fs = json.load(open(f"{data.SP}/research2/funding_summary.json"))
F0 = c.pc.F
floor = {}
for j, cn in enumerate(c.coins):
    rec = fs.get(f"{cn}USD|all")
    if rec and "ann" in rec:
        floor[j] = float(rec["ann"]) / 100 / 365
print("Delta records:", {c.coins[j]: round(v * 365 * 100, 2) for j, v in floor.items()})
def stress(mode):
    F = F0.copy()
    for j in range(c.N):
        if j in floor:
            F[:, j] = np.where(c.pos[:, j], np.maximum(F0[:, j], floor[j]), 0.0)
        elif mode == "S1":
            F[:, j] = np.where(F0[:, j] > 0, 1.5 * F0[:, j], F0[:, j])
        elif mode == "S2":
            F[:, j] = 1.5 * F0[:, j]
    return F
out = {}
for name, cad in CADS.items():
    U, _ = U_uni1(c, cad); W = W_of(c, cad, U); Wb = W_of(c, cad, U_static24(c))
    print(f"\n=== {name}")
    for mode in ("none", "S0", "S1", "S2"):
        F = None if mode == "none" else stress(mode)
        r = run(c, cad, W, F=F); b = run(c, cad, Wb, F=F)
        bt = boot(r, b, POST, None, r); bf = boot(r, b, None, None, r)
        yrs = len(r["rets"]) / 365
        fu, fb = r["fund_frac"].sum() / yrs, b["fund_frac"].sum() / yrs
        mp = mask(r, POST); fup, fbp = r["fund_frac"][mp].sum() / (mp.sum() / 365), b["fund_frac"][mp].sum() / (mp.sum() / 365)
        print(f"  {mode:4s} FULL {sh(r):.3f} vs {sh(b):.3f} d {bf[0]:+.3f} [{bf[1]:+.2f},{bf[2]:+.2f}] | POST {sh(r, POST):.3f} vs {sh(b, POST):.3f} d {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P<=0 {bt[3]:.2f}"
              f" | funding/yr FULL {fu:.2%} vs {fb:.2%}, POST {fup:.2%} vs {fbp:.2%} | CAGR {sim.cagr(r['rets']):+.1%} vs {sim.cagr(b['rets']):+.1%}")
        out[f"{name}|{mode}"] = dict(full=(sh(r), sh(b)), post=(sh(r, POST), sh(b, POST)), ci_post=bt[1:3], p=bt[3], fund=(fu, fb))
        if mode == "S1":
            tot = {cn: round(float(r["fund_frac"].sum()), 4) for cn in []}
json.dump(out, open(f"{OUT}/a5.json", "w"), default=float)
