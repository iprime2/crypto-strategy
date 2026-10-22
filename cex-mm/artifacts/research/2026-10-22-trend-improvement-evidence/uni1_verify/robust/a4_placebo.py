"""(4) random-universe placebo: 200 draws, 9 coins drawn at random each January (no hysteresis, no ranking), same eligibility
(2020-04-30: candidates with >= 30 closes, no age floor; later resets: >= 365 closes, plus incumbents still listed), same sizing,
cadence, band and cap.  P1 = uniform from the whole eligible list (the task's placebo); P2 = uniform 9 of the eligible top-18 by
30-day median turnover (liquidity tier); P3 = uniform from the eligible list restricted to the static 24 (concentration inside the cohort)."""
from common import *
import sys
c = ctx()
NDRAW = int(sys.argv[1]) if len(sys.argv) > 1 else 200
H1b = (vu.A0, dt.date(2021, 12, 31))
ex24 = np.array([cn not in set(data.EXANTE24) for cn in c.coins])
res = {}
t0 = time.time()
for name, cad in CADS.items():
    U, _ = U_uni1(c, cad); r = run(c, cad, W_of(c, cad, U))
    b = run(c, cad, W_of(c, cad, U_static24(c)))
    ref = dict(uni=[sh(r), sh(r, POST), sh(r, *H1b)], s24=[sh(b), sh(b, POST), sh(b, *H1b)])
    res[name] = dict(ref=ref)
    for pl, kwp in (("P1", dict(pick="random")), ("P2", dict(pick=("random_top", 18))), ("P3", dict(pick="random", excl=ex24))):
        arr = np.zeros((NDRAW, 3)); names = []
        for i in range(NDRAW):
            rng = np.random.default_rng(10_000 + i)
            Ui, lg = membership_custom(c, cad, rng=rng, **kwp)
            ri = run(c, cad, W_of(c, cad, Ui))
            arr[i] = [sh(ri), sh(ri, POST), sh(ri, *H1b)]
            names.append(lg)
        pct = lambda col, v: float((arr[:, col] < v).mean() * 100)
        res[name][pl] = dict(sharpe=arr.tolist(), pct_uni=[pct(k, ref["uni"][k]) for k in range(3)], pct_s24=[pct(k, ref["s24"][k]) for k in range(3)])
        q = lambda col: np.percentile(arr[:, col], [5, 25, 50, 75, 95])
        print(f"{name} {pl} n={NDRAW} ({time.time()-t0:.0f}s)")
        for k, lbl in enumerate(("FULL", "POST", "2020-21")):
            print(f"   {lbl:7s} mean {arr[:, k].mean():.3f} sd {arr[:, k].std():.3f} p5/25/50/75/95 {' '.join(f'{x:.3f}' for x in q(k))} | UNI-1 {ref['uni'][k]:.3f} at pct {pct(k, ref['uni'][k]):.1f} | static-24 {ref['s24'][k]:.3f} at pct {pct(k, ref['s24'][k]):.1f} | share > static-24 {np.mean(arr[:, k] > ref['s24'][k]):.2f}")
json.dump(res, open(f"{OUT}/a4.json", "w"), default=float)
