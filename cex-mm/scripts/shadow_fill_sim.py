#!/usr/bin/env python3
"""Shadow-test fill simulator: replay dry-run quotes against recorded Delta mainnet trades.

Inputs (from `scripts/shadow.sh start`):
  - dry-run log with `MM_METRICS` JSON lines (quotes, fair, Delta top of book, Binance mid)
  - `record-delta` JSONL with the Delta public `trades` channel

A resting quote fills when an aggressive trade on the other side prints through it:
  strict (default): sell prints strictly below our bid / buy strictly above our ask.
                    A quote inside the Delta spread is first in line, so any aggressor fills it.
  touch:            also fills when the trade prints exactly at our price (optimistic: ignores
                    the queue ahead of us when we join an existing level).
Quotes take `--latency-ms` to go live, move only when the target drifts more than
`--requote-tol-bps` (like the bot's OMS), and vanish when the dry-run stops logging
(warm-up, regime pause, kill). Inventory is capped at `--max-inv-orders` quotes; the
dry-run itself always has zero inventory, so inventory skew is not simulated.

Per fill: capture = side * (delta_mid - price), markout(h) = side * (delta_mid(t+h) - delta_mid(t)),
net(h) = capture + markout(h) - maker fee. All in bps.

    python3 scripts/shadow_fill_sim.py --run-dir artifacts/shadow/<run>
    python3 scripts/shadow_fill_sim.py --run-dir artifacts/shadow/<run> --sweep 3,4,5,6,8 --latencies 0,300,1000
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import gzip
import json
import math
import os
import urllib.request
from dataclasses import dataclass, field

HORIZONS = [1, 5, 30, 60, 300]
REGIME_MULT = {0: 1.0, 1: 1.5, 2: 2.25}


# ---------------------------------------------------------------- loading

def open_text(path: str):
    return gzip.open(path, "rt", errors="replace") if path.endswith(".gz") else open(path, errors="replace")


def iter_lines(path: str):
    f = open_text(path)
    try:
        for line in f:
            yield line
    except EOFError:
        pass  # gzip still being written by the running dry-run
    finally:
        f.close()


@dataclass(slots=True)
class Sample:
    ts: float  # local wall clock, ms
    fair: float
    bid: float
    ask: float
    place_bid: bool
    place_ask: bool
    regime: int
    book_bid: float
    book_ask: float
    binance_mid: float


def parse_metrics_line(line: str) -> tuple[str, Sample] | None:
    """One dry-run log line -> (symbol, Sample), or None if it is not a usable MM_METRICS line."""
    if "MM_METRICS" not in line:
        return None
    start, end = line.find("{"), line.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        m = json.loads(line[start : end + 1])
    except json.JSONDecodeError:
        return None
    if "ts_ms" not in m or not m.get("book_bid"):
        return None
    return m["symbol"], Sample(
        ts=float(m["ts_ms"]),
        fair=float(m["fair"]),
        bid=float(m["bid"]),
        ask=float(m["ask"]),
        place_bid=bool(m["place_bid"]),
        place_ask=bool(m["place_ask"]),
        regime=int(m.get("regime_level", 0)),
        book_bid=float(m["book_bid"]),
        book_ask=float(m["book_ask"]),
        binance_mid=float(m.get("binance_mid") or 0.0),
    )


def load_metrics(paths: list[str]) -> dict[str, list[Sample]]:
    out: dict[str, list[Sample]] = collections.defaultdict(list)
    for path in paths:
        for line in iter_lines(path):
            parsed = parse_metrics_line(line)
            if parsed:
                out[parsed[0]].append(parsed[1])
    for s in out.values():
        s.sort(key=lambda x: x.ts)
    return out


@dataclass(slots=True)
class Trade:
    ts: float  # local receive time, ms
    price: float
    size: float  # contracts
    aggressor: int  # +1 buy (hits asks), -1 sell (hits bids)


def parse_trade_record(line: str) -> tuple[str, Trade, float] | None:
    """One recorder JSONL line -> (delta_symbol, Trade, exchange_ts_ms), or None."""
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None
    m = rec.get("msg")
    if not isinstance(m, dict) or m.get("type") != "trades":
        return None
    # `r` is the buyer's role: "t" = buyer was taker (aggressive buy), "m" = aggressive sell.
    role = m.get("r")
    if role not in ("t", "m"):
        return None
    trade = Trade(
        ts=rec["recv_us"] / 1000.0,
        price=float(m["p"]),
        size=float(m["s"]),
        aggressor=1 if role == "t" else -1,
    )
    return m["sy"], trade, float(m.get("t") or 0) / 1000.0


def load_trades(paths: list[str]) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = collections.defaultdict(list)
    for path in paths:
        for line in iter_lines(path):
            parsed = parse_trade_record(line)
            if parsed:
                out[parsed[0]].append(parsed[1])
    for t in out.values():
        t.sort(key=lambda x: x.ts)
    return out


def product_meta(delta_symbol: str) -> tuple[float, float]:
    url = f"https://api.india.delta.exchange/v2/products/{delta_symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "cex-mm-shadow/0.1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        r = json.loads(resp.read())["result"]
    return float(r["tick_size"]), float(r["contract_value"])


def delta_symbol(mm_symbol: str) -> str:
    return mm_symbol[:-1] if mm_symbol.endswith("USDT") else mm_symbol


# ---------------------------------------------------------------- simulation

@dataclass
class Fill:
    ts: float
    side: int  # +1 bought, -1 sold
    price: float
    qty: float  # contracts
    notional: float
    fee: float
    mid: float
    fair: float


@dataclass
class SideState:
    price: float | None = None
    remaining: float = 0.0
    dead_until: float = 0.0  # after a full fill, the bot needs a loop + latency to requote


@dataclass
class SimConfig:
    latency_ms: float
    half_spread_bps: float | None  # None = use the bot's logged quotes
    rule: str  # strict | touch
    quote_usd: float
    max_inv_orders: int
    fee_bps: float
    requote_tol_bps: float
    max_gap_ms: float
    loop_ms: float


@dataclass
class SimResult:
    fills: list[Fill] = field(default_factory=list)
    quoted_ms: float = 0.0
    inside_ms: float = 0.0
    span_ms: float = 0.0
    final_inv: float = 0.0


def floor_tick(px: float, tick: float) -> float:
    return round(math.floor(px / tick + 1e-9) * tick, 12)


def ceil_tick(px: float, tick: float) -> float:
    return round(math.ceil(px / tick - 1e-9) * tick, 12)


def targets(s: Sample, cfg: SimConfig, tick: float) -> tuple[float | None, float | None]:
    if cfg.half_spread_bps is None:
        bid, ask = s.bid, s.ask
    else:
        h = cfg.half_spread_bps * REGIME_MULT.get(s.regime, 1.0) / 1e4
        bid = floor_tick(s.fair * (1 - h), tick)
        ask = ceil_tick(s.fair * (1 + h), tick)
        # Post-only: never cross the book the quote was computed from.
        bid = min(bid, s.book_ask - tick)
        ask = max(ask, s.book_bid + tick)
    return (bid if s.place_bid else None), (ask if s.place_ask else None)


def simulate(samples: list[Sample], trades: list[Trade], tick: float, cv: float, cfg: SimConfig) -> SimResult:
    res = SimResult()
    if not samples:
        return res
    ref_px = samples[len(samples) // 2].fair
    qty = max(1.0, round(cfg.quote_usd / (ref_px * cv)))
    max_inv = qty * cfg.max_inv_orders
    sides = {1: SideState(), -1: SideState()}  # +1 = our bid, -1 = our ask
    inv = 0.0
    alive_until = 0.0
    si = 0
    last_eff = None
    last_sample: Sample | None = None

    def apply_sample(s: Sample) -> None:
        nonlocal alive_until, last_sample
        eff = s.ts + cfg.latency_ms
        tb, ta = targets(s, cfg, tick)
        for side, tgt in ((1, tb), (-1, ta)):
            st = sides[side]
            if tgt is None:
                st.price, st.remaining = None, 0.0
                continue
            if st.remaining <= 0 and eff < st.dead_until:
                continue
            moved = st.price is None or abs(tgt - st.price) / tgt * 1e4 > cfg.requote_tol_bps
            if moved or st.remaining <= 0:
                st.price, st.remaining = tgt, qty
        alive_until = eff + cfg.max_gap_ms
        last_sample = s

    def advance(to_ms: float) -> None:
        nonlocal si, last_eff
        while si < len(samples) and samples[si].ts + cfg.latency_ms <= to_ms:
            s = samples[si]
            eff = s.ts + cfg.latency_ms
            if last_eff is not None and last_sample is not None:
                live_to = min(eff, alive_until)
                dt = max(0.0, live_to - last_eff)
                if sides[1].price and sides[-1].price and sides[1].remaining > 0 and sides[-1].remaining > 0:
                    res.quoted_ms += dt
                    if sides[1].price > last_sample.book_bid or sides[-1].price < last_sample.book_ask:
                        res.inside_ms += dt
            apply_sample(s)
            last_eff = eff
            si += 1

    for t in trades:
        advance(t.ts)
        if last_sample is None or t.ts > alive_until:
            continue
        side = -t.aggressor  # aggressive sell (-1) hits our bid (+1)
        st = sides[side]
        if st.price is None or st.remaining <= 0:
            continue
        through = (t.price < st.price) if side == 1 else (t.price > st.price)
        at = abs(t.price - st.price) < tick / 2
        if not (through or (cfg.rule == "touch" and at)):
            continue
        q = min(st.remaining, t.size)
        if side * inv >= 0:  # adding to (or opening) a position
            q = min(q, max_inv - abs(inv))
        if q <= 0:
            continue
        notional = q * cv * st.price
        s = last_sample
        res.fills.append(
            Fill(
                ts=t.ts,
                side=side,
                price=st.price,
                qty=q,
                notional=notional,
                fee=notional * cfg.fee_bps / 1e4,
                mid=(s.book_bid + s.book_ask) / 2,
                fair=s.fair,
            )
        )
        inv += side * q
        st.remaining -= q
        if st.remaining <= 0:
            st.dead_until = t.ts + cfg.loop_ms + cfg.latency_ms
    advance(float("inf"))
    res.span_ms = samples[-1].ts - samples[0].ts
    res.final_inv = inv
    return res


# ---------------------------------------------------------------- reporting

class MidSeries:
    def __init__(self, samples: list[Sample]):
        self.ts = [s.ts for s in samples]
        self.mid = [(s.book_bid + s.book_ask) / 2 for s in samples]

    def at(self, t: float) -> float | None:
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0 or t - self.ts[i] > 5_000:
            return None
        return self.mid[i]


def summarize(res: SimResult, mids: MidSeries, cv: float) -> dict:
    rows = []
    for f in res.fills:
        mo = {}
        for h in HORIZONS:
            m = mids.at(f.ts + h * 1000)
            if m is None:
                break
            mo[h] = f.side * (m - f.mid) / f.mid * 1e4
        else:
            rows.append((f, f.side * (f.mid - f.price) / f.price * 1e4, mo))
    w = sum(f.notional for f, _, _ in rows)

    def wavg(fn) -> float:
        return sum(fn(f, c, mo) * f.notional for f, c, mo in rows) / w if w else 0.0

    days = max(res.span_ms / 86_400_000, 1e-9)
    # Cash-flow PnL (all fills), final inventory marked at the last mid.
    cash = sum(-f.side * f.qty * cv * f.price for f in res.fills)
    fees = sum(f.fee for f in res.fills)
    last_mid = mids.mid[-1] if mids.mid else 0.0
    total = cash + res.final_inv * cv * last_mid - fees
    spread_usd = sum(f.side * (f.mid - f.price) * f.qty * cv for f in res.fills)
    fee_bps = wavg(lambda f, c, mo: f.fee / f.notional * 1e4)
    return {
        "fills": len(res.fills),
        "scored": len(rows),
        "days": days,
        "fills_per_day": len(res.fills) / days,
        "usd_per_day": sum(f.notional for f in res.fills) / days,
        "uptime": res.quoted_ms / res.span_ms if res.span_ms else 0.0,
        "inside": res.inside_ms / res.quoted_ms if res.quoted_ms else 0.0,
        "capture": wavg(lambda f, c, mo: c),
        "mo": {h: wavg(lambda f, c, mo, h=h: mo[h]) for h in HORIZONS},
        "fee": fee_bps,
        "net60": wavg(lambda f, c, mo: c + mo[60]) - fee_bps,
        "net300": wavg(lambda f, c, mo: c + mo[300]) - fee_bps,
        "pnl_total": total,
        "pnl_spread": spread_usd,
        "pnl_fees": -fees,
        "pnl_inventory": total + fees - spread_usd,
        "final_inv": res.final_inv,
    }


def verdict(s: dict, min_fills: int, target: float) -> str:
    if s["scored"] < min_fills:
        return f"CONTINUE ({s['scored']}/{min_fills} fills)"
    if s["net60"] >= target:
        return "PASS"
    if s["net60"] < 0:
        return "STOP"
    return "INCONCLUSIVE"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--latency-ms", type=float, default=300)
    ap.add_argument("--latencies", help="comma list; latency sensitivity for the bot's own quotes")
    ap.add_argument("--sweep", help="comma list of half-spreads (bps) around the logged fair")
    ap.add_argument("--rule", choices=["strict", "touch"], default="strict")
    ap.add_argument("--quote-usd", type=float, default=50.0, help="notional per quote")
    ap.add_argument("--max-inv-orders", type=int, default=3)
    ap.add_argument("--fee-bps", type=float, default=2.12, help="maker fee incl. GST")
    ap.add_argument("--requote-tol-bps", type=float, default=3.0)
    ap.add_argument("--max-gap-ms", type=float, default=1500)
    ap.add_argument("--loop-ms", type=float, default=400)
    ap.add_argument("--min-fills", type=int, default=300)
    ap.add_argument("--target-bps", type=float, default=0.5)
    args = ap.parse_args()

    metric_paths = sorted(glob.glob(os.path.join(args.run_dir, "dry-run*.log*")))
    trade_paths = sorted(glob.glob(os.path.join(args.run_dir, "delta_mainnet_public_*.jsonl")))
    metrics = load_metrics(metric_paths)
    trades = load_trades(trade_paths)
    if not metrics:
        raise SystemExit(f"no MM_METRICS samples in {metric_paths}")

    base = dict(
        rule=args.rule,
        quote_usd=args.quote_usd,
        max_inv_orders=args.max_inv_orders,
        fee_bps=args.fee_bps,
        requote_tol_bps=args.requote_tol_bps,
        max_gap_ms=args.max_gap_ms,
        loop_ms=args.loop_ms,
    )
    for sym in sorted(metrics):
        samples = metrics[sym]
        dsym = delta_symbol(sym)
        tape = trades.get(dsym, [])
        tick, cv = product_meta(dsym)
        mids = MidSeries(samples)
        span_h = (samples[-1].ts - samples[0].ts) / 3.6e6
        spreads = sorted((s.book_ask - s.book_bid) / ((s.book_ask + s.book_bid) / 2) * 1e4 for s in samples)
        quoted = sorted((s.ask - s.bid) / s.fair * 1e4 / 2 for s in samples)
        tape_usd = sum(t.size * cv * t.price for t in tape)
        print(f"\n=== {sym} ({dsym})  tick={tick} contract={cv}  {span_h:.1f} h of quotes, {len(samples)} samples")
        print(
            f"Delta touch spread median {spreads[len(spreads) // 2]:.2f} bps | bot half-spread median "
            f"{quoted[len(quoted) // 2]:.2f} bps | tape {len(tape)} trades, ${tape_usd:,.0f} "
            f"({sum(t.aggressor > 0 for t in tape)} buys / {sum(t.aggressor < 0 for t in tape)} sells)"
        )
        header = (
            f"{'config':22s} {'fills':>6s} {'/day':>6s} {'$/day':>8s} {'up%':>5s} {'in%':>5s} "
            f"{'capt':>6s} " + " ".join(f"{f'mo{h}':>6s}" for h in HORIZONS) + f" {'fee':>5s} {'net60':>6s} {'net300':>6s} "
            f"{'PnL$':>7s} {'spr$':>7s} {'inv$':>7s} {'fee$':>7s}  verdict"
        )
        print(header)

        def row(label: str, cfg: SimConfig) -> None:
            s = summarize(simulate(samples, tape, tick, cv, cfg), mids, cv)
            print(
                f"{label:22s} {s['fills']:6d} {s['fills_per_day']:6.0f} {s['usd_per_day']:8,.0f} "
                f"{s['uptime']:5.0%} {s['inside']:5.0%} {s['capture']:6.2f} "
                + " ".join(f"{s['mo'][h]:6.2f}" for h in HORIZONS)
                + f" {s['fee']:5.2f} {s['net60']:6.2f} {s['net300']:6.2f} "
                f"{s['pnl_total']:7.2f} {s['pnl_spread']:7.2f} {s['pnl_inventory']:7.2f} {s['pnl_fees']:7.2f}  "
                f"{verdict(s, args.min_fills, args.target_bps)}"
            )

        row(f"bot quotes {args.latency_ms:.0f}ms", SimConfig(latency_ms=args.latency_ms, half_spread_bps=None, **base))
        if args.latencies:
            for lat in (float(x) for x in args.latencies.split(",")):
                if lat != args.latency_ms:
                    row(f"bot quotes {lat:.0f}ms", SimConfig(latency_ms=lat, half_spread_bps=None, **base))
        if args.sweep:
            for h in (float(x) for x in args.sweep.split(",")):
                row(f"fair +/- {h:g}bps", SimConfig(latency_ms=args.latency_ms, half_spread_bps=h, **base))
    print(
        f"\nRule: {args.rule}; ${args.quote_usd:g}/quote; inventory cap {args.max_inv_orders} quotes; "
        f"maker fee {args.fee_bps} bps. Verdict: PASS if net60 >= {args.target_bps} bps over >= {args.min_fills} "
        f"fills, STOP if net60 < 0. up% = both sides quoted; in% = at least one side inside the Delta touch."
    )


if __name__ == "__main__":
    main()
