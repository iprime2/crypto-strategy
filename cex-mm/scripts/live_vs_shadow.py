#!/usr/bin/env python3
"""Compare the real-money live run (scripts/live.sh) with the shadow simulator.

Real fills come from Delta's GET /v2/fills (read-only, the mainnet key in quote-bot/.env): the venue is the
source of truth. Fill times are exchange times; they are moved onto the VM's local clock by the median recorder
offset (local receive time minus exchange time) of the shadow's trade tape.

While the live bot quotes, its own orders are usually the Delta touch (ADA's spread is ~12 bps, the bot quotes
fair +/- 5 bps). The shadow then sees our quotes as the book, its fair follows them, and the trades that fill us
print at our price, which the simulator's strict rule does not count. So the simulator cannot be run on the live
window itself. Instead:

  real (Delta fills)   the live bot's fills over the report window, fees as charged
  sim baseline <N>ms   shadow_fill_sim on the shadow's quotes and tape just BEFORE the live run started, when the
                       book and tape did not contain our orders (the window's length, kept within 1-24 h)

Per-fill edge (net60 = capture + 60 s markout - fee, bps, notional-weighted, as shadow_fill_sim.py) on two
references, and one figure that needs none:
  capt, mo*, net60     the Delta L1 mid logged by the shadow. Clean for the baseline; for the real row it is
                       biased, because during the run that mid is mostly our own two quotes.
  bcapt, bmo*, bnet60  the Binance mid in MM_METRICS, which our orders cannot move, shifted by the Delta-Binance
                       basis measured in the baseline (ADA: Delta 4-7 bps below Binance, daily medians 6-8 Oct).
                       A Binance mid unchanged for over 15 min is treated as missing: the feed froze for 3.5 days
                       on 8-12 Oct. Compare real with sim on these columns, like for like.
  PnLbp                PnL$ per dollar traded, in bps: cash flows plus the inventory marked at the last mid,
                       minus fees.

Live stop rule (2026-10-12 memo, calibrated on the 6-12 Oct shadow): STOP if real PnL per dollar traded is below
-2.6 bps after 300 fills, or below 0 after 1,000 fills. It counts every real fill in the window, marked at the live
bot's own last mid, so it does not depend on the shadow running.

    python3 scripts/live_vs_shadow.py                    # artifacts/live/current vs the shadow runs around it
    python3 scripts/live_vs_shadow.py --hours 24 --json
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
# Live stop rule (2026-10-12 memo): PnL per $ traded below EARLY_BPS after EARLY_FILLS fills, or below 0 after
# FULL_FILLS. About 5% false stops on flat-start 300-fill blocks of the 6-12 Oct ADA shadow (mean +2.6, sd 2.6 bps).
EARLY_FILLS, EARLY_BPS, FULL_FILLS = 300, -2.6, 1000
DMS_MS = 15_000.0  # MM_DMS_TTL_MS in config/dism.env: a stopped run's orders may rest this long
TAIL_BYTES = 4_000_000  # live_span reads this much of the log's end before falling back to a full scan
BASELINE_GAP_MS = 300_000.0  # the baseline ends this long before the live start, so its 300 s markouts are clean
MIN_BASELINE_MS, MAX_BASELINE_MS = 3.6e6, 24 * 3.6e6  # baseline = the window's length, clamped to 1-24 h
LATE_FILL_MS = 20_000.0  # real fills this long after the bot's last sample still count (orders rest until the DMS)


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
    fill_type: str = "normal"


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
            fill_type=str(row.get("fill_type") or "normal"),
        )
    except (KeyError, TypeError, ValueError):
        return None


class FillsIncomplete(RuntimeError):
    """Paging hit its cap before reaching the run's start; `rows` holds what was fetched."""

    def __init__(self, message: str, rows: list[dict]):
        super().__init__(message)
        self.rows = rows


def fetch_fills(get, product_id: int, since_ms: float, known_ids: set[str] | frozenset = frozenset(),
                max_pages: int = 500) -> list[dict]:
    """New fills for one product, newest first: pages until one reaches back past `since_ms` or holds a fill
    already in `known_ids` (the cache). Raises rather than return a silently truncated history."""
    rows: list[dict] = []
    after = None
    for _ in range(max_pages):
        query = f"product_ids={product_id}&page_size=100" + (f"&after={urllib.parse.quote(after, safe='')}" if after else "")
        body = get("/v2/fills", query)
        if body.get("success") is not True:
            raise RuntimeError(f"Delta /v2/fills failed: {error_code(body)}")
        page = body.get("result") or []
        rows.extend(r for r in page if str(r.get("id")) not in known_ids)
        after = (body.get("meta") or {}).get("after")
        oldest = min((parse_iso_ms(r["created_at"]) for r in page if r.get("created_at")), default=None)
        if (not after or not page or (oldest is not None and oldest < since_ms)
                or any(str(r.get("id")) in known_ids for r in page)):
            return rows
        time.sleep(0.2)
    raise FillsIncomplete(f"Delta /v2/fills: {max_pages} pages did not reach back to the live run's start; "
                          "rerun (fills.json keeps what was fetched) or raise --max-pages", rows)


def merge_fills(cached: list[dict], new: list[dict]) -> list[dict]:
    """Cached and new fill rows, one per id, newest first."""
    by_id = {str(r.get("id")): r for r in cached}
    by_id.update({str(r.get("id")): r for r in new})
    return sorted(by_id.values(), key=lambda r: r.get("created_at") or "", reverse=True)


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
                f.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
            tail = f.read().splitlines()
        for line in reversed(tail):
            if needle in line and "MM_METRICS" in line and (m := metrics_json(line)) and m.get("ts_ms"):
                last = m
                break
        if not last:  # e.g. hours of stale-book warnings at the end: scan the whole file
            for line in sim.iter_lines(path):
                if needle in line and "MM_METRICS" in line and (m := metrics_json(line)) and m.get("ts_ms"):
                    last = m
        if last:
            break
    if not first or not last:
        return None
    return float(first["ts_ms"]), float(last["ts_ms"]), float(first.get("inventory") or 0.0)


def inventory_at(paths: list[str], symbol: str, t: float) -> float | None:
    """The bot's inventory (base units) at its first MM_METRICS sample at or after t."""
    needle = f'"{symbol}"'
    for path in paths:
        for line in sim.iter_lines(path):
            if needle in line and "MM_METRICS" in line and (m := metrics_json(line)) and float(m.get("ts_ms") or 0) >= t:
                return float(m.get("inventory") or 0.0)
    return None


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


def sibling_runs(live_dir: Path) -> list[Path]:
    """Other live run directories next to this one (artifacts/live/<UTC start>)."""
    me = live_dir.resolve()
    try:
        return sorted(p for p in me.parent.iterdir()
                      if p.is_dir() and not p.is_symlink() and RUN_NAME.match(p.name) and p.resolve() != me)
    except OSError:
        return []


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


def sizing(cfg: dict[str, str], symbol: str, cv: float) -> tuple[int, int]:
    """(order size in contracts, inventory cap in orders) from the live run's profile lines."""
    qty = float(cfg.get(f"MM_ORDER_QTY_{symbol}") or cfg.get("MM_ORDER_QTY") or 0)
    cap = float(cfg.get(f"MM_MAX_INVENTORY_{symbol}") or cfg.get("MM_MAX_INVENTORY") or 0)
    if qty <= 0 or cap <= 0:
        raise SystemExit(f"the live run's config.txt has no MM_ORDER_QTY_{symbol} / MM_MAX_INVENTORY_{symbol}")
    contracts = max(1, round(qty / cv))
    return contracts, max(1, round(cap / qty))


# A Binance mid unchanged this long is a frozen feed. Healthy ADA feed, 6-8 Oct 2026: longest unchanged 275 s (one
# tick is about 4 bps). The 8-12 Oct freeze: 3.5 days.
BINANCE_STALE_MS = 900_000.0


def fresh_binance(samples: list[sim.Sample]) -> list[tuple[float, float]]:
    """(ts, binance_mid) of samples whose Binance mid changed within BINANCE_STALE_MS. The first sample counts as a
    change, so a freeze that began before the samples passes for up to BINANCE_STALE_MS."""
    out, last_px, changed_at = [], None, 0.0
    for s in samples:
        if s.binance_mid <= 0:
            continue
        if s.binance_mid != last_px:
            last_px, changed_at = s.binance_mid, s.ts
        if s.ts - changed_at <= BINANCE_STALE_MS:
            out.append((s.ts, s.binance_mid))
    return out


class RefSeries:
    """Binance mid from MM_METRICS (binance_mid), with MidSeries' contract: the last value at or before t, or
    None if it is older than 5 s or frozen. Our Delta orders cannot move it."""

    def __init__(self, samples: list[sim.Sample]):
        pts = fresh_binance(samples)
        self.ts = [t for t, _ in pts]
        self.px = [p for _, p in pts]

    def at(self, t: float) -> float | None:
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0 or t - self.ts[i] > 5_000:
            return None
        return self.px[i]


def basis_bps(samples: list[sim.Sample]) -> float | None:
    """Median Delta mid over Binance mid, in bps, over samples with a fresh Binance mid."""
    fresh = {t for t, _ in fresh_binance(samples)}
    vals = [((s.book_bid + s.book_ask) / 2 / s.binance_mid - 1) * 1e4 for s in samples if s.ts in fresh]
    return float(statistics.median(vals)) if vals else None


def ref_metrics(fills: list[sim.Fill], ref: RefSeries, basis: float | None) -> dict:
    """Capture, markouts and net against the Binance reference (Delta-equivalent via the basis)."""
    rows = []
    for f in fills:
        b0 = ref.at(f.ts)
        if b0 is None:
            continue
        mo = {}
        for h in sim.HORIZONS:
            b = ref.at(f.ts + h * 1000)
            if b is None:
                break
            mo[h] = f.side * (b - b0) / b0 * 1e4
        else:
            rows.append((f, mo))
    w = sum(f.notional for f, _ in rows)
    wavg = (lambda fn: sum(fn(f, mo) * f.notional for f, mo in rows) / w) if w else (lambda fn: None)
    fee = wavg(lambda f, mo: f.fee / f.notional * 1e4)
    out = {"bscored": len(rows), "bmo": {h: wavg(lambda f, mo, h=h: mo[h]) for h in sim.HORIZONS},
           "bcapture": None, "bnet60": None, "bnet300": None}
    if w and basis is not None:
        cap = wavg(lambda f, mo: f.side * (f.mid_ref - f.price) / f.price * 1e4)
        out.update(bcapture=cap, bnet60=cap + out["bmo"][60] - fee, bnet300=cap + out["bmo"][300] - fee)
    return out


def with_ref(fills: list[sim.Fill], ref: RefSeries, basis: float | None) -> list[sim.Fill]:
    """Tag each fill with its Delta-equivalent Binance reference price at fill time (mid_ref)."""
    for f in fills:
        b0 = ref.at(f.ts)
        f.mid_ref = b0 * (1 + basis / 1e4) if (b0 is not None and basis is not None) else float("nan")
    return fills


def row(s: dict, ref: dict, extra: dict | None = None) -> dict:
    keep = ["fills", "scored", "days", "fills_per_day", "usd_per_day", "uptime", "inside", "capture", "fee", "net60",
            "net300", "pnl_total", "pnl_spread", "pnl_inventory", "pnl_fees", "final_inv"]
    out = {k: s[k] for k in keep}
    out.update({f"mo{h}": s["mo"][h] for h in sim.HORIZONS})
    out.update({"bscored": ref["bscored"], "bcapture": ref["bcapture"], "bnet60": ref["bnet60"],
                "bnet300": ref["bnet300"]})
    out.update({f"bmo{h}": ref["bmo"][h] for h in sim.HORIZONS})
    traded = s["usd_per_day"] * s["days"]
    out["pnl_bps"] = s["pnl_total"] / traded * 1e4 if traded > 0 else None
    if extra:
        out.update(extra)
    return out


def compare(live_dir: Path, shadow_dirs: list[Path], fill_rows: list[dict], latencies: list[float], tick: float,
            cv: float, symbol: str | None = None, since_ms: float = 0.0, heartbeat_ms: float = 0.0,
            baseline_ms: float | None = None, fills_until_ms: float | None = None) -> dict:
    """Real fills over the live run's window (from since_ms on, if later) and the simulator on the shadow just
    before the live run. No network: fills and the product's tick and contract value are passed in."""
    cfg = read_config(live_dir)
    symbol = symbol or (cfg.get("MM_SYMBOLS") or cfg.get("symbols") or "ADAUSDT").split(",")[0]
    dsym = sim.delta_symbol(symbol)
    live_logs = sorted(glob.glob(str(live_dir / "bot*.log*")))
    span_info = live_span(live_logs, symbol)
    if not span_info:
        raise SystemExit(f"no MM_METRICS samples for {symbol} in {live_dir}")
    run_start = span_info[0]
    live = load_samples(live_logs, symbol, since_ms, float("inf"), heartbeat_ms)
    if fills_until_ms is not None:
        live = [s for s in live if s.ts <= fills_until_ms]
    if len(live) < 2:
        raise SystemExit(f"no MM_METRICS samples for {symbol} in {live_dir} in the window")
    t0, t1 = live[0].ts, live[-1].ts
    last_live_mid = (live[-1].book_bid + live[-1].book_ask) / 2
    metric_paths = [p for d in shadow_dirs for p in sorted(glob.glob(str(d / "dry-run*.log*")))]
    trade_paths = [p for d in shadow_dirs for p in sorted(glob.glob(str(d / "delta_mainnet_public_*.jsonl")))]

    # Real fills, against the shadow's mids over the window (+300 s for markouts, + late fills after the last sample).
    win = load_samples(metric_paths, symbol, t0 - 5000, t1 + LATE_FILL_MS + 310_000, heartbeat_ms)
    if len([s for s in win if t0 <= s.ts <= t1]) < 2:
        raise SystemExit(f"the shadow runs {[d.name for d in shadow_dirs]} have no {symbol} samples in the live window")
    mids, ref = sim.MidSeries(win), RefSeries(win)
    offset = clock_offset_ms(trade_paths, dsym, t0, t1)

    # Baseline: the shadow just before the live run, ending BASELINE_GAP_MS early so its markouts are clean. Only
    # the shadow run live.sh checked at start (same binary), and never while another live run was quoting.
    b1 = run_start - BASELINE_GAP_MS
    length = baseline_ms if baseline_ms is not None else min(max(t1 - t0, MIN_BASELINE_MS), MAX_BASELINE_MS)
    b0 = b1 - length
    for other in sibling_runs(live_dir):
        span_o = live_span(sorted(glob.glob(str(other / "bot*.log*"))), symbol)
        if span_o and span_o[0] < b1 and span_o[1] + DMS_MS + BASELINE_GAP_MS > b0:
            b0 = max(b0, span_o[1] + DMS_MS + BASELINE_GAP_MS)
    base_dirs = [d for d in shadow_dirs if d.name == cfg.get("shadow_run")] or shadow_dirs
    base_paths = [p for d in base_dirs for p in sorted(glob.glob(str(d / "dry-run*.log*")))]
    base_trades = [p for d in base_dirs for p in sorted(glob.glob(str(d / "delta_mainnet_public_*.jsonl")))]
    base = load_samples(base_paths, symbol, b0 - 5000, b1 + 310_000, heartbeat_ms) if b1 > b0 else []
    base_q = [s for s in base if b0 <= s.ts <= b1]
    basis = basis_bps(base_q)

    accounting = {"total": 0, "used": 0, "before_window": 0, "after_window": 0, "no_mid": 0, "unparsed": 0,
                  "other_types": {}}
    real: list[RealFill] = []
    for r in fill_rows:
        if r.get("product_symbol") != dsym:
            continue
        f = parse_fill(r, cv)
        if not f:
            accounting["unparsed"] += 1
            continue
        accounting["total"] += 1
        if f.fill_type != "normal":
            accounting["other_types"][f.fill_type] = accounting["other_types"].get(f.fill_type, 0) + 1
            continue
        local = f.ts + offset
        if local < t0:
            accounting["before_window"] += 1
        elif local > t1 + LATE_FILL_MS:
            accounting["after_window"] += 1
        else:
            real.append(f)
    sf = to_sim_fills(real, offset, mids, cv)
    accounting["no_mid"] = len(real) - len(sf)
    accounting["used"] = len(sf)
    with_ref(sf, ref, basis)
    quoted, _ = quote_time(live)
    res = sim.SimResult(fills=sf, quoted_ms=quoted, inside_ms=0.0, span_ms=t1 - t0,
                        final_inv=sum(f.side * f.qty for f in sf))
    maker_notional = sum(f.contracts * cv * f.price for f in real if f.maker)
    all_notional = sum(f.contracts * cv * f.price for f in real)
    rows = {"real": row(sim.summarize(res, mids, cv), ref_metrics(sf, ref, basis), {
        "maker_pct": 100.0 * maker_notional / all_notional if all_notional else 100.0,
        "taker_fills": sum(1 for f in real if not f.maker), "inside": None})}

    contracts, inv_orders = sizing(cfg, symbol, cv)
    baseline = None
    if len(base_q) >= 2 and base_q[-1].ts - base_q[0].ts >= 600_000:
        bmids, bref = sim.MidSeries(base), RefSeries(base)
        tape = load_trades(base_trades, dsym, base_q[0].ts, base_q[-1].ts)
        ref_px = base_q[len(base_q) // 2].fair
        for lat in latencies:
            c = sim.SimConfig(
                latency_ms=lat, half_spread_bps=None, rule="strict", quote_usd=contracts * cv * ref_px,
                max_inv_orders=inv_orders, fee_bps=float(cfg.get("MM_MAKER_FEE_BPS") or 2.12),
                requote_tol_bps=float(cfg.get("MM_REQUOTE_TOL_BPS") or 3.0), max_gap_ms=MAX_GAP_MS, loop_ms=400.0)
            res_b = sim.simulate(base_q, tape, tick, cv, c)
            with_ref(res_b.fills, bref, basis)
            rows[f"sim baseline {lat:g}ms"] = row(sim.summarize(res_b, bmids, cv), ref_metrics(res_b.fills, bref, basis),
                                                  {"maker_pct": 100.0, "taker_fills": 0})
        baseline = {"t0": base_q[0].ts, "t1": base_q[-1].ts, "hours": (base_q[-1].ts - base_q[0].ts) / 3.6e6,
                    "tape_trades": len(tape), "shadow_runs": [d.name for d in base_dirs]}

    # Stop rule: every real fill in the window, marked at the live bot's own last mid (no shadow needed).
    traded = sum(f.contracts * cv * f.price for f in real)
    pnl = (sum(-f.side * f.contracts * cv * f.price for f in real) - sum(f.fee for f in real)
           + sum(f.side * f.contracts for f in real) * cv * last_live_mid)
    stop = {"fills": len(real), "pnl_usd": pnl, "pnl_bps": pnl / traded * 1e4 if traded else None}

    return {
        "symbol": symbol, "live_run": live_dir.name, "shadow_runs": [d.name for d in shadow_dirs],
        "run_start": run_start,
        "window": {"t0": t0, "t1": t1, "hours": (t1 - t0) / 3.6e6, "clock_offset_ms": offset,
                   "whole_run": t0 <= run_start + 60_000},
        "baseline": baseline, "basis_bps": basis,
        "sizing": {"order_contracts": contracts, "max_inv_orders": inv_orders},
        "inventory_at_window_start": inventory_at(live_logs, symbol, t0),
        "fills": accounting,
        "stop": stop,
        "rows": rows,
    }


def stop_rule(out: dict) -> str:
    """The live stop rule on PnL per dollar traded over every real fill (see EARLY_* / FULL_FILLS)."""
    st = out["stop"]
    n, pnl = st["fills"], st["pnl_bps"]
    scope = "" if out["window"]["whole_run"] else " [this window only; the rule is on the whole run: --all]"
    if n < EARLY_FILLS:
        return f"CONTINUE ({n}/{EARLY_FILLS} real fills){scope}"
    limit = 0.0 if n >= FULL_FILLS else EARLY_BPS
    head = "STOP" if pnl < limit else "OK"
    rel = "<" if pnl < limit else ">="
    return f"{head}: real PnL {pnl:+.2f} bps per $ traded over {n} fills ({rel} {limit:+.1f} bps after " \
           f"{FULL_FILLS if n >= FULL_FILLS else EARLY_FILLS} fills){scope}"


def fmt(v, spec: str, width: int) -> str:
    return f"{'-':>{width}s}" if v is None else format(v, spec)


def format_table(out: dict) -> str:
    w = out["window"]
    iso = lambda ms: dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")  # noqa: E731
    lines = [
        f"=== {out['symbol']} live run {out['live_run']} vs shadow {', '.join(out['shadow_runs'])}",
        f"window {iso(w['t0'])} -> {iso(w['t1'])} ({w['hours']:.2f} h{', whole run' if w['whole_run'] else ''}), "
        f"fill clock shift {w['clock_offset_ms']:+.0f} ms; quotes {out['sizing']['order_contracts']} contracts, "
        f"cap {out['sizing']['max_inv_orders']} quotes",
    ]
    b = out["baseline"]
    if b:
        lines.append(f"baseline (shadow {', '.join(b['shadow_runs'])} before the live start) {iso(b['t0'])} -> "
                     f"{iso(b['t1'])} ({b['hours']:.2f} h, {b['tape_trades']} trades); Delta-Binance basis "
                     + (f"{out['basis_bps']:+.2f} bps" if out["basis_bps"] is not None else "unknown (no Binance mid)"))
    else:
        lines.append("no baseline: under 10 min of shadow data before the live start (same shadow run, no other live "
                     "run quoting)")
    head = (f"{'row':20s} {'fills':>6s} {'/day':>6s} {'$/day':>8s} {'mkr%':>5s} {'up%':>5s} {'capt':>6s} "
            + " ".join(f"{f'mo{h}':>6s}" for h in sim.HORIZONS)
            + f" {'fee':>5s} {'net60':>6s} {'net300':>6s} | {'bcapt':>6s} {'bmo60':>6s} {'bnet60':>6s} {'bnet300':>7s}"
            f" | {'PnL$':>7s} {'PnLbp':>6s} {'spr$':>7s} {'inv$':>7s} {'fee$':>7s}")
    lines.append(head)
    for label, r in out["rows"].items():
        name = "real (Delta fills)" if label == "real" else label
        lines.append(
            f"{name:20s} {r['fills']:6d} {r['fills_per_day']:6.0f} {r['usd_per_day']:8,.0f} {r['maker_pct']:5.0f} "
            f"{r['uptime']:5.0%} {r['capture']:6.2f} "
            + " ".join(f"{r[f'mo{h}']:6.2f}" for h in sim.HORIZONS)
            + f" {r['fee']:5.2f} {r['net60']:6.2f} {r['net300']:6.2f} | {fmt(r['bcapture'], '6.2f', 6)} "
            f"{fmt(r['bmo60'], '6.2f', 6)} {fmt(r['bnet60'], '6.2f', 6)} {fmt(r['bnet300'], '7.2f', 7)}"
            f" | {r['pnl_total']:7.2f} {fmt(r['pnl_bps'], '6.2f', 6)} {r['pnl_spread']:7.2f} {r['pnl_inventory']:7.2f}"
            f" {r['pnl_fees']:7.2f}")
    real = out["rows"]["real"]
    lines.append("The real row's capt/mo/net60 use the Delta mid, which is mostly our own quotes while we quote: "
                 "compare real and sim on the b* columns and PnLbp.")
    if out["basis_bps"] is None:
        lines.append("no fresh Binance mid in the shadow log (missing or frozen): the b* columns are unavailable")
    for label, r in out["rows"].items():
        if label.startswith("sim") and r["fills_per_day"]:
            lines.append(f"real fills/day / {label} fills/day: {real['fills_per_day'] / r['fills_per_day']:.2f}")
    a = out["fills"]
    lines.append(f"real fills: {a['used']} scored of {a['total']} ({a['before_window']} before the window, "
                 f"{a['after_window']} after it, {a['no_mid']} without a shadow mid, {a['unparsed']} unparsable)"
                 + "".join(f", {n} {t} fill(s) excluded" for t, n in a["other_types"].items()))
    if real["taker_fills"]:
        lines.append(f"! {real['taker_fills']} real taker fill(s): quotes are post-only, so only a reduce-only exit takes")
    if out.get("inventory_at_window_start"):
        lines.append(f"inventory at the window start: {out['inventory_at_window_start']:g} {out['symbol'][:-4]} "
                     "(PnL$ covers the window's trades only, not that position's mark-to-market)")
    lines.append(f"live stop rule: {stop_rule(out)}")
    lines.append("Fills are scored once their 300 s markouts exist. The shadow dashboard's simulator runs on the live "
                 "window and is NOT an independent prediction while the live bot quotes.")
    return "\n".join(lines)


# ---------------------------------------------------------------- venue

def venue_text(get, product_id: int, symbol: str) -> str:
    """Account equity, the product's position and its open orders (read-only)."""
    return venue_report(get, product_id, symbol)[0]


def venue_report(get, product_id: int, symbol: str) -> tuple[str, int | None]:
    """(text, number of open orders or None if they could not be read)."""
    lines = []
    open_orders = None
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
        open_orders = len(rows)
        lines.append(f"venue: open orders {len(rows)}")
        for o in rows:
            lines.append(f"  {o.get('side')} {o.get('size')} @ {o.get('limit_price')} ({o.get('state')})")
    return "\n".join(lines), open_orders


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
    ap.add_argument("--baseline-hours", type=float,
                    help="length of the pre-live shadow baseline (default: the window's length within 1-24 h; 0 = none)")
    ap.add_argument("--max-pages", type=int, default=500, help="most /v2/fills pages to fetch in one report")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-no-orders", action="store_true", help="venue: exit 3 unless the product has no open orders")
    args = ap.parse_args(argv)

    live_dir = args.live_dir.resolve()
    cfg = read_config(live_dir)
    symbol = args.symbol or (cfg.get("MM_SYMBOLS") or "ADAUSDT").split(",")[0]
    dsym = sim.delta_symbol(symbol)
    if venue_mode:
        pid, _, _ = product(dsym)
        text, open_orders = venue_report(Delta(args.env_file).get, pid, dsym)
        print(text)
        if args.require_no_orders and open_orders != 0:
            sys.exit(3)
        return

    span = live_span(sorted(glob.glob(str(live_dir / "bot*.log*"))), symbol)
    if not span:
        raise SystemExit(f"no MM_METRICS samples for {symbol} in {live_dir}")
    tick, cv = sim.product_meta(dsym)
    fills_path = live_dir / "fills.json"
    cached = json.loads(fills_path.read_text()) if fills_path.exists() else []
    fills_until = None
    if args.offline:
        if not fills_path.exists():
            raise SystemExit(f"--offline: no {fills_path} yet; run once without --offline")
        rows = cached
        fills_until = fills_path.stat().st_mtime * 1000
        print(f"offline: fills.json is {(time.time() * 1000 - fills_until) / 60_000:.0f} min old; the window "
              "ends there", file=sys.stderr)
    else:
        pid, _, _ = product(dsym)
        try:
            new = fetch_fills(Delta(args.env_file).get, pid, span[0] - 120_000, {str(r.get("id")) for r in cached},
                              args.max_pages)
        except FillsIncomplete as e:
            fills_path.write_text(json.dumps(merge_fills(cached, e.rows)))
            raise SystemExit(str(e))
        rows = merge_fills(cached, new)
        fills_path.write_text(json.dumps(rows))
    end = min(span[1], fills_until) if fills_until is not None else span[1]
    since = end - args.hours * 3.6e6 if args.hours else 0.0
    if (span[1] - max(since, span[0])) > 72 * 3.6e6 and not args.compact:
        print("warning: a window over 72 h at full resolution needs about 150 MB of RAM per day; consider --hours or "
              "--compact", file=sys.stderr)
    shadow_dirs = [d.resolve() for d in args.shadow_dir] if args.shadow_dir else None
    if not shadow_dirs:
        base_len = args.baseline_hours * 3.6e6 if args.baseline_hours is not None else MAX_BASELINE_MS
        shadow_dirs = shadow_runs_for(CEX_MM / "artifacts" / "shadow", span[0] - BASELINE_GAP_MS - base_len, span[1])
    out = compare(live_dir, shadow_dirs, rows, [float(x) for x in args.latencies.split(",")], tick, cv, symbol,
                  since_ms=since, heartbeat_ms=COMPACT_MS if args.compact else 0.0,
                  baseline_ms=args.baseline_hours * 3.6e6 if args.baseline_hours is not None else None,
                  fills_until_ms=fills_until)
    print(json.dumps(out, indent=1) if args.json else format_table(out))


if __name__ == "__main__":
    main()
