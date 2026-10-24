"""Self-tests: data alignment (daily close vs hourly), synthetic cointegrated pair, independent random walks, no look-ahead."""
import datetime as dt, sys, math
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/PAIR-1")
import numpy as np, engine as E

mk = E.load_market(E.NINE)
# 1. daily close at 00:00 D == close of the 1 h bar opening 23:00 D-1
diffs, n = [], 0
for j, c in enumerate(mk.coins):
    for i, d in enumerate(mk.days):
        if not np.isfinite(mk.CL[i, j]) or d < dt.date(2020, 1, 3):
            continue
        k = (E.d2ms(d) - mk.h0) // E.H - 1
        hc = mk.HC[k, j]
        if np.isfinite(hc):
            diffs.append(abs(math.log(hc) - mk.CL[i, j])); n += 1
diffs = np.array(diffs)
print(f"[1] daily close vs 23:00 hourly close: n {n}, max |dln| {diffs.max():.2e}, share > 1e-9: {np.mean(diffs > 1e-9):.4f}")
# P01 availability in window
miss = {c: int(sum(1 for d in mk.days if dt.date(2020, 5, 1) <= d <= dt.date(2026, 9, 30) and not np.isfinite(mk.HC[(E.d2ms(d) - mk.h0) // E.H, j]))) for j, c in enumerate(mk.coins)}
print("[1] missing P01 bars 2020-05..2026-09 per coin:", miss)

# 2/3. synthetic markets
def synth(kind, seed):
    rng = np.random.default_rng(seed)
    T = 1200
    days = [dt.date(2020, 1, 2) + dt.timedelta(days=i) for i in range(T)]
    lx = np.log(100) + np.cumsum(rng.normal(0, 0.03, T))
    if kind == "coint":
        phi = 2 ** (-1 / 8)  # half-life 8 days
        u = np.zeros(T)
        for t in range(1, T):
            u[t] = phi * u[t - 1] + rng.normal(0, 0.02)
        ly = 1.0 + 0.8 * lx + u
    else:
        ly = np.log(50) + np.cumsum(rng.normal(0, 0.03, T))
    CL = np.column_stack([lx, ly])
    h0 = E.d2ms(dt.date(2019, 12, 1))
    nh = (E.d2ms(days[-1] + dt.timedelta(days=3)) - h0) // E.H
    HC = np.full((nh, 2), np.nan)
    for i, d in enumerate(days):
        k = (E.d2ms(d) - h0) // E.H
        HC[k - 1] = np.exp(CL[i])       # 23:00 bar of D-1 closes at the daily close
        HC[k:k + 23] = np.exp(CL[i])    # flat intraday: the 01:00 fill equals the close
    HO = HC.copy()
    fund = {c: (np.array([], dtype=np.int64), np.array([])) for c in ("X", "Y")}
    return E.Market(["X", "Y"], days, CL, np.full(CL.shape, np.nan), h0, HO, HC, fund)

for kind in ("coint", "rw"):
    elig, ntr, nets = 0, 0, []
    mondays = 0
    for seed in range(20):
        m = synth(kind, seed)
        s = E.Sim(m, [(0, 1)], E.Params(), dt.date(2020, 8, 1), dt.date(2023, 3, 31)).run()
        elig += sum(1 for _, S in s.formations_used if S); mondays += len(s.formations_used)
        ntr += len(s.trades); nets += [r["gross_bps"] for r in E.trade_table(s)]
    print(f"[2] synthetic {kind}: selected on {elig}/{mondays} Mondays, trades {ntr}, mean gross bps {np.mean(nets) if nets else float('nan'):.1f}")

# 4. no look-ahead: truncate every input after the cut, rerun, compare trades closed before the cut
cut = dt.date(2023, 3, 15)
full = E.Sim(mk, [(i, j) for i in range(9) for j in range(i + 1, 9)], E.Params(), dt.date(2020, 5, 1), dt.date(2026, 9, 30)).run()
icut = mk.di(cut)
kcut = (E.d2ms(cut) - mk.h0) // E.H + 24   # hourly data up to 00:00 cut+1
CL2 = mk.CL.copy(); CL2[icut + 1:] = np.nan
HC2 = mk.HC.copy(); HC2[kcut:] = np.nan
HO2 = mk.HO.copy(); HO2[kcut:] = np.nan
cms = E.d2ms(cut + dt.timedelta(days=1))
fund2 = {c: (st[st < cms], rt[st < cms]) for c, (st, rt) in mk.fund.items()}
mk2 = E.Market(mk.coins, mk.days, CL2, mk.Q, mk.h0, HO2, HC2, fund2)
trunc = E.Sim(mk2, [(i, j) for i in range(9) for j in range(i + 1, 9)], E.Params(), dt.date(2020, 5, 1), cut).run()
A = [(r["pair"], r["d_entry"], r["d_exit"], r["reason"], round(r["net_bps"], 9)) for r in E.trade_table(full) if r["d_exit"] < cut]
B = [(r["pair"], r["d_entry"], r["d_exit"], r["reason"], round(r["net_bps"], 9)) for r in E.trade_table(trunc) if r["d_exit"] < cut]
same_rets = np.allclose(full.rets[:len(trunc.rets) - 1], trunc.rets[:-1], atol=1e-15, rtol=0)
print(f"[4] look-ahead: trades closed before {cut}: full {len(A)}, truncated {len(B)}, identical: {A == B}; daily returns before the cut identical: {same_rets}")
