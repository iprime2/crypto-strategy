# Selling daily option premium on Delta Exchange India — backtest

**Date:** 2026-09-29 · **Verdict:** no edge. Do not trade this as specified.

## Setup
- Data: Delta India public API. 148,179 expired BTC/ETH options (Dec 2023 → Sep 2026), MARK price candles per contract, index candles `.DEXBTUSD` / `.DEETHUSD`.
- Trade: 24 h before the 12:00 UTC daily expiry, sell at MARK minus a spread cost (0 / 5 / 10 % of premium), hold to settlement. Settlement = 30-minute TWAP of Delta's index, as Delta settles.
- Costs: 0.010% of notional capped at 3.5% of premium, +18% GST, per opened leg; ITM legs pay again at settlement.
- Structures: ATM straddle; strangles 1–4% OTM; iron condors; single 2–3% OTM puts/calls. PnL in bps of underlying notional per day.

## Results
- In-sample (12 months to 2026-09-29, 366 expiries each): ATM straddle implied move 148 bps vs realised 163 (BTC), 192 vs 227 (ETH). Implied was below realised in every quarter. At a 5% spread cost every structure is negative except BTC 3% puts (+0.6 bps/day, t 0.2). Win rates 80–94% with single-day losses up to −947 (BTC) and −1,820 bps (ETH).
- Buying the ATM straddle at mark +5% also loses (−7 BTC, −14 ETH bps/day): prices are roughly fair and costs kill both sides.
- A filter found in-sample (sell only when implied move > 1.5× trailing 7-day realised) looked positive (+22 bps/day, ~25 days each), but it was chosen after 18 tries. Out-of-sample (Jan 2024 → Sep 2025, ~600 expiries each) it gave +7.8 (BTC, t 0.6) and −4.2 bps (ETH): not an edge.
- Out-of-sample unconditional: BTC ≈ 0; ETH strangle −16.1 bps/day (t −2.0).

## Not tested (possible next steps)
Weekly/monthly expiries (where the volatility risk premium is usually documented), delta-hedged short straddles, entries closer to expiry, using real order-book bids instead of MARK.

Update 2026-10-24: weekly expiries were tested. Selling the BTC and ETH ATM straddle 168 h before the Friday expiry at MARK × 0.95 lost −26.3 bps per week over 145 weeks (t −0.63); see `cex-mm/artifacts/research/2026-10-24-quant-trading-repo-review.md` (screen OPT-W1).

Files: `fetch_products.py` (contract list), `backtest.py` (12-month grid), `oos.py` (pre-registered out-of-sample rule), `results-*.txt`.
