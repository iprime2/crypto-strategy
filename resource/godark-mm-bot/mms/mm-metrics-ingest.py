#!/usr/bin/env python3
"""Tail MM bot logs and insert MM_METRICS rows into MM TimescaleDB (mm_ops)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["BTC-USDC-PERP", "ETH-USDC-PERP", "SOL-USDC-PERP"]
METRICS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:\.]+Z).*MM_METRICS (\{.*\})")
LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:\.]+Z)")

ARTIFACTS_ROOT = Path.home() / "scripts" / "mms" / "artifacts"
STACK_DIRS: dict[str, Path] = {
    "testnet": ARTIFACTS_ROOT,
    "devnet": ARTIFACTS_ROOT / "devnet",
}


def slug(symbol: str) -> str:
    return symbol.split("-")[0]


def parse_ts(iso: str) -> datetime:
    s = iso.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def state_path(artifacts: Path) -> Path:
    return artifacts / "mm-metrics" / "ingest-state.json"


def load_state(artifacts: Path) -> dict:
    p = state_path(artifacts)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def save_state(artifacts: Path, state: dict) -> None:
    p = state_path(artifacts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n")


def iter_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    if not path.exists():
        return [], offset
    size = path.stat().st_size
    if size < offset:
        offset = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        raw = fh.read()
        new_offset = fh.tell()
    if not raw:
        return [], new_offset
    text = raw.decode(errors="replace")
    lines = text.splitlines()
    if text and not text.endswith("\n") and lines:
        # partial line — keep in file for next pass
        partial = lines.pop()
        new_offset -= len(partial.encode(errors="replace"))
    return lines, new_offset


def run_psql(sql: str, url: str) -> None:
    try:
        proc = subprocess.run(
            ["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-c", sql],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return
    except FileNotFoundError:
        proc = None
    # Host may lack psql — use Timescale container.
    proc2 = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "mm-strategy-timescale",
            "psql",
            "-U",
            os.environ.get("MM_TSDB_USER", "mm"),
            "-d",
            os.environ.get("MM_TSDB_DB", "mm_ops"),
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
    )
    if proc2.returncode != 0:
        err = proc2.stderr.strip() or (proc.stderr.strip() if proc else "") or "psql failed"
        raise RuntimeError(err)


def psql_insert(url: str, rows: list[tuple]) -> None:
    if not rows:
        return
    values_sql = []
    for row in rows:
        (
            t,
            stack,
            symbol,
            loop_n,
            account_id,
            upl,
            real,
            net,
            fees,
            inv,
            spread,
            markout,
            fair,
        ) = row
        acc = "NULL" if account_id is None else f"'{account_id}'::uuid"
        upl_sql = "NULL" if upl is None else str(float(upl))
        values_sql.append(
            f"('{t.isoformat()}','{stack}','{symbol}',{loop_n},{acc},"
            f"{upl_sql},{real},{net},{fees},{inv},{spread},{markout},{fair})"
        )
    sql = (
        "INSERT INTO mm_metric_samples "
        "(time, stack, symbol, loop, account_id, unrealized_pnl_usdc, "
        "realized_pnl_usdc, net_realized_pnl_usdc, fees_usdc, inventory, "
        "spread_bps, markout_extra_bps, fair) VALUES "
        + ",".join(values_sql)
        + " ON CONFLICT (stack, symbol, loop, time) DO NOTHING;"
    )
    run_psql(sql, url)


def ingest_stack(stack: str, artifacts: Path, url: str, account_id: str | None) -> int:
    state = load_state(artifacts)
    offsets: dict[str, int] = state.get("offsets", {})
    inserted = 0
    for symbol in SYMBOLS:
        log_file = artifacts / f"mm-bot-{slug(symbol)}.log"
        key = str(log_file)
        offset = int(offsets.get(key, 0))
        lines, new_offset = iter_new_lines(log_file, offset)
        batch: list[tuple] = []
        for line in lines:
            m = METRICS_RE.search(line)
            if not m:
                continue
            ts_m = LOG_TS_RE.match(line)
            if not ts_m:
                continue
            try:
                row = json.loads(m.group(2))
            except json.JSONDecodeError:
                continue
            if row.get("symbol") != symbol:
                continue
            t = parse_ts(ts_m.group(1))
            upl = row.get("unrealized_pnl")
            upl_f = float(upl) if upl is not None else None
            batch.append(
                (
                    t,
                    stack,
                    symbol,
                    int(row.get("loop") or 0),
                    account_id,
                    upl_f,
                    float(row.get("realized_pnl_usdc") or 0),
                    float(row.get("net_realized_pnl_usdc") or 0),
                    float(row.get("fees_usdc") or 0),
                    float(row.get("inventory") or 0),
                    float(row.get("spread_bps") or 0),
                    float(row.get("markout_extra_bps") or 0),
                    float(row.get("fair") or 0),
                )
            )
        if batch:
            psql_insert(url, batch)
            inserted += len(batch)
        offsets[key] = new_offset
    state["offsets"] = offsets
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(artifacts, state)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest MM_METRICS into TimescaleDB")
    parser.add_argument(
        "--stack",
        choices=["testnet", "devnet", "both"],
        default="both",
    )
    parser.add_argument("--once", action="store_true", help="Single pass (default for cron)")
    args = parser.parse_args()

    url = os.environ.get("MM_TSDB_URL")
    if not url:
        print("MM_TSDB_URL not set — source ~/scripts/mms/mm-db-env.sh", file=sys.stderr)
        return 1

    account_id = os.environ.get("GODARK_ACCOUNT_ID")
    stacks = ["testnet", "devnet"] if args.stack == "both" else [args.stack]
    total = 0
    for stack in stacks:
        artifacts = STACK_DIRS[stack]
        n = ingest_stack(stack, artifacts, url, account_id)
        print(f"ingest [{stack}] rows={n}")
        total += n
    print(f"ingest total rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
