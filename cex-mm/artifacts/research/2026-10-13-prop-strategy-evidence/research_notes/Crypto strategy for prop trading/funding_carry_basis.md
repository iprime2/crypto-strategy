# Funding-rate carry, basis and market-neutral crypto strategies (2023 – Oct 2026)

Research date: 2026-10-13. Method note: every direct page fetch (WebFetch and curl via the session proxy) failed with DNS/403 errors for bitmex.com, bis.org, amberdata.io, delta.exchange, arxiv.org, coindesk.com, springer.com, prestolabs.io. All findings below therefore come from search-engine snippets of those pages plus the repo's own research notes (`resource/01-academic-papers.md`, `resource/02-practitioner-articles.md`, `resource/05-risk-hedging-pnl-failure-modes.md`), which were written from the full texts. Numbers taken only from a snippet, where the surrounding context could not be checked, are tagged [UNVERIFIED]. My own arithmetic is tagged [SYNTHETIC]. The shared web-search budget ran out before the last eight queries (BitMEX per-exchange breakdown, ScienceDirect paper details, He et al. numbers, Delta funding formula, Ethena annual averages, 2023 funding levels, Coin Metrics Hyperliquid detail); those are listed under Gaps.

## KQ1. Funding levels by period and what a simple cash-and-carry earned, net of fees, with drawdowns

### Takeaway
No source surfaced a clean quarter-by-quarter table of annualized BTC/ETH funding per exchange for 2023–2026; what exists is a set of dated point estimates that trace the same shape: a 2024 spike (basis 15–25% annualized at the early-2024 and Dec-2024 peaks, sUSDe 35% in Q1 2024), a collapse to ~4–5% by Feb 2025, a Q3 2025 Binance BTC mean of 0.0057%/8h (~6.2% annualized, 78% of intervals pinned at the 0.01% floor), then a 2026 regime in which Binance BTC funding was negative for 67 consecutive days (Mar–May 2026) and ~35% of Q2 2026 across six venues, with basis ~1.5% in May 2026 and sUSDe ~4.8% at end-Sep 2026. A fully-funded spot-vs-perp carry therefore earned roughly 10–20% gross in 2024, mid-single digits in 2025, and near zero to low single digits in 2026 before costs; the "drawdowns" are months of negative carry rather than price losses.

### Cited Findings

**Funding-rate structure and baseline**
- Binance BTC funding was exactly 0.01% (the interest-rate floor) for 78.19% of Q3 2025; Binance BTC mean 0.0057% per 8h interval, std dev 0.0039%, ~92.5% of intervals positive; rates "tightly anchored around the 0.01% baseline" — [BitMEX Q3 2025 Derivatives Report](https://www.bitmex.com/blog/2025q3-derivatives-report) [UNVERIFIED: figures from search snippet; page not fetchable]
- 0.01% every 8 hours ≈ 11% annualized — [Datawallet funding-rates page](https://www.datawallet.com/crypto-funding-rates)
- [SYNTHETIC] 0.0057%/8h × 3 × 365 = 6.2% annualized for Binance BTC in Q3 2025.
- Binance USDⓈ-M settlement is 8h (00/08/16 UTC) or 4h; when the prior settlement hits the cap/floor the contract moves to 1h settlement within ~15 min; since 2 Jan 2026 hourly contracts revert to 4h after 16 consecutive cycles with |rate| ≤ 0.025% — [Binance announcement, cited in repo notes](https://www.binance.info/en/support/announcement/detail/e4445d0389ce4defa6009021fcf6ee46)
- The Block's Binance 7-day moving average showed ~4.4% APY in a snapshot ~98 days before 2026-10-13 (i.e. ~early July 2026) — [The Block BTC funding rates](https://www.theblock.co/data/crypto-markets/futures/btc-funding-rates)
- Hyperliquid BTC funding was 1.95× more volatile than Binance BTC and 3.32× more volatile than Deribit BTC; over "the last six months" Hyperliquid BTC had the second-lowest funding for longs, averaging 0.00135% (interval not stated in the snippet; Hyperliquid settles hourly) — [Coin Metrics State of the Network #368](https://coinmetrics.substack.com/p/state-of-the-network-issue-368) [UNVERIFIED]
- [SYNTHETIC] If 0.00135% is hourly: × 8,760 ≈ 11.8% annualized; if it were per-8h it would be ~1.5%. Cannot resolve from the snippet.
- Hyperliquid's own funding-comparison page showed (undated snapshot) BTC: Hyperliquid 0.0100% vs Binance −0.0055%, difference 0.0155%, Hyperliquid BTC OI $3.48B — [Hyperliquid funding comparison](https://app.hyperliquid.xyz/fundingComparison) [UNVERIFIED, undated]

**2024**
- Ethena sUSDe all-time-high APY 35.2% in Q1 2024; all-time-low 4.1% during an August 2024 funding inversion — [Stablecoin Insider sUSDe review](https://stablecoininsider.org/ethenas-staked-usde-stablecoin/) [UNVERIFIED, secondary, figures unsourced]
- Realized sUSDe APY across 2024–2025 ranged ~4% to 30%, "most periods between 8% and 18%", per Ethena's dashboard as relayed by [Eco.com sUSDe explainer](https://eco.com/support/en/articles/14798653-susde-explained-ethena-s-yield-bearing-stablecoin) [UNVERIFIED]
- "At peak in early and late 2024, the annualised Bitcoin basis reached 20–25% and was about 10% by mid-2025" — [jeangalea.com carry-trade guide](https://jeangalea.com/carry-trade-crypto/) [UNVERIFIED, low-quality source]
- Velo Data: annualized one-month CME bitcoin basis ~15% in December 2024 — [CoinDesk, 26 Feb 2025](https://www.coindesk.com/markets/2025/02/26/u-s-bitcoin-etfs-see-record-daily-outflow-of-over-usd930m-as-carry-trades-yield-goes-below-10-year-treasury-note)
- 2024 described as "a relatively stable but low funding rate environment, with occasional dips into negative territory", with price sliding to ~$55,000 in August 2024 — [CryptoSlate](https://cryptoslate.com/insights/bitcoin-funding-rates-showcase-market-sentiment-shifts-from-2021-to-2024/)
- Negative funding during the August 2024 yen-carry unwind and the April 2025 selloff coincided with local price lows — [CoinDesk, 16 Apr 2026](https://www.coindesk.com/markets/2026/04/16/bitcoin-funding-rates-hit-most-negative-since-2023-history-suggests-bottom-is-in)

**2025**
- Feb 2025: CME one-month basis ~4% annualized, lowest in nearly two years; BTC and ETH carry "offer barely more than the U.S. 10-year Treasury"; record $930M+ single-day spot ETF outflow — [CoinDesk, 26 Feb 2025](https://www.coindesk.com/markets/2025/02/26/u-s-bitcoin-etfs-see-record-daily-outflow-of-over-usd930m-as-carry-trades-yield-goes-below-10-year-treasury-note)
- Analyst attribution of the Feb 2025 crash to erosion of the ETF cash-and-carry trade — [Cointelegraph](https://cointelegraph.com/news/bitcoin-crash-triggered-erosion-etf-cash-carry-trade-analyst)
- April 2025: "BTC perpetual funding rates transitioning into negative territory" — [Kaiko Research](https://research.kaiko.com/insights/bitcoin-booms-in-low-risk-environment)
- One source puts 2025 cash-and-carry at ~5.4% vs 4.5% T-bills, "unattractive" — [Bit.com basis trade page](https://www.bit.com/knowledge-hub/basis-trade) [UNVERIFIED, exchange content]
- Dec 2025: CME basis compressed to ~5% (Velo); Binance overtook CME in BTC futures OI as institutional basis demand waned — [CoinDesk, 22 Dec 2025](https://www.coindesk.com/markets/2025/12/22/cme-loses-top-spot-to-binance-in-bitcoin-futures-open-interest-as-institutional-demand-wanes); CME BTC futures activity at a 14-month low "as basis trade unwind drains institutional demand" — [The Block](https://www.theblock.co/post/396722/cme-bitcoin-futures-activity-slumps-to-14-month-low-as-basis-trade-unwind-drains-institutional-demand)
- Oct 2025: Amberdata titled its post-mortem "The Carry Trade That Broke: How Basis Compression Triggered the Cascade" — [Amberdata](https://blog.amberdata.io/the-carry-trade-that-broke-how-basis-compression-triggered-the-cascade) [UNVERIFIED: body not fetchable; only title confirmed]
- Post-10/10, market makers' funding-arb returns fell below ~4% and MMs "have been slow to return" — [CoinGecko Oct-10 explainer, as cited in repo notes](https://www.coingecko.com/learn/october-10-crypto-crash-explained)

**2026**
- Binance 30-day average BTC funding had been below zero since ~1 Mar 2026; Bybit and OKX similar — [Phemex blog](https://phemex.com/blogs/bitcoin-funding-rates-negative-46-days-ftx-bottom) [UNVERIFIED, vendor blog]
- 16 Apr 2026: BTC 7-day average funding ≈ −0.005% (per 8h), most negative since 2023, with price rising toward $75,000 — [CoinDesk, 16 Apr 2026](https://www.coindesk.com/markets/2026/04/16/bitcoin-funding-rates-hit-most-negative-since-2023-history-suggests-bottom-is-in); Glassnode data relayed by [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/bitcoin-funding-rates-hit-lowest-since-2023-as-price-climbs-glassnode-reports)
- 67 consecutive days of negative funding by early May 2026 — [KuCoin news](https://www.kucoin.com/news/flash/bitcoin-funding-rate-turns-negative-as-spot-buyers-push-btc-up-1-2) [UNVERIFIED]
- 1 May 2026: BTC OI flat at ~$19B, basis "subdued at roughly 1.5% annualized" — [CoinDesk, 1 May 2026](https://www.coindesk.com/markets/2026/05/01/bitcoin-ticks-higher-but-remains-range-bound-as-traders-keep-short-bias)
- Funding was negative ~35% of Q2 2026 across six venues, clustering around sell-offs — [Bitsgap, "What a spot hedge on perpetuals really cost in 2026"](https://bitsgap.com/blog/what-a-spot-hedge-on-perpetuals-really-cost-in-2026) (cited in repo `resource/05`)
- ~Apr 2026: CME basis ~5% vs ~4.5% risk-free, "little incentive to run the trade" — search summary of an article ~186 days old; URL not captured [UNVERIFIED]
- Funding flipped positive in the third week of Aug 2026; on 20 Aug ~$1.74B short liquidations in 24h, BTC +7.5% to ~$69,117 — [Bitsgap funding-rate explainer](https://bitsgap.com/blog/funding-rate-explained) [UNVERIFIED, vendor blog]
- sUSDe 30-day average APY: 7.17% on 1 Oct 2025 (supply 6.02B USDe) → 3.85% on 1 Jul 2026 (supply 1.68B USDe) — [Aavescan sUSDe](https://aavescan.com/rates/ethena-susde) (note: this is the Aave-supplied sUSDe pool; supply figure is pool supply, not total USDe)
- 28 Sep 2026: sUSDe ~4.76% APY, 30-day average 4.79%; total USDe supply down from ~$14.8B (Oct 2025 peak) to ~$4.95B — [Stablecoin Insider](https://stablecoininsider.org/ethenas-staked-usde-stablecoin/) [UNVERIFIED]
- Ethena states bitcoin funding has averaged 3.9% vs 13.9% for equity perpetuals, and is routing part of the strategy into equity perps — [Zipp Feed](https://zippfeed.com/a/ethena-pivots-usde-basis-trade-into-equity-perpetuals) [UNVERIFIED; period of the average not stated]
- CME launched 24/7 crypto futures on 29 May 2026, which may remove the weekend premium — [Phemex](https://phemex.com/blogs/cme-crypto-24-7-bitcoin-futures) [UNVERIFIED]

**Drawdown episodes for carry books**
- 5–6 Feb 2026: BTC < $60k intraday, −12.6% day; "CME basis unwinds", IBIT record $10B volume; futures OI fell >20% in a week — [Convex Dispatch](https://convexdispatch.substack.com/p/the-day-liquidity-died-the-february); [VanEck / Sigel](https://www.vaneck.com/us/en/blogs/digital-assets/matthew-sigel-what-triggered-bitcoins-major-selloff-in-february-2026/) (both cited in repo `resource/05`)
- BTC drawdown from the Oct 2025 ATH (~$126,000) to ~$58,000 by late June/early July 2026, >54% — [CryptoBriefing](https://cryptobriefing.com/bitcoin-down-54-from-october-peak-longest-drawdown-since-2022/); Feb 13 2026 level ~$60,246 (−52%) — [Leverage Shares](https://crypto.leverageshares.com/insights/bitcoin-is-approaching-a-major-bottom)

**Academic evidence on carry returns**
- BIS Working Paper 1087 "Crypto carry": the Jan 2024 spot-ETF launch cut the basis across exchanges and cut the CME basis by ~97% of its mean — [BIS WP 1087](https://www.bis.org/publ/work1087.pdf) [UNVERIFIED: figure from search summary; PDF not fetchable]
- He, Manela, Ross & von Wachter: crypto perp–spot deviations are larger than in FX, co-move across coins, and "shrink over time"; an implied arbitrage strategy earns high Sharpe ratios — [arXiv 2212.06888 v7, Sept 2026](https://arxiv.org/abs/2212.06888) (abstract, via repo `resource/01`)
- ScienceDirect study of funding-rate arbitrage on CEX and DEX: annualized Sharpe 3.53 for BTC at zero fees, 1.80 under "high trading costs a retail participant pays"; return split 8.64% from price convergence vs 5.06% from funding for BTC; "up to 115.9% over six months with losses limited to 1.92% across 60 scenarios"; authors warn results "might not be applicable in future scenarios" — [ScienceDirect S2096720925000818](https://www.sciencedirect.com/science/article/pii/S2096720925000818) [UNVERIFIED: period, leverage and venues not visible in snippet]

### Inferences
- [SYNTHETIC] Gross carry on a fully funded 1:1 spot/perp position at the 0.01% floor is ~11%/yr; at the Q3 2025 Binance mean it is ~6%/yr; in H1 2026, with funding negative for roughly two-thirds of Mar–May and 35% of Q2, gross carry was plausibly 0–3%/yr and negative for whole months. Levered carry (perp at 3–5× margin, spot fully funded) raises return on capital by only ~1.2–1.3× because the spot leg still has to be fully paid for.
- Fee drag on BTC/ETH majors is small relative to 2024 carry but material relative to 2026 carry: a round trip at retail taker rates on a big CEX (~4–5 bps/side on perp plus ~10 bps spot) is ~20–30 bps, i.e. one to two months of 2026-level carry.
- The "worst drawdown" of a plain cash-and-carry is not a price loss (the hedge holds) but (a) months of paying negative funding (Aug 2024 inversion; Mar–May 2026 67-day streak), (b) basis widening against a short perp during sell-offs, and (c) the tail where the short-perp leg is ADL'd or the venue mis-marks collateral (Oct 10 2025, KQ7). No source quantified a realized drawdown path for a retail carry book; treat as a gap.
- The 2024 peaks were an ETF/institutional-entry artefact; the BIS finding that the ETF cut the CME basis by ~97% of its mean [UNVERIFIED] plus the Dec 2025 CME OI loss to Binance and The Block's "basis trade unwind" are consistent with the trade being arbitraged to near the risk-free rate on regulated venues.

### Gaps
- No quarter-by-quarter annualized funding averages for Binance, Bybit, OKX, Hyperliquid or Delta India for 2023–2026 were found in any source; the search engine returned only dashboards (Coinglass, Coinalyze, Glassnode, The Block, Lookintobitcoin) whose historical tables could not be read. Building the table requires pulling each exchange's funding-history endpoint and averaging; Delta has no funding-history endpoint (see KQ5).
- 2023 funding levels: nothing beyond the implication that Apr 2026 was "most negative since 2023".
- ETH-specific funding/basis figures: none found separately from BTC except Ethena's blended yield.
- OKX- and Bybit-specific averages: none.
- The ScienceDirect and Springer papers' sample periods, venues and leverage assumptions could not be read.
- The BIS WP 1087 exact sample period, Sharpe and crash-risk results could not be read (PDF blocked).

## KQ2. Cross-exchange funding arbitrage (long perp on A, short perp on B)

### Takeaway
Practitioner sources quote 3–5% annualized of extra spread from cross-venue funding differentials on top of base carry, and single-snapshot Hyperliquid-vs-Binance gaps of ~0.015%/interval, but every return figure is a backtest or marketing claim; the two peer-reviewed-style papers both say counterparty/venue failure dominates the risk and that results are "highly assumption-sensitive". Capital efficiency is poor because both legs must be pre-funded and margined on separate venues.

### Cited Findings
- Cross-platform funding differentials add roughly 3–5% annualized; Gate claims a 19.26% average annual return for funding arbitrage in 2025 vs 14.39% in 2024 — [Gate Learn](https://www.gate.com/learn/articles/perpetual-contract-funding-rate-arbitrage/2166) [UNVERIFIED, exchange marketing, methodology unstated]
- Ouinex estimates ~19% annualized at average rates, noting "competitive environments can halve this" — [Ouinex](https://ouinex.com/en/education/funding-rate-arbitrage-cashing-in-on-perpetual-swings) [UNVERIFIED, exchange content]
- Hyperliquid-vs-Binance BTC snapshot: 0.0100% vs −0.0055%, i.e. 0.0155% per interval gap — [Hyperliquid funding comparison](https://app.hyperliquid.xyz/fundingComparison) [UNVERIFIED, undated]
- Hyperliquid settles hourly; Binance USDⓈ-M every 8h (or 4h/1h per the cap rules) — any spread must be normalized to the same clock — [OneKey guide](https://onekey.so/blog/ecosystem/hyperliquid-binance-funding-arbitrage/)
- Springer (2026) CEX–DEX basis trade paper: net annualized returns are driven mainly by funding carry; returns are "highly assumption-sensitive and should not be interpreted as frictionless arbitrage profits"; stress tests find counterparty-risk episodes more damaging than directional price crashes — [Springer s42521-026-00213-3](https://link.springer.com/article/10.1007/s42521-026-00213-3) [UNVERIFIED: numbers not visible]
- ScienceDirect CEX/DEX funding-arb study: leverage "a double-edged sword", prudent collateral management needed against liquidation — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2096720925000818)
- Listed risks: funding reversal, transfer delays, margin management on both legs simultaneously, thin books widening fills, pre-funded capital across venues, crowding compressing rates — [CCXT arbitrage playbook](https://docs.ccxt.com/blog/crypto-arbitrage-strategies); [Wundertrading](https://wundertrading.com/journal/en/funding-arbitrage); [ArbitrageGhost Medium](https://arbitrageghost.medium.com/funding-rate-arbitrage-in-2026-the-complete-guide-with-real-calculations-40e6cf341e52) [all UNVERIFIED practitioner content]
- Venue-failure examples relevant to the "exchange failure" leg: Bybit lost ~400,000 ETH (~$1.4–1.5B) on 21 Feb 2025, processed 99.994% of 350,000+ withdrawal requests within 10 hours and stayed solvent — [Bybit incident timeline](https://www.bybit.com/en/learn/this-week-in-bybit/bybit-security-incident-timeline); [CNBC](https://www.cnbc.com/2025/02/21/hackers-steal-1point5-billion-from-exchange-bybit-biggest-crypto-heist.html)
- Wintermute had short positions ADL'd at ~$5 when the token traded at ~$1 on Oct 10 2025 and "could not move inventory between venues" — [BlockBeats](https://en.theblockbeats.news/news/59932) (via repo `resource/05`)
- OKX reports API pressure and `50004` unknown-result timeouts at funding timestamps — [OKX API FAQ](https://www.okx.com/help/api-faq) (via repo `resource/05`)

### Inferences
- With the Binance BTC rate pinned at the 0.01% floor 78% of the time (Q3 2025), the only source of cross-venue spread is the venue whose rate is not pinned (Hyperliquid, smaller CEXs, or altcoin perps). That spread is episodic, so realized returns depend on being positioned before the episode, not on a steady carry.
- The Oct 10 2025 Wintermute case is the canonical failure: a two-leg hedge is only neutral if neither venue force-closes a leg; ADL on one venue converts the book into a naked position at the worst moment, and transfers between venues were not possible in time.
- For an Indian resident this strategy requires capital on a foreign venue, which runs into the FEMA/LRS problem in KQ5.

### Gaps
- No independent, audited live track record for cross-exchange funding arb was found; all numbers are backtests or exchange marketing.
- Typical realized spread distribution (percentiles) between Binance/Bybit/OKX/Hyperliquid was not available; only one undated snapshot.

## KQ3. Funding rate as a directional signal

### Takeaway
The post-2023 evidence that funding predicts returns is weak and mostly about regime extremes: Presto Labs finds funding changes explain ~12.5% of 7-day price variation with the effect fading afterwards; the only academic predictability paper found (Inan, SSRN) forecasts the funding rate itself, not returns; and the "extreme negative funding marks local bottoms" claim (Aug 2024, Apr 2025, Apr–May 2026) is anecdotal. No systematic post-2023 event study at 1-hour to 1-week horizons net of costs, and no "basis momentum"/"funding momentum" paper, was found.

### Cited Findings
- Presto Labs: "a statistically significant yet weak correlation between funding rate changes and price movements, with funding rate changes explaining 12.5% of price variation over a 7-day period"; predictive power "diminishes significantly" in subsequent periods; signal "may be more useful when applied cross-sectionally across multiple assets" — [Presto Labs](https://www.prestolabs.io/research/can-funding-rate-predict-price-change) [UNVERIFIED: sign of the effect, sample and costs not visible in snippet]
- Inan, "Predictability of Funding Rates" (SSRN 5576424): double-autoregressive models beat a no-change benchmark on forecast error and directional accuracy for next-period BTC funding on Binance and Bybit — forecasts the rate level, not returns — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424)
- Zhang (SSRN, Jan 2026), "Funding Rate Mechanism in Perpetual Futures": theory; a linear funding rule induces an endogenous mean-reverting basis — [ResearchGate](https://www.researchgate.net/publication/401892113_Funding_Rate_Mechanism_in_Perpetual_Futures)
- He, Manela, Ross & von Wachter: perp–spot deviations are mean-reverting; cross-venue basis dispersion is a stress signal; implied arbitrage earns high Sharpe — [arXiv 2212.06888](https://arxiv.org/abs/2212.06888); Ackerer, Hugonnier & Jermann: perp price = risk-neutral expectation of spot sampled at a random time whose intensity reflects funding anchoring — [arXiv 2310.11771](https://arxiv.org/abs/2310.11771) (both via repo `resource/01`)
- Le (2026), funding-aware market making calibrated on Hyperliquid: funding fits an OU process with jumps (hourly jump probability 2.05% ETH, 1.24% BTC, 0.16% SOL); funding-aware quoting beat Avellaneda-Stoikov on ETH/BTC but BTC win rate only 0.57 and "simple projected funding-aware quote rules are not robust" — [repo `resource/papers/le-2026-funding-aware-optimal-mm-perpetual-dexs.pdf`](https://arxiv.org/abs/2506.08573) (note: repo cites Le separately from Kim & Park's arXiv 2506.08573 design paper)
- Negative-funding-as-bottom: 16 Apr 2026 7-day funding most negative since 2023 while price rose, "history suggests bottom is in" — [CoinDesk](https://www.coindesk.com/markets/2026/04/16/bitcoin-funding-rates-hit-most-negative-since-2023-history-suggests-bottom-is-in); 7 May 2026 "negative funding is actually a bullish signal" — [CoinDesk](https://www.coindesk.com/business/2026/05/07/the-great-derivatives-disconnect-why-negative-funding-is-actually-a-bullish-signal-for-bitcoin); 10 Mar 2025 "No bottom in sight as funding swings" — [CoinDesk](https://www.coindesk.com/markets/2025/03/10/no-bottom-in-sight-as-bitcoin-funding-rate-swings); Van Straten on 2024 negative prints preceding rallies — [Yahoo Finance](https://finance.yahoo.com/news/bitcoin-funding-rates-briefly-went-102603146.html)
- 46 consecutive days of negative funding at the FTX bottom (2022) — [Phemex](https://phemex.com/blogs/bitcoin-funding-rates-negative-46-days-ftx-bottom) [UNVERIFIED]
- Extreme positive funding (0.15–0.20%/8h in 2021) preceded 10–30% corrections — exchange educational content, a few episodes, no event study — [Kraken Learn](https://www.kraken.com/learn/futures-trading-funding-rate-strategy); [Nexo](https://nexo.com/blog/crypto-funding-rates-explained) [UNVERIFIED]
- Robot Wealth uses funding as a "carry" feature alongside momentum and breakout in decile sorts of a perp universe, with forward return defined as next-period funding plus price change; no public backtest numbers for funding alone — [Robot Wealth, modelling features as expected returns](https://robotwealth.com/how-to-model-features-as-expected-returns/); [Quantifying and combining crypto alphas](https://robotwealth.com/quantifying-and-combining-crypto-alphas/); carry mechanics in [Art and Science of Trading Carry](https://robotwealth.com/the-art-and-science-of-trading-carry/)
- Crypto.com (Aug 2026) RWA-perp cash-and-carry backtest convention: next-day execution, 4 bps taker + 2 bps slippage per side, 3% minimum annualized funding threshold to enter — [Crypto.com Research](https://crypto.com/us/research/rwa-enhancing-portfolio-beyond-crypto-aug-2026)
- MDPI (2026) "Two-Tiered Structure of Cryptocurrency Funding Rate Markets": descriptive CEX-vs-DEX statistics, decomposes funding into interest differential and basis premium; no momentum sorts in the visible excerpt — [MDPI Mathematics 14(2):346](https://www.mdpi.com/2227-7390/14/2/346)
- Crypto momentum literature finds time-series momentum stronger than cross-sectional under realistic costs; none of it uses funding as the sorting variable — [AUT working paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf); [Cryptocurrency Factor Momentum, Quantitative Finance 2023](https://www.tandfonline.com/doi/abs/10.1080/14697688.2023.2269999)

### Inferences
- Because Binance BTC funding sits at the 0.01% floor most of the time, the signal has almost no variance on majors on the largest venue in calm regimes; whatever information exists is concentrated in (a) regime flips to sustained negative funding and (b) altcoin or Hyperliquid prints that are not pinned.
- A 12.5% R² at 7 days with fading persistence, before costs, is not evidence of a tradable standalone signal at retail fees (Delta taker 5.31 bps/side); it is at most a conditioning variable for a strategy that already trades.
- The repo's own funding-aware MM evidence (Le 2026) points the same way: modest, non-robust gains.

### Gaps
- No peer-reviewed or practitioner event study with forward returns after extreme funding at 1h/4h/1d/1w horizons net of costs, post-2023, was found.
- No paper using "basis momentum" or "funding-rate momentum" in crypto perps was found; this appears to be an open question, not a settled literature.
- The sign of Presto's 7-day relationship (continuation vs reversal) could not be read from the snippet.

## KQ4. Capacity and crowding since 2024

### Takeaway
The trade has compressed sharply and visibly: CME basis ~15% (Dec 2024) → ~4% (Feb 2025) → ~5% (Dec 2025 and ~Apr 2026) against a ~4.5% risk-free rate; Binance BTC funding pinned at the floor 78% of Q3 2025 and negative for most of Mar–May 2026; USDe supply fell from ~$14.8B to ~$5B and Ethena is moving capital to equity perps; CME lost its OI lead to Binance. Realistic 2026 gross yields on BTC/ETH majors are low single digits to ~10% in short positive episodes, not the 15–25% of 2024.

### Cited Findings
- CME basis: ~15% (Dec 2024) → ~4% (late Feb 2025) — [CoinDesk, 26 Feb 2025](https://www.coindesk.com/markets/2025/02/26/u-s-bitcoin-etfs-see-record-daily-outflow-of-over-usd930m-as-carry-trades-yield-goes-below-10-year-treasury-note); ~5% (Dec 2025) — [CoinDesk, 22 Dec 2025](https://www.coindesk.com/markets/2025/12/22/cme-loses-top-spot-to-binance-in-bitcoin-futures-open-interest-as-institutional-demand-wanes); ~5% vs 4.5% risk-free (~Apr 2026, source URL not captured) [UNVERIFIED]
- BIS WP 1087: spot-ETF launch cut the CME basis by ~97% of its mean — [BIS](https://www.bis.org/publ/work1087.pdf) [UNVERIFIED]
- Binance BTC funding exactly 0.01% for 78.19% of Q3 2025 — [BitMEX Q3 2025 report](https://www.bitmex.com/blog/2025q3-derivatives-report) [UNVERIFIED]
- Basis ~1.5% annualized, OI ~$19B on 1 May 2026 — [CoinDesk](https://www.coindesk.com/markets/2026/05/01/bitcoin-ticks-higher-but-remains-range-bound-as-traders-keep-short-bias)
- USDe supply: peak ~$14.8B (Oct 2025) → ~$4.95B (28 Sep 2026) — [Stablecoin Insider](https://stablecoininsider.org/ethenas-staked-usde-stablecoin/) [UNVERIFIED]; another report has supply below $5B from a ~$15B peak and Ethena pivoting to equity perps where funding averaged 13.9% vs 3.9% for BTC — [Zipp Feed](https://zippfeed.com/a/ethena-pivots-usde-basis-trade-into-equity-perpetuals) [UNVERIFIED]
- Ethena adding tokenized-gold perps (PAXG, XAUT) as a funding floor and diversifying beyond crypto basis — [BingX Learn](https://bingx.com/en/learn/article/usde-2-ethena-internet-bond-diversification-2026) [UNVERIFIED]
- Ethena reserve fund ~$61M in Mar 2026 against $5.6B supply (~1.1%) — [EarnPark](https://earnpark.com/en/posts/ethena-fees-apy-interest-rates-explained-2026/) [UNVERIFIED]
- CME BTC futures activity at a 14-month low as the basis trade unwinds — [The Block](https://www.theblock.co/post/396722/cme-bitcoin-futures-activity-slumps-to-14-month-low-as-basis-trade-unwind-drains-institutional-demand)
- Post-Oct-10 2025: MM funding-arb yields "below ~4%", MMs slow to return; BTC 10-bp depth $48M → $26M in 48h and still ~40% below peak three months later; Binance perp OI down ~50% on average — [CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained); [Amberdata liquidity post](https://blog.amberdata.io/the-liquidity-that-vanished-inside-octobers-40-depth-collapse); [Odaily](https://www.odaily.news/en/post/5206861) (all via repo `resource/05`)
- Kaiko: >55% of BTC-USD trading now in U.S. hours vs 39% in 2020, read as institutional participation — [Kaiko](https://www.kaiko.com/resources/btc-etfs-impact-on-spot-market-structure)
- Crowding mechanism noted by practitioners: as capital enters, rates compress toward zero — [CCXT playbook](https://docs.ccxt.com/blog/crypto-arbitrage-strategies)

### Inferences
- A retail book of a few thousand to a few lakh INR is far below any capacity limit; the binding constraint is not capacity but that the marginal yield has fallen to roughly the risk-free rate on the deepest venues. Capacity only matters in the episodic spikes (altcoins, Hyperliquid listings, equity/gold perps) where it is small and contested by Ethena-scale players.
- Realistic 2026 expectation for BTC/ETH on a large CEX: 0–6% gross annualized carry with months of negative carry; higher only by taking altcoin, DEX or RWA-perp funding (and the ADL/venue risk that comes with it).

### Gaps
- No figure for current (Sep–Oct 2026) CME or Binance BTC basis; the latest dated point is May 2026 (1.5%) and the ~Apr 2026 CME 5%.
- No estimate of total capital deployed in cash-and-carry in 2026 beyond USDe supply.

## KQ5. Feasibility on Delta Exchange India

### Takeaway
Delta Exchange India now offers spot (BTC, ETH, SOL, XRP; buyer 0% fee, seller 0.1%) alongside INR-margined perpetuals and options, so an on-venue spot-vs-perp carry is mechanically possible; funding is exchanged at 05:30/13:30/21:30 IST (8-hourly, some products 1h/2h/4h) since 8 Sep 2025, there are no dated futures to lock a basis, there is no funding-history API endpoint, and no public record of Delta's historical funding levels was found. Cross-venue carry with a foreign exchange runs into FEMA: Schedule III of the FEM (CAT) Rules bars margin to overseas exchanges, AD banks generally refuse LRS for crypto, and the 1% TDS / 30% flat tax regime applies to spot.

### Cited Findings
**Products**
- Delta Exchange India launched spot trading in BTC, ETH, SOL and XRP; buyers pay zero trading fees, sellers 0.1% (PTI/PRNewswire release ~Apr 2026) — [The Wire / PTI](https://m.thewire.in/article/ptiprnews/delta-exchange-unveils-indias-most-cost-effective-crypto-spot-trading) [UNVERIFIED: press release]
- Official India guide lists four spot pairs: BTC/USD, ETH/USD, XRP/USD, SOL/USD, "more markets in the offing" — [Delta India user guide](https://guides.delta.exchange/delta-exchange-india-user-guide)
- Delta also launched "Trackers" as an alternative to spot — [The Wire / PTI](https://m.thewire.in/article/ptiprnews/delta-exchange-launches-trackers-a-game-changing-alternative-to-spot-crypto-trading) [UNVERIFIED]
- All contracts are notionally quoted, margined and settled in USD, but the platform's USD-INR rate is fixed and balances are maintained in INR, so contracts are effectively margined and settled in INR — [Delta India user guide](https://guides.delta.exchange/delta-exchange-india-user-guide)
- Futures are perpetuals that do not expire; a 2026 review says there are no dated (expiring) futures — [BestCryptoIndia review](https://bestcryptoindia.com/delta-exchange-review) [UNVERIFIED]; contradicted by a cryptonews piece listing daily/weekly/monthly expiry futures — [Cryptonews.net](https://cryptonews.net/editorial/analytics/analyzing-delta-exchange-a-hub-for-inr-settled-derivatives-and-advanced-crypto-trading-strategies/) [UNVERIFIED, outlier]
- Options with daily, weekly and monthly expiries — [delta.exchange](https://www.delta.exchange/); [Google Play listing](https://play.google.com/store/apps/details?id=com.deltaexchangeindia&hl=en_IN)
- Spot product list is served from `api.india.delta.exchange` — [Delta API docs](https://docs.delta.exchange/)

**Funding**
- Funding exchanged at 5:30 am, 1:30 pm and 9:30 pm IST, effective from the interval starting 5:30 pm on 8 Sep 2025; previously exchanged every minute; "broadly every 8 hours, but exact intervals may vary depending on the product, such as 1 hour, 2 hours, or 4 hours" — [Delta support article 80001183756](https://www.delta.exchange/support/solutions/articles/80001183756-update-on-funding-exchange-schedule-for-perpetual-contracts)
- India perpetuals guide: 8-hourly funding at the same IST times; some contracts 4/2/1-hour — [Delta India derivatives guide](https://guides.delta.exchange/delta-exchange-india-user-guide/derivatives-guide/docs)
- Delta has no funding-rate-history API endpoint, so third-party backtesters cannot back-adjust funding — [freqtrade-delta-exchange on PyPI](https://pypi.org/project/freqtrade-delta-exchange/)
- The repo's bot reads Delta's funding rate as a percent per 8h and applies a fair-value shift of −sign(q) × funding (since 2026-10-12); an earlier bug read the percent as a fraction — repo `STRATEGY.md` line 188 (local)

**Fees and tax**
- Retail fees incl. GST with referral discount: maker 2.12 bps, taker 5.31 bps — given in the task brief (repo `CLAUDE.md`)
- 1% TDS and 30% flat tax apply if you buy spot on Delta India — [Delta India user guide](https://guides.delta.exchange/delta-exchange-india-user-guide); a review claims no 1% TDS or 30% flat tax on derivatives contracts — [BestCryptoIndia](https://bestcryptoindia.com/delta-exchange-review) [UNVERIFIED, conflicting with the VDA-tax reading of perps; treat as unresolved]
- Crypto gains taxed under Section 115BBH — [TaxGuru, Crypto & FEMA](https://taxguru.in/rbi/crypto-fema-evolving-grey-zone.html); "legal but taxed (1% TDS + 30% on gains)" — [righttoinformation.wiki](https://righttoinformation.wiki/cryptocurrency-legal-india-2026) [UNVERIFIED]

**FEMA / LRS / foreign venues**
- No notified FEMA rule directly governs crypto purchases abroad or LRS remittances to crypto platforms; banks have become conservative and often question such remittances — [TaxGuru](https://taxguru.in/rbi/crypto-fema-evolving-grey-zone.html)
- "RBI has banned LRS for investment in cryptocurrency. Banks will reject any remittance request where the purpose is to invest in digital currency" — [Karbon Card](https://www.karboncard.com/blog/what-is-liberalised-remittance-scheme-lrs) [UNVERIFIED, fintech blog, no RBI citation]
- AD banks "generally do not permit LRS remittances for overseas cryptocurrency investments" — [Groww](https://groww.in/blog/liberalised-remittance-scheme)
- Schedule III of the FEM (Current Account Transactions) Rules bars "trading in foreign exchange abroad" and "margin or margin calls to overseas exchanges or counterparties" — [Xflow summary](https://www.xflowpay.com/blog/lrs-liberalized-remittance-scheme); RBI FAQ on residual current-account transactions — [RBI LRS FAQ](https://www.rbi.org.in/commonman/english/Scripts/FAQs.aspx?Id=1834)
- Binance registered with FIU-IND in Aug 2024 after a ~₹18.82 crore (~$2.25M) penalty; website and app fully available in India — [Business Today](https://www.businesstoday.in/technology/news/story/crypto-exchange-binance-achieves-legal-status-in-india-registers-with-financial-intelligence-unit-441692-2024-08-16); [CoinDesk](https://www.coindesk.com/policy/2024/08/15/binance-completes-registration-with-indias-financial-intelligence-unit-months-after-being-fined)
- PMLA notification of March 2023 requires any VDA service provider serving Indian users to register with FIU-IND; ~54 registered as of mid-2026 per a secondary list — [OpenRate](https://openrate.live/blog/fiu-ind-registration-explained) [UNVERIFIED count]

### Inferences
- [SYNTHETIC] On-venue carry cost on Delta India: open = buy spot (0 bps) + short perp maker (2.12 bps); close = sell spot (10 bps) + buy perp maker (2.12 bps); round trip ≈ 14.2 bps if both perp legs are post-only, ≈ 20.6 bps at taker. Against 0.01%/8h carry (10.95%/yr gross) that is ~5 days of carry; against 2026-style 0–3% carry it is one to two months. The 1% TDS on the spot sale is a cash drag of 100 bps (creditable against tax, not a cost) that dwarfs the fee math for short holds.
- [SYNTHETIC] Capital use: spot fully funded (100% of notional) plus perp margin (~20–33% at 3–5× plus buffer) → ~1.3× notional; a 6%/yr gross carry becomes ~4.5% on capital before tax; a 30% flat tax on the spot gain with the uncertain ability to offset derivative losses (Section 115BBH treatment of perps unresolved above) can make the after-tax result negative when spot rallies and the perp loses.
- Without dated futures there is no locked basis; the trade is pure floating-funding harvest, fully exposed to sign flips and to Delta's own (unobservable-in-history) funding distribution.
- Delta's INR-fixed USD rate removes FX basis between the spot and perp legs on-venue, but a cross-venue hedge (Delta perp vs Binance spot) would carry INR/USD and transfer risk, and funding the foreign leg via LRS is in practice refused by AD banks and arguably barred by Schedule III (margin to overseas exchanges).
- Since Delta India's own BTCUSD/ETHUSD perps run on one-tick spreads (0.06/0.18 bps per repo `CLAUDE.md`), a post-only basis entry on the perp leg is feasible; the 10 bps spot seller fee is the dominant venue cost.

### Gaps
- Delta India's historical funding levels (mean, % positive, extremes) for BTCUSD/ETHUSD: not found anywhere; no history endpoint exists. Would need to be recorded by polling (the repo's shadow infrastructure could do this).
- Delta's funding formula, interest-rate component and cap could not be read (support page blocked; search budget exhausted before the targeted query ran).
- Whether Delta India spot is INR-quoted or USD-quoted at the fixed rate, and whether spot assets can be withdrawn on-chain: not established.
- Whether Delta India perps are treated as VDA transfers (30% / 1% TDS) or as derivatives for income-tax purposes: sources conflict; no CBDT or statutory text found.
- Whether Binance's FIU-registered India offering supports INR on-ramps that avoid LRS, and whether a cross-venue carry (Delta perp vs Binance spot, both FIU-registered) is FEMA-compliant: not researched.

## KQ6. Prop-firm fit (brief; another researcher covers firms)

### Takeaway
Crypto prop firms are single-venue CFD-style accounts, so neither cash-and-carry nor cross-exchange funding arbitrage can be run inside one; "arbitrage", "long/short arbitrage", "reverse arbitrage" and cross-account hedging are explicitly prohibited at several firms, while same-account hedging is allowed at some. No source stated how funding payments are treated against drawdown.

### Cited Findings
- FundedNext allows hedging only within the same account; cross-account/cross-firm/cross-platform hedging is "strictly prohibited" with one firm applying a soft-breach warning first — [Dolvero prop-firm rules comparison](https://dolvero.com/blog/prop-firm-rules-compared-2026) [UNVERIFIED]
- A crypto firm's prohibited list: "High-Frequency Trading, toxic order flow, long/short arbitrage, reverse arbitrage, tick scalping, server execution manipulation"; another defines HFT as 4+ filled orders in the same direction on the same asset within 3 minutes — [PropFirmMatch crypto rules](https://propfirmmatch.com/crypto/prop-firm-rules) [UNVERIFIED]
- Crypto Fund Trader prohibits arbitrage (with HFT, tick scalping, all-in trades) — [LuxAlgo CFT page](https://www.luxalgo.com/prop-firms/crypto-fund-trader/); prohibits hedging and opposite positions across accounts, "abusive hedging", "reverse trading across accounts"; normal scalping allowed; 40% single-day consistency rule only on Break Final Stage accounts — [TheGodFunded CFT review](https://thegodfunded.com/en/firms/cryptofundtrader/) [UNVERIFIED]
- HyroTrader: mandatory stop-loss within 5 minutes of every trade, breach on second violation; trailing drawdown; 3% max loss per trade; 70% starting split — [Kraken Breakout vs HyroTrader](https://www.kraken.com/ca/learn/breakout-vs-hyrotrader); [FundedTrading HyroTrader review](https://fundedtrading.com/propfirm/hyrotrader/) [UNVERIFIED]
- Breakout: 80% split from day one, no stop-loss requirement, no minimum trading days, no consistency rules, on-demand USDC payouts; hedging/arbitrage terms not found — [Kraken comparison](https://www.kraken.com/ca/learn/breakout-vs-hyrotrader)
- Typical limits 5% daily / 10% overall, with static-vs-trailing and balance-vs-equity definitions differing by firm — [Funding Pips rules](https://tradingfinder.com/props/funding-pips/rules/); [H2T hedging guide](https://h2tfunding.com/best-prop-firms/allow-hedging/)

### Inferences
- Only the directional use of funding (KQ3) is even expressible in a prop account, and the evidence for that is weak; the market-neutral strategies in this brief are structurally incompatible with prop accounts.
- If a firm passes through perp funding to the account, holding a position across settlements during negative funding reduces equity and therefore counts against a trailing drawdown; this is an inference, not a documented rule.

### Gaps
- No firm's terms on whether funding payments are charged to the account or count toward daily/max drawdown were found.

## KQ7. Operational risks documented 2024–2026

### Takeaway
Oct 10–11 2025 is the reference event: ~$19–19.3B liquidated across 1.6M accounts, Hyperliquid ADL'd an estimated $660M (simulated) to $2.1B (realized) of winning PnL in 12 minutes across ~35,000 executions, Binance mis-marked USDe to ~$0.65 and BNSOL to $0.13 off its own thin books and rejected reduce-only orders for over 100 minutes, dYdX was offline ~8 hours, and BTC depth was still ~40% below peak three months later. Bybit's $1.4–1.5B hack (Feb 2025) and the Feb 2026 CME-basis unwind are the other documented stress cases.

### Cited Findings
- ~$19B liquidated in 24h, >1.6M accounts; Coinglass figure $19.3B — [Datawallet](https://www.datawallet.com/crypto/october-10-crypto-crash-explained); [TokenPost](https://www.tokenpost.com/news/investing/29166); trigger was the 100%-China-tariff headline — [CoinShares](https://coinshares.com/us/insights/knowledge/billions-in-liquidations-what-happened/)
- Hyperliquid ~53% of global liquidations ($10.25B) on-chain, partly a visibility artefact since Binance's API reports one liquidation per second per market — [CCN](https://www.ccn.com/education/crypto/oct-10-crypto-flash-crash-exchanges-whales-traders-who-lost/)
- arXiv "Autodeleveraging: Impossibilities and Optimization" (Dec 2025): Hyperliquid autodeleveraged ~$660M (simulated) to ~$2.1B (realized) of winning-trader PnL during the 12-minute cascade; ADL used >40 times in 10 minutes; 34,983 ADL executions across 19,337 wallets and 162 markets; first Hyperliquid ADL in >2 years — [arXiv 2512.01112](https://arxiv.org/html/2512.01112v2); [Datawallet table](https://www.datawallet.com/crypto/october-10-crypto-crash-explained) [UNVERIFIED: paper not fetchable]
- Binance: USDe, BNSOL and wBETH depegged 21:36–22:16 UTC on Oct 10 because collateral was marked off Binance's internal spot books; USDe to ~$0.65, WBETH 80–90% below redemption, BNSOL to $0.13; USDE/USDT liquidity fell 74% in 15 minutes — [LlamaRisk](https://llamarisk.com/research/when-pricing-breaks-usde); [CT research orderbook data](https://ct.com/research/exclusively-obtained-orderbook-data-reveals-details-about-usde-crash) (via repo `resource/05`); $283M compensation in two batches — [The Block](https://www.theblock.co/post/374295/binance-pays-283-million-in-compensation-following-fridays-depegs-covering-user-losses); Binance post-mortem: ~75% of liquidations before the depeg, >$328M compensation plus $300M goodwill, tightened deviation thresholds and cross-exchange reference pricing — [BanklessTimes](https://www.banklesstimes.com/articles/2026/01/31/october-10-crypto-crash-binance-releases-post-mortem-findings/)
- Traders locked out of risk-reducing orders for nearly two hours — [Forbes](https://www.forbes.com/sites/boazsobrado/2025/10/21/locked-out-and-liquidated-traders-blame-binance-for-19-billion-crash/); one MM lost 591,835 USDT on DOGE/XRP after reduce-only rejections >100 min — [CoinEdition](https://coinedition.com/binance-system-failure-reduceonly-order-outage/) (via repo)
- Wintermute shorts ADL'd at ~$5 vs ~$1 market, could not move inventory between venues — [BlockBeats](https://en.theblockbeats.news/news/59932) (via repo)
- dYdX offline nearly eight hours — [EdgeX news](https://pro.edgex.exchange/en-US/news/article/crypto-auto-deleveraging-risks) [UNVERIFIED]
- Ethena's Guy Young: "not accurate to describe this as a USDe depeg when a single venue was out of line"; Ethena said its strategies were profitable during the event (no independent confirmation) — [ArkStream on X](https://x.com/ark_stream/status/1977655268810142182) [UNVERIFIED]
- BTC top-of-book depth fell >90% on key venues; spreads from single-digit bps to double-digit % — [FTI Consulting](https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity) (via repo)
- Bybit: ~400,000 ETH (~$1.4B) stolen 21 Feb 2025; 99.994% of 350,000+ withdrawals processed within 10h; solvent; Hacken PoR later >100% — [Bybit timeline](https://www.bybit.com/en/learn/this-week-in-bybit/bybit-security-incident-timeline); [CNBC](https://www.cnbc.com/2025/02/24/bybit-replenished-reserves-after-record-breaking-1point5-billion-hack.html)
- OKX `50004` unknown-result timeouts at funding timestamps; Binance `-1008 Server busy` — [OKX API FAQ](https://www.okx.com/help/api-faq) (via repo)
- Ethena reserve fund ~$61M vs $5.6B supply (Mar 2026), "not a guarantee" against negative funding — [EarnPark](https://earnpark.com/en/posts/ethena-fees-apy-interest-rates-explained-2026/) [UNVERIFIED]
- Feb 5–6 2026: BTC −12.6% day, CME basis unwind, futures OI −20% in a week, VanEck −6.05σ rate-of-change — [Convex Dispatch](https://convexdispatch.substack.com/p/the-day-liquidity-died-the-february); [VanEck](https://www.vaneck.com/us/en/blogs/digital-assets/matthew-sigel-what-triggered-bitcoins-major-selloff-in-february-2026/) (via repo)
- "Could October 2025 repeat?" retrospective published 10 Oct 2026 — [The Coin Republic](https://www.thecoinrepublic.com/2026/10/10/19b-crypto-liquidation-crash-could-october-2025-repeat/) [UNVERIFIED]

### Inferences
- For a carry book the Oct-10 lesson is specific: the short-perp leg can be ADL'd (closing the hedge at a price far from spot) or the venue can mark your collateral (USDe, wBETH, BNSOL) wrongly and liquidate you while reduce-only orders are rejected. "Delta-neutral" survived at Ethena scale (per Ethena) but not for the Wintermute altcoin book or for retail accounts on Binance.
- Venue failure (Bybit) resolved well in 2025, but a cross-venue arb would have had one leg frozen for most of a day; the Springer paper's finding that counterparty episodes dominate directional crashes matches this.

### Gaps
- No documented list of API outages during volatility in 2025–2026 beyond Oct 10 (Binance/dYdX) and the standing OKX funding-time warning; the Binance-outage search returned only Bybit-hack results.
- No stablecoin depeg in 2024–2026 other than the Binance-local USDe event was surfaced.

## Overall assessment (for the report writer)

- Delta-neutral yield on BTC/ETH majors is real but has been arbitraged to roughly the risk-free rate on the deepest venues since early 2025 (CME basis 4–5% vs 4.5% risk-free; Binance funding at the 0.01% floor 78% of Q3 2025; negative for most of Mar–May 2026; basis 1.5% in May 2026; sUSDe ~4.8% in Sep 2026). 2024-style 15–35% was a one-off ETF-entry regime.
- For a small India-based trader on Delta India: an on-venue spot-vs-perp carry is mechanically possible (spot since ~Apr 2026), fee-cheap on the perp leg (2.12 bps maker) but burdened by a 10 bps spot seller fee, 1% TDS, a 30% flat tax regime whose treatment of perp losses is unresolved, no dated futures to lock basis, and no record of Delta's funding history. Expected gross carry at 2026 funding levels is low single digits; after costs and tax it is plausibly zero or negative in flip regimes.
- Cross-venue funding arb from India is blocked in practice by AD banks refusing LRS for crypto and by Schedule III's bar on margin to overseas exchanges; it is also the strategy with the worst documented tail (Oct 10 ADL, venue freezes).
- Funding as a directional signal: weak (R² ~12.5% at 7 days, fading), anecdotal at extremes, no post-2023 after-cost event study found, and almost no variance on majors while the rate is pinned at the floor.
- Prop accounts cannot host any of the market-neutral variants and several firms ban "arbitrage" by name.
- The [UNVERIFIED] tags above are concentrated on the most quantitative claims (BitMEX Q3 2025 stats, BIS 97%, arXiv ADL dollar figures, Ethena yields) because the source pages could not be fetched from this environment; they should be re-checked against the primary pages before being quoted in a final report.
