#!/usr/bin/env python3
"""(4) Funding audit: coverage of funding for coins UNI-1 holds (and the static 24), weight-days with zero funding, raw funding events
per day from the files, and a stress that imputes missing funding."""
import sys, os, csv, datetime as dt, collections
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data, sim
import variants_universe as vu
from base import build

P, ctx, out = build()
T = len(P.dates)

# raw funding events per coin-day (first file wins per filename, as data._read_binance)
def raw_events(coins):
    ev = {c: collections.defaultdict(list) for c in coins}; seen = set(); files = collections.defaultdict(list)
    for cache in data.CACHES:
        for fn in sorted(os.listdir(cache)):
            if not fn.startswith("binance-") or "fundingRate" not in fn or fn in seen:
                continue
            coin = fn.split("-")[1][:-4]
            if coin not in ev:
                continue
            seen.add(fn); files[coin].append((cache.split("/")[-1], fn))
            with open(os.path.join(cache, fn)) as f:
                for row in csv.reader(f):
                    if not row or not row[0].isdigit():
                        continue
                    ts = int(row[0]); ts = ts / 1e6 if ts > 1e14 else ts / 1000
                    t = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
                    ev[coin][t.date()].append((t, float(row[2])))
    return ev, files

held = sorted(set(out["daily"]["r"]["cols"]))
allc = sorted(set(held) | set(data.EXANTE24))
ev, files = raw_events(allc)

print("== funding events per day and coverage while the book holds the coin (daily book; position decided at close t pays F[t+1])")
for name, o in out.items():
    print(f"-- {name}")
    W = o["W"]
    # holding indicator per coin-day via coin_pnl / fund_frac is not split per coin; rebuild exposure from simulate units: use W shifted
    r = o["r"]; cols = r["cols"]; dates = r["dates"]
    tot_wd, tot_zero = 0, 0
    for c in cols:
        j = P.ci[c]
        # exposure on day d (dated return) = nonzero coin_pnl or nonzero W[t-1]; use W[t-1] (daily) as the held target
        k = cols.index(c)
        held_days = [d for i, d in enumerate(dates) if r["coin_pnl"][i, k] != 0]
        zero = [d for d in held_days if P.F[P.idx[d], j] == 0]
        cnt = collections.Counter(len(ev[c].get(d, [])) for d in held_days)
        tot_wd += len(held_days); tot_zero += len(zero)
        fsum = float(np.mean([P.F[P.idx[d], j] for d in held_days])) * 365 if held_days else 0
        print(f"   {c:9s} held days {len(held_days):5d} F==0 days {len(zero):4d} {[str(x) for x in zero[:6]]} events/day {dict(sorted(cnt.items()))} "
              f"mean funding while held {fsum:+.2%}/yr")
    print(f"   total coin-days held {tot_wd}, with F == 0: {tot_zero} ({tot_zero / max(tot_wd, 1):.2%})")

# static 24 side
o = out["daily"]; b = o["b"]
print("\n-- static-24 (daily book) coverage")
tot_wd = tot_zero = 0
for k, c in enumerate(b["cols"]):
    j = P.ci[c]
    held_days = [d for i, d in enumerate(b["dates"]) if b["coin_pnl"][i, k] != 0]
    zero = [d for d in held_days if P.F[P.idx[d], j] == 0]
    tot_wd += len(held_days); tot_zero += len(zero)
    if zero:
        print(f"   {c:6s} held {len(held_days)} F==0 {len(zero)} first {[str(x) for x in zero[:5]]}")
print(f"   total coin-days held {tot_wd}, with F == 0: {tot_zero} ({tot_zero / max(tot_wd, 1):.2%})")

# months with klines but no funding file, per held coin, inside the A window
print("\n-- months with a 1d file but no fundingRate file (A window) for held coins and the static 24")
kl = collections.defaultdict(set); fu = collections.defaultdict(set)
for cache in data.CACHES:
    for fn in os.listdir(cache):
        if not fn.startswith("binance-"):
            continue
        parts = fn.split("-"); coin = parts[1][:-4]
        if coin not in allc:
            continue
        ym = f"{parts[3]}-{parts[4][:2]}"
        (kl if "-1d-" in fn else fu)[coin].add(ym)
for c in allc:
    miss = sorted(m for m in kl[c] - fu[c] if "2020-05" <= m <= "2026-09")
    if miss:
        print(f"   {c}: {miss}")

# Stress: impute funding on every held coin-day with F == 0 by the cross-section mean of the nonzero funding of BTC/ETH that day,
# and separately add a flat +10 %/yr funding drag to the coins only UNI-1 holds (SOL, MATIC, AVAX, DOGE, 1000PEPE) on their held days.
print("\n== stress lines")
for name, o in out.items():
    r, b = o["r"], o["b"]
    cols = r["cols"]; cp = r["coin_pnl"]; dates = r["dates"]
    jb, je = P.ci["BTC"], P.ci["ETH"]
    adj = r["rets"].copy()
    nimp = 0
    for k, c in enumerate(cols):
        j = P.ci[c]
        for i, d in enumerate(dates):
            if cp[i, k] != 0 and P.F[P.idx[d], j] == 0:
                t = P.idx[d]
                ref = np.mean([x for x in (P.F[t, jb], P.F[t, je]) if x != 0] or [0.0003])
                # exposure fraction at the start of day d: approximate by the coin's price pnl / day return
                px0, px1 = P.C[t - 1, j], P.C[t, j]
                expo = (cp[i, k] + 0) / (px1 / px0 - 1) if px1 != px0 else 0.0
                adj[i] -= expo * ref; nimp += 1
    print(f"   {name}: imputed {nimp} coin-days; Sharpe {sim.sharpe(r['rets']):.4f} -> {sim.sharpe(adj):.4f}")
    extra = {"SOL", "MATIC", "AVAX", "DOGE", "1000PEPE"}
    adj2 = r["rets"].copy()
    for k, c in enumerate(cols):
        if c not in extra:
            continue
        j = P.ci[c]
        for i, d in enumerate(dates):
            if cp[i, k] != 0:
                t = P.idx[d]; px0, px1 = P.C[t - 1, j], P.C[t, j]
                expo = cp[i, k] / (px1 / px0 - 1 - P.F[t, j]) if (px1 / px0 - 1 - P.F[t, j]) != 0 else 0.0
                adj2[i] -= abs(expo) * 0.10 / 365
    print(f"   {name}: +10 %/yr extra funding on the 5 UNI-only coins: Sharpe {sim.sharpe(r['rets']):.4f} -> {sim.sharpe(adj2):.4f} (static-24 {sim.sharpe(b['rets']):.4f})")

# funding level comparison: annualized funding paid per unit gross, UNI-1 vs static-24
for name, o in out.items():
    r, b = o["r"], o["b"]
    print(f"   {name}: funding paid/yr (fraction of equity) UNI-1 {r['fund_frac'].sum() / len(r['rets']) * 365:.3%} at mean gross {r['gross'].mean():.3f}; "
          f"static-24 {b['fund_frac'].sum() / len(b['rets']) * 365:.3%} at mean gross {b['gross'].mean():.3f}")
