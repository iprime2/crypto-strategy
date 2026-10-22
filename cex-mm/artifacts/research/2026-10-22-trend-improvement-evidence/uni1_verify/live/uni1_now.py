#!/usr/bin/env python3
"""Part 6: UNI-1 target weights on the panel's last row (2026-09-30) and the contracts they map to on Delta at $5,000 (marks
from dl/tickers_now.json, 2026-10-21). stdout only."""
import json, os, sys
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f"{SP}/tools2"); sys.dont_write_bytecode = True
import variants_universe as vu  # noqa: E402
P = vu.load_pool(); ctx = vu._ctx(P)
tick = {t["symbol"]: t for t in json.load(open(f"{HERE}/dl/tickers_now.json"))["result"]}
for cad in (vu.DAILY, vu.WEEKLY):
    U, log = vu._membership(ctx, cad, vu.SPECS["UNI-1"])
    W = vu._weights(ctx, cad, U)
    t = ctx.T - 1
    # weekly: last decision row (Sunday) <= t
    if cad["weekly"]:
        while P.dates[t].weekday() != 6: t -= 1
    js = np.flatnonzero(U[t])
    print(f"{cad['name']} targets at {P.dates[t]} (gross {np.abs(W[t]).sum():.3f}):")
    for E in (1000, 5000):
        parts = []
        for j in js:
            c = ctx.coins[j]; tk = tick[f"{c}USD"]; ct = float(tk["contract_value"]) * float(tk["mark_price"])
            parts.append(f"{c} sig {ctx.sig[t, j]:.2f} w {W[t, j]:.3f} -> {W[t, j]*E/ct:.1f} ct")
        print(f"  E ${E:,}: " + "; ".join(parts))
