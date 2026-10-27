# Quant memo: bitra is a well-guarded LLM trading-agent framework with no published edge; nothing in it to run on Delta, and three ideas worth borrowing
**Date:** 2026-10-27 · **Subject:** https://github.com/BijectiveLabs/bitra (MIT, PyPI `bitra`, CLI `tra`, v0.10.2, alpha). Cloned read-only at `1e2d798` (2026-10-24) to `/home/user/bijectivelabs/bitra` in the session sandbox. About 42k lines of Python in `src/` and 24k in `tests/`. Never installed or executed. · **Venue:** none touched. No orders, keys or bot actions. · **Data:** none. This is a code and docs review.

## Question
The user asked what is interesting about this repo and how we could use it for trading. "We" means the post-only ADA market maker on Delta India mainnet, which is the only engine here that pays (about $5.65/day on $292, `2026-10-26-trend-strategy-review.md` finding 9), and the two trend paper books on nine Delta perps.

## What it is
- **An LLM trading-agent desk with no model in the order path.** Each cycle:
  - code pulls data and computes every figure;
  - four "analyst" models (technical, macro, on-chain, sentiment) read only those figures, answer in a closed schema and cite figures by name and value, and code checks every citation;
  - a technical analyst on 15-minute bars proposes a direction, a setup, a stop and a target;
  - code then prices the round trip (fee, spread, book-walk impact, funding, latency slippage), holds the stop and target inside operator bounds, runs pro and contra validators plus a neutral judge, scores conviction, sizes the trade from a risk-per-trade rule, and either records the intent (sandbox) or sends one order with the stop and take profit attached (venue mode, behind a signed mandate).
  - A risk-manager model can only cut size, pause or halt. Two auditor models only report.
- **Venues through ccxt.** Run end to end on the demo or testnet APIs of Bybit, OKX, Bitget, BingX, Binance and Gate. Real capital "has not been run by us" (README).
- **A research toolkit underneath, older than the agents.** It is called the "falsification chain" (`chain/`, `docs/opensource/chain.md`):
  - cost floor;
  - observation count;
  - a nine-element pre-registration, sealed by SHA-256;
  - data requirements;
  - validation: block bootstrap on the collapsed portfolio series, a sign-flip or cross-sectional null that pays the same costs, three subperiods, declared power, Benjamini–Hochberg, and rebalance-phase ("anchor") robustness;
  - shadow, then canary.
  - A kill ledger records each idea that died and why. A promotion ladder (research, paper, shadow, canary, production) needs evidence to step up and steps down without it.
- **No results.** The 0.9/0.10 changelog took every trade result out of the source and docs: "Results will be published when there is a sample large enough to audit." The README says the example strategies are "there to show the path, not to make money."

## Can we trade with it? No, for three independent reasons
| Reason | Evidence |
|---|---|
| **It cannot reach Delta India safely.** ccxt's `delta` adapter targets `api.delta.exchange` (global), not `api.india.delta.exchange`. Its `stopLossPrice` and `takeProfitPrice` are marked `# todo` (False). It does not list `createOrderWithTakeProfitAndStopLoss`, `createStopLossOrder` or `createTakeProfitOrder`. Under bitra's capability check (`data/sources/capability.py`) that is "venue mode only with exits = none": you carry the stops yourself. That is the one protection the whole design rests on. | ccxt `python/ccxt/delta.py` on master, read 2026-10-27 |
| **The strategy it runs is a class we have already rejected.** By default it is an LLM calling direction on 15-minute bars and trading as a taker in and out. At Delta's 5.31 bps taker fee plus spread, every trade must beat about 11 bps. resource/07's rejected table covers each of its inputs: ML and signal stacking (52.9–54.1 % daily accuracy, which fails at 10 bps), sentiment and news NLP, on-chain, events, intraday seasonality, and the Binance lead (a pick-off risk, not a taker edge). Its "edge ≥ 2× cost" gate does not measure edge. The "claimed edge" is the distance to the analyst's own take profit, or a declared `magnitude_bps` (default 20) (`agents/cycle.py` `_claimed_edge`). The gate checks a reward-to-cost ratio. Whether the break-even win rate is ever reached is measured only afterwards, by `tra hindsight`. | `resource/07-trend-rule-and-prop-trading-research.md` rejected table; bitra `execution/targets.py` |
| **There is no evidence of edge, from them or anyone.** No published P&L. The only outside evidence their docs cite is Alpha Arena Season 1 (Oct–Nov 2025), where 4 of 6 frontier models lost 42–59 % of $10,000 on Hyperliquid perps. LLM calls also cost tokens on every cycle that is not held by the trigger. | `docs/opensource/why.md` and its sources |

Running it in sandbox on Bybit data would cost tokens and weeks of calendar. It would test an idea whose whole class already failed here. I would not run it.

## What we already do, which bitra confirms
Nothing in this table is new to us. Each row is an independent team reaching the same rule we use, so it is a check on our practice and not a change to make.

| bitra | Ours |
|---|---|
| Funding over a holding period: settlements strictly after entry and at or before exit. A missing rate is refused, never booked as zero (`execution/cost.py` `FundingSchedule`, `funding_accrual_bps`) | The same half-open interval and the same "an empty answer is not zero" rule, in the `trend_paper.py` fix deployed 27 Oct (`2026-10-26-trend-strategy-review.md`) |
| Markout signed by side and set beside the half-spread (`execution/markout.py`) | `markout_report.py` goes further and splits capture from markout against the Binance 1 s fair |
| Passive fill as two bounds: "at or through" (upper) and "strictly through" (lower) (`execution/fill.py` `FillMode`) | Shadow simulator: a strict through-the-price rule plus `--rule touch` |
| Pre-registration sealed by hash, an amendment can only tighten, holdouts opened once | `PREREG.md` with md5 and sha256 in every evidence pack, holdouts run once (for example `2026-10-25-inventory-lean-replay.md`) |
| Block bootstrap, a costed null, BH, and rebalance-phase robustness | `2026-10-22-trend-improvement` engine. TIME-1 and TIME-3 were exactly a phase-robustness test |
| Kill ledger | resource/07 "considered and rejected" table |
| Ladder and canary caps | `docs/MAINNET_GATE.md`, live stage 1 then 2 |
| Leverage read back from the venue; refuse a stale book; kill switch | `MM_MAX_LEVERAGE` refusal on mainnet start; `BookWatch` and `FrozenBookWatch`; cancel-all and the Delta dead man's switch |

## What is worth borrowing, ranked by money at stake
| # | Idea | Where in bitra | Why it matters to us | Money at stake |
|---|---|---|---|---|
| 1 | **The effective-cost formula for maker-first rebalancing.** `c_eff = p_fill · c_passive + (1 − p_fill) · (c_cross + drift_unfilled)`, measured on recorded prints at a fixed wait budget, reported under both fill bounds. Two of their findings come with it: unfilled orders are the ones the market moved away from, and a longer wait budget makes the cost worse. | `execution/fill.py` `effective_cost`, `passive_fill` | This makes our untested **COST-4** (post-only with taker fallback for the trend books, `resource/08` line 102) testable on recorded Delta prints rather than candles. resource/08 parked it as "not testable on candles". | Upper bound: the daily book trades about 34× equity a year at 6.33 bps all-in. A full maker fill at 2.12 bps would save ≤ 34 × 4.2 bps ≈ **1.4 %/yr of equity**, about 14 % of the ≈ 10 %/yr expected gross. That is ≤ $14/yr at $1k and ≤ $360/yr at $25k. The true figure is lower after non-fills and drift. |
| 2 | **A data audit before any replay verdict.** One bounded-memory pass that fails a dataset on duplicates, out-of-order rows, sequence resets, mismatches, or an empty result. It warns on gaps above a threshold, price or quantity scale changes, and one day carrying a large share of rows. | `data/audit.py` | Every market-maker replay verdict (lean, imbalance pull, basis) rests on the shadow recorder's tapes, and UNI-1 already needed gap-patched data. The engine that pays should not rest on an unaudited tape. | Indirect: it protects the decisions on the $160–170/month market maker |
| 3 | **"The model's side against its reverse, resampled by whole days."** This is the default test for any discretionary or AI signal. Replay each call with its own stop, target and hold, then replay the opposite side on the same path. Report the difference net of cost, bootstrapped by day, with a minimum of 10 decisions and 5 days. | `execution/hindsight.py` `side_check` | It is the cheapest way to answer the next "is this Instagram or LLM strategy any good" question without building it. | None directly. It saves research time |

Smaller items, not worth a change on their own:
- **A clock-skew guard.** bitra refuses to sign when the local clock is more than 1 s off the venue's.
  - We know WSL runs about 1 s behind Delta. `mm-delta` handles this for data ages (it uses `received_at`), but nothing checks the offset before signing.
  - [UNVERIFIED] Delta's signature validity window; it has not bitten us.
- **Fee read-back.** bitra found a library reporting a charged fee as a rebate. Our fee figures come from the venue ledger, and the 2.12 bps tier is still [SYNTHETIC] in resource/08 until COST-5 confirms it from fills.

## What the code actually does (spot checks)
- `execution/cost.py` keeps the four terms of the round trip separate: 2 × fee, spread, slippage and funding. It raises on a missing term instead of using zero. `pair_leg_fee_bps` charges a hedged pair `fee × (1 + β)` per touch, which is correct and often missed.
- `execution/markout.py` measures fill price to mid at t + h. So it mixes capture and adverse selection, which our split keeps apart. On their control instrument the 60 s adverse move was "about four times the spread captured" (docstring; no data shipped).
- `chain/validation.py` sums trades into one portfolio return per timestamp before bootstrapping, so correlated legs count once. Its sign-flip null keeps costs, so the null centres near minus the cost.
- `execution/kelly.py` and `execution/montecarlo.py` use the desk's own record only to lower a declared risk per trade, never to raise it.

## Next experiment (one knob, metric, success, stop)
Only if the trend books are ever meant for more than $5k; at $1k the ceiling is $14 a year.
- **Knob:** execution of trend rebalances. Taker at 00:05 UTC (current) against a post-only quote at the touch for B seconds, then crossing. B ∈ {60, 300} is fixed in advance.
- **Data:** the existing shadow recorder (`trades` and `ob_l1`, public, no keys) on the nine trend perps. It needs at least 300 simulated orders per side. Recording all day gives the power, and the 00:05 window is reported separately. No orders are placed.
- **Metric:** `c_eff` in bps per dollar traded, under both fill bounds. It is compared with the measured taker cost (5.31 bps fee + walked-book slippage).
- **Success:** `c_eff` under the strict-through bound is at least 1.5 bps below the taker cost on at least 7 of the 9 coins.
- **Stop:** if the at-or-through (optimistic) bound does not clear 1.5 bps, COST-4 joins the rejected table.
- Any live use needs a new order path and the owner's go-ahead (CLAUDE.md hard rules).

## Limits
- This is a review of code and documentation as published at `1e2d798`. Nothing was run, so the behaviours above are as read, not as observed.
- bitra's claims about its own runs (demo end-to-end on six venues, "832 answers" checked for made-up rules, validator voting patterns) are theirs and [UNVERIFIED].
- The ccxt Delta capability read is from ccxt master on 2026-10-27. A later ccxt release, or a custom subclass pointed at the India host, could change the venue verdict. It would not change the strategy verdict.
- The COST-4 money figure is an upper bound from the daily book's 19-day turnover in a one-third-signal regime (`2026-10-26-trend-strategy-review.md` finding 7). Turnover in other regimes differs.
