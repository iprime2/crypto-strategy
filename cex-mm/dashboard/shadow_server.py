#!/usr/bin/env python3
"""Shadow-test dashboard: live dry-run quotes, recorded Delta mainnet trades, simulated fills.

Tails `artifacts/shadow/current/` (see `scripts/shadow.sh`) and re-runs the fill simulator
from `scripts/shadow_fill_sim.py` in the background. Read-only; binds to 127.0.0.1.

    python3 dashboard/shadow_server.py            # http://127.0.0.1:8788/
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import json
import os
import statistics
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
CEX_MM = ROOT.parent
sys.path.insert(0, str(CEX_MM / "scripts"))
import shadow_fill_sim as sim  # noqa: E402

CURRENT = CEX_MM / "artifacts" / "shadow" / "current"
PAGE = ROOT / "static" / "shadow.html"
# Other pages and shared assets, by URL path.
STATIC = {
    "/trend": ("trend.html", "text/html; charset=utf-8"),
    "/common.css": ("common.css", "text/css; charset=utf-8"),
    "/charts.js": ("charts.js", "text/javascript; charset=utf-8"),
}
TREND_DIR = CEX_MM / "artifacts" / "trend" / "paper"  # written by scripts/trend_paper.py
RECENT_MS = 60 * 60 * 1000  # full-resolution window kept for the live chart
MAX_POINTS = 900
MAX_POINTS_ALL = 1500  # "All" window: whole run, thinned for the chart
READ_CHUNK = 32 * 1024 * 1024
SWEEP = [3.0, 4.0, 5.0, 6.0, 8.0]
PRIMARY = "bot quotes 300ms"


def config_for(label: str) -> sim.SimConfig:
    base = dict(
        rule="strict",
        quote_usd=50.0,
        max_inv_orders=3,
        fee_bps=2.12,
        requote_tol_bps=3.0,
        max_gap_ms=1500.0,
        loop_ms=400.0,
        latency_ms=300.0,
        half_spread_bps=None,
    )
    if label == "bot quotes 1000ms":
        base["latency_ms"] = 1000.0
    elif label == "bot quotes, touch rule":
        base["rule"] = "touch"
    elif label.startswith("fair +/- "):
        base["half_spread_bps"] = float(label.split()[2].removesuffix("bps"))
    return sim.SimConfig(**base)


CONFIGS = [PRIMARY, "bot quotes 1000ms", "bot quotes, touch rule"] + [f"fair +/- {h:g}bps" for h in SWEEP]


class SymbolState:
    def __init__(self) -> None:
        self.recent: collections.deque[sim.Sample] = collections.deque()
        self.sim_samples: list[sim.Sample] = []
        self.samples = 0
        self.with_binance = 0

    def add(self, s: sim.Sample) -> None:
        self.samples += 1
        if s.binance_mid > 0:
            self.with_binance += 1
        self.recent.append(s)
        while self.recent and s.ts - self.recent[0].ts > RECENT_MS:
            self.recent.popleft()
        # Compact copy for the simulator: keep a sample when the quote or book changed,
        # fair moved >= 0.5 bps, or 1 s passed (keeps quotes alive under the 1.5 s gap rule).
        last = self.sim_samples[-1] if self.sim_samples else None
        if (
            last is None
            or s.ts - last.ts >= 1000
            or (s.bid, s.ask, s.place_bid, s.place_ask, s.regime, s.book_bid, s.book_ask)
            != (last.bid, last.ask, last.place_bid, last.place_ask, last.regime, last.book_bid, last.book_ask)
            or abs(s.fair / last.fair - 1) * 1e4 >= 0.5
        ):
            self.sim_samples.append(s)


class RunState:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.offsets: dict[str, int] = {}
        self.partial: dict[str, str] = {}
        self.symbols: dict[str, SymbolState] = collections.defaultdict(SymbolState)
        self.trades: dict[str, list[sim.Trade]] = collections.defaultdict(list)
        self.clock_offset: collections.deque[float] = collections.deque(maxlen=500)
        self.l3_pauses: collections.Counter[str] = collections.Counter()
        self.sim: dict[str, dict] = {}
        self.sim_at = 0.0
        self.sim_seconds = 0.0
        self.meta: dict[str, tuple[float, float]] = {}


LOCK = threading.Lock()
STATE: RunState | None = None


def read_new_lines(state: RunState, path: str) -> list[str]:
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    off = state.offsets.get(path, 0)
    if size < off:  # truncated or replaced
        off = 0
    if size == off:
        return []
    with open(path, "rb") as f:
        f.seek(off)
        chunk = f.read(READ_CHUNK)
    state.offsets[path] = off + len(chunk)
    text = state.partial.pop(path, "") + chunk.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if not text.endswith("\n"):
        state.partial[path] = lines.pop()
    return lines


def tail_once() -> bool:
    """Read whatever is new; returns True if a backlog remains."""
    global STATE
    run_dir = CURRENT.resolve() if CURRENT.exists() else None
    if run_dir is None:
        return False
    with LOCK:
        if STATE is None or STATE.run_dir != run_dir:
            STATE = RunState(run_dir)
        state = STATE
    backlog = False
    log = str(run_dir / "dry-run.log")
    lines = read_new_lines(state, log)
    parsed = []
    l3 = collections.Counter()
    for line in lines:
        p = sim.parse_metrics_line(line)
        if p:
            parsed.append(p)
        elif "L3 pause" in line and "symbol=" in line:
            l3[line.split("symbol=", 1)[1].split()[0]] += 1
    trades = []
    for path in sorted(glob.glob(str(run_dir / "delta_mainnet_public_*.jsonl"))):
        for line in read_new_lines(state, path):
            t = sim.parse_trade_record(line)
            if t:
                trades.append(t)
        backlog |= state.offsets.get(path, 0) < os.path.getsize(path)
    backlog |= state.offsets.get(log, 0) < (os.path.getsize(log) if os.path.exists(log) else 0)
    with LOCK:
        for sym, s in parsed:
            state.symbols[sym].add(s)
        state.l3_pauses.update(l3)
        for dsym, t, exch_ms in trades:
            state.trades[dsym].append(t)
            if exch_ms:
                state.clock_offset.append(t.ts - exch_ms)
    return backlog


def tail_loop() -> None:
    while True:
        try:
            backlog = tail_once()
        except Exception:  # keep the dashboard alive; show the error in the server log
            traceback.print_exc()
            backlog = False
        time.sleep(0.05 if backlog else 1.0)


def pnl_series(fills: list[sim.Fill], mids: sim.MidSeries, cv: float, end_ts: float) -> dict:
    t, net, spread, fees = [], [], [], []
    cash = inv = fee_sum = spread_sum = 0.0
    for f in fills:
        cash -= f.side * f.qty * cv * f.price
        inv += f.side * f.qty
        fee_sum += f.fee
        spread_sum += f.side * (f.mid - f.price) * f.qty * cv
        mid = mids.at(f.ts) or f.mid
        t.append(f.ts)
        net.append(cash + inv * cv * mid - fee_sum)
        spread.append(spread_sum)
        fees.append(-fee_sum)
    if fills and mids.mid:
        t.append(end_ts)
        net.append(cash + inv * cv * mids.mid[-1] - fee_sum)
        spread.append(spread_sum)
        fees.append(-fee_sum)
    step = max(1, len(t) // MAX_POINTS)
    idx = list(range(0, len(t), step))
    if t and idx[-1] != len(t) - 1:
        idx.append(len(t) - 1)
    return {
        "t": [t[i] for i in idx],
        "net": [round(net[i], 4) for i in idx],
        "spread": [round(spread[i], 4) for i in idx],
        "fees": [round(fees[i], 4) for i in idx],
    }


def fill_rows(fills: list[sim.Fill], mids: sim.MidSeries, cv: float, n: int = 40) -> list[dict]:
    rows = []
    for f in fills[-n:]:
        row = {
            "t": f.ts,
            "side": "buy" if f.side > 0 else "sell",
            "price": f.price,
            "usd": round(f.notional, 2),
            "capture": round(f.side * (f.mid - f.price) / f.price * 1e4, 2),
        }
        for h in (5, 60, 300):
            m = mids.at(f.ts + h * 1000)
            row[f"mo{h}"] = None if m is None else round(f.side * (m - f.mid) / f.mid * 1e4, 2)
        rows.append(row)
    return rows[::-1]


def run_sim_once() -> None:
    with LOCK:
        state = STATE
        if state is None:
            return
        work = {
            sym: (list(st.sim_samples), list(state.trades.get(sim.delta_symbol(sym), [])))
            for sym, st in state.symbols.items()
        }
    started = time.time()
    results = {}
    for sym, (samples, tape) in work.items():
        if len(samples) < 10:
            continue
        dsym = sim.delta_symbol(sym)
        if dsym not in state.meta:
            state.meta[dsym] = sim.product_meta(dsym)
        tick, cv = state.meta[dsym]
        mids = sim.MidSeries(samples)
        rows = []
        primary = None
        for label in CONFIGS:
            res = sim.simulate(samples, tape, tick, cv, config_for(label))
            s = sim.summarize(res, mids, cv)
            s["label"] = label
            s["half_spread"] = config_for(label).half_spread_bps
            s["verdict"] = sim.verdict(s, 300, 0.5)
            rows.append(s)
            if label == PRIMARY:
                primary = (res, s)
        res, s = primary
        edge = [{"h": 0, "bps": round(s["capture"] - s["fee"], 3)}] + [
            {"h": h, "bps": round(s["capture"] + s["mo"][h] - s["fee"], 3)} for h in sim.HORIZONS
        ]
        results[sym] = {
            "rows": rows,
            "pnl": pnl_series(res.fills, mids, cv, samples[-1].ts),
            "edge": edge,
            "fills": fill_rows(res.fills, mids, cv),
            "fill_ts": [(f.ts, f.price, f.side) for f in res.fills],
            "tick": tick,
            "contract_value": cv,
        }
    with LOCK:
        if STATE is state:
            state.sim = results
            state.sim_at = time.time()
            state.sim_seconds = time.time() - started


def sim_loop(every: float) -> None:
    time.sleep(5)
    while True:
        try:
            run_sim_once()
        except Exception:
            traceback.print_exc()
        time.sleep(every)


def pid_alive(path: Path) -> bool:
    try:
        os.kill(int(path.read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def downsample(samples: list, max_points: int = MAX_POINTS) -> list:
    step = max(1, len(samples) // max_points)
    out = samples[::step]
    if samples and out[-1] is not samples[-1]:
        out.append(samples[-1])
    return out


def build_payload(symbol: str | None, window_min: float | None) -> dict:
    """`window_min=None` means the whole run (compact samples kept for the simulator)."""
    with LOCK:
        state = STATE
        if state is None:
            return {"ok": False, "error": "no shadow run found (artifacts/shadow/current)"}
        syms = sorted(state.symbols)
        symbol = symbol if symbol in state.symbols else (syms[0] if syms else None)
        st = state.symbols.get(symbol) if symbol else None
        recent = list(st.recent) if st else []
        whole = list(st.sim_samples) if st and window_min is None else []
        dsym = sim.delta_symbol(symbol) if symbol else ""
        tape_all = state.trades.get(dsym, [])
        sim_res = state.sim.get(symbol) if symbol else None
        sim_at, sim_seconds = state.sim_at, state.sim_seconds
        counts = {
            s: {
                "samples": v.samples,
                "binance_pct": round(100 * v.with_binance / v.samples, 1) if v.samples else 0.0,
                "l3_pauses": state.l3_pauses.get(s, 0),
                "trades": len(state.trades.get(sim.delta_symbol(s), [])),
            }
            for s, v in state.symbols.items()
        }
        offsets = list(state.clock_offset)
        run_dir = state.run_dir
    config = {}
    cfg_path = run_dir / "config.txt"
    if cfg_path.exists():
        for line in cfg_path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                config[k] = v
    now_ms = time.time() * 1000
    last = recent[-1] if recent else None
    if window_min is None:
        win = whole
        cutoff = win[0].ts if win else now_ms
        max_points = MAX_POINTS_ALL
    else:
        cutoff = (last.ts if last else now_ms) - window_min * 60_000
        win = [s for s in recent if s.ts >= cutoff]
        max_points = MAX_POINTS
    ratios = [((s.book_bid + s.book_ask) / 2) / s.binance_mid for s in win if s.binance_mid > 0]
    basis = statistics.median(ratios) if ratios else None
    pts = downsample(win, max_points)
    series = {
        "t": [s.ts for s in pts],
        "book_bid": [s.book_bid for s in pts],
        "book_ask": [s.book_ask for s in pts],
        "bid": [s.bid if s.place_bid else None for s in pts],
        "ask": [s.ask if s.place_ask else None for s in pts],
        "fair": [round(s.fair, 8) for s in pts],
        "binance": [round(s.binance_mid * basis, 8) if basis and s.binance_mid > 0 else None for s in pts],
    }
    i0 = bisect.bisect_left([t.ts for t in tape_all], cutoff) if tape_all else 0
    in_window = tape_all[i0:]
    # Short windows show the latest 500 trades; "All" thins the whole tape evenly.
    shown = downsample(in_window, max_points) if window_min is None else in_window[-500:]
    tape = [{"t": t.ts, "p": t.price, "side": "buy" if t.aggressor > 0 else "sell", "size": t.size} for t in shown]
    fills_win = []
    if sim_res:
        fills_win = [{"t": t, "p": p, "side": "buy" if s > 0 else "sell"} for t, p, s in sim_res["fill_ts"] if t >= cutoff]
    live = None
    if last:
        mid = (last.book_bid + last.book_ask) / 2
        live = {
            "t": last.ts,
            "age_s": round((now_ms - last.ts) / 1000, 1),
            "fair": last.fair,
            "bid": last.bid if last.place_bid else None,
            "ask": last.ask if last.place_ask else None,
            "book_bid": last.book_bid,
            "book_ask": last.book_ask,
            "binance": last.binance_mid or None,
            "regime": last.regime,
            "delta_spread_bps": round((last.book_ask - last.book_bid) / mid * 1e4, 2),
            "our_half_bps": round((last.ask - last.bid) / last.fair * 1e4 / 2, 2),
            "basis_bps": round((basis - 1) * 1e4, 2) if basis else None,
        }
    sim_out = None
    if sim_res:
        sim_out = {k: v for k, v in sim_res.items() if k != "fill_ts"}
        sim_out["computed_at"] = sim_at * 1000
        sim_out["seconds"] = round(sim_seconds, 1)
    try:
        disk_mb = sum(p.stat().st_size for p in run_dir.iterdir() if p.is_file()) / 1e6
    except OSError:
        disk_mb = None
    return {
        "ok": True,
        "run": {"id": run_dir.name, "config": config},
        "symbols": syms,
        "symbol": symbol,
        "health": {
            "dry_run": pid_alive(run_dir / "dry-run.pid"),
            "recorder": pid_alive(run_dir / "recorder.pid"),
            "clock_offset_ms": round(statistics.median(offsets)) if offsets else None,
            "disk_mb": round(disk_mb, 1) if disk_mb is not None else None,
            "counts": counts,
        },
        "live": live,
        "series": series,
        "tape": tape,
        "fills_window": fills_win,
        "sim": sim_out,
        "server_time": now_ms,
    }


def trend_payload() -> dict:
    """Paper trader state plus its journal (one line per daily rebalance)."""
    try:
        state = json.loads((TREND_DIR / "state.json").read_text())
        journal = [json.loads(line) for line in (TREND_DIR / "journal.jsonl").read_text().splitlines() if line.strip()]
    except FileNotFoundError:
        return {"ok": False, "error": f"No paper trader state in {TREND_DIR}: it has not rebalanced yet"}
    if not journal:
        return {"ok": False, "error": "The paper trader has not rebalanced yet"}
    return {"ok": True, "state": state, "journal": journal, "server_time": int(time.time() * 1000)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quiet access log
        return

    def send_body(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send_body(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/shadow":
            q = parse_qs(url.query)
            raw = q.get("window", ["15"])[0]
            window: float | None
            if raw == "all":
                window = None
            else:
                try:
                    window = max(1.0, min(60.0, float(raw)))
                except ValueError:
                    window = 15.0
            payload = build_payload(q.get("symbol", [None])[0], window)
            self.send_body(200, json.dumps(payload, allow_nan=False, default=str).encode(), "application/json")
        elif url.path in STATIC:
            name, ctype = STATIC[url.path]
            self.send_body(200, (ROOT / "static" / name).read_bytes(), ctype)
        elif url.path == "/api/trend":
            self.send_body(200, json.dumps(trend_payload()).encode(), "application/json")
        else:
            self.send_body(404, b"not found", "text/plain")


def main() -> None:
    global TREND_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--sim-every", type=float, default=120.0, help="seconds between simulator runs")
    ap.add_argument("--trend-dir", type=Path, default=TREND_DIR, help="trend paper trader state directory")
    args = ap.parse_args()
    TREND_DIR = args.trend_dir
    threading.Thread(target=tail_loop, daemon=True).start()
    threading.Thread(target=sim_loop, args=(args.sim_every,), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"shadow dashboard on http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
