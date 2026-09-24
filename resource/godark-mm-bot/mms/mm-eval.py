#!/usr/bin/env python3
"""Evaluate vanilla MM bot performance from MM_METRICS log lines and tune params."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from mm_markout import parse_markout_samples, summarize_markout_samples  # noqa: E402

def _artifacts_dir() -> Path:
    return Path(
        os.environ.get(
            "MM_ARTIFACTS_DIR",
            Path.home() / "scripts/mms/artifacts",
        )
    )


TUNING_PATH = Path(
    os.environ.get("MM_TUNING_ENV", str(_artifacts_dir() / "mm-tuning.env"))
)
LOG_PATH = Path(os.environ.get("MM_BOT_LOG", str(_artifacts_dir() / "mm-bot.log")))
REPORT_DIR = Path(os.environ.get("MM_REPORT_DIR", str(_artifacts_dir() / "mm-metrics")))

METRICS_RE = re.compile(r"MM_METRICS (\{.*\})")

SYMBOL_QTY_KEYS = {
    "BTC-USDC-PERP": "MM_ORDER_QTY_BTC",
    "ETH-USDC-PERP": "MM_ORDER_QTY_ETH",
    "SOL-USDC-PERP": "MM_ORDER_QTY_SOL",
}
SYMBOL_BASE_QTY = {
    "BTC-USDC-PERP": 0.005,
    "ETH-USDC-PERP": 0.05,
    "SOL-USDC-PERP": 0.5,
}
SCALE_MAX_MULT = 2.0
SCALE_MIN_MULT = 0.5
SCALE_UP_PCT = 0.05
SCALE_DOWN_PCT = 0.10
MIN_MARKOUT_SAMPLES = 8


def load_tuning() -> dict[str, str]:
    out: dict[str, str] = {}
    if not TUNING_PATH.exists():
        return out
    for line in TUNING_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def save_tuning(values: dict[str, str]) -> None:
    TUNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Auto-tuned MM parameters (updated by mm-eval.py / mm-tune-loop.sh)",
        f"# Last eval: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for k in sorted(values):
        lines.append(f"{k}={values[k]}")
    TUNING_PATH.write_text("\n".join(lines) + "\n")


def parse_metrics(log_path: Path, symbol: str | None = None, tail_lines: int = 500) -> list[dict]:
    if not log_path.exists():
        return []
    lines = log_path.read_text(errors="replace").splitlines()[-tail_lines:]
    rows: list[dict] = []
    for line in lines:
        m = METRICS_RE.search(line)
        if not m:
            continue
        try:
            row = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if symbol and row.get("symbol") and row.get("symbol") != symbol:
            continue
        rows.append(row)
    return rows


def parse_markouts(log_path: Path, tail_lines: int = 8000) -> list[float]:
    samples = parse_markout_samples(log_path, tail_lines=tail_lines)
    return [float(s["signed_bps"]) for s in samples]


def qty_key_for(symbol: str | None) -> str:
    if symbol and symbol in SYMBOL_QTY_KEYS:
        return SYMBOL_QTY_KEYS[symbol]
    return "MM_ORDER_QTY"


def evaluate_size_scaling(
    symbol: str | None,
    log_path: Path,
    tuning: dict[str, str],
    markout_extra: float,
    notes: list[str],
) -> tuple[dict[str, str], bool]:
    """Gradual size scaling from signed markout history (research: scale when edge is positive)."""
    if not symbol or symbol not in SYMBOL_QTY_KEYS:
        return tuning, False

    key = qty_key_for(symbol)
    base = SYMBOL_BASE_QTY[symbol]
    current = float(tuning.get(key, str(base)))
    samples = parse_markouts(log_path)
    if len(samples) < MIN_MARKOUT_SAMPLES:
        notes.append(
            f"size scale: need {MIN_MARKOUT_SAMPLES}+ markout samples (have {len(samples)})"
        )
        return tuning, False

    window = samples[-50:]
    avg_mk = sum(window) / len(window)
    pct_pos = sum(1 for v in window if v > 0) / len(window)
    changed = False
    new_qty = current

    buy_samples = [
        s for s in parse_markout_samples(log_path, tail_lines=8000) if s.get("bought") is True
    ]
    buy_avg = (
        sum(s["signed_bps"] for s in buy_samples) / len(buy_samples) if buy_samples else None
    )
    if buy_avg is not None and buy_avg < -15.0:
        notes.append(f"size scale blocked: buy_30s={buy_avg:+.1f}bps")
        return tuning, False

    if (
        avg_mk > 1.0
        and pct_pos >= 0.55
        and markout_extra < 2.0
        and current < base * SCALE_MAX_MULT
    ):
        new_qty = min(base * SCALE_MAX_MULT, current * (1.0 + SCALE_UP_PCT))
        notes.append(
            f"scale up {key}={new_qty:.4f} (avg markout {avg_mk:+.2f} bps, {pct_pos:.0%} positive)"
        )
        changed = new_qty != current
    elif avg_mk < -5.0 and current > base * SCALE_MIN_MULT:
        new_qty = max(base * SCALE_MIN_MULT, current * (1.0 - SCALE_DOWN_PCT))
        notes.append(
            f"scale down {key}={new_qty:.4f} (avg markout {avg_mk:+.2f} bps adverse)"
        )
        changed = new_qty != current
    else:
        notes.append(
            f"size scale hold {key}={current:.4f} (avg markout {avg_mk:+.2f} bps, guard={markout_extra:.1f})"
        )

    if changed:
        tuning[key] = f"{new_qty:.4f}".rstrip("0").rstrip(".")
    return tuning, changed


def fnum(d: dict, key: str, default: float) -> float:
    v = d.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def evaluate(
    metrics: list[dict],
    tuning: dict[str, str],
    symbol: str | None = None,
    log_path: Path | None = None,
) -> tuple[dict[str, str], list[str], bool]:
    notes: list[str] = []
    out = dict(tuning)
    size_changed = False

    def get(k: str, default: str) -> float:
        return float(out.get(k, tuning.get(k, default)))

    qty_key = qty_key_for(symbol)
    half_spread = get("MM_HALF_SPREAD_BPS", "50")
    skew = get("MM_INVENTORY_SKEW_BPS", "5")
    max_inv = get("MM_MAX_INVENTORY", "0.05")
    loop_sec = get("MM_LOOP_INTERVAL_SEC", "10")
    order_qty = get(qty_key, get("MM_ORDER_QTY", "0.01"))
    tune_spread = symbol in (None, "BTC-USDC-PERP")

    if len(metrics) < 3:
        notes.append(f"insufficient metrics ({len(metrics)} rows); skipping tune")
        return out, notes, False

    recent = metrics[-min(30, len(metrics)) :]
    fill_events = int(recent[-1].get("fill_events", 0))
    fills_in_window = sum(1 for i in range(1, len(recent)) if recent[i].get("inventory") != recent[i - 1].get("inventory"))
    avg_spread = sum(fnum(r, "spread_bps", 54) for r in recent) / len(recent)
    avg_vol = sum(fnum(r, "vol_bps", 0) for r in recent) / len(recent)
    markout_extra = fnum(recent[-1], "markout_extra_bps", 0)
    inv = fnum(recent[-1], "inventory", 0.0)
    at_cap = any(r.get("at_cap") for r in recent[-10:])
    upl = recent[-1].get("unrealized_pnl")
    upl_f = float(upl) if upl is not None else None

    notes.append(
        f"snapshot inv={inv:.4f} spread_bps={avg_spread:.1f} vol_bps={avg_vol:.1f} markout_extra={markout_extra:.1f} fills_total={fill_events} fills_window={fills_in_window} at_cap={at_cap}"
    )

    # High vol → already widened by bot; don't tighten below fee floor
    vol_mult = float(out.get("MM_VOL_SPREAD_MULT", tuning.get("MM_VOL_SPREAD_MULT", "1.5")))
    fee_floor = 2.0 * float(out.get("MM_MAKER_FEE_BPS", tuning.get("MM_MAKER_FEE_BPS", "2"))) + float(
        out.get("MM_ADVERSE_BUFFER_BPS", tuning.get("MM_ADVERSE_BUFFER_BPS", "8"))
    )
    min_half = max(12.0, fee_floor / 2.0)

    mk_summary = (
        summarize_markout_samples(parse_markout_samples(log_path))
        if log_path and log_path.exists()
        else {}
    )
    avg_mk = mk_summary.get("avg_bps")
    buy_mk = mk_summary.get("buy_avg_bps")
    block_tighten = False
    if avg_mk is not None and avg_mk < -5.0:
        block_tighten = True
        notes.append(f"markout guard eval: avg_30s={avg_mk:+.1f}bps — no spread tighten")
    if buy_mk is not None and buy_mk < -15.0:
        block_tighten = True
        notes.append(f"markout guard eval: buy_30s={buy_mk:+.1f}bps — no spread tighten / no size up")

    if tune_spread:
        # No fills + wide spread → tighten slightly (respect min half spread)
        if (
            not block_tighten
            and fills_in_window == 0
            and avg_spread > 45
            and half_spread > min_half + 5
        ):
            half_spread = max(min_half, half_spread - 3.0)
            notes.append(f"tighten spread → MM_HALF_SPREAD_BPS={half_spread:.0f} (no fills, spread wide)")

        # Markout guard active → don't tighten until decay
        if markout_extra > 2.0 and half_spread < 60.0:
            notes.append(f"markout guard active ({markout_extra:.1f} bps); holding spread")

        # High realized vol → ensure vol mult not too low
        if avg_vol > 25.0 and vol_mult < 2.0:
            out["MM_VOL_SPREAD_MULT"] = f"{min(2.5, vol_mult + 0.25):.2f}"
            notes.append(f"raise vol mult → MM_VOL_SPREAD_MULT={out['MM_VOL_SPREAD_MULT']} (avg_vol={avg_vol:.1f})")

        # Fills but inventory drifting at cap → stronger skew
        if at_cap and fills_in_window > 0 and abs(inv) >= max_inv * 0.9:
            skew = min(30.0, skew + 3.0)
            notes.append(f"raise skew → MM_INVENTORY_SKEW_BPS={skew:.0f} (inventory pinned at cap)")

        # Large unrealized loss → widen spread to reduce adverse selection
        if upl_f is not None and upl_f < -50.0 and half_spread < 80.0:
            half_spread = min(80.0, half_spread + 5.0)
            notes.append(f"widen spread → MM_HALF_SPREAD_BPS={half_spread:.0f} (upl={upl_f:.2f})")

        # Very active fills → slightly widen to earn more per round trip
        if fills_in_window >= 3 and half_spread < 60.0:
            half_spread = min(60.0, half_spread + 3.0)
            notes.append(f"widen spread → MM_HALF_SPREAD_BPS={half_spread:.0f} (active fills)")

        # Slow loop if many cancels but no fills — stay at 10s minimum
        if loop_sec < 10:
            loop_sec = 10.0
            notes.append("floor loop interval at 10s")

        out["MM_HALF_SPREAD_BPS"] = f"{half_spread:.0f}"
        out["MM_INVENTORY_SKEW_BPS"] = f"{skew:.0f}"
        out["MM_LOOP_INTERVAL_SEC"] = f"{loop_sec:.0f}"
        if "MM_VOL_SPREAD_MULT" not in out:
            out["MM_VOL_SPREAD_MULT"] = tuning.get("MM_VOL_SPREAD_MULT", "1.5")

    # Long at cap: reduce clip for gradual unwind
    min_qty = SYMBOL_BASE_QTY.get(symbol or "", 0.005) * SCALE_MIN_MULT
    if inv > max_inv and order_qty > min_qty:
        order_qty = max(min_qty, order_qty * 0.9)
        notes.append(f"reduce clip → {qty_key}={order_qty:.4f} (over max inventory)")

    out[qty_key] = f"{order_qty:.4f}".rstrip("0").rstrip(".")

    if log_path and symbol:
        out, scaled = evaluate_size_scaling(symbol, log_path, out, markout_extra, notes)
        size_changed = scaled

    return out, notes, size_changed


def write_report(metrics: list[dict], notes: list[str], symbol: str | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = (symbol or "all").split("-")[0]
    path = REPORT_DIR / f"eval-{slug}-{ts}.json"
    payload = {
        "ts": ts,
        "symbol": symbol,
        "metrics_count": len(metrics),
        "last_metric": metrics[-1] if metrics else None,
        "notes": notes,
        "tuning_path": str(TUNING_PATH),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def main() -> int:
    global TUNING_PATH, REPORT_DIR, LOG_PATH
    TUNING_PATH = Path(os.environ.get("MM_TUNING_ENV", str(_artifacts_dir() / "mm-tuning.env")))
    REPORT_DIR = Path(os.environ.get("MM_REPORT_DIR", str(_artifacts_dir() / "mm-metrics")))
    LOG_PATH = Path(os.environ.get("MM_BOT_LOG", str(_artifacts_dir() / "mm-bot.log")))

    parser = argparse.ArgumentParser(description="Evaluate MM bot and update tuning env")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--symbol", help="Filter metrics to this symbol (e.g. BTC-USDC-PERP)")
    parser.add_argument("--log", help="Bot log path (default: MM_BOT_LOG env)")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else LOG_PATH
    if args.symbol and args.log is None:
        slug = args.symbol.split("-")[0]
        log_path = _artifacts_dir() / f"mm-bot-{slug}.log"

    tuning = load_tuning()
    metrics = parse_metrics(log_path, symbol=args.symbol)
    new_tuning, notes, size_changed = evaluate(
        metrics, tuning, symbol=args.symbol, log_path=log_path
    )

    label = args.symbol or "all"
    print(f"MM eval [{label}]")
    for n in notes:
        print(f"  - {n}")

    changed = {k: v for k, v in new_tuning.items() if tuning.get(k) != v}
    if changed:
        print("changes:")
        for k, v in sorted(changed.items()):
            print(f"  {k}: {tuning.get(k, '(new)')} → {v}")
    else:
        print("no tuning changes")

    report = write_report(metrics, notes, args.symbol)
    print(f"report: {report}")

    restart = size_changed or any(
        k in changed
        for k in (
            "MM_HALF_SPREAD_BPS",
            "MM_INVENTORY_SKEW_BPS",
            "MM_VOL_SPREAD_MULT",
            "MM_LOOP_INTERVAL_SEC",
        )
    )

    if not args.dry_run and changed:
        save_tuning(new_tuning)
        print(f"updated: {TUNING_PATH}")
        if restart:
            return 2  # signal restart needed

    return 0


if __name__ == "__main__":
    sys.exit(main())
