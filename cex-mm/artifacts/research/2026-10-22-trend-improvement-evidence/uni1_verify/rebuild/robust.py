import sys, json, time
sys.path.insert(0, ".")
from uni1 import *
p0 = load()
p, qpos, last = d0_panel(p0)
pb = p.sub(data.EXANTE24)
BASE = {}
for cad in (DAILY, WEEKLY):
    r = run(pb, rules.baseline_weights(pb.C, tv=cad["tv"], max_gross=cad["max_gross"]), cad)
    BASE[cad["name"]] = (r, summarize(r))

def build(cad, **kw):
    reset_rows = kw.pop("reset_rows", None) or reset_rows_for(p, cad, "calendar")
    nmode = kw.pop("nmode", "valid")
    log = []
    mask = universe(p, qpos, last, reset_rows=reset_rows, log=log, **kw)
    return mask, log, nmode

def evaluate(cad, mask, nmode="valid", tv=None):
    c2 = dict(cad)
    if tv: c2["tv"] = tv
    us = None
    if nmode == "U":
        us = np.zeros(len(p.dates)); cur = 0
        for t in range(len(p.dates)):
            if t == 0 or (mask[t] & ~mask[t - 1]).any():
                cur = mask[t].sum()
            us[t] = cur
    W = weights(p, qpos, mask, c2, nmode=nmode, umask_size=us)
    return run(p, W, c2)

def judge(cad, mask, nmode="valid", boot=False):
    br, bs = BASE[cad["name"]]
    r = evaluate(cad, mask, nmode)
    s = summarize(r, br if boot else None)
    vv, vb = s["full"]["vol"], bs["full"]["vol"]
    mv = None
    if abs(vv / vb - 1) > 0.05:
        rm = evaluate(cad, mask, nmode, tv=cad["tv"] * vb / vv)
        sm = sim.stats(rm); mv = dict(sharpe=sm["sharpe"], mdd=sm["mdd"], worst7=sm["worst7"], vol=sm["vol"])
    thr = 0.86 if cad["name"] == "daily" else 0.82
    mdd_dec = mv["mdd"] if mv else s["full"]["mdd"]
    R = dict(R1=s["full"]["sharpe"] >= thr, R2=s["post"]["sharpe"] - bs["post"]["sharpe"] >= 0,
             R3mv=mdd_dec >= bs["full"]["mdd"], R3raw=s["full"]["mdd"] >= bs["full"]["mdd"],
             R4=(s["h1"]["sharpe"] >= bs["h1"]["sharpe"]) and (s["h2"]["sharpe"] >= bs["h2"]["sharpe"]))
    return dict(s=s, mv=mv, R=R, res=r)

def fmt(lab, cad, J):
    s, bs = J["s"], BASE[cad["name"]][1]
    mv = J["mv"]
    R = J["R"]
    flags = "".join(k + ("+" if v else "-") + " " for k, v in R.items())
    return (f"{lab:38s} {cad['name'][0]} FULL {s['full']['sharpe']:.3f} POST {s['post']['sharpe']:.3f} (dPOST {s['post']['sharpe']-bs['post']['sharpe']:+.3f}) "
            f"H1 {s['h1']['sharpe']-bs['h1']['sharpe']:+.3f} H2 {s['h2']['sharpe']-bs['h2']['sharpe']:+.3f} vol {s['full']['vol']:.3f} DD {s['full']['mdd']:.3f} "
            f"mvDD {mv['mdd'] if mv else float('nan'):.3f} | {flags}")
