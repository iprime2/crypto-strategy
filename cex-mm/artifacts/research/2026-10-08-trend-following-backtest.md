# Quant memo: trend following on Delta India perps (backtest)
**Date:** 2026-10-08 · **Venue:** Delta India mainnet public data (no orders), Binance USDT-M perp archive as the longer proxy · **Symbols:** BTC, ETH, XRP, BNB, ADA, LTC, LINK, DOGE, BCH · **Data:** daily closes and funding, Binance 2020-01 to 2026-09, Delta 2023-12 to 2026-09. `scripts/trend_backtest.py`

## Question
Does a standard trend-following rule, fixed before testing, make money after Delta costs, and can it run on a small account?

## Rule (fixed before any test, no parameter search)
- Universe: the 9 large coins that had perps in January 2020 and are all listed on Delta India, so the test does not pick coins known to have risen later.
- Signal: mean of sign(20, 60, 120-day return). Long-only uses max(signal, 0).
- Size: (40% / N) / 60-day realized vol per coin, gross exposure capped at 2x. Set at the day's close, held over the next day.
- Costs: taker 5.31 bps plus 2 bps slippage on traded notional; funding paid on longs and received on shorts (Binance archive, Delta `FUNDING:<sym>`).
- Basis: time-series momentum (Moskowitz, Ooi and Pedersen 2012, https://doi.org/10.1016/j.jfineco.2011.11.003); in crypto, Liu and Tsyvinski (https://www.nber.org/system/files/working_papers/w24877/w24877.pdf).

## Results

Binance data, 2020-05 to 2026-09:

| | CAGR | Vol | Sharpe | Max drawdown | Fees/yr | Funding/yr | Avg gross |
|---|---|---|---|---|---|---|---|
| **Trend, long-only** | **+24.2%** | 19% | **1.25** | **−21.9%** | 1.1% | 3.4% | 0.20x |
| Trend, long/short | +17.5% | 24% | 0.78 | −36.6% | 2.3% | 3.1% | 0.39x |
| Buy and hold, equal weight | +61.5% | 75% | 1.01 | −80.2% | | | 1.00x |

Long-only by year: 2020 +53%, 2021 +47%, 2022 −5%, 2023 +16%, 2024 +47%, 2025 +3%, 2026 (to Sep) +8%.

Same window on both sources, 2024-08-10 to 2026-09-30 (Delta's coins listed April 2024, plus 120 days of history):

| Long-only | CAGR | Sharpe | Max drawdown |
|---|---|---|---|
| Binance prices | +19.7% | 1.17 | −14.0% |
| **Delta prices and funding** | **+19.4%** | **1.15** | **−14.1%** |
| Buy and hold (Delta) | +18.3% | 0.58 | −66.3% |

Daily strategy returns on the two sources correlate at 0.999 over 782 days, so the Binance archive is a valid stand-in for Delta before 2024.

## Robustness
- **All 18 settings are reported** (`--grid`: lookbacks 10/30/60, 20/60/120, 50/100/200, 20, 60, 120 × target vol 25/40/60%). Every one is positive. Sharpe ranges 0.99 to 1.25 on Binance 2020 to 2026 and 0.48 to 1.02 on Delta 2024 to 2026.
- **Target vol does not change the Sharpe ratio.** It scales return and drawdown together: on Binance 2020 to 2026, 25% gives +15% a year with a −14% drawdown, 40% gives +24% with −22%, and 60% gives +36.5% with −32%.
- **The 60-day lookback alone scored best on Delta**, but choosing it after seeing the results would be selection bias. The fixed rule stays.
- **Recent years are weak:** 2025 +3%, 2026 to September +8%. The literature also reports crypto momentum as sample-dependent (https://www.journals.vu.lt/BATP/en/article/view/44540).
- **Shorts hurt:** long/short lost 7% in 2023 and has a lower Sharpe over the full period. Long-only it is.

## Small accounts
Delta contract values: BTC 0.001 (~$83), BNB 0.1 (~$76), ETH 0.01 (~$25), LTC 0.1, LINK 1, DOGE 100, BCH 0.01, XRP 1, ADA 1. Positions rounded to whole contracts (Delta prices, 2024-08 to 2026-09):

| Capital | CAGR | Sharpe | Max drawdown | Avg gross |
|---|---|---|---|---|
| $280 (~₹25k) | +17.5% | 1.11 | −15.6% | 0.14x |
| $1,000 (~₹90k) | +18.2% | 1.08 | −15.2% | 0.19x |
| $2,300 | +19.3% | 1.15 | −14.3% | 0.19x |
| $5,000 | +19.5% | 1.15 | −13.7% | 0.19x |

At $280, the BTC and BNB positions round to zero on most days. From about $1,000, rounding costs under 1.5% a year. Margin is not a constraint: average gross exposure is 0.19x of equity.

## Not modelled
- Slippage above 2 bps on thin Delta alts (BCH ~$1M/day, ADA ~$1.4M/day turnover). Small at these sizes.
- Missed rebalances (exchange or bot outages).
- Tax: whether INR-settled crypto futures fall under the 30% VDA rule or count as business income is unresolved (https://www.caindelhiindia.com/blog/crypto-futures-taxation/).

## Next experiment
Paper-trade the fixed rule for 4 weeks on Delta mainnet public data (`scripts/trend_paper.py`, dashboard `/trend`, started 2026-10-08 on the Tokyo VM with $1,000 paper equity at the default 40% target vol): one rebalance a day after the 00:00 UTC close, whole contracts, taker fills walked through the live L2 book, Delta funding. Mainnet data rather than Delta demo, because demo prices do not track mainnet and demo fills do not validate economics; order plumbing gets its own check before any live start.
- **Metric:** paper equity tracks the model equity (backtest arithmetic on the same days); measured slippage and fees per rebalance.
- **Success:** every rebalance executes, and costs stay within 2x of the 7.31 bps modelled.
- **Stop:** missed or partial rebalances on two days, or costs above 2x the model.

**Before going live, the user decides the target vol (risk level).**
