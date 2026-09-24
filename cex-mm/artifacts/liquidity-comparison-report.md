# Liquidity comparison: Bybit mainnet vs Delta India mainnet vs Delta India demo

**Snapshot:** 2026-09-22 ~13:40 UTC (single point-in-time; public REST only)  
**Raw data:** `artifacts/liquidity-snapshot.json`

## Scope

| Venue | API base | Symbols |
|--------|-----------|---------|
| **Bybit mainnet** | `api.bybit.com` | USDT linear perps (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`) |
| **Delta Exchange India mainnet** | `api.india.delta.exchange` | INR/USD-style perps (`BTCUSD`, `ETHUSD`, `SOLUSD`) |
| **Delta Exchange India demo (testnet)** | `cdn-ind.testnet.deltaex.org` | Same symbols as mainnet demo |

Comparable notionals: Delta size is contracts × `contract_value` (BTC/ETH/SOL base per contract).

## Methodology

- **Spread:** `(best_ask − best_bid) / mid` in basis points (bps).
- **Depth:** Sum of **USD notional** (`price × base_qty`) on bid and ask sides with prices within **±N bps** of mid (N = 1, 5, 10, 25, 50).
- **24h activity:** Bybit `turnover24h` (USD); Delta `turnover_usd` from tickers.
- **Caveat — Bybit:** Order book endpoint returns **at most 50 levels** per side. Reported depth within 10–50 bps can **plateau** once all 50 levels are inside the band (especially BTC/ETH). True depth is often **≥** the Bybit numbers here.
- **Caveat — Delta:** Full L2 can list **thousands** of levels. Large displayed depth may include **resting test/MM walls**; **turnover** and **spread** are better “real liquidity” signals than raw stacked size alone.
- **Caveat — Demo:** Testnet books and turnover are **not** representative of live markets (simulated flow, key/API testing).

## Executive summary

1. **Tightest spreads & highest real activity:** **Bybit mainnet** on BTC/ETH (sub‑0.04 bps ETH/BTC); SOL ~0.85 bps.
2. **Delta India mainnet:** **~5× wider** BTC spread than Bybit, **~10×** on ETH; **~4×** on SOL vs Bybit. **24h turnover** is **~5–18%** of Bybit on majors (still meaningful for smaller MM).
3. **Delta India demo:** **Do not** use for liquidity sizing. BTC book can **look** deep, but **24h turnover** is **~3–4%** of Delta mainnet and **~0.4%** of Bybit BTC. ETH/SOL demo depth within 10 bps is **far below** Bybit and often below Delta mainnet.

**For your MM bot:** Demo is for **API/regression**; **mainnet Delta** or **Bybit** for economic liquidity. Quote widths on demo (~24 bps in your bot) are sensible given demo spread noise; on Bybit you would compete at much tighter levels.

## Spread at touch (bps)

| Asset | Bybit mainnet | Delta India mainnet | Delta India demo |
|-------|---------------|---------------------|------------------|
| BTC | **0.012** | 0.058 | 0.467 |
| ETH | **0.036** | 0.365 | 0.182 |
| SOL | **0.855** | 3.503 | 1.933 |

## Depth within ±10 bps (USD millions)

| Asset | Bybit mainnet | Delta India mainnet | Delta India demo |
|-------|---------------|---------------------|------------------|
| BTC | **2.2** † | 82.9 | 15.6 |
| ETH | **1.2** † | 56.5 | 0.58 |
| SOL | **3.3** | 19.0 | 0.22 |

† Bybit figures capped by 50-level API; Delta figures from full L2.

## 24h turnover (USD billions)

| Asset | Bybit mainnet | Delta India mainnet | Delta India demo |
|-------|---------------|---------------------|------------------|
| BTC | **7.43** | 1.34 | 0.27 |
| ETH | **3.66** | 0.92 | 0.09 |
| SOL | **1.14** | 0.24 | 0.01 |

## Order book shape (around the touch)

| Asset | Venue | L2 levels (bid / ask) | Top-of-book (bid / ask base) |
|-------|--------|------------------------|------------------------------|
| BTC | Bybit | 50 / 50 (max) | 1.33 / 0.001 BTC |
| BTC | Delta mainnet | 2431 / 1228 | 2.55 / 3.18 BTC |
| BTC | Delta demo | 658 / 144 | 0.96 / 0.45 BTC |
| ETH | Bybit | 50 / 50 (max) | 0.43 / 110 ETH |
| ETH | Delta mainnet | 2249 / 985 | 30.9 / 5.4 ETH |
| SOL | Bybit | 50 / 50 (max) | 516 / 313 SOL |
| SOL | Delta mainnet | (see JSON) | wider spread, thinner touch |

## Practical takeaways for market making

| Goal | Recommendation |
|------|----------------|
| Minimize adverse selection, tightest market | **Bybit mainnet** (if legally/operationally OK for you) |
| India venue, live capital | **Delta India mainnet** — start **BTC/ETH**; treat **SOL** as wider/thinner (wider quotes, smaller size) |
| Bot dev, IP whitelist, post-only tests | **Delta demo** only — **ignore** depth vs mainnet for spread capture expectations |
| Cross-venue fair value | Your Binance lead on Delta is appropriate; **venue_mid** can diverge **80+ bps** on SOL demo vs Binance (see bot metrics) |

## Reproduce

```bash
python3 # script used for snapshot — see liquidity-snapshot.json timestamp
# Or re-run analysis from crypto-strategy/cex-mm after adding a script if desired
```

---

*This report is research, not investment advice. Liquidity changes by time of day and volatility.*
