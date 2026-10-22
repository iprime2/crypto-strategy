"""Build my own T events for OT and OX (base config = plan) and save them as pickles for the check scripts.
Also builds the trigger 'ge' variant and coverage variants used in the fill / data sensitivities."""
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv")
import adv_lib as A  # noqa: E402

OUT = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv"


def weeks_OT(c, b):
    first = int(A.monday(b["t"][0] - 1)) + 2 * A.WK
    return list(range(first, A.ts("2020-04-20") + 1, A.WK))


def weeks_OX(c, b):
    return list(range(A.ts("2022-01-03"), A.ts("2026-09-21") + 1, A.WK))


def main():
    t0 = time.time()
    res = {}
    for panel, coins, wf in (("OT", A.OT_COINS, weeks_OT), ("OX", A.OX_COINS, weeks_OX)):
        bars = {c: A.load(panel, c) for c in coins}
        variants = {"base": dict(cov=0.99, trigger="tol", p3=True),
                    "ge": dict(cov=0.99, trigger="ge", p3=False),
                    "cov95": dict(cov=0.95, trigger="tol", p3=False),
                    "cov90": dict(cov=0.90, trigger="tol", p3=False),
                    "cov0": dict(cov=0.0, trigger="tol", p3=False)}
        for vn, kw in variants.items():
            if panel == "OX" and vn in ("cov95", "cov90", "cov0"):
                continue  # OX has no outages inside the listing; low coverage would only add delisting stubs
            ev, wk = A.build(panel, coins, bars, weeks_fn=wf, **kw)
            ev = A.attach(ev, bars)
            res[(panel, vn)] = (ev, wk)
            print(panel, vn, len(ev), int(wk.used.sum()), f"{time.time() - t0:.1f}s", flush=True)
        meta = {c: dict(end=bars[c]["end"], eff_end=bars[c]["eff_end"], n=len(bars[c]["t"])) for c in coins}
        res[(panel, "meta")] = meta
    with open(f"{OUT}/events_adv.pkl", "wb") as fh:
        pickle.dump(res, fh)


if __name__ == "__main__":
    main()
