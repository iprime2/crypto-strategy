#!/usr/bin/env python3
"""MM bot fill-rate / markout dashboard — reads MM_METRICS + fill lines from bot logs."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path as _Path

_SCRIPT_DIR = _Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from mm_markout import parse_markout_samples, summarize_markout_samples  # noqa: E402
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["BTC-USDC-PERP", "ETH-USDC-PERP", "SOL-USDC-PERP"]
ARTIFACTS_ROOT = Path.home() / "scripts" / "mms" / "artifacts"
DEFAULT_ARTIFACTS = Path(
    os.environ.get("MM_ARTIFACTS_DIR", ARTIFACTS_ROOT)
)
CHART_POINTS = int(os.environ.get("MM_DASHBOARD_CHART_POINTS", "80"))
METRICS_TAIL = int(os.environ.get("MM_DASHBOARD_METRICS_TAIL", "0"))
MAX_LOG_BYTES = int(os.environ.get("MM_DASHBOARD_MAX_LOG_BYTES", str(32 * 1024 * 1024)))
BUCKET_SEC = int(os.environ.get("MM_DASHBOARD_BUCKET_SEC", "60"))
INCLUDE_ARCHIVED = os.environ.get("MM_DASHBOARD_INCLUDE_ARCHIVED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)

METRICS_RE = re.compile(r"MM_METRICS (\{.*\})")
LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:\.]+Z)")
FILL_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T[\d:.]+Z).*fill detected inv ([-\d.]+) -> ([-\d.]+)"
)

STACK_DIRS: list[tuple[str, Path]] = [
    ("testnet", ARTIFACTS_ROOT),
    ("devnet", ARTIFACTS_ROOT / "devnet"),
]


def slug(symbol: str) -> str:
    return symbol.split("-")[0]


def log_path(symbol: str, artifacts: Path) -> Path:
    return artifacts / f"mm-bot-{slug(symbol)}.log"


def discover_metric_log_paths(symbol: str, artifacts: Path, *, include_archived: bool) -> list[Path]:
    """Active log plus archived run logs (chronological) for long-range charts."""
    sym_slug = slug(symbol)
    paths: list[Path] = []
    active = log_path(symbol, artifacts)
    if not include_archived:
        return [active] if active.exists() else []
    runs_dir = artifacts / "runs"
    if runs_dir.is_dir():
        for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            archived = run_dir / f"mm-bot-{sym_slug}.log"
            if archived.is_file():
                paths.append(archived)
    if active.is_file():
        paths.append(active)
    return paths


def parse_metrics_merged(paths: list[Path], symbol: str, tail: int = METRICS_TAIL) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        rows.extend(parse_metrics(path, symbol, tail=tail))
    if len(paths) <= 1:
        return rows
    rows.sort(key=lambda r: (int(r.get("ts_ms") or 0), int(r.get("loop") or 0)))
    seen: set[tuple[int | None, int | None]] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row.get("ts_ms"), row.get("loop"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _float_metric(row: dict, key: str, default: float = 0.0) -> float:
    v = row.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _optional_float(row: dict, key: str) -> float | None:
    v = row.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_ts_ms(iso: str) -> int | None:
    try:
        s = iso.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def iter_log_lines(path: Path, tail: int) -> list[str]:
    if not path.exists():
        return []
    if tail > 0:
        return path.read_text(errors="replace").splitlines()[-tail:]
    raw = path.read_bytes()
    if len(raw) > MAX_LOG_BYTES:
        raw = raw[-MAX_LOG_BYTES:]
    return raw.decode(errors="replace").splitlines()


def parse_metrics(path: Path, symbol: str, tail: int = METRICS_TAIL) -> list[dict]:
    rows: list[dict] = []
    for line in iter_log_lines(path, tail):
        m = METRICS_RE.search(line)
        if not m:
            continue
        try:
            row = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if row.get("symbol") != symbol:
            continue
        ts_m = LOG_TS_RE.match(line)
        if ts_m:
            ts_ms = parse_ts_ms(ts_m.group(1))
            if ts_ms is not None:
                row["ts_ms"] = ts_ms
        rows.append(row)
    return rows


def parse_markouts(path: Path, tail: int = 8000) -> list[dict]:
    return parse_markout_samples(path, tail_lines=tail)


def parse_fills(path: Path, tail: int = 5000) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(errors="replace").splitlines()[-tail:]:
        m = FILL_RE.search(line)
        if m:
            out.append(
                {
                    "ts": m.group(1),
                    "inv_from": float(m.group(2)),
                    "inv_to": float(m.group(3)),
                }
            )
    return out


def summarize_markouts(samples: list[dict]) -> dict:
    return summarize_markout_samples(samples)


def timeseries_from_metrics(
    metrics: list[dict],
    key: str,
    *,
    row_key: str | None = None,
) -> list[dict]:
    """Points {t: ms, v: float} with log timestamps."""
    src_key = row_key or key
    out: list[dict] = []
    for row in metrics:
        ts_ms = row.get("ts_ms")
        if ts_ms is None:
            continue
        if src_key == "unrealized_pnl":
            v = _optional_float(row, src_key)
            if v is None:
                v = 0.0
        else:
            v = _float_metric(row, src_key, 0.0)
        out.append({"t": int(ts_ms), "v": v})
    return out


def bucket_ms(ts_ms: int, bucket_sec: int = BUCKET_SEC) -> int:
    step = max(bucket_sec, 1) * 1000
    return (ts_ms // step) * step


def portfolio_timeseries(reports: list[dict], field: str) -> list[dict]:
    """Sum BTC+ETH+SOL using per-minute buckets (forward-filled per symbol)."""
    buckets: dict[int, dict[str, float]] = defaultdict(dict)
    for rep in reports:
        slug = rep["slug"]
        for pt in rep.get("timeseries", {}).get(field, []):
            bt = bucket_ms(int(pt["t"]))
            buckets[bt][slug] = float(pt["v"])
    if not buckets:
        return []
    last: dict[str, float] = {}
    out: list[dict] = []
    for t in sorted(buckets.keys()):
        last.update(buckets[t])
        out.append({"t": t, "v": sum(last.values())})
    return out


def stack_timeseries_embed(stack_data: dict) -> dict:
    symbols: dict[str, dict] = {}
    for sym in stack_data.get("symbols", []):
        symbols[sym["slug"]] = sym.get("timeseries") or {}
    return {
        "portfolio": (stack_data.get("portfolio") or {}).get("timeseries") or {},
        "symbols": symbols,
    }


def series_from_metrics(metrics: list[dict], key: str, last_n: int = CHART_POINTS) -> list[float]:
    window = metrics[-last_n:] if metrics else []
    out: list[float] = []
    for row in window:
        if key == "unrealized_pnl":
            v = _optional_float(row, key)
            out.append(0.0 if v is None else v)
        else:
            out.append(_float_metric(row, key, 0.0))
    return out


def portfolio_sum_series(reports: list[dict], key: str) -> list[float]:
    """Sum per-symbol series point-wise (last N loops, not time-synced across hosts)."""
    series_list = [sym.get("series", {}).get(key, []) for sym in reports]
    series_list = [s for s in series_list if s]
    if not series_list:
        return []
    n = min(len(s) for s in series_list)
    totals: list[float] = []
    for i in range(n):
        totals.append(sum(s[-n + i] for s in series_list))
    return totals


def build_symbol_report(symbol: str, artifacts: Path) -> dict:
    paths = discover_metric_log_paths(symbol, artifacts, include_archived=INCLUDE_ARCHIVED)
    path = log_path(symbol, artifacts)
    metrics = parse_metrics_merged(paths, symbol) if paths else []
    markout_paths = paths if paths else ([path] if path.exists() else [])
    markouts: list[dict] = []
    for mp in markout_paths:
        markouts.extend(parse_markouts(mp))
    markouts.sort(key=lambda s: s.get("ts", ""))
    fills = parse_fills(path)
    last = metrics[-1] if metrics else {}
    recent = metrics[-30:] if metrics else []
    chart_n = CHART_POINTS

    fill_rate_per_hour = None
    if len(recent) >= 2:
        loops = max(1, recent[-1].get("loop", 0) - recent[0].get("loop", 0))
        loop_sec = 15.0
        hours = (loops * loop_sec) / 3600.0
        if hours > 0:
            fill_delta = len(fills)
            fill_rate_per_hour = fill_delta / max(hours, 0.01)

    spreads = [float(r.get("spread_bps", 0)) for r in recent]
    vols = [float(r.get("vol_bps", 0)) for r in recent]

    upl = series_from_metrics(metrics, "unrealized_pnl", chart_n)
    realized = series_from_metrics(metrics, "realized_pnl_usdc", chart_n)
    net = series_from_metrics(metrics, "net_realized_pnl_usdc", chart_n)
    fees = series_from_metrics(metrics, "fees_usdc", chart_n)

    ts = {
        "unrealized_pnl_usdc": timeseries_from_metrics(
            metrics, "unrealized_pnl_usdc", row_key="unrealized_pnl"
        ),
        "realized_pnl_usdc": timeseries_from_metrics(metrics, "realized_pnl_usdc"),
        "net_realized_pnl_usdc": timeseries_from_metrics(metrics, "net_realized_pnl_usdc"),
        "fees_usdc": timeseries_from_metrics(metrics, "fees_usdc"),
        "spread_bps": timeseries_from_metrics(metrics, "spread_bps"),
        "inventory": timeseries_from_metrics(metrics, "inventory"),
        "markout_extra_bps": timeseries_from_metrics(metrics, "markout_extra_bps"),
    }

    return {
        "symbol": symbol,
        "slug": slug(symbol),
        "last_metric": last,
        "metrics_window": len(recent),
        "metrics_total": len(metrics),
        "avg_spread_bps": sum(spreads) / len(spreads) if spreads else None,
        "avg_vol_bps": sum(vols) / len(vols) if vols else None,
        "markout": summarize_markouts(markouts[-50:]),
        "fills_recent": len(fills),
        "fill_rate_per_hour_est": fill_rate_per_hour,
        "series": {
            "spread_bps": series_from_metrics(metrics, "spread_bps", 20),
            "vol_bps": vols[-20:],
            "inventory": series_from_metrics(metrics, "inventory", 20),
            "markout_extra_bps": series_from_metrics(metrics, "markout_extra_bps", 20),
            "unrealized_pnl_usdc": upl,
            "realized_pnl_usdc": realized,
            "net_realized_pnl_usdc": net,
            "fees_usdc": fees,
        },
        "timeseries": ts,
    }


def build_stack_payload(stack: str, artifacts: Path) -> dict:
    symbols = [build_symbol_report(s, artifacts) for s in SYMBOLS]
    last_metrics = [s.get("last_metric") or {} for s in symbols]
    portfolio = {
        "unrealized_pnl_usdc": sum(
            _optional_float(m, "unrealized_pnl") or 0.0 for m in last_metrics
        ),
        "realized_pnl_usdc": sum(_float_metric(m, "realized_pnl_usdc") for m in last_metrics),
        "net_realized_pnl_usdc": sum(
            _float_metric(m, "net_realized_pnl_usdc") for m in last_metrics
        ),
        "fees_usdc": sum(_float_metric(m, "fees_usdc") for m in last_metrics),
        "series": {
            "unrealized_pnl_usdc": portfolio_sum_series(symbols, "unrealized_pnl_usdc"),
            "realized_pnl_usdc": portfolio_sum_series(symbols, "realized_pnl_usdc"),
            "net_realized_pnl_usdc": portfolio_sum_series(symbols, "net_realized_pnl_usdc"),
        },
        "timeseries": {
            "unrealized_pnl_usdc": portfolio_timeseries(symbols, "unrealized_pnl_usdc"),
            "realized_pnl_usdc": portfolio_timeseries(symbols, "realized_pnl_usdc"),
            "net_realized_pnl_usdc": portfolio_timeseries(symbols, "net_realized_pnl_usdc"),
            "fees_usdc": portfolio_timeseries(symbols, "fees_usdc"),
        },
    }
    return {
        "stack": stack,
        "artifacts_dir": str(artifacts),
        "symbols": symbols,
        "portfolio": portfolio,
    }


def build_payload(artifacts: Path | None = None, stack: str = "testnet") -> dict:
    """Single-stack payload (backward compatible with dashboard-latest.json consumers)."""
    art = artifacts or DEFAULT_ARTIFACTS
    payload = build_stack_payload(stack, art)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def build_combined_payload() -> dict:
    stacks = []
    for name, path in STACK_DIRS:
        if path.is_dir() or any(log_path(s, path).exists() for s in SYMBOLS):
            stacks.append(build_stack_payload(name, path))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stacks": stacks,
    }


METRIC_HELP: dict[str, str] = {
    "fair": "Reference mid-price the bot centers quotes on. Usually a blend of GoDark oracle and Hyperliquid/Binance book.",
    "source": "Where fair price comes from: blended (oracle + external book), oracle, orderbook_mid, or fallback.",
    "bid": "Current resting buy limit price the bot is quoting.",
    "ask": "Current resting sell limit price the bot is quoting.",
    "spread": "Distance between bid and ask in basis points (1 bps = 0.01%). Wider = more profit per round-trip, fewer fills.",
    "vol": "Realized short-term volatility of fair price. High vol widens spreads automatically.",
    "inventory": "Net position size (+ long, − short). Bot skews quotes to flatten inventory toward zero.",
    "order_qty": "Size of each bid/ask clip. Auto-scales up when markout is consistently positive.",
    "fills": "Total fill events detected since bot start. Each inventory change counts as one fill.",
    "markout_guard": "Extra spread added after adverse fills. Decays over time when price stops moving against you.",
    "avg_markout": "Average signed 30s markout from MM_MARKOUT_HORIZON logs. Positive = favorable; negative = adverse selection.",
    "side_markout": "30s markout split: buys vs sells. Toxic SOL often shows very negative buy leg while sells look fine.",
    "positive_markout": "Share of recent fills with positive markout. Higher is better for MM profitability.",
    "loop": "Quote loop counter (~every 15s). Bot refreshes fair, spread, and resting orders each loop.",
    "unrealized_pnl": "Mark-to-market PnL on open position from bot metrics (venue uPnL). Flat when flat.",
    "realized_pnl": "Bot-estimated realized PnL from fill economics (round-trip attribution).",
    "net_realized": "Realized minus estimated maker fees (bot-local, may differ from FE settlement).",
    "fees": "Cumulative estimated maker fees tracked by the bot process.",
    "chart_spread": "Spread (bps) over the last 20 quote loops.",
    "chart_inventory": "Inventory level over the last 20 quote loops.",
    "chart_markout": "Markout guard extra spread (bps) over the last 20 loops.",
    "chart_upl": "Unrealized PnL (USDC) vs time from MM_METRICS log timestamps.",
    "chart_realized": "Realized PnL from bot fill economics vs time.",
    "chart_net_realized": "Net realized (realized − fees) vs time.",
    "chart_range": "Filter all charts in this tab: 1D, 1W, 1M, or custom from/to (local time).",
    "portfolio_upl": "Sum of BTC+ETH+SOL unrealized PnL (last sample per symbol).",
    "portfolio_net": "Sum of net realized across the three bot processes.",
}


def sparkline(
    values: list[float],
    width: int = 160,
    height: int = 36,
    color: str = "#60a5fa",
    *,
    include_zero: bool = False,
) -> str:
    if not values:
        return '<span class="spark-empty">No data yet</span>'
    lo = min(values)
    hi = max(values)
    if include_zero:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)
    span = hi - lo or 1.0
    pts = []
    n = len(values)
    for i, v in enumerate(values):
        x = (i / max(n - 1, 1)) * width
        y = height - ((v - lo) / span) * (height - 6) - 3
        pts.append(f"{x:.1f},{y:.1f}")
    zero_line = ""
    if include_zero and lo < 0 < hi:
        y0 = height - ((0.0 - lo) / span) * (height - 6) - 3
        zero_line = (
            f'<line x1="0" y1="{y0:.1f}" x2="{width}" y2="{y0:.1f}" '
            f'stroke="#4b5563" stroke-width="1" stroke-dasharray="3,3"/>'
        )
    return (
        f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"{zero_line}"
        f'<polyline fill="none" stroke="{color}" stroke-width="1.75" points="{" ".join(pts)}"/>'
        f"</svg>"
    )


def tip(key: str) -> str:
    text = html.escape(METRIC_HELP.get(key, ""))
    return (
        f'<span class="info" tabindex="0" aria-label="Help">'
        f'<span class="info-icon">i</span>'
        f'<span class="tip">{text}</span></span>'
    )


def metric_cell(key: str, label: str, value: str, val_class: str = "") -> str:
    cls = f"val {val_class}".strip()
    return (
        f'<div class="metric">'
        f'<div class="label-row"><span class="label">{html.escape(label)}</span>{tip(key)}</div>'
        f'<span class="{cls}">{value}</span></div>'
    )


def chart_cell(key: str, label: str, svg: str) -> str:
    return (
        f'<div class="chart-box">'
        f'<div class="label-row"><span class="label">{html.escape(label)}</span>{tip(key)}</div>'
        f"{svg}</div>"
    )


def chart_time_cell(key: str, label: str, series_path: str, color: str, *, zero_line: bool = False) -> str:
    z = "1" if zero_line else "0"
    return (
        f'<div class="chart-box chart-box-wide">'
        f'<div class="label-row"><span class="label">{html.escape(label)}</span>{tip(key)}</div>'
        f'<canvas class="time-chart" data-series-path="{html.escape(series_path)}" '
        f'data-color="{html.escape(color)}" data-zero-line="{z}"></canvas>'
        f"</div>"
    )


def render_range_bar() -> str:
    return f"""
            <div class="range-bar">
              <span class="range-label">Chart range {tip("chart_range")}</span>
              <button type="button" class="range-btn active" data-range="1d">1D</button>
              <button type="button" class="range-btn" data-range="1w">1W</button>
              <button type="button" class="range-btn" data-range="1m">1M</button>
              <button type="button" class="range-btn" data-range="custom">Custom</button>
              <div class="range-custom" hidden>
                <input class="range-from" type="datetime-local" aria-label="From"/>
                <span class="range-sep">→</span>
                <input class="range-to" type="datetime-local" aria-label="To"/>
              </div>
            </div>
            """


def fmt_num(v, digits: int = 4) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_usd(v) -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
        return f"${x:+,.2f}"
    except (TypeError, ValueError):
        return str(v)


def pnl_class(v) -> str:
    if v is None:
        return ""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    if x > 0.005:
        return "good"
    if x < -0.005:
        return "bad"
    return "neutral"


def markout_class(avg: float | None) -> str:
    if avg is None:
        return ""
    if avg > 0.5:
        return "good"
    if avg < -0.5:
        return "bad"
    return "neutral"


def render_symbol_card(sym: dict, stack_id: str) -> str:
    m = sym.get("last_metric") or {}
    mk = sym["markout"]
    avg_mk = mk.get("avg_bps")
    avg_mk_s = f"{avg_mk:+.2f} bps" if avg_mk is not None else "—"
    buy_mk = mk.get("buy_avg_bps")
    sell_mk = mk.get("sell_avg_bps")
    side_mk_s = "—"
    if buy_mk is not None or sell_mk is not None:
        b = f"{buy_mk:+.1f}" if buy_mk is not None else "—"
        s = f"{sell_mk:+.1f}" if sell_mk is not None else "—"
        side_mk_s = f"buy {b} / sell {s} bps (30s)"
    pct_pos = mk.get("pct_positive")
    pct_pos_s = f"{pct_pos:.0f}%" if pct_pos is not None else "—"
    inv = m.get("inventory")
    inv_f = float(inv) if inv is not None else 0.0
    inv_s = fmt_num(inv, 4)
    at_cap = m.get("at_cap", False)
    status = "At inventory cap" if at_cap else "Quoting"
    status_cls = "badge-warn" if at_cap else "badge-ok"

    fair_s = fmt_num(m.get("fair"), 2) if m.get("fair") is not None else "—"
    bid_s = fmt_num(m.get("bid"), 2) if m.get("bid") is not None else "—"
    ask_s = fmt_num(m.get("ask"), 2) if m.get("ask") is not None else "—"
    spread_s = f"{float(m['spread_bps']):.1f} bps" if m.get("spread_bps") is not None else "—"
    vol_s = f"{float(m['vol_bps']):.1f} bps" if m.get("vol_bps") is not None else "—"
    qty_s = fmt_num(m.get("order_qty"), 4) if m.get("order_qty") is not None else "—"
    guard = float(m.get("markout_extra_bps") or 0)
    guard_s = f"{guard:.1f} bps"
    guard_cls = "warn" if guard > 2 else ""

    upl_v = _optional_float(m, "unrealized_pnl")
    upl_s = fmt_usd(upl_v) if upl_v is not None else "$0.00"
    real_s = fmt_usd(m.get("realized_pnl_usdc"))
    net_s = fmt_usd(m.get("net_realized_pnl_usdc"))
    fees_s = fmt_usd(m.get("fees_usdc"))

    slug = sym["slug"]
    prefix = f"symbols.{slug}"
    metrics_html = "".join(
        [
            metric_cell("fair", "Fair price", fair_s),
            metric_cell("source", "Fair source", html.escape(str(m.get("fair_source", "—")))),
            metric_cell("bid", "Bid", bid_s, "bid"),
            metric_cell("ask", "Ask", ask_s, "ask"),
            metric_cell("spread", "Spread", spread_s),
            metric_cell("vol", "Volatility", vol_s),
            metric_cell("inventory", "Inventory", inv_s, "warn" if abs(inv_f) > 0.001 else ""),
            metric_cell(
                "inv_ratio",
                "Inv ratio",
                fmt_num(m.get("inv_ratio"), 2) if m.get("inv_ratio") is not None else "—",
            ),
            metric_cell(
                "res_skew",
                "Reservation skew",
                f"{float(m['reservation_skew_bps']):+.1f} bps"
                if m.get("reservation_skew_bps") is not None
                else "—",
            ),
            metric_cell("order_qty", "Order size", qty_s),
            metric_cell("fills", "Fills (total)", str(m.get("fill_events", 0))),
            metric_cell("unrealized_pnl", "Unrealized PnL", upl_s, pnl_class(upl_v)),
            metric_cell("realized_pnl", "Realized PnL", real_s, pnl_class(m.get("realized_pnl_usdc"))),
            metric_cell("net_realized", "Net realized (est.)", net_s, pnl_class(m.get("net_realized_pnl_usdc"))),
            metric_cell("fees", "Fees (est.)", fees_s),
            metric_cell("markout_guard", "Markout guard", guard_s, guard_cls),
            metric_cell("avg_markout", "Avg markout (30s)", avg_mk_s, markout_class(avg_mk)),
            metric_cell("side_markout", "Markout by side (30s)", side_mk_s),
            metric_cell("positive_markout", "Positive markout", pct_pos_s),
            metric_cell("loop", "Loop #", str(m.get("loop", "—"))),
        ]
    )

    charts_html = "".join(
        [
            chart_time_cell(
                "chart_upl",
                "Unrealized PnL",
                f"{prefix}.unrealized_pnl_usdc",
                "#38bdf8",
                zero_line=True,
            ),
            chart_time_cell(
                "chart_realized",
                "Realized PnL",
                f"{prefix}.realized_pnl_usdc",
                "#4ade80",
                zero_line=True,
            ),
            chart_time_cell(
                "chart_net_realized",
                "Net realized",
                f"{prefix}.net_realized_pnl_usdc",
                "#a78bfa",
                zero_line=True,
            ),
            chart_time_cell("chart_spread", "Spread (bps)", f"{prefix}.spread_bps", "#60a5fa"),
            chart_time_cell("chart_inventory", "Inventory", f"{prefix}.inventory", "#c084fc"),
            chart_time_cell(
                "chart_markout",
                "Markout guard (bps)",
                f"{prefix}.markout_extra_bps",
                "#fbbf24",
            ),
        ]
    )

    return f"""
            <section class="card">
              <header class="card-head">
                <div>
                  <h2>{html.escape(sym['symbol'])}</h2>
                  <span class="slug">{html.escape(sym['slug'])}</span>
                </div>
                <span class="badge {status_cls}">{status}</span>
              </header>
              <div class="grid">{metrics_html}</div>
              <div class="charts">{charts_html}</div>
            </section>
            """


def render_stack_panel(stack_data: dict) -> str:
    stack_id = str(stack_data.get("stack", "stack"))
    parts = [render_portfolio_card(stack_data, hide_stack_in_title=True, stack_id=stack_id)]
    for sym in stack_data.get("symbols", []):
        parts.append(render_symbol_card(sym, stack_id))
    return "\n".join(parts)


def render_portfolio_card(
    stack_data: dict, *, hide_stack_in_title: bool = False, stack_id: str = "stack"
) -> str:
    pf = stack_data.get("portfolio") or {}
    metrics_html = "".join(
        [
            metric_cell(
                "portfolio_upl",
                "Portfolio uPnL",
                fmt_usd(pf.get("unrealized_pnl_usdc")),
                pnl_class(pf.get("unrealized_pnl_usdc")),
            ),
            metric_cell(
                "realized_pnl",
                "Portfolio realized",
                fmt_usd(pf.get("realized_pnl_usdc")),
                pnl_class(pf.get("realized_pnl_usdc")),
            ),
            metric_cell(
                "portfolio_net",
                "Portfolio net realized",
                fmt_usd(pf.get("net_realized_pnl_usdc")),
                pnl_class(pf.get("net_realized_pnl_usdc")),
            ),
            metric_cell("fees", "Portfolio fees", fmt_usd(pf.get("fees_usdc"))),
        ]
    )
    charts_html = "".join(
        [
            chart_time_cell(
                "chart_upl",
                "Portfolio uPnL",
                "portfolio.unrealized_pnl_usdc",
                "#38bdf8",
                zero_line=True,
            ),
            chart_time_cell(
                "chart_realized",
                "Portfolio realized",
                "portfolio.realized_pnl_usdc",
                "#4ade80",
                zero_line=True,
            ),
            chart_time_cell(
                "chart_net_realized",
                "Portfolio net realized",
                "portfolio.net_realized_pnl_usdc",
                "#a78bfa",
                zero_line=True,
            ),
        ]
    )
    stack = html.escape(stack_data.get("stack", ""))
    art = html.escape(stack_data.get("artifacts_dir", ""))
    title = "Portfolio" if hide_stack_in_title else f"Portfolio · {stack}"
    return f"""
            <section class="card portfolio-card">
              <header class="card-head">
                <div>
                  <h2>{title}</h2>
                  <span class="slug">{art}</span>
                </div>
              </header>
              <div class="grid">{metrics_html}</div>
              <div class="charts pnl-charts">{charts_html}</div>
            </section>
            """


def render_tabbed_html(data: dict) -> str:
    """Single page with Testnet / Devnet tabs."""
    stacks = data.get("stacks") or []
    if not stacks:
        return render_html({"generated_at": data["generated_at"], "symbols": [], "stack": "testnet"})

    tab_buttons: list[str] = []
    panels: list[str] = []
    for i, stack_data in enumerate(stacks):
        sid = html.escape(str(stack_data.get("stack", f"stack{i}")))
        label = sid.upper()
        active_cls = " active" if i == 0 else ""
        tab_buttons.append(
            f'<button type="button" class="tab{active_cls}" role="tab" '
            f'aria-selected="{"true" if i == 0 else "false"}" '
            f'data-tab="{sid}" id="tab-{sid}">{label}</button>'
        )
        hidden = "" if i == 0 else ' hidden=""'
        panels.append(
            f'<div class="tab-panel{active_cls}" role="tabpanel" '
            f'id="panel-{sid}" data-stack="{sid}" data-range-preset="1d" '
            f'aria-labelledby="tab-{sid}"{hidden}>'
            f"{render_range_bar()}"
            f"{render_stack_panel(stack_data)}"
            f"</div>"
        )

    ts_embed = {s["stack"]: stack_timeseries_embed(s) for s in stacks}
    ts_json = json.dumps(ts_embed, separators=(",", ":"))
    ts_script = f'<script type="application/json" id="mm-timeseries">{ts_json}</script>'

    body = (
        '<nav class="tab-bar" role="tablist" aria-label="Environment">'
        + "".join(tab_buttons)
        + "</nav>"
        + "".join(panels)
        + ts_script
        + '<script src="/dashboard-charts.js"></script>'
        + """
<script>
(function () {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");
  function select(id) {
    tabs.forEach((t) => {
      const on = t.dataset.tab === id;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((p) => {
      const on = p.id === "panel-" + id;
      p.classList.toggle("active", on);
      p.hidden = !on;
    });
    history.replaceState(null, "", "#" + id);
  }
  tabs.forEach((t) => t.addEventListener("click", () => select(t.dataset.tab)));
  const hash = (location.hash || "").replace(/^#/, "");
  const ids = Array.from(tabs).map((t) => t.dataset.tab);
  if (hash && ids.includes(hash)) select(hash);
})();
</script>"""
    )
    return _render_page_shell(data["generated_at"], body, title_suffix="")


def render_html(data: dict) -> str:
    if "stacks" in data:
        return render_tabbed_html(data)
    sid = str(data.get("stack", "testnet"))
    body = render_portfolio_card(data, stack_id=sid)
    body += "\n".join(render_symbol_card(s, sid) for s in data.get("symbols", []))
    stack = data.get("stack", "testnet")
    title_suffix = f" · {html.escape(str(stack))}"
    return _render_page_shell(data["generated_at"], body, title_suffix=title_suffix)


def _render_page_shell(generated_at: str, body: str, title_suffix: str) -> str:
    generated = html.escape(generated_at)
    chart_note = html.escape(
        "Charts use MM_METRICS timestamps from bot logs (up to "
        f"{MAX_LOG_BYTES // (1024 * 1024)}MB per log). "
        "1M range needs ~30d of history in logs. Bot estimates ≠ GoDark FE settlement."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta http-equiv="refresh" content="60"/>
  <title>GoDark MM Dashboard{title_suffix}</title>
  <style>
    :root {{
      --bg: #0b0d12;
      --surface: #141820;
      --surface2: #0f1218;
      --border: #252b38;
      --text: #e8eaed;
      --muted: #8b93a7;
      --accent: #7cb8ff;
      --green: #4ade80;
      --red: #f87171;
      --amber: #fbbf24;
      --bid: #4ade80;
      --ask: #f87171;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .hero {{
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }}
    .hero h1 {{
      margin: 0 0 6px;
      font-size: 1.35rem;
      font-weight: 650;
      letter-spacing: -0.02em;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .meta kbd {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1px 6px;
      font-size: 0.75rem;
    }}
    .tab-bar {{
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
    }}
    .tab {{
      appearance: none;
      border: 1px solid var(--border);
      background: var(--surface2);
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 8px 18px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s, border-color 0.15s;
    }}
    .tab:hover {{
      color: var(--text);
      border-color: #3d4659;
    }}
    .tab.active {{
      background: rgba(124, 184, 255, 0.12);
      border-color: rgba(124, 184, 255, 0.45);
      color: var(--accent);
    }}
    .tab-panel:not(.active) {{
      display: none;
    }}
    .tab-panel[hidden] {{
      display: none !important;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 20px 20px;
      margin-bottom: 18px;
    }}
    .portfolio-card {{
      border-color: rgba(124, 184, 255, 0.35);
      background: linear-gradient(180deg, #161c28 0%, var(--surface) 100%);
    }}
    .card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .card h2 {{
      margin: 0;
      font-size: 1.05rem;
      font-weight: 600;
      color: var(--accent);
    }}
    .slug {{
      display: inline-block;
      margin-top: 2px;
      font-size: 0.72rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .badge {{
      font-size: 0.72rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 999px;
      white-space: nowrap;
    }}
    .badge-ok {{ background: rgba(74, 222, 128, 0.12); color: var(--green); border: 1px solid rgba(74, 222, 128, 0.25); }}
    .badge-warn {{ background: rgba(251, 191, 36, 0.12); color: var(--amber); border: 1px solid rgba(251, 191, 36, 0.25); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
      gap: 12px;
    }}
    .metric {{
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 11px;
      min-height: 68px;
    }}
    .label-row {{
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 6px;
    }}
    .label {{
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      font-weight: 600;
    }}
    .val {{
      display: block;
      font-size: 0.98rem;
      font-variant-numeric: tabular-nums;
      font-weight: 500;
    }}
    .val.bid {{ color: var(--bid); }}
    .val.ask {{ color: var(--ask); }}
    .val.good {{ color: var(--green); }}
    .val.bad {{ color: var(--red); }}
    .val.warn {{ color: var(--amber); }}
    .val.neutral {{ color: var(--text); }}
    .info {{
      position: relative;
      display: inline-flex;
      align-items: center;
      cursor: help;
      outline: none;
    }}
    .info-icon {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 1px solid #4b5563;
      color: var(--muted);
      font-size: 0.58rem;
      font-weight: 700;
      font-style: italic;
      font-family: Georgia, serif;
      line-height: 1;
      transition: border-color 0.15s, color 0.15s;
    }}
    .info:hover .info-icon,
    .info:focus .info-icon {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .tip {{
      display: none;
      position: absolute;
      left: 50%;
      bottom: calc(100% + 8px);
      transform: translateX(-50%);
      width: max-content;
      max-width: 240px;
      padding: 8px 10px;
      background: #1e2430;
      border: 1px solid #3d4659;
      border-radius: 8px;
      color: #d1d5db;
      font-size: 0.72rem;
      font-weight: 400;
      text-transform: none;
      letter-spacing: normal;
      line-height: 1.4;
      box-shadow: 0 8px 24px rgba(0,0,0,0.45);
      z-index: 20;
      pointer-events: none;
    }}
    .tip::after {{
      content: "";
      position: absolute;
      top: 100%;
      left: 50%;
      margin-left: -5px;
      border: 5px solid transparent;
      border-top-color: #3d4659;
    }}
    .info:hover .tip,
    .info:focus .tip,
    .info:focus-within .tip {{
      display: block;
    }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }}
    .pnl-charts {{
      grid-template-columns: 1fr;
    }}
    .chart-box {{
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px 8px;
    }}
    .chart-box-wide {{
      grid-column: 1 / -1;
    }}
    canvas.time-chart {{
      display: block;
      width: 100%;
      height: 140px;
      margin-top: 6px;
    }}
    .range-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
      padding: 10px 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
    }}
    .range-label {{
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-right: 4px;
    }}
    .range-btn {{
      appearance: none;
      border: 1px solid var(--border);
      background: var(--surface2);
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
    }}
    .range-btn.active {{
      border-color: rgba(124, 184, 255, 0.45);
      color: var(--accent);
      background: rgba(124, 184, 255, 0.1);
    }}
    .range-custom {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .range-custom input {{
      background: var(--surface2);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 6px;
      padding: 5px 8px;
      font-size: 0.78rem;
    }}
    .range-sep {{ color: var(--muted); font-size: 0.75rem; }}
    .spark {{ display: block; margin-top: 4px; width: 100%; max-width: 240px; }}
    .spark-empty {{ color: var(--muted); font-size: 0.75rem; }}
    @media (max-width: 640px) {{
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
      .tip {{ max-width: 180px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <h1>GoDark MM Dashboard</h1>
      <p class="meta">
        Generated {generated} UTC · auto-refresh 60s ·
        hover <kbd>i</kbd> on any label for help<br/>
        {chart_note}
      </p>
    </header>
    {body}
  </div>
</body>
</html>"""


def write_stack_outputs(stack: str, artifacts: Path) -> None:
    data = build_payload(artifacts, stack=stack)
    metrics_dir = artifacts / "mm-metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "dashboard-latest.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f"json [{stack}]: {metrics_dir / 'dashboard-latest.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MM metrics dashboard")
    parser.add_argument("--json", action="store_true", help="Print combined JSON to stdout")
    parser.add_argument(
        "--combined-only",
        action="store_true",
        help="Only write testnet+devnet combined dashboard",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Override HTML output (single-stack mode only; uses MM_ARTIFACTS_DIR)",
    )
    args = parser.parse_args()

    combined = build_combined_payload()
    combined_dir = ARTIFACTS_ROOT / "mm-metrics"
    combined_dir.mkdir(parents=True, exist_ok=True)
    combined_json = combined_dir / "dashboard-both-latest.json"
    tabbed_html = ARTIFACTS_ROOT / "mm-dashboard.html"
    combined_json.write_text(json.dumps(combined, indent=2) + "\n")
    tabbed_html.write_text(render_tabbed_html(combined))
    print(f"dashboard: {tabbed_html}")
    print(f"json [combined]: {combined_json}")

    if args.json:
        print(json.dumps(combined, indent=2))
        return 0

    if not args.combined_only:
        for stack_name, art_path in STACK_DIRS:
            if art_path.is_dir() or any(log_path(s, art_path).exists() for s in SYMBOLS):
                write_stack_outputs(stack_name, art_path)

        if args.out:
            single = build_payload(DEFAULT_ARTIFACTS, stack=os.environ.get("MM_STACK", "testnet"))
            Path(args.out).write_text(render_html(single))
            print(f"dashboard [custom out]: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
