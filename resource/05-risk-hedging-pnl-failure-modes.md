# 05 — Risk Management, Hedging, PnL Attribution & Failure Modes for a CEX Market-Making Bot

Scope: spot + USDT-margined perps on OKX / Binance / Bybit. Research date: 2026-09-20.
Every claim carries a URL. Exchange-API facts were read from the vendor docs on the research date; re-verify before relying on them in code (endpoints, limits and eligibility change).

Notation used throughout: `side ∈ {+1 (we bought), −1 (we sold)}`, `p` = our fill price, `m_t` = mid at time `t` (mid at fill = `m_0`), `q` = signed inventory (base units), `τ` = horizon, `f` = fee rate (negative for rebate), `Q` = hard inventory bound.

---

## 1. PnL decomposition, markouts, effective vs realized spread, fill toxicity

### 1.1 Top-level accounting identity

Per instrument, per period:

```
PnL_total = PnL_spread_capture + PnL_inventory + PnL_fees_rebates + PnL_funding + PnL_hedge
```

- **Spread capture (realized spread)**: what you keep per fill after the market has moved — the part of the half-spread that adverse selection did not take back.
- **Inventory / positional PnL**: mark-to-market on the position you were left holding (`q_t · (m_{t+1} − m_t)` summed). For a MM this should be noise around zero; a persistent sign means you are running a directional bet you did not choose.
- **Fees/rebates**: maker fee (or rebate) on passive fills + taker fee on hedges and forced flattening. Fee-tier drop-off is a real PnL risk (Section 5).
- **Funding**: perps only; paid/received every funding interval on the perp leg (hedge or quoting leg). Kraken's primer on hedging spot with perps: funding is the recurring cost of holding the hedge; when funding is positive shorts *receive*, when negative shorts *pay* (https://www.kraken.com/learn/futures-trading-hedging-spot-with-perps).
- **Hedge PnL**: taker cost + basis move on the hedge leg (Section 2.6).

### 1.2 Markout — the core per-fill diagnostic

Definition (identical across Strasmore, Quant Memo, QuestDB):

```
markout(τ) = side × (m_{t+τ} − p)                       [vs fill price: "money" markout]
mid_markout(τ) = side × (m_{t+τ} − m_0)                 [vs mid-at-fill: pure adverse selection]
```

- Positive = the market moved *toward* you after the fill; negative = adverse selection (https://quantmemo.com/concepts/markout-analysis, https://www.strasmore.com/blog/trade-markouts-explained).
- Measuring against the mid at fill strips the spread out and isolates post-trade drift; measuring against fill price includes the half-spread you earned (https://www.strasmore.com/blog/trade-markouts-explained).
- Normalize to bps of fill price (`× 1e4 / p`) for aggregation, and also keep the currency version (`× qty`) because 0.1 bp on $100M ≠ 0.1 bp on $1M (https://questdb.com/docs/cookbook/sql/finance/markout/).

Horizons to compute for every passive fill: **1s, 10s, 1m, 5m** (plus 100ms if you have it). Interpretation of the aggregate curve (mean markout vs τ):

- Flat or improving with τ → uninformed flow, you are earning spread (https://quantmemo.com/concepts/markout-analysis).
- Worsens then stabilizes within ~1–2s → fast, latency-sensitive informed flow (latency arbs picking off stale quotes).
- Keeps worsening out to 1m+ → slower, fundamentals/positioning-driven informed flow (https://quantmemo.com/concepts/markout-analysis).

### 1.3 Maker PnL decomposition per fill (capture + adverse drift − fee)

From the Daru Finance true-aggressor-signed CME study (https://daru.finance/research/market-making):

```
capture       = side × (m_0 − p)          ≥ 0 by construction for a passive fill
adverse(τ)    = side × (m_τ − m_0)        ≤ 0 on average when flow is informed
net(τ)        = capture + adverse(τ) − f
```

Empirical warning from that paper: across 13 CME roots / 353k fills, captured half-spread was +0.654 bp and adverse drift at 10s was −0.661 bp → net −0.022 bp (≈ zero). In stress weeks (SVB, COVID, FOMC) adverse/capture ran 105–112%, i.e. adverse selection *over*-consumes the spread and the maker loses. Also: an Avellaneda–Stoikov inventory-skew family did not beat naive touch quoting net of fee on that data (https://daru.finance/research/market-making). Treat this as the null hypothesis for your own bot: you must show your markout curve beats it.

### 1.4 Effective spread vs realized spread vs price impact

Full-spread convention (multiply half-spread quantities by 2):

```
effective_spread   = 2 × side_taker × (p − m_0)          # what the taker paid, relative to mid at fill
realized_spread(τ) = 2 × side_taker × (p − m_τ)          # what the maker keeps after τ
price_impact(τ)    = 2 × side_taker × (m_τ − m_0)        # = adverse selection component
effective_spread   = realized_spread(τ) + price_impact(τ)  # exact identity
```

(https://www.strasmore.com/blog/trade-markouts-explained). The split depends on τ, so never publish a "realized spread" without its horizon.

**Quoted spread** `= a_t − b_t` (best ask − best bid) is what you *offer*; **effective** is what actually trades (can be tighter than quoted if fills happen inside, or wider if the taker walks the book). Track `effective / quoted` ratio per venue; a ratio persistently < 1 while realized(τ) is negative means your quotes are being hit exactly when they are stale.

### 1.5 Fill toxicity — how to compute it

Per-fill toxicity score (use as a label for counterparty/flow classification):

```
tox_i(τ) = −mid_markout_i(τ) / half_spread_at_fill_i
         = −side × (m_τ − m_0) / ((a_0 − b_0)/2)
```

- `tox ≈ 0` benign, `tox ≈ 1` the adverse move ate exactly your half-spread, `tox > 1` you lost money on the fill before fees.
- Aggregate: **toxicity ratio** `Σ adverse(τ) / Σ capture` over a window. Daru's calm-market value ≈ 1.0 and crisis ≈ 1.05–1.12 (https://daru.finance/research/market-making); a healthy crypto MM should target `< 0.7` at 10s on its main pairs, or the strategy is a fee-rebate play, not spread capture.
- Break-even / horizon model (https://uditsamani.com/markouts/):

```
E[PnL_LP(τ)] = s/2 − α·μ·(1 − e^{−λτ})
```
  where `α` = fraction of informed flow, `μ` = mean adverse move size, `λ` = speed of information incorporation. Toxic regime iff `s/2 < α·μ`. Use this to set the *minimum* half-spread you may quote: `s*/2 = α·μ` (estimate α·μ from your own 1m markouts).

- Slice toxicity by: venue, pair, hour-of-day (UTC), fill size bucket, queue position at fill, whether the fill was the first level-clearing trade, and whether a cross-venue reference price moved in the prior 100–500 ms. The last slice is the direct test for latency-arb pick-offs (Section 5.1).

### 1.6 Operational checklist for attribution

1. Store for every fill: venue, symbol, side, qty, price, our mid at fill, reference (cross-venue) mid at fill, order id, time-in-queue, fee, liquidity flag (maker/taker).
2. Store mids at fill+1s/10s/1m/5m (event-driven join, e.g. QuestDB `HORIZON JOIN` pattern: https://questdb.com/docs/cookbook/sql/finance/markout/).
3. Daily report: PnL by bucket (spread/inventory/fees/funding/hedge), markout curve by venue×pair, toxicity ratio, effective/quoted spread, share of fills within 500 ms of a reference-price jump.

---

## 2. Inventory risk controls and hedging

### 2.1 Position limits (absolute and % of capital)

Layered limits per instrument and per venue (all in quote currency, USDT):

```
soft_limit  = k_soft × capital_allocated_to_pair     (e.g. 20–30 %)
hard_limit  = k_hard × capital_allocated_to_pair     (e.g. 40–50 %)
abs_cap     = min(hard_limit, X × ADV_1min_notional)  # never hold more than you can flatten in ~1 min at 2× taker
```

- At **soft**: skew quotes (2.2) and shrink the size on the side that adds inventory.
- At **hard**: stop quoting the side that adds inventory (Guéant–Lehalle–Fernandez-Tapia: at `q = Q` the bid is removed, at `q = −Q` the ask is removed; https://arxiv.org/html/1105.3115v5). Hummingbot's PMM implements exactly this: with `inventory_skew_enabled`, once base holdings leave the range `target ± inventory_range_multiplier × total_order_size`, no bids (or asks) are emitted (https://hummingbot.org/strategies/v1-strategies/strategy-configs/inventory-skew/).
- Above hard for more than `T_flat` seconds (e.g. 30–60s) or if `|q| > abs_cap`: hedge or flatten via taker (2.5).
- Also set a **portfolio-level gross and net delta cap** in USDT across all pairs/venues (Section 5.4 correlation risk).

### 2.2 Inventory-based skew (reservation price)

Avellaneda–Stoikov reservation price and optimal spread (https://quantmemo.com/concepts/avellaneda-stoikov; original: https://www.math.nyu.edu/faculty/avellane/HighFrequencyTrading.pdf):

```
r(s, q, t)   = s − q·γ·σ²·(T − t)                        # personal mid, leans against inventory
δ_a + δ_b    = γ·σ²·(T − t) + (2/γ)·ln(1 + γ/κ)           # optimal total spread
bid = r − δ_b,   ask = r + δ_a
```

- `γ` risk aversion, `σ` volatility (per √time), `κ` order-book liquidity/arrival decay, `T − t` horizon. For a perpetual MM the `(T − t)` term is an artifact; use the infinite-horizon / inventory-bounded version from Guéant–Lehalle–Fernandez-Tapia, where quotes become asymptotically constant functions of `q` and are computed from a `2Q+1` linear ODE system (https://arxiv.org/html/1105.3115v5).
- Practical linear skew that most bots run:

```
skew_bps(q) = −k_skew × (q / Q)              # shift both quotes by skew_bps; k_skew ≈ 0.5–2 × half-spread
size_bid    = S × clip(1 − q/Q, 0, 2),  size_ask = S × clip(1 + q/Q, 0, 2)
```

- **Time-based inventory decay**: increase `k_skew` with inventory age, e.g. `k_skew(t) = k_0 × (1 + t_held / T_half)`. Rationale: the A-S penalty `q·γ·σ²·(T−t)` grows with the time you expect to hold; a position that has not mean-reverted in `T_half` is evidence of trend, not noise.

### 2.3 When to skew vs when to hedge

| Condition | Action |
|---|---|
| `|q| < soft`, markouts benign | Skew only (cheapest: costs nothing if the other side fills). |
| `soft ≤ |q| < hard`, low vol | Skew hard + one-sided quoting. |
| `|q| ≥ hard`, or 1m markout on the inventory-building side < −(half-spread) | Hedge with perp (taker) now; do not wait for the passive side to fill — that is how "inventory death spirals" happen (Section 5.5). |
| Realized vol spike / kill-switch pre-trigger | Flatten via taker regardless of `q`. |

Economic test: hedge when expected cost of holding exceeds hedge cost:

```
hedge if   γ·σ²·q²·Δt  +  |E[drift | markouts]|·|q|   >   taker_fee×|q|×p + half_spread_perp×|q| + expected_funding
```

### 2.4 Hedging spot inventory with perps (same or different exchange)

- Long spot + equal-notional short perp ≈ delta-neutral, but **not risk-free**: funding can flip sign, basis can widen, the short can be liquidated before spot gains are realized (different accounts/venues), and execution lag leaves residual delta (https://www.kraken.com/learn/futures-trading-hedging-spot-with-perps; https://denizra.com/guides/basis-risk-in-cash-and-carry).
- **Same exchange** (e.g. OKX spot + OKX USDT-swap under one unified/portfolio-margin account): margin nets, no transfer risk, one API. Downside: a venue outage kills both legs at once (Oct 10 2025: Binance internal transfers between Spot/Earn/Futures degraded 21:18–21:51 UTC — https://www.banklesstimes.com/articles/2026/01/31/october-10-crypto-crash-binance-releases-post-mortem-findings/).
- **Cross-exchange hedge**: diversifies venue/counterparty risk and lets you hedge on the venue with the best perp liquidity, but the hedge leg needs its own margin, and rebalancing collateral is exactly what fails in a crash. Wintermute's CEO on Oct 10–11 2025: they could buy on Binance and sell on Coinbase/DeFi but could not withdraw to rebalance, so quoting became "impossible, not unwilling" (https://en.theblockbeats.news/news/59932; https://www.theblock.co/podcasts/big-brain/2025-10-21-breaking-down-cryptos-biggest-ever-liquidation-event-with-wintermute-founder-evgeny-gaevoy-375483). Pre-fund both legs; never rely on intraday transfers in stress.

### 2.5 Hedge execution (taker) cost vs holding

```
hedge_cost   = taker_fee × N + (half_spread_perp + impact(N)) × N       # one-off, N = notional
holding_cost = γ·σ²·q²·Δt (risk charge) + funding × N × Δt/8h + expected adverse drift
```

- Use IOC/limit-at-touch on the perp with a max slippage cap; fall back to market only inside kill-switch flatten (Section 7).
- Hedge in slices when `N > X% of top-5-level perp depth` to avoid paying your own impact; but in a kill-switch scenario prefer certainty over price (Amberdata: 10-bp depth fell 46% in 48h in Oct 2025 — https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse).
- Binance/OKX/Bybit hedge legs are typically `reduceOnly` when *closing*; note that on Oct 10–11 2025 traders reported `reduceOnly` rejections (`-1008 Server busy`, `-4118 ReduceOnly failed`, HTTP 503) for >100 minutes on Binance Futures — Binance disputes the 503 claims (https://coinedition.com/binance-system-failure-reduceonly-order-outage/; https://www.forbes.com/sites/boazsobrado/2025/10/21/locked-out-and-liquidated-traders-blame-binance-for-19-billion-crash/). Design for the hedge venue being unavailable.

### 2.6 Basis and funding risk of the hedge

```
basis_t        = perp_mark_t − spot_index_t
hedge_PnL      = −N_perp × Δbasis  +  funding_received − funding_paid  −  taker_costs
funding_cost/8h ≈ funding_rate × N_perp   (sign: shorts pay when funding < 0)
```

- Basis widens against a short-perp hedge when perps trade at a discount in a sell-off (exactly when you most need the hedge) (https://www.kraken.com/learn/futures-trading-hedging-spot-with-perps).
- Funding is positive most of the time (structural interest component pulls it to ~0.01%/8h) but was negative ~35% of Q2 2026 across six venues, clustering around sell-offs (https://bitsgap.com/blog/what-a-spot-hedge-on-perpetuals-really-cost-in-2026).
- Controls: cap `|basis|` at which you will open a new hedge; alert if `|Δbasis|` over 5 min > X bps; include realized funding in daily PnL; if predicted funding for the next interval exceeds `Y bps` and inventory is small, prefer flattening spot over holding the hedge through the funding timestamp. OKX notes API pressure spikes at funding times (08/16/24 UTC) with `50004` timeouts whose result is *unknown* — do not schedule hedge bursts at those instants (https://www.okx.com/help/api-faq).

### 2.7 Delta-neutral MM (quote both spot and perp)

- Quote spot and perp on the same underlying with a shared inventory book; net delta `Δ_net = q_spot + q_perp` is what you control, and the *basis* becomes your residual risk. Advantage: fills on one leg are naturally offset by fills on the other; you earn two spreads for one unit of delta risk. Disadvantage: a basis blow-out (perp discount in a liquidation cascade) hits both books simultaneously and index-price deviations (Section 3.5, USDe/WBETH/BNSOL) can mark your perp leg at fictitious prices.

---

## 3. Volatility regime handling and historical crash behaviour

### 3.1 Detecting a vol spike (three independent signals, any one can trigger)

```
RV_fast   = sqrt( Σ_{i∈last 60s} (ln m_i − ln m_{i−1})² ) × sqrt(86400/60)    # annualized-ish 1-min realized vol from 1s mids
ratio_RV  = RV_fast / RV_slow(1h)                       # regime ratio; trigger e.g. > 2.5
range_1m  = (max m − min m)_{60s} / m                   # Parkinson-style range, trigger > k × median range
intensity = trades_{10s} / median(trades_{10s}, 1h)     # trade-arrival intensity; trigger > 4
jump      = |m_t − m_{t−1s}| / m > J_bps                 # single-step jump
```

- Also watch: perp-vs-spot basis change, funding prediction, liquidation feed rate (Bybit `allLiquidation`, Binance `forceOrder`), cross-venue mid dispersion, and your own 10s markouts turning sharply negative (Amberdata: on Oct 10 2025 "liquidity collapsed before price did" — https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse).

### 3.2 Graduated response

| Level | Trigger (examples) | Quote action |
|---|---|---|
| L0 normal | none | Base spread from A-S: `δ ∝ γσ²` |
| L1 elevated | `ratio_RV > 1.5` or `intensity > 2` | Widen spread ×1.5–2 (σ² scaling), halve size, tighten inventory soft limit |
| L2 stressed | `ratio_RV > 2.5`, `jump > J`, markout(10s) < −half-spread on last N fills | Pull the inventory-adding side; quote only the reducing side; hedge to `|q| < soft` |
| L3 disorderly | L2 + (cross-venue dispersion > X bps or book depth < 30% of 1h median or exchange error rate up) | Cancel all; flatten via taker if `|q| > soft`; halt; requires manual or timed resume |

Wintermute's post-mortem note is instructive: their internal circuit breakers tripped "almost every minute" on Oct 10 and they considered making them *less* aggressive — i.e. tune L2/L3 so you do not flap; add hysteresis (resume only after `ratio_RV < 1.5` for ≥ 5 min) (https://en.theblockbeats.news/news/59932).

### 3.3 Scheduled events — pause or widen

- **CPI / FOMC**: 1-hour BTC realized vol rises ~107 pts after CPI and ~115 pts after Fed decisions; implied vol falls afterwards (https://volmex.finance/papers/Macroeconomic%20Announcements%20Fuel%20Volatility%20An%20In-Depth%20Analysis.pdf). In the first post-FOMC-statement hour (14:00–15:00 ET) mean |BTC return| rises from 0.66% to 1.25% and USD volume ×2.54 (41 statements, 2021–Jan 2026; https://ideas.repec.org/a/eee/finlet/v101y2026ics1544612326006021.html). Intraday RV is elevated roughly 11:00–15:00 ET on FOMC days (https://doi.org/10.4236/jmf.2024.144022). Initial FOMC price reaction tends to reverse over the next ~4 hours (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4478184) — so a MM that survives the first 15 minutes can earn from the reversal. Policy: pull or widen ×3 from T−2min to T+5min; L1 until T+60min.
- **Large token unlocks / listings / delistings**: treat as L1 for the affected pair from T−1h to T+24h, and cap inventory at 25% of normal (no clean quantitative source found in this pass; policy is judgment-based).
- **Exchange maintenance**: OKX states that planned maintenance causing <5s interruption or a WS disconnect *will not be announced* and only happens in low-vol windows; a `64008` notice is sent 60s before WS service upgrades (https://www.okx.com/docs-v5/trick_en/; https://www.okx.com/docs-v5/en/). Bybit similarly does not announce <10s interruptions and exposes `GET /v5/system-status` (https://bybit-exchange.github.io/docs/v5/system-status). Poll status endpoints + announcement feeds; pre-cancel before announced windows.
- **Funding timestamps** (00/08/16 UTC): OKX warns of server pressure and `50004` unknown-result timeouts (https://www.okx.com/help/api-faq). Avoid order bursts ±30s.

### 3.4 What happened to liquidity and MMs in past crashes

**19 May 2021 (BTC −30%)**
- Coinbase web/app/Pro API degraded 05:50–07:38 PT under traffic (https://postmortem.io/incidents/coinbase--2021-05-19--market-volatility-traffic-spike-outage/).
- Binance interface/API delayed or omitted transactions ~13:00–15:10 UTC while liquidations continued; Binance futures price diverged from other venues ~7× more than normal; modelled insurance-fund intervention >$1B (https://www.econstor.eu/bitstream/10419/266345/1/1822049504.pdf).
- Lesson: your "cancel all" may not be honoured for tens of minutes; price on the venue you quote can decouple from the rest of the market → cross-venue deviation kill trigger (Section 7).

**LUNA/UST, 7–12 May 2022**
- Trigger was a sequence of Curve UST/3CRV trades on Sat 7 May plus Anchor outflows; Binance UST/USDT was the most liquid CEX market (https://jumpcrypto.com/resources/the-depegging-of-ust).
- Kaiko order-book data: Binance UST/USDT bid depth fell from ~$6.4M to $3.7M while ask depth rose to $10.7M on 7 May; Coinbase UST/USD min ask depth hit $1,200 (https://www.loyola.edu/_media/sellinger-business/documents/academics/departments/finance/wealth-management-conference/speakers/Joshi_Ravi.pdf). Consistent with Glosten–Milgrom: MMs widened and pulled depth on the side being hit.
- LFG sent 52,189 BTC to Jump to defend the peg; TFL spent hundreds of millions more than received (https://lfg.org/audit/LFG-Audit-2022-11-14.pdf).
- Lesson for a MM quoting stablecoin pairs: a one-sided book (bid depth collapsing, ask depth ballooning) is itself an L3 trigger; never run mean-reversion skew on a pegged asset whose peg is being tested.

**FTX, Nov 2022**
- Genesis had $175M stuck on FTX; Wintermute admitted remaining funds "within risk tolerance"; K33 puts Wintermute's loss at ~$55M (https://k33.com/research/archive/articles/the-ftx-collapse-more-contagion; https://cointelegraph.com/news/the-ftx-contagion-which-companies-were-affected-by-the-ftx-collapse).
- Kaiko "Alameda gap": BTC 2% depth fell 57% on Kraken, 25% Binance, 18% Coinbase as MMs "aggressively reduc[ed] their exposure to most centralized exchanges" (Gaevoy) (https://www.theblock.co/post/188845/crypto-market-liquidity-dries-up-following-alameda-and-ftx-collapse); still ~55% below pre-FTX a year later (https://crypto.news/kaiko-reports-alameda-gap-still-exists/). Jump and Wintermute net-withdrew ~$362M and ~$144M from exchanges in the week (https://members.delphidigital.io/reports/the-aftermath-of-ftxs-downfall).
- Lesson: exchange counterparty risk is a first-order MM risk; cap per-venue capital and sweep excess (Section 4.8).

**5 Aug 2024 (BTC −20%, <$50k)**
- Kaiko: $100k-order slippage tripled within hours on major US exchanges and stayed elevated; KuCoin BTC-EUR >5%; even stablecoin-quoted pairs on BitMEX/Binance.US deteriorated; liquidity increasingly weekday-concentrated post-ETF, so weekend-starting sell-offs are worse (https://www.kaiko.com/resources/moving-markets-liquidity-and-large-sell-orders; https://cryptoslate.com/crypto-liquidity-crisis-causes-major-price-slippages-during-sell-offs-kaiko-reports/).
- Lesson: size limits should be a function of *live* depth, not static; weekend/Asia-hours limits lower.

**10–11 Oct 2025 ("10/10", >$19B liquidations)**
- FTI: BTC top-of-book depth on key venues fell >90%; spreads went from single-digit bps to double-digit % at extremes; "many market makers either widened their spreads dramatically or stepped away altogether" (https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity).
- Binance-local depeg: USDe to ~$0.65, WBETH 80–90% below redemption, BNSOL to $0.13, because collateral was marked off Binance's own thin spot books (https://llamarisk.com/research/when-pricing-breaks-usde). USDE/USDT liquidity on Binance fell 74% ($89M→$23M) in 15 minutes and to ~$2M by 21:54 UTC with 22% spreads (https://ct.com/research/exclusively-obtained-orderbook-data-reveals-details-about-usde-crash).
- Binance's own post-mortem: macro shock + record leverage + "market makers' automated risk controls sharply reduced exposure, pulling liquidity" + ETH congestion; two platform incidents (transfer degradation 21:18–21:51, index deviations 21:36–22:15); ~75% of liquidations before the depeg; >$328M compensation; tightened deviation thresholds, cross-exchange reference pricing (https://www.banklesstimes.com/articles/2026/01/31/october-10-crypto-crash-binance-releases-post-mortem-findings/; https://www.htx.com/news/binance-says-macro-shock-not-exchange-failure-drove-octobers-3r1HDSWw).
- MMs who did *not* pull: one reported −591,835 USDT on DOGE/XRP after risk-reducing orders were rejected for >100 min (https://coinedition.com/binance-system-failure-reduceonly-order-outage/). Wintermute had short positions ADL'd at ~$5 when the token traded at ~$1 — "cannot be hedged" — and could not move inventory between venues (https://en.theblockbeats.news/news/59932).
- Liquidity did not fully recover: 10-bp BTC depth $48M→$26M in 48h, still ~40% below peak three months later; MM funding-arb yields collapsed and MMs "have been slow to return" (https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse; https://www.coingecko.com/learn/october-10-crypto-crash-explained). Binance perp OI fell ~50% on average, >64% on 50+ instruments (https://www.odaily.news/en/post/5206861).
- Lessons: (i) ADL is a real MM tail risk on altcoin perps — cap perp inventory per pair to what you can afford to have ADL'd at a bad price; (ii) your hedge venue's *index* can be wrong — kill on index-vs-cross-venue deviation; (iii) reduceOnly is not guaranteed to execute; (iv) pre-fund every venue.

**5–6 Feb 2026 (BTC < $60k intraday, −12.6% day)**
- Multi-asset deleveraging: CME basis unwinds, IBIT record $10B volume and 2.33M options contracts, short-gamma/vanna hedging; ~$1B BTC liquidations in 24h after $2.5B the prior weekend; 1% depth "down meaningfully vs 2025" (https://convexdispatch.substack.com/p/the-day-liquidity-died-the-february; https://www.coindesk.com/markets/2026/02/07/blackrock-bitcoin-etf-options-errupt-in-crash-hedge-fund-blowup-or-just-market-madness; https://dgt10011.substack.com/p/so-what-happened-on-25). VanEck: −6.05σ rate-of-change day; futures OI fell >20% in a week (https://www.vaneck.com/us/en/blogs/digital-assets/matthew-sigel-what-triggered-bitcoins-major-selloff-in-february-2026/).
- Lesson: crypto vol shocks increasingly originate in TradFi hours (US 09:30–16:00 ET) via ETF/options dealers; treat US equity open/close and options expiry as L1 windows.

### 3.5 Index-price risk on perps (specific to hedging on Binance/OKX/Bybit)

- Your perp hedge is marked to the venue's index/mark price; if the venue overweights its own thin spot book, a local depeg liquidates you even when the global price is fine (LlamaRisk: BNSOL and WBETH index 30%/20% weighted to Binance spot pre-fix; https://llamarisk.com/research/when-pricing-breaks-usde).
- Control: compute your own cross-venue reference index; if `|venue_mark − own_ref| > X bps` (e.g. 50 bps majors, 200 bps alts) → stop adding perp exposure on that venue, and pre-emptively reduce leverage.

---

## 4. Exchange / operational risk and safeguards

### 4.1 Incident history to design against

| Venue | Incident | Source |
|---|---|---|
| Binance | 19 May 2021: API/interface delayed/omitted transactions ~2h during crash | https://www.econstor.eu/bitstream/10419/266345/1/1822049504.pdf |
| Binance | 29 Aug 2025: USDⓈ-M Futures order placement down (18-min trading suspension; 37-min API impact) | https://beincrypto.com/traders-frustrated-binance-futures-temporary-downtime/; https://www.binance.com/en/square/post/307798457395697 |
| Binance | 14 Aug 2025 Kline outage 18 min; 9 Oct 2025 Futures UM order-processing delay 66 min; H2-2025 Futures UM uptime 99.95–99.96% (Spot 100%) | https://www.binance.com/en/square/post/307798457395697 |
| Binance | 10–11 Oct 2025: transfer subsystem degraded 33 min; index deviations 39 min; user reports of 503 / -1008 / -4118 for >100 min (disputed) | https://www.banklesstimes.com/articles/2026/01/31/october-10-crypto-crash-binance-releases-post-mortem-findings/; https://coinedition.com/binance-system-failure-reduceonly-order-outage/ |
| OKX | 27 Mar 2024: REST GET queries returned incorrect (CDN-cached) data 11:39–14:09 UTC, incl. balances/positions | https://www.okx.cab/en-eu/help/mar-27-2024-rest-api-service-issues |
| OKX | Recurring: `50004` timeouts at funding times with unknown order result | https://www.okx.com/help/api-faq |
| Bybit | 21 Feb 2025: ~$1.5B ETH stolen from Safe multisig cold wallet via compromised Safe{Wallet} front-end (Lazarus/TraderTraitor) | https://www.nccgroup.com/research/in-depth-technical-analysis-of-the-bybit-hack/; https://www.fbi.gov/investigate/cyber/alerts/2025/north-korea-responsible-for-1-5-billion-bybit-hack |
| Coinbase | 19 May 2021 traffic-spike outage | https://postmortem.io/incidents/coinbase--2021-05-19--market-volatility-traffic-spike-outage/ |
| FTX | Nov 2022 insolvency; MM funds stuck | https://cointelegraph.com/news/the-ftx-contagion-which-companies-were-affected-by-the-ftx-collapse |

### 4.2 Websocket disconnects and stale books

- **Staleness check**: for each subscribed book, track `t_last_update`; if `now − t_last_update > S_ms` (e.g. 1,000 ms majors / 3,000 ms alts) *and* trades are still printing elsewhere → mark the book stale → cancel quotes on that instrument. Bybit resends L1 snapshots every 3s when unchanged (a heartbeat you can use) (https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook).
- **Sequence integrity**: Bybit — reset the local book on any new `snapshot` or `u == 1` (service restart); use `seq` to order (https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook). OKX — `checksum` is deprecated (fixed to 0); verify continuity with `seqId`/`prevSeqId` and resubscribe on a gap (https://www.okx.com/docs-v5/en/). Binance — track `U/u/pu` per its depth-stream rules and resync from a REST snapshot on a gap.
- **Heartbeats**: Bybit recommends `ping` every 20s; private connections die after 10 min without ping/data (configurable `max_active_time` 30s–10m) (https://bybit-exchange.github.io/docs/v5/ws/connect). OKX sends `64008` 60s before a planned WS disconnect (https://www.okx.com/docs-v5/en/).
- **Reconnect storms**: Bybit limits 500 connections / 5 min per IP; violating it worsens the outage (https://bybit-exchange.github.io/docs/v5/ws/connect). Use exponential backoff with jitter; cancel-on-disconnect (4.4) covers the gap.

### 4.3 Order-state desync, unknown fills, zombie orders

- Exchange acks mean "accepted", not "done": OKX — a cancel is only confirmed when the WS `orders` channel reports `state: canceled`; "successful response only means the request has been accepted" (https://www.okx.com/docs-v5/trick_en/). Bybit batch-cancel is asynchronous — confirm on WS (https://bybit-exchange.github.io/docs/v5/order/batch-cancel).
- **Unknown-result requests**: OKX `50004` (funding-time pressure) — request may have succeeded or failed; query before retrying (https://www.okx.com/help/api-faq). Binance `-1008 Server busy` similar. Rule: on timeout, *never* blindly resend; reconcile by `clientOrderId`.
- **Private stream gaps**: Binance futures user-data streams close after 60 min without keepalive (`PUT /fapi/v1/listenKey`), and there is no replay; on reconnect fetch open orders, positions and recent trades and reconcile (https://developers.binance.com/docs/derivatives/coin-margined-futures/user-data-streams/Keepalive-User-Data-Stream). Nautilus' Binance adapter requests a full mass-status after listen-key rotation precisely because events can land in a window with no subscriber (https://github.com/nautechsystems/nautilus_trader/blob/master/nautilus_trader/adapters/binance/execution.py).
- **Reconciliation loop** (every 5–15s, and immediately on any reconnect/error): pull `openOrders` + `positions/balances` via REST; diff against local OMS; any order on the exchange not in local state = **zombie** → cancel; any local "live" order not on exchange = query by id → mark filled/cancelled; position mismatch > tolerance → freeze quoting until resolved. Idempotency: always set your own `clientOrderId`/`orderLinkId`/`clOrdId`.
- **Request expiry**: OKX `expTime` header makes stale place/amend requests self-discard (https://www.okx.com/docs-v5/en/). Use it on every quote update; on Binance keep `recvWindow ≤ 5000` (default 5000, max 60000) (https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md).

### 4.4 Cancel-on-disconnect / dead-man's switch — venue support

| Venue | Mechanism | Details | Source |
|---|---|---|---|
| **Bybit** | DCP "Disconnect Cancel All" | `POST /v5/order/disconnected-cancel-all` with `timeWindow` 3–300s (default 10s), per product (`OPTIONS`/`DERIVATIVES`/`SPOT`); private WS must subscribe `dcp.future` / `dcp.spot` / `dcp.option`; triggers when *all* DCP-subscribed private connections are dead past the window. **Institutional clients only** (enabled via client manager; VIP retail cannot). | https://bybit-exchange.github.io/docs/v5/order/dcp; https://bybit-exchange.github.io/docs/v5/websocket/private/dcp |
| **OKX** | Cancel All After (countdown) | `POST /api/v5/trade/cancel-all-after`, `timeOut` = 0 or 10–120 s; must be re-armed periodically; cancels all pending order-book orders (spread trading excluded); cancellations tagged `cancelSource = 20`. Not tied to WS state — your heartbeat loop is the trigger. Separate `/api/v5/rfq/cancel-all-after` for RFQ quotes. | https://www.okx.com/docs-v5/en/ (Order Book Trading → Trade → Cancel All After) |
| **Binance USDⓈ-M Futures** | Auto-Cancel All Open Orders (countdown) | `POST /fapi/v1/countdownCancelAll` with `symbol`, `countdownTime` ms (0 = disable); call repeatedly as a heartbeat (e.g. every 30s with 120,000 ms); checked ~every 10 ms; Binance advises not to set it "too precise or too small". **Per symbol.** | https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Auto-Cancel-All-Open-Orders; https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/account.py |
| **Binance Spot** | No account-level cancel-on-disconnect found in the spot REST docs reviewed | Rely on your own watchdog + `DELETE /api/v3/openOrders`; keep a second, independent "cancel-only" process on a different host/IP. | https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md |

Design rule: arm the venue dead-man's switch **and** run an out-of-process watchdog that cancels all if the strategy process misses two heartbeats; the watchdog must use a separate API key (cancel/read only) and IP.

### 4.5 Clock skew

- OKX rejects requests whose `OK-ACCESS-TIMESTAMP` differs from server time by >30s (`50102`); most common cause is local-timezone offsets — always UTC; sync with `GET /api/v5/public/time` (https://www.okx.com/docs-v5/en/; https://www.okx.com/help/api-faq).
- Binance: request valid iff `timestamp < serverTime + 1s` and `serverTime − timestamp ≤ recvWindow` (default 5,000 ms) (https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md).
- Bybit: `10002 The request time exceeds the time window range` (https://bybit-exchange.github.io/docs/v5/error).
- Run chrony/NTP with multiple sources; alert if offset > 200 ms; measure per-venue `serverTime − localTime` on every response and feed it into the staleness logic.

### 4.6 Rate limits and bans

- **Binance**: request-weight limits per IP, order limits per account; `429` on breach with `Retry-After`; continuing after 429 → automated IP ban `418`, 2 minutes to 3 days, escalating for repeat offenders. Unfilled-order count decrements when an order trades, so fills "refund" order budget; `-1015 Too many new orders` (https://developers.binance.com/docs/fiat/general-info; https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/rate-limits; https://developers.binance.com/en/docs/products/spot/faqs/order_count_decrement).
- **Bybit**: 600 requests / 5s per IP; `403 access too frequent` → stop *all* HTTP sessions ≥10 min; per-UID per-endpoint limits → `10006 Too many visits`, `10018 IP rate limit`; headers `X-Bapi-Limit-Status` / `X-Bapi-Limit-Reset-Timestamp` (https://bybit-exchange.github.io/docs/v5/rate-limit; https://bybit-exchange.github.io/docs/v5/error).
- **OKX**: place/amend/cancel limits are independent of each other and shared across REST+WS; sub-account rate limits with fill-ratio-based adjustments (https://www.okx.com/docs-v5/en/).
- Controls: token-bucket per venue at ≤70% of the published limit; **reserve a cancel budget** that quoting can never consume (a ban during a crash that leaves orders resting is the worst case); prefer WS order entry and amend-in-place over cancel/replace; Hummingbot's `rate_limits_share_pct` is a simple pattern for splitting budget across processes (https://mintlify.wiki/hummingbot/hummingbot/configuration/global-settings).

### 4.7 API-key hygiene, IP whitelist, sub-accounts

- Binance: withdrawal permission *requires* IP restriction; system-generated keys without IP restriction are read-only; up to 30 keys per sub-account; keys not IP-whitelisted and inactive 30 days are auto-deleted; one key per purpose (https://www.binance.info/en/support/faq/detail/360002502072; https://www.binance.com/en/blog/security/8638066848800196896). Sub-accounts isolate assets/strategies and can be API-only via virtual email (https://www.binance.info/en/support/faq/detail/360020632811).
- OKX: each key binds up to 20 IPs (IPv4/IPv6/CIDR); permissions are `Read` / `Trade` / `Withdraw`; keys with trade/withdraw permission and no IP binding are deleted after 14 days idle (https://www.okx.com/docs-v5/en/; https://www.okx.com/help/api-faq).
- Bybit: `10010 Unmatched IP` when calling from a non-bound IP; `403` also returned for US IPs (https://bybit-exchange.github.io/docs/v5/error).
- Policy: **no withdrawal permission on any trading key**; one sub-account per strategy×venue; strategy key = trade+read, watchdog key = read+cancel where permission granularity allows, treasury key (withdraw) offline/hardware-gated; rotate keys quarterly; store secrets in a KMS, never in the repo.

### 4.8 Counterparty risk and capital allocation across exchanges

- FTX lesson: MMs with $55–175M stuck; industry-wide depth −50% for a year (Section 3.4). Bybit lesson: even a top-3 venue can lose $1.5B from a "cold" wallet via a supply-chain compromise; Bybit stayed solvent, but the assumption "big exchange = safe custody" is false (https://www.nccgroup.com/research/in-depth-technical-analysis-of-the-bybit-hack/).
- Allocation rules: (i) cap per-venue exposure at `≤ 35–40%` of total MM capital; (ii) keep only working capital + margin buffer on-venue and sweep excess to self-custody daily; (iii) size the buffer so that a full day of one-sided fills at hard limit does not require an intraday deposit (transfers fail in crashes — Wintermute Oct 2025); (iv) pre-agree an "exit ladder": at rumours/withdrawal delays → stop adding inventory, hedge off-venue, drain to minimum; (v) monitor proof-of-reserves, withdrawal latency, and stablecoin/perp basis on that venue as early-warning signals.

---

## 5. Strategy risk

### 5.1 Adverse selection by latency arbitrage / being picked off

- Mechanism: Binance leads price discovery; slower venues carry stale quotes for hundreds of ms (Hyperliquid ~700 ms lag, Lighter ~100 ms, in one 29-market study) and arbitrageurs fire IOCs at the stale price while MMs race to cancel (https://arrakis.finance/blog/crypto-price-discovery). Large-scale live experiments on Bybit/Binance show a consistent adverse-selection effect: profitable taker orders fail to fill or get worse prices, unprofitable ones fill as expected — the mirror image for the maker is that your quotes fill precisely when they are wrong (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4677989). Maker orders exhibit a "negative drift": if the next tick is against you, you fill with probability 1 (https://arxiv.org/html/2502.18625v2).
- Detection: fraction of your fills that occur within 100–500 ms *after* a reference-venue mid jump in the same direction; 1s markouts on those fills. If >30% of fills are jump-coincident, you are the liquidity provider to latency arbs.
- Mitigation: quote off a **cross-venue fair value** (Binance-led composite), not the local mid; pull/re-price on reference jumps before local book reacts; use amend (OKX/Bybit support amend-in-place) rather than cancel/replace to keep queue position; widen on venues where your feed-to-order round-trip is slow; co-locate/regional VPS near matching engines (OKX INC. moved latency-sensitive services HK→Tokyo mid-2026: https://www.okx.com/en-us/help/okx-us-trading-server-migration-announcement-hong-kong-tokyo).

### 5.2 Stale quotes after a jump

- Set a **max quote age** (e.g. 500 ms majors, 2 s alts) after which an order is amended or cancelled regardless of book state; use OKX `expTime` so in-flight requests cannot land late (https://www.okx.com/docs-v5/en/).
- On any `jump > J_bps` in the reference price: cancel-all on that instrument first, re-quote second. Never re-quote from a book that has not updated since the jump (Section 4.2 staleness).

### 5.3 Thin books and low-liquidity hours

- Depth is weekday/US-hours concentrated post-ETF; weekend sell-offs overshoot (https://cryptoslate.com/crypto-liquidity-crisis-causes-major-price-slippages-during-sell-offs-kaiko-reports/). Oct 10 2025 near-mid BTC depth on Binance at 0.1% was ~0.01 BTC while wider bands held 8 BTC (https://www.datawallet.com/crypto/october-10-crypto-crash-explained).
- Controls: scale quote size and inventory limits with live depth (`size ≤ x% of depth within 10 bps`); do not quote more levels than the book can absorb; lower limits 00:00–06:00 UTC and weekends; halt quoting on a pair when top-5-level depth < 20% of its 24h median.

### 5.4 Correlation risk across many pairs

- Alts are highly correlated in crashes; 50+ Binance perp instruments lost >64% OI on 10/10 (https://www.odaily.news/en/post/5206861). Quoting 30 pairs "diversifies" only in calm markets; in stress every bid fills at once.
- Control: portfolio net delta in BTC-beta terms `Δ_β = Σ β_i q_i p_i`, capped separately from per-pair limits; hedge `Δ_β` with BTC/ETH perps when it exceeds the cap; run a daily stress test: "all bids fill to hard limit, then market −15%" and make sure the loss < daily loss limit.

### 5.5 Inventory death spiral in trending markets

- Pattern: price trends down → your bids fill → you skew lower → still filled → inventory grows → you widen the ask to "get paid" → ask never fills → hard limit → forced taker flatten at the low. Amberdata's description of 10/10 is exactly this at market scale: every fill followed by more forced selling, so rational MMs pulled quotes (https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse).
- Controls: (i) markout-gated quoting — if the last N fills on one side have mean 1m markout < −half-spread, stop quoting that side (trend detection via your own fills); (ii) inventory age decay (2.2); (iii) hedge at *hard*, do not wait for passive exit; (iv) daily loss limit (Section 6).

### 5.6 Fee-tier drop-off and competition

- Maker fee/rebate tiers depend on 30-day volume and holdings (BNB/OKB etc.); losing a tier can flip `net = capture + adverse − f` negative because `capture ≈ −adverse` (Daru). Track projected tier daily; include fees at the *next-lower* tier in the go/no-go for each pair.
- Competition: post-10/10, MMs' funding-arb returns fell below ~4% and they were slow to return (https://www.coingecko.com/learn/october-10-crypto-crash-explained); when competitors return, spreads compress. Monitor your fill share and effective/quoted ratio; when the market half-spread falls below your `α·μ` floor (1.5) on a pair, stop quoting it rather than "competing".

---

## 6. Risk metrics, monitoring, and capital sizing

### 6.1 Real-time dashboard (1s–10s refresh) and alert thresholds

| Metric | Definition | Warn | Critical |
|---|---|---|---|
| PnL (realized + MTM) per venue/pair/total | Section 1.1 buckets | −0.5 × daily limit | −1.0 × daily limit (kill) |
| Inventory `q·p` per pair, net Δ_β | Section 2.1, 5.4 | > soft | > hard (kill side / hedge) |
| Inventory age | time since `|q|` last crossed 0.25×soft | > 10 min | > 30 min |
| Markout 1s/10s/1m (rolling 100 fills) | Section 1.2 | < 0 at 10s | < −half-spread at 10s |
| Toxicity ratio | Σ adverse/Σ capture | > 0.8 | > 1.0 |
| Fill rate / quote uptime | fills per hour; % of time two-sided | uptime < 90% | fill rate 5× median (you are the only bid) |
| Quoted vs market spread | our spread / touch spread | < 1 (we are tightest) | — |
| Book staleness | `now − t_last_update` | > 500 ms | > S_ms (kill quotes) |
| Order round-trip latency p50/p99 | send→ack | p99 > 300 ms | p99 > 1 s |
| Exchange error rate | rejects+timeouts / requests (1 min) | > 2% | > 10% (kill) |
| Rate-limit headroom | used/limit | > 70% | > 90% |
| Ref-price deviation | `|venue_mid − composite|` bps | > 10 (majors) | > X (kill; 3.5) |
| Basis / funding | Section 2.6 | Δbasis 5m > X | predicted funding > Y |
| Clock offset per venue | `serverTime − local` | > 200 ms | > 1 s |
| Reconciliation diffs | zombies, unknown fills, position mismatch | any | position mismatch (freeze) |

### 6.2 Daily loss limit and drawdown-based deleveraging

```
daily_loss_limit  = L_d × capital        (e.g. 1–2 % for a MM book)
dd_t              = (peak_equity − equity_t) / peak_equity
size_multiplier   = clip(1 − dd_t / dd_max, 0.25, 1)     # linear delever; dd_max e.g. 8 %
hard_stop         = dd_t ≥ dd_max  or  daily_PnL ≤ −daily_loss_limit
```

- Hummingbot's global kill switch stops the bot at a configured session PnL rate (e.g. `kill_switch_rate: -5`), but it measures session PnL only, excludes previous sessions and unrealized PnL — a reminder to define *your* limit on total (realized + MTM) PnL with a daily reset (https://hummingbot.org/client/global-configs/kill-switch/; https://mintlify.wiki/hummingbot/hummingbot/configuration/global-settings).
- After a hard stop, resume requires: reconciled positions, root cause written, and either next UTC day or manual override.

### 6.3 Sharpe / Sortino / Calmar for MM strategies

```
Sharpe  = (R̄ − r_f) / σ_R                     # all volatility
Sortino = (R̄ − T) / DR,  DR = sqrt(E[min(R − T, 0)²])   # downside only
Calmar  = CAGR / |MaxDD|
```
(https://en.wikipedia.org/wiki/Sortino_ratio; https://www.investopedia.com/terms/c/calmarratio.asp)

- MM return series are high-frequency, positively skewed in calm and violently negatively skewed in stress; Sharpe on daily returns will look great until the one day that matters. Report **Sortino and Calmar** alongside Sharpe, and always compute on the *full timeline* (including flat periods), not per-trade (https://marketmaker.cc/en/blog/post/objective-function-design-backtest/). Shrink any ratio by `n/(n+k)` for small samples (same source).
- Include crash days (19 May 2021, 9–12 May 2022, 8–10 Nov 2022, 5 Aug 2024, 10–11 Oct 2025, 5–6 Feb 2026) in every backtest and report the strategy's PnL on those days separately.

### 6.4 Capital sizing (Kelly-ish for MM)

```
f*_i = μ_i / σ_i²                 # continuous Kelly leverage for strategy i (QuantStart)
f*   = Σ⁻¹ μ                      # multi-strategy / multi-venue version
deploy = c × f*,  c ∈ [0.25, 0.5]  # fractional Kelly
```
(https://www.quantstart.com/articles/Money-Management-via-the-Kelly-Criterion/)

- Full Kelly has a 50% chance of a 50% drawdown even under Gaussian assumptions; half-Kelly ~12.5%, quarter-Kelly a fraction of a percent; MMs face margin calls and forced reductions at the worst moment, so the smooth equity curve has standalone value; add hard caps (max per position, max leverage, max drawdown) on top (https://marketmaker.cc/en/blog/post/kelly-criterion-strategy-sizing/). Institutional practice: shrink the edge estimate first, compute raw Kelly, impose an explicit drawdown-probability constraint (Busseti–Ryu–Boyd), then external hard caps (https://www.atlaspeakresearch.com/report/07bf72).
- For MM specifically: estimate `μ, σ` from *live* daily PnL on the pair/venue (not backtest), re-estimate monthly with a 3–6-month window; the Kelly output sets the **inventory hard limit and quote size**, and the per-venue cap from 4.8 overrides it.

---

## 7. Kill-switch design

### 7.1 Trigger conditions (any → level shown)

| # | Condition | Level | Rationale/source |
|---|---|---|---|
| K1 | Daily PnL ≤ −daily_loss_limit, or dd ≥ dd_max | HALT | 6.2 |
| K2 | `|q|` > hard limit for > T_flat, or Δ_β > portfolio cap | FLATTEN | 2.1, 5.4 |
| K3 | Book/trade feed stale > S_ms while other venues print | CANCEL (instrument) | 4.2 |
| K4 | Private stream disconnected / listenKey expired / auth failure | CANCEL-ALL (venue) + reconcile | 4.3 |
| K5 | Exchange error/timeouts > 10%/min, or `429/418/403/10006` received | CANCEL-ALL (venue) using reserved cancel budget; back off | 4.6 |
| K6 | `|venue_mid − composite_ref| > X bps` or venue index vs own ref > X bps | CANCEL-ALL (venue); no new perp exposure | 3.5, May-2021 Binance divergence |
| K7 | Reject storm: > N rejects in 10s (e.g. price-limit, insufficient margin, reduceOnly failures) | CANCEL-ALL + HALT quoting | Oct 2025 `-4118` reports |
| K8 | Reconciliation: position mismatch > tol, or unknown fill detected | FREEZE (no new orders) until resolved | 4.3 |
| K9 | RV ratio / jump / one-sided depth collapse (L3) | CANCEL-ALL; FLATTEN if `|q| > soft` | 3.2 |
| K10 | Clock offset > 1 s, or `50102`/`-1021`/`10002` errors | CANCEL-ALL; resync | 4.5 |
| K11 | Scheduled: FOMC/CPI T−2m, announced maintenance T−5m | CANCEL-ALL (pair/venue) | 3.3 |
| K12 | Watchdog: strategy process missed 2 heartbeats | CANCEL-ALL via independent key/IP; venue dead-man's switch fires as backstop | 4.4 |

### 7.2 Actions (ordered, idempotent, each with its own timeout)

1. **Stop new orders** (flag in OMS; all quoting loops check it first).
2. **Cancel all** on the affected scope: venue-level cancel-all endpoints first (`DELETE /fapi/v1/allOpenOrders`, OKX `cancel-batch-orders`, Bybit `cancel-all`), then per-order cancels for anything still `live` after 2s, then verify via WS `orders` channel + REST `openOrders` (OKX: only WS `state: canceled` is confirmation — https://www.okx.com/docs-v5/trick_en/).
3. **Flatten via taker** if the trigger requires: IOC at touch with slippage cap, re-issue every 500 ms up to a max slippage schedule (e.g. 5 → 15 → 50 bps), use `reduceOnly` on perps; if the primary venue rejects, hedge on the secondary venue's perp (cross-venue hedge from 2.4). Expect ADL/rejects in the tail (Oct 2025).
4. **Halt** the strategy process; keep the watchdog and reconciler running; page a human.
5. **Log** trigger, state snapshot (orders, positions, books, last 100 fills with markouts), and all exchange responses.

### 7.3 Recovery procedure

1. Confirm feeds healthy (staleness < threshold for ≥ 60s on all instruments), clock offset < 200 ms, error rate < 1%.
2. Full reconciliation: REST open orders (expect zero), positions/balances vs OMS, last-N trades vs local fills; resolve every diff before step 3.
3. Re-arm dead-man's switches (Bybit DCP topic subscribed; OKX `cancel-all-after` re-set; Binance `countdownCancelAll` per symbol).
4. Resume at **L2 posture** (reduced size, wider spread, tighter limits) for ≥ 15 min with hysteresis (`ratio_RV < 1.5` sustained) before returning to L0 (Wintermute's "don't flap" lesson: https://en.theblockbeats.news/news/59932).
5. K1 (loss-limit) halts do not auto-resume the same UTC day.

---

## 8. Regulatory / compliance notes (brief)

- **Wash trading / self-trades.** Enforcement is active and criminal: SEC charged Gotbit, ZM Quant, CLS Global and nine individuals in Oct 2024 for bot-driven wash trading "as-a-service" (https://www.sec.gov/newsroom/press-releases/2024-166); DOJ's Operation Token Mirrors produced guilty pleas (Gotbit founder, Mar 2025) and, on 30 Mar 2026, indictments of ten individuals across Gotbit, Vortex, Antier, Contrarian, charged as wire fraud (https://www.reuters.com/technology/cryptocurrency-firm-founder-pleads-guilty-us-market-manipulation-scheme-2025-03-21/; https://www.irs.gov/compliance/criminal-investigation/ten-foreign-nationals-charged-in-an-international-operation-targeting-cryptocurrency-market-manipulation; https://www.trmlabs.com/resources/blog/ten-fraudsters-from-four-financial-services-firms-charged-in-different-cryptocurrency-market-manipulation-schemes-out-of-northern-district-of-california). A MM quoting the same book from several sub-accounts *will* self-trade unless STP is on.
  - **Binance** STP modes `NONE / EXPIRE_TAKER / EXPIRE_MAKER / EXPIRE_BOTH / DECREMENT / TRANSFER`, applied per order via `selfTradePreventionMode`; scope is the account or `tradeGroupId`; prevented matches queryable via `GET /api/v3/preventedMatches` (https://developers.binance.com/en/docs/products/spot/faqs/stp_faq).
  - **OKX** STP is *mandatory* at master-account level (incl. all sub-accounts) since 14 Mar 2024; modes `cancel_maker` (default) / `cancel_taker` / `cancel_both` via `stpMode`; STP cancels appear as `cancelSource = 32` (https://www.okx.com/help/okx-to-implement-mandatory-self-trade-prevention; https://www.okx.com/docs-v5/en/).
  - **Bybit** SMP via `smpType` `CancelMaker / CancelTaker / CancelBoth` for same UID or SMP group; note an order's `smpType` is only evaluated when it is the taker; mandatory on some regional sites from 2026-08-04 (https://bybit-exchange.github.io/docs/v5/smp).
  - Policy: set STP on *every* order; use one trading entity per venue where possible; log prevented matches and review daily.
- **Spoofing / layering.** Multi-level quoting is legitimate; the legal line is *intent to cancel before execution* to mislead. CFTC has pursued spoofing in regulated crypto futures, and OKX's API agreement explicitly prohibits configuring automated agents for "wash trading, layering, spoofing, quote stuffing, momentum ignition" (https://web3.okx.com/help/okx-api-agreement). Under MiCA, EU platforms must surveil for layering/wash trading/order-book abuse and file STORs (https://eco.com/support/en/articles/15183698-binance-reserves-regulation-and-us-access-in-2026). Defensive design: quotes must be *executable* (real size, priced to fill with non-trivial probability), cancel/replace driven by observable inputs (fair-value moves, inventory), documented in the strategy spec; keep order-to-trade ratio and cancel-latency stats per venue as evidence; avoid flickering layered orders far from touch.
- **KYC / jurisdiction.** Binance.com blocks US persons (Binance.US is a separate spot-only entity; VPN use was cited in the DOJ settlement) (https://eco.com/support/en/articles/15183698-binance-reserves-regulation-and-us-access-in-2026). Bybit excludes the United States, mainland China, Hong Kong, Singapore, Canada, and others; misrepresenting location can lead to account termination and forced liquidation of open positions (https://www.bybit.com/en/help-center/article/Service-Restricted-Countries); Bybit returns `403` for US IPs (https://bybit-exchange.github.io/docs/v5/error). OKX API access requires a verified KYC account meeting residency requirements and may require disclosure of trading strategies/risk frameworks for API access; OKX US serves only specific states (https://web3.okx.com/help/okx-api-agreement; https://okx.cab/en-us/help/terms-of-service-us). Bybit DCP is restricted to institutional accounts (https://bybit-exchange.github.io/docs/v5/order/dcp) — onboarding as an institution also unlocks better rate limits and support in incidents.

---

## Risk control checklist

| Control | Trigger | Action | Source |
|---|---|---|---|
| Per-fill markout logging (1s/10s/1m/5m) | every passive fill | store `side, p, m_0, m_τ`, compute capture/adverse/net | https://quantmemo.com/concepts/markout-analysis; https://daru.finance/research/market-making |
| Toxicity gate | rolling Σadverse/Σcapture > 1.0 on a pair×venue | widen to `s/2 ≥ α·μ` or stop quoting pair | https://uditsamani.com/markouts/ |
| Inventory soft limit | `|q·p|` > 20–30% pair capital | skew `r = s − qγσ²`, shrink adding side | https://quantmemo.com/concepts/avellaneda-stoikov |
| Inventory hard limit | `|q|` ≥ Q | remove adding-side quote entirely | https://arxiv.org/html/1105.3115v5; https://hummingbot.org/strategies/v1-strategies/strategy-configs/inventory-skew/ |
| Forced hedge/flatten | hard limit > T_flat, or adverse markouts on adding side | IOC perp hedge with slippage cap; reduceOnly | https://www.kraken.com/learn/futures-trading-hedging-spot-with-perps |
| Basis/funding guard | `|Δbasis|_5m` > X bps or predicted funding > Y | no new hedge; prefer spot flatten | https://denizra.com/guides/basis-risk-in-cash-and-carry; https://bitsgap.com/blog/what-a-spot-hedge-on-perpetuals-really-cost-in-2026 |
| Portfolio beta cap | Δ_β > cap | BTC/ETH perp hedge | https://www.odaily.news/en/post/5206861 |
| Vol regime L1–L3 | RV ratio / jump / intensity thresholds | widen → one-side → cancel-all/flatten, with hysteresis | https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse; https://en.theblockbeats.news/news/59932 |
| Event calendar pause | CPI/FOMC T−2m..T+5m; maintenance T−5m | cancel-all pair/venue; L1 to T+60m | https://ideas.repec.org/a/eee/finlet/v101y2026ics1544612326006021.html; https://www.okx.com/docs-v5/trick_en/ |
| Book staleness | no update > S_ms while others print | cancel quotes on instrument; resync book | https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook; https://www.okx.com/docs-v5/en/ |
| Sequence-gap resync | Bybit `u==1`/new snapshot; OKX `seqId` gap | rebuild from snapshot before re-quoting | https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook |
| Venue dead-man's switch | armed always | Bybit DCP (inst.), OKX cancel-all-after 10–120s, Binance futures countdownCancelAll | https://bybit-exchange.github.io/docs/v5/order/dcp; https://www.okx.com/docs-v5/en/; https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Auto-Cancel-All-Open-Orders |
| Independent watchdog | 2 missed heartbeats | cancel-all via separate key/IP | design (4.4) |
| Reconciliation loop | every 5–15s + on reconnect | cancel zombies, adopt unknown fills, freeze on mismatch | https://developers.binance.com/docs/derivatives/coin-margined-futures/user-data-streams/Keepalive-User-Data-Stream; https://www.okx.com/docs-v5/trick_en/ |
| Unknown-result handling | timeout / OKX 50004 / Binance -1008 | query by clientOrderId before any retry | https://www.okx.com/help/api-faq |
| Request expiry | every place/amend | OKX `expTime`; Binance `recvWindow ≤ 5000` | https://www.okx.com/docs-v5/en/; https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md |
| Clock sync | offset > 200 ms | alert; > 1 s cancel-all | https://www.okx.com/docs-v5/en/ (50102) |
| Rate-limit budget | > 70% used | throttle quoting; cancel budget reserved | https://developers.binance.com/docs/fiat/general-info; https://bybit-exchange.github.io/docs/v5/rate-limit |
| Ref-price deviation | venue mid/index vs composite > X bps | cancel-all venue; no new perp exposure | https://llamarisk.com/research/when-pricing-breaks-usde; https://www.econstor.eu/bitstream/10419/266345/1/1822049504.pdf |
| Daily loss limit / DD delever | PnL ≤ −L_d; dd ≥ dd_max | halt / scale size by `1 − dd/dd_max` | https://hummingbot.org/client/global-configs/kill-switch/ |
| API key hygiene | always | no withdraw perm; IP whitelist; sub-account per strategy | https://www.binance.info/en/support/faq/detail/360002502072; https://www.okx.com/docs-v5/en/ |
| Venue capital cap | > 35–40% of capital on one venue | sweep excess to self-custody | https://www.theblock.co/post/188845/crypto-market-liquidity-dries-up-following-alameda-and-ftx-collapse |
| STP on every order | always | Binance `selfTradePreventionMode`; OKX `stpMode`; Bybit `smpType` | https://developers.binance.com/en/docs/products/spot/faqs/stp_faq; https://www.okx.com/help/okx-to-implement-mandatory-self-trade-prevention; https://bybit-exchange.github.io/docs/v5/smp |
| Depth-scaled sizing | depth within 10 bps < threshold | shrink size; halt pair at < 20% of 24h median | https://www.datawallet.com/crypto/october-10-crypto-crash-explained |

## Failure-mode catalog

| Failure | Example incident | Impact on MM | Mitigation |
|---|---|---|---|
| Adverse selection eats the spread | CME true-signed study: capture +0.654 bp vs adverse −0.661 bp; crisis weeks 105–112% | Net PnL ≈ 0 or negative despite "earning spread" | Markout-gated quoting, `s/2 ≥ α·μ` floor, cross-venue fair value (https://daru.finance/research/market-making) |
| Picked off by latency arbs | Binance leads; ~700 ms lag on slower venues; stale quotes hit by IOCs | Negative 1s markouts clustered after reference jumps | Quote off composite, max quote age, amend-in-place, colocate (https://arrakis.finance/blog/crypto-price-discovery; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4677989) |
| Liquidity vacuum / one-sided book | 10/10/2025: BTC top-of-book depth −90%, USDE depth $89M→$2M, 22% spreads | Fills on one side only; inventory explodes; hedge impossible | L3 cancel-all, depth-scaled sizing, pre-funded hedge venue (https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity; https://ct.com/research/exclusively-obtained-orderbook-data-reveals-details-about-usde-crash) |
| Venue-local index depeg | USDe $0.65 / WBETH −80–90% / BNSOL $0.13 on Binance only | Perp hedge marked at fictitious price; liquidation/ADL | Own composite index; deviation kill; lower perp leverage on alt collateral (https://llamarisk.com/research/when-pricing-breaks-usde) |
| ADL at irrational price | Wintermute shorts ADL'd at ~$5 vs $1 market | Unhedgeable instant loss | Cap perp inventory per alt to affordable ADL loss; prefer majors for hedges (https://en.theblockbeats.news/news/59932) |
| Cannot cancel / reduce during outage | Binance 19 May 2021 (~2h), 29 Aug 2025 futures (37 min), Oct 2025 reduceOnly rejections (reported) | Orders rest through the move; −$591k reported by one MM | Dead-man's switch, cancel budget reserve, independent watchdog, cross-venue hedge (https://www.binance.com/en/square/post/307798457395697; https://coinedition.com/binance-system-failure-reduceonly-order-outage/) |
| Withdrawals/transfers jammed | Binance transfer subsystem 21:18–21:51 UTC 10/10; MMs unable to rebalance across venues | Cannot re-quote where inventory is wrong; hedge stranded | Pre-fund both legs; no intraday-transfer dependence (https://www.banklesstimes.com/articles/2026/01/31/october-10-crypto-crash-binance-releases-post-mortem-findings/; https://en.theblockbeats.news/news/59932) |
| Stale order book after WS gap | Bybit `u==1` restart; OKX seq gap; Binance depth gap | Quoting off a book that no longer exists | Staleness + sequence checks; rebuild before quoting (https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook) |
| Silent private-stream death | Binance listenKey expires at 60 min; no replay | Missed fills → wrong inventory → wrong skew | Keepalive 30 min, reconcile on reconnect (https://developers.binance.com/docs/derivatives/coin-margined-futures/user-data-streams/Keepalive-User-Data-Stream) |
| Unknown order result | OKX 50004 at funding times; Binance -1008 | Duplicate orders on retry; doubled inventory | Query by clientOrderId first; idempotent IDs (https://www.okx.com/help/api-faq) |
| Wrong REST data | OKX 27 Mar 2024 CDN cache returned incorrect balances/positions for 2.5h | Reconciler "fixes" state to wrong values | Cross-check REST vs WS; freeze on inconsistent sources (https://www.okx.cab/en-eu/help/mar-27-2024-rest-api-service-issues) |
| Rate-limit ban mid-crash | Binance 418 (2 min–3 days); Bybit 403 (≥10 min) | Cannot cancel or hedge | ≤70% budget, reserved cancel quota, backoff, second IP/key (https://developers.binance.com/docs/fiat/general-info; https://bybit-exchange.github.io/docs/v5/rate-limit) |
| Clock skew rejects | OKX 50102 (>30s), Binance recvWindow, Bybit 10002 | All requests rejected incl. cancels | NTP, per-venue offset monitoring (https://www.okx.com/docs-v5/en/) |
| Exchange insolvency / custody loss | FTX Nov 2022 ($55–175M MM losses); Bybit $1.5B hack Feb 2025 | Capital loss; industry depth −50% for a year | Venue caps, daily sweeps, exit ladder (https://k33.com/research/archive/articles/the-ftx-collapse-more-contagion; https://www.nccgroup.com/research/in-depth-technical-analysis-of-the-bybit-hack/) |
| Stablecoin peg break while quoting mean-reversion | UST May 2022: bid depth halves, ask depth doubles | Long a collapsing asset at hard limit | One-sided-depth trigger; no mean-reversion skew on tested pegs (https://www.loyola.edu/_media/sellinger-business/documents/academics/departments/finance/wealth-management-conference/speakers/Joshi_Ravi.pdf) |
| Macro-event vol spike | FOMC hour |ret| 0.66%→1.25%, volume ×2.5; CPI +107 pts RV | Stale quotes swept; inventory built at extremes | Calendar pause/widen; resume on reversal (https://ideas.repec.org/a/eee/finlet/v101y2026ics1544612326006021.html; https://volmex.finance/papers/Macroeconomic%20Announcements%20Fuel%20Volatility%20An%20In-Depth%20Analysis.pdf) |
| TradFi-hours deleveraging | 5 Feb 2026: −6σ day, IBIT $10B, CME basis unwind | Crash outside "crypto" catalysts; weekend thin books precede | Treat US open/close and options expiries as L1; weekend limits lower (https://www.vaneck.com/us/en/blogs/digital-assets/matthew-sigel-what-triggered-bitcoins-major-selloff-in-february-2026/) |
| Inventory death spiral | Trending market fills only bids; MM widens ask and waits | Forced taker exit at the low | Hedge at hard limit; markout-gated one-sided quoting; inventory age decay (https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse) |
| Correlated alt exposure | 50+ Binance perps lost >64% OI on 10/10 | All bids fill simultaneously | Portfolio Δ_β cap and stress test (https://www.odaily.news/en/post/5206861) |
| Fee-tier drop-off | 30-day volume falls below tier | `capture − adverse − f` flips negative | Fee-at-next-tier go/no-go per pair (https://daru.finance/research/market-making) |
| Self-trade / wash-trade exposure | SEC/DOJ actions vs Gotbit, CLS Global, ZM Quant; 2026 indictments | Regulatory/criminal liability; fee burn | STP on every order; one entity per venue (https://www.sec.gov/newsroom/press-releases/2024-166; https://developers.binance.com/en/docs/products/spot/faqs/stp_faq) |
| Jurisdiction breach | Bybit/Binance.com exclude US persons; account termination + forced liquidation | Positions liquidated by venue; funds frozen | Verify entity eligibility and IP locality per venue (https://www.bybit.com/en/help-center/article/Service-Restricted-Countries) |
| Circuit-breaker flapping | Wintermute's internal breakers tripping "every minute" on 10/10 | Never quoting when spreads are widest; missed recovery | Hysteresis; L2 resume posture (https://en.theblockbeats.news/news/59932) |

---

## Open items / caveats

- Bybit DCP requires institutional onboarding; until then Bybit has no server-side cancel-on-disconnect for your account → the independent watchdog is mandatory there.
- Binance Spot: no account-level dead-man's switch found in the spot REST docs reviewed this pass; confirm with Binance API support (there may be a VIP/FIX feature).
- Token-unlock impact on MM PnL: no rigorous quantitative source found in this pass; treat with judgment-based L1 posture.
- All thresholds given as "e.g." are starting points to be calibrated from your own markout and depth data, not published constants.
