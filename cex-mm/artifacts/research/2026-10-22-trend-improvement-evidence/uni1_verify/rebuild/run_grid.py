import sys, json, time, itertools
sys.path.insert(0, ".")
from run_primary import *
res = []
t0 = time.time()
for rank_pop, start_elig, nmode, age_inc, cont in itertools.product(["eligible", "all"], ["any", "sig121"], ["U", "valid", "U9"], [False, True], [False, True]):
    for cad in (DAILY, WEEKLY):
        for rm in (["calendar", "sunday"] if cad["weekly"] else ["calendar"]):
            cfg = dict(rank_pop=rank_pop, start_elig=start_elig, nmode=nmode, age_inc=age_inc, cont=cont, reset_mode=rm)
            r, mask, log = go(cfg, cad)
            sf = sim.stats(r); sp = sim.stats(r, POST)
            res.append(dict(cfg=cfg, cad=cad["name"], full=sf["sharpe"], post=sp["sharpe"], vol=sf["vol"], mdd=sf["mdd"],
                            uni={str(e[0]): sorted(map(str, e[2])) for e in log}))
            print(cad["name"], cfg, round(sf["sharpe"], 4), round(sp["sharpe"], 4), round(sf["vol"], 4), round(sf["mdd"], 4), flush=True)
json.dump(res, open("grid.json", "w"), indent=1)
print("elapsed", round(time.time() - t0))
