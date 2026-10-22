"""(1) calendar-year Sharpe/return, both books; (2) per-coin and per-coin-year P&L attribution; funding coverage of members."""
from common import *
c = ctx()
out = {}
for name, cad in CADS.items():
    U, log = U_uni1(c, cad); W = W_of(c, cad, U); r = run(c, cad, W)
    Ub = U_static24(c); Wb = W_of(c, cad, Ub); b = run(c, cad, Wb)
    yu, yb = yearly(r), yearly(b)
    print(f"\n=== {name}: FULL {sh(r):.3f} vs {sh(b):.3f}; POST {sh(r, POST):.3f} vs {sh(b, POST):.3f}")
    print(" year | UNI-1 Sharpe ret vol | static24 Sharpe ret vol | dSharpe dRet")
    for y in yu:
        print(f" {y} | {yu[y]['sharpe']:6.2f} {yu[y]['ret']:+7.1%} {yu[y]['vol']:5.1%} | {yb[y]['sharpe']:6.2f} {yb[y]['ret']:+7.1%} {yb[y]['vol']:5.1%} | {yu[y]['sharpe']-yb[y]['sharpe']:+5.2f} {yu[y]['ret']-yb[y]['ret']:+6.1%}")
    # per-coin P&L (sum of daily fractions of equity, price net of funding, before costs)
    def coin_tab(res):
        d = np.array(res["dates"]); yrs = np.array([q.year for q in d])
        cp = res["coin_pnl"]
        tot = {cn: float(cp[:, k].sum()) for k, cn in enumerate(res["cols"])}
        post = {cn: float(cp[d >= POST, k].sum()) for k, cn in enumerate(res["cols"])}
        cy = {(cn, int(y)): float(cp[yrs == y, k].sum()) for k, cn in enumerate(res["cols"]) for y in sorted(set(yrs))}
        return tot, post, cy
    tu, pu, cyu = coin_tab(r); tb, pb, cyb = coin_tab(b)
    print(f" sum coin pnl (pre-cost): UNI-1 {sum(tu.values()):+.3f} (costs {r['cost_frac'].sum():.3f}) static24 {sum(tb.values()):+.3f} (costs {b['cost_frac'].sum():.3f})")
    print(f" POST: UNI-1 {sum(pu.values()):+.3f} (costs {r['cost_frac'][mask(r, POST)].sum():.3f}) static24 {sum(pb.values()):+.3f} (costs {b['cost_frac'][mask(b, POST)].sum():.3f})")
    coins = sorted(set(tu) | set(tb), key=lambda k: -(tu.get(k, 0) - tb.get(k, 0)))
    print(" coin | UNI-1 full post | static24 full post | diff full post")
    for cn in coins:
        print(f"  {cn:9s} | {tu.get(cn, 0):+.3f} {pu.get(cn, 0):+.3f} | {tb.get(cn, 0):+.3f} {pb.get(cn, 0):+.3f} | {tu.get(cn, 0)-tb.get(cn, 0):+.3f} {pu.get(cn, 0)-pb.get(cn, 0):+.3f}")
    top = sorted(cyu.items(), key=lambda kv: -kv[1])[:12]
    print(" top UNI-1 coin-years:", ", ".join(f"{k[0]}{k[1]} {v:+.3f}" for k, v in top))
    topb = sorted(cyb.items(), key=lambda kv: -kv[1])[:12]
    print(" top static24 coin-years:", ", ".join(f"{k[0]}{k[1]} {v:+.3f}" for k, v in topb))
    # differences by coin-year: UNI-1 minus static24
    keys = set(cyu) | set(cyb)
    dif = sorted(((k, cyu.get(k, 0) - cyb.get(k, 0)) for k in keys), key=lambda kv: -kv[1])
    print(" top +diff coin-years:", ", ".join(f"{k[0]}{k[1]} {v:+.3f}" for k, v in dif[:10]))
    print(" top -diff coin-years:", ", ".join(f"{k[0]}{k[1]} {v:+.3f}" for k, v in dif[-10:]))
    # by group: shared coins (in both), static24-only, UNI-1-only
    s24 = set(data.EXANTE24); uc = set(tu)
    grp = {"shared": [k for k in uc if k in s24], "uni_only": [k for k in uc if k not in s24], "s24_only": [k for k in tb if k not in uc]}
    for g, ks in grp.items():
        print(f"  group {g:9s} {sorted(ks)}: UNI-1 {sum(tu.get(k, 0) for k in ks):+.3f} (post {sum(pu.get(k, 0) for k in ks):+.3f}); static24 {sum(tb.get(k, 0) for k in ks):+.3f} (post {sum(pb.get(k, 0) for k in ks):+.3f})")
    out[name] = dict(yearly_uni=yu, yearly_s24=yu and yb, coin_uni=tu, coin_s24=tb, coin_uni_post=pu, coin_s24_post=pb,
                     coinyear_uni={f"{k[0]}|{k[1]}": v for k, v in cyu.items()}, coinyear_s24={f"{k[0]}|{k[1]}": v for k, v in cyb.items()})
# funding coverage for members
print("\nfunding coverage of UNI-1 members (share of candidate rows in membership with F != 0; mean ann funding while member):")
U, _ = U_uni1(c, CADS["daily"])
for j in np.flatnonzero(U.any(axis=0)):
    m = U[:, j] & c.pos[:, j]
    f = c.pc.F[m, j]
    print(f"  {c.coins[j]:9s} member rows {m.sum():5d} F!=0 {np.mean(f != 0):.2f} mean ann {f.mean()*365:+.2%}")
json.dump(out, open(f"{OUT}/a1.json", "w"), default=float)
