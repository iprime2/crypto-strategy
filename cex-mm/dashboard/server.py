#!/usr/bin/env python3
"""Live MM bot telemetry dashboard — tails MM_METRICS log + economics JSON."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from delta_pnl import fetch_venue_pnl

ROOT = Path(__file__).resolve().parent
CEX_MM = ROOT.parent
DEFAULT_LOG = CEX_MM / "artifacts" / "delta-mm-run.log"
STATIC = ROOT / "static"
MAX_POINTS = 400

METRICS_RE = re.compile(r"MM_METRICS:\s*(\{.*\})\s*$")
WARN_RE = re.compile(
    r"mm_bot::runner:\s+(?P<msg>.+?)\s+symbol=(?P<sym>\S+)"
)
ORDER_RE = re.compile(
    r"MM_ORDER:\s+placed post-only symbol=(?P<sym>\S+) side=\"?(?P<side>\w+)\"? "
    r"price=(?P<price>[\d.]+) qty=(?P<qty>[\d.]+)"
)
REDUCE_ORDER_RE = re.compile(
    r"MM_ORDER:\s+reduce-only\s+symbol=(?P<sym>\S+)\s+side=\"?(?P<side>\w+)\"?\s+"
    r"qty=(?P<qty>[\d.]+)\s+price=(?P<price>[\d.]+)"
)
REJECT_LEGACY_RE = re.compile(
    r"mm_bot::runner:\s+(?P<side>bid|ask) reject symbol=(?P<sym>\S+)"
)
REJECT_RE = re.compile(
    r"MM_REJECT:\s+post-only reject symbol=(?P<sym>\S+) side=\"(?P<side>\w+)\" "
    r"price=(?P<price>[\d.]+) qty=(?P<qty>[\d.eE+-]+)"
)
REJECT_ERR_RE = re.compile(r'"code"\s*:\s*"([^"]+)"')


def load_dashboard_config() -> dict:
    """Active bot symbols from .env; optional inactive cards for monitoring only."""
    active = ["BTCUSDT", "ETHUSDT"]
    venue = "delta"
    env_path = CEX_MM / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("MM_SYMBOLS="):
                active = [
                    s.strip().upper()
                    for s in line.split("=", 1)[1].split(",")
                    if s.strip()
                ]
            elif line.startswith("MM_VENUE="):
                venue = line.split("=", 1)[1].strip().lower()
    inactive_env = os.environ.get("MM_DASHBOARD_INACTIVE", "SOLUSDT")
    inactive = [
        s.strip().upper()
        for s in inactive_env.split(",")
        if s.strip() and s.strip().upper() not in active
    ]
    caps: dict[str, float] = {}
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if not key.startswith("MM_MAX_INVENTORY"):
                continue
            try:
                qty = float(val.strip())
            except ValueError:
                continue
            if key == "MM_MAX_INVENTORY":
                caps["*"] = qty
            elif key.startswith("MM_MAX_INVENTORY_"):
                caps[key.removeprefix("MM_MAX_INVENTORY_").upper()] = qty
    return {
        "venue": venue,
        "active_symbols": active,
        "inactive_symbols": inactive,
        "max_inventory": caps,
    }


def cap_for(config: dict, symbol: str) -> float | None:
    caps = config.get("max_inventory") or {}
    if symbol in caps:
        return float(caps[symbol])
    if "*" in caps:
        return float(caps["*"])
    return None


def build_risk_rows(latest: dict, venue_pnl: dict, config: dict) -> list[dict]:
    """Per-symbol account risk from bot metrics + venue positions."""
    positions = (venue_pnl or {}).get("positions") or {}
    equity = float((venue_pnl or {}).get("net_equity_usd") or 0.0)
    inactive = set(config.get("inactive_symbols") or [])
    symbols = sorted(
        (
            set(latest)
            | set(positions)
            | set(config.get("active_symbols") or [])
        )
        - {s for s in inactive if s not in positions}
    )
    rows: list[dict] = []
    for sym in symbols:
        metrics = latest.get(sym) or {}
        pos = positions.get(sym) or {}
        bot_q = metrics.get("inventory")
        venue_q = pos.get("position_base")
        cap = cap_for(config, sym)
        mark = pos.get("mark_price") or metrics.get("venue_mid") or metrics.get("fair")
        q_ref = venue_q if venue_q is not None else bot_q
        notional = None
        if q_ref is not None and mark:
            notional = abs(float(q_ref)) * float(mark)
        upnl = pos.get("unrealized_pnl_usd")
        leverage = (notional / equity) if notional is not None and equity > 0 else None
        shock_10 = (0.10 * notional) if notional is not None else None
        upnl_pct = (float(upnl) / equity * 100.0) if upnl is not None and equity > 0 else None
        mismatch = False
        if bot_q is not None and venue_q is not None:
            mismatch = abs(float(bot_q) - float(venue_q)) > 1e-5
        over_cap = False
        cap_ratio = None
        if cap and cap > 0 and q_ref is not None:
            cap_ratio = abs(float(q_ref)) / cap
            over_cap = abs(float(q_ref)) > cap * 1.05
        shock_flag = bool(
            shock_10 is not None and equity > 0 and shock_10 > 0.02 * equity
        )
        rows.append(
            {
                "symbol": sym,
                "bot_qty": bot_q,
                "venue_qty": venue_q,
                "cap": cap,
                "cap_ratio": cap_ratio,
                "mark": mark,
                "notional_usd": notional,
                "leverage": leverage,
                "unrealized_pnl_usd": upnl,
                "upnl_pct_equity": upnl_pct,
                "shock_10pct_usd": shock_10,
                "mismatch": mismatch,
                "over_cap": over_cap,
                "shock_flag": shock_flag,
                "metrics_ts": metrics.get("_ts"),
            }
        )
    return rows


class TelemetryStore:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.lock = threading.Lock()
        self.offset = 0
        self.latest: dict[str, dict] = {}
        self.series: dict[str, dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=MAX_POINTS))
        )
        self.events: deque[dict] = deque(maxlen=200)
        self.counters = defaultdict(int)
        self.session_counters = defaultdict(float)
        self.session_started_at = time.time()
        self.last_order: dict[str, dict] = {}
        self.started = time.time()
        self.config = load_dashboard_config()
        self._venue_pnl: dict = {}
        self._venue_pnl_at: float = 0.0
        self._venue_pnl_ttl = float(os.environ.get("MM_DASHBOARD_PNL_POLL_SEC", "8"))

    def ingest_line(self, line: str, *, record_session: bool = True) -> None:
        line = line.strip()
        if not line:
            return
        m = METRICS_RE.search(line)
        if m:
            try:
                row = json.loads(m.group(1))
            except json.JSONDecodeError:
                return
            sym = row.get("symbol", "?")
            ts = time.time()
            row["_ts"] = ts
            with self.lock:
                self.latest[sym] = row
                for key in (
                    "fair",
                    "venue_mid",
                    "spread_bps",
                    "vol_bps",
                    "inventory",
                    "lead_skew_bps",
                    "rolling_adverse_bps",
                    "regime_level",
                    "snipe_rate",
                ):
                    val = row.get(key)
                    if val is None:
                        continue
                    self.series[sym][key].append({"t": ts, "v": float(val)})
                if row.get("binance_mid") is not None:
                    self.series[sym]["binance_mid"].append(
                        {"t": ts, "v": float(row["binance_mid"])}
                    )
            return
        rom = REDUCE_ORDER_RE.search(line)
        if rom:
            sym = rom.group("sym")
            side = rom.group("side")
            qty = float(rom.group("qty"))
            with self.lock:
                if record_session:
                    self.session_counters["reduce_only_orders"] += 1
                    self.session_counters["order_placed_total"] += 1
                    self.session_counters[f"order_placed_{sym}"] += 1
                self.last_order[sym] = {
                    "t": time.time(),
                    "side": side,
                    "price": float(rom.group("price")),
                    "qty": qty,
                    "reduce_only": True,
                }
                if record_session:
                    self.events.appendleft(
                        {
                            "t": time.time(),
                            "symbol": sym,
                            "kind": "order",
                            "message": f"reduce-only {side} @ {rom.group('price')} qty {rom.group('qty')}",
                        }
                    )
            return
        om = ORDER_RE.search(line)
        if om:
            sym = om.group("sym")
            side = om.group("side")
            qty = float(om.group("qty"))
            with self.lock:
                if record_session:
                    key = f"order_placed_{sym}"
                    self.counters[key] += 1
                    self.counters["order_placed_total"] += 1
                    self.session_counters[key] += 1
                    self.session_counters["order_placed_total"] += 1
                    self.session_counters[f"order_qty_{sym}"] += qty
                    self.session_counters["order_qty_total"] += qty
                self.last_order[sym] = {
                    "t": time.time(),
                    "side": side,
                    "price": float(om.group("price")),
                    "qty": qty,
                }
                if record_session:
                    self.events.appendleft(
                        {
                            "t": time.time(),
                            "symbol": sym,
                            "kind": "order",
                            "message": f"placed {side} @ {om.group('price')} qty {om.group('qty')}",
                        }
                    )
            return
        rm = REJECT_RE.search(line) or REJECT_LEGACY_RE.search(line)
        if rm:
            sym = rm.group("sym")
            side = rm.group("side")
            if side in ("bid", "ask"):
                side = "buy" if side == "bid" else "sell"
            qty = float(rm.group("qty")) if rm.re is REJECT_RE else 0.0
            price = float(rm.group("price")) if rm.re is REJECT_RE else 0.0
            err_m = REJECT_ERR_RE.search(line)
            err_code = err_m.group(1) if err_m else "unknown"
            with self.lock:
                if record_session:
                    self.counters[f"reject_{sym}"] += 1
                    self.counters["reject_total"] += 1
                    self.session_counters[f"reject_{sym}"] += 1
                    self.session_counters["reject_total"] += 1
                    if qty > 0:
                        self.session_counters[f"reject_qty_{sym}"] += qty
                        self.session_counters["reject_qty_total"] += qty
                    self.session_counters[f"reject_reason_{err_code}"] += 1
                    msg = f"{side} reject qty {qty}" if qty else f"{side} reject"
                    if price > 0:
                        msg += f" @ {price}"
                    msg += f" ({err_code})"
                    self.events.appendleft(
                        {
                            "t": time.time(),
                            "symbol": sym,
                            "kind": "reject",
                            "message": msg,
                        }
                    )
            return
        wm = WARN_RE.search(line)
        if wm:
            msg = wm.group("msg")
            sym = wm.group("sym")
            with self.lock:
                self.counters[msg] += 1
                if record_session:
                    if "risk kill" in msg:
                        self.session_counters["risk_kill"] += 1
                    elif "hard cap" in msg and "reduce-only" in msg:
                        self.session_counters["hard_cap_reduce"] += 1
                    elif "regime L3" in msg or "kill switch / L3" in msg:
                        self.session_counters["l3_cancel"] += 1
                self.events.appendleft(
                    {
                        "t": time.time(),
                        "symbol": sym,
                        "kind": "warn",
                        "message": msg,
                    }
                )

    def tail_once(self) -> None:
        if not self.log_path.is_file():
            return
        with self.log_path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(self.offset)
            for line in f:
                self.ingest_line(line)
            self.offset = f.tell()

    def load_economics(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        eco_dir = CEX_MM / "artifacts" / "economics"
        if not eco_dir.is_dir():
            return out
        for path in eco_dir.glob("*.json"):
            try:
                out[path.stem.upper().replace("_", "")] = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def venue_pnl_cached(self) -> dict:
        now = time.time()
        if now - self._venue_pnl_at >= self._venue_pnl_ttl:
            self._venue_pnl = fetch_venue_pnl()
            self._venue_pnl_at = now
        return self._venue_pnl

    def snapshot(self) -> dict:
        self.tail_once()
        venue_pnl = self.venue_pnl_cached()
        with self.lock:
            return {
                "uptime_sec": time.time() - self.started,
                "log_path": str(self.log_path),
                "config": dict(self.config),
                "latest": dict(self.latest),
                "last_order": dict(self.last_order),
                "series": {
                    sym: {k: list(v) for k, v in metrics.items()}
                    for sym, metrics in self.series.items()
                },
                "events": list(self.events)[:40],
                "counters": dict(self.counters),
                "session_counters": dict(self.session_counters),
                "session_started_at": self.session_started_at,
                "economics": self.load_economics(),
                "venue_pnl": venue_pnl,
                "risk": build_risk_rows(self.latest, venue_pnl, self.config),
                "server_now": time.time(),
            }


STORE: TelemetryStore | None = None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            assert STORE is not None
            body = json.dumps(STORE.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        return


def tail_loop(store: TelemetryStore) -> None:
    while True:
        store.tail_once()
        time.sleep(0.5)


def main() -> None:
    global STORE
    log_path = Path(os.environ.get("MM_LOG_PATH", str(DEFAULT_LOG)))
    port = int(os.environ.get("MM_DASHBOARD_PORT", "8787"))
    STORE = TelemetryStore(log_path)
    if log_path.is_file():
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                STORE.ingest_line(line, record_session=False)
            STORE.offset = f.tell()
    threading.Thread(target=tail_loop, args=(STORE,), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"MM dashboard http://127.0.0.1:{port}/  (log: {log_path})")
    server.serve_forever()


if __name__ == "__main__":
    main()
