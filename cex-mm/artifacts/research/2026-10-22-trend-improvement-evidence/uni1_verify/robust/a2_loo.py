"""(2) leave-one-coin-out and coin-year trimming."""
from common import *
c = ctx()
res = {}
for name, cad in CADS.items():
    U, _ = U_uni1(c, cad); W = W_of(c, cad, U); r = run(c, cad, W)
    Wb = W_of(c, cad, U_static24(c)); b = run(c, cad, Wb)
    S0 = (sh(r), sh(r, POST), sh(b), sh(b, POST))
    print(f"\n=== {name}: base UNI-1 FULL {S0[0]:.3f} POST {S0[1]:.3f} | static24 FULL {S0[2]:.3f} POST {S0[3]:.3f} | d FULL {S0[0]-S0[2]:+.3f} POST {S0[1]-S0[3]:+.3f}")
    tot = {cn: float(r["coin_pnl"][:, k].sum()) for k, cn in enumerate(r["cols"])}
    top = sorted(tot, key=lambda k: -tot[k])[:8]
    rows = []
    print(" (a) zero weight in UNI-1 only (N_t unchanged)         | (b) coin removed from the world (UNI-1 re-selects; static24 drops it)")
    for cn in top:
        j = c.coins.index(cn)
        Wa = W.copy(); Wa[:, j] = 0.0; ra = run(c, cad, Wa)
        ex = excl_mask(c, [cn]); Ux, lg = membership_custom(c, cad, excl=ex); rx = run(c, cad, W_of(c, cad, Ux))
        bx = run(c, cad, W_of(c, cad, static_mask_excl(c, data.EXANTE24, [cn]))) if cn in data.EXANTE24 else b
        repl = sorted(set(m for _, ms in lg for m in ms) - set(m for _, ms in membership_custom(c, cad)[1] for m in ms))
        rows.append(dict(coin=cn, a_full=sh(ra), a_post=sh(ra, POST), b_full=sh(rx), b_post=sh(rx, POST), s_full=sh(bx), s_post=sh(bx, POST), repl=repl))
        print(f"  -{cn:6s} (a) FULL {sh(ra):.3f} (d {sh(ra)-S0[2]:+.3f}) POST {sh(ra, POST):.3f} (d {sh(ra, POST)-S0[3]:+.3f}) | (b) UNI {sh(rx):.3f}/{sh(rx, POST):.3f} vs s24 {sh(bx):.3f}/{sh(bx, POST):.3f}: d FULL {sh(rx)-sh(bx):+.3f} POST {sh(rx, POST)-sh(bx, POST):+.3f} new names {repl}")
    # cumulative removal of the top contributors from the world
    print(" cumulative removal from the world (top-k UNI-1 contributors):")
    for k in range(1, 6):
        drop = top[:k]
        Ux, lg = membership_custom(c, cad, excl=excl_mask(c, drop)); rx = run(c, cad, W_of(c, cad, Ux))
        bx = run(c, cad, W_of(c, cad, static_mask_excl(c, data.EXANTE24, drop)))
        bt = boot(rx, bx, POST, None, rx)
        print(f"  -{'+'.join(drop):28s} UNI {sh(rx):.3f}/{sh(rx, POST):.3f} s24 {sh(bx):.3f}/{sh(bx, POST):.3f} d FULL {sh(rx)-sh(bx):+.3f} POST {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P<=0 {bt[3]:.2f}")
    # coin-year trimming
    d = np.array(r["dates"]); yrs_r = np.array([q.year for q in d])
    def cy(res_):
        dd = np.array(res_["dates"]); yy = np.array([q.year for q in dd])
        return sorted((((cn, int(y)), float(res_["coin_pnl"][yy == y, k].sum())) for k, cn in enumerate(res_["cols"]) for y in sorted(set(yy))), key=lambda kv: -kv[1])
    cyu, cyb = cy(r), cy(b)
    yrow = np.array([q.year for q in c.dates])
    def trim(Wx, lst, k):
        Wt = Wx.copy()
        for (cn, y), _ in lst[:k]:
            Wt[yrow == y, c.coins.index(cn)] = 0.0
        return Wt
    print(" coin-year trimming (zero the coin's weight for that calendar year):")
    for k in (1, 3, 5, 10):
        ru = run(c, cad, trim(W, cyu, k)); rb = run(c, cad, trim(Wb, cyb, k))
        print(f"  top-{k:2d}: UNI-1 only trimmed: {sh(ru):.3f}/{sh(ru, POST):.3f} vs s24 {S0[2]:.3f}/{S0[3]:.3f} -> d {sh(ru)-S0[2]:+.3f}/{sh(ru, POST)-S0[3]:+.3f}"
              f" | both trimmed: s24 {sh(rb):.3f}/{sh(rb, POST):.3f} -> d {sh(ru)-sh(rb):+.3f}/{sh(ru, POST)-sh(rb, POST):+.3f}  [{', '.join(f'{a}{y}' for (a, y), _ in cyu[:k])}]")
    # POST-only coin-year trimming (top coin-years within 2022+)
    cyu_p = [kv for kv in cyu if kv[0][1] >= 2022]; cyb_p = [kv for kv in cyb if kv[0][1] >= 2022]
    for k in (1, 2, 3, 5):
        ru = run(c, cad, trim(W, cyu_p, k)); rb = run(c, cad, trim(Wb, cyb_p, k))
        print(f"  POST top-{k}: UNI-1 only trimmed d POST {sh(ru, POST)-S0[3]:+.3f} | both trimmed d POST {sh(ru, POST)-sh(rb, POST):+.3f}  [{', '.join(f'{a}{y}' for (a, y), _ in cyu_p[:k])}] vs s24 [{', '.join(f'{a}{y}' for (a, y), _ in cyb_p[:k])}]")
    res[name] = rows
json.dump(res, open(f"{OUT}/a2.json", "w"), default=float)
