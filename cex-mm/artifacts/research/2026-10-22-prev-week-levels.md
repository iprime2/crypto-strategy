# Quant memo: previous-week highs and lows on crypto perps. The reel's three trades fail; the level is real but not tradable at Delta costs
**Date:** 2026-10-22 · **Venue:** Binance USDT-M perps and spot as the long-history proxy, Delta India public 1 h candles (no orders, no keys) · **Symbols:** the running nine (BTC ETH XRP BNB ADA LTC LINK DOGE BCH); 25 coins for breadth (the nine plus 16 ex-ante perps); out of sample, 13 spot pairs 2017–2020 and 15 perps chosen by 2021-Q4 volume · **Data:** Binance 5 m klines 2020-05..2026-09 (nine), Binance 1 h 2020-05..2026-09 (25), Delta 1 h 2025-01..2026-10 (nine), Binance spot 5 m 2017-08..2020-04, Binance perp 5 m 2021-12..2026-09 (15) · **Evidence:** `cex-mm/artifacts/research/2026-10-22-prev-week-levels-evidence/` (both frozen plans with sha256, the engines, results, events, data audits, the literature note and the workflow records of every check)

## Question
The user shared a Quantlab reel (https://www.instagram.com/reel/Dd8vV7ZMbPs/ [UNVERIFIED: transcript supplied by the user]). On the NASDAQ it found:
- price reached at least one previous-week level in 91.9 % of weeks and the previous-week high (PWH) in 64.2 %;
- price "rejected" within 60 minutes of touching the PWH only 40.4 % of the time;
- after a confirmed breakout price continued 78.9 % of the time, but 77.6 % at control levels a similar distance away, so the level itself had no edge.

The user asked whether this can be used on crypto, and for a backtest if so.

How it was tested:
- **Phase 1, the reel's three trades** (`plan.md`, sha256 `8c7bf923...f19a`, frozen before any run):
  - F, fade at the first touch with a resting limit;
  - B, breakout entered at the first 1 h close beyond the level;
  - S, failed breakout entered at the first 1 h close back inside.

  Each was scored as a trade after Delta costs: taker 5.31 bps plus 2 bps slippage a side, maker 2.12 bps. Each was compared with the reel's control, levels at 0.5–1.5 times the real level's distance from the week open (P1). Weeks run Monday 00:00 UTC to Monday. Uncertainty comes from a week-cluster bootstrap with 2,000 draws.
- **Phase 2, one confirmation test** (`phase2_plan.md`, sha256 `940a391b...40f2`, frozen before any run). It tests a trade that Phase 1 suggested but did not register: enter in the breakout direction at the first touch (T). It runs once, on data Phase 1 never used.
- **Engineering.**
  - Phase 1: two independent implementations of the plan agreed on every number once four ambiguous readings were settled. Three adversarial checks followed (look-ahead and fills; controls and statistics; data). One blocking data defect was fixed and re-checked: 120 missing hourly bars on the 25-coin panel in 2022.
  - Phase 2: an independent recompute matched the run, and an adversarial review found nothing that changes a verdict.

## Outcome
- **Do not use the reel's trades.** Fading, confirmed breakouts and failed breakouts all fail every pre-registered rule, on every panel. Fading at the level is the worst trade of all.
- **On crypto the level is real, unlike the reel's NASDAQ result.** At the first touch of the real PWH or PWL, price keeps running through the level much more than at the control levels. This holds:
  - on all five panels;
  - in every calendar year of the 2020–26 panel and of the 2022–26 out-of-sample panel (real minus control, 4 h).

  The likeliest cause is stop-loss and liquidation orders clustered just beyond obvious highs and lows (Osler 2003, 2005 [UNVERIFIED], in `literature/literature.md`).
- **It is not a strategy at Delta's costs.**
  - The move is about 20–30 bps over 4 h in recent years, and half or more of it comes in the first hour (4 h gross +22.4 bps, of which +15.1 by 1 h, on the 15 unseen perps; +33.0, of which +17.7, on the nine).
  - A stop entry pays taker fees on both sides: 14.62 bps at base, 30.62 bps with 10 bps slippage.
  - On the 15 unseen perps (2022–26) it made +7.8 bps per trade after base costs (P 0.25). It lost in 2023 and 2024, and it lost −8.2 bps at stress costs.
  - Under the frozen rule the touch-breakout is rejected. No paper book, no order path, nothing changed in the bot or the trend books.
- **Where it may still be useful: as a risk signal for the market maker, not as a trade.** A resting quote on the side price is running toward is the order that gets run over when stops trigger at the level. See Next experiment.

## Findings, ranked by money at stake
| # | Finding | Numbers | Source |
|---|---|---|---|
| 1 | Fading the first touch (the reel's "rejection" trade) loses, and loses more at the real level than at the controls | 4 h, gross bps, real vs P1 (difference, 95 % CI): Binance 5 m nine −33.0 vs −6.8 (−26.2, −34.6 to −17.9); 25 coins 1 h −16.2 vs +0.6 (−16.8, −22.8 to −10.9); Delta 1 h −41.9 vs −28.3 (−13.6, −26.5 to −1.0). Net of costs: −42.5 / −25.7 / −51.4. Negative in both halves and on 0 of 9 coins positive | `phase1/judge_out.txt`; `phase1/engine/results.json` |
| 2 | Confirmed breakouts (first 1 h close beyond) do no better than at the controls, as the reel found | 24 h, nine coins: real +27.7 gross / +13.0 net vs P1 +34.2 (difference −6.5, P 0.77); halves +48.4 / −20.5 net; 5 of 9 coins. 25 coins: −10.8 net. Delta: −51.1 net. Reel-style "continued" rate 72.5 % at the real level vs 70.5 % at the controls | `phase1/judge_out.txt` |
| 3 | Failed breakouts lose | 4 h net: −30.1 (nine), −28.9 (25 coins), −40.4 (Delta); real minus P1 −10.7 / −12.7 / −7.4 | `phase1/judge_out.txt` |
| 4 | The level effect replicates out of sample, so it is real | Touch-breakout T, 4 h, real minus P1 gross: spot 2017–20 +42.0 (CI +26.6 to +57.6), 15 unseen perps 2022–26 +19.4 (+9.8 to +28.8), P < 0.001 on both; positive in every year on both. Against the shifted-calendar control (weeks anchored Thursday 12:00), real minus P3 is +33.3 (P 0.016) on spot and +7.2 (P 0.30) on the unseen perps, so part of it belongs to the Monday week and part to any recent 7-day extreme | `phase2/engine/results.json`; `phase2/summary_table.txt` |
| 5 | The touch-breakout is not tradable after Delta costs in the recent regime | 4 h net at base / stress costs: spot 2017–20 +43.9 (P 0.0005) / +27.9; 15 perps 2022–26 +7.8 (P 0.25) / −8.2, halves −1.9 / +18.4, by year 2022 +10.1, 2023 −22.8, 2024 −6.1, 2025 +51.2, 2026 +14.8; the nine 2020–26 +18.4 (P 0.02) / +2.4. Fails the frozen rule on the 2022–26 panel (tests 1 and 3) | `phase2/engine/results.json`; `phase2/workflow_result.json` (run gating) |
| 6 | Even the 2017–20 pass is fragile | It rests on 5 weeks (fails without them), fails test 1 with a wider coin list (net +27.8) and fails under a fill at the touch-bar close or at the level + 20 bps | `phase2/workflow_result.json` (adversarial findings) |
| 7 | The reel's descriptive numbers carry over roughly, and they say nothing about edge | Weeks touching PWH or PWL 80.1 % (nine; reel 91.9 % on NASDAQ), PWH 47.3 %, PWL 42.6 %. "Rejected within 60 min" 44.2 % at the real level vs 54.6 % at the controls (reel 40.4 %) | `phase1/judge_out.txt` |

## What the code actually does
- **Nothing in the repo changed apart from this memo, its evidence and one row in resource/07's rejected table.** No file under `cex-mm/scripts/`, `quote-bot/`, `backend/` or `web/` changed, and no order was placed. The paper books, the shadow test and the live ADA market-making run (another session's) were not touched.
- **The engines are research code.** They live in the evidence pack and are not wired to any book or order path. They use absolute paths under the session scratchpad, which is not kept.
- **The touch-breakout has no execution path in the repo.** Trading it would need resting stop orders at the levels. That is a taker path, which the market-making bot's invariants forbid except for reduce-only risk exits (`.claude/rules/cex-mm.md`). It would need a separate design and the user's approval.

## Next experiment (one knob, metric, success, stop)
**Use the level as a quote-pull signal for the market maker, measured before anything is built.**
- **Question.** Are fills near a first touch of PWH or PWL more adversely selected than other fills? These are fills on the side price is running toward, in the minutes after the touch.
- **Data.** The existing live and shadow fill logs for ADAUSD on Delta, with Delta 1 h or Binance 5 m prices for the levels. Read-only.
- **Metric.** Signed markouts at 5 s / 30 s / 5 min for fills within 15 minutes after a first touch, against all other fills. Use the same week-cluster bootstrap. Run the same comparison at P1 control levels.
- **Success.** The touch fills' 30 s markout is worse than both the other fills and the P1-touch fills, by more than the 2.12 bps maker fee. Only then would one knob be proposed: pull the quote on the side being approached for N minutes after a first touch (*(start)* N = 15). It would go through the usual demo, then shadow, then live gates.
- **Stop.** No difference, or too few touch fills (under 100). Then the level idea is closed for this repo.

## Limits
- **Binance is a proxy for Delta.** Delta's own sample is 1 h bars for 2025–26 (828 coin-weeks). That is too short and too coarse to judge a trade whose move is mostly in the first hour.
- **Fills are modelled, not observed.** Stop-entry fills at the level plus 2 bps are optimistic in fast touches; the 10 bps stress line is the more honest reading. Fade fills at the level ignore queue position, which only makes the fade look better than it is.
- **The out-of-sample perps share Phase 1's calendar (2022–26).** They are new coins, not new years. The spot panel is new years but spot, and its short leg was not tradable on spot then.
- **Departures from the frozen plans, none of which changes a verdict:**
  - Phase 1: the window-shifted control P2 is always beyond the real level by construction, so it cannot test the calendar week as intended. It did not gate, and Phase 2's P3 replaced it.
  - Phase 1: the 25-coin panel's 2022 hourly holes were patched from Binance's daily files, after the data check found them.
  - Phase 2: the 15 out-of-sample perps were ranked over the union of the two daily caches (`universe/cache_all/` and `universe/cache/`), because the plan's named folder alone skips most large coins. The ranking used only 2021-Q4 volumes and was written before any 5 m data was downloaded (`phase2/data_ox/selection.csv`).
  - Phase 2: the last spot event week is 2020-04-13, not 2020-04-20, because a maintenance outage leaves that week under the 99 % bar rule.
