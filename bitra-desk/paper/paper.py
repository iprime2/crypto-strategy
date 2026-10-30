#!/usr/bin/env python3
"""bitra-desk paper account: the desk's would-be trades, taken one position at a time.

The sandbox desk writes an intent whenever every gate passes, even while an earlier one would still
be open, so its record overstates how many trades a real account takes. This replays the intents the
way venue mode would trade them: one position at a time, an intent while a position is open is
skipped, entry at the open of the first 5-minute bar that starts once the cycle has finished (the
decision exists only then), the size and levels the
intent carries, out at the stop, the take or the 12-hour hold limit (a bar that reaches both levels
counts as the stop, as `tra hindsight` does), net of the round trip the intent priced. Nothing is sent
anywhere: the only network call is Bybit's public kline endpoint, cached on disk.

    python3 paper.py --desk ~/bitra/desk --out ~/bitra/paper     # writes state.json, candles.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BAR_MS = 300_000
KLINE_URL = "https://api.bybit.com/v5/market/kline"


def cycle_ms(cycle_id: str) -> int:
    """`2026-10-29T10-00-03Z-BTCUSDT` -> epoch milliseconds."""
    t = datetime.strptime(cycle_id[:20], "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    return int(t.timestamp() * 1000)


def load_intents(cycles: Path) -> list[dict]:
    """Every intent the desk recorded, oldest first, from runs/cycles/index/*.jsonl."""
    by_id: dict[str, dict] = {}
    for f in sorted((cycles / "index").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("intent") and row.get("cycle_id"):
                by_id[row["cycle_id"]] = row["intent"]
    out = []
    for cid in sorted(by_id):
        it = by_id[cid]
        # the decision exists when the cycle finished; a minute after its start if that is not on record
        decided_ms = cycle_ms(cid) + 60_000
        try:
            fin = json.loads((cycles / cid / "cycle.json").read_text()).get("finished_at")
            decided_ms = int(datetime.fromisoformat(fin).timestamp() * 1000)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        out.append({
            "cycle": cid, "at_ms": decided_ms, "side": it["target"], "size": float(it["size"]),
            "stop": float(it["stop_price"]), "take": float(it["take_price"]),
            "round_trip_bps": float(it.get("priced_round_trip_bps") or 0), "setup": it.get("setup", ""),
            "conviction": it.get("conviction"), "reason": it.get("reason", ""),
        })
    return out


# ---- candles -------------------------------------------------------------------------------

def read_cache(path: Path) -> dict[int, tuple[float, float, float, float]]:
    bars: dict[int, tuple[float, float, float, float]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                ms, o, h, lo, c = json.loads(line)
                bars[int(ms)] = (float(o), float(h), float(lo), float(c))
            except (ValueError, TypeError):
                continue
    return bars


def parse_klines(payload: dict) -> list[tuple[int, float, float, float, float]]:
    """Bybit v5 kline rows, newest first, as [start_ms, open, high, low, close, volume, turnover]."""
    if payload.get("retCode") != 0:
        raise ValueError(f"bybit kline: {payload.get('retCode')} {payload.get('retMsg')}")
    rows = []
    for r in payload["result"]["list"]:
        rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
    return sorted(rows)


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float, float, float, float]]:
    """5-minute bars covering [start_ms, end_ms], 1000 at a time."""
    rows: list[tuple[int, float, float, float, float]] = []
    cursor = start_ms
    while cursor <= end_ms:
        q = urllib.parse.urlencode({"category": "linear", "symbol": symbol, "interval": "5",
                                    "start": cursor, "end": min(end_ms, cursor + 999 * BAR_MS), "limit": 1000})
        with urllib.request.urlopen(f"{KLINE_URL}?{q}", timeout=20) as r:
            page = parse_klines(json.loads(r.read()))
        if not page:
            break
        rows.extend(page)
        cursor = page[-1][0] + BAR_MS
        time.sleep(0.2)
    return rows


def update_cache(path: Path, symbol: str, start_ms: int, now_ms: int) -> tuple[dict, str | None]:
    """Fetch the bars the cache is missing; a failed fetch keeps what is cached and says why."""
    bars = read_cache(path)
    have_from = max(bars) + BAR_MS if bars else start_ms
    if bars and min(bars) > start_ms:
        have_from = start_ms  # the record now starts earlier than the cache: refetch from the start
    last_closed = (now_ms // BAR_MS) * BAR_MS - BAR_MS
    error = None
    if have_from <= last_closed:
        try:
            for ms, o, h, lo, c in fetch_klines(symbol, have_from, last_closed):
                if ms <= last_closed:
                    bars[ms] = (o, h, lo, c)
        except (OSError, ValueError, KeyError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        path.write_text("".join(json.dumps([ms, *bars[ms]]) + "\n" for ms in sorted(bars)))
    return bars, error


# ---- the account ---------------------------------------------------------------------------

def simulate(intents: list[dict], bars: dict[int, tuple[float, float, float, float]], hold_ms: int,
             start_equity: float) -> dict:
    """One position at a time; see the module docstring for the rules."""
    times = sorted(bars)
    trades: list[dict] = []
    skipped: list[dict] = []
    pos: dict | None = None

    def first_bar_at_or_after(ms: int) -> int | None:
        for t in times:
            if t >= ms:
                return t
        return None

    def advance(p: dict, until_ms: int) -> dict | None:
        """Walk the open position bar by bar before `until_ms`; return the closed trade or None."""
        for t in times:
            if t < p["next_ms"] or t >= until_ms:
                continue
            o, h, lo, c = bars[t]
            p["next_ms"] = t + BAR_MS
            p["mark"] = c
            if p["side"] == "short":
                hit_stop, hit_take = h >= p["stop"], lo <= p["take"]
            else:
                hit_stop, hit_take = lo <= p["stop"], h >= p["take"]
            if hit_stop:
                return close(p, p["stop"], t + BAR_MS, "stop")
            if hit_take:
                return close(p, p["take"], t + BAR_MS, "take")
            if t + BAR_MS >= p["deadline_ms"]:
                return close(p, c, t + BAR_MS, "time limit")
        return None

    def close(p: dict, price: float, at_ms: int, why: str) -> dict:
        sign = 1 if p["side"] == "long" else -1
        gross = sign * (price - p["entry"]) * p["size"]
        cost = p["round_trip_bps"] / 1e4 * p["entry"] * p["size"]
        return {**{k: p[k] for k in ("cycle", "side", "setup", "size", "entry", "entry_ms", "stop", "take",
                                     "round_trip_bps", "conviction", "reason")},
                "exit": price, "exit_ms": at_ms, "exit_reason": why,
                "gross_usd": round(gross, 2), "cost_usd": round(cost, 2), "net_usd": round(gross - cost, 2),
                "net_bps": round((gross - cost) / (p["entry"] * p["size"]) * 1e4, 1)}

    for it in intents:
        if pos is not None:
            done = advance(pos, it["at_ms"])
            if done:
                trades.append(done)
                pos = None
        if pos is not None:
            skipped.append({"cycle": it["cycle"], "side": it["side"], "why": f"a {pos['side']} is already open"})
            continue
        entry_ms = first_bar_at_or_after(it["at_ms"])
        if entry_ms is None:
            skipped.append({"cycle": it["cycle"], "side": it["side"], "why": "waiting for its first bar"})
            continue
        pos = {**it, "entry": bars[entry_ms][0], "entry_ms": entry_ms, "next_ms": entry_ms,
               "deadline_ms": entry_ms + hold_ms, "mark": bars[entry_ms][0]}
    open_pos = None
    if pos is not None:
        done = advance(pos, (times[-1] + BAR_MS) if times else 0)
        if done:
            trades.append(done)
        else:
            sign = 1 if pos["side"] == "long" else -1
            unreal = sign * (pos["mark"] - pos["entry"]) * pos["size"] - pos["round_trip_bps"] / 1e4 * pos["entry"] * pos["size"]
            open_pos = {k: pos[k] for k in ("cycle", "side", "setup", "size", "entry", "entry_ms", "stop", "take",
                                            "deadline_ms", "mark", "round_trip_bps", "conviction", "reason")}
            open_pos["unrealized_usd"] = round(unreal, 2)

    realized = round(sum(t["net_usd"] for t in trades), 2)
    unrealized = open_pos["unrealized_usd"] if open_pos else 0.0
    equity = round(start_equity + realized + unrealized, 2)
    wins = sum(1 for t in trades if t["net_usd"] > 0)
    curve, running = [], start_equity
    for t in trades:
        running += t["net_usd"]
        curve.append([t["exit_ms"], round(running, 2)])
    return {"start_equity": start_equity, "equity": equity, "realized_usd": realized, "unrealized_usd": unrealized,
            "return_pct": round((equity / start_equity - 1) * 100, 3), "closed": len(trades), "wins": wins,
            "losses": len(trades) - wins, "open": open_pos, "trades": trades, "skipped": skipped,
            "equity_curve": curve, "intents": len(intents),
            "last_bar_ms": times[-1] if times else None}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--desk", type=Path, default=Path.home() / "bitra" / "desk")
    p.add_argument("--out", type=Path, default=Path.home() / "bitra" / "paper")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--hold-hours", type=float, default=12.0)   # [exit].timeout_bars x the 1h bar
    p.add_argument("--equity", type=float, default=10_000.0)   # [run].equity
    args = p.parse_args()
    desk, out = args.desk.expanduser(), args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    intents = load_intents(desk / "runs" / "cycles")
    now_ms = int(time.time() * 1000)
    error = None
    bars: dict = {}
    if intents:
        start_ms = (intents[0]["at_ms"] // BAR_MS) * BAR_MS
        bars, error = update_cache(out / "candles.jsonl", args.symbol, start_ms, now_ms)
    state = simulate(intents, bars, int(args.hold_hours * 3_600_000), args.equity)
    state.update({"generated_ms": now_ms, "symbol": args.symbol, "hold_hours": args.hold_hours, "fetch_error": error})
    tmp = out / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(out / "state.json")
    print(f"paper: equity {state['equity']:.2f} ({state['return_pct']:+.2f}%), {state['closed']} closed, "
          f"open: {state['open']['side'] if state['open'] else 'none'}, {len(state['skipped'])} skipped"
          + (f"; fetch error: {error}" if error else ""))


if __name__ == "__main__":
    main()
