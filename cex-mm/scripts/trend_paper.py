#!/usr/bin/env python3
"""Paper trader for the trend-following rule in scripts/trend_backtest.py, on Delta India mainnet data.

Once per UTC day, after the 00:00 close: compute the backtest's long-only target weights from Delta daily
closes, size them off paper equity in whole contracts, and fill the difference as taker orders walked
through Delta's live L2 book, so slippage is measured rather than assumed. Funding is charged from
Delta's FUNDING:<sym> rates. A "model" equity holds the rule's unrounded weights between the same
rebalances (mid to mid) with the backtest's modelled costs, so the two can be compared. Public data only: no API keys, no orders. Safe to run hourly; it rebalances at most
once per UTC day and exits non-zero when data is missing, so the next run retries.

    python3 scripts/trend_paper.py --capital 1000     # state in artifacts/trend/paper/
    python3 scripts/trend_paper.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path

import trend_backtest as tb

STATE_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "trend" / "paper"
MODEL_COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4  # the backtest's cost per unit of turnover


# ---------------------------------------------------------------- Delta public data

def fetch(url: str):
    for attempt in range(3):
        try:
            return json.loads(tb.get(url))["result"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def fetch_closes(today: dt.date) -> dict[str, dict[dt.date, float]]:
    """Completed daily closes (UTC) for the last 160 days; today's partial candle is dropped."""
    t1 = int(dt.datetime.combine(today, dt.time(), dt.timezone.utc).timestamp())
    out = {}
    for c in tb.COINS:
        bars = fetch(f"{tb.DELTA}/v2/history/candles?resolution=1d&symbol={c}USD&start={t1 - 160 * 86400}&end={t1}")
        out[c] = {dt.datetime.fromtimestamp(b["time"], dt.timezone.utc).date(): float(b["close"]) for b in bars if b["time"] < t1}
    return out


def fetch_book(coin: str) -> tuple[list, list]:
    r = fetch(f"{tb.DELTA}/v2/l2orderbook/{coin}USD?depth=50")
    side = lambda levels: [(float(x["price"]), float(x["size"])) for x in levels]  # noqa: E731
    return side(r["buy"]), side(r["sell"])


def fetch_funding(since: int, until: int) -> dict[str, float]:
    """Funding per unit of notional paid by a long over [since, until): hourly rates in % per 8 h."""
    out = {}
    for c in tb.COINS:
        rates = []
        for s in range(since, until, 1999 * 3600):
            rates += fetch(f"{tb.DELTA}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={s}&end={min(s + 1999 * 3600, until)}")
        out[c] = sum(float(r["close"]) for r in rates if since <= r["time"] < until) / 100 / 8
    return out


# ---------------------------------------------------------------- paper book

def walk_book(levels: list[tuple[float, float]], qty: float) -> float:
    """Average price for taking `qty` contracts from `levels` [(price, size)], best level first."""
    left, cost = qty, 0.0
    for px, size in levels:
        take = min(left, size)
        cost += take * px
        left -= take
        if left <= 0:
            return cost / qty
    raise ValueError(f"book too thin for {qty} contracts")


def init_state(capital: float, now: dt.datetime) -> dict:
    return {"started": now.isoformat(), "capital": capital, "cash": capital, "positions": {},
            "model_equity": capital, "model_weights": {}, "model_mids": {}, "signal_day": None,
            "last_rebalance": None, "last_rebalance_ts": None}


def equity(state: dict, mids: dict, cvals: dict) -> float:
    return state["cash"] + sum(q * cvals[c] * mids[c] for c, q in state["positions"].items())


def step(state: dict, closes: dict, books: dict, funding: dict, cvals: dict, now: dt.datetime) -> dict:
    """One daily rebalance on fetched data (no I/O). Mutates `state`, returns the journal record."""
    signal_day = now.date() - dt.timedelta(1)
    missing = [c for c in tb.COINS if signal_day not in closes.get(c, {})]
    if missing:
        raise RuntimeError(f"no {signal_day} close yet for {', '.join(missing)}")
    mids = {c: (books[c][0][0][0] + books[c][1][0][0]) / 2 for c in tb.COINS}
    pos = state["positions"]

    # Funding over the holding period (positions were constant since the last rebalance).
    fund_paid = sum(q * cvals[c] * mids[c] * funding.get(c, 0.0) for c, q in pos.items())
    state["cash"] -= fund_paid
    eq_before = equity(state, mids, cvals)

    w = tb.target_weights(closes, signal_day, tb.LOOKS, tb.VOL_WIN, tb.TARGET_VOL, long_only=True)
    orders, fees = [], 0.0
    for c in tb.COINS:
        target = round(w.get(c, 0.0) * eq_before / (mids[c] * cvals[c]))
        qty = target - pos.get(c, 0)
        if not qty:
            continue
        bids, asks = books[c]
        px = walk_book(asks if qty > 0 else bids, abs(qty))
        notional = abs(qty) * cvals[c] * px
        fee = notional * tb.TAKER_BPS / 1e4
        state["cash"] -= qty * cvals[c] * px + fee
        fees += fee
        if target:
            pos[c] = target
        else:
            pos.pop(c, None)
        orders.append({"coin": c, "contracts": qty, "mid": mids[c], "price": px, "notional": notional, "fee": fee,
                       "slippage_bps": (px / mids[c] - 1) * 1e4 * (1 if qty > 0 else -1)})
    eq_after = equity(state, mids, cvals)

    # Model: the rule's unrounded weights held over the same window as the paper book (rebalance mid to
    # rebalance mid), with the backtest's modelled costs. Close-to-close would charge a mid-day start
    # for moves that happened before the paper book existed.
    prev_w, prev_mids = state["model_weights"], state.get("model_mids") or {}
    r = sum(x * (mids[c] / prev_mids[c] - 1) for c, x in prev_w.items() if c in prev_mids)
    r -= sum(x * funding.get(c, 0.0) for c, x in prev_w.items())
    r -= sum(abs(w.get(c, 0.0) - prev_w.get(c, 0.0)) for c in tb.COINS) * MODEL_COST
    state["model_equity"] *= 1 + r

    state.update(model_weights=w, model_mids=mids, signal_day=signal_day.isoformat(),
                 last_rebalance=now.date().isoformat(), last_rebalance_ts=int(now.timestamp()))
    return {"time": now.isoformat(), "signal_day": signal_day.isoformat(), "equity_before": eq_before,
            "equity": eq_after, "model_equity": state["model_equity"], "cash": state["cash"], "funding": fund_paid,
            "fees": fees, "orders": orders, "weights": w, "positions": dict(pos), "mids": mids,
            "values": {c: q * cvals[c] * mids[c] for c, q in pos.items()},
            "gross": sum(abs(q) * cvals[c] * mids[c] for c, q in pos.items()) / eq_after}


# ---------------------------------------------------------------- self-check

def selftest() -> None:
    assert walk_book([(100.0, 2), (101.0, 3)], 4) == 100.5
    try:
        walk_book([(100.0, 1)], 2)
        raise AssertionError("thin book must raise")
    except ValueError:
        pass
    now = dt.datetime(2026, 7, 1, 0, 5, tzinfo=dt.timezone.utc)
    days = [now.date() - dt.timedelta(k) for k in range(200, 0, -1)]
    closes = {c: {d: 100 * 1.01 ** i * (1 + 0.02 * (-1) ** i) for i, d in enumerate(days)} for c in tb.COINS}
    last = closes["BTC"][days[-1]]
    books = {c: ([(last * 0.9999, 1e9)], [(last * 1.0001, 1e9)]) for c in tb.COINS}
    cvals = {c: 0.01 for c in tb.COINS}
    s = init_state(1000.0, now)
    rec = step(s, closes, books, {}, cvals, now)
    assert set(s["positions"]) == set(tb.COINS) and all(q > 0 for q in s["positions"].values()), s["positions"]
    assert 0 < 1000 - rec["equity"] < 1, rec["equity"]  # only fees and half-spread lost
    assert s["last_rebalance"] == "2026-07-01" and rec["signal_day"] == "2026-06-30"
    # Next day: prices up 2%, positions gain; nothing traded at the same target means no fees.
    nxt = now + dt.timedelta(1)
    for c in tb.COINS:
        closes[c][nxt.date() - dt.timedelta(1)] = last * 1.02
    books = {c: ([(last * 1.02 * 0.9999, 1e9)], [(last * 1.02 * 1.0001, 1e9)]) for c in tb.COINS}
    rec2 = step(s, closes, books, {c: 0.0003 for c in tb.COINS}, cvals, nxt)
    assert rec2["equity_before"] > rec["equity"] and rec2["funding"] > 0, rec2
    assert s["model_equity"] > 1000 * (1 - 0.01), s["model_equity"]
    # A big close-to-close drop with flat mids between rebalances (e.g. a mid-day start) must not move the
    # model: it only holds positions between rebalance mids, like the paper book.
    m0, nxt2 = s["model_equity"], nxt + dt.timedelta(1)
    for c in tb.COINS:
        closes[c][nxt2.date() - dt.timedelta(1)] = last * 1.02 * 0.9
    rec3 = step(s, closes, books, {}, cvals, nxt2)
    assert abs(s["model_equity"] / m0 - 1) < 0.002, (m0, s["model_equity"])
    assert abs(rec3["model_equity"] - rec3["equity"]) / rec3["equity"] < 0.01, rec3
    print("selftest ok")


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=1000.0, help="starting paper equity in USD (first run only)")
    ap.add_argument("--state-dir", type=Path, default=STATE_DIR)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    path = args.state_dir / "state.json"
    now = dt.datetime.now(dt.timezone.utc)
    state = json.loads(path.read_text()) if path.exists() else init_state(args.capital, now)
    if state["last_rebalance"] == now.date().isoformat():
        print(f"already rebalanced for {state['last_rebalance']} UTC")
        return
    cvals = tb.contract_values()
    closes = fetch_closes(now.date())
    books = {c: fetch_book(c) for c in tb.COINS}
    since = state["last_rebalance_ts"]
    funding = fetch_funding(since, int(now.timestamp())) if since else {}
    rec = step(state, closes, books, funding, cvals, now)
    with open(args.state_dir / "journal.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, path)
    held = ", ".join(f"{c} {q:+d}" for c, q in sorted(rec["positions"].items())) or "flat"
    print(f"{now:%Y-%m-%d %H:%M} UTC  signal {rec['signal_day']}  equity ${rec['equity']:,.2f}  "
          f"model ${rec['model_equity']:,.2f}  orders {len(rec['orders'])}  fees ${rec['fees']:.2f}  "
          f"funding ${rec['funding']:.2f}  gross {rec['gross']:.2f}x  holding {held}")


if __name__ == "__main__":
    main()
