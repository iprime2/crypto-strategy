#!/usr/bin/env python3
"""Paper trader for the trend-following rule in scripts/trend_backtest.py, on Delta India mainnet data.

Once per UTC day, after the 00:00 close (or once per ISO week with --weekly, on the first run after the
Monday 00:00 UTC close): compute the backtest's long-only target weights from Delta daily closes, size them
off paper equity in whole contracts, and fill the difference as taker orders walked through Delta's live L2
book, so slippage is measured rather than assumed. Funding is charged at every 8-hourly exchange the
position was held through, at Delta's FUNDING:<sym> rate for that exchange, and each journal row records the
window, the exchanges and the rates it charged (funding_window, funding_exchanges, funding_rates). A "model"
equity holds the rule's unrounded weights between the same rebalances (mid to mid) with the backtest's modelled
costs, so the two can be compared. Public data only: no API keys, no orders. Safe to
run hourly; it rebalances at most once per day (or week) and exits non-zero when data is missing, so the
next run retries. A state directory remembers its settings and refuses a run with different ones.

    python3 scripts/trend_paper.py --capital 1000     # daily book, TV 0.40, state in artifacts/trend/paper/
    python3 scripts/trend_paper.py --weekly --target-vol 0.25 --band 0.10 --capital 1000 \
        --state-dir artifacts/trend/paper-weekly       # the weekly book from resource/07 (Monday 00:00 UTC close)
    python3 scripts/trend_paper.py --weekly --target-vol 0.25 --band 0.10 \
        --state-dir artifacts/trend/paper-weekly --orders-only   # print the order list for hand execution; writes nothing
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
DEFAULT_CONFIG = {"weekly": False, "target_vol": tb.TARGET_VOL, "band": 0.0}  # the daily book, as before
FUNDING_EVERY = 8 * 3600  # Delta India exchanges funding at 00:00, 08:00 and 16:00 UTC
FUNDING_TRIES = 5


def due(state: dict, today: dt.date, weekly: bool) -> bool:
    """Daily: one rebalance per UTC day. Weekly: one per ISO week (Monday to Sunday), so the normal run is
    Monday 00:05 UTC on the Sunday candle and a missed Monday is caught up later that week, never twice."""
    last = state.get("last_rebalance")
    if not last:
        return True
    last_day = dt.date.fromisoformat(last)
    if weekly:
        return last_day.isocalendar()[:2] != today.isocalendar()[:2]
    return last_day != today


def check_config(state: dict, config: dict) -> None:
    """A state directory belongs to one configuration; refuse to continue it with another one."""
    have = state.get("config") or DEFAULT_CONFIG
    diff = {k: (have.get(k), config[k]) for k in DEFAULT_CONFIG if have.get(k) != config[k]}
    if diff:
        raise SystemExit("state directory was created with different settings: "
                         + ", ".join(f"{k}={a!r} (run asks {b!r})" for k, (a, b) in diff.items())
                         + ". Use another --state-dir for a different configuration.")


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


def funding_exchanges(since: int, until: int) -> list[int]:
    """The funding exchanges a position held from `since` to `until` (unix seconds) takes part in: every 8-hour
    stamp after `since`, up to and including `until` (a run at 00:05 has been through the 00:00 exchange)."""
    return list(range((since // FUNDING_EVERY + 1) * FUNDING_EVERY, until + 1, FUNDING_EVERY))


def fetch_funding(since: int, until: int) -> dict:
    """The rate (% per 8 h) of each funding exchange in (since, until], per coin: the FUNDING:<sym> hourly candle
    stamped at the exchange, which is the rate Delta's ledger charges there (checked against the live ADA book's
    funding entries, 22-26 Oct 2026). Two quirks of the candles endpoint, measured 26 Oct 2026: a FUNDING series
    starts at the first 8-hour stamp at or after `start`, not at the first hour, and about one answer in ten is an
    empty list. Until 2026-10-26 this function summed hourly candles from `since` / 8, so a daily window charged the
    08:00 and 16:00 exchanges, 1/8 of the 00:00 one, and zero for a coin that answered empty. Now a coin missing a
    stamp is asked again, and if it is still missing the run fails and the next hourly run retries.
    Returns {"since", "until", "exchanges": [unix s], "rates": {coin: [% per 8 h, one per exchange]}}."""
    exchanges = funding_exchanges(since, until)
    rates = {}
    for c in tb.COINS:
        got = {}
        for attempt in range(FUNDING_TRIES):
            if attempt:
                time.sleep(2 * attempt)
            for s in range(since + 1, until + 1, 1999 * 3600):  # pages under the per-request candle cap
                for r in fetch(f"{tb.DELTA}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD"
                               f"&start={s}&end={min(s + 1999 * 3600, until)}"):
                    got[r["time"]] = float(r["close"])
            if all(e in got for e in exchanges):
                break
        missing = [e for e in exchanges if e not in got]
        if missing:
            when = ", ".join(f"{dt.datetime.fromtimestamp(e, dt.timezone.utc):%Y-%m-%d %H:%M}" for e in missing)
            raise RuntimeError(f"no FUNDING:{c}USD rate for the exchange at {when} UTC after {FUNDING_TRIES} tries")
        rates[c] = [got[e] for e in exchanges]
    return {"since": since, "until": until, "exchanges": exchanges, "rates": rates}


def funding_owed(detail: dict | None) -> dict[str, float]:
    """Funding per unit of notional paid by a long over the window: the exchanges' rates summed, % -> fraction."""
    return {c: sum(r) / 100 for c, r in detail["rates"].items()} if detail else {}


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


def init_state(capital: float, now: dt.datetime, config: dict | None = None) -> dict:
    return {"started": now.isoformat(), "capital": capital, "cash": capital, "positions": {},
            "model_equity": capital, "model_weights": {}, "model_mids": {}, "signal_day": None,
            "last_rebalance": None, "last_rebalance_ts": None, "config": dict(config or DEFAULT_CONFIG)}


def equity(state: dict, mids: dict, cvals: dict) -> float:
    return state["cash"] + sum(q * cvals[c] * mids[c] for c, q in state["positions"].items())


def plan_orders(pos: dict, w: dict, eq: float, mids: dict, cvals: dict, band: float = 0.0) -> tuple[list, list]:
    """Whole-contract targets and the trades that reach them. A trade smaller than `band` of its target (in
    contracts) is skipped as noise; closing a position is never skipped. Returns (plan, skipped)."""
    plan, skipped = [], []
    for c in tb.COINS:
        target = round(w.get(c, 0.0) * eq / (mids[c] * cvals[c]))
        held = pos.get(c, 0)
        qty = target - held
        if not qty:
            continue
        row = {"coin": c, "held": held, "target": target, "contracts": qty, "notional": abs(qty) * cvals[c] * mids[c]}
        if target and abs(qty) < band * abs(target):
            skipped.append(row)
        else:
            plan.append(row)
    return plan, skipped


def mark(state: dict, closes: dict, books: dict, funding: dict, cvals: dict, now: dt.datetime, target_vol: float) -> dict:
    """What a rebalance at `now` sees, without changing anything: the signal day (yesterday's close), mids,
    funding owed since the last rebalance, equity after that funding, and the rule's weights."""
    signal_day = now.date() - dt.timedelta(1)
    missing = [c for c in tb.COINS if signal_day not in closes.get(c, {})]
    if missing:
        raise RuntimeError(f"no {signal_day} close yet for {', '.join(missing)}")
    mids = {c: (books[c][0][0][0] + books[c][1][0][0]) / 2 for c in tb.COINS}
    pos = state["positions"]
    # Funding over the holding period (positions were constant since the last rebalance).
    fund_paid = sum(q * cvals[c] * mids[c] * funding.get(c, 0.0) for c, q in pos.items())
    eq = equity(state, mids, cvals) - fund_paid
    w = tb.target_weights(closes, signal_day, tb.LOOKS, tb.VOL_WIN, target_vol, long_only=True)
    return {"signal_day": signal_day, "mids": mids, "funding": fund_paid, "equity": eq, "weights": w}


def order_list(state: dict, closes: dict, books: dict, funding: dict, cvals: dict, now: dt.datetime, *,
               target_vol: float = tb.TARGET_VOL, band: float = 0.0) -> dict:
    """The orders a rebalance at `now` would send, from the same sizing as step(). Read-only."""
    m = mark(state, closes, books, funding, cvals, now, target_vol)
    plan, skipped = plan_orders(state["positions"], m["weights"], m["equity"], m["mids"], cvals, band)
    return {**m, "plan": plan, "skipped": skipped}


def step(state: dict, closes: dict, books: dict, funding: dict, cvals: dict, now: dt.datetime, *,
         target_vol: float = tb.TARGET_VOL, band: float = 0.0, funding_detail: dict | None = None) -> dict:
    """One rebalance on fetched data (no I/O). Mutates `state`, returns the journal record. `funding` is
    funding_owed(funding_detail); the detail (window, exchanges, rates) is written to the record for audit."""
    m = mark(state, closes, books, funding, cvals, now, target_vol)
    signal_day, mids, fund_paid, eq_before, w = m["signal_day"], m["mids"], m["funding"], m["equity"], m["weights"]
    pos = state["positions"]
    state["cash"] -= fund_paid

    plan, skipped = plan_orders(pos, w, eq_before, mids, cvals, band)
    orders, fees = [], 0.0
    for row in plan:
        c, target, qty = row["coin"], row["target"], row["contracts"]
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
            "funding_window": [funding_detail["since"], funding_detail["until"]] if funding_detail else None,
            "funding_exchanges": funding_detail["exchanges"] if funding_detail else [],
            "funding_rates": funding_detail["rates"] if funding_detail else {},
            "fees": fees, "orders": orders, "skipped": skipped, "weights": w, "positions": dict(pos), "mids": mids,
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

def print_order_list(listed: dict, config: dict, now: dt.datetime) -> None:
    sd = listed["signal_day"]
    print(f"{now:%Y-%m-%d %H:%M} UTC  signal {sd} ({sd:%A} close)  equity ${listed['equity']:,.2f} after "
          f"${listed['funding']:.2f} funding  target vol {config['target_vol']:.2f}  band {config['band']:.0%}"
          f"{'  weekly' if config['weekly'] else ''}")
    print(f"{'coin':<5} {'held':>6} {'target':>7} {'trade':>6} {'notional':>10} {'mid':>12}")
    for r in listed["plan"]:
        print(f"{r['coin']:<5} {r['held']:>6} {r['target']:>7} {r['contracts']:>+6} {r['notional']:>10,.2f} {listed['mids'][r['coin']]:>12,.4f}")
    if not listed["plan"]:
        print("(nothing to trade)")
    for r in listed["skipped"]:
        print(f"skipped inside the band: {r['coin']} {r['contracts']:+d} of {r['target']} contracts")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=1000.0, help="starting paper equity in USD (first run only)")
    ap.add_argument("--state-dir", type=Path, default=STATE_DIR)
    ap.add_argument("--weekly", action="store_true", help="rebalance once per ISO week, on the first run after the Monday 00:00 UTC close")
    ap.add_argument("--target-vol", type=float, default=tb.TARGET_VOL, help="annualized target vol for the whole book (the backtest's TARGET_VOL)")
    ap.add_argument("--band", type=float, default=0.0, help="skip a trade smaller than this share of its target, e.g. 0.10 (closes always trade)")
    ap.add_argument("--orders-only", action="store_true", help="print the order list a rebalance now would send; change nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    config = {"weekly": args.weekly, "target_vol": args.target_vol, "band": args.band}
    path = args.state_dir / "state.json"
    now = dt.datetime.now(dt.timezone.utc)
    state = json.loads(path.read_text()) if path.exists() else init_state(args.capital, now, config)
    check_config(state, config)
    state.setdefault("config", dict(config))  # a book written before this field existed is the daily default
    if not args.orders_only and not due(state, now.date(), args.weekly):
        print(f"already rebalanced for {'the week of ' if args.weekly else ''}{state['last_rebalance']} UTC")
        return
    cvals = tb.contract_values()
    closes = fetch_closes(now.date())
    books = {c: fetch_book(c) for c in tb.COINS}
    since = state["last_rebalance_ts"]
    detail = fetch_funding(since, int(now.timestamp())) if since else None
    funding = funding_owed(detail)
    if args.orders_only:
        print_order_list(order_list(state, closes, books, funding, cvals, now, target_vol=args.target_vol, band=args.band), config, now)
        return
    rec = step(state, closes, books, funding, cvals, now, target_vol=args.target_vol, band=args.band, funding_detail=detail)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    with open(args.state_dir / "journal.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, path)
    held = ", ".join(f"{c} {q:+d}" for c, q in sorted(rec["positions"].items())) or "flat"
    print(f"{now:%Y-%m-%d %H:%M} UTC  signal {rec['signal_day']}  equity ${rec['equity']:,.2f}  "
          f"model ${rec['model_equity']:,.2f}  orders {len(rec['orders'])}  skipped {len(rec['skipped'])}  "
          f"fees ${rec['fees']:.2f}  funding ${rec['funding']:.2f}  gross {rec['gross']:.2f}x  holding {held}")


if __name__ == "__main__":
    main()
