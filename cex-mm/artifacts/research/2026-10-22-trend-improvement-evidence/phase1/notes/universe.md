# Angle: UNIVERSE AND DIVERSIFICATION — research notes (2026-10-20/21)

Role: quant researcher, read-only. Nothing in the repo modified, no orders. Web budget ran out after 13 searches
(shared 200-search cap for this turn), so later facts come from the Delta API, data.binance.vision, raw GitHub and
local caches. Every claim I could not open is tagged [UNVERIFIED] with its URL. Numbers I computed are [COMPUTED]
with the script path.

Scratch files (all under /tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research2/):
- data/products.json, products2.json, tickers.json — Delta `/v2/products` (two pages, 1138 products) and `/v2/tickers`, 2026-10-20 02:59 UTC
- data/delta_perps.csv — 237 live USD perps with contract_value, tick, launch, $/contract, 24h turnover_usd, OI, funding
- data/binance_first_month.csv — first Binance USDT-M monthly 1d kline per Delta underlying (HEAD binary search, tools/binance_first_month.py)
- data/candidate_universe.csv — join of the two, turnover-ranked, `eligible` = Delta age >= 121 d AND Binance history
- data/corr_effn.txt — pairwise correlations / effective bets (tools/corr_effn.py on ../av_cache)
- data/exante_top15.txt — ex-ante Jan-1 top-15 lists 2021-26 and whole-contract feasibility (tools/exante_top15.py)
- data/delta_noncrypto_funding.json — Delta funding + candles for XAUT/PAXG/QQQX/SPYX/SLVON/BTC/SOL/ZEC since 2025-10
- data/delta_daily_turnover_400d.json — 400 d of Delta daily volume for the 84 eligible perps with turnover >= $200k
- dl/paxg_spot/ — Binance spot PAXGUSDT monthly 1d zips 2020-08..2026-09 (gold proxy)

A sibling step of this workflow had already built ../universe/ (fetch_universe.py, cache/ with 10,890 monthly files for
181 Binance-listed Delta underlyings, binance_first_month.json). My independent HEAD probe agrees with it on every
symbol except HUSDT (mine 2025-06, sibling 2025-07; immaterial). NOTE the sibling's `listed()` keeps only symbols with a
2026-08/09 file, i.e. it conditions on survival to today; see Fact F6.

---------------------------------------------------------------------------------------------------------------------
## 1. Literature (what it says about breadth, correlation and universe selection)

### 1.1 Sharpe vs number of instruments / effective bets
- Carver, "I got more than 99 instruments..." (2023) https://qoppac.blogspot.com/2023/03/i-got-more-than-99-instruments-in-my.html
  [UNVERIFIED, search snippet]: across 102 futures the average pairwise correlation is 0.224, "effective number of
  independent bets 4.3"; realised Sharpe only doubles vs one instrument, "equivalent to 4 independent bets".
- Carver rule-of-thumb table (blog reproduction of book table 18, correlation 0.25) [UNVERIFIED]:
  SR 0.35 for 1 instrument, 0.54 for 4, 0.61 for 8 (one per asset class), 0.70 for all 37.
  https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html
- Carver, "Diversification and small account size" (2016) [UNVERIFIED]: with few contracts you cannot hold many
  instruments; advice = hold >= 4 contracts at max forecast; in his example only two instruments fit; he then tests
  1..8, 15, 20, 25, 37 instruments. Secondary summaries put the "minimum to capture diversification" near $100k
  [UNVERIFIED, secondary]. Directly relevant: our $1,000 book (Fact F7).
- AQR / Baltas-Kosowski "Trends Everywhere" [UNVERIFIED]: 12-month TSMOM gross Sharpe 1.17 (traditional assets),
  1.34 (alternatives), 1.60 combined across all groups — the gain comes from adding *uncorrelated groups*, not more
  names in one group. https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf
- Baltas & Kosowski (2012) "Momentum strategies in futures markets and trend-following funds" [UNVERIFIED]:
  71 contracts, strategy Sharpe > 1.2; commodity TSMOM has low correlation to other groups.
  https://www.efmaefm.org/0efmameetings/efma%20annual%20meetings/2012-Barcelona/papers/BK_MOMF_Full.pdf
- Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing" (JPM 2017) [UNVERIFIED]: 67 markets
  1880-2016, positive in every market, average net Sharpe ~0.4; the diversified portfolio is what makes it ~1.
  https://www.pm-research.com/content/iijpormgmt/44/1/15
- Man Institute, "The Optimal Market Mix for a Trend Follower" [UNVERIFIED, landing page only]: alternative markets
  improve Sharpe because of "more idiosyncratic price drivers"; no universal mix.
  https://www.man.com/insights/trend-following-optimal-market-mix
- Etienne, Ohana, Benhamou et al., arXiv 2510.23150 "Revisiting the Structure of Trend Premia: When Diversification
  Hides Redundancy" (Oct 2025) [UNVERIFIED]: about *horizon* redundancy (the ~125-day layer adds nothing once short
  and long layers exist). Tangential to universe; noted because our 20/60/120 stack has the same structure.
  https://arxiv.org/abs/2510.23150
- Mechanics used below: with N instruments at average pairwise correlation rho, equal-risk weights give
  N_eff = N / (1 + (N-1) rho) and Sharpe multiplier sqrt(N_eff) vs a single instrument (Carver / Meucci effective bets).

### 1.2 Crypto-specific trend / universe evidence
- Man Group (AHL), "In Crypto We Trend" (Dec 2024) https://www.man.com/insights/in-crypto-we-trend [UNVERIFIED]:
  "with limited diversification between coins ... peak risk-adjusted returns in a trend-following crypto portfolio
  occur with around 10-15 coins"; beyond that "transaction costs and liquidity constraints outweigh diversification
  benefits". No Sharpe table seen. Secondary: QuantSeeker note https://substack.com/@quantseeker/note/c-82199199
- Zarattini, Pagani, Barbon, "Catching Crypto Trends; A Tactical Approach for Bitcoin and Altcoins" (SSRN 5209907,
  2025) [UNVERIFIED]: Donchian ensemble (several lookbacks), vol-based sizing (25% vol target, 200% cap per
  third-party transcription), "rotational portfolio of the top 20 most liquid coins", "survivorship bias-free
  dataset ... since 2015", Sharpe > 1.5, alpha 10.8%/yr vs BTC; Concretum summary: monthly rotation 18% CAGR net,
  max DD -11% [UNVERIFIED, vendor]. Selection mechanics (how "most liquid" is measured, rebalance of the list)
  not visible. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 ;
  https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/
- Ammann, Burdorf, Liebi, Stöckl, "Survivorship and Delisting Bias in Cryptocurrency Markets" (SSRN 4287573, 2022)
  [UNVERIFIED]: 3,904 coins 2014-2021; annualized survivorship+delisting bias 0.93% (value-weighted) and 62.19%
  (equal-weighted); size premium overestimated ~50% in the survival-conditioned sample; no positive relation between
  returns and one-week momentum once delistings are handled. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4287573
  Takeaway for us: equal-weight (our TV/N is close to equal-risk) universes are where the bias bites; the Phase-2
  universe backtest must include delisted perps.
- AUT, "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market" [UNVERIFIED]: "strong evidence of
  time-series momentum"; sample includes inactive coins; liquidity filters tested: 30-day MA market cap >= $1M,
  30-day MA volume >= $1M, or both; warns that market cap alone is an incomplete liquidity filter.
  https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
- Liu, Tsyvinski, Wu, "Common Risk Factors in Cryptocurrency" (NBER w25882) [UNVERIFIED]: universe = coins with
  market cap > $1M at the prior week end, ex stablecoins, ~1,700 coins. https://www.nber.org/system/files/working_papers/w25882/w25882.pdf
- "Cryptocurrency momentum has (not) its moments" [UNVERIFIED]: restricts to top-30 by market cap "to control for
  liquidity". https://www.researchgate.net/publication/380467146_Cryptocurrency_momentum_has_not_its_moments
- arXiv 2009.12155 "A Decade of Evidence of Trend Following Investing in Cryptocurrencies" [UNVERIFIED]: 2011-2019,
  SMA/EMA/DEMA crossovers best Sharpe 1.09/1.35/1.32, *no costs*. https://pith.science/paper/2009.12155
- Owusuk/crypto-stat-arb README (VERIFIED via raw.githubusercontent.com): V2 universe = "Top 40 by market cap on
  2021-01-03 (ex stablecoins / wrapped); 39 with data", "Failures (FTT, EOS, MKR exits) included"; V1 had used the 16
  survivors (the bias V2 removes). Momentum book hold-out Sharpe 0.30 at 20 bps; combined book hold-out Sharpe 0.20,
  max DD -26.7%, alpha t = 0.52. Snapshot, not rolling point-in-time. https://github.com/Owusuk/crypto-stat-arb
- Platanakis, Sutcliffe, Urquhart (2018) "Optimal vs naive diversification in cryptocurrencies" [UNVERIFIED]: 4 coins,
  weekly; naive ~ optimal. Not informative on the plateau. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3209573
- Correlation facts from secondary sources: CoinDesk (Sep 2023) top-25 tokens, two years of daily returns, average
  correlation to BTC 0.40 [UNVERIFIED]; 21Shares Q1 2025 (10/20-day windows) BTC 36%, ETH 38% vs rest [UNVERIFIED];
  retail guides quote 0.60-0.80 for major alts vs BTC, "converge toward 1 in selloffs" [UNVERIFIED]. My own numbers
  (F3) are higher (0.55-0.76 pairwise among large caps) and are the ones to use.
- Point-in-time universe practice (blogs, [UNVERIFIED, vendor]): gimmer "Rebuild the Point-in-Time Universe"
  https://blog.gimmer.com/2026/09/01/crypto-backtest-survivorship-bias-point-in-time-universe/ ; Concretum
  "survivorship-bias-free dataset with CoinMarketCap API" https://concretumgroup.com/building-a-survivorship-bias-free-crypto-dataset-with-coinmarketcap-api/ ;
  Vantixs claims survivorship inflates returns 15-40% [UNVERIFIED, no primary].

### 1.3 New-listing effect (why a listing-age floor)
All [UNVERIFIED], industry/press, mixed windows and benchmarks:
- Empirica "The Binance Effect" (7-year analysis): 2024 Binance listings fell 6.34% in week 1, trailed ETH by 31.2%
  cumulatively; 6-month absolute average +8%. https://empirica.io/blog/the-binance-effect-a-7-year-analysis-for-token-founders/
- Delphi Consulting via cryptorank: 652 listings since Jan 2025, 12% profitable, median return -82%.
  https://cryptorank.io/news/feed/e1b0f-new-crypto-listings-losses-2025-report
- Bitget/Dune: 89% of 2025 Binance listings negative, 11.1% positive. https://www.bitget.com/news/detail/12560604680760
- PANews/ChainCatcher: primary (TGE) listings underperform, secondary listings do better.
  https://panews.io/articles/1b09cf81-e875-4188-8f45-4171d5c51f4d
Mechanism for a long-only trend rule: the 20-day sign is positive during the listing pump, so with only 121 closes
the rule can buy the first post-listing high; the 60/120-day legs do not exist yet to veto it. A 365-close floor
is the cheap fix; it costs nothing on the current 9 (all > 2,000 Binance closes).

---------------------------------------------------------------------------------------------------------------------
## 2. Facts (verified by me unless marked)

### F1. Delta India live USD perpetuals (2026-10-20 02:59 UTC, `/v2/products` + `/v2/tickers`) [VERIFIED]
- 237 live perpetual_futures, all quoted and settled in USD. 24h turnover total $2.99B; top-25 = 98.3% of it.
- Turnover >= $5M: 17 perps; >= $2M: 28; >= $1M: 42. Launched >= 121 days ago (<= 2026-06-21): 193.
- Non-crypto perps now on Delta (tags): metal = XAUTUSD (launched 2026-04-17, $695M/24h, OI $108M, 0.001 oz ~ $4.1),
  PAXGUSD (2026-02-19, $134M), SLVONUSD (silver, 2026-02-26, $7.9M), OILUSD (2026-09-30, $3.0M); xStock = 37
  tokenized equities/ETFs incl. QQQXUSD (2026-04-07, $2.2M, OI $2.6M), SPYXUSD (2026-04-07, $0.44M), TSLAX, NVDAX...;
  KORUBUSD (2026-10-13). Maker fee 0.02% / taker 0.05% before GST on every perp checked.
- Top-45 by 24h turnover with Delta launch and Binance first month (data/candidate_universe.csv), crypto only,
  eligible = launch <= 2026-06-21 AND Binance USDT-M history:
  BTC(2020-01) ETH(2020-01) SOL(2020-09) ZEC(2020-02) XRP(2020-01) UNI(2020-09) AAVE(2020-10) ARC(2025-01)
  ALT(2024-01) DOGE(2020-07) BMT(2025-03) AVAX(2020-09) BNB(2020-02) LTC(2020-01) SIREN(2025-03) WLD(2023-07)
  LINK(2020-01) DOT(2020-08) BCH(2020-01) VVV(2025-01) BLESS(2025-09) NEAR(2020-10) TRX(2020-01) M(2025-07)
  TIA(2023-10) AIOT(2025-04) ADA(2020-01) STRK(2024-02) AIN(2025-07) XMR(2020-02) FIL(2020-10) SOPH(2025-05) ...
  Not eligible today (age < 121 d): BR, AKE, GTC, BTW, KORUB, OIL, MRNAB, QNT; or no Binance perp: all xStocks,
  SLVON, OIL.
- Eligible crypto perps: 180 (28 with turnover >= $1M, 36 >= $0.5M, 50 >= $0.25M). With Binance history back to
  2020-05 (full-sample backtest possible): BTC ETH ZEC XRP BNB LTC LINK BCH TRX ADA XMR ETC DASH XLM IOTA (15).
  With history to 2021-12: 41.

### F2. Binance public archive coverage [VERIFIED by HEAD probes on data.binance.vision]
- First monthly 1d file per Delta underlying is in data/binance_first_month.csv (197 of 237 have a Binance USDT-M
  perp; 40 do not: xStocks, SLVON, OIL, KORUB and a few small alts).
- Delisted perps REMAIN in the archive: FTTUSDT 2022-10, LUNAUSDT 2022-04, SRMUSDT 2022-12, BTCSTUSDT 2022-01,
  TOMOUSDT 2023-06 all return HTTP 200; EOSUSDT files end 2025-05 (404 for 2025-06). So a true point-in-time
  Binance universe is buildable from public data; the open problem is enumerating the historical symbol list (the
  `?prefix=` listing is a JS page, the S3 XML endpoint was not tested, fapi.binance.com is DNS-blocked here).
- Gold proxy: Binance SPOT PAXGUSDT 1d exists from 2020-08 (2020-07 404); Binance futures PAXGUSDT from 2025-03,
  XAUTUSDT from 2026-03. No Binance equity-index proxy.

### F3. Correlation and effective number of bets [COMPUTED, tools/corr_effn.py on ../av_cache, Binance 1d closes]
Average pairwise correlation rho of daily log returns, N_eff = N/(1+(N-1)rho), sqrt(N_eff) = Sharpe multiplier
vs one coin:
  window        set     N   rho   N_eff  sqrtNeff
  2020          nine    9   0.59  1.57   1.25      all25 25 0.63 1.55 1.25
  2021          nine    9   0.60  1.56   1.25      all25 25 0.64 1.53 1.24
  2022          nine    9   0.76  1.27   1.13      all25 25 0.75 1.32 1.15
  2023          nine    9   0.57  1.62   1.27      all25 25 0.60 1.63 1.28
  2024          nine    9   0.58  1.59   1.26      all25 25 0.60 1.63 1.28
  2025          nine    9   0.72  1.33   1.15      all25 25 0.67 1.47 1.21
  2026 (Jan-Sep) nine   9   0.76  1.27   1.13      all25 24 0.55 1.77 1.33
  2020-08..26   nine    9   0.62  1.50   1.23      all25 25 0.64 1.53 1.24
=> Going from 9 to 25 large-cap crypto perps adds essentially nothing in effective bets (1.50 -> 1.53). The whole
   crypto block is ~1.5 independent bets; correlation rises to ~0.75 in bear years (2022, 2026). This is the
   quantitative reason the ex-ante 24-coin universe does not beat the 9 (av_universe_9: 0.86/0.82 vs 1.25/1.12):
   adding names adds no diversification and adds weaker trends.
Correlation of each coin with the EW nine basket, 2022-01..2026-09 (ann. vol): TRX 0.47 (58%), XMR 0.53 (73%),
ZEC 0.60 (107%), IOST 0.66, DASH 0.66, ONT 0.71, XLM 0.74, NEO/XTZ/BCH 0.78, ATOM/QTUM 0.79, EOS/BAT/BNB/XRP 0.80,
IOTA 0.81, ETC/VET/LTC 0.84, DOGE 0.85, LINK 0.86, BTC 0.87, ADA 0.88, ETH 0.89.

### F4. Gold (PAXG spot proxy) vs crypto [COMPUTED, dl/paxg_spot + av_cache]
  year  corr(PAXG,BTC)  corr(PAXG,EW9)  PAXG vol  PAXG ret
  2020      0.29           0.16           17%       -2%  (Aug-Dec)
  2021      0.06           0.14           15%       -5%
  2022      0.11           0.08           16%       -2%
  2023      0.14           0.12           13%      +11%
  2024      0.14           0.12           16%      +30%
  2025      0.07           0.05           20%      +65%
  2026      0.42           0.41           31%       -4%  (Jan-Sep)
  all       0.15           0.14           19%     +108%  (2,217 days)
Adding one asset at rho 0.14 to nine at 0.62: average pairwise rho = (36*0.62 + 9*0.14)/45 = 0.524,
N_eff = 10/(1+9*0.524) = 1.75 vs 1.50 -> sqrt ratio 1.08. Gold is worth more effective bets than 16 extra alts.
The repo's 20/60/120 sign rule on PAXG, long/flat, unit notional, no costs: long 64% of days, cumulative log-return
+0.68 vs buy-and-hold +0.77 over 2020-12-27..2026-09-30 (illustrative only; 2025's +65% dominates).

### F5. Delta funding paid by longs, 2025-10-01..2026-10-20 (hourly FUNDING candles, % per 8 h) [VERIFIED, API]
  XAUTUSD  mean +0.0050%/8h = +5.5%/yr of notional, 100% of samples > 0, 0% at the 0.01% cap (187 closes since 2026-04-17)
  PAXGUSD  +0.0046% = +5.0%/yr, 97% > 0, 1% at cap (244 closes since 2026-02-19)
  QQQXUSD  +0.0100% = +10.9%/yr, 100% at cap (197 closes)      SPYXUSD identical +10.9%/yr, 100% at cap
  SLVONUSD +0.0102% = +11.2%/yr, 100% at cap
  BTCUSD   +0.0079% = +8.6%/yr, 66% at cap        SOLUSD +0.0093% = +10.2%/yr, 99% at cap
  ZECUSD   -0.0033% = -3.6%/yr (longs are PAID), 57% > 0, 81% at either cap
=> Tokenized equity/ETF perps are pinned at the cap: a long pays ~11%/yr, which is the whole equity premium; they are
   not usable for a long-only trend book. Gold perps cost 5-5.5%/yr, about 1/3 of gold's 2020-26 drift, and the rate
   has never been at the cap. (Resource 07 already records BTC 8.9%, ETH 9.2%, BNB 13.5%/yr on Delta.)

### F6. Ex-ante Jan-1 top-15 by trailing 30-day median Binance quote volume, >= 121 closes [COMPUTED,
tools/exante_top15.py over av_cache + trend-cache + ../universe/cache = 206 symbols]
  2021: BTC ETH XRP LTC LINK BCH ADA XLM EOS BNB DOT ETC TRX VET XMR
  2022: BTC ETH SOL 1000SHIB AVAX MANA NEAR XRP DOT BNB ADA DOGE LINK LTC SUSHI   (7 of 15 changed)
  2023: BTC ETH DOGE BNB XRP LTC LINK MASK SOL ADA AXS ETC DYDX EOS DOT             (5 changed)
  2024: BTC ETH SOL AVAX XRP ADA DOGE OP BNB LINK TRB ARB INJ DOT SEI               (6 changed)
  2025: BTC ETH XRP SOL DOGE 1000PEPE SUI BNB ADA LINK WIF HBAR ENA AVAX AAVE       (6 changed)
  2026: BTC ETH SOL ZEC XRP DOGE BNB PIPPIN SUI 1000PEPE HYPE ADA AVAX BCH LINK     (4 changed)
CAVEAT: the caches hold only today's Delta names plus the 25-coin set; Binance perps delisted before 2026 are
absent, so these lists are survivorship-tilted (FTT would have been top-15 in 2022, LUNA in 2022, etc.). Still, a
yearly reset changes 4-7 of 15 names; the top-5 is stable. On Delta itself (400 d of daily volume, 84 perps) the
quarterly top-15 changes 5-7 names per quarter (data/delta_daily_turnover_400d.json), driven by new listings
(RIVER, LAB, SKYAI, SIREN) that spike and fade — exactly the names a 365-close floor removes.

### F7. Whole-contract feasibility at small capital [COMPUTED, current prices and 60-day vols to 2026-09-30]
Position when fully long = capital * (TV/N) / max(vol60, 0.05); coins whose position < 0.5 contract round to zero:
  $1,000 daily TV0.40:  N=9 -> ZEC AAVE (2);  N=15 -> SOL ZEC AAVE (3);  N=20 -> same 3
  $1,000 weekly TV0.25: N=9 -> SOL ZEC AAVE (3);  N=15 -> BTC SOL ZEC AAVE (4);  N=20 -> BTC SOL ZEC AAVE BNB (5)
  $5,000 daily TV0.40:  none round to zero at N=9/15/20
  $5,000 weekly TV0.25: N=15 -> ZEC;  N=20 -> ZEC AAVE
(Contract notionals today: BTC $82.7, SOL $106, ZEC $127, AAVE $156, BNB $74, ETH $24, LINK $12, DOGE $8, LTC $6,
BCH $2.9, XRP $1.3, ADA $0.22, XAUT $4.1.) Carver's point stands: at $1,000 the universe cannot grow; at $5,000
N=15 is implementable.

---------------------------------------------------------------------------------------------------------------------
## 3. Candidates (exact rules). Status of each: not backtested; Phase 2 must run them pre-registered.

C1. Ex-ante turnover-ranked universe, listing-age floor, yearly reset ("Top-N/121/yearly")
  Rule: at the first rebalance of each calendar year (daily book 1 Jan 00:05 UTC; weekly book first Monday), set
  U = the N=12 Delta USD perps with tags not in {metal, xStock}, underlying not a stablecoin, ranked by the median
  daily USD turnover over the prior 30 calendar days (Delta 1d candle volume x contract_value x close; before
  2024-04 use Binance USDT-M quote volume, col 8 of the 1d kline), requiring >= 121 daily closes and median turnover
  >= $1M. Hold U fixed until the next reset; a coin delisted mid-year goes flat and is not replaced; everything else
  (signal, vol, TV/N with N = |U|, caps, band) unchanged.
  Evidence: av_universe_9.txt (all 24 perps listed by 2020-02-20: daily Sharpe 0.86, weekly 0.82 vs 1.25/1.12 for
  the hindsight nine; the 16 unchosen names 0.62); Man 10-15 coins [UNVERIFIED]; Zarattini top-20 liquid
  [UNVERIFIED]; Ammann et al. EW bias 62%/yr [UNVERIFIED]; F3 (N_eff flat 1.50->1.53); F6 (4-7 names change per
  yearly reset). Honest expectation: Sharpe at or below the 9-coin figure (0.8-0.9 on Binance 2020-26); the gain is
  a reproducible, hindsight-free rule that would have picked SOL/AVAX/DOGE/SUI when they were liquid, not a Sharpe
  uplift. Plausibility 4 (as a robustness measure), 2 (as a performance measure).

C2. Add gold as the tenth instrument (XAUTUSD; PAXGUSD if XAUT turnover < $10M/day)
  Rule: U = current nine + XAUTUSD, same 20/60/120 sign signal floored at 0, same weight sig*(TV/N)/max(vol60,0.05)
  with N=10, same gross cap; optional cap w_gold <= 0.25 of equity. Costs: taker 5.31 + 2 bps; funding 5.5%/yr of
  notional while long (F5, assume constant). Backtest price series: Binance spot PAXGUSDT 1d from 2020-08 (public),
  stitched to Delta XAUTUSD from 2026-04-17.
  Evidence: F4 (rho 0.14 to the crypto basket, stable 0.06-0.16 in five of seven years; N_eff 1.50 -> 1.75);
  AQR "Trends Everywhere" cross-group gain 1.17/1.34 -> 1.60 [UNVERIFIED]; Hurst-Ooi-Pedersen all 67 markets
  positive [UNVERIFIED]; Man "optimal market mix" (idiosyncratic drivers) [UNVERIFIED]. Risks: only 187 Delta closes;
  gold's 2025 +65% is in-sample and the obvious reason this looks good now; 5.5%/yr carry vs ~12%/yr gold drift
  2020-26; 2021-22 would have paid funding for flat gold. Contract $4.1 -> no rounding problem at $1,000.
  Plausibility 4.
  Do NOT add QQQX/SPYX/SLVON: funding pinned at the 0.01%/8h cap = 10.9-11.2%/yr paid by longs (F5).

C3. Listing-age floor of 365 closes for any coin not in the original nine
  Rule: a coin may enter U at a reset only if it has >= 365 daily closes on Binance USDT-M or Delta (whichever is
  longer) by the reset date; the signal still needs only 121. Evidence: new-listing underperformance (Empirica -31%
  vs market for 2024 Binance listings; Delphi 652 listings since 2025 median -82%, 12% profitable; Bitget/Dune 11%
  positive) all [UNVERIFIED]; F6 shows 2025-26 Delta turnover leaders RIVER/LAB/SKYAI/SIREN/ARIA/AKE are 2-9 month
  listings. Mechanism: pump at listing makes the 20-day sign positive before the 60/120 legs exist. Cost: zero on
  the current nine. Plausibility 3 (mechanism clear, evidence is press/vendor, 1 parameter).

C4. Liquidity floor with hysteresis (entry $2M, exit $0.5M)
  Rule: entry at a reset requires 30-day median daily Delta turnover >= $2M; a held coin goes flat (not replaced)
  when its 30-day median < $0.5M at a weekly rebalance, re-entering only at the next yearly reset. Formalises
  resource 07's *(start)* "$0.5M for 30 consecutive days". Evidence: AUT paper's $1M 30-day volume filter
  [UNVERIFIED]; index-provider buffer-zone practice; F1 (28 crypto perps >= $1M today, ~17 >= $5M; BCH ~$1.4M is near
  the floor). Effect is on slippage/cost, not Sharpe. Plausibility 3.

C5. Capital-aware universe size
  Rule: N = 9 while capital < $2,500; N = 12 at $2,500-5,000; N = 15 at >= $5,000; a coin is eligible only if its
  fully-long position (capital*(TV/N)/max(vol60,0.05)) is >= 2 contracts at the reset. Evidence: F7 (at $1,000 weekly
  TV0.25 N=15 BTC/SOL/ZEC/AAVE round to zero); Carver 2016 [UNVERIFIED]. Plausibility 4 as an arithmetic constraint;
  note that the >= 2 contracts test would drop BTC from the $1,000 weekly book, which the design must not do
  (BTC-only weekly Sharpe 0.85 is the single best coin, T3f), so apply it to *added* coins only.

C6. Correlation-aware selection (one name per cluster, "handcrafting")
  Rule: at a reset, start with BTC and ETH; from the top-30 by turnover (>= 365 closes) add coins in turnover order,
  skipping any whose 120-day daily-return correlation with an already-chosen coin exceeds 0.80, until N=12.
  Evidence: F3 (within-crypto rho 0.55-0.76; lowest-correlation large caps TRX 0.47, XMR 0.53, ZEC 0.60 but with
  58-107% vol and delisting/privacy risk); Carver handcrafting / Meucci effective bets [UNVERIFIED]. Expected N_eff
  gain small (<= 1.8) and noisy; adds a threshold parameter. Plausibility 2.

C7. Funding-cost eligibility filter (cost filter, not a signal)
  Rule: at a reset exclude a coin whose trailing 90-day mean Delta funding paid by longs exceeds 12%/yr of notional
  (0.011%/8h); never changes direction or size, only membership. Evidence: F5 (SOL 10.2%/yr at cap 99% of the time;
  BNB 13.5%/yr per resource 07; ZEC -3.6%/yr), memo: funding is the real running cost (2-3.4%/yr of equity at
  Binance rates, Delta 1.8-17x higher on majors). Overlap: "funding as directional signal" and "funding carry" were
  rejected; this is neither — it is an expected-cost screen. Risk: would have excluded BNB and SOL in strong 2024-25
  trends; the net effect is unknown. Plausibility 3.

C8. Data requirement for every universe backtest (Phase 2): survivorship-free Binance perp list
  Rule: the point-in-time universe at each reset must be drawn from every Binance USDT-M perp with a 1d file in that
  month, including later-delisted symbols (FTT, LUNA, SRM, BTCST, TOMO, EOS verified present), not from today's
  Delta list; funding from the matching fundingRate files. Enumeration: HEAD-probe a superset symbol list (all
  symbols that ever appear in the data.binance.vision bucket; the S3 XML listing or a GitHub mirror of exchangeInfo
  history is needed — unresolved here). The sibling's ../universe/cache conditions on survival to 2026-08/09 and must
  not be used alone for the ex-ante test. Plausibility 5 (correctness).

---------------------------------------------------------------------------------------------------------------------
## 4. What this angle says in one paragraph
Within crypto, breadth is not a lever: nine large caps are ~1.5 independent bets and 25 are ~1.5 as well (F3), which
is why the honest ex-ante 24-coin universe tests *worse* (0.86/0.82) than the hindsight nine and why Man's "10-15
coins" optimum is a cost statement, not a diversification statement. The only universe change with a real
diversification mechanism available on Delta India is gold (XAUT/PAXG, rho 0.14, N_eff 1.50 -> 1.75) at a 5-5.5%/yr
funding cost; tokenized equities are priced out by cap-pinned funding (10.9%/yr). Everything else in this angle
(turnover ranking, 121/365-close floor, liquidity hysteresis, yearly reset, capital-aware N) is about making the
universe reproducible and cheap rather than raising Sharpe, and at $1,000 whole contracts cap N at about 9 anyway.
Not opened (blocked): every paper and blog above except the Owusuk README; the Delta API, data.binance.vision probes
and all [COMPUTED] numbers are first-hand.
