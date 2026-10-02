---
paths:
  - "cex-mm/**"
---

# cex-mm stack and trading invariants

## Crate boundaries

- `mm-core`: pure quote, fair-value, regime, OFI, markout and economics math. No I/O. Every behavior change comes with a unit test in the same module.
- `mm-delta`, `mm-bybit`, `mm-binance`: thin venue I/O. Parse venue JSON defensively (skip malformed messages, never panic). No secrets in logs.
- `mm-bot`: orchestration only (per-symbol loop, OMS, risk, recorder, CLI). Quote math stays in `mm-core`.
- `mm-oems`: book of record and process supervisor. It never computes quotes.
- Rust 2021, tokio, workspace dependency versions from `cex-mm/Cargo.toml`. Do not add heavy dependencies without a reason.
- Business numbers come from `STRATEGY.md` / `resource/`. Do not write parallel strategy docs inside `cex-mm/` (runbooks in `docs/` and `README.md` are fine).

## Config

- Every new env knob gets a default in code and a line in `config/example.env`. Follow the existing per-symbol override pattern (`KEY_ETHUSDT`) where sizing already uses it.
- Secrets only in gitignored `cex-mm/.env` and `cex-mm/quote-bot/.env`.

## Trading invariants (do not break without the user's explicit approval)

1. Quoting orders are post-only. The only taker path is reduce-only for a hard-cap or risk exit.
2. Cancel-all stays reachable: `mm-bot cancel-all`, `scripts/fire_drill.sh`, and cancel on start. Any new order-entry path must be covered by cancel-all.
3. On stale book, L3 regime, or reject storm, cancel before re-quoting.
4. Signed markouts are logged before any edge claim. Spread is tightened only on markout evidence.
5. Respect venue rate limits (Delta: 20,000 weight per 5 min; place/edit 5, batch 25).

## Known code gaps (verify before relying on the feature)

- `StrategyConfig::as_half_spread_bps` vol term uses σ as a fraction and is ~0; the half-spread is effectively `MM_MIN_HALF_SPREAD_BPS`.
- `KappaEstimator` in `runner.rs` is never fed; κ is always `MM_AS_KAPPA`.
- `FillEconomics::on_fill` does not realize PnL when a long closes to flat or on partial reduces; Delta fees are passed as 0.
- `RiskState::daily_pnl_usd` is never updated, so the daily loss halt cannot fire.
- The Delta book is polled over REST every 250 ms unless `MM_DELTA_BOOK_FEED=ws` (public `ob_l1` websocket; the shadow test uses it). Funding is fetched over REST on every loop. A book with no feed update for `MM_BOOK_STALE_MS` (default 2000) cancels quotes once and pauses quoting until fresh (`BookWatch` in `mm-bot/src/risk.rs`).
