import sys
sys.path.insert(0, ".")
from robust import *
res = {}
print("=== exact reproduction, full stats ===")
for cad in (DAILY, WEEKLY):
    mask, log, nmode = build(cad, rank_pop="eligible", start_elig="any")
    J = judge(cad, mask, nmode, boot=True)
    s = J["s"]; bs = BASE[cad["name"]][1]
    for w in ("full", "post", "h1", "h2"):
        print(cad["name"], w, f"UNI-1 Sharpe {s[w]['sharpe']:.4f} vol {s[w]['vol']:.4f} maxDD {s[w]['mdd']:.4f} CAGR {s[w]['cagr']:.4f} worst7 {s[w]['worst7']:.4f} | static-24 Sharpe {bs[w]['sharpe']:.4f} vol {bs[w]['vol']:.4f} maxDD {bs[w]['mdd']:.4f} | delta {s[w]['delta']:+.4f} CI [{s[w]['ci'][0]:+.3f},{s[w]['ci'][1]:+.3f}] P<=0 {s[w]['p_le0']:.3f}")
    print(cad["name"], "matched-vol", {k: round(v, 4) for k, v in J["mv"].items()}, "static worst7", round(bs["full"]["worst7"], 4))
    # yearly
    r = J["res"]; br = BASE[cad["name"]][0]
    d = np.array(r["dates"]); yrs = np.array([x.year for x in d])
    for y in range(2020, 2027):
        m = yrs == y
        print(f"   {cad['name']} {y}: UNI-1 ret {np.prod(1 + r['rets'][m]) - 1:+.3f} SR {sim.sharpe(r['rets'][m]):+.2f} | static-24 ret {np.prod(1 + br['rets'][m]) - 1:+.3f} SR {sim.sharpe(br['rets'][m]):+.2f}")
    if cad is DAILY:
        for e in log:
            print("   membership", e[0], e[1], sorted(map(str, e[2])), {k: (sorted(map(str, v)) if isinstance(v, list) else {str(a): b for a, b in v.items()}) for k, v in (e[3].items() if len(e) > 3 else [])})
        # delisting events hit while a member
        for j in np.where(mask.any(0))[0]:
            if last[j] < len(p.dates) - 1 and mask[last[j], j]:
                t = last[j]
                W = weights(p, qpos, mask, cad)
                print("   delisting hit:", p.coins[j], p.dates[t], "target weight day before", round(W[t - 1, j], 4), "close", p.C[t, j])
        mask_d = mask
    else:
        same = (mask == mask_d).all()
        print("   weekly membership identical to daily:", same)
print("=== age-floor cliff: who enters at age 330 vs 365 ===")
for a in (330, 340, 365):
    mask, log, _ = build(DAILY, rank_pop="eligible", start_elig="any", age_min=a)
    print(a, [(str(e[0]), sorted(map(str, e[2]))) for e in log if e[0].year in (2022,)])
j = p.ci["LUNA"]; t = p.idx[dt.date(2022, 1, 1)]
print("LUNA closes at 2022-01-01:", int(np.isfinite(p.C[:t + 1, j]).sum()), "first close", p.dates[np.argmax(np.isfinite(p.C[:, j]))], "last q>0", p.dates[last[j]])
print("=== controls: where does the gain come from ===")
t0 = p.idx[dt.date(2020, 4, 30)]
for cad in (DAILY, WEEKLY):
    # (a) static liquid-9: start set frozen forever (no resets)
    mask, log, _ = build(cad, rank_pop="eligible", start_elig="any", reset_rows=[len(p.dates) + 5])
    J = judge(cad, mask); print(fmt("frozen 2020-04-30 top-9 (no resets)", cad, J))
    # (b) rotation restricted to the 24 ex-ante coins
    excl_saved = set(EXCL)
    EXCL.update(c for c in p.coins if c not in data.EXANTE24)
    mask, log, _ = build(cad, rank_pop="eligible", start_elig="any")
    J = judge(cad, mask); print(fmt("UNI-1 rule inside the 24 only", cad, J))
    if cad is DAILY: print("   inside-24 membership", [(str(e[0]), sorted(map(str, e[2]))) for e in log])
    EXCL.clear(); EXCL.update(excl_saved)
