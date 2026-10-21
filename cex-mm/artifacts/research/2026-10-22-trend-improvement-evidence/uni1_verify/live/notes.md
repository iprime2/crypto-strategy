# UNI-1 verification, lens: live feasibility on Delta India (2026-10-21)

Scope: whether UNI-1 (the yearly liquidity-ranked universe, N 9) can be traded on Delta India at $1,000 / $2,500 / $5,000.
I read the study's files and changed none of them. Delta data is public and read-only (no keys, no orders), fetched
2026-10-21 about 22:30 UTC into `dl/`. Scripts and their stdout are in this folder:
`uni1_live.py`, `uni1_delta.py`, `uni1_attrib.py`, `uni1_contracts.py`, `uni1_funding_corr.py`, `uni1_fundbook.py`, `uni1_now.py`;
outputs in `*_out.txt` and `*_out.json`.
All selection code is the implementation's own (`variants_universe._membership` / `_select`). Prices are Delta marks from
2026-10-21. vol60 is the rule's close-to-close 60-day vol on the Binance panel at 2026-09-30.

Verdict from this lens: the research number is **not refuted**. The plan already limits live use to >= $5,000, and that
limit holds up. Live use still has five problems:
- $1,000 and $2,500 are infeasible.
- $5,000 works for the 2026 universe, but the 2027 entrant (ZEC) fails the gate at $5,000.
- The implementation's whole-contract and gate code uses the wrong contract values for exactly the new names.
- 1000PEPE trades under $0.5M a day on Delta.
- Delta funding is about twice Binance's, which would break the A4 funding-fidelity check unless the reference line uses
  Delta funding.

## 1. UNI-1 universes (both cadences give the same members; weekly reset dates in brackets)

| reset | members (rank) | in / out |
|---|---|---|
| 2020-04-30 | BTC(1) ETH(2) LINK(3) BCH(4) XTZ(5) LTC(6) BNB(7) EOS(8) XRP(9) | start |
| 2021-01-01 [01-03] | the same nine; age floor not yet binding | none |
| 2022-01-01 [01-02] | BTC ETH MATIC SOL XRP BNB LINK LTC EOS(18) | +MATIC +SOL / -BCH -XTZ |
| 2023-01-01 | BTC ETH DOGE XRP BNB LTC MATIC LINK SOL | +DOGE / -EOS |
| 2024-01-01 [01-07] | BTC ETH SOL AVAX XRP DOGE MATIC LINK BNB | +AVAX / -LTC |
| 2025-01-01 [01-05] | BTC ETH XRP SOL DOGE 1000PEPE BNB LINK AVAX(12) | +1000PEPE / -MATIC |
| 2026-01-01 [01-04] | BTC(1) ETH(2) SOL(3) XRP(5) DOGE(6) BNB(7) 1000PEPE(9) AVAX(11) LINK(13) | none |

- **2027 proxy**, using the 30-day window to 2026-09-30 with the 2026 members as incumbents and age >= 365:
  BTC ETH ZEC SOL XRP DOGE BNB 1000PEPE LINK. ZEC (rank 3) comes in. AVAX (rank 25 > 18) goes out. LINK is exactly at
  rank 18, the edge of the incumbent buffer.
- **The proxy is unstable.** I ran the same selection on 30-day windows ending 06-30, 07-31, 08-31, 09-15 and 09-30.
  - The entrant is ZEC in 3 of the 5 and HYPE (age 489) in 2 of the 5.
  - AVAX is dropped in 4 of the 5, and LINK in 1 (06-30, rank 19).
  - The next ranks are NEAR 8, UNI 9 and SUI 11.
- Overlap with the live nine (BTC ETH XRP BNB ADA LTC LINK DOGE BCH): 6 of 9 in both 2026 and 2027.
  - 2026 adds SOL, AVAX and 1000PEPE in place of ADA, LTC and BCH.
  - 2027 adds ZEC, SOL and 1000PEPE.

## 2. Delta India listing

Every 2026 and 2027-proxy member is a live, operational USD perp on Delta. Taker fee 0.05% and maker 0.02% before GST.

| coin | Delta cv | 1 contract $ | 24 h turnover $M (file 10-20 / now) | 30-day median $M (min) | spread bp | launch |
|---|---|---|---|---|---|---|
| BTC | 0.001 | 84.59 | 1073.1 / 1035.4 | 1122.5 (317.3) | 0.1 | 2023-12-18 |
| ETH | 0.01 | 24.89 | 717.1 / 690.9 | 731.9 (183.6) | 0.2 | 2024-02-05 |
| SOL | 1 | 107.71 | 150.8 / 152.3 | 179.2 (69.6) | 1.0 | 2024-04-08 |
| XRP | 1 | 1.38 | 12.1 / 14.5 | 16.2 (5.9) | 1.5 | 2024-04-10 |
| DOGE | 100 | 8.25 | 3.67 / 4.51 | 7.76 (3.01) | 1.2 | 2024-04-08 |
| BNB | 0.1 | 75.02 | 2.26 / 2.47 | 2.50 (1.35) | 0.3 | 2024-04-10 |
| 1000PEPE | 1000 | 4.69 | **0.44 / 0.17** | **0.13 (0.02)** | **10.7** | **2025-12-29** |
| AVAX | 1 | 9.75 | 2.33 / 2.41 | 4.55 (1.84) | 4.1 | 2024-04-08 |
| LINK | 1 | 12.60 | 1.58 / 1.37 | 2.98 (1.27) | 1.6 | 2024-04-10 |
| ZEC (2027) | 0.1 | 134.87 | 16.06 / 14.59 | 12.36 (3.55) | 0.4 | 2025-10-06 |
| HYPE (alt 2027) | 0.1 | 8.16 | 0.59 | 0.71 (0.31) | 0.2 | 2025-06-04 |

- **History.** Delta India launched most of these perps in 2023-12 to 2024-04, so the 2020-23 universes cannot be checked
  on Delta. 1000PEPE was in the 2025 universe but only reached Delta on 2025-12-29. MATIC is not on Delta; POL has been
  listed since 2024-10-08. XTZ and EOS are not listed.
- **Restricting 2024-05-01..2026-09-30 to Delta-listed members barely changes the result.** The restriction mostly drops
  1000PEPE in 2025.

| book | unrestricted Sharpe | MATIC tradeable | MATIC not tradeable |
|---|---|---|---|
| daily | 1.036 | 1.065 | 1.050 |
| weekly | 0.887 | 0.894 | 0.869 |

## 3. Contracts at full signal: E x (TV/9)/max(vol60, 0.05) / (cv x mark). Gate: >= 2 contracts

**2026 universe**

| | $1,000 | $2,500 | $5,000 |
|---|---|---|---|
| TV 0.25 | BTC 0.79, ETH 1.97, SOL 0.42, BNB 0.97 below 2 | BTC 1.99, SOL 1.04 | all >= 2 (SOL 2.05, the thinnest) |
| TV 0.40 | BTC 1.27, SOL 0.66, BNB 1.56 | SOL 1.66 | all >= 2 (SOL 3.3) |

The plan exempts the live nine from the gate, so only SOL counts at $1,000 and $2,500. On the weekly book at $1,000, SOL
rounds to 0 contracts.

**2027 proxy**

| | $1,000 | $2,500 | $5,000 |
|---|---|---|---|
| TV 0.25 | ZEC 0.16, SOL 0.42 (plus BTC, ETH, BNB) | ZEC 0.40, SOL 1.04 | **ZEC 0.80 fails** |
| TV 0.40 | ZEC 0.26, SOL 0.66 (plus BTC, BNB) | ZEC 0.64, SOL 1.66 | **ZEC 1.28 fails** |

**Equity needed for every member to reach 2 contracts**

| universe | TV 0.40 | TV 0.25 |
|---|---|---|
| 2026 (SOL sets it) | $3,051 | $4,882 (2.4% headroom at $5,000) |
| 2027 proxy (ZEC sets it) | $8,316 | $13,306 |

- At $5,000, ZEC passes only if its vol60 falls to 0.82 or below (daily) or 0.515 or below (weekly). It is 1.37 now.
- HYPE, the alternative 2027 entrant, needs only $234 / $375, so it is feasible at any capital.

**Whole-contract lines from the implementation (`uni1_contracts.py`)**

- **Defect.** `variants_universe` rounds whole contracts with `data.CVALS`, which holds only the nine coins. Every other
  coin gets $25 divided by its first close. Against Delta's real contract values that makes:

  | coin | implementation contract | Delta contract | ratio |
  |---|---|---|---|
  | SOL | 7.65 SOL ($813) | 1 SOL ($108) | 7.65 |
  | AVAX | | | 7.1 |
  | 1000PEPE | | | 6.7 |
  | ZEC | | | 3.5 |

  So the implementation's gate drops SOL in every year at every capital up to $5,000. It keeps ADA or SUI in SOL's place.
- **Delta's real contract values with compounding equity**, against the static 24 rounded the same way:

  | book | Sharpe | static 24 | SOL gated out in |
  |---|---|---|---|
  | daily $5,000 | 1.050 | 0.846 | never; no gate binds |
  | weekly $5,000 | 0.936 | 0.838 | 2022, 2024, 2025 |
  | daily $1,000 | 1.094 | 0.908 | most years; different members |

  The whole-contract equity compounds, to $14.2k (daily) and $9.7k (weekly) by 2026. A live book starting at $5,000
  faces the gate at $5,000.
- None of this changes the unrounded headline, which has no contract constraint and no gate. It does matter for Phase 3.
  A4 compares a third book with its own "$1,000 whole-contract backtest line". That line would be computed with the wrong
  contract values, and at $1,000 it is not the tested universe.

## 4. Liquidity

Full-signal position at $5,000, TV 0.40, by coin: BTC $526, ETH $385, SOL $353, XRP $284, DOGE $304, BNB $575,
1000PEPE $202, AVAX $258, LINK $288, ZEC $162.

- Every position is at most 0.05% of the coin's Delta 24 h turnover, so market impact is negligible.
- **1000PEPE is below $0.5M a day on Delta.** Its 30-day median is $0.13M, the worst day $0.02M, 24 h now $0.17M, and
  open interest $0.08M. That is a live risk: liquidity can vanish and Delta may delist it.
  - The L1 ask is $139, less than one full $5k position.
  - Taking the full position costs 5.3 bp over mid against the backtest's 2.0 bp slippage. In equity terms that is about
    +0.03% a year: roughly 6% of book turnover at 15x a year, times 3.3 bp.
- HYPE, if it enters in 2027, is borderline: 30-day median $0.71M, minimum $0.31M.
- Walk cost for the other names at full size: AVAX 2.0 bp, DOGE 1.8, LINK 0.8, XRP 0.7, SOL 0.5, and ETH, BNB, BTC, ZEC
  0.0-0.2.

## 5. Funding and distinguishability (affects all books, not only UNI-1)

Delta funding paid by longs, 2026-07-01..09-30, annualized, against Binance:

| coin | Delta | Binance |
|---|---|---|
| DOGE | +38.3% | +6.6% |
| ZEC | +21.6% | +5.9% |
| 1000PEPE | +17.5% | +6.1% |
| AVAX | +13.3% | +4.5% |
| SOL | +11.1% | +3.4% |
| LINK | +5.7% | +6.6% |
| HYPE | +5.0% | +6.6% |

- **Book level:** UNI-1 daily pays 3.09% a year on Delta rates against 1.54% on Binance rates (ratio 2.00). The nine
  show the same ratio, 2.01.
- A4(b) requires funding a year within 20% of the backtest line. It will fail unless the reference line uses Delta
  funding.
- **UNI-1 against the live nine, 2024-05..2026-09:**

  | book | correlation | tracking error a year | Sharpe gain vs nine | P |
  |---|---|---|---|---|
  | daily | 0.960 | 4.4% | +0.04 | 0.42 |
  | weekly | 0.963 | 2.6% | +0.14 | 0.14 |

  Over the 8-week A4 window the tracking error is 1.7% and the t-stat about 0 (daily), so a paper run cannot tell the
  books apart. That is consistent with A4 being a fidelity check only.
- Over the full 2020-26 window UNI-1 trails the hindsight nine: -0.20 Sharpe daily (P 0.96) and -0.14 weekly.
- Of UNI-1's total daily P&L (+1.309), the names outside the static 24 add +0.271: SOL +0.128, DOGE +0.109, AVAX +0.035,
  MATIC +0.010 and 1000PEPE -0.012.

## 6. Operations and a live spec

**Data for the yearly reset**

- **Turnover.** Binance USDT-M daily klines (quote_volume) from data.binance.vision, daily files
  `data/futures/um/daily/klines/<SYM>/1d/`, for every symbol in the S3 index. That is about 700 symbols x 30 files.
  - The ranking can be cut to symbols with a recent month's median above roughly $50M.
  - The age floor (365 closes with quote volume above 0) comes from the monthly kline files.
  - The Jan 1 daily file is published hours after 00:00 UTC. Run the reset at the first hourly timer run where all 30
    files exist, or fall back to fapi klines from the Tokyo VM.
- **Do not rank on Delta's own turnover.** Delta's 30-day median top-9 among perps at least 365 days old is BTC ETH SOL
  XRP UNI ZEC AAVE DOGE AVAX. That is a different, untested rule, and Delta's 24 h ranking is dominated by promotions and
  new listings (BR, ARIA, AKE, GTC). Use Delta turnover only as a liquidity flag.
- **Contract values and state** come from Delta `/v2/products`: `contract_value`, `state`, `trading_status` and
  `product_specs.only_reduce_only_orders_allowed`. A selected coin with no live USD perp counts as gated out and is not
  replaced.
- **Signal and vol** come from Delta daily closes, as the current books do (160 days). The 2027 candidates have enough
  history: ZEC since 2025-10, 1000PEPE since 2025-12, HYPE since 2025-06.

**Spec for a third paper book (feasible only at $5,000 or more; at $1,000 and $2,500 it is not the tested universe)**

- `trend_paper.py` plus a universe file:
  - state dir `artifacts/trend/paper-uni1`
  - daily cadence (00:05 UTC), TV 0.40, cap 2x, band 0
  - paper equity $5,000
  - N_t = members with 121 Delta closes
  - taker fills walked through the L2 book, as in the existing books
- Members until the reset: BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK. SOL has the fewest contracts at full signal (3.3).
- Reset at the close of the 2027-01-01 candle:
  - top 9 by 30-day median quote volume; entrants need 365 closes; incumbents stay while rank <= 18
  - exclude the I-U1.5 lists
  - gate with paper equity E: E x (0.40/N_pre)/max(vol60, 0.05) >= 2 x Delta cv x Delta close, live nine exempt
  - Expected outcome today: ZEC is selected and fails the gate (1.28 contracts), so the book runs 8 names.
- Log, but do not act on, a liquidity flag for coins under a $0.5M 30-day median on Delta (1000PEPE today).
- The A4 reference line must be the $5,000 whole-contract line rebuilt with Delta's real contract values, and with Delta
  funding (or a stated Binance-to-Delta funding adjustment). The plan's $1,000 line is inconsistent with "live only at
  >= $5,000".
- A weekly UNI-1 book at $5,000 is marginal: SOL has 2.05 contracts against a floor of 2, and ZEC fails at 0.80. I do not
  recommend it below about $13.3k, the equity at which ZEC clears the gate.
