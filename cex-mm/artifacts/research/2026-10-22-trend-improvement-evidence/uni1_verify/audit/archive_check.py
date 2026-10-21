#!/usr/bin/env python3
"""Archive completeness: (a) month holes in the cached 1d files of every pool symbol; (b) for coins that rank in the top 30 of the
no-age-floor shadow at any UNI-1 reset (and the static 24), compare the cached 1d months with the live S3 listing of
data.binance.vision (public, read-only) to find silently failed downloads; (c) candidates kept out by the age floor."""
import sys, os, re, json, collections, urllib.request, datetime as dt
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2"); sys.path.insert(0, f"{SP}/uni1_verify/audit")
import numpy as np
import data
import variants_universe as vu

P = vu.load_pool(); ctx = vu._ctx(P)
kl = collections.defaultdict(set); fu = collections.defaultdict(set)
for cache in data.CACHES:
    for fn in os.listdir(cache):
        if not fn.startswith("binance-") or fn.split("-")[1] == "spot":
            continue
        parts = fn.split("-"); coin = parts[1][:-4]
        ym = f"{parts[3]}-{parts[4][:2]}"
        (kl if "-1d-" in fn else fu)[coin].add(ym)


def months(a, b):
    y, m = map(int, a.split("-")); out = []
    while f"{y}-{m:02d}" <= b:
        out.append(f"{y}-{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


holes = {}
for c in P.coins:
    ms = sorted(kl[c])
    if not ms:
        continue
    h = [m for m in months(ms[0], ms[-1]) if m not in kl[c]]
    if h:
        holes[c] = h
print(f"(a) pool symbols with month holes in cached 1d files: {len(holes)}")
for c, h in holes.items():
    print(f"   {c}: {h}")

# (b) top-30 shadow candidates at each reset (no age floor, no exclusions besides the plan's), both resets schedules
cands = set(data.EXANTE24)
blocked = []
for sched in ("yearly", "quarterly"):
    for weekly in (False, True):
        rows = vu._reset_rows(ctx, weekly, sched)
        for r in rows:
            _, rank = vu._select(ctx, r, {}, 9, 18, None)
            for j, k in rank.items():
                if k <= 30:
                    cands.add(ctx.coins[j])
                if k <= 18 and ctx.AGE[r, j] < 365:
                    blocked.append((str(P.dates[r]), sched, weekly, ctx.coins[j], k, int(ctx.AGE[r, j])))
print(f"\n(c) coins ranked <= 18 by turnover (no age floor) but with age < 365 at a reset: {len(set(b[3] for b in blocked))} coins")
seen = set()
for b in blocked:
    if b[1] == "yearly" and not b[2]:
        print("   ", b)


def s3_months(sym):
    url = f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/{sym}USDT/1d/"
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "audit"}), timeout=30).read().decode()
    return set(re.findall(rf"{sym}USDT-1d-(\d{{4}}-\d{{2}})\.zip<", xml))


def s3_funding_first(sym):
    url = f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/fundingRate/{sym}USDT/"
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "audit"}), timeout=30).read().decode()
    ms = sorted(set(re.findall(rf"{sym}USDT-fundingRate-(\d{{4}}-\d{{2}})\.zip<", xml)))
    return ms


chk = sorted(cands | set(holes) | {b[3] for b in blocked} | {"LUNA", "FTT", "SRM"})
print(f"\n(b) S3 listing vs cache for {len(chk)} symbols (top-30 shadow at any reset, static 24, symbols with holes, age-blocked)")
bad = 0
for c in chk:
    try:
        s3 = s3_months(c)
    except Exception as e:
        print(f"   {c}: S3 error {e}"); continue
    s3w = {m for m in s3 if m <= "2026-09"}
    missing = sorted(s3w - kl[c]); extra = sorted(kl[c] - s3w)
    fm = s3_funding_first(c) if c in {b[3] for b in blocked} or c in ("LUNA", "FTT", "SRM") else []
    if missing or extra or fm:
        bad += bool(missing or extra)
        print(f"   {c}: S3 months {len(s3w)} cached {len(kl[c])} missing-from-cache {missing} extra {extra}"
              + (f" | first S3 kline month {min(s3w) if s3w else None}, first funding month {fm[0] if fm else None}" if fm else ""))
print(f"   symbols with a cache/S3 mismatch: {bad}")
