# CEX-MM dashboard telemetry

Use when editing `cex-mm/dashboard/` (Python tail + static UI).

## Data sources

- **MM_METRICS** JSON lines in `artifacts/delta-mm-run.log` (or `MM_LOG_PATH`)
- **MM_ORDER** / rejects / L3 warnings from same log
- **Economics** JSON under `artifacts/economics/{SYMBOL}.json`

## Active vs inactive symbols

- **Active:** `MM_SYMBOLS` from `cex-mm/.env` (what the bot trades)
- **Inactive cards:** `MM_DASHBOARD_INACTIVE` env (default `SOLUSDT`) — shown grayed out with last snapshot only

## Run

```bash
./scripts/run_dashboard.sh
# http://127.0.0.1:8787/
```

Restart dashboard after `server.py` changes (Python does not hot-reload).

## UI conventions

- Tooltips on KPI labels (`?` circle, `title=`)
- Benchmark table: fair vs Binance mid vs venue mid
- **Delta P&L strip:** `venue_pnl` from `dashboard/delta_pnl.py` (REST positions + wallet; poll ~8s)
- Charts: fair, Binance, venue mid (dashed), spread bps (right axis)
