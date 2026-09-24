# Practitioner Knowledge on Crypto Market Making (blogs, docs, talks, forums)

Compiled 2026-09-20 for the OKX / Binance / Bybit market-making bot design.
Scope: practitioner sources only (docs, blogs, interviews, forum threads, open-source READMEs). Academic papers live in `01-*`.

Conventions:
- Every claim carries a URL. Numbers quoted from sources are the source's numbers, not ours.
- `[UNVERIFIED]` = we could not open the page or confirm the number ourselves (e.g. Reddit blocks fetches; only search snippets were visible).
- `[SYNTHETIC]` = the source labels its own numbers as illustrative/synthetic, not measured.
- "Actionable for our bot" lines are our translation into design decisions.

---

## 1. Hummingbot docs & blog (PMM, Avellaneda-Stoikov, liquidity mining, V2 controllers)

### 1.1 Pure Market Making (PMM) strategy reference
- Title: Pure Market Making (PMM) — Hummingbot docs (v1 strategies)
- Author/site: Hummingbot Foundation; Date: current docs (undated page)
- URL: https://hummingbot.org/strategies/v1-strategies/pure-market-making/
- Key takeaways:
  - Core loop: place bid at `mid*(1-bid_spread)` and ask at `mid*(1+ask_spread)`; every `order_refresh_time` seconds cancel and re-place. Strategy runs tick-by-tick (default 1 s tick), each order gets an expiry = `order_refresh_time`.
  - Defaults worth knowing: `max_order_age` 1800 s; `filled_order_delay` 60 s; `inventory_target_base_pct` 50; `inventory_range_multiplier` 50 (tolerable inventory range expressed in multiples of total order size); `hanging_orders_cancel_pct` 10 (%); `order_refresh_tolerance_pct` 0; `minimum_spread` -100 (disabled); `price_band_refresh_time` 86400 s; `custom_api_update_interval` 5 s (min 0.5 s).
  - `order_refresh_tolerance_pct`: skip the cancel/replace cycle if the new price is within X% of the existing order — the built-in hysteresis knob that reduces churn.
  - `order_levels` / `order_level_spread` / `order_level_amount` build a ladder; `bid_order_level_spreads`/`ask_order_level_spreads` give arbitrary per-level ladders.
  - `inventory_skew_enabled`: resizes bid vs ask amounts to steer toward `inventory_target_base_pct` within `inventory_range_multiplier`.
  - `hanging_orders_enabled`: when one side fills, the opposite order is left resting (not refreshed) until its distance from mid exceeds `hanging_orders_cancel_pct`.
  - `order_optimization_enabled` (formerly "penny jumping"): moves orders to one tick better than top-of-book, ignoring dust orders up to `*_order_optimization_depth` (base units). The Medium post describes the bot re-jumping competitors down to your spread floor (https://medium.com/hummingbot/how-to-navigate-hummingbots-advanced-market-making-features-59233df773b8).
  - `price_ceiling`/`price_floor` (+ `moving_price_band_enabled`, `price_ceiling_pct`): above the ceiling only sells are placed, below the floor only buys — a crude regime/trend guard.
  - `price_source` can be `external_market` (quote off another exchange's book) or `custom_api`; `price_type` includes `mid_price`, `last_price`, `best_bid/ask`, `inventory_cost`.
  - `take_if_crossed`, `add_transaction_costs`, `ping_pong_enabled`, `should_wait_order_cancel_confirmation` are the remaining execution toggles.
  - Source code default signature (`init_params`): `order_refresh_time=30.0`, `max_order_age=1800`, `filled_order_delay=60`, `hanging_orders_cancel_pct=0.1`, `status_report_interval=900` (https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making.pyx).
- Actionable for our bot: reproduce the PMM knob set as our baseline config surface (spreads, refresh, refresh-tolerance/hysteresis, max order age, filled-order delay, hanging orders, ladder, inventory target/range, price bands, external price source). It is the de-facto vocabulary retail MMs already understand.

### 1.2 Filled Order Delay (why it exists)
- Title: Filled Order Delay — Hummingbot docs
- URL: https://hummingbot.org/strategies/v1-strategies/strategy-configs/filled-order-delay/
- Key takeaways:
  - Purpose: after any fill, wait `filled_order_delay` seconds before placing the next pair, to stop continuously buying into a down-trend (or selling into an up-trend).
  - Interaction: with `order_refresh_time: 30, filled_order_delay: 60`, the unfilled sibling is cancelled at 30 s and you sit with no orders until ~69 s. With refresh 120 / delay 60, the sibling stays live until the normal refresh.
- Actionable for our bot: implement a post-fill cooldown per side (not global), and treat it as a cheap anti-trend / anti-toxic-flow control. Combine with markout telemetry: lengthen cooldown when recent markouts are negative.

### 1.3 "What is Inventory Risk?" (Hummingbot Academy)
- Title: What is Inventory Risk?
- Author/site: Hummingbot blog (Academy series); Date: ~2020 (Academy series, undated)
- URL: https://hummingbot.org/blog/what-is-inventory-risk/
- Key takeaways:
  - Defines inventory risk as accumulating the depreciating asset in a trend (bids keep filling, asks don't). Range-bound markets are the MM's best case.
  - Mitigations offered, in order: `history` command to audit inventory drift; inventory skew (target + range multiplier); filled-order delay; hanging orders (keep the sibling so the pair can still complete at the original spread); ping-pong (after a buy fill, only quote sells until a sell fills); asymmetric spreads to follow a trend (e.g. bid 0.1% / ask 0.9% keeps total 1% but favours buys in an up-trend).
- Actionable for our bot: ship inventory skew + filled-order delay + optional hanging orders as first-class. Asymmetric spread by trend is the manual precursor of a reservation-price shift; we should do it automatically via the A-S skew rather than hand-tuned spreads.

### 1.4 Avellaneda Market Making — strategy reference (current implementation)
- Title: Avellaneda Market Making — Hummingbot docs
- URL: https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/
- Key takeaways:
  - Implements A-S reservation price + optimal spread with `risk_factor` (γ) user-set, and `alpha`/`kappa` (trading intensity) estimated automatically from order-book snapshots via a `trading_intensity` indicator. Volatility via `instant_volatility` (tick-to-tick deviation vs zero change).
  - Both estimators need full buffers first; defaults `volatility_buffer_size` 200 ticks and `trading_intensity_buffer_size` 200 ticks (only changed snapshots count, so warm-up can exceed 200 s).
  - Removed legacy knobs: `parameters_based_on_spread`, `max_spread`, `vol_to_spread_multiplier`, `volatility_sensibility`, `inventory_risk_aversion`, `order_book_depth_factor`, `closing_time`. `min_spread` is now a hard floor (as % of mid) below which orders are not placed; `risk_factor` has a new scale.
  - γ guidance verbatim: "common values of this parameter are between 1 and 20", unrestricted upside (100–1000 possible but uncommon); asset-dependent because γ is normalised by instant volatility in absolute price units. If spread > price or reservation price too far, no orders are placed → lower γ.
  - `execution_timeframe`: `infinite` / `from_date_to_date` / `daily_between_times`. Infinite uses modified equations (the code comments say the paper's infinite-horizon formulas have unit inconsistencies; Hummingbot uses the finite-horizon formula with a fixed time-left fraction of 1: https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx).
  - Code (same file): `reservation_price = mid - q*γ*vol*time_left`, `optimal_spread = γ*vol*time_left + 2*ln(1+γ/κ)/γ`, then clamped by `min_spread`. Note vol enters linearly (σ), not σ², in this implementation.
  - `order_amount_shape_factor` (η, 0..1) from Fushimi/Rojas/Herman "Optimal High-Frequency Market Making": asymmetric order sizes to reach inventory target faster; η=1 → equal sizes.
  - Multi-level: `order_levels` with `level_distances` as a % of optimal spread ("tens or hundreds of percents" because optimal spreads are tight).
  - Config defaults from pydantic map: `risk_factor` default 1, `order_optimization_enabled` default True, `order_amount_shape_factor` 0 (https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making_config_map_pydantic.py).
- Actionable for our bot: (a) estimate κ from live book/trade data, not hand-set; (b) require a warm-up gate before quoting; (c) always enforce a fee-aware `min_spread` floor independent of the model; (d) note Hummingbot's deliberate linear-σ variant — the Crypto_MM walk-forward study (§10.4) independently found linear-σ spreads cut extreme-vol losses, so we should test both.

### 1.5 Guide to the Avellaneda & Stoikov Strategy (intro)
- Title: Guide to the Avellaneda & Stoikov Strategy
- Author/site: Hummingbot Academy; Date: Hummingbot 0.38 release era (2021)
- URL: https://hummingbot.org/blog/guide-to-the-avellaneda--stoikov-strategy/
- Key takeaways:
  - Plain-language mapping: q = deviation from target inventory (computed from `inventory_target_base_pct`); γ ≈ 0 → symmetric quotes around mid; higher γ → more aggressive reservation-price shift; high κ (dense book) → tighter spreads; σ widens reservation-price gap and spread.
  - Original "easy mode" derived γ and κ from user `min_spread`/`max_spread` bounds (legacy version).
  - "Risk aversion close to 1 indicates a conservative approach" (legacy IRA ∈ [0,1] scale).
- Actionable for our bot: expose a user-facing "risk aversion 0–1" that maps to γ internally, and always publish the resulting reservation price and spread so operators can sanity-check.

### 1.6 Technical Deep Dive into the A&S Strategy (legacy parameterisation)
- Title: Technical Deep Dive into the Avellaneda & Stoikov Strategy
- URL: https://hummingbot.org/blog/technical-deep-dive-into-the-avellaneda--stoikov-strategy/
- Key takeaways:
  - Derives `γ_max = (MaxSpread − MinSpread) / (2|q|σ²)` and sets `γ = γ_max × IRA` so the model respects user spread bounds.
  - κ solved so the t=0 spread equals the max allowed: `(δa+δb)_max = (2−IRA)·MaxSpread + IRA·MinSpread`.
  - η = 1/q_decay with `q_decay = total_inventory / IRA`.
  - Crypto adaptations proposed: `vol_to_spread_multiplier` (recalc when vol spikes), finite `closing_time` T with recalibration each cycle (because bots run indefinitely).
  - As γ→0 the A-S strategy reduces to fixed-spread PMM — PMM is a special case.
- Actionable for our bot: bound the A-S output with explicit min/max spreads (in bps) and re-derive γ/κ from those bounds when the operator prefers to think in spreads rather than in γ.

### 1.7 Liquidity-mining lessons: Interview with Liquidity Miner "MrBig"
- Title: Interview with Liquidity Miner MrBig
- Author/site: Hummingbot blog; Date: ~9 months after Liquidity Mining launch (late 2020)
- URL: https://hummingbot.org/blog/interview-with-liquidity-miner-mrbig/
- Key takeaways:
  - Ran 20 PMM instances (Docker on an 8 vCPU / 16 GB VPS) across all campaign pairs to diversify.
  - Lost money early "when markets went like a roller coaster"; profitable only once MM PnL + mining rewards balanced.
  - Rules: "Do not try to be in the front row of the order book, the market will kill you." "Stay out of very trendy markets. Stable markets are market makers' best friends." Start with wide spreads and tighten slowly until fills are at least fee-neutral; enable `kill_switch_enable: True`; paper-trade first; adjust only spreads day to day.
  - Claimed 0.6–0.7%/day including mining rewards (subsidised; not spread PnL alone).
- Actionable for our bot: default to conservative (wide) spreads and a tightening schedule gated by realised fee-adjusted PnL; hard kill switch; venue/pair diversification; treat any headline daily-return number that includes rewards as non-transferable.

### 1.8 Liquidity-mining mechanics (what campaigns rewarded)
- Title: Demystifying Liquidity Mining Rewards; Liquidity Mining in Hummingbot vs DeFi; Hummingbot Miner: Year 1 Recap
- URLs: https://hummingbot.org/blog/demystifying-liquidity-mining-rewards/ ; https://hummingbot.org/blog/liquidity-mining-in-hummingbot-vs-defi/ ; https://hummingbot.org/blog/hummingbot-miner-year-1-recap/
- Key takeaways:
  - Rewards paid per minute-snapshot, pro-rated by order size × spread factor ρ(s); e.g. ρ(0.10%)=0.82 vs ρ(0.45%)=0.41, so a 0.10% quote earned ~2× a 0.45% quote of equal size. Eligibility typically ≤1–2% from mid.
  - Year-1 numbers: 18 issuers, 1,622 miners, $376k rewards → $837M filled volume; top miner earned $66k.
  - Community campaign reports (FIRO, PIVX forums) show 15–40 active bots supplying 6–15% of Binance pair volume for ~$4–5k/month of rewards (https://forum.firo.org/t/fcs-proposal-hummingbot-miner-firo-btc-firo-busd-campaigns-extension/2878 ; https://forum.pivx.org/threads/hummingbot-miner-liquidity-campaign-renewal-8-weeks.1769/).
  - Lesson (ours, from the above): rewards paid for *presence* at tight spreads, which incentivised quoting through toxic periods; the interviewed miners' losses in trending markets are the expected result.
- Actionable for our bot: if we ever join an exchange MM/rebate programme, model the uptime/spread obligations as a cost (writing the adverse-selection option continuously — see §5.3), not as free yield.

### 1.9 Hummingbot V2 controllers: PMM Simple, PMM Dynamic, D-Man Maker V2
- Titles: Controllers (docs); Dashboard Tutorial: PMM Simple V2; How to Configure a V2 Strategy Controller; `pmm_dynamic.py`; `dman_maker_v2.py`
- URLs: https://hummingbot.org/strategies/v2-strategies/controllers/ ; https://hummingbot.org/blog/dashboard-tutorial-pmm-simple-v2/ ; https://hummingbot.org/blog/how-to-configure-a-v2-strategy-controller-in-hummingbot/ ; https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/pmm_dynamic.py ; https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/dman_maker_v2.py ; https://hummingbot.org/dashboard/config/
- Key takeaways:
  - Architecture: controllers consume a `MarketDataProvider` (book, trades, candles) and emit `ExecutorActions`; one `v2_with_controllers.py` runs many controllers/pairs; YAML configs hot-reload (`config_update_interval` default 60 s).
  - Market-making controllers listed: `pmm_simple`, `pmm_dynamic`, `dman_maker_v2`; plus `xemm_multiple_levels`, `grid_strike`, `pmm_v1`, `pmm_mister`, `hedge_asset`, etc.
  - PMM Simple: `buy_spreads`/`sell_spreads` lists (e.g. [0.01, 0.02] = 1%, 2%), `buy_amounts_pct`/`sell_amounts_pct`, `executor_refresh_time` (example 300 s), `cooldown_time` (60 s) after a stop-loss. Each fill is wrapped in a `PositionExecutor` with a triple barrier: `stop_loss` (e.g. 0.03), `take_profit` (0.02), `time_limit` (2700 s), optional trailing stop. Spot-only `position_rebalance_threshold_pct` (0.05) triggers a market order to restore the target split.
  - PMM Dynamic: spreads expressed in *units of NATR* (defaults `"1,2,4"`); `spread_multiplier = NATR(14)/100`; reference price shifted by MACD(21/42/9): `price_multiplier = (0.5·z(MACD) + 0.5·sign(MACDh)) · NATR/2`. Dashboard text: "spread unit of 1 with NATR 0.005 → first order 0.5% from mid". Can use candles from one exchange to quote on another.
  - D-Man Maker V2: each level is a DCA executor (`dca_spreads`, `dca_amounts`), `top_executor_refresh_time` refreshes level-0 faster than deeper levels; `activation bounds` optional.
  - The V2 design treats every fill as a *position with an exit plan* rather than pure inventory — closer to a scalper than a classic MM.
- Actionable for our bot: (a) volatility-unit spreads (NATR or short-window realised vol multiples) instead of fixed %; (b) refresh top level faster than deep levels; (c) per-fill time-limit / stop-loss as a last-resort inventory backstop; (d) hot-reloadable YAML config.

---

## 2. Microprice / fair value estimation in practice

### 2.1 Stoikov, "The Micro-Price" (SSRN abstract + code)
- Title: The Micro-Price: A High Frequency Estimator of Future Prices
- Author: Sasha Stoikov; Date: Nov 2017 (SSRN)
- URL: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694 (code: https://github.com/sstoikov/microprice)
- Key takeaways:
  - Micro-price = limit of expected future mid-prices, a martingale by construction; expressed as an adjustment to mid that depends on imbalance *and* spread; empirically a better short-horizon predictor than mid or weighted mid.
  - The simple "weighted mid" `(ask·bid_qty + bid·ask_qty)/(bid_qty+ask_qty)` is only the first-order version; the full estimator is fitted from discretised imbalance/spread transition matrices.
- Actionable for our bot: use weighted mid as the day-1 fair value; log imbalance/spread states so we can fit the full Stoikov adjustment per venue/pair later.

### 2.2 Replication on Binance data
- Title: MicroPriceIndicator (replicates Stoikov on Binance ETHBTC / TRXBTC)
- Author/site: shaileshkakkar (GitHub); Date: created 2018
- URL: https://github.com/shaileshkakkar/MicroPriceIndicator
- Key takeaways:
  - Reconstructed the book from three Binance streams (trades, partial depth, snapshot) and found micro-price adjustment vs imbalance/spread "shares the same dynamics" in crypto as in US equities.
  - Author's stated use: fair-price for quoting.
- Actionable for our bot: the imbalance→drift relationship transfers to crypto; fit it per pair.

### 2.3 Live implementation patterns (mm-live)
- Title: mm-live (real-time MM system, Binance + OKX feeds)
- Author/site: Aliipou (GitHub README); Date: 2026 (repo)
- URL: https://github.com/Aliipou/mm-live
- Key takeaways:
  - Quoting on a fixed 100 ms timer, not per-event. Fair value = Kalman(mid) + α·OFI; microprice = Stoikov weighted mid; vol = blend of short/long EWMA; regime = HIGH_VOL if σ_short/σ_long > 1.5; imbalance EMA-smoothed.
  - Quotes: `bid = r − δ·regime_mult·(1+α|imb|)`, `ask = r + δ·regime_mult·(1−α|imb|)`; one-sided quoting at inventory limit. Defaults: γ 0.05, k 1.5, horizon 600 ticks, max inventory 0.1 BTC.
  - Insists on markout validation at 100 ms/500 ms/1 s before trusting any signal; README warns to paper trade "several weeks".
- Actionable for our bot: timer-based quote cycle (100 ms class), dual-EWMA vol with a regime ratio trigger, imbalance-skewed half-spreads, one-sided quoting at limits, markout gate before enabling a signal.

### 2.4 Cross-exchange lead-lag: Binance leads (perps)
- Title: An honest assessment of where crypto price discovery happens
- Author/site: Arihant Nayyar, Arrakis Finance blog; Date: 4 Jun 2026
- URL: https://arrakis.finance/blog/crypto-price-discovery
- Key takeaways:
  - Hayashi–Yoshida lead-lag on side-separated fills, 29 assets, 16 days to 26 Feb 2026: Binance led Hyperliquid 29/29 (≈700 ms), Lighter led Hyperliquid 27/29, Binance led Lighter 23/29 (~100 ms, the grid floor).
  - Mechanism of stale liquidity on the lagging venue: arbitrageurs spam IOCs at stale maker quotes while makers race cancels; whoever reaches the matcher first wins.
  - Method notes: 1-second grids destroy sub-second lead-lag; use side-separated fills to kill bid-ask bounce.
- Actionable for our bot: Binance perp mid/microprice is a legitimate leading fair-value input for OKX/Bybit quoting; measure our own lag with an HY estimator at ≤100 ms resolution before trusting a fixed offset.

### 2.5 Lead-lag is resolution- and regime-dependent (Binance vs OKX spot)
- Title: Analyzing Lead–Lag Effects Between Exchanges Using Flat Files
- Author/site: CoinAPI tutorial; Date: 2026 (uses Feb-2026 data)
- URL: https://www.coinapi.io/tutorials/analyzing-lead-lag-effects-between-exchanges-flat-files
- Key takeaways:
  - At 1 s resolution Binance vs OKX BTC/USDT shows best lag = 0 (no leader visible); any lead-lag lives at sub-second scale.
  - "There is no permanently leading exchange"; leadership varies with liquidity, time of day, period. Always compare same quote currency (USDT vs USDT).
- Actionable for our bot: don't hard-code "Binance leads by X ms"; estimate a rolling lead-lag per pair and fall back to local mid when the estimate is unstable.

### 2.6 Wallet-level evidence that Binance leads BTC perps
- Title: Binance Leads, but Some Wallets Anticipate (Research Square preprint)
- Date: covers 25 May–22 Jun 2026
- URL: https://www.researchsquare.com/article/rs-10147582/v1.pdf
- Key takeaways: venue-level Binance leads Hyperliquid in every price-discovery window; some wallets anticipate. Corroborates §2.4.
- Actionable for our bot: same as 2.4.

---

## 3. Adverse selection & toxic flow

### 3.1 "The Day the Spread Stopped Being Free"
- Title: The Day the Spread Stopped Being Free — Surviving the Race Against Adverse Selection (CLOBs & DeFi)
- Author/site: Nagu Thogiti, thogiti.github.io; Date: 2 Jan 2026
- URL: https://thogiti.github.io/2026/01/02/the-spread-is-not-free.html
- Key takeaways:
  - Maker PnL identity: `Π_buy(τ) = ΔM(τ) + s/2`; adverse selection is `E[ΔM(τ) | fill] ≠ 0`. A markout curve that drops and stays negative = you are exit liquidity.
  - Mid moves when best quotes vanish; queue depletion (trades + cancels − adds) per unit depth is the hazard; cancel waves are a regime signal ("the crowd leaving the theatre").
  - Queue position: two makers at the same price get different outcomes; backtests fail mostly by assuming fills at best without a queue model.
  - Inventory couples fills into a feedback system; risk penalty scales with σ² and with horizon Δ (slow cancels make inventory more expensive).
  - Latency: "the model reacted in time, and the order did not." Highest hazard moments are when takers are fastest and other makers cancel hardest.
  - Advice: "Don't start by coding a strategy. Start by coding a logger." Record fills and mid at 0.1/0.5/1/2/5/10 s.
  - Signal decoder: geometry (OBI), pressure (OFI), fragility (cancel ratio), persistence (Hawkes), toxicity (markout), control (skew/widen/size).
- Actionable for our bot: build the markout logger and a per-side "depletion pressure / depth" hazard before writing the quoter; add a cancel-wave detector that widens/pulls.

### 3.2 Daru Finance: touch quoting does not pay its adverse selection (Bybit, Binance USD-M, Hyperliquid)
- Title: Quoting the Touch Does Not Pay Its Adverse Selection
- Author/site: Daru Finance research (SSRN 7461901, replication on GitHub); Date: 2026
- URL: https://daru.finance/research/crypto-adverse-selection
- Key takeaways:
  - Simulated a back-of-queue one-unit quoter at best bid/ask, re-posted ≤ every 100 ms, across 9,983 coin-days / 125.8M fills, with true aggressor flags.
  - Pooled 10 s pre-fee results: capture +0.21 bp (Bybit), +0.46 bp (Binance USD-M), +0.56 bp (Hyperliquid); adverse drift −1.04 / −0.85 / −1.02 bp; net −0.84 / −0.39 / −0.46 bp, 95% CI excludes zero on all three.
  - Bybit majors trade one tick wide most of the time → BTC capture ≈ 0.0124 bp per fill; adverse/capture ratio 5.1 pooled, 50 on Bybit BTC.
  - Front-of-queue matters: cites Albers et al. measuring Hyperliquid BTC maker fills at −0.48 bp average but +0.32 bp for first-in-queue traders (≈0.8 bp gap).
  - Trade-sign classifiers (Lee–Ready, tick rule) agree with exchange flags 89–98% and never flip the sign.
- Actionable for our bot: (a) do not quote at the touch on one-tick-wide majors unless we can be front-of-queue; (b) prefer pairs where the quoted spread is several ticks; (c) use exchange aggressor flags (available on all three of our venues) for our own markouts; (d) our baseline expectation for naive touch-quoting is negative before fees.

### 3.3 The Market Maker's Dilemma (Binance BTC perp live experiment)
- Title: The Market Maker's Dilemma: Navigating the Fill Probability vs. Post-Fill Returns Trade-Off
- Authors: Albers, Cucuringu, Howison, Shestopaloff (Oxford / QMUL); Date: arXiv 2502.18625 v2, Aug 2026
- URL: https://arxiv.org/html/2502.18625v2
- Key takeaways:
  - 232,897 real minimum-size maker orders on Binance BTCUSDT perp over one week; spread "virtually always one tick"; best fee tier taker 1.5 bp / maker −0.5 bp; tick 0.1 USD ≈ 0.03 bp.
  - Documented negative correlation between fill probability and post-fill return: if the next price move is against you at the touch you fill with probability 1 (adverse selection); if it is in your favour you no longer fill.
  - Posting *with* the imbalance = back of the long queue; posting *against* it = good queue position but against expected drift. Viable maker strategies were contrarian ("reversals"), and required engineered microstructure features; "commonly-cited strategies" were highly unprofitable.
  - Fill probabilities are easy to predict from queue sizes; exploiting them is not.
- Actionable for our bot: track our own queue position (queue-ahead estimate from depth at placement minus subsequent trades/cancels); cancel back-of-queue orders on the side facing imbalance; treat imbalance as a skew input, not as a "join the crowd" signal.

### 3.4 Markout / P&L attribution as the daily diagnostic
- Titles: P&L Attribution For A Market Maker (Quant Memo); Performance attribution (HFT Book); Spread vs adverse selection (HFT Book); QuestDB markout cookbook
- URLs: https://quantmemo.com/concepts/pnl-attribution-market-making ; https://hftradingbook.com/performance/attribution ; https://hftradingbook.com/strategies/spread-vs-adverse-selection ; https://questdb.com/docs/cookbook/sql/finance/markout/
- Key takeaways:
  - Four buckets: spread capture + rebates + inventory MTM + adverse selection (markout). Worked example: +$120 spread, +$24 rebate, −$128 adverse selection, +$600 inventory → the "great day" was a lucky directional position; true MM skill was ~$16.
  - Judge the quoter on `spread + rebate − adverse selection` with inventory PnL zeroed.
  - HFT Book [SYNTHETIC] waterfall: gross +9.0 bp, adverse −5.5 bp, own impact −1.2 bp, microprice-skew alpha +1.8 bp, fees −0.4 bp → net +3.7 bp; per-hour slicing revealed a toxic midday window worth gating off. Spread-vs-adverse page: adverse selection ate ~70% of gross in the [SYNTHETIC] example; break-even spread ≈ AdvSel/fill + inventory cost/fill + net fee/fill.
  - QuestDB: markout by venue/counterparty/passive-aggressive at multiple horizons; falling curve = adverse selection; use HORIZON JOIN / LIST offsets.
- Actionable for our bot: daily attribution report with the four buckets, per pair, per hour-of-day, per queue-position decile; automatic rules — negative adverse bucket → widen/skew/drop pair; inventory-dominated PnL → tighten limits.

### 3.5 Stale-quote sniping (the mechanism)
- Title: Stale Quote Sniping, Explained
- Author/site: Quant Memo; Date: 2026 (undated concept page)
- URL: https://quantmemo.com/concepts/stale-quote-sniping
- Key takeaways:
  - Any quote is stale for the window between a fair-value move and your cancel landing; snipers only need speed since the trigger is public. Structural, not a bug.
  - Worked example: 200 moves/day × 40% snipe success × $0.03 = $2.40/day per unit size, recovered by adding ~$0.0012 to each of 2,000 round trips.
  - Exchanges' speed bumps / batch auctions exist to shrink the window (not present on our CEXs).
- Actionable for our bot: measure "snipe rate" = fraction of our fills within X ms after a Binance-lead move; feed it into the spread floor as an explicit adverse-selection term.

### 3.6 Latency arbitrage across crypto venues
- Titles: Latency arbitrage in crypto — and why you can't do it from home (Finder); Crypto Market Makers & HFT (DennTech)
- URLs: https://finder-arbitrage.com/blog/latency-arbitrage ; https://denntech.io/blog/crypto-market-makers-hft-guide
- Key takeaways:
  - After a Binance move, other venues are stale for milliseconds; whoever reprices first wins. Finder claims windows "close in 3 milliseconds" and a home trader is "100+ milliseconds late with a 5x-worse fee structure" [UNVERIFIED — vendor blog].
  - DennTech: cross-venue monitoring (watch Binance to reprice OKX/Coinbase quotes) is the standard MM defence; latency arb is "the most common HFT strategy in crypto".
  - Finder: "Binance and OKX lean on AWS Tokyo" — conflicts with §9.1 measurements placing OKX nearest Hong Kong. [UNVERIFIED]
- Actionable for our bot: we are the *target* of latency arbs on OKX/Bybit; defend by (a) leading fair value from Binance, (b) pulling/widening on Binance-lead jumps, (c) never quoting inside our measured reprice latency.

### 3.7 Reddit r/algotrading: "Avoiding MM adverse selection in practice?" [UNVERIFIED — snippet only, Reddit blocks fetch]
- URL: https://www.reddit.com/r/algotrading/comments/pjsxn4/avoiding_mm_adverse_selection_in_practice/
- Key takeaways (from search snippet):
  - OP's three tools: skew by flow/trade-throughs; stop quoting one side for a while if it keeps filling; (third not visible).
  - Top reply: "give" (skew of fair price by inventory) plus size modulation — `light side size = (std_size + |pos|)/2`, `heavy side size = ((std_size + |pos|)/2)·exp(−γ·q/Q)`.
  - Futures MBO tip: track exact queue position; "only take a fill if you are in the top 10% of the queue", cancel back-of-queue orders because they only get toxic fills.
  - Depth-imbalance at ±1% as a directional filter (e.g. 1000 bid vs 9000 ask → likely to fall).
- Actionable for our bot: implement side-size modulation as a complement to price skew; cancel-if-back-of-queue rule where queue position can be estimated.

---

## 4. Inventory management in practice

### 4.1 HFT Book — Inventory management (the "ladder of sophistication")
- Title: Inventory management
- Author/site: hftradingbook.com; Date: reviewed 4 Jun 2026
- URL: https://hftradingbook.com/strategies/inventory-management
- Key takeaways:
  - Symmetric quoting lets inventory random-walk (spread grows like √t) and park at the limit under any flow imbalance.
  - Rung 1: linear skew `centre = mid − k·q` + hard limits — "the realistic default for an independent or crypto quoting bot in 2026". Rung 2: A-S gives `k = γσ²(T−t)`. Rung 3: multi-asset, hedged, regime-aware, learned.
  - Hard limits: as |q| approaches cap, widen/pull the growing side; at cap quote only the flattening side. Hedging converts price risk to basis risk; "a trap when the basis breaks".
  - Inventory as OU: `dq = −κ(q − q*)dt + noise`; target q* need not be zero.
  - [SYNTHETIC] example: 60/40 sell-heavy flow; symmetric k=0 → |q| ~52 lots; k=0.01 → ~18 lots, cost ≈ 0.45/lot given up on flattening sells.
- Actionable for our bot: ship Rung 1 first (linear skew + hard cap + flatten-only mode at cap), calibrate k against A-S, then add perp hedge as a separate module.

### 4.2 CCXT blog — minimal quoting loop with hard limits
- Title: Market making: the strategy exchanges literally pay you to run
- Author/site: CCXT Team; Date: 7 Jul 2026
- URL: https://docs.ccxt.com/blog/market-making-with-ccxt
- Key takeaways:
  - Skeleton: 20 bp quoted spread (fees-inclusive), order 0.001 BTC, `MAX_INVENTORY` 0.005 BTC, refresh 5 s, `skew = −(inventory/MAX_INVENTORY)·(SPREAD/2)`, `postOnly: true` ("non-negotiable"), stop quoting one side at the bound, `cancelAllOrders` in `finally`.
  - Use WebSocket book (`watchOrderBook`), never polled REST; `editOrder` where supported ("you often keep queue position on exchanges that preserve it for size-down amendments").
  - Non-optional controls: hard inventory bounds, tested kill switch, dead-man's switch where offered, spread floors during volatility ("the makers who survive news events are the ones who weren't quoting through them"), fee-aware spread ("0.02% maker, 0.1% spread nets 0.06% before adverse selection — which will claim most of it").
  - Roadmap order: real inventory tracking via `watchMyTrades` → vol-aware spreads → OBI signals → multi-level.
- Actionable for our bot: adopt the same control checklist and build order; wire exchange-native cancel-on-disconnect.

### 4.3 perp.wiki — Market making on Hyperliquid (inventory techniques) [page fetch timed out; snippet only]
- URL: https://perp.wiki/learn/market-making-on-hyperliquid
- Key takeaways (snippet): four inventory techniques — skew quotes proportional to imbalance; hard max-inventory and stop quoting the growing side; periodic hedge/flatten with a market order past a threshold (pay taker fee to kill directional risk); time-decay unwind with increasingly aggressive orders. Widen on vol spikes, skew, or "a series of fills consistently going against you".
- Actionable for our bot: implement "time-decayed aggression" for stale inventory (inventory half-life target) as an alternative to instant taker flatten.

### 4.4 Delta-neutral practice at firms (Wintermute, Kairon Labs, DWF)
- Titles: Evgeny Gaevoy interview (When Shift Happens recap); Kairon Labs interviews (Metaverse Post; MEXC News); DWF Labs hedging guide
- URLs: https://www.kevinfollonier.com/post/the-flat-earth-theory-of-crypto-evgeny-gaevoy-on-market-myths-trading-truths-and-mars ; https://mpost.io/bulls-vs-bears-unveiling-the-adaptive-strategies-of-a-top-crypto-market-maker/ ; https://www.mexc.com/news/75726 ; https://www.dwf-labs.com/news/understanding-market-maker-hedging
- Key takeaways:
  - Wintermute (Gaevoy, Aug 2025): core is delta-neutral — buy on Binance, immediately look to sell on Coinbase/Uniswap; retail flow is the *valuable* uninformed flow; "It's other market makers and informed funds who can move markets. That's where we get run over." Shorting illiquid alts is the most dangerous position (capped upside, unlimited downside).
  - Kairon Labs (Beke): systems track "inventory skews to portfolio skews, big P&L drawdowns, liquidation or margin thresholds, and counterparty risk", even exchange outflows; ML for near-real-time inventory-skew management, no "AI" in the quoter. Willemen: on CEXs the job is "place/refresh bids and asks across multiple price levels, manage queue priority and tick size, target measurable spread and depth"; good liquidity = tight, resilient, consistent.
  - DWF: hedge accumulated spot inventory with an offsetting perp/futures short; complement with dynamic quote adjustment.
- Actionable for our bot: hedge module on the perp of the same venue (or Binance perp) with a delta band; monitor margin/liquidation thresholds and exchange health as first-class risk inputs.

### 4.5 Moontower (Kris Abdelmessih) — market making is measurement, not prediction
- Titles: Primer #3 The Nature of Edge; Primer #4 Measurement Not Prediction; a market-making project you can do today; the sound of inevitability
- URLs: https://moontower.substack.com/p/primer-3-the-nature-of-edge ; https://moontower.substack.com/p/primer-4-measurement-not-prediction ; https://moontower.substack.com/p/a-market-making-project-you-can-do ; https://moontower.substack.com/p/the-sound-of-inevitability
- Key takeaways:
  - "Fair value is the consensus-driven price that you can easily buy or sell at"; the more liquid market provides fair value; edge = buying below / selling above it, then deciding whether to hedge.
  - "The business of market-making has nothing to do with prediction" — worked example of quoting a Polymarket contract around a futures-implied fair value and hedging with futures.
  - Dealer's function: "price liquidity and manage inventory"; blow-ups come from "Leverage + Concentration"; "nobody is bigger than the market".
- Actionable for our bot: fair value from the most liquid venue (Binance) and hedge decisions are the two design centres; keep leverage low and inventory concentration bounded.

---

## 5. Spread setting in practice

### 5.1 Fee-aware minimum spread and the "VIP-9 bug"
- Title: The maker-taker decision: fee tiers, rebates, and the true cost of crossing the spread
- Author/site: marketmaker.cc blog; Date: 21 Jul 2026
- URL: https://marketmaker.cc/en/blog/post/maker-taker-fees-rebates-execution/
- Key takeaways:
  - Representative mid-2026 base tiers (verify on venue pages): Binance spot 10/10 bp; Binance USDⓈ-M perp 2/5 bp (VIP9 0/1.7); Bybit perp 2/5.5 bp (MM programme to −1.5 bp maker with obligations); OKX perp 2/5 bp (top ≈ −0.5/1.5–2 bp); Hyperliquid 1.5/4.5 (rebate to −0.3).
  - "Retail maker fees are positive nearly everywhere… the decision is pay 2 or pay 5, not earn or pay." BTCUSDT perp often quotes <1 bp wide while retail taker pays 5 bp — the fee *is* the cost.
  - Corrected break-even: making beats taking only if `s + f_t − f_m > A + ((1−p)/p)·D` (A = conditional adverse move, p = fill prob, D = miss cost). Worked: apparent 5 bp saving shrinks to 0.4 bp.
  - Quote value `V = p(q)(s/2 + r − A(q)) − (1−p(q))·C_miss`; [SYNTHETIC] front-decile +0.37 bp vs back-decile −1.68 bp at the same price — queue position flips the sign.
  - VIP-9 bug: a 2.6 bp gross-capture strategy nets +2.6 at 0 bp maker, +0.6 at 1 bp, −1.4 at 2 bp. Model fee tier as a rolling-30-day-volume state machine; token discounts (BNB/OKB) are positions.
  - Cancel/replace resets queue position → converts your fills into back-of-queue (toxic) fills.
- Actionable for our bot: spread floor = 2×maker fee at the tier we *actually* hold + measured A(q) + margin; simulate fee tier endogenously; never assume rebates.

### 5.2 Foreseer — the fee floor and the toxicity guard [page content did not render; snippet only]
- URL: https://foreseer.co/insights/fee-floor-market-making-algorithms
- Key takeaways (snippet): "quote mid ± (base half-spread + skew × normalized inventory), and shrink size on the side that adds to inventory" beat everything fancier on their tapes; a toxicity guard (widen/pull when recent taker flow is one-sided and pushing through price) "was the single largest PnL lever we measured". Use A-S as a sanity anchor, not the live driver. Floor ≈ 2× maker fee + intended edge (their HL spot example: 4 bp maker → unprofitable below ~8–10 bp quoted).
- Actionable for our bot: same simple structure; the toxicity guard is a must-have, not an enhancement.

### 5.3 Rebates and MM programmes are wages for writing the option
- Source: marketmaker.cc (§5.1) and Hyperliquid Guide (https://hyperliquidguide.com/guides/trading/hyperliquid-trading-strategies)
- Key takeaways: negotiated programmes come with spread caps, minimum size, uptime — "you are paid to write the adverse-selection option continuously — including through news, cascades". Hyperliquid Guide: fee-tier moves "can be the entire difference between a profitable strategy and a losing one".
- Actionable for our bot: model programme obligations as forced quoting through toxic windows before signing up.

### 5.4 Volatility-unit spreads (NATR) — Hummingbot PMM Dynamic
- See §1.9. Spreads in units of NATR(14) on candles; reference price shifted by a bounded MACD signal (max shift NATR/2).
- Actionable for our bot: express spreads as `k × σ_short` with k per level (e.g. 1, 2, 4), clamp between fee floor and a max.

### 5.5 Volatility regime → spread multiplier (mm-live)
- See §2.3: `HIGH_VOL if σ_short/σ_long > 1.5` → `regime_mult` widening; dual-EWMA vol.
- Actionable for our bot: two EWMA windows (e.g. ~1 min and ~15 min; tune) and a ratio trigger.

### 5.6 Time-of-day spreads (measured hourly vol)
- Title: Everyone Is Talking About AI Trading Bots. We Actually Built One. (prediction-market MM post-mortem)
- Author/site: dev.to/crashland; Date: 2026
- URL: https://dev.to/crashland/everyone-is-talking-about-ai-trading-bots-we-actually-built-one-heres-what-happened-4cb3
- Key takeaways: one-day sim: 719,624 orders, 1,212 fills (0.17% fill rate), −$5,499 paper; root cause was directional inventory from informed flow, not a wrong model. Fix adopted: spreads ×1.94 at US-equity-open hour, ×0.55 in quiet Asian midday, "derived from actual measured BTC volatility by hour"; "static spreads during peak volatility were the single biggest source of adverse selection".
- Actionable for our bot: hour-of-day spread multiplier table from our own measured vol; widen around scheduled macro releases and US open.

### 5.7 Join vs improve, tick size, queue
- Sources: Albers et al. (§3.3); marketmaker.cc (§5.1); Hummingbot order optimization (§1.1); Bybit post-only/priority FAQ (https://www.bybit.com/en/help-center/article/FAQ-Order-Execution-and-Liquidation)
- Key takeaways:
  - On one-tick-wide books (BTC/ETH perps on Binance/Bybit) "improving" is impossible; you join and your fate is your queue position. Bybit confirms strict price-time priority; post-only cancels if it would take.
  - Where the book is several ticks wide (alts, some spot), Hummingbot-style "jump one tick inside best" wins priority at the cost of spread; do it only down to the fee-aware floor.
  - Any price change via cancel/replace or amend-with-new-price goes to the back of the new level (Binance states this explicitly; see §9.3).
- Actionable for our bot: decision rule per level: if `quoted_spread_ticks ≥ 3` and our floor allows, improve by 1 tick; else join and estimate queue-ahead; cancel if queue-ahead > X% of level size when imbalance is against us.

---

## 6. Practitioner posts, threads and interviews

### 6.1 Robot Wealth — "Market making for beginners"
- Author: Kris Longmore; Date: 22 Oct 2024
- URL: https://robotwealth.com/market-making-for-beginners/
- Key takeaways:
  - Three hard things: know fair value; "you can't be wrong by more than half your spread on average"; learning is expensive (feedback costs asymmetric to edge).
  - Early crypto: "quoting prices on various exchanges about 5% around whatever BitMEX was showing" made a living; gone now.
  - Successful MMs have better fair-value models *and update faster than others can pick off their stale quotes*; "knowing the price on Binance would be a very good idea" when making a smaller venue.
  - Recommends beginners first learn by picking off stale quotes (they did this CEX→DEX), or do perp basis / risk-premia harvesting.
- Actionable for our bot: the fair-value + reprice-speed pair is the product; build a "stale-quote detector" on ourselves (how often does Binance move before we cancel?).

### 6.2 quantframe.io — The Market Making Machine (institutional view)
- Author: Antonije Mirkovic; Date: 2026 (references Jul 2026 events)
- URL: https://www.quantframe.io/article/institutional-market-making
- Key takeaways:
  - Break-even half-spread `h* = πJ` (informed fraction × informed move); "quote tighter and every fill is, on average, a donation".
  - Reran the A-S paper experiment (γ=0.1, σ=2, k=1.5, A=140, 1,000 sessions): symmetric quoter final-inventory SD 8.3 / PnL SD 13.5 vs skewed 2.9 / 6.5 — "PnL risk cut in half for almost the same mean".
  - Speed is defence: Budish et al. arbitrage windows 97 ms (2005) → 7 ms (2011); UK races decided in 5–10 µs. "If your strategy does not rest quotes, you are not in that race."
  - Virtu: 1 losing day in 1,238 — via averaging thousands of small-edge trades; toy model shows ~1 losing day in 4 at 100 trades/day, ~1 in 100 at 1,000.
- Actionable for our bot: our edge per fill will be small; profitability depends on trade count and on keeping π·J small via fair value and fast cancels; target many fills per day on pairs with uninformed flow.

### 6.3 LinkedIn post-mortem: "I just built a quantitative trading bot… It lost money"
- Author: Abdulaziz AlSharif; Date: 25 Mar 2026
- URL: https://www.linkedin.com/posts/abdulaziz-alsharif-sa_i-just-built-a-quantitative-trading-bot-to-activity-7442522410987454464-HMna
- Key takeaways: three iterations of a paper MM on live Binance data (v1 naive → v2 inventory skew + defensive quote suppression → v3 toxic-flow avoidance); each less negative, none profitable. "Most fills occurred right before price moved against me"; "small spreads couldn't overcome fees + adverse selection"; "defensive logic is not the same as edge".
- Actionable for our bot: defensive controls are necessary but insufficient; we need a fair-value edge (Binance lead) and pair selection for uninformed flow.

### 6.4 Reddit r/algotradingcrypto — "Market Making in Crypto" [UNVERIFIED — snippet only]
- URL: https://www.reddit.com/r/algotradingcrypto/comments/1q2qcss/market_making_in_crypto/
- Key takeaways: OP's A-S paper sim (avg spread 30 bp, γ 0.1, σ 1.8%, λ 0.8/s) "always" profitable; replies: no latency modelled ("feed latency, order-post latency, confirmation latency… one of the biggest factors"); fees unrealistic ("at least 10 bps maker/taker… 20 bps total"); "quoting source is very important as there are algorithms specifically designed to drain poorly designed algorithms"; "you need to hedge to avoid directional risk".
- Actionable for our bot: any backtest without latency, queue, and real fee tier is disqualified as evidence.

### 6.5 Reddit r/algotrading — "Help Me Understand Market Making 101" [UNVERIFIED — snippet only]
- URL: https://www.reddit.com/r/algotrading/comments/7whgkm/help_me_understand_market_making_101/
- Key takeaways: adverse selection explained as "you don't control when a trade happens… on average trades will happen at worse-than-average times and it's up to speed, smarts and value from the captured bid-ask spread to make up for those costs."
- Actionable for our bot: none beyond §3.

### 6.6 Keyrock — What is Crypto Market Making? (firm's own guide)
- URL: https://keyrock.com/knowledge-hub/guide-crypto-market-making/
- Key takeaways: firms analyse average spread vs daily volume to pick markets ("wide spreads are precisely where market makers can intervene"); revenue also from OTC and retainers (projects pay for liquidity), not spread alone.
- Actionable for our bot: pair screening metric = quoted spread vs volume; we cannot count on retainers.

### 6.7 Grid-vs-MM and "bots that blow up" (see §8)

---

## 7. Perpetual-futures specifics

### 7.1 Funding settlement rules on Binance USDⓈ-M
- Titles: Binance announcements on funding settlement frequency (2 May 2025; 2 Jan 2026)
- URLs: https://www.binance.info/en/support/announcement/detail/3243c81a35bd4f0c86a37315c3dc96cc ; https://www.binance.info/en/support/announcement/detail/e4445d0389ce4defa6009021fcf6ee46 ; https://www.odaily.news/en/newsflash/462803
- Key takeaways:
  - Standard 8 h (00/08/16 UTC) or 4 h (every 4 h) settlement; if the previous settlement hits the cap/floor, frequency moves to 1 h within ~15 min; since 2 Jan 2026, hourly contracts revert to 4 h after 16 consecutive cycles with |rate| ≤ 0.025%. Query `GET /fapi/v1/fundingInfo`.
  - OKX and Bybit intervals: not verified here — check per symbol via API. [UNVERIFIED]
- Actionable for our bot: read funding interval and next-funding time per symbol from the API; treat the 15 min before settlement as a risk window for inventory (funding accrues to holders at settlement) and for flow spikes.

### 7.2 Funding-aware market making (research with Hyperliquid data)
- Title: Funding-Aware Optimal Market Making for Perpetual DEXs
- Date: arXiv 2605.06405 (2026)
- URL: https://arxiv.org/html/2605.06405
- Key takeaways:
  - Adds funding as a state: cash drift `−q·f` couples inventory and funding — long inventory with positive funding bleeds; quotes should skew by funding sign, not just inventory.
  - Calibrated OU funding with short half-lives; residuals heavy-tailed (hourly jump probabilities 2.05% ETH, 1.24% BTC, 0.16% SOL).
  - 100-seed holdout (26 Nov–31 Dec 2025): funding-aware HJB improves mean equity vs pure A-S on ETH/BTC and lowers inventory RMS; BTC win rate only 0.57; SOL gain is a leverage effect; loses in ETH high-funding and BTC high-vol windows. "Simple projected funding-aware quote rules are not robust."
- Actionable for our bot: add funding carry to the reservation price as `− q·(expected funding per horizon)` and prefer holding inventory on the side that *receives* funding; keep it modest — evidence of benefit is narrow.

### 7.3 Funding-flip and cascade behaviour
- Titles: Perp DEX Liquidity (investors-planet); How Do Market Makers Respond to the Start of a Liquidation Cascade? (greeks.live); Hyperliquid Trading Strategies (hyperliquidguide)
- URLs: https://investors-planet.com/perp-dex-liquidity/ ; https://learn.greeks.live/path/how-do-market-makers-respond-to-the-start-of-a-liquidation-cascade/ ; https://hyperliquidguide.com/guides/trading/hyperliquid-trading-strategies
- Key takeaways:
  - Funding can flip deeply negative in downturns, turning a "delta-neutral" short-perp carry into negative carry unless re-hedged.
  - During liquidation cascades MMs widen or withdraw; forced flow consumes depth; this worsens the cascade (feedback loop). Circuit breakers: cancel all resting orders when index oracles lag or margin thresholds approach.
  - Hyperliquid Guide (bot-operator voice): "a bot holds it through settlement after settlement unless you coded the check"; "a mean-reversion bot buys straight into [a cascade]". Alt funding can exceed 0.1% per settlement in momentum periods.
- Actionable for our bot: liquidation-cascade detector (liquidation feed / OI drop / trade intensity + one-sided prints) → pull quotes; funding-sign check before carrying inventory over settlement; margin-utilisation kill threshold.

### 7.4 Maker fees/rebates on perps (our venues)
- Source: marketmaker.cc table (§5.1). Base maker 2 bp on Binance/Bybit/OKX perps; rebates only at top VIP or via MM programmes (Bybit −1.5 bp with obligations; OKX ≈ −0.5 bp top tier). [Verify on venue fee pages before relying on any number.]
- Actionable for our bot: plan economics at 2 bp maker; treat rebates as upside.

---

## 8. Grid trading vs real market making

### 8.1 Neutralis — crypto MM bots: grids, fees, risks
- URL: https://neutralis.finance/insights/crypto-market-making-bot-grids
- Key takeaways: grids profit from oscillation but "as soon as a trend develops, inventory loads on one side"; backtests show 30–50% drawdown in persistent drift (citing ainvest.com, 2026) [UNVERIFIED secondary]; practitioners cap global loss at 25–30%; "a professional market-making system… adjusts its quotes based on the spread, order flow, and accumulated inventory".
- Actionable for our bot: grids are the Rung-0 symmetric quoter with memory; we must not ship without skew + caps.

### 8.2 crypto-resources — Grid bot disadvantages
- URL: https://crypto-resources.com/grid-trading-bots-on-exchanges-risks/
- Key takeaways: common configuration errors — grid too tight when vol expands, too wide in calm, "no cap on maximum inventory (unbounded accumulation)", launching at the end of a range; on futures add liquidation, funding and cascade risk. Useful borrowings: regime-gated entry, cooldowns after vol spikes, inventory and trade-frequency caps, derivatives checks (funding/premium/OI/liquidations) as hard stops.
- Actionable for our bot: adopt the "derivatives checks as hard stops" list.

### 8.3 HaasOnline — Why most grid bots blow up
- URL: https://haasonline.com/blog/why-most-grid-trading-bots-blow-up
- Key takeaways: "trailing down" designs add capital as price falls (averaging down); their fix is anchor-scaling (shrink order size as price runs) and re-anchoring around current price *without* adding capital; still exhausts in a multi-week one-way move.
- Actionable for our bot: re-centre the ladder on fair value continuously (we do by construction) and shrink size on the accumulating side — same idea as inventory-scaled sizing.

### 8.4 tokenmarketmaker.io — MM strategies 2026: grid and delta
- URL: https://www.tokenmarketmaker.io/crypto-market-making-strategies-2026/
- Key takeaways: grid "requires the support of spread optimisation and inventory controls to function safely"; position limits pause buys past a one-sided threshold; widen spread as skew grows.
- Actionable for our bot: same as above; nothing new.

---

## 9. Latency & infrastructure

### 9.1 Where the matching engines answer from (measured)
- Titles: Crypto Exchange Server Locations & Latency Map (Arbitron); Binance Server Location (Arbitron); How far is your exchange? (CCXT blog)
- URLs: https://arbitron.app/learn/crypto-exchange-server-locations ; https://arbitron.app/learn/binance-server-location ; https://docs.ccxt.com/blog/how-far-is-your-exchange
- Key takeaways:
  - Binance fastest from AWS Tokyo ap-northeast-1 (Arbitron ~23 ms REST RTT; CCXT 8 ms). Bybit fastest from Singapore ap-southeast-1 (Arbitron ~16 ms; CCXT 10 ms). OKX fastest from Hong Kong ap-east-1 (CCXT 29 ms; Arbitron lists OKX "closest to Hong Kong").
  - Cross-region penalties (CCXT table): Binance from Singapore 73 ms, from HK 58 ms, from London 229 ms; Bybit from Tokyo 75 ms, HK 40 ms; OKX from Tokyo 88 ms, Singapore 92 ms. Arbitron: Binance from N. Virginia ~424 ms.
  - Region choice "is the single biggest latency win available"; local CDN PoPs do not help live order-book requests.
  - Note: these are REST ping-class numbers from cloud VMs, not colocated order-to-ack. The user prompt's assumption (Tokyo/Binance, HK/OKX, Singapore/Bybit) is consistent with both sources; "Alibaba HK for OKX" not verified. [UNVERIFIED]
- Actionable for our bot: one deployment per venue region (Tokyo for Binance, HK for OKX, Singapore for Bybit); the cross-venue fair-value feed (Binance→OKX/Bybit) will carry ~40–90 ms of geography — budget for it in the "stale window".

### 9.2 Intra-region edge latency and endpoint separation (Binance)
- Title: bn-edge-bench
- Author/site: OctopusTakopi (GitHub); Date: 2026
- URL: https://github.com/OctopusTakopi/bn-edge-bench
- Key takeaways: from a Tokyo instance, Binance edge TCP ~0.18–0.25 ms; WS-API order round-trips p50 ≈ 0.48–0.55 ms (spot/futures), REST ping p50 ≈ 1.6 ms with p99 ≈ 6.8 ms; market-data one-way lag ≈ 1–2 ms. Order-entry hosts (`ws-fapi`) share no IPs with market-data hosts (`fstream`) — benchmark both; edge IP assignment is "luck", so measure the distribution.
- Actionable for our bot: use the WebSocket order-entry API (not REST) on Binance; pin/benchmark edges; separate connections for data vs orders.

### 9.3 Amend vs cancel-replace on our venues
- Titles: Binance "Order Amend Keep Priority" FAQ; Bybit V5 Amend Order; OKX API guide (amend-order)
- URLs: https://developers.binance.com/en/docs/products/spot/faqs/order_amend_keep_priority ; https://bybit-exchange.github.io/docs/v5/order/amend-order ; https://www.okx.com/docs-v5/trick_en/ ; https://www.okx.com/learn/complete-guide-to-okex-api-v5-upgrade
- Key takeaways:
  - Binance spot: `PUT /api/v3/order/amend/keepPriority` (also WS `order.amend.keepPriority`, FIX) keeps time priority but only for *quantity reductions* on symbols with `amendAllowed=true`; cancel-replace (`POST /api/v3/order/cancelReplace`) is atomic but loses priority. (Snippet-verified; the FAQ page itself requires JS.) Futures equivalents not verified here. [UNVERIFIED]
  - Bybit: `POST /v5/order/amend` changes `price` and/or `qty` on unfilled/partially-filled orders; ack is asynchronous — confirm via private WS. Docs do not state priority retention on price change; assume a new-level amend = back of queue. [UNVERIFIED]
  - OKX: `POST /api/v5/trade/amend-order` (and WS `amend-order`) with `newPx`/`newSz`, `cxlOnFail` option, batch up to 20; confirm via `amendResult` in the `orders` channel; mandatory STP at master-account level (`cancel_maker` default).
- Actionable for our bot: prefer size-down amends to keep queue (Binance); for price moves use single-message cancel-replace/amend to minimise time-out-of-market; treat every acknowledgement as asynchronous and reconcile against the private order channel; enable STP.

### 9.4 Cross-region backbone (if one process must see all three venues)
- Title: Ultra-low-latency cross-Region crypto trading with Avelacom and AWS
- Author/site: AWS for Industries blog; Date: 2026
- URL: https://aws.amazon.com/blogs/industries/ultra-low-latency-cross-region-crypto-trading-with-avelacom-and-aws/
- Key takeaways: Tokyo↔Singapore P50 RTT 68 ms via VPC peering vs 65.4 ms via Direct Connect (only 3.8% better); Tokyo↔Frankfurt 224 → 137 ms (39%). AWS names Binance/Tokyo, Bybit/Singapore.
- Actionable for our bot: Asia intra-region links are already near light-speed; don't pay for private backbone between Tokyo/Singapore/HK; run per-venue quoters with a shared but tolerant fair-value bus.

### 9.5 Quote-to-fill and the logger-first mindset
- Sources: Thogiti (§3.1) — "the model reacted in time, and the order did not"; realistic-mm-backtester README (https://github.com/tfrmma/realistic-mm-backtester) — FIFO queue sim, lognormal latency ("fits colo latencies well"), iceberg detection, "your strategy sees a stale book; your orders arrive late".
- Actionable for our bot: instrument every order with `t_decision → t_sent → t_ack → t_fill` and every cancel with `t_decision → t_confirmed`; the cancel-confirm latency defines our snipeable window.

---

## 10. Realistic expectations

### 10.1 Naive A-S backtests turn negative once fees/latency are added
- Titles: Haoyu-tech A-S research project (Binance Futures BTCUSDT L2); Starkl7/Crypto_MM (C++ walk-forward on Coincall BTCUSD perp)
- URLs: https://github.com/Haoyu-tech/An-Avellaneda-Stoikov-market-making-research-project-built-on-real-Binance-Futures-BTCUSDT-L2-data. ; https://github.com/Starkl7/Crypto_MM/blob/main/README.md
- Key takeaways:
  - Haoyu-tech 5-minute baseline: 5 fills, gross +0.0453 USDT, fees 0.169 USDT, net −0.1237 USDT; "once realistic fees are added, net PnL often turns negative"; latency/refresh materially change fills; larger size raises both return and drawdown.
  - Crypto_MM (snippet; README fetch returned empty [UNVERIFIED]): 105 walk-forward windows, negative PnL even before fees; σ-adaptive horizon + tighter inventory bounds (q=±5) cut losses 58% and drawdown 47%; linear-in-σ half-spread (α=1) "cut extreme-vol losses by ~87%"; realised spread negative on average.
- Actionable for our bot: expect naive A-S to lose; the fixes that helped (linear-σ spread, tight inventory caps, σ-adaptive horizon) match Hummingbot's implementation choices (§1.4).

### 10.2 Bar-level backtests overstate results
- Title: Market Making in Python (Backtested) — Manifold-BT
- URL: https://www.manifoldbt.com/strategies/market-making-python
- Key takeaways: 1-minute fair-value-fade proxy reports +16.3%, Sharpe 1.42, max DD −7.8%, 9,820 trades — the author says to treat numbers as "directional, not literal" because queue position and live quoting are not modelled.
- Actionable for our bot: do not use bar backtests as evidence; only tick/L2 replay with queue + latency.

### 10.3 Independent-crypto-MM viability (HFT Book)
- Title: Crypto market making
- URL: https://hftradingbook.com/markets/crypto
- Key takeaways: accessible (no prime broker, free L2 over WS, 24/7) but "counterparty/venue risk is the dominant risk"; wash volume and fake depth corrupt fair value/toxicity estimates; books gap; "the very top of crypto market making is now contested by the same pro firms"; opening is "one rung down (second-tier pairs, smaller venues)". [SYNTHETIC] example uses 20 bp spread, 4 bp taker, no rebate; funding must be netted into PnL.
- Actionable for our bot: pair universe = second-tier liquid pairs on our three venues; keep most capital off-exchange; venue diversification.

### 10.4 Why retail MM bots lose (aggregated)
- Sources: CCXT (§4.2), marketmaker.cc (§5.1), Daru (§3.2), Albers (§3.3), AlSharif (§6.3), Reddit threads (§6.4), cryptoaimeta explainer (https://cryptoaimeta.com/crypto-market-makers-explained/), Polymarket LP guide (https://polymarkets.co.il/en/guide/liquidity-rewards/), Paybis guide (https://paybis.com/blog/your-first-market-making-bot-crypto-trading-guide/)
- Key takeaways:
  - Fees at retail tier ≥ the edge; adverse selection ≥ half-spread on touch quotes; stale quotes around news; inventory accumulation in trends; cancel/replace churn → back-of-queue toxic fills; outages leaving quotes exposed ("Market makers are most visible when they disappear").
  - Headline yields are promotional: Paybis "professional… 15–30% APY; retail grid bots 10–20%" [UNVERIFIED, promotional]; Polymarket LP guide claims 40–120% APY net for disciplined makers with rewards but warns "a single bad week of adverse selection… can wipe out a month" [UNVERIFIED, different market].
  - No credible source found reporting a *verified* Sharpe or capital for a small independent crypto CEX MM in 2024–2026; the honest data points are negative (§10.1, §6.3) or synthetic.
- Actionable for our bot: set the success criterion as "positive `spread + rebate − adverse selection` per pair after real fees over ≥4 weeks live", not an APY target.

---

## Cross-source consensus (what practitioners agree on)

1. Adverse selection, not spread width, decides profitability; measure it with post-fill markouts at multiple horizons (Thogiti; Daru; HFT Book; Quant Memo; marketmaker.cc).
2. Naive touch quoting on one-tick-wide majors is net negative before fees; back-of-queue fills are the toxic ones (Daru; Albers et al.; marketmaker.cc).
3. Fair value should come from the most liquid/leading venue — in practice Binance — and be updated faster than snipers can act (Robot Wealth; Arrakis; DennTech; Moontower).
4. Inventory must be actively mean-reverted: skew quotes against inventory, hard caps, one-sided quoting at the cap, hedge residual on perps (HFT Book; CCXT; Hummingbot; Wintermute; DWF).
5. Fee-aware minimum spread ≥ 2× maker fee at the tier you actually hold + measured adverse selection; model tiers endogenously (marketmaker.cc; CCXT; Foreseer).
6. Widen or pull quotes in vol spikes, one-sided flow bursts, cancel waves, news and liquidation cascades; "the makers who survive news events weren't quoting through them" (CCXT; Foreseer; greeks.live; Thogiti).
7. Spreads should scale with short-window volatility (NATR / EWMA σ multiples) and by time of day (Hummingbot PMM Dynamic; mm-live; dev.to post-mortem).
8. Latency is defence: deploy in the venue's region (Tokyo/Binance, HK/OKX, Singapore/Bybit), use WebSocket order entry, minimise cancel-confirm latency (Arbitron; CCXT; bn-edge-bench; quantframe).
9. Cancel/replace resets queue priority; use size-down amends where the venue preserves priority; use hysteresis (`order_refresh_tolerance_pct`) to avoid churn (Binance docs; CCXT; Hummingbot).
10. Post-only always; reconcile against private WS; kill switch and dead-man's switch tested (CCXT; Bybit FAQ; Hummingbot MrBig).
11. Backtests without queue position, latency and real fee tier are not evidence (Thogiti; realistic-mm-backtester; Reddit; Haoyu-tech; Manifold-BT).
12. Attribute PnL daily into spread / rebate / inventory / adverse selection; judge the quoter on the first three minus the last with inventory zeroed (Quant Memo; HFT Book).
13. Grid bots are symmetric quoters without inventory control; their failure mode (unbounded accumulation in trends) is exactly what skew + caps fix (Neutralis; crypto-resources; HaasOnline).
14. Perps add funding carry: net `−q·f` into the objective, check funding sign before carrying inventory over settlement, read the settlement interval from the API (HFT Book; funding-aware HJB paper; Binance announcements).
15. Range-bound markets with uninformed (retail) flow are where MMs earn; trends and informed/other-MM flow are where they "get run over" (Hummingbot; Wintermute; MrBig).
16. Start wide, tighten only on evidence; paper trade weeks; small size; scale with data (MrBig; mm-live; CCXT).
17. Venue/counterparty risk is first-order in crypto: diversify venues, sweep funds, monitor exchange health (HFT Book; Kairon Labs).
18. Defensive logic is necessary but not an edge; an edge needs a fair-value signal or pair selection (AlSharif; Robot Wealth; Albers et al.).

## Disagreements / open questions

- σ vs σ² in the spread: the A-S paper uses γσ²(T−t); Hummingbot's implementation uses γ·σ (linear) with normalisation, and the Crypto_MM study reports linear-σ cut extreme-vol losses ~87% [UNVERIFIED]. Which scaling to use in crypto's fat tails is unresolved; test both.
- Does Binance permanently lead? Arrakis (perps, 100 ms grid) says yes vs Hyperliquid/Lighter; CoinAPI (spot Binance vs OKX at 1 s) sees no leader and says leadership rotates. Needs our own sub-100 ms HY estimate per pair.
- Imbalance as signal: mm-live and many bots skew *toward* imbalance-implied direction; Albers et al. find profitable maker orders were *contrarian* to imbalance because of queue position. Resolution likely depends on whether you can be front-of-queue.
- Hedge vs skew: firms (Wintermute, DWF) hedge inventory immediately across venues; retail sources (HFT Book, CCXT) rely mainly on skew + caps because hedging costs taker fees and basis. Threshold-based hedging is the compromise; the right threshold is unknown for our capital.
- Funding-aware quoting helped ETH/BTC but not robustly (BTC win rate 0.57; failures in high-funding/high-vol windows) — value of the complexity is unclear.
- Rebate/MM programmes: marketmaker.cc treats them as a wage for writing the option through toxic windows; Hyperliquid Guide treats fee tiers as decisive for profitability. Whether obligations outweigh rebates depends on venue terms.
- Realistic returns: no verified independent-MM Sharpe/APY found; promotional sources (10–30% APY, 40–120% APY with rewards) are unverified and possibly survivorship-biased.
- Amend semantics on Bybit/OKX (priority retained on price change?) and Binance futures keep-priority support remain [UNVERIFIED]; must be tested empirically on testnets.
- OKX hosting (AWS vs Alibaba Hong Kong) — only "closest to HK" is measured; provider unverified.

## Parameter starting points practitioners suggest

| Parameter | Starting point | Source |
|---|---|---|
| Order refresh interval | 30 s default (`order_refresh_time`), 5 s in CCXT skeleton, 100 ms timer in mm-live; use with refresh tolerance / hysteresis | https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making.pyx ; https://docs.ccxt.com/blog/market-making-with-ccxt ; https://github.com/Aliipou/mm-live |
| Max order age | 1800 s (`max_order_age`) | https://hummingbot.org/strategies/v1-strategies/pure-market-making/ |
| Post-fill cooldown | 60 s default (`filled_order_delay`), 300 s example in Academy | https://hummingbot.org/strategies/v1-strategies/strategy-configs/filled-order-delay/ ; https://hummingbot.org/blog/what-is-inventory-risk/ |
| Quoted spread (bps), calm regime | ≥ 2×maker fee + adverse-selection estimate; 20 bp fees-inclusive in CCXT skeleton; ~8–10 bp floor at 4 bp maker (Foreseer HL example); level spreads 1×/2×/4× NATR (PMM Dynamic) | https://docs.ccxt.com/blog/market-making-with-ccxt ; https://foreseer.co/insights/fee-floor-market-making-algorithms ; https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/pmm_dynamic.py |
| Spread multiplier, high-vol regime | trigger when σ_short/σ_long > 1.5 (mm-live); ×1.94 at US open vs ×0.55 Asian midday from measured hourly vol (dev.to) | https://github.com/Aliipou/mm-live ; https://dev.to/crashland/everyone-is-talking-about-ai-trading-bots-we-actually-built-one-heres-what-happened-4cb3 |
| Adverse-selection budget (majors, touch) | ≈0.85–1.04 bp drift at 10 s vs 0.21–0.56 bp capture (Bybit/Binance USD-M/HL) | https://daru.finance/research/crypto-adverse-selection |
| Maker fee assumption | 2 bp base on Binance/Bybit/OKX perps; 10 bp Binance spot base; rebates only at VIP/MM tiers | https://marketmaker.cc/en/blog/post/maker-taker-fees-rebates-execution/ |
| Inventory target / range | target 50% base; `inventory_range_multiplier` 50× order size (HB default); CCXT hard cap 5× order size (0.005 vs 0.001 BTC); Crypto_MM best at q = ±5 units | https://hummingbot.org/strategies/v1-strategies/pure-market-making/ ; https://docs.ccxt.com/blog/market-making-with-ccxt ; https://github.com/Starkl7/Crypto_MM/blob/main/README.md |
| Inventory skew | linear `centre = mid − k·q`, `skew = −(q/q_max)·(spread/2)`; A-S `k = γσ²(T−t)` | https://hftradingbook.com/strategies/inventory-management ; https://docs.ccxt.com/blog/market-making-with-ccxt |
| Side-size modulation | heavy side × exp(−γ·q/Q) (Reddit) [UNVERIFIED]; η shape factor 0..1 (HB A-S) | https://www.reddit.com/r/algotrading/comments/pjsxn4/avoiding_mm_adverse_selection_in_practice/ ; https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/ |
| Risk factor γ (Hummingbot scale) | 1–20 typical, default 1; mm-live 0.05 (paper scale); quantframe paper rerun 0.1 | https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/ ; https://github.com/Aliipou/mm-live ; https://www.quantframe.io/article/institutional-market-making |
| κ (order-book depth / arrival decay) | estimate live; buffers 200 ticks; mm-live default 1.5 | https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/ ; https://github.com/Aliipou/mm-live |
| Volatility window | 200 ticks (`volatility_buffer_size`); NATR(14) on candles; dual EWMA short/long | https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/ ; https://github.com/hummingbot/hummingbot/blob/master/controllers/market_making/pmm_dynamic.py ; https://github.com/Aliipou/mm-live |
| Markout horizons to log | 100 ms, 500 ms, 1 s, 2 s, 5 s, 10 s (and 60 s) | https://thogiti.github.io/2026/01/02/the-spread-is-not-free.html ; https://daru.finance/research/crypto-adverse-selection |
| Queue-position rule | only keep fills when in top ~10% of queue (futures MBO) [UNVERIFIED] | https://www.reddit.com/r/algotrading/comments/pjsxn4/avoiding_mm_adverse_selection_in_practice/ |
| Per-fill backstop (V2 executors) | stop_loss 3%, take_profit 2%, time_limit 2700 s, cooldown 60 s, rebalance threshold 5% (examples) | https://hummingbot.org/blog/dashboard-tutorial-pmm-simple-v2/ |
| Hanging order cancel distance | 10% from mid (`hanging_orders_cancel_pct` default) | https://hummingbot.org/strategies/v1-strategies/pure-market-making/ |
| Config hot-reload interval | 60 s (`config_update_interval`) | https://hummingbot.org/strategies/v2-strategies/walkthrough-controller/ |
| Deployment region | Binance: AWS Tokyo (~8–23 ms REST RTT); Bybit: AWS Singapore (~10–16 ms); OKX: Hong Kong (~29 ms) | https://docs.ccxt.com/blog/how-far-is-your-exchange ; https://arbitron.app/learn/crypto-exchange-server-locations |
| Order-entry latency target (Binance, in-region) | WS-API p50 ≈ 0.5 ms round trip; REST p50 ≈ 1.6 ms, p99 ≈ 6.8 ms | https://github.com/OctopusTakopi/bn-edge-bench |
| Cross-venue lead time (Binance → others) | ~100 ms to Lighter, ~700 ms to Hyperliquid (perps); Binance↔OKX not resolvable at 1 s | https://arrakis.finance/blog/crypto-price-discovery ; https://www.coinapi.io/tutorials/analyzing-lead-lag-effects-between-exchanges-flat-files |
| Funding settlement | Binance USDⓈ-M: 8 h or 4 h; 1 h when capped; revert after 16 calm hourly cycles (|rate| ≤ 0.025%) | https://www.binance.info/en/support/announcement/detail/e4445d0389ce4defa6009021fcf6ee46 |
| Global loss cap (grid practitioners) | 25–30% of committed capital [UNVERIFIED secondary] | https://neutralis.finance/insights/crypto-market-making-bot-grids |
| Paper-trading period before live | "minimum of several weeks under diverse market conditions" | https://github.com/Aliipou/mm-live |
