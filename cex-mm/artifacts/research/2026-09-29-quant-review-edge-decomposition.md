# Quant memo: Where the loss comes from, and where a Delta market maker can earn
**Date:** 2026-09-29 · **Venue:** Delta India demo (fills), Delta India mainnet (public tickers) · **Symbols:** ETHUSD, BTCUSD; alt perps scanned
**Data:** all 3,842 account fills 2026-09-22 → 2026-09-29 from `GET /v2/fills`; Binance spot 1-second closes (data.binance.vision) for markouts; 8 mainnet ticker snapshots for spreads.
**Reproduce:** `.claude/skills/quant-researcher/scripts/` (`fetch_delta_fills.py`, `markout_report.py`, `scan_delta_markets.py`).

## Question
Why does the market maker lose money on Delta demo, and what changes would let it earn on a real account?

## Bottom line
1. **The strategy earns nothing before fees.** Gross edge per maker fill is between −0.1 and +0.4 bps. Fees are 2.12 bps per maker fill and 5.31 bps per taker fill. Fees are $55.29 of the $64.73 lost.
2. **Better adverse-selection control alone cannot fix it.** With zero markout, a maker fill still nets −1.3 bps (BTC) to −2.0 bps (ETH), because the spread captured at the fill is 0.2–0.8 bps against a 2.12 bps fee.
3. **The fix is where and how wide we quote, not more tuning of the same quote.** ETHUSD and BTCUSD are 1 tick wide on Delta mainnet (0.18 and 0.06 bps). Several Delta alt perps are 6–12 bps wide with $1–7M daily turnover and a Binance reference price. That is the only place in this data where the spread is larger than the fee.
4. **The quote engine is not the model it appears to be.** The Avellaneda–Stoikov volatility term rounds to zero, κ is never estimated, and the half-spread is the fixed 8 bps floor. After one fill, inventory skew saturates and the exit quote is pinned to 1 tick from fair.

## PnL attribution (venue fills, cash-flow, position flat at the end)

| Product | Fills | Gross trading PnL | Maker fees | Taker fees | Net |
|---|---:|---:|---:|---:|---:|
| ETHUSD | 2,576 | +$0.44 | $10.14 | $11.93 | **−$21.62** |
| BTCUSD | 1,266 | −$9.89 | $18.51 | $14.71 | **−$43.11** |
| Total | 3,842 | −$9.45 | $28.65 | $26.64 | **−$64.73** |

- 27% of fills and 48% of fees were taker fills, mostly on 09-23 → 09-27 while inventory ran to 10–20 contracts. Today's fills are all maker.

Per maker fill, notional-weighted (bps; capture is against Delta's mark at the fill, markout is Binance 1s mid change after the fill):

| | n | Capture | Markout 5s | 60s | 300s | Fee | **Net at 60s** |
|---|---:|---:|---:|---:|---:|---:|---:|
| ETHUSD maker | 1,758 | +0.16 | −0.25 | −0.05 | −0.83 | 2.12 | **−2.01** |
| BTCUSD maker | 1,024 | +0.81 | −0.40 | −0.53 | −1.06 | 2.12 | **−1.85** |
| ETHUSD taker | 792 | −0.15 | −0.17 | +0.28 | +0.73 | 5.31 | **−5.18** |
| BTCUSD taker | 241 | −0.06 | +0.03 | +0.14 | −1.62 | 5.31 | **−5.22** |

## Why the quoted 8 bps turns into 0.2 bps of capture

The bot rests quotes 8–12 bps from fair, but it fills almost only when the price has already come to the quote:

| Window before the maker fill | Median Binance move toward our quote | Fills with > 1 bp move toward us |
|---|---:|---:|
| 5 s | 1.8 bps | 70% |
| 30 s | 3.8 bps | 77% |
| 60 s | 4.5 bps | 71% |

A wide passive quote is an option that only gets exercised when it is at the money. By the time it fills, fair value is at our price, so the 8 bps is gone. This is the fill-probability / post-fill-return trade-off in `resource/02` §3.3.

A finding against the obvious fix: the fills after the largest moves (≥ 3 bps in 5 s, 784 fills) were the *least* bad (net −0.97 bps, capture +1.17). The worst were the slow-drift fills (−2.3 bps). A "pull the quote when Binance moves" fade would remove some of the better fills. Test it, but expect at most about 0.5 bps of improvement against a 2 bps gap.

## What the code actually does (vs the config)

| Intended | Actual | Where |
|---|---|---|
| AS half-spread `γσ²/2 + (2/γ)ln(1+γ/κ)` | σ enters as a fraction, so the vol term is about 0.007 bps. The arrival term is 1.2 bps. `max(as, fee_half=6, min_half=8)` is always 8 bps, or 12 bps when `vol_bps > 8` triggers the 1.5× multiplier. | `strategy.rs` `as_half_spread_bps`, `compute_quote` |
| κ from fill distances and the trade tape | `KappaEstimator` is created and never fed; κ is always 1.5 | `runner.rs` `kappa_est` |
| Inventory skew that grows with position | `MM_MAX_INVENTORY` = 1 order, so one fill sets `inv_ratio = ±1`: reservation moves 45 bps (30 skew + 15 boundary), the adding side switches off, and the exit quote clamps to fair ± 1 tick. Entry fills on sweeps, exit at the touch: the round trip keeps almost no spread. | `compute_quote`, `.env` |
| Event-driven quotes | Delta book polled over REST every 250 ms, loop every 400 ms, funding ticker fetched over REST on every loop, both sides edited one after another. Quotes can be 0.3–0.7 s stale. | `mm-delta/src/book.rs`, `runner.rs` |
| Bot-side PnL | `FillEconomics::on_fill` never realizes PnL when a long closes to flat (`0.0_f64.signum() == 1.0`) and resets entry on partial reduces. Delta fees are passed as 0. That is why the JSON shows 3,005 fills and $0 realized. | `economics.rs`, `handle_delta_fill_row` |
| OEMS fills and TCA | Supervisor never sets `MM_OEMS_URL`, so the bot posts nothing; `/api/fills` and `/api/tca` are empty. Bot stdout goes to /dev/null, so no `MM_METRICS` since 09-24. | `mm-oems` supervisor, `mm-bot/src/oems.rs` |
| Daily loss halt | `daily_pnl_usd` is never updated | `risk.rs` |

## Where the spread is (Delta India mainnet, 8 snapshots, 2026-09-29)

| Perp | Median spread (bps) | Spread in ticks | 24h turnover | Note |
|---|---:|---:|---:|---|
| BTCUSD | 0.06 | 1 | $1,231M | Tick-bound. Passive MM needs a rebate. |
| ETHUSD | 0.18 | 1 | $845M | Same |
| SOLUSD | 0.92 | ~90 | $234M | Below the fee |
| AVAXUSD | 5.2 | ~58 | $7.8M | Borderline |
| NEARUSD | 6.2–6.3 | ~30 | $1.7M | Candidate |
| ADAUSD | 9.7–11.9 | ~25–30 | $1.1M | Candidate: wide in bps, fine tick, so we can quote inside and be first |
| DOTUSD | 8.2 | 1 | $1.6M | Large-tick: one tick is 8 bps; queue position decides |
| ARUSD | 8.1 | 3.5 | $1.6M | Candidate, thin OI |
| MUBARAKUSD, AINUSD, RAREUSD | 6–12 | 1.5–5 | $1.5–7.4M | No reliable Binance reference; skip at first |

Delta turnover includes its own designated market makers, and alt books gap harder than majors. The candidates are hypotheses to test, not a forecast.

## Improvements, ranked by money at stake

### P0 — Measure correctly (without this, nothing below can be judged)
1. Pass `MM_OEMS_URL` from the supervisor to the bot and send the real Delta commission with each fill. The OEMS TCA tables then fill themselves.
2. Fix `FillEconomics::on_fill`: realize PnL on every reducing fill, including long → flat and partial reduces. Add unit tests for those three cases.
3. Send bot stdout to a rotating log file so `MM_METRICS` exists for research.
4. Rerun `markout_report.py` after each deploy with `--since <merge time>`. Judge by net at 60 s per maker fill over ≥ 300 fills.

### P1 — Quote where the spread pays (the only lever larger than the 2 bps gap)
5. **Shadow-run the existing engine on Delta mainnet alts, no keys, no money:** `mm-bot dry-run --venue delta --env mainnet --symbols ADAUSDT,NEARUSDT,AVAXUSDT`. Record Delta mainnet trades alongside, and count a simulated fill only when a trade prints strictly through our price (conservative queue model, as in hftbacktest). Go live only on pairs where simulated net-of-fee markout is positive over ≥ 1 week.
6. **Quote inside the spread on wide, fine-tick pairs (ADA, NEAR).** Anchor fair on Binance, set the half-spread from break-even: `half ≥ maker_fee + E[adverse at 60 s] + margin`, about 3.5–5 bps to start. Inside a 10 bps market we are first at our price, so fills come from ordinary taker flow instead of sweeps.
7. **Ask Delta about the Registered Market Maker program** (insti-support@delta.exchange). RMM gets zero fee at trade time plus cashback rebates, 200 live orders per contract (vs 50), batch edit of 50, and market maker protection. A rebate is the only change that makes BTC/ETH viable. Discounted fills are excluded from VIP and referral programs.

### P2 — Make the quote engine the model it claims to be
8. Replace the AS formula with a data-driven floor, or fix its units: σ in bps at the holding horizon, κ from a real fit (feed `KappaEstimator` from fills or trades). Today the only active spread input is `MM_MIN_HALF_SPREAD_BPS`.
9. Inventory: set `MM_MAX_INVENTORY` to 3–5 orders with linear skew of about one half-spread at the cap, so one fill does not saturate the skew. Price exits at `fair + fee + margin`, not `fair ± 1 tick`.
10. Calibrate the Binance lead per symbol on mainnet (β and lookback by regression on recorded data) instead of the fixed 0.8 × 3 s. Then test an asymmetric fade (pull only the side the market is moving toward) as its own experiment.

### P3 — Latency and venue plumbing
11. Delta public websocket order book instead of 250 ms REST polling; requote on book or Binance events, not on a 400 ms timer.
12. Cache funding once a minute; use batch edit (one call for both sides); arm Delta's dead-man switch (heartbeat / cancel-after) in case the process dies.
13. Measure order round-trip from the host. A WSL laptop behind a VPN is the slowest link in the chain.

## Next experiment (one knob)
**Hypothesis:** On ADAUSD mainnet, a quote 4 bps from Binance-anchored fair (inside the ~10 bps Delta touch) earns positive net-of-fee markout.
- Change: none to live trading. `dry-run` on Delta mainnet for ADAUSDT with `MM_MIN_HALF_SPREAD_BPS=4`, `MM_MAX_HALF_SPREAD_BPS=6`, plus a Delta mainnet trade recorder.
- Measure over 7 days: simulated fills per day, capture, markout at 5/60/300 s, net after 2.12 bps.
- Success: net at 60 s ≥ +0.5 bps per fill over ≥ 300 simulated fills.
- Stop: net below 0 after 300 fills. Try NEARUSD next, then consider a wider half-spread.

**Status (2026-09-29 11:55 UTC):** running as `cex-mm/scripts/shadow.sh` (run `artifacts/shadow/20260929T115546Z`, ADAUSDT + NEARUSDT). Evaluate with `scripts/shadow.sh report --sweep 3,4,5,6,8 --latencies 0,300,1000`.

**Found while setting it up:** `fstream.binance.com` does not resolve on this network, and the live demo bot has no Binance connection. The Binance-move lead merged today (PR #11) is therefore a no-op in the live bot unless the VPN is on. The shadow run uses Binance's public spot mirror (`MM_BINANCE_WS_BASE=wss://data-stream.binance.vision/ws`).

## Limits
- Demo fills measure plumbing. Demo flow and the demo Delta–Binance basis (mean −11.9 bps, sd 30.5 bps) differ from mainnet.
- Capture uses Delta's mark price as fair; markouts use Binance spot, not Delta's own mid.
- Mainnet spreads are 8 snapshots over 2 minutes on one afternoon. Rerun `scan_delta_markets.py` at several times of day before choosing a pair.

## Sources
- Delta market makers' guide: https://guides.delta.exchange/delta-exchange-user-guide/market-makers-guide
- Delta API (rate limits, batch size 50, dead-man switch, websocket channels): https://docs.delta.exchange/
- Delta fees (18% GST): https://www.delta.exchange/fees
- Adverse selection in crypto perps (touch quoting nets −0.4 to −0.8 bp before fees): https://github.com/DaruFinance/crypto-adverse-selection
- Informed vs retail flow for passive makers: https://multicoin.capital/2026/02/17/adverse-selection-rules-everything-around-me/
