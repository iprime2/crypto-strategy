# Literature: previous-period highs and lows as trading levels (for the PWH/PWL study)

Written 2026-10-22 for the frozen plan `research3/plan.md` (sha256 8c7bf923...f19a, checked to match `plan_sha256.txt` before starting). This file reviews prior work. It does not change the plan and has no effect on any pass rule.

## How the sources were read (this limits every tag below)
- The agent proxy refused every academic and blog host tried. The refused hosts were newyorkfed.org, resources.newyorkfed.org, ssrn, arxiv (including web3/ar5iv mirrors), researchgate, wiley, sciencedirect, repec/ideas/econpapers, fedinprint, brandeis, georgetown, lse, wharton, bauer.uh.edu, kevinsheppard.com, technicalanalysis.org.uk, substack, tradingview, quantifiedstrategies, wikipedia and instagram. WebFetch failed on the same hosts with DNS errors. The only reachable hosts were github.com (through WebFetch) and raw.githubusercontent.com.
- So every academic paper below is **[UNVERIFIED]**. Its claims come from search-engine result summaries and snippets. Where a number appeared consistently across separate searches, the entry says so. Where only one snippet gave it, the entry says that too.
- **[VERIFIED]** is used only for pages I read myself: GitHub pages fetched with WebFetch (the page text goes through a model extractor, so quotes are as returned) and files in this repository.
- A secondary transcription that I read, such as a GitHub PR that quotes a paper's table, is still tagged [UNVERIFIED] for the paper's numbers. I did not see the paper.

---

## 1. The claim under test
**Quantlab reel, NASDAQ previous-week high/low.** https://www.instagram.com/reel/Dd8vV7ZMbPs/ **[UNVERIFIED]**: transcript supplied by the user; instagram.com is blocked.
- **Claims:**
  - Price reached at least one previous-week level in 91.9 % of weeks, and the PWH in 64.2 %.
  - Price "rejected" within 60 min of a PWH touch 40.4 % of the time.
  - After a confirmed breakout, price continued 78.9 % of the time, against 77.6 % at control levels "at a similar distance from the market".
  - Conclusion: the level carries no special edge.
- **Not stated:** sample period, bar size, what counts as "confirmed", what counts as "continued", the number of events, and costs.
- **Account:** not identified. Four searches ("Quantlab" + previous week high, + the reel's percentages, + Instagram quant reels) returned nothing matching. One search surfaced "M3 Quant Lab" (@m3quantlab, Patreon) as a similarly named account, but nothing links it to this reel. Do not attribute the reel to it.

## 2. Support/resistance and order clustering (FX: the mechanism literature)

**Osler (2000), "Support for Resistance: Technical Analysis and Intraday Exchange Rates", FRBNY Economic Policy Review 6(2), 53–68.** https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf **[UNVERIFIED]**
- **Claim:** S/R levels published by FX firms predict intraday trend interruptions ("bounces") better than artificial levels.
- **Numbers (found in several separate searches):**
  - Rates bounced off published levels 60.8 % of the time and off artificial levels 56.2 % (difference 4.6 pp).
  - Published levels beat artificial levels in all 16 firm-currency pairs, significant at 5 % in all but three.
  - Advantage by currency: about 4.2 pp for DEM, 5.6 pp for JPY and 4.0 pp for GBP.
  - Predictive power lasts at least five business days; bounce rates five days after publication were 1.7 pp lower than on the publication day.
  - Published levels end in 0 or 5 far more often than chance.
- **Sample:** levels published daily by six firms, Jan 1996 – Mar 1998, for DEM, JPY and GBP against USD; one-minute indicative quotes, 09:00–16:00 New York time.
- **Control:** the artificial levels were reportedly drawn near the day's opening rate, which is close in spirit to our P1. A single snippet says the edge was smaller in high-volatility periods; that was not confirmed.

**Osler (2003), "Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis", Journal of Finance 58(5), 1791–1819** (working paper: FRBNY Staff Report 125). https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf **[UNVERIFIED]**
- **Claim:** order clustering explains two technical-analysis predictions.
  - Take-profit orders cluster *at* round numbers, so trends tend to reverse there.
  - Stop-loss orders cluster *just beyond* round numbers (stop-buys just above 00/50, stop-sells just below), so trends accelerate after crossing.
  - Reversals at round numbers are short-lived: "behavior is once again indistinguishable from average within an hour in most cases."
- **Numbers (working-paper version, snippet):** almost 10 % of orders at rates ending in 00, against about 3 % at each other rate ending in 0.
- **Sample:** stop-loss and take-profit orders at one large dealing bank, 1 Aug 1999 – 11 Apr 2000, for USD/JPY, GBP/USD and EUR/USD.
  - Total amount: "in excess of $55 billion" (snippet cut off).
  - About 9,700 orders (one secondary snippet).

**Osler (2005), "Stop-loss orders and price cascades in currency markets", Journal of International Money and Finance 24(2), 219–241** (FRBNY Staff Report 150, 2002). https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf **[UNVERIFIED]**
- **Claim:**
  - Trends are unusually rapid when rates reach levels where stop-loss orders are documented to cluster. Stop-losses propagate trends and are sometimes triggered in waves ("price cascades").
  - The effects are "statistically significant for hours, although not for days."
  - The paper suggests cascades help explain fat tails, and argues the moves come from stop clusters, not central-bank intervention.
- **Sample:** minute-by-minute USD/DEM, USD/JPY and USD/GBP quotes, New York hours, Jan 1996 – Apr 1998.
- **Numbers:** effect sizes were not retrieved.

**Osler and Savaser (2011), "Extreme returns: the case of currencies", Journal of Banking & Finance 35(11), 2868–2880.** https://ideas.repec.org/a/eee/jbfina/v35y2011i11p2868-2880.html **[UNVERIFIED]**
- **Claim:** price-contingent trading (stops, technical and algorithmic orders, option hedging) raises the frequency of extreme returns without news. The channels are order-size distribution, intraday clustering, clustering at particular prices, and trade–return feedback.
- **Numbers:** not retrieved. A blog headline, "stop orders drive half of abnormal currency moves", is unchecked.

**Kavajecz and Odders-White (2004), "Technical analysis and liquidity provision", Review of Financial Studies 17(4), 1043–1071.** https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html **[UNVERIFIED]**
- **Claim:** S/R levels coincide with peaks in limit-order-book depth, and the relationship comes from technical rules *locating depth already in place*. The levels map existing liquidity; they do not create it.
- **Sample and numbers:** not retrieved.

**Curcio, Goodhart, Guillaume and Payne (1997), "Do technical trading rules generate profits? Conclusions from the intra-day foreign exchange market", Int. J. Finance & Economics 2(4), 267–280.** https://ideas.repec.org/a/ijf/ijfiec/v2y1997i4p267-80.html **[UNVERIFIED]**
- **Claim:** filter rules supplied by technical analysts (S/R based, intraday FX) were profitable in trending periods but not on average. The result is worse after costs, and earlier academic rules were also unprofitable intraday.

**Neely and Weller (2003), "Intraday technical trading in the foreign exchange market", JIMF 22(2), 223–237.** https://gpbib.cs.ucl.ac.uk/gp-html/neely_2003_JIMF.html **[UNVERIFIED]**
- **Claim:** out-of-sample intraday rules (genetic program and linear forecast) earn no excess return once realistic costs and trading hours are included, although they pick up "remarkably stable patterns".

## 3. Trading-range breaks and anchoring to highs (equities)

**Brock, Lakonishok and LeBaron (1992), "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns", Journal of Finance 47(5), 1731–1764.** https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1992.tb04681.x **[UNVERIFIED]**: numbers from a GitHub PR that says it transcribed Table IV digit by digit (https://github.com/HCH725/alpha-strategy-research/pull/178, read via WebFetch); I did not read the paper.
- **Claim:** the trading-range break (TRB) rule beats the random-walk, AR(1), GARCH-M and EGARCH nulls by bootstrap. It buys when price exceeds the max of the prior 50/150/200 days and sells below the min (0 % and 1 % bands). Buy returns are higher and less volatile than sell returns, and sell-signal returns are negative.
- **Numbers (10-day returns, before costs):**
  - Across the six TRB rules: buy mean 0.55 %, sell mean −0.24 %, buy−sell 0.86 %.
  - TRB(1,200,0.01): 146 buys and 124 sells; buy +0.72 % (t 1.86), sell −0.47 % (t −1.98), buy−sell 1.19 % (t 2.78).
- **Sample:** DJIA daily, 1897–1986.

**Sullivan, Timmermann and White (1999), "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", Journal of Finance 54(5), 1647–1691.** https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf **[UNVERIFIED]**
- **Claim:** BLL's in-sample results survive White's Reality Check over 1897–1986, across a universe of 7,846 rules. On DJIA 1987–1996 the best rule's mean return was statistically insignificant: 8.63 %/yr before costs, per a secondary paper. One snippet puts the probability that the best rule did not beat the benchmark in 1987–96 at about 12 %.

**George and Hwang (2004), "The 52-Week High and Momentum Investing", Journal of Finance 59(5), 2145–2176.** https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf **[UNVERIFIED]**
- **Claim:**
  - Nearness to the 52-week high dominates past returns (individual and industry) in forecasting returns.
  - The returns it forecasts do not reverse in the long run.
  - The proposed reason is anchoring: traders under-react to news when price is near (or far from) the high.
- **Numbers:**
  - Winner−loser about 0.45 %/month, close to JT momentum (0.48 %, t 2.35) and industry momentum (0.45 %).
  - Ex-January 1.23 %/month (winner 1.30 %, loser 0.07 %); January only −8.27 %; t 7.06 and −5.49. These come from https://github.com/HCH725/alpha-strategy-research/pull/181, also unverified.
- **Sample:** CRSP stocks 1963–2001, top/bottom 30 %, six-month holding period.
- **Relevance:** this is a cross-sectional, monthly-horizon anchor effect, not an intraday level trade.

**Li and Yu (2012), "Investor attention, psychological anchors, and stock return predictability", Journal of Financial Economics 104, 401–419.** **[UNVERIFIED]**
- **Claim:** nearness of the Dow to its 52-week high predicts aggregate market returns positively; nearness to its historical high predicts them negatively. The result is robust across G7.

**Lo, Mamaysky and Wang (2000), "Foundations of Technical Analysis", Journal of Finance 55(4).** https://www.nber.org/papers/w7613 **[UNVERIFIED]**
- **Claim:** kernel-regression pattern detection finds that several patterns carry incremental information, especially for Nasdaq stocks. The patterns include rectangle tops and bottoms, which are range boundaries.
- **Sample:** US stocks 1962–1996. Rectangle-specific numbers were not retrieved.

## 4. Statistical tests of S/R and round-number barriers

**Garzarelli, Cristelli, Pompa, Zaccaria and Pietronero (2014), "Memory effects in stock price dynamics: evidences of technical trading", Scientific Reports 4:4487** (arXiv 1110.5197). **[UNVERIFIED]**
- **Claim:** at mechanically identified S/R levels, prices re-bounce more often than they cross, and more than a memoryless benchmark predicts. The bounce probability rises with the number of earlier bounces.
- **Data:** high-frequency LSE stocks (from memory, not confirmed). Numbers not retrieved.

**Chung and Bellotti (2021), "Evidence and Behaviour of Support and Resistance Levels in Financial Time Series", arXiv 2101.07410.** **[UNVERIFIED]**
- **Claim:** heuristic intraday S/R levels reverse trends significantly more than random-walk or shuffled-return benchmarks. More prior bounces mean a higher bounce probability, and the probability decays over time. No difference between support and resistance.

**Bhattacharya, Holden and Jacobsen (2012), "Penny Wise, Dollar Foolish: Buy–Sell Imbalances On and Around Round Numbers", Management Science 58(2), 413–431.** **[UNVERIFIED]**
- **Claim:** in more than 100 million US stock trades, liquidity demanders over-buy one cent below round numbers and over-sell one cent above. The effect is graded by roundness (whole dollar, then half dollar).
- **Relevant detail:** the imbalance is much stronger when the quote approaches an integer and stops than when it crosses. Investors lose close to $1 billion a year from this.

**Donaldson and Kim (1993), "Price barriers in the Dow Jones Industrial Average", JFQA 28(3).** **[UNVERIFIED]** (from memory plus one search summary)
- **Claim:** DJIA multiples of 100 acted at least temporarily as support and resistance. Numbers not retrieved.

**Aggarwal and Lucey (2007), "Psychological barriers in gold prices?", Review of Financial Economics 16, 217–230**; **Lucey and O'Connor (2016), "Mind the gap: psychological barriers in gold and silver prices".** **[UNVERIFIED]**
- **Claim:** round-number barriers affect the conditional mean and variance of gold. Intraday 1975–2015: barriers at 0 and 00 for gold, none significant for silver.

**Grimes, "Randomness revisited: random levels?" (SMB Training blog).** https://www.smbtraining.com/blog/randomness-revisited-random-levels **[UNVERIFIED]**
- **Practitioner argument, no statistics:** random levels on real charts show every behaviour traders cite: tests to the tick, multiple tests, support turning into resistance, gaps holding on retest. This is the visual version of the placebo argument.

## 5. Previous-day / opening-range breakouts (futures, ETFs)

No peer-reviewed study of previous-*week* high/low levels in futures or FX was found in five searches. The closest work is on opening-range and previous-day breakouts.

**Holmberg, Lönnbark and Lundström (2013), "Assessing the profitability of intraday opening range breakout strategies", Finance Research Letters 10(1), 27–33.** http://www.econ.umu.se/ueslpnr/ues845.pdf **[UNVERIFIED]**
- **Claim:** a test of ORB success rates using only daily OHLC. Applied to US crude-oil futures, it finds positive average returns and evidence of intraday trending.
- **Related paper:** Lundström, "Day trading returns across volatility states", reports about 200 bps/day difference between the highest and lowest volatility states for crude oil ORB.

**Zarattini and Aziz (2023), "Can Day Trading Really Be Profitable?" (SSRN 4416622).** **[UNVERIFIED]**
- **Claim:** a 5-minute ORB on QQQ, 2016–2023, gives annualised alpha 33 % net of commissions.
- **Replication:** an independent MQL5 blog reran it on NQ, SPX, Dow, DAX and FTSE CFDs, 2015–2026. The gross edge reproduces on NQ, but net of spread and slippage no market differs from zero and four of five are negative. https://www.mql5.com/en/blogs/post/776235 **[UNVERIFIED]**

**Marketcalls, "Trading the previous day high and previous day low breakout" (Nifty futures).** https://www.marketcalls.in/amibroker/trading-the-previous-day-high-and-previous-day-low-breakout-do-simple-strategies-really-work-part1.html **[UNVERIFIED]**
- **Practitioner backtest:** 1-minute data, 2010–2017, 0.02 % costs and slippage.
  - Net positive overall, with win rate 37–40 % and drawdowns of −34 % to −47 %.
  - Short-only lost money.
  - No control level.

**Gao, Han, Li and Zhou (2018), "Market intraday momentum", Journal of Financial Economics (2018), pp. 394–414, doi 10.1016/j.jfineco.2018.05.009.** **[UNVERIFIED]**
- **Claim:** SPY's first-half-hour return predicts its last-half-hour return, 1993–2013. The effect is stronger on volatile, high-volume and news days.
- **Relevance:** generic intraday momentum with no level involved. It is the alternative explanation for any breakout "edge".

## 6. Crypto-specific

### Round numbers and barriers
**Urquhart (2017), "Price clustering in Bitcoin", Economics Letters 159, 145–148.** **[UNVERIFIED]**
- **Claim:** over 10 % of BTC prices end in .00. Clustering rises with price and volume, which supports the negotiation hypothesis.
- **Follow-up:** Mbanga (2019) finds clustering strongest on Fridays and weakest on Mondays.

**Hu, McInish, Miller and Zeng (2019), "Intraday price behavior of cryptocurrencies", Finance Research Letters.** **[UNVERIFIED]**
- **Claim:** trade prices cluster at round numbers all day, with strategic pricing just above and below them. The authors read this as negotiation and strategic trading, not psychology.

**Fonseca, Pacheco and Lobão (2020), "Psychological barriers in the cryptocurrency market", Review of Behavioral Finance 12(2), 151–169.** **[UNVERIFIED]**
- **Claim:** four barrier tests on daily closes of six cryptocurrencies find barriers in four of them. For BTC there are some signs at the 100 and 1,000 levels.

**Choi (2026), "Strong clustering and weak barriers at round numbers in Bitcoin markets", Research in International Business and Finance 90.** https://ideas.repec.org/a/eee/riibaf/v90y2026ics0275531926002217.html **[UNVERIFIED]**
- **Sample:** Binance one-minute data, more than seven years.
- **Claim:** clustering is among the strongest documented in any market, but the barriers are weak.
  - Time above versus below round numbers is only slightly asymmetric.
  - Volatility near round numbers is about the same as elsewhere.
  - ML classifiers predict direction there at chance.
- **Reading:** round numbers act as coordination points for order flow, not as price constraints.

**Quiroga-Garcia, Pariente-Martinez and Arenas-Parra (2022), "Evidence for round number effects in cryptocurrencies prices", FRL 47, 102811.** **[UNVERIFIED]**
- Findings were not retrieved.

### Breakout and range rules in crypto
**Gerritsen, Bouri, Ramezanifar and Roubaud (2020), "The profitability of technical trading rules in the Bitcoin market", FRL 34, 101263.** **[UNVERIFIED]**
- **Claim:** in daily BTC data, Jul 2010 – Jan 2019, the trading-range-breakout rule (50/150/200-day) has significant forecasting power and beats buy-and-hold on a bootstrapped Sharpe. The outperformance comes in strongly trending markets.

**Hudson and Urquhart (2021), "Technical trading and cryptocurrencies", Annals of Operations Research 297, 191–220.** **[UNVERIFIED]**
- **Claim:** about 15,000 rules in five classes, including S/R, show significant predictability in every class and coin after multiple-testing corrections, with breakeven costs above typical crypto costs.
- **Caveat:** BTC showed no predictability out of sample.

**Corbet, Eraslan, Lucey and Sensoy (2019), "The effectiveness of technical trading rules in cryptocurrency markets", FRL 31, 32–37.** **[UNVERIFIED]**
- **Claim:** on one-minute BTC data, MA-oscillator and TRB (S/R) rules were tested. The variable-length MA got the strongest support; the TRB results were not retrieved.

**Zarattini, Pagani and Barbon (2025), "Catching Crypto Trends: A Tactical Approach for Bitcoin and Altcoins".** https://ideas.repec.org/p/chf/rpseri/rp2580.html **[UNVERIFIED]**
- **Claim:** a Donchian-channel ensemble over a survivorship-free coin set since 2015. On a top-20 rotational portfolio: Sharpe above 1.5 and alpha 10.8 %/yr against BTC, net of fees.
- **Relevance:** daily-horizon trend, not an intraday level effect.

### Anchoring to recent highs
**Fičura (2023), "Impact of size and volume on cryptocurrency momentum and reversal", FFA Working Papers 5.003.** https://wp.ffu.vse.cz/artkey/wps-202301-0003_impact-of-size-and-volume-on-cryptocurrency-momentum-and-reversal.php **[UNVERIFIED]**
- **Claim:** weekly cross-sectional returns.
  - Small, illiquid coins show weekly reversal; large, liquid coins show weekly momentum.
  - "High momentum" (distance of last week's close from the k-week high) predicts returns better than ordinary momentum.
- **Numbers:** distance from the 1-week high predicts negative returns for small, illiquid coins (t −9.03) and positive returns for large, liquid coins (t 4.93).
- **Relevance:** this is the only academic result found that uses the *previous-week high* in crypto. It is cross-sectional with weekly holding, not a touch event.

**Jia, Simkins, Yan, Zhang and Zhao, "Psychological Anchoring Effect and Cross Section of Cryptocurrency Returns" (SSRN 5386180).** **[UNVERIFIED]**
- **Claim:** nearness to the 52-week high positively predicts the crypto cross-section, 2014–2023 (per a Quantpedia summary). No independent replication was found.

### Liquidations, stops and sweeps
**"Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets", Applied Economics 53(47), 2021** (arXiv 2102.04591). **[UNVERIFIED]**
- **Sample:** BitMEX perpetual.
- **Numbers:** daily forced liquidations equal 3.51 % of long and 1.89 % of short positions; average leverage of liquidated traders about 60x. Uses extreme-value tails.
- **Scope:** this is about margins, not direction.

**"Towards Understanding Cryptocurrency Derivatives: A Case Study of BitMEX", ACM WWW 2021.** https://dl.acm.org/doi/fullHtml/10.1145/3442381.3450059 **[UNVERIFIED]**
- More than 425,000 liquidation events. Smaller traders account for liquidations disproportionately. Descriptive only.

**"Where does the criticality live? ...seven crypto-perpetual liquidation cascades", arXiv 2607.27070 (2026 preprint).** **[UNVERIFIED]**
- Seven Binance BTCUSDT cascades, May 2022 – Oct 2025. No early-warning signal works for all seven, and several look like shock-driven jumps.

**Glassnode liquidation maps and Kaiko depth notes** (e.g. https://research.glassnode.com/the-week-onchain-week-42-2026). **[UNVERIFIED]**
- These describe liquidation clusters at prices and the forced-buying chains that follow. Kaiko notes price impact rising non-linearly when activity outruns depth.
- They are maps of positioning, with no test that crossings of clustered levels continue more than placebo crossings.

**No study found** (three searches) that uses order-level stop or conditional-order data from a crypto exchange, or that tests "stop hunts" or "liquidity sweeps" against a control. A 2024 study of 10-minute order-book snapshots (five coins, a US exchange, Jan–Aug 2020) finds round-cent clustering in resting limit orders that grows with depth and distance from the best price. **[UNVERIFIED]**

### Crypto previous-week and previous-day levels (practitioner)
**SignalPilotLabs, "HOW-TO: tell whether a break above last week's high will hold" (TradingView, 2026).** https://www.tradingview.com/chart/ZROUSDT.P/JV1XvElC-HOW-TO-tell-whether-a-break-above-last-week-s-high-will-hold/ **[UNVERIFIED]**
- **Sample:** the 50 most-traded Bybit perps. Main window 12 Oct 2025 – 12 Oct 2026, with the prior year as a check, and more than 900 breaks per year.
- **Event:** the first 1 h close above last week's high in weeks that opened below it.
- **Results:**
  - 53.6 % were still above the level 24 h later (53.8 % in the prior year).
  - Only 25.5 % (22.2 %) never closed back below it within 24 h, so about three in four closed back below at least once.
  - Breaks of at least 0.25 ATR(14, 1 h) held 56.8 % (57.4 %), against 46.3 % (46.5 %) for smaller breaks.
- **Caveats:** a vendor post with no placebo level and no costs. It is, though, the closest published analogue of our breakout and reclaim events.

**ibrahimjaved12/crypto-watcher issue #185, "Support/resistance level detection and level-reaction study with placebo levels" (closed 9 Oct 2026).** https://github.com/ibrahimjaved12/crypto-watcher/issues/185 **[VERIFIED]**: page read via WebFetch.
- **Sample:** BTC, ETH, BNB, SOL, DOGE and XRP USDT, 1-minute bars.
- **Levels:** round numbers, previous UTC day and week high/low, and 4 h swing clusters.
- **Placebo:** 20 placebo levels per real level at L ± d·σ240, with d from 0.5 to 1.4.
- **Statistics:** UTC-day cluster bootstrap, B = 2,000.
- **Results (qualitative only):**
  - Bounce share is above the 20 % Brownian reference at every level set, but equal to the placebo: "no level effect on bounce."
  - Previous-*day* levels are penetrated more often than placebo, pooled and across most symbols. The author calls this "a lead for a break-continuation test, not a result."
- **Missing:** no counts or bps in the public issue; no level entry was adopted.

**Kaiko via The Block (Feb 2024), weekend liquidity.** https://www.theblock.co/post/279353/bitcoin-weekend-trading **[UNVERIFIED]**
- The weekend share of BTC volume fell to 13 % from 24 % in 2018 (11 % on US exchanges), and weekend spreads widen.
- **Relevance:** the Monday 00:00 UTC week boundary is a charting convention in a 24/7 market, and part of each "week" trades in thin liquidity.

**CME gap "fill rates".** Community claims of 65–95 % fill rates have no citable study behind them. https://www.tradingview.com/ideas/cmegaps/ **[UNVERIFIED]** This is a good example of the reel's first point: nearby prices get revisited at high base rates with no level effect.

## 7. This repository (prior internal evidence)
**`cex-mm/artifacts/research/2026-10-22-trend-improvement.md`, findings row 7.** **[VERIFIED]**
- Daily-horizon breakout variants did not improve the running trend rule. Sharpe gain against the running book on panel B POST, daily / weekly book:
  - SIG-4 Donchian ensemble with ratchet exit: +0.008 / −0.049 (A POST −0.200 / −0.272).
  - SIG-11 Carver breakout blend: +0.011 / −0.020.
- Neither passed the pre-registered rule.
- **Relevance:** our book already holds daily-horizon breakout and trend exposure. Any PWH/PWL breakout effect must be intraday and level-specific to add anything.

---

## Synthesis

**(a) Fades at the level.**
- **The only well-identified level-specific fade effect is small, short-lived and tied to levels where orders demonstrably cluster:**
  - Osler (2000): published S/R levels bounced 60.8 % against 56.2 % at artificial levels, +4.6 pp, in FX 1996–98.
  - Osler (2003): take-profit orders sit *at* round numbers, and reversals there fade within about an hour.
  - Kavajecz and Odders-White: levels coincide with resting depth.
  - Mechanically chosen S/R in stocks bounces more than a random walk would (Garzarelli et al.; Chung and Bellotti), with the probability rising in the number of prior touches.
- **For crypto the closest tests are null:**
  - Choi (2026): BTC round numbers are strong clustering points but weak barriers, with ML prediction at chance.
  - crypto-watcher #185: bounce share at previous-day/week levels equals the placebo.
  - The reel: 40.4 % rejection at the PWH, an effect it found no edge in once a control was added.
- **The base rate of "bouncing" is high at any level** (56 % at Osler's artificial levels; well above the 20 % Brownian reference in #185). Raw rejection rates therefore say nothing without a matched control.
- **Prior: a level-specific fade at PWH/PWL is at most a few percentage points of hit rate.** That is unlikely to clear the 9.43 bps round trip (maker entry plus taker exit) at a 4 h horizon.

**(b) Breakout continuation.**
- **There is a credible mechanism with FX order data:**
  - Stop-losses cluster *just beyond* salient levels, so crossings run faster (Osler 2003, 2005), with effects significant "for hours, not days".
  - Crypto adds liquidation levels that are mapped and widely watched (Glassnode). But no study tests that crossings of those clusters, or of PWH/PWL, continue more than placebo crossings do.
- **At daily horizons, range-break rules look good in sample** (BLL on the DJIA, 0.86 % buy−sell per 10 days; Gerritsen et al. on BTC). They weaken out of sample and after data-snooping control (STW 1999; Hudson and Urquhart: no BTC out-of-sample predictability). Our own SIG-4 and SIG-11 failed to add to the trend book.
- **Intraday breakout and ORB evidence is mostly gross, and tends to vanish net of spread and slippage** (Zarattini and Aziz versus its MQL5 replication; Neely and Weller; Curcio et al.).
- **The most direct crypto evidence is near a coin flip.**
  - SignalPilotLabs: 53.6 % of 1 h closes above last week's high were still above 24 h later.
  - The reel's 78.9 % continuation was matched by 77.6 % at controls.
  - The one hint of something level-specific is crypto-watcher's "previous-day levels penetrated more often than placebo". It is unquantified and the author treated it only as a lead.
- **Prior:** expect real − P1 near zero, possibly slightly positive through the stop/liquidation mechanism, concentrated in the first hours. Expect that to fall short of the 14.62 bps taker round trip at 24 h.

**(c) Failed-breakout (sweep-and-reclaim) reversals.**
- **This is the thinnest literature.**
  - No peer-reviewed test of sweep-and-reclaim against a control was found.
  - "Turtle soup" (Connors and Raschke 1995) has only practitioner claims with no independent statistics.
  - ICT-style "liquidity sweep" material has no data at all.
- **Indirect evidence:**
  - Osler's two-cluster structure (take-profits at the level, stops beyond it) allows a sweep that exhausts the stops and then reverses. No one has tested it.
  - Bhattacharya et al. show that order imbalances concentrate when price approaches a round number and *stops*, not when it crosses.
  - SignalPilotLabs implies reclaims are the norm: about 74.5 % of 1 h closes above last week's high closed back below within 24 h. So the reclaim condition selects a very common event.
  - Short-horizon reversal in crypto is documented for small, illiquid coins (Fičura; daily reversal studies), which a reclaim rule would pick up generically.
- **Prior: no edge expected. Treat pattern S as exploratory.**

**(d) Level-specific or generic momentum / mean reversion.**
- **Where a control exists, the level-specific part is small or zero:**
  - Osler (2000): +4.6 pp over artificial levels, for expert-chosen levels.
  - Reel: +1.3 pp (78.9 − 77.6) on breakout continuation.
  - crypto-watcher: 0 on bounce, and an unquantified positive on previous-day penetration.
  - Choi: weak barriers.
- **Most of what traders see at these levels is the base rate.** Touch frequency is a property of distance against volatility. Under a driftless random walk the probability of reaching a level at distance D within T is 2[1 − Φ(D/σ√T)] (reflection principle), which is why 91.9 % of weeks touch one of two nearby levels. The same base rate explains why "CME gaps fill". Bounce and continuation rates near 55–80 % appear at arbitrary levels too.
- **Effects that are genuinely level-specific exist where orders demonstrably cluster:**
  - round numbers and published levels, through stops and take-profits;
  - 52-week and historical highs as cross-sectional anchors at monthly horizons (George and Hwang; Li and Yu; Jia et al. in crypto);
  - distance from the 1-week high as a weekly cross-sectional predictor in crypto (Fičura).
  None of these is a PWH/PWL touch trade, and Fičura's sign flips between large and small coins. That is momentum and liquidity, not a level.
- **For 24/7 perps the weekly boundary is a convention.** Weekend liquidity is thin (13 % weekend volume share in 2024). The plan's P2 control (a 7×24 h window shifted to end on Thursday 12:00 UTC) is the right test of whether the calendar week matters at all.

**Bottom line for the frozen plan.**
- The prior favours the reel's null.
- The most plausible non-null is a small, short-lived breakout effect from stop and liquidation clustering. If it exists, it should appear as real − P1 > 0 at 1–4 h, more than at 24 h. It will probably be too small for taker costs.
- The literature also points at three design risks for the adversarial check:
  1. **Placebo validity.** Osler's artificial levels were drawn near the open, as P1 is. But P1 levels at 1.25× and 1.5× the distance can only be touched after the real level has broken, so their events come from moves already in progress and can inflate or deflate the placebo.
  2. **Fill optimism on fades.** Osler and Bhattacharya et al. show that resting depth sits at the level, so a limit at L competes in a queue.
  3. **Clustering in time.** Cascades come in waves (Osler 2005; the October 2025 liquidation cascade), which supports the plan's week-cluster bootstrap.
