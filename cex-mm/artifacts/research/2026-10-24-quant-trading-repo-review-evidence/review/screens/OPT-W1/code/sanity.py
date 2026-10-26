"""Sanity checks on weeks.json: strike distance outliers, put-call parity at entry, credit vs a BS-like scale."""
import json, sys, os, numpy as np
from datetime import datetime, timezone
DIR = sys.argv[1]
w = json.load(open(os.path.join(DIR, "out", "weeks.json")))
d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
for u in ("BTC", "ETH"):
    r = [x for x in w if x["underlying"] == u]
    dist = np.array([abs(x["K"] / x["s0"] - 1) * 1e4 for x in r])
    par = np.array([((x["mc"] - x["mp"]) - (x["s0"] - x["K"])) / x["s0"] * 1e4 for x in r])
    print(u, "n", len(r), "strike dist >100 bps:", [(d(x["expiry"]), round(dd), x["n_live_strikes_both"]) for x, dd in zip(r, dist) if dd > 100])
    print(u, "parity residual (C-P)-(S0-K) bps: median %.1f p5 %.1f p95 %.1f min %.1f max %.1f" % (np.median(par), np.percentile(par, 5), np.percentile(par, 95), par.min(), par.max()))
    big = [(d(x["expiry"]), round(p, 1)) for x, p in zip(r, par) if abs(p) > 30]
    print(u, "|parity| > 30 bps:", big)
    ns = [x["n_settle"] for x in r]; print(u, "settle candles min", min(ns), "max", max(ns))
    nd = sum(1 for x in r for dm in x["daily"] for k in ("mc", "mp") if dm[k] is None); print(u, "missing daily marks", nd)
    gaps = [(x["expiry"] - x["entry"]) for x in r]; print(u, "entry->expiry seconds set", set(gaps))
    print(u, "weekdays of expiry", set(datetime.fromtimestamp(x["expiry"], timezone.utc).strftime("%a %H:%M") for x in r))
