import sys, json, time
sys.path.insert(0, ".")
from uni1 import *
t0 = time.time()
p0 = load()
p, qpos, last = d0_panel(p0)
print("load+trim", round(time.time() - t0, 1), "s")
pb = p.sub(data.EXANTE24)
pb_raw = p0.sub(data.EXANTE24)
for cad in (DAILY, WEEKLY):
    for lab, pp in (("D-0 trimmed", pb), ("raw Bw", pb_raw)):
        W = rules.baseline_weights(pp.C, tv=cad["tv"], max_gross=cad["max_gross"])
        r = run(pp, W, cad)
        s = summarize(r)
        print(cad["name"], lab, {k: (round(v["sharpe"], 4), round(v["vol"], 4), round(v["mdd"], 4)) for k, v in s.items()}, "days", len(r["rets"]))
# delisting events in static-24
for c in data.EXANTE24:
    j = p.ci[c]
    if last[j] < len(p.dates) - 1:
        print("static-24 delisting:", c, p.dates[last[j]])
