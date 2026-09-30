#!/usr/bin/env python3
"""Backtest: selling daily BTC/ETH option premium on Delta Exchange India.

Data (all from Delta's public API, cached to disk):
  - expired option contracts (expired_options.json, from fetch_products.py)
  - MARK price candles of each contract (Delta's fair value), 1 h
  - index candles (.DEXBTUSD / .DEETHUSD), used for entry spot and for settlement:
    Delta settles European options on the 30-minute TWAP of the index before expiry.

Trade: every day, 24 h before the 12:00 UTC expiry, sell the next-day option(s)
at MARK minus a spread haircut, hold to settlement. No stops, no hedging.

Costs: Delta India option fee 0.010% of notional (spot x qty), capped at 3.5% of
premium, +18% GST, charged on each opened leg; ITM legs pay the same again at
settlement (conservative); OTM expiry is free.
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

B = "https://api.india.delta.exchange"
LEVELS = tuple(float(x) for x in os.environ.get("BT_LEVELS", "0,0.01,0.02,0.03,0.04,0.05,0.06").split(","))
SINCE = int(os.environ.get("BT_SINCE", datetime(2025, 9, 29, tzinfo=timezone.utc).timestamp()))
UNTIL = int(os.environ.get("BT_UNTIL", 4102444800))
CACHE = "cache"
os.makedirs(CACHE, exist_ok=True)
INDEX = {"BTC": ".DEXBTUSD", "ETH": ".DEETHUSD"}
FEE_RATE, FEE_CAP, GST = 0.0001, 0.035, 1.18


def get(path: str, params: dict) -> dict:
    key = os.path.join(CACHE, (path + "_" + urllib.parse.urlencode(params)).replace("/", "_").replace(":", "_")[:200] + ".json")
    if os.path.exists(key):
        with open(key) as f:
            return json.load(f)
    url = f"{B}{path}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            with open(key, "w") as f:
                json.dump(d, f)
            return d
        except Exception as e:  # network is slow/flaky here; back off and retry
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def candles(symbol: str, resolution: str, start: int, end: int) -> list[dict]:
    d = get("/v2/history/candles", {"resolution": resolution, "symbol": symbol, "start": start, "end": end})
    return sorted(d.get("result") or [], key=lambda c: c["time"])


def ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def fee(spot: float, cv: float, premium: float) -> float:
    return min(FEE_RATE * spot * cv, FEE_CAP * premium) * GST


# ------------------------------------------------------------------ data per expiry

def day_data(underlying: str, expiry: int, contracts: list[dict]) -> dict | None:
    entry = expiry - 86400
    idx_entry = candles(INDEX[underlying], "1m", entry - 120, entry + 60)
    idx_settle = candles(INDEX[underlying], "1m", expiry - 1800, expiry - 60)
    if not idx_entry or len(idx_settle) < 20:
        return None
    s0 = idx_entry[-1]["open"] if idx_entry[-1]["time"] <= entry else idx_entry[0]["close"]
    twap = st.mean(c["close"] for c in idx_settle)
    live = [c for c in contracts if c["launch_time"] and ts(c["launch_time"]) <= entry]
    if not live:
        return None
    # Fetch marks only for the strikes the structures use: nearest listed strike at or
    # beyond each target distance from spot, falling back outward if a mark is missing.
    marks: dict[str, float] = {}
    picks: dict[tuple[str, float], dict] = {}
    for typ in ("C", "P"):
        for pct in LEVELS:
            target = s0 * (1 + pct) if typ == "C" else s0 * (1 - pct)
            cands = [c for c in live if c["type"] == typ and (c["strike"] >= target - 1e-9 if typ == "C" else c["strike"] <= target + 1e-9)]
            cands.sort(key=lambda c: c["strike"] if typ == "C" else -c["strike"])
            if not cands:
                # Target beyond the listed grid (price moved since listing): use the furthest
                # listed strike instead of dropping the day, which would bias out big moves.
                cands = sorted((c for c in live if c["type"] == typ), key=lambda c: -c["strike"] if typ == "C" else c["strike"])
            for c in cands[:3]:
                if c["symbol"] not in marks:
                    rows = candles("MARK:" + c["symbol"], "1h", entry - 3600, entry + 3600)
                    at = [r for r in rows if r["time"] == entry] or [r for r in rows if r["time"] < entry]
                    if not at:
                        continue
                    marks[c["symbol"]] = at[-1]["open"] if at[-1]["time"] == entry else at[-1]["close"]
                picks[(typ, pct)] = c
                break
    return {"underlying": underlying, "expiry": expiry, "s0": s0, "settle": twap, "picks": picks, "marks": marks}


# ------------------------------------------------------------------ structures

def pick(day: dict, typ: str, pct: float) -> dict | None:
    c = day["picks"].get((typ, pct))
    return c if c and c["symbol"] in day["marks"] else None


def leg_pnl(day: dict, c: dict, side: int, haircut: float) -> tuple[float, float, float]:
    """(pnl per 1 underlying unit, premium per unit, max-loss contribution) for one leg; side -1 = sold."""
    mark = day["marks"][c["symbol"]]
    price = mark * (1 - haircut) if side < 0 else mark * (1 + haircut)
    s0, st_ = day["s0"], day["settle"]
    intrinsic = max(st_ - c["strike"], 0) if c["type"] == "C" else max(c["strike"] - st_, 0)
    cv = 1.0  # per 1 unit of underlying; fees scale linearly
    cost = fee(s0, cv, price) + (FEE_RATE * st_ * cv * GST if intrinsic > 0 else 0.0)
    pnl = -side * price + side * intrinsic - cost
    return pnl, price, intrinsic


def structure(day: dict, name: str, haircut: float) -> dict | None:
    legs: list[tuple[str, float, int]]  # (type, pct OTM, side)
    if name == "straddle":
        legs = [("C", 0.0, -1), ("P", 0.0, -1)]
    elif name.startswith("strangle"):
        k = float(name.split("_")[1]) / 100
        legs = [("C", k, -1), ("P", k, -1)]
    elif name.startswith("condor"):
        k, w = (float(x) / 100 for x in name.split("_")[1:3])
        legs = [("C", k, -1), ("P", k, -1), ("C", k + w, 1), ("P", k + w, 1)]
    elif name.startswith("put"):
        k = float(name.split("_")[1]) / 100
        legs = [("P", k, -1)]
    elif name.startswith("call"):
        k = float(name.split("_")[1]) / 100
        legs = [("C", k, -1)]
    else:
        raise ValueError(name)
    chosen = []
    for typ, pct, side in legs:
        c = pick(day, typ, pct)
        if c is None:
            return None
        chosen.append((c, side))
    if len({c["symbol"] for c, _ in chosen}) != len(chosen):
        return None  # wing collapsed onto the short strike
    pnl = credit = 0.0
    for c, side in chosen:
        p, price, _ = leg_pnl(day, c, side, haircut)
        pnl += p
        credit += -side * price
    s0 = day["s0"]
    max_risk = None
    if name.startswith("condor"):
        shorts = {c["type"]: c["strike"] for c, s in chosen if s < 0}
        longs = {c["type"]: c["strike"] for c, s in chosen if s > 0}
        width = max(longs["C"] - shorts["C"], shorts["P"] - longs["P"])
        max_risk = max(width - credit, 1e-9)
    return {
        "date": datetime.fromtimestamp(day["expiry"], timezone.utc).strftime("%Y-%m-%d"),
        "pnl_bps": pnl / s0 * 1e4,        # per unit of underlying notional
        "credit_bps": credit / s0 * 1e4,
        "move_pct": (day["settle"] / s0 - 1) * 100,
        "max_risk_bps": None if max_risk is None else max_risk / s0 * 1e4,
    }


def stats(rows: list[dict]) -> dict:
    p = [r["pnl_bps"] for r in rows]
    cum, peak, dd = 0.0, 0.0, 0.0
    for x in p:
        cum += x
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    sd = st.stdev(p) if len(p) > 1 else float("nan")
    out = {
        "n": len(p),
        "win": sum(x > 0 for x in p) / len(p),
        "mean": st.mean(p),
        "median": st.median(p),
        "sd": sd,
        "worst": min(p),
        "best": max(p),
        "total": sum(p),
        "max_dd": dd,
        "sharpe": st.mean(p) / sd * math.sqrt(365) if sd and sd > 0 else float("nan"),
        "t": st.mean(p) / (sd / math.sqrt(len(p))) if sd and sd > 0 else float("nan"),
        "credit": st.mean(r["credit_bps"] for r in rows),
    }
    risks = [r["max_risk_bps"] for r in rows if r["max_risk_bps"]]
    if risks:
        out["ror"] = st.mean(r["pnl_bps"] / r["max_risk_bps"] for r in rows if r["max_risk_bps"])
    return out


def main():
    products = json.load(open("expired_options.json"))
    by_exp: dict[tuple[str, int], list[dict]] = {}
    for c in products:
        if not c.get("settlement_time") or not c["settlement_time"].endswith("12:00:00Z"):
            continue
        by_exp.setdefault((c["underlying"], ts(c["settlement_time"])), []).append(c)
    # Daily contracts: listed ≤ ~3 days before expiry. Keep expiries that had a contract live 24 h before.
    keys = sorted(k for k, cs in by_exp.items() if SINCE <= k[1] < UNTIL and any(c["launch_time"] and ts(c["launch_time"]) <= k[1] - 86400 for c in cs))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        keys = [k for k in keys if k[0] == only]
    print(f"{len(keys)} expiries to load ({keys[0][1] and datetime.fromtimestamp(keys[0][1], timezone.utc):%Y-%m-%d} → {datetime.fromtimestamp(keys[-1][1], timezone.utc):%Y-%m-%d})", file=sys.stderr)
    days = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(day_data, u, e, by_exp[(u, e)]): (u, e) for u, e in keys}
        for i, f in enumerate(futs):
            try:
                d = f.result()
                if d:
                    days.append(d)
            except Exception as e:
                print("skip", futs[f], e, file=sys.stderr)
            if i % 20 == 0:
                print(f"  loaded {i}/{len(futs)}", file=sys.stderr)
    days.sort(key=lambda d: (d["underlying"], d["expiry"]))
    json.dump([{k: v for k, v in d.items() if k != "picks"} | {"picks": {f"{t}{p}": c["symbol"] for (t, p), c in d["picks"].items()}} for d in days], open("days.json", "w"))

    structures = ["straddle", "strangle_1", "strangle_2", "strangle_3", "strangle_4",
                  "condor_2_2", "condor_3_2", "condor_2_4", "put_2", "put_3", "call_2", "call_3"]
    report = {}
    for u in ("BTC", "ETH"):
        ud = [d for d in days if d["underlying"] == u]
        if not ud:
            continue
        # Volatility risk premium: ATM straddle price vs realised absolute move.
        vrp = []
        for d in ud:
            r = structure(d, "straddle", 0.0)
            if r:
                vrp.append((r["credit_bps"], abs(r["move_pct"]) * 100))
        report[u] = {"days": len(ud), "from": ud[0]["expiry"], "to": ud[-1]["expiry"],
                     "vrp": {"implied_move_bps": st.mean(a for a, _ in vrp), "realised_move_bps": st.mean(b for _, b in vrp)} if vrp else None,
                     "results": {}}
        for hc in (0.0, 0.05, 0.10):
            for s in structures:
                rows = [r for d in ud if (r := structure(d, s, hc))]
                if len(rows) >= 10:
                    report[u]["results"][f"{s}@{int(hc*100)}"] = stats(rows) | {"rows": rows if hc == 0.05 else None}
    json.dump(report, open("report.json", "w"), default=str)
    for u, r in report.items():
        print(f"\n=== {u}: {r['days']} daily expiries {datetime.fromtimestamp(r['from'], timezone.utc):%Y-%m-%d} → {datetime.fromtimestamp(r['to'], timezone.utc):%Y-%m-%d}")
        if r["vrp"]:
            print(f"ATM straddle premium (implied move) {r['vrp']['implied_move_bps']:.0f} bps vs realised |move| {r['vrp']['realised_move_bps']:.0f} bps")
        print(f"{'structure@haircut':22s} {'n':>4s} {'win':>5s} {'mean':>7s} {'median':>7s} {'sd':>6s} {'worst':>7s} {'total':>8s} {'maxDD':>8s} {'sharpe':>6s} {'t':>5s} {'credit':>6s} {'RoR':>6s}")
        for k, s in r["results"].items():
            print(f"{k:22s} {s['n']:>4d} {s['win']:>5.0%} {s['mean']:>+7.1f} {s['median']:>+7.1f} {s['sd']:>6.1f} {s['worst']:>+7.0f} {s['total']:>+8.0f} {s['max_dd']:>+8.0f} {s['sharpe']:>6.2f} {s['t']:>+5.2f} {s['credit']:>6.1f} {s.get('ror', float('nan')):>+6.1%}")


if __name__ == "__main__":
    main()
