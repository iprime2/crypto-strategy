"""Parse MM markout samples from bot logs (MM_MARKOUT_HORIZON + legacy lines)."""

from __future__ import annotations

import json
import re
from pathlib import Path

HORIZON_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T[\d:.]+Z).*MM_MARKOUT_HORIZON (\{.*\})"
)
LEGACY_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T[\d:.]+Z).*fill markout signed=([-\d.]+) bps"
)

DEFAULT_HORIZON_SEC = int(__import__("os").environ.get("MM_MARKOUT_SUMMARY_HORIZON", "30"))


def parse_markout_samples(
    path: Path,
    *,
    tail_lines: int = 8000,
    horizon_sec: int | None = DEFAULT_HORIZON_SEC,
) -> list[dict]:
    """One row per fill-quality sample (default: 30s horizon only)."""
    if not path.exists():
        return []
    lines = path.read_text(errors="replace").splitlines()
    if tail_lines > 0:
        lines = lines[-tail_lines:]
    out: list[dict] = []
    for line in lines:
        hm = HORIZON_RE.search(line)
        if hm:
            try:
                row = json.loads(hm.group(2))
            except json.JSONDecodeError:
                continue
            h = int(row.get("horizon_sec", 0))
            if horizon_sec is not None and h != horizon_sec:
                continue
            out.append(
                {
                    "ts": hm.group(1),
                    "signed_bps": float(row["signed_bps"]),
                    "bought": bool(row.get("bought")),
                    "horizon_sec": h,
                }
            )
            continue
        if horizon_sec is None:
            lm = LEGACY_RE.search(line)
            if lm:
                out.append(
                    {
                        "ts": lm.group(1),
                        "signed_bps": float(lm.group(2)),
                        "bought": None,
                        "horizon_sec": None,
                    }
                )
    return out


def summarize_markout_samples(samples: list[dict]) -> dict:
    if not samples:
        return {
            "count": 0,
            "avg_bps": None,
            "pct_positive": None,
            "last_bps": None,
            "buy_avg_bps": None,
            "sell_avg_bps": None,
            "buy_count": 0,
            "sell_count": 0,
        }
    vals = [float(s["signed_bps"]) for s in samples]
    pos = sum(1 for v in vals if v > 0)
    buys = [float(s["signed_bps"]) for s in samples if s.get("bought") is True]
    sells = [float(s["signed_bps"]) for s in samples if s.get("bought") is False]

    def _avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    return {
        "count": len(vals),
        "avg_bps": sum(vals) / len(vals),
        "pct_positive": 100.0 * pos / len(vals),
        "last_bps": vals[-1],
        "buy_avg_bps": _avg(buys),
        "sell_avg_bps": _avg(sells),
        "buy_count": len(buys),
        "sell_count": len(sells),
    }
