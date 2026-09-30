#!/usr/bin/env python3
"""Per-fill edge attribution for Delta fills, using Binance spot 1-second closes.

For each fill:
  capture   = side * (delta_mark_at_fill - fill_price) / price     (bps, spread earned vs fair)
  markout_h = side * (binance(t+h) - binance(t)) / binance(t)      (bps, adverse selection)
  pre_k     = side * (binance(t) - binance(t-k)) / binance(t)      (bps, negative = price ran
                                                                     into our resting quote)
  net_h     = capture + markout_h - fee_bps

Binance 1s klines come from data.binance.vision daily dumps (cached in --cache).
Fills from today are skipped because the daily dump is not published yet.

    python3 markout_report.py --fills /tmp/fills.json --cache /tmp/bn [--since 2026-09-29T10:36]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import io
import json
import urllib.request
import zipfile
from pathlib import Path

HORIZONS = [1, 5, 30, 60, 300]
PRE = [5, 30, 60]
BINANCE_SYMBOL = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT", "SOLUSD": "SOLUSDT"}


def binance_symbol(delta_symbol: str) -> str:
    return BINANCE_SYMBOL.get(delta_symbol, delta_symbol.removesuffix("USD") + "USDT")


def load_klines(symbol: str, day: str, cache: Path) -> dict[int, float]:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{symbol}-1s-{day}.zip"
    if not path.exists():
        url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1s/{path.name}"
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                path.write_bytes(resp.read())
        except OSError as e:
            print(f"  no Binance data for {symbol} {day}: {e}")
            return {}
    out: dict[int, float] = {}
    with zipfile.ZipFile(path) as z:
        for row in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]))):
            t = int(row[0])
            t = t // 1_000_000 if t > 10**14 else t // 1000  # µs since 2025, ms before
            out[t] = float(row[4])
    return out


def enrich(fills: list[dict], cache: Path) -> list[dict]:
    need = {(f["product_symbol"], f["created_at"][:10]) for f in fills}
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    prices: dict[str, dict[int, float]] = collections.defaultdict(dict)
    for sym, day in sorted(need):
        if day >= today:
            continue
        prices[sym].update(load_klines(binance_symbol(sym), day, cache))
    out = []
    for f in fills:
        p = prices.get(f["product_symbol"], {})
        ts = dt.datetime.fromisoformat(f["created_at"].replace("Z", "+00:00")).timestamp()
        t0 = int(ts)
        if t0 not in p or t0 + max(HORIZONS) not in p:
            continue
        side = 1 if f["side"] == "buy" else -1
        price = float(f["price"])
        b0 = p[t0]
        md = f.get("meta_data") or {}
        mark = float(md.get("mark") or price)
        out.append(
            {
                "sym": f["product_symbol"],
                "role": f["role"],
                "side": side,
                "ts": ts,
                "day": f["created_at"][:10],
                "notional": float(f["notional"]),
                "fee_bps": float(f["commission"]) / float(f["notional"]) * 1e4,
                "capture": side * (mark - price) / price * 1e4,
                "mo": {h: side * (p[t0 + h] - b0) / b0 * 1e4 for h in HORIZONS},
                "pre": {k: side * (b0 - p[t0 - k]) / b0 * 1e4 for k in PRE if t0 - k in p},
            }
        )
    return out


def wavg(rows: list[dict], fn) -> float:
    w = sum(r["notional"] for r in rows)
    return sum(fn(r) * r["notional"] for r in rows) / w if w else 0.0


def line(rows: list[dict], name: str) -> str:
    if not rows:
        return f"{name:28s} n=0"
    s = f"{name:28s} n={len(rows):5d} ${sum(r['notional'] for r in rows):>9,.0f}"
    s += f" fee={wavg(rows, lambda r: r['fee_bps']):4.2f} cap={wavg(rows, lambda r: r['capture']):5.2f}"
    s += " mo " + " ".join(f"{h}s:{wavg(rows, lambda r, h=h: r['mo'][h]):5.2f}" for h in HORIZONS)
    s += f" | net60={wavg(rows, lambda r: r['capture'] + r['mo'][60] - r['fee_bps']):5.2f}"
    return s


def cashflow_pnl(fills: list[dict]) -> None:
    print("\nCash-flow PnL per product (position marked at last fill price):")
    by = collections.defaultdict(list)
    for f in sorted(fills, key=lambda f: f["created_at"]):
        by[f["product_symbol"]].append(f)
    for sym, rows in by.items():
        pos = cash = fees = 0.0
        last = 0.0
        role_fee = collections.Counter()
        for f in rows:
            qty = int(f["size"]) * float(f["product"]["contract_value"])
            s = 1 if f["side"] == "buy" else -1
            last = float(f["price"])
            cash -= s * qty * last
            pos += s * qty
            fees += float(f["commission"])
            role_fee[f["role"]] += float(f["commission"])
        gross = cash + pos * last
        print(
            f"  {sym:8s} fills={len(rows):5d} pos={pos:+.4f} gross={gross:+8.2f} "
            f"fees={fees:7.2f} (maker {role_fee['maker']:.2f}, taker {role_fee['taker']:.2f}) net={gross - fees:+8.2f}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", required=True)
    ap.add_argument("--cache", default="/tmp/binance-1s")
    ap.add_argument("--since", help="ISO time; only fills at or after it (compare before/after a change)")
    args = ap.parse_args()
    fills = json.loads(Path(args.fills).read_text())
    if args.since:
        fills = [f for f in fills if f["created_at"] >= args.since]
    cashflow_pnl(fills)
    rows = enrich(fills, Path(args.cache))
    print(f"\nEnriched {len(rows)} of {len(fills)} fills (need Binance 1s data t..t+300s)\n")
    for sym in sorted({r["sym"] for r in rows}):
        for role in ("maker", "taker"):
            print(line([r for r in rows if r["sym"] == sym and r["role"] == role], f"{sym} {role}"))
            if role == "maker":
                for side, name in ((1, "buy"), (-1, "sell")):
                    sel = [r for r in rows if r["sym"] == sym and r["role"] == role and r["side"] == side]
                    print(line(sel, f"  {sym} maker {name}"))
    print("\nMaker fills by day:")
    for day in sorted({r["day"] for r in rows}):
        print(line([r for r in rows if r["day"] == day and r["role"] == "maker"], f"  {day}"))
    maker = [r for r in rows if r["role"] == "maker"]
    if maker:
        print("\nPrice path before maker fills (negative = market ran into our resting quote):")
        for k in PRE:
            vals = sorted(r["pre"][k] for r in maker if k in r["pre"])
            if not vals:
                continue
            n = len(vals)
            toward = sum(v < -1 for v in vals) / n
            print(f"  {k:3d}s before: median {vals[n // 2]:6.2f} bps, {toward:.0%} of fills had >1 bp move toward us")
        print("\nMaker markout by 5s pre-move bucket:")
        for lo, hi in [(-99, -3), (-3, -1), (-1, 1), (1, 99)]:
            print(line([r for r in maker if lo <= r["pre"].get(5, 0) < hi], f"  pre5 in [{lo},{hi})"))


if __name__ == "__main__":
    main()
