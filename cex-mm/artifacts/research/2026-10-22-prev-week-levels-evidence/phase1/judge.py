import json, sys
R = json.load(open(sys.argv[1]))
PRIM = {"F": "4h", "B": "24h", "S": "4h"}
def cell(p, pat, hz, ctl, side="pooled"):
    for c in R[p]["cells"]:
        if c["pattern"] == pat and c["horizon"] == hz and c["control"] == ctl and c["side"] == side: return c
def test(p, pat, hz, ctl):
    for t in R[p]["tests"]:
        if t["pattern"] == pat and t["horizon"] == hz and t["control"] == ctl: return t
out = []
for p in "ABC":
    pr = R[p]
    out.append(f"## Panel {p}: coin-weeks used {pr['coin_weeks_used']}, skipped {pr['coin_weeks_skipped']}; touch rates any {pr['touch_rates']['any']:.3f} PWH {pr['touch_rates']['pwh']:.3f} PWL {pr['touch_rates']['pwl']:.3f}")
    if pr.get("reel"): out.append("   reel-style: " + json.dumps(pr["reel"]))
    for pat in "FBS":
        for hz in ("1h", "4h", "24h"):
            r, a, b = cell(p, pat, hz, "real"), cell(p, pat, hz, "P1"), cell(p, pat, hz, "P2")
            t = test(p, pat, hz, "P1")
            out.append(f"   {pat} {hz:>3}: real n {r['n']:6d} gross {r['gross_bps']:+7.2f} net {r['net_bps']:+7.2f} hit {r['hit']:.3f} | P1 n {a['n']:6d} gross {a['gross_bps']:+7.2f} | P2 n {b['n']:5d} gross {b['gross_bps']:+7.2f} | diff P1 {t['diff_bps']:+7.2f} [{t['ci_lo']:+.2f},{t['ci_hi']:+.2f}] P {t['p_one_sided']:.4f} | real net P {t['real_net_p']:.4f}" + (" *primary*" if PRIM[pat] == hz else ""))
print("\n".join(out))
print("\n## Pass rules (plan section 5), primary horizons")
for pat, hz in PRIM.items():
    tA, tB, tC = test("A", pat, hz, "P1"), test("B", pat, hz, "P1"), test("C", pat, hz, "P1")
    lvl = [("1 diff>=5 & P<=0.003 (A)", tA["diff_bps"] >= 5 and tA["p_one_sided"] <= 0.003),
           ("2 both halves diff>0 (A)", tA["halves"]["H1"]["diff_bps"] > 0 and tA["halves"]["H2"]["diff_bps"] > 0),
           ("3 >=6/9 coins diff>0 (A)", (tA["coins_pos_diff"] or 0) >= 6),
           ("4 diff>0 on B", tB["diff_bps"] > 0)]
    trd = [("1 net>0 & P<=0.003 (A)", tA["real_net_bps"] > 0 and tA["real_net_p"] <= 0.003),
           ("2a halves net>0 (A)", tA["halves"]["H1"]["real_net_bps"] > 0 and tA["halves"]["H2"]["real_net_bps"] > 0),
           ("2b >=6/9 coins net>0 (A)", (tA["coins_pos_net"] or 0) >= 6),
           ("2c net>0 on B", tB["real_net_bps"] > 0),
           ("3 net>0 on C (info if n<300)", tC["real_net_bps"] > 0)]
    print(f"{pat} {hz}: LEVEL EDGE {'PASS' if all(v for _, v in lvl) else 'FAIL'}: " + "; ".join(f"{k}={'ok' if v else 'NO'}" for k, v in lvl))
    print(f"   details A diff {tA['diff_bps']:+.2f} P {tA['p_one_sided']:.4f}; halves {tA['halves']['H1']['diff_bps']:+.2f}/{tA['halves']['H2']['diff_bps']:+.2f}; coins {tA['coins_pos_diff']}; B diff {tB['diff_bps']:+.2f}; C diff {tC['diff_bps']:+.2f}")
    print(f"{pat} {hz}: TRADABLE {'PASS' if all(v for _, v in trd[:4]) else 'FAIL'}: " + "; ".join(f"{k}={'ok' if v else 'NO'}" for k, v in trd))
    print(f"   details A net {tA['real_net_bps']:+.2f} P {tA['real_net_p']:.4f}; halves {tA['halves']['H1']['real_net_bps']:+.2f}/{tA['halves']['H2']['real_net_bps']:+.2f}; coins {tA['coins_pos_net']}; B net {tB['real_net_bps']:+.2f}; C net {tC['real_net_bps']:+.2f} (C n {cell('C',pat,hz,'real')['n']})")
print("\ndaily Sharpe A:", json.dumps(R["A"]["daily_sharpe"]))
