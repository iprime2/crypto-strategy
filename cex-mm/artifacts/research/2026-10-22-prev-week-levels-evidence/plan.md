# Pre-registered plan: previous-week high / low levels on crypto perps (frozen 2026-10-22, before any run)

## 0. Question and claim under test
Source: a Quantlab Instagram reel (https://www.instagram.com/reel/Dd8vV7ZMbPs/ [UNVERIFIED: transcript supplied by the user, not watched]).
Its NASDAQ claims: price reached at least one previous-week level in 91.9 % of weeks, the previous-week high (PWH) in 64.2 %;
at the PWH price "rejected within the next 60 minutes" only 40.4 % of the time; after a confirmed breakout price continued in the
breakout direction 78.9 % of the time, but at comparable control levels at a similar distance the figure was 77.6 %, so the level
itself had no edge.

Question for us: on the crypto perps we can trade (Delta India; Binance USDT-M as the long-history proxy), do PWH / PWL levels carry
an edge that survives (a) a matched control level and (b) Delta costs? If yes, is any of the three patterns tradable?

Priors, stated before running: the reel's own result is null. A mechanism exists for crypto: stop-loss and liquidation orders cluster
just beyond obvious highs and lows, so breakouts through such levels may run further and faster than through arbitrary prices
(Osler, "Currency orders and exchange-rate dynamics", stop-loss clustering and price cascades in FX [UNVERIFIED]). A breakout effect
that is not level-specific is ordinary short-horizon momentum; our daily trend rule already holds that exposure, and the 2026-10-22
study rejected Donchian-style breakouts at the daily horizon (SIG-4, SIG-11).

## 1. Data and panels
- **A (primary): Binance USDT-M perp 5 m klines, the nine** (BTC ETH XRP BNB ADA LTC LINK DOGE BCH), 2020-05-01..2026-09-30.
  2024-01..2026-09 is on disk (`universe/klines5m/`); 2020-01..2023-12 is downloaded from data.binance.vision
  (`data/futures/um/monthly/klines/<SYM>USDT/5m/`) and checked against the S3 listing; any missing month is reported, never silently dropped.
  DOGE starts with its first full prior week after its 2020-07-10 listing.
- **B (breadth): Binance USDT-M 1 h, 25 coins** (the nine from `hourly/<SYM>USDT-1h.csv` plus the 16 ex-ante perps in
  `universe/hourly_extra/`), same window, events at 1 h resolution.
- **C (venue): Delta India 1 h, the nine** (`research2/delta_data/hourly_<SYM>USD.json`), 2025-01..2026-10 (full weeks only; the first week with a full prior week starts 2025-01-13).
- Timestamps: Binance open time in ms (µs when > 1e14). All times UTC.
- A week is Monday 00:00 to the next Monday 00:00 UTC (TradingView's weekly candle). A coin-week is used only if it and the prior
  week each have ≥ 99 % of their bars; otherwise it is skipped and counted.

## 2. Levels
For coin c and week w: PWH = max high of week w−1, PWL = min low of week w−1, O = open of the first bar of week w (always inside
[PWL, PWH], since the market trades 24/7). D_H = ln(PWH/O) > 0, D_L = ln(O/PWL) > 0.

**Controls (placebo levels), computed the same way and scored with exactly the same event and outcome code:**
- **P1, price-shifted (the reel's control):** for each real level, four placebo levels on the same side at multiples m ∈ {0.5, 0.75,
  1.25, 1.5} of its distance from the week open: O·exp(+m·D_H) above, O·exp(−m·D_L) below. Same week, same first-touch rule.
- **P2, window-shifted (is the calendar week special?):** the high and low of the 7 × 24 h window that ends 84 h before week w starts
  (Thursday 12:00 UTC to Thursday 12:00 UTC); a P2 level is used only if no bar between the window end and the week-w start traded
  beyond it (an unbroken recent extreme, like the PWH at the week start), and only if it differs from the PWH / PWL by ≥ 10 bps.

## 3. Events and outcomes
One event per level per coin-week: the **first touch**, the first bar t in week w with high_t > L·(1 + 0.5 bp) (above) or
low_t < L·(1 − 0.5 bp) (below). Only touches inside week w count. Outcomes whose exit falls after the data end are dropped.
Costs per side (bps of notional): taker 5.31 + 2 slippage = 7.31; maker 2.12 (Delta retail incl. GST, the repo's model).

- **F, fade at the touch:** sell at L (above) / buy at L (below) with a resting limit, filled at L on the touch bar. Exit at the close
  of the bar that ends h after the touch bar opens, h ∈ {1 h, 4 h, 24 h}. Return signed in the fade direction. Net = gross − 2.12 − 7.31.
- **B, breakout continuation:** confirmation = the first close of a 1 h bar (aligned on the hour; on panel A built from 5 m bars) beyond L
  at or after the touch, inside week w. Enter at that close (taker), exit at the close h ∈ {1 h, 4 h, 24 h} later, signed in the breakout
  direction. Net = gross − 14.62.
- **S, sweep and reclaim (failed breakout):** after the touch, if a 1 h close back inside L comes within 4 h of the touch and before any
  1 h close beyond L, enter at that close against the break (taker), exit h ∈ {1 h, 4 h, 24 h} later. Net = gross − 14.62.
- **Reel-style descriptive rates (no trading meaning):** touch rates per coin-week (any level; PWH; PWL); "rejected within 60 min" =
  within the 60 min after the touch, a 5 m close at least r inside L before any 5 m close at least r beyond it, r = 10 bps; "continued"
  = after confirmation, price trades a further r beyond the confirming close before trading back to L, within 24 h.

Primary horizon: 4 h for F and S, 24 h for B. Sides H and L are pooled (each signed in its own direction) and also reported separately.

## 4. Statistics
- Unit: one event. Means of gross and net bps; hit rate (net > 0).
- Uncertainty: **week-cluster bootstrap** (resample weeks with replacement, 2,000 draws, seed 11; all coins' events in a week move
  together), for the real mean, the pooled-placebo mean and the difference real − placebo (placebo events from the same resampled
  weeks). One-sided P(difference ≤ 0).
- Halves: 2020-05..2023-06 and 2023-07..2026-09 (panel A, B); per coin (panel A).
- A daily P&L series per pattern (equal notional per event, booked on the exit day) gives an annualised Sharpe, as information.

## 5. Pass rules (fixed now; any failure means "no edge" / "do nothing")
**Level edge (pattern p):** all of
1. A primary horizon: real − P1 ≥ +5 bps gross and one-sided P ≤ 0.003 (0.05 / 18 tests: 3 patterns × 3 horizons × 2 controls);
2. real − P1 > 0 in both halves on A;
3. ≥ 6 of the 9 coins with real − P1 > 0 on A;
4. real − P1 > 0 on B at the primary horizon.
P2 and C are reported next to it; they qualify the reading (calendar-specific or any recent extreme; Delta sample) but do not gate.

**Tradable pattern (with or without a level edge):** all of
1. A primary horizon: real net mean > 0 with one-sided P(net ≤ 0) ≤ 0.003;
2. net > 0 in both halves on A, on ≥ 6 of 9 coins, and on B;
3. net > 0 on C (Delta 1 h, information only if fewer than 300 events).

## 6. What follows
- If nothing passes: report the null with the numbers; no strategy backtest beyond this event study, which already is one trade per event
  with costs. No parameter in sections 2–5 is changed after a run.
- If a tradable pattern passes: a Phase 2 backtest, frozen before it runs, of exactly that rule on C and A at $1,000 and $5,000 in whole
  Delta contracts, one position per coin, with the daily-return correlation to the two trend paper books. A paper book would need the
  user's go-ahead; nothing here places an order.

## 7. Engineering
Two independent implementations from this text (separate folders, no shared code) must agree before any number is reported; any
disagreement above 0.1 bps in a mean or 1 event in a count is traced to its cause. Then an adversarial check for look-ahead, fill
optimism (limit fills at L on the touch bar; confirmation closes), placebo validity and the clustering.
