#!/usr/bin/env python3
"""Compare the real-money live run (scripts/live.sh) with the shadow simulator over the same window.

Real fills come from Delta's GET /v2/fills (read-only, the mainnet key in quote-bot/.env): the venue is the
source of truth. Both sides are priced against the same reference, the Delta L1 mid that the shadow dry-run
logs in MM_METRICS on the VM's local clock. Fill times are exchange times; they are moved onto the local clock
by the median recorder offset (local receive time minus exchange time) of the shadow's trade tape.

Rows (net60 = capture + 60 s markout - fee, bps per fill, notional-weighted, as in shadow_fill_sim.py):
  real (Delta fills)  the live bot's fills, fees as charged (taker fills, if any, are counted in maker%)
  sim shadow <N>ms    shadow_fill_sim on the shadow dry-run's quotes and recorded tape, same window
  sim live <N>ms      the same simulator on the live bot's own logged quotes: real vs this row is the fill
                      model (queue, latency); this row vs sim shadow is the quotes (the live bot holds inventory)

    python3 scripts/live_vs_shadow.py                    # artifacts/live/current vs the shadow runs it overlaps
    python3 scripts/live_vs_shadow.py --latencies 20,300 --json
    python3 scripts/live_vs_shadow.py --offline          # reuse <live run>/fills.json, no API call
    python3 scripts/live_vs_shadow.py venue              # equity, position and open orders (read-only)

Never prints the key or secret. Places no orders.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import glob
import hashlib
import hmac
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shadow_fill_sim as sim  # noqa: E402

CEX_MM = Path(__file__).resolve().parent.parent
BASE = os.environ.get("DELTA_REST_BASE", "https://api.india.delta.exchange")
RUN_NAME = re.compile(r"^\d{8}T\d{6}Z$")
MAX_GAP_MS = 1500.0  # same as shadow_fill_sim's default: a quote older than this is gone
COMPACT_MS = 1000.0  # with --compact, at least one sample per second is kept
STOP_FILLS = 300  # live stop rule (2026-10-05 memo): net60 < 0 after this many real fills


# ---------------------------------------------------------------- keys and the venue

def env_value(path: Path, key: str) -> str | None:
    """Value of `key` in a .env file, parsed like the OEMS's load_env_file: trimmed, surrounding double quotes
    stripped, last assignment wins, empty counts as missing. Never logged."""
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    value = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            value = v.strip().strip('"')
    return value or None


class Delta:
    """Signed read-only GETs on Delta India mainnet, signed like mm-delta (method + timestamp + path + query)."""

    def __init__(self, env_file: Path):
        self.key = env_value(env_file, "DELTA_MAINNET_API_KEY")
        self.secret = env_value(env_file, "DELTA_MAINNET_API_SECRET")
        if not self.key or not self.secret:
            raise SystemExit(f"DELTA_MAINNET_API_KEY / DELTA_MAINNET_API_SECRET not set in {env_file}")

    def get(self, path: str, query: str = "") -> dict:
        qs = f"?{query}" if query else ""
        ts = str(int(time.time()))
        sig = hmac.new(self.secret.encode(), f"GET{ts}{path}{qs}".encode(), hashlib.sha256).hexdigest()
        req = urllib.request.Request(BASE + path + qs, headers={
            "api-key": self.key, "timestamp": ts, "signature": sig,
            "User-Agent": "cex-mm-live-vs-shadow/0.1", "Accept": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                try:
                    return json.load(e)
                except ValueError:
                    return {"success": False, "error": {"code": f"HTTP {e.code}"}}
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == 2:
                    return {"success": False, "error": {"code": f"network: {e}"}}
                time.sleep(2 * (attempt + 1))
        return {"success": False, "error": {"code": "unreachable"}}


def error_code(body: dict) -> str:
    e = body.get("error") or {}
    return str(e.get("code") or e) if e else "no error body"


def product(symbol: str) -> tuple[int, float, float]:
    """(product id, tick size, contract value) from the public product endpoint."""
    req = urllib.request.Request(f"{BASE}/v2/products/{symbol}", headers={"User-Agent": "cex-mm-live-vs-shadow/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.load(r)["result"]
    return int(res["id"]), float(res["tick_size"]), float(res["contract_value"])


# ---------------------------------------------------------------- real fills

@dataclass
class RealFill:
    id: str
    ts: float  # exchange time, ms
    side: int  # +1 bought, -1 sold
    contracts: float
    price: float
    fee: float  # USD as charged (GST included), positive = paid
    maker: bool


def parse_iso_ms(s: str) -> float:
    """RFC 3339 time ('...Z', any fraction length, or an offset) -> Unix ms."""
    s = s.strip().replace("Z", "+00:00")
    m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)$", s)
    if not m:
        raise ValueError(s)
    head, frac, tz = m.groups()
    frac = ((frac or "") + "000000")[:6]
    return dt.datetime.fromisoformat(f"{head}.{frac}{tz or '+00:00'}").timestamp() * 1000.0


def parse_fill(row: dict, cv: float) -> RealFill | None:
    """One /v2/fills row (strings or numbers) -> RealFill, or None if it is not a usable trade."""
    try:
        side = {"buy": 1, "sell": -1}[row["side"]]
        return RealFill(
            id=str(row["id"]),
            ts=parse_iso_ms(row["created_at"]),
            side=side,
            contracts=float(row["size"]),
            price=float(row["price"]),
            fee=float(row.get("commission") or 0.0),
            maker=row.get("role") != "taker",
        )
    except (KeyError, TypeError, ValueError):
        return None


def fetch_fills(get, product_id: int, since_ms: float, max_pages: int = 200) -> list[dict]:
    """Fills for one product, newest first, until a page reaches back past `since_ms`."""
    rows: list[dict] = []
    after = None
    for _ in range(max_pages):
        query = f"product_ids={product_id}&page_size=100" + (f"&after={urllib.parse.quote(after, safe='')}" if after else "")
        body = get("/v2/fills", query)
        if body.get("success") is not True:
            raise RuntimeError(f"Delta /v2/fills failed: {error_code(body)}")
        page = body.get("result") or []
        rows.extend(page)
        after = (body.get("meta") or {}).get("after")
        oldest = min((parse_iso_ms(r["created_at"]) for r in page if r.get("created_at")), default=None)
        if not after or not page or (oldest is not None and oldest < since_ms):
            break
        time.sleep(0.2)
    return rows


# ---------------------------------------------------------------- logs

def changed(a: sim.Sample, b: sim.Sample) -> bool:
    return (a.bid != b.bid or a.ask != b.ask or a.place_bid != b.place_bid or a.place_ask != b.place_ask
            or a.book_bid != b.book_bid or a.book_ask != b.book_ask or a.regime != b.regime
            or (b.fair and abs(a.fair - b.fair) / b.fair * 1e4 >= 0.5))


def load_samples(paths: list[str], symbol: str, t0: float, t1: float, heartbeat_ms: float = 0.0) -> list[sim.Sample]:
    """MM_METRICS samples of one symbol in [t0, t1], streamed. With heartbeat_ms > 0 they are compacted: a sample
    is kept when the quote, the book, the regime or fair (by 0.5 bps) changed, or heartbeat_ms passed. That keeps
    the quotes and the mid series but delays the simulated re-quote after a fill to the next kept sample, which
    cost about 1% of simulated fills (net60 within 0.02 bps) on the 6 Oct run. Full resolution takes about
    76 MB per day of samples."""
    needle = f'"{symbol}"'
    out: list[sim.Sample] = []
    for path in paths:
        for line in sim.iter_lines(path):
            if needle not in line or "MM_METRICS" not in line:
                continue
            parsed = sim.parse_metrics_line(line)
            if not parsed or parsed[0] != symbol:
                continue
            s = parsed[1]
            if s.ts < t0 or s.ts > t1:
                continue
            if heartbeat_ms and out and s.ts >= out[-1].ts and not changed(s, out[-1]) \
                    and s.ts - out[-1].ts < heartbeat_ms:
                continue
            out.append(s)
    out.sort(key=lambda s: s.ts)
    return out


def metrics_json(line: str) -> dict | None:
    try:
        return json.loads(line[line.index("{"): line.rindex("}") + 1])
    except ValueError:
        return None


def live_span(paths: list[str], symbol: str) -> tuple[float, float, float] | None:
    """(first ts, last ts, inventory at the first sample) of a symbol's MM_METRICS lines, reading only the head
    of the first log and the tail of the last one."""
    needle = f'"{symbol}"'
    first = last = None
    for path in paths:
        for line in sim.iter_lines(path):
            if needle in line and "MM_METRICS" in line and (m := metrics_json(line)) and m.get("ts_ms"):
                first = m
                break
        if first:
            break
    for path in reversed(paths):
        with sim.open_text(path) as f:
            if not path.endswith(".gz"):
                f.seek(max(0, os.path.getsize(path) - 4_000_000))
            tail = f.read().splitlines()
        for line in reversed(tail):
            if needle in line and "MM_METRICS" in line and (m := metrics_json(line)) and m.get("ts_ms"):
                last = m
                break
        if last:
            break
    if not first or not last:
        return None
    return float(first["ts_ms"]), float(last["ts_ms"]), float(first.get("inventory") or 0.0)


def load_trades(paths: list[str], delta_sym: str, t0: float, t1: float) -> list[sim.Trade]:
    out = []
    for path in paths:
        for line in sim.iter_lines(path):
            parsed = sim.parse_trade_record(line)
            if parsed and parsed[0] == delta_sym and t0 <= parsed[1].ts <= t1:
                out.append(parsed[1])
    out.sort(key=lambda t: t.ts)
    return out


def clock_offset_ms(paths: list[str], delta_sym: str, t0: float, t1: float) -> float:
    """Median (local receive - exchange) time of the recorded trades: adds to a fill's exchange time."""
    offsets = []
    for path in paths:
        for line in sim.iter_lines(path):
            parsed = sim.parse_trade_record(line)
            if parsed and parsed[0] == delta_sym and t0 <= parsed[1].ts <= t1 and parsed[2] > 0:
                offsets.append(parsed[1].ts - parsed[2])
    return float(statistics.median(offsets)) if offsets else 0.0


def read_config(run_dir: Path) -> dict[str, str]:
    out = {}
    try:
        for line in (run_dir / "config.txt").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def shadow_runs_for(shadow_root: Path, t0: float, t1: float) -> list[Path]:
    """Shadow run directories whose lifetime [own start, next run's start) overlaps [t0, t1]."""
    runs = sorted(p for p in shadow_root.iterdir() if p.is_dir() and not p.is_symlink() and RUN_NAME.match(p.name))
    starts = [dt.datetime.strptime(p.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000 for p in runs]
    picked = []
    for i, p in enumerate(runs):
        end = starts[i + 1] if i + 1 < len(runs) else float("inf")
        if starts[i] <= t1 and end > t0:
            picked.append(p)
    return picked


# ---------------------------------------------------------------- metrics

def to_sim_fills(fills: list[RealFill], offset_ms: float, mids: sim.MidSeries, cv: float) -> list[sim.Fill]:
    """Real fills as simulator fills on the local clock, each with the reference mid at fill time."""
    out = []
    for f in sorted(fills, key=lambda f: f.ts):
        ts = f.ts + offset_ms
        mid = mids.at(ts)
        if mid is None:
            continue
        notional = f.contracts * cv * f.price
        out.append(sim.Fill(ts=ts, side=f.side, price=f.price, qty=f.contracts, notional=notional, fee=f.fee,
                            mid=mid, fair=mid))
    return out


def quote_time(samples: list[sim.Sample]) -> tuple[float, float]:
    """(ms with both sides quoted, ms with at least one side inside the touch) from a bot's own samples."""
    quoted = inside = 0.0
    for a, b in zip(samples, samples[1:]):
        if a.place_bid and a.place_ask:
            gap = min(b.ts - a.ts, MAX_GAP_MS)
            quoted += gap
            if a.bid > a.book_bid or a.ask < a.book_ask:
                inside += gap
    return quoted, inside


def quote_agreement(live: list[sim.Sample], shadow: list[sim.Sample], tick: float) -> tuple[int, int]:
    """(live samples whose quote equals the shadow's nearest sample within 1 s, live samples compared)."""
    ts = [s.ts for s in shadow]
    same = total = 0
    for s in live:
        i = bisect.bisect_left(ts, s.ts)
        near = [shadow[j] for j in (i - 1, i) if 0 <= j < len(shadow) and abs(shadow[j].ts - s.ts) <= 1000]
        if not near:
            continue
        o = min(near, key=lambda x: abs(x.ts - s.ts))
        total += 1
        if (o.place_bid, o.place_ask) == (s.place_bid, s.place_ask) and abs(o.bid - s.bid) < tick / 2 \
                and abs(o.ask - s.ask) < tick / 2:
            same += 1
    return same, total


def sizing(cfg: dict[str, str], symbol: str, cv: float) -> tuple[int, int]:
    """(order size in contracts, inventory cap in orders) from the live run's profile lines."""
    qty = float(cfg.get(f"MM_ORDER_QTY_{symbol}") or cfg.get("MM_ORDER_QTY") or 0)
    cap = float(cfg.get(f"MM_MAX_INVENTORY_{symbol}") or cfg.get("MM_MAX_INVENTORY") or 0)
    if qty <= 0 or cap <= 0:
        raise SystemExit(f"the live run's config.txt has no MM_ORDER_QTY_{symbol} / MM_MAX_INVENTORY_{symbol}")
    contracts = max(1, round(qty / cv))
    return contracts, max(1, round(cap / qty))


def row(s: dict, extra: dict | None = None) -> dict:
    keep = ["fills", "scored", "days", "fills_per_day", "usd_per_day", "uptime", "inside", "capture", "fee", "net60",
            "net300", "pnl_total", "pnl_spread", "pnl_inventory", "pnl_fees", "final_inv"]
    out = {k: s[k] for k in keep}
    out.update({f"mo{h}": s["mo"][h] for h in sim.HORIZONS})
    if extra:
        out.update(extra)
    return out


def compare(live_dir: Path, shadow_dirs: list[Path], fill_rows: list[dict], latencies: list[float], tick: float,
            cv: float, symbol: str | None = None, since_ms: float = 0.0, heartbeat_ms: float = 0.0) -> dict:
    """Real fills and simulated fills over the live run's window (from since_ms on, if later). No network: fills
    and the product's tick and contract value are passed in."""
    cfg = read_config(live_dir)
    symbol = symbol or (cfg.get("MM_SYMBOLS") or cfg.get("symbols") or "ADAUSDT").split(",")[0]
    dsym = sim.delta_symbol(symbol)
    live_logs = sorted(glob.glob(str(live_dir / "bot*.log*")))
    live = load_samples(live_logs, symbol, since_ms, float("inf"), heartbeat_ms)
    if len(live) < 2:
        raise SystemExit(f"no MM_METRICS samples for {symbol} in {live_dir}")
    t0, t1 = live[0].ts, live[-1].ts
    metric_paths = [p for d in shadow_dirs for p in sorted(glob.glob(str(d / "dry-run*.log*")))]
    trade_paths = [p for d in shadow_dirs for p in sorted(glob.glob(str(d / "delta_mainnet_public_*.jsonl")))]
    # Mids reach 300 s past the window so late fills still get their markouts.
    shadow_all = load_samples(metric_paths, symbol, t0 - 5000, t1 + 310_000, heartbeat_ms)
    shadow = [s for s in shadow_all if t0 <= s.ts <= t1]
    if len(shadow) < 2:
        raise SystemExit(f"the shadow runs {[d.name for d in shadow_dirs]} have no {symbol} samples in the live window")
    t0, t1 = max(t0, shadow[0].ts), min(t1, shadow[-1].ts)
    live = [s for s in live if t0 <= s.ts <= t1]
    shadow = [s for s in shadow if t0 <= s.ts <= t1]
    mids = sim.MidSeries(shadow_all)
    tape = load_trades(trade_paths, dsym, t0, t1)
    offset = clock_offset_ms(trade_paths, dsym, t0, t1)
    span = t1 - t0

    real = [f for f in (parse_fill(r, cv) for r in fill_rows if r.get("product_symbol") == dsym) if f]
    real = [f for f in real if t0 <= f.ts + offset <= t1]
    sf = to_sim_fills(real, offset, mids, cv)
    inv = sum(f.side * f.qty for f in sf)
    quoted, inside = quote_time(live)
    res = sim.SimResult(fills=sf, quoted_ms=quoted, inside_ms=inside, span_ms=span, final_inv=inv)
    maker_notional = sum(f.contracts * cv * f.price for f in real if f.maker)
    all_notional = sum(f.contracts * cv * f.price for f in real)
    rows = {"real": row(sim.summarize(res, mids, cv), {
        "maker_pct": 100.0 * maker_notional / all_notional if all_notional else 100.0,
        "taker_fills": sum(1 for f in real if not f.maker)})}

    contracts, inv_orders = sizing(cfg, symbol, cv)
    for label, quotes in (("shadow", shadow), ("live", live)):
        ref_px = quotes[len(quotes) // 2].fair
        for lat in latencies:
            c = sim.SimConfig(
                latency_ms=lat, half_spread_bps=None, rule="strict", quote_usd=contracts * cv * ref_px,
                max_inv_orders=inv_orders, fee_bps=float(cfg.get("MM_MAKER_FEE_BPS") or 2.12),
                requote_tol_bps=float(cfg.get("MM_REQUOTE_TOL_BPS") or 3.0), max_gap_ms=MAX_GAP_MS, loop_ms=400.0)
            rows[f"sim {label} {lat:g}ms"] = row(sim.summarize(sim.simulate(quotes, tape, tick, cv, c), mids, cv),
                                                 {"maker_pct": 100.0, "taker_fills": 0})

    same, total = quote_agreement(live, shadow, tick)
    span_info = live_span(live_logs, symbol)
    return {
        "symbol": symbol, "live_run": live_dir.name, "shadow_runs": [d.name for d in shadow_dirs],
        "window": {"t0": t0, "t1": t1, "hours": span / 3.6e6, "clock_offset_ms": offset, "tape_trades": len(tape)},
        "sizing": {"order_contracts": contracts, "max_inv_orders": inv_orders},
        "quotes": {"same": same, "compared": total, "pct": 100.0 * same / total if total else None},
        "start_inventory": span_info[2] if span_info else None,
        "rows": rows,
    }


def stop_rule(real: dict) -> str:
    if real["scored"] < STOP_FILLS:
        return f"CONTINUE ({real['scored']}/{STOP_FILLS} scored real fills)"
    return "STOP: real net60 < 0 after 300 fills" if real["net60"] < 0 else "OK: real net60 >= 0"


def format_table(out: dict) -> str:
    w = out["window"]
    iso = lambda ms: dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")  # noqa: E731
    lines = [
        f"=== {out['symbol']} live run {out['live_run']} vs shadow {', '.join(out['shadow_runs'])}",
        f"window {iso(w['t0'])} -> {iso(w['t1'])} ({w['hours']:.2f} h), tape {w['tape_trades']} trades, "
        f"fill clock shift {w['clock_offset_ms']:+.0f} ms; quotes {out['sizing']['order_contracts']} contracts, "
        f"cap {out['sizing']['max_inv_orders']} quotes",
    ]
    q = out["quotes"]
    if q["compared"]:
        lines.append(f"live quotes equal to the shadow's: {q['same']}/{q['compared']} samples ({q['pct']:.1f}%)")
    head = (f"{'row':20s} {'fills':>6s} {'/day':>6s} {'$/day':>8s} {'mkr%':>5s} {'up%':>5s} {'in%':>5s} {'capt':>6s} "
            + " ".join(f"{f'mo{h}':>6s}" for h in sim.HORIZONS)
            + f" {'fee':>5s} {'net60':>6s} {'net300':>6s} {'PnL$':>7s} {'spr$':>7s} {'inv$':>7s} {'fee$':>7s}")
    lines.append(head)
    for label, r in out["rows"].items():
        name = "real (Delta fills)" if label == "real" else label
        lines.append(
            f"{name:20s} {r['fills']:6d} {r['fills_per_day']:6.0f} {r['usd_per_day']:8,.0f} {r['maker_pct']:5.0f} "
            f"{r['uptime']:5.0%} {r['inside']:5.0%} {r['capture']:6.2f} "
            + " ".join(f"{r[f'mo{h}']:6.2f}" for h in sim.HORIZONS)
            + f" {r['fee']:5.2f} {r['net60']:6.2f} {r['net300']:6.2f} {r['pnl_total']:7.2f} {r['pnl_spread']:7.2f} "
            f"{r['pnl_inventory']:7.2f} {r['pnl_fees']:7.2f}")
    real = out["rows"]["real"]
    if real["taker_fills"]:
        lines.append(f"! {real['taker_fills']} real taker fill(s): quotes are post-only, so only a reduce-only exit takes")
    for label, r in out["rows"].items():
        if label.startswith("sim shadow") and r["fills"]:
            lines.append(f"real fills / {label} fills: {real['fills'] / r['fills']:.2f}")
    if out.get("start_inventory"):
        lines.append(f"the live bot started holding {out['start_inventory']:g} {out['symbol'][:-4]}")
    lines.append(f"live stop rule: {stop_rule(real)}")
    lines.append("Real fills are scored once their 300 s markout exists; PnL$ excludes the mark-to-market of any position "
                 "held before the run.")
    return "\n".join(lines)


# ---------------------------------------------------------------- venue

def venue_text(get, product_id: int, symbol: str) -> str:
    """Account equity, the product's position and its open orders (read-only)."""
    lines = []
    bal = get("/v2/wallet/balances")
    eq = (bal.get("meta") or {}).get("net_equity") if bal.get("success") is not False else None
    lines.append(f"venue: equity {eq}" if eq is not None else f"venue: wallet read failed ({error_code(bal)})")
    pos = get("/v2/positions/margined", f"product_ids={product_id}")
    if pos.get("success") is False:
        lines.append(f"venue: position read failed ({error_code(pos)})")
    else:
        rows = pos.get("result") or []
        size = sum(float(r.get("size") or 0) for r in rows)
        entry = next((r.get("entry_price") for r in rows if float(r.get("size") or 0)), None)
        lines.append(f"venue: position {symbol} {size:g} contracts" + (f" @ {entry}" if entry else ""))
    orders = get("/v2/orders", f"product_ids={product_id}&states=open,pending")
    if orders.get("success") is False:
        lines.append(f"venue: open orders read failed ({error_code(orders)})")
    else:
        rows = orders.get("result") or []
        lines.append(f"venue: open orders {len(rows)}")
        for o in rows:
            lines.append(f"  {o.get('side')} {o.get('size')} @ {o.get('limit_price')} ({o.get('state')})")
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    venue_mode = bool(argv) and argv[0] == "venue"
    if venue_mode:
        argv = argv[1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live-dir", type=Path, default=CEX_MM / "artifacts" / "live" / "current")
    ap.add_argument("--shadow-dir", type=Path, action="append",
                    help="shadow run directory (repeatable); default: every run that overlaps the live window")
    ap.add_argument("--env-file", type=Path, default=CEX_MM / "quote-bot" / ".env")
    ap.add_argument("--symbol", help="MM symbol, default the live run's MM_SYMBOLS")
    ap.add_argument("--latencies", default="20,300", help="comma list of simulated quote latencies, ms")
    ap.add_argument("--offline", action="store_true", help="use <live run>/fills.json instead of calling Delta")
    ap.add_argument("--hours", type=float, help="compare only the last N hours of the live run")
    ap.add_argument("--compact", action="store_true",
                    help=f"keep one unchanged sample per {COMPACT_MS / 1000:g} s: fits a long run in memory, "
                    "about 1%% fewer simulated fills")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    live_dir = args.live_dir.resolve()
    cfg = read_config(live_dir)
    symbol = args.symbol or (cfg.get("MM_SYMBOLS") or "ADAUSDT").split(",")[0]
    dsym = sim.delta_symbol(symbol)
    if venue_mode:
        pid, _, _ = product(dsym)
        print(venue_text(Delta(args.env_file).get, pid, dsym))
        return

    span = live_span(sorted(glob.glob(str(live_dir / "bot*.log*"))), symbol)
    if not span:
        raise SystemExit(f"no MM_METRICS samples for {symbol} in {live_dir}")
    tick, cv = sim.product_meta(dsym)
    fills_path = live_dir / "fills.json"
    if args.offline:
        rows = json.loads(fills_path.read_text()) if fills_path.exists() else []
    else:
        pid, _, _ = product(dsym)
        rows = fetch_fills(Delta(args.env_file).get, pid, span[0] - 120_000)
        fills_path.write_text(json.dumps(rows))
    shadow_dirs = [d.resolve() for d in args.shadow_dir] if args.shadow_dir else None
    if not shadow_dirs:
        shadow_dirs = shadow_runs_for(CEX_MM / "artifacts" / "shadow", span[0], span[1])
    since = span[1] - args.hours * 3.6e6 if args.hours else 0.0
    out = compare(live_dir, shadow_dirs, rows, [float(x) for x in args.latencies.split(",")], tick, cv, symbol,
                  since_ms=since, heartbeat_ms=COMPACT_MS if args.compact else 0.0)
    print(json.dumps(out, indent=1) if args.json else format_table(out))


if __name__ == "__main__":
    main()
