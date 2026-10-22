#!/usr/bin/env python3
"""Fill the archive gaps (2022-02-26..28, 2022-04-01..02 for XRP LTC SOL TRX XLM ZEC IOTA VET; DASH 2022-10) from Binance's own daily /
monthly files (downloaded to dl_raw/), re-run UNI-1 and the static 24 on both books, and report the Sharpe change."""
import sys, io, csv, zipfile, os, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data, sim
import variants_universe as vu
from base import build

DL = f"{SP}/uni1_verify/audit/dl_raw"
P0 = vu.load_pool()


def rows_from_zip(path):
    with zipfile.ZipFile(path) as z:
        txt = z.read(z.namelist()[0]).decode()
    out = []
    for row in csv.reader(io.StringIO(txt)):
        if row and row[0].isdigit():
            out.append(row)
    return out


O, H, L, C, V, F, Q = (x.copy() for x in (P0.O, P0.H, P0.L, P0.C, P0.V, P0.F, P0.Q))
filled = []
for fn in sorted(os.listdir(DL)):
    path = os.path.join(DL, fn)
    coin = fn.split("-")[0][:-4]
    j = P0.ci[coin]
    for row in rows_from_zip(path):
        ts = int(row[0]); ts = ts / 1e6 if ts > 1e14 else ts / 1000
        d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()
        if d not in P0.idx:
            continue
        t = P0.idx[d]
        if "fundingRate" in fn:
            if F[t, j] == 0:
                pass
            continue
        if np.isfinite(C[t, j]):
            continue
        O[t, j], H[t, j], L[t, j], C[t, j], V[t, j], Q[t, j] = float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[7])
        filled.append((coin, str(d), float(row[4])))
# DASH funding for 2022-10 (the monthly funding file was also missing from the cache): sum per day
fz = os.path.join(DL, "DASHUSDT-fundingRate-2022-10.zip")
jd = P0.ci["DASH"]; before = float(F[P0.idx[dt.date(2022, 10, 1)]:P0.idx[dt.date(2022, 10, 31)] + 1, jd].sum())
acc = {}
for row in rows_from_zip(fz):
    ts = int(row[0]) / 1000
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()
    acc[d] = acc.get(d, 0.0) + float(row[2])
for d, v in acc.items():
    if d in P0.idx and F[P0.idx[d], jd] == 0:
        F[P0.idx[d], jd] = v
print(f"filled {len(filled)} coin-rows; DASH Oct-2022 funding sum before {before:.5f} after {sum(acc.values()):.5f}")
gapF = [(c, d, float(P0.F[P0.idx[dt.date.fromisoformat(d)], P0.ci[c]])) for c, d, _ in filled if c != "DASH"][:5]
print("funding already present on gap days (sample):", gapF)
P1 = data.Panel(P0.dates, list(P0.coins), O, H, L, C, V, F, Q)

_, _, o0 = build(P0)
_, _, o1 = build(P1)
for name in ("daily", "weekly"):
    s0, b0 = sim.stats(o0[name]["r"]), sim.stats(o0[name]["b"])
    s1, b1 = sim.stats(o1[name]["r"]), sim.stats(o1[name]["b"])
    p0, pb0 = sim.stats(o0[name]["r"], vu.POST), sim.stats(o0[name]["b"], vu.POST)
    p1, pb1 = sim.stats(o1[name]["r"], vu.POST), sim.stats(o1[name]["b"], vu.POST)
    same_U = np.array_equal(o0[name]["U"], o1[name]["U"])
    print(f"{name}: FULL UNI-1 {s0['sharpe']:.4f} -> {s1['sharpe']:.4f}; static-24 {b0['sharpe']:.4f} -> {b1['sharpe']:.4f}; "
          f"delta {s0['sharpe'] - b0['sharpe']:+.4f} -> {s1['sharpe'] - b1['sharpe']:+.4f}")
    print(f"        POST UNI-1 {p0['sharpe']:.4f} -> {p1['sharpe']:.4f}; static-24 {pb0['sharpe']:.4f} -> {pb1['sharpe']:.4f}; "
          f"delta {p0['sharpe'] - pb0['sharpe']:+.4f} -> {p1['sharpe'] - pb1['sharpe']:+.4f}; MDD UNI-1 {s0['mdd']:.4f}->{s1['mdd']:.4f} "
          f"static {b0['mdd']:.4f}->{b1['mdd']:.4f}; membership unchanged: {same_U}")
