import sys
sys.path.insert(0, ".")
from robust import *
out = {}
def do(lab, cads=(DAILY, WEEKLY), **kw):
    for cad in cads:
        kw2 = dict(kw)
        mask, log, nmode = build(cad, **kw2)
        J = judge(cad, mask, nmode)
        print(fmt(lab, cad, J), flush=True)
        out[f"{lab}|{cad['name']}"] = dict(full=J["s"]["full"]["sharpe"], post=J["s"]["post"]["sharpe"], h1=J["s"]["h1"]["sharpe"], h2=J["s"]["h2"]["sharpe"],
                                           vol=J["s"]["full"]["vol"], mdd=J["s"]["full"]["mdd"], mv=J["mv"], R=J["R"])
for cad in (DAILY, WEEKLY):
    bs = BASE[cad["name"]][1]
    print("static-24", cad["name"], {k: (round(v["sharpe"], 4), round(v["vol"], 4), round(v["mdd"], 4)) for k, v in bs.items()})
print("== readings ==")
do("REPRO (elig,any,valid)", rank_pop="eligible", start_elig="any")
do("N=|U| literal", rank_pop="eligible", start_elig="any", nmode="U")
do("age floor on incumbents", rank_pop="eligible", start_elig="any", age_applies_to_incumbents=True)
do("continuous hysteresis", rank_pop="eligible", start_elig="any", continuous_hyst=True)
do("start set needs 121 closes", rank_pop="eligible", start_elig="sig121")
do("rank among all ages", rank_pop="all", start_elig="any")
print("== age floor sweep ==")
for a in (121, 180, 240, 300, 330, 340, 350, 365, 380, 400, 450, 540):
    do(f"age {a}", rank_pop="eligible", start_elig="any", age_min=a)
print("== N / keep-rank sweep ==")
for n_ in (6, 7, 8, 10, 11, 12):
    do(f"N {n_} keep 2N", rank_pop="eligible", start_elig="any", n=n_, keep_rank=2 * n_)
for k in (9, 12, 15, 24, 27, 999):
    do(f"N 9 keep {k}", rank_pop="eligible", start_elig="any", keep_rank=k)
print("== median window / ranking lag ==")
for w in (7, 14, 20, 45, 60, 90):
    do(f"median win {w}", rank_pop="eligible", start_elig="any", med_win=w)
for lag in (1, 3, 7, 14):
    do(f"rank lag {lag}d", rank_pop="eligible", start_elig="any", rank_lag=lag)
print("== start date of the start set (ranking on day s, trading from s) ==")
for sd in (dt.date(2020, 4, 23), dt.date(2020, 4, 26), dt.date(2020, 4, 28), dt.date(2020, 4, 29), dt.date(2020, 5, 1), dt.date(2020, 5, 3), dt.date(2020, 5, 7)):
    do(f"start set {sd}", rank_pop="eligible", start_elig="any", start_date=sd)
print("== reset month (yearly, first day of month m) ==")
for mth in range(1, 13):
    def rows(cad, m=mth):
        return [p.idx[dt.date(y, m, 1)] for y in range(2020, 2027) if dt.date(2020, 4, 30) < dt.date(y, m, 1) <= dt.date(2026, 9, 30)]
    for cad in (DAILY, WEEKLY):
        mask, log, nmode = build(cad, reset_rows=rows(cad), rank_pop="eligible", start_elig="any")
        J = judge(cad, mask, nmode)
        print(fmt(f"reset month {mth}", cad, J), flush=True)
        out[f"reset month {mth}|{cad['name']}"] = dict(full=J["s"]["full"]["sharpe"], post=J["s"]["post"]["sharpe"], R=J["R"])
json.dump(out, open("robust.json", "w"), indent=1, default=float)
