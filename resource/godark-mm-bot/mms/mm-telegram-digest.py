#!/usr/bin/env python3
"""GoDark MM bot scorecard → Telegram (parse logs, optional send)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MMS = Path(__file__).resolve().parent
ARTIFACTS = MMS / "artifacts"
SYMBOLS = ("BTC", "ETH", "SOL")
RUNBOOK = ARTIFACTS / "runs" / "current" / "RUNBOOK.md"


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return False
    body = urllib.parse.urlencode(
        {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as exc:  # noqa: BLE001
        print(f"telegram send failed: {exc}", file=sys.stderr)
        return False


def run_started_utc() -> datetime | None:
    if not RUNBOOK.exists():
        return None
    m = re.search(r"Started \(UTC\)\s*\|\s*([^\|]+)", RUNBOOK.read_text())
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_symbol(sym: str) -> dict:
    path = ARTIFACTS / f"mm-bot-{sym}.log"
    out = {
        "symbol": sym,
        "fills": 0,
        "fill_rate_hr": 0.0,
        "spread_min": 0.0,
        "spread_med": 0.0,
        "spread_max": 0.0,
        "kappa_eff": None,
        "kappa_raw": None,
        "upnl_start": None,
        "upnl_end": None,
        "error_streak_max": 0,
        "markout_avg": None,
        "markout_n": 0,
        "calibrated": False,
    }
    if not path.exists():
        return out

    spreads: list[float] = []
    markouts: list[float] = []
    with path.open() as f:
        for line in f:
            if "fill distance" in line:
                out["fills"] += 1
                if "raw=" in line:
                    out["calibrated"] = True
            if "fill markout signed=" in line:
                m = re.search(r"signed=([-\d.]+) bps", line)
                if m:
                    markouts.append(float(m.group(1)))
            if "MM_METRICS" not in line:
                continue
            try:
                d = json.loads(line.split("MM_METRICS ", 1)[1])
            except json.JSONDecodeError:
                continue
            spreads.append(float(d.get("spread_bps", 0)))
            out["error_streak_max"] = max(
                out["error_streak_max"], int(d.get("error_streak", 0))
            )
            upnl = d.get("unrealized_pnl")
            if upnl is not None:
                upnl = float(upnl)
                if out["upnl_start"] is None:
                    out["upnl_start"] = upnl
                out["upnl_end"] = upnl
            out["kappa_eff"] = float(d.get("effective_kappa", 0))
            if d.get("kappa_raw") is not None:
                out["kappa_raw"] = float(d["kappa_raw"])
            if d.get("net_realized_pnl_usdc") is not None:
                out["net_realized"] = float(d["net_realized_pnl_usdc"])

    if spreads:
        s = sorted(spreads)
        out["spread_min"] = s[0]
        out["spread_med"] = s[len(s) // 2]
        out["spread_max"] = s[-1]
    if markouts:
        out["markout_avg"] = sum(markouts) / len(markouts)
        out["markout_n"] = len(markouts)

    started = run_started_utc()
    if started and out["fills"]:
        hrs = max((datetime.now(timezone.utc) - started).total_seconds() / 3600, 0.1)
        out["fill_rate_hr"] = out["fills"] / hrs
    return out


def build_digest() -> str:
    started = run_started_utc()
    now = datetime.now(timezone.utc)
    if started:
        hrs = (now - started).total_seconds() / 3600
        run_line = f"Run {started.strftime('%Y-%m-%d %H:%M')} UTC · {hrs:.1f}h"
    else:
        run_line = "Run age unknown"

    rows = [parse_symbol(s) for s in SYMBOLS]
    total_fills = sum(r["fills"] for r in rows)
    total_rate = sum(r["fill_rate_hr"] for r in rows)
    any_wide = any(r["spread_max"] > 80 for r in rows)
    any_cal = any(r["calibrated"] for r in rows)
    kappa_ok = all(
        (r["kappa_eff"] or 1.5) >= 0.5 and (r["spread_max"] or 24) < 80 for r in rows if r["fills"]
    ) or not any_cal

    if any_wide:
        verdict = "FAIL spread blow-up"
    elif kappa_ok and total_fills > 0:
        verdict = "PASS κ floor holding"
    elif total_fills == 0:
        verdict = "WARN no fills yet"
    else:
        verdict = "CHECK"

    lines = [
        f"MM Bot Daily · {now.strftime('%Y-%m-%d %H:%M')} UTC",
        run_line,
        f"Verdict: {verdict}",
        "",
        f"Fills: {total_fills} total ({total_rate:.1f}/hr)",
        "",
    ]

    for r in rows:
        kappa = f"{r['kappa_eff']:.2f}" if r["kappa_eff"] is not None else "—"
        raw = f"{r['kappa_raw']:.3f}" if r["kappa_raw"] is not None else "—"
        upnl_s = r["upnl_start"]
        upnl_e = r["upnl_end"]
        net_r = r.get("net_realized")
        if upnl_s is not None and upnl_e is not None:
            pnl = f"uPnL ${upnl_s:+.2f}→${upnl_e:+.2f}"
        else:
            pnl = "uPnL —"
        if net_r is not None:
            pnl += f" · net real ${net_r:+.2f}"
        mo = (
            f"{r['markout_avg']:+.1f}bps×{r['markout_n']}"
            if r["markout_avg"] is not None
            else "—"
        )
        lines.append(
            f"{r['symbol']}: {r['fills']} fills ({r['fill_rate_hr']:.1f}/hr) · "
            f"spread {r['spread_min']:.0f}/{r['spread_med']:.0f}/{r['spread_max']:.0f} bps"
        )
        lines.append(f"  κ {kappa} raw {raw} · uPnL {pnl} · markout {mo}")

    lines.extend(
        [
            "",
            "Old bug: κ→0.06 spread→155 bps",
            "Fix: floor 0.5 cap 5.0 arrival×1",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    dry = "--dry-run" in sys.argv
    text = build_digest()
    print(text)
    if dry:
        return 0
    return 0 if send_telegram(text) else 1


if __name__ == "__main__":
    raise SystemExit(main())
