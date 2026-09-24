# Backtest artifacts (Slices 7 / 7b)

## Recorder → replay

1. Record feeds: `cargo run -p mm-bot -- record --symbol BTCUSDT --duration 3600`
2. Convert JSONL to hftbacktest input (column map documented below).

## hftbacktest 2.4.4 (Slice 7b)

```bash
python3 -m venv .venv-backtest
source .venv-backtest/bin/activate
pip install 'hftbacktest==2.4.4' pandas pyarrow

python scripts/hftbacktest_glft_compare.py \
  --recording artifacts/recordings/BTCUSDT_*.jsonl \
  --out artifacts/backtest/report.json
```

The script compares:

- GoDark-calibrated AS params (from `MM_*` env defaults)
- GLFT notebook-style A/k calibration on the same replay window

Queue model: `RiskAdverseQueueModel` with documented latency (WSL local default 5–20ms).

Outputs: `artifacts/backtest/report.json` and `artifacts/backtest/summary.md`.

## Assumptions

- Post-only fills; no hidden taker unless reduce-only flatten
- Bybit ob500 or self-recorded L1/L2
- Testnet replay is **not** a mainnet promotion criterion
