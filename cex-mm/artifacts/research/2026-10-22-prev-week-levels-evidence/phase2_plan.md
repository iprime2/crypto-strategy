# Pre-registered Phase 2: out-of-sample test of the touch-breakout at previous-week highs and lows (frozen 2026-10-22, before any run)

## 0. Why this exists
Phase 1 (`plan.md`, sha256 8c7bf923...f19a; results `final/results.json`, judged in `judge_out.txt`) found none of the three
pre-registered patterns passes. It also found, unplanned, the mirror image of the fade: at the first touch of the real PWH / PWL price
keeps running through the level much more than at the price-shifted controls (fade gross 4 h, real vs P1: A −33.04 vs −6.85 bps,
B −16.22 vs +0.62, C −41.94 vs −28.31; the 95 % CIs of the difference exclude 0 on A, B and C). Entering in the breakout direction at the touch would have
earned +33.04 bps gross at 4 h on A (+18.42 net of 14.62 bps), +16.22 on B (+1.60 net), +41.94 on C (+27.32 net). The literature
names a mechanism: stop-loss and liquidation orders cluster just beyond salient levels, so crossings run fast for hours (Osler 2003,
2005 [UNVERIFIED]). Because the idea came from the Phase 1 data, those numbers are not evidence. This plan tests it once, on data
Phase 1 never used. No parameter below is tuned after a run.

## 1. Rule under test (T, touch-breakout)
Levels, weeks, first-touch rule and the P1 controls exactly as Phase 1 `plan.md` sections 1–3 (Monday 00:00 UTC weeks; PWH/PWL from
week w−1; first bar with high > L·(1 + 0.5 bp) or low < L·(1 − 0.5 bp); P1 at m ∈ {0.5, 0.75, 1.25, 1.5} of the distance from the
week open; 99 % bar-coverage rule for the week and the prior week).
- Entry: at the first touch, in the breakout direction (buy at PWH, sell at PWL), as a stop order filled at L (the fill price used
  for the gross return; slippage is charged in costs).
- Exit: the close of the bar that ends h after the touch bar opens, h ∈ {1 h, 4 h, 24 h}. **Primary h = 4 h.**
- Gross = signed return from L to the exit close in the breakout direction (equals minus the Phase 1 fade gross).
- Costs, both sides taker: base 5.31 + 2 bps slippage per side = 14.62 round trip; stress 5.31 + 10 = 30.62 round trip.

## 2. Out-of-sample panels (5 m bars; none used in Phase 1)
- **OT, out of time: Binance SPOT 5 m klines, from the first week with a full prior week through the event week starting 2020-04-20** (Phase 1's first event week was 2020-05-04), for the
  USDT pairs with continuous history in that window: BTC, ETH, BNB, LTC, NEO, XRP, ADA, EOS, XLM, TRX, ETC, LINK, DOGE (each from its
  first full prior week). Source `data.binance.vision/data/spot/monthly/klines/<SYM>USDT/5m/`. Spot has no funding; the cost model is
  unchanged.
- **OX, out of cross-section: Binance USDT-M perps 5 m, 2022-01-03..2026-09-21 weeks**, for 15 coins chosen mechanically before any
  price outcome is looked at: among USDT-M perps whose first daily bar is on or before 2021-09-30, excluding the 25 Phase 1 coins and
  index or synthetic contracts (DEFIUSDT, BTCDOMUSDT, and any name ending in INDEX), rank by median daily quote volume over
  2021-10-01..2021-12-31 (from `universe/cache_all/`) and take the top 15. Delisted coins stay in until their last full week. Source
  `data.binance.vision/data/futures/um/monthly/klines/<SYM>/5m/`, checked against the S3 listing and checksums; monthly holes are
  patched from daily files and logged.

## 3. Controls and statistics
- P1 as Phase 1 (pooled; also reported split into m < 1, levels inside last week's range, and m > 1, levels beyond it).
- **P3, shifted calendar (reported, not gating):** the same construction with weeks anchored at Thursday 12:00 UTC instead of Monday
  00:00 (the "previous week" is the 168 h before that anchor). If T at P3 matches T at the Monday PWH, the effect belongs to any
  7-day extreme, not to the calendar week.
- Week-cluster bootstrap as Phase 1: 2,000 draws, default_rng(11), resample (Monday) weeks with replacement; one-sided P.
- Halves: OT 2017-08..2018-12 and 2019-01..2020-04; OX 2022-01..2024-04 and 2024-05..2026-09.

## 4. Pass rule (all must hold on BOTH OT and OX at h = 4 h; else "no edge, do nothing")
1. Real net mean at base costs > 0, with one-sided P(net ≤ 0) ≤ 0.01.
2. Real − P1 gross > 0, with one-sided P(diff ≤ 0) ≤ 0.01.
3. Real net > 0 in both halves of the panel.
4. Real net > 0 on at least two thirds of the panel's coins (OT 9 of 13, OX 10 of 15).
Reported beside it: the stress-cost net, 1 h and 24 h, real − P3, P1 split by m, the daily-P&L Sharpe (equal notional per event,
booked on the exit day), and the per-year means.

## 5. What follows
- Fail: record the touch-breakout as rejected with these numbers; no further work on it.
- Pass: a Phase 3 strategy backtest, frozen before it runs, on Delta (panel C prices, 2025–26, in-sample there and labelled so) and on
  OX, in whole Delta contracts at $1,000 and $5,000 with one position per coin, including the daily-return correlation with the two
  trend paper books. Trading it would need a stop-order entry path, which the repo does not have and which breaks the market-making
  bot's post-only rule, so even a paper book needs the user's explicit go-ahead.

## 6. Engineering
Implemented by extending the reconciled Phase 1 engine (`final/`) with the new loaders, P3 and T only. An independent check
recomputes the four gating numbers on both panels with separate code and must match to 0.1 bps and 1 event, plus an adversarial
review of data, fills and look-ahead, as in Phase 1.
