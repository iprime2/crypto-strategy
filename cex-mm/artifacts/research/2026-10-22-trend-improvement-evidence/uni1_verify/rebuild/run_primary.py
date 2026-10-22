import sys, json, time
sys.path.insert(0, ".")
from uni1 import *
p0 = load()
p, qpos, last = d0_panel(p0)
pb = p.sub(data.EXANTE24)

def usize(mask, p, rows):
    """|U| at the most recent reset/start row, forward-filled (not reduced by delistings)."""
    T = len(p.dates); out = np.zeros(T)
    marks = sorted(set([p.idx[dt.date(2020, 4, 30)]] + list(rows)))
    cur = 0
    for t in range(T):
        if t in marks:
            # size of the set formed at t, before any same-day delisting
            cur = mask[t].sum()
        out[t] = cur
    return out

def go(cfg, cad, verbose=False):
    rows = reset_rows_for(p, cad, cfg.get("reset_mode", "calendar"))
    log = []
    mask = universe(p, qpos, last, reset_rows=rows, rank_pop=cfg["rank_pop"], start_elig=cfg["start_elig"],
                    age_applies_to_incumbents=cfg.get("age_inc", False), continuous_hyst=cfg.get("cont", False), log=log)
    us = usize(mask, p, rows)
    W = weights(p, qpos, mask, cad, nmode=cfg["nmode"], umask_size=us)
    r = run(p, W, cad)
    return r, mask, log

base = {}
for cad in (DAILY, WEEKLY):
    base[cad["name"]] = run(pb, rules.baseline_weights(pb.C, tv=cad["tv"], max_gross=cad["max_gross"]), cad)

if __name__ == "__main__":
    cfg = dict(rank_pop="eligible", start_elig="any", nmode="U", reset_mode="calendar")
    for cad in (DAILY, WEEKLY):
        r, mask, log = go(cfg, cad)
        s = summarize(r, base[cad["name"]])
        print(cad["name"], json.dumps({k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "yearly"} for k, v in s.items()}))
        if cad is DAILY:
            for e in log:
                print("  ", e[0], e[1], e[2], e[3] if len(e) > 3 else "")
