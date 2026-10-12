# Mainnet promotion gate (Slice 8)

Testnet validates **plumbing**; mainnet validates **edge**. Do not promote on testnet PnL alone.

## Preconditions

- [ ] `cargo test -p mm-core -p mm-bot` green
- [ ] Testnet: 30+ minutes stable run, no reject storm, `MM_METRICS` sane
- [ ] Fire drill: `scripts/fire_drill.sh` cancel-all under 2s
- [ ] Slice 7b backtest report in `artifacts/backtest/` (hftbacktest 2.4.4, queue model documented)

## Symbol selection

- Pick symbol from ≥1 week recorder output (`artifacts/recordings/`)
- Prefer tight tick, stable depth, moderate vol

## Small live (mainnet)

1. Read+Trade API keys only; start at min lot; wide half-spread (≥2× backtest-calibrated)
2. Run 48h monitor, then 4 weeks per [STRATEGY.md §11.3](../../STRATEGY.md)
   (on the Tokyo VM: `scripts/live.sh` next to the shadow test; `scripts/live.sh report` compares real fills
   with the simulator over the same window)
3. Evidence to collect:
   - Signed markout at 1s/5s/30s (and 100ms/1m/5m when enabled)
   - Toxicity ratio < 0.7 at 10s
   - No unreconciled positions vs exchange
   - Positive quoter score trend (spread + rebate − adverse − fees)
   - Exchange realized PnL export / screenshot

## Rollback

- `cargo run -p mm-bot -- cancel-all --env mainnet`
- Set `MM_HALT=1` or kill process; verify flat or reduce-only per runbook
