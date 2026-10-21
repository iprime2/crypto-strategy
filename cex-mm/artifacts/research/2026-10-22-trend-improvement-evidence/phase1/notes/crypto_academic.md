# Crypto-specific academic evidence on time-series momentum / trend following, 2018–2026

**Angle:** crypto-specific academic evidence (lookbacks, holding periods, vol scaling, filters, universe, costs, post-2021 behaviour, long-only vs long-short, momentum crashes, day-of-week).
**Date:** 2026-10-21. **Author:** research subagent. **Repo state:** read-only; nothing edited, no orders.
**Sourcing caveat:** every paper host (SSRN, arXiv, ScienceDirect, Springer, Wiley, journals.vu.lt, Monash, zenodo, Concretum, Medium) was unreachable: `WebFetch https://arxiv.org/abs/2602.11708` → `getaddrinfo ENOTFOUND arxiv.org`. The only hosts opened were `raw.githubusercontent.com` and `api.india.delta.exchange`. So almost every number below comes from search-engine summaries of abstracts and is tagged **[UNVERIFIED]**; where a second-hand transcription of a paper was opened on GitHub it is tagged **[SECONDHAND]** with the file URL. Numbers from the repo's own evidence are tagged **[REPO]**.

---

## 0. Repo baseline facts reused (all [REPO], `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/backtest_results.md`)

- Daily TV0.40 (20/60/120, 9 coins, Binance 2020-05..2026-09): Sharpe 1.25, CAGR +24.2%, maxDD −21.9%, fees 1.14%/yr, funding +3.43%/yr, 1,773 trades/yr.
- Weekly Mon TV0.25 band 10%: Sharpe 1.12, +14.1%, −16.9%; 2024-01..2026-09 Sharpe 0.86. Daily TV0.25 band 10%: Sharpe 1.25, 538 trades/yr (the band costs nothing in Sharpe).
- **T3d lookback sets (weekly book):** (20,60,120) 1.12; **(10,30,60) 1.08** (2024-26: 0.72, maxDD −15.6%); **(50,100,200) 0.95** (2024-26: 0.62, maxDD −21.7%); (20,) 0.90. So in the repo's own data neither faster nor slower *sets* beat the design; the design sits at the sweet spot.
- T3e vol window: 30d Sharpe 1.16 / 60d 1.12 (90d not shown in the grep).
- T3j regime filters (weekly book): none 1.12 / −16.9%; BTC<200d→flat 1.18 / −14.4%; BTC 30d vol>70%→flat 1.02 / −14.0%. (The task brief says the 200d filter gave "same Sharpe, worse DD" — that must be the daily book; on the weekly book it was mildly better on both. Either way it was rejected as a regime filter.)
- Ex-ante 24-perp universe: daily 0.86, weekly 0.82 → the 9-coin set is a hindsight universe.
- No Donchian / channel-breakout / trailing-exit signal was ever tested in the repo (grep of the evidence pack, `resource/`, `scripts/`: only the prop-firm "Breakout" and the Hummingbot trailing-stop note in resource/02).

---

## 1. Paper-by-paper

### 1.1 Liu & Tsyvinski, "Risks and Returns of Cryptocurrency" (NBER w24877, 2018; RFS 2021, DOI 10.1093/rfs/hhaa113)
- URL: https://www.nber.org/system/files/working_papers/w24877/w24877.pdf ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3226952 [UNVERIFIED]
- Sample: BTC/ETH/XRP (coin-market index) 2011–2018. Time-series momentum at daily and weekly frequency. One-sd rise in this week's BTC return → +3.16% / +3.66% / +3.49% / +1.50% over the next 1/2/3/4 weeks; one-sd rise in today's return → +0.33% next day. Weekly quintile sort: top quintile 11.22%/week (Sharpe 0.45) vs bottom 2.60%/week (0.19). Effect "smaller but still significant from 2013 onward"; ETH less significant than BTC.
- **In-sample, 2011–2018, pre-futures, three coins.** Horizon 1–4 weeks is the published evidence for a *short* momentum horizon; nothing about 60–120 day lookbacks here.
- Not opened. Secondary pages: VoxEU column https://cepr.org/voxeu/columns/risks-and-returns-cryptocurrencies ; a replicator note https://raw.githubusercontent.com/alfred1123/Quant_Strategies/2db49183360d0c9dab8fd2572bdad75b30da978a/docs/research/momentum-reversal-filters.md [SECONDHAND, opened].

### 1.2 Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency" (NBER w25882; JF 2022, 77:1133–1177)
- URL: https://www.nber.org/system/files/working_papers/w25882/w25882.pdf ; https://onlinelibrary.wiley.com/doi/10.1111/jofi.13119 [UNVERIFIED]
- Cross-sectional long-short momentum, weekly rebalance, 1-/2-/3-/4-week formation: 2.7% / 3.3% / 4.1% / 2.5% excess per week (2014–2018, ~1,800 coins). Three-factor model (CMKT, CSMB, CMOM) prices all nine successful strategies. **Cross-sectional, small-coin heavy, in-sample 2014–18.** Grobys et al. (1.14) later show that these payoffs are driven by trimming/outliers and vanish among survivors. Relevance to us: only as the origin of "1–4 week momentum is where the crypto anomaly is strongest".

### 1.3 Grobys & Sapkota, "Cryptocurrencies and momentum", Economics Letters 180 (2019) 6–10
- https://www.sciencedirect.com/science/article/pii/S0165176519301077 [UNVERIFIED]
- 143 coins, 2014–2018, monthly data: 12-1 momentum insignificant; previous-month sort shows **reversal** (as summarised by Dobrynskaya). No one-week test. Monthly horizons are too slow for crypto.

### 1.4 Tzouvanas, Kizys & Tsend-Ayush, Economics Letters 191 (2020) 108728
- https://ideas.repec.org/a/eee/ecolet/v191y2020ics0165176519303647.html [UNVERIFIED]; accepted MS at https://eprints.soton.ac.uk/434719 (not opened)
- 12 coins, 3 years of daily data, J/K strategies: momentum "highly significant for short-term portfolios but disappears over the longer term"; momentum portfolios diversify traditional assets. No Sharpe figures retrieved. In-sample, tiny sample.

### 1.5 Kość, Sakowski & Ślepaczuk, Physica A 523 (2019) 691–701
- https://ideas.repec.org/a/eee/phsmap/v523y2019icp691-701.html ; shiny app https://github.com/pawelsakowski/fintech2020 [UNVERIFIED]
- Top-100 coins by cap, weekly: "clear and significant dominance of the short-term contrarian effect over momentum" — but a later FRL paper reads it as "momentum found only in the 1-week winner strategy with a weekly rolling window". Cross-sectional, 2015–2018, contradictory readings. Treat as: 1-week *cross-sectional* reversal exists in the broad universe (illiquid coins), not in large caps.

### 1.6 Borgards, "Dynamic time series momentum of cryptocurrencies", NAJEF 57 (2021) 101428
- https://www.sciencedirect.com/science/article/abs/pii/S1062940821000590 ; PDF copy (not opened) https://community.portfolio123.com/uploads/short-url/amrMsuqIKzdHcHHyvMud4YNPwZB.pdf [UNVERIFIED]
- 20 largest coins as of 2019-12-31, Jan 2014–Dec 2019, daily and intraday. Method counts "momentum periods" after a "formation period" (no fixed lookback/holding) vs the S&P 500 and vs a GBM that never shows a cycle. Finding: a large share of formation phases are followed by momentum periods; "short-term TSM identifiable without an external model parameter". **No tradable rule, no after-cost numbers, in-sample to 2019, universe chosen ex post.** Not a candidate source.

### 1.7 Dobrynskaya, "Cryptocurrency Momentum and Reversal" (SSRN 3913263, 2021; J. Alternative Investments 2023) and Fičura & Colak, "Impact of Size and Volume on Cryptocurrency Momentum and Reversal" (SSRN 4378429, FFA WP 2023)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263 ; https://wp.ffu.vse.cz/pdfs/wps/2023/01/03.pdf [UNVERIFIED] (the task brief's "JBEF 2024" citation was not found; the published venue is JAI 2023)
- Dobrynskaya: ~2,000 largest coins 2014–2020, cross-sectional sorts, holding 1 week–2 years: **positive momentum at 2–4 week horizons, significant reversal at longer horizons**, stronger with longer sorting/holding; not explained by crypto factors.
- Fičura & Colak: the weekly reversal is confined to small/illiquid coins; **large, liquid coins show weekly momentum (t = 4.93)**; 1-week and 2-week return signals predict next-week return for large/liquid coins (t = 2.33, 2.87); a "high momentum" measure = distance from the 1-week high is the strongest predictor (t = 4.93). Cross-sectional, 2014–2022-ish, in-sample.
- Relevance: for *our* large-cap set the 1–2 week horizon is momentum, not reversal; the distance-from-high signal is a Donchian-type signal.

### 1.8 Jia, Goodell & Shen, "Momentum or reversal: which is the appropriate third factor for cryptocurrencies?", FRL 45 (2022) 102139
- https://www.sciencedirect.com/science/article/abs/pii/S1544612321002208 [UNVERIFIED]. Momentum, not reversal, is the right third factor; momentum returns grow as cap shrinks (small-coin effect again).

### 1.9 Zaremba et al., "Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets", IRFA 78 (2021) 101908
- https://doi.org/10.1016/j.irfa.2021.101908 [UNVERIFIED, via the alfred1123 note]. Broad universe: last-day reversal tied to illiquidity; **the largest, most liquid coins show daily momentum instead.**

### 1.10 Begušić & Kostanjčar, "Momentum and liquidity in cryptocurrencies", arXiv:1904.00890
- https://arxiv.org/abs/1904.00890 [UNVERIFIED]. Momentum concentrated in liquid coins; two long-only books (liquid winners, illiquid losers) beat the cap-weighted market. Consistent with 1.7/1.9.

### 1.11 Bianchi & Babiak, "A Factor Model for Cryptocurrency Returns" (CERGE-EI WP 710, 2021/22)
- https://www.cerge-ei.cz/pdf/wp/Wp710.pdf ; http://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-056-Daniele-Bianchi.pdf [UNVERIFIED]
- IPCA with 3 latent factors beats a 6-observable-factor benchmark (market, size, momentum, volatility, liquidity, reversal) in daily R² (17.2% vs 9.6%). Secondary summaries say "a strong time-series momentum effect" and that market, size, momentum dominate. No rule, no numbers for TSM. Pricing paper, not a strategy paper.

### 1.12 Han, Kang & Ryu, "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions" (SSRN 4675565, Dec 2023)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565 ; PDF https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf [UNVERIFIED, not openable]
- Dec 2013–Aug 2023; lookbacks and holding periods 1–56 days; "realistic assumptions" = transaction costs and **intraday price fluctuations that liquidate leveraged positions**; many significant-return portfolios earn insignificant profit once these are charged. **Best TSM pair: 28-day lookback, 5-day holding: Sharpe 1.51 vs market 0.84; the gain "mainly results from reduced downside risk".** Cross-sectional momentum "almost non-existent". TSM is the anomaly that survives frictions.
- Relevance: strongest crypto-specific support for (i) TSM over CSM, (ii) a ~1-month lookback with ~weekly re-decision, (iii) the whole Sharpe gain being drawdown control (matches the repo: signal adds ~0.1–0.2 Sharpe and halves DD).

### 1.13 Kang & Ryu, "Time-series momentum and market timing in Bitcoin", Risk Management 28:54 (2026, online 10 Jul 2026)
- https://link.springer.com/article/10.1057/s41283-026-00234-7 ; https://ideas.repec.org/a/pal/risman/v28y2026i3d10.1057_s41283-026-00234-7.html [UNVERIFIED]
- BTC only; momentum "speed" varied continuously; **slow signal (12-week ≈ 84-day baseline) beats intermediate and fast in BTC**, the reverse of equities; slow signals "keep exposure through profitable disagreement states", fast ones overreact to noise; **dynamic speed adjustment adds little beyond a simple low-speed rule**; speed is "an endogenous risk-management device". Sample period and exact construction not retrieved.
- Relevance: supports our 60/120-day legs and argues *against* adaptive-speed (ML) tinkering; consistent with repo T3d where (10,30,60) < (20,60,120). Note that (50,100,200) was also worse in T3d, so "slower is better" has a ceiling in our data.

### 1.14 Grobys and co-authors (three papers)
- **Grobys, Kolari, Sandretto, Shahzad & Äijö, "Cryptocurrency momentum has (not) its moments", FMPM 39 (2025) 443–476**, https://link.springer.com/article/10.1007/s11408-025-00474-9 [UNVERIFIED]: top-30 coins, equal-weighted, weekly rebalance, cross-sectional momentum; severe crashes (one of ≈255% in Dec 2020) caused by **an extreme jump in a single coin in the short leg**, not by market reversals; raw payoffs insignificant without trimming; momentum is a large-cap phenomenon; also tests volatility-managed momentum (result not retrieved).
- **Grobys & Shahzad, "Cryptocurrency Momentum: Is It an Illusion?", IJFE 31(2) (2026) 2180–2193**, https://onlinelibrary.wiley.com/doi/abs/10.1002/ijfe.70036 ; SSRN 4633099 [UNVERIFIED]: realised variances of six momentum strategies follow power laws with undefined mean/variance; infinite-variance hypothesis not rejected → t-stats and Sharpe ratios "may not exist"; variance-based metrics uninformative.
- **Grobys, Sandretto & Äijö, "On survivor cryptocurrency momentum", FRL 92 (2026) 109602**, https://ideas.repec.org/a/eee/finlet/v92y2026ics1544612326001339.html ; author copy https://iris.unito.it/retrieve/f41aebe6-ee86-4e5e-b065-e85c3e38cb3b/1-s2.0-S1544612326001339-main%20(1).pdf [UNVERIFIED]: **nine coins that stayed in the top-100 from Jan 2017 to Aug 2024, weekly data: momentum among survivors generates no significant payoff**; plain momentum on the yearly top-30 is profitable only after trimming and is sample-dependent; "significant payoffs are an artefact of coins only temporarily accessible for trading".
- Relevance: all three are about **cross-sectional** long-short momentum. For our long/flat TSM rule they say: (a) never add a short leg (confirms repo 0.78 vs 1.25), (b) the 9-coin survivor universe is exactly the sample where cross-sectional momentum is absent — our edge, if any, is time-series beta-timing, not relative ranking, and (c) report drawdown and tail metrics alongside Sharpe.

### 1.15 Zarattini, Pagani & Barbon, "Catching Crypto Trends; A Tactical Approach for Bitcoin and Altcoins" (SSRN 5209907, SFI RP 25-80; posted 6 May 2025, revised 2 Oct 2025)
- Paper: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 [UNVERIFIED]; summaries https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/ , https://concretumgroup.substack.com/p/catching-crypto-trends , https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/ , https://ideas.repec.org/p/chf/rpseri/rp2580.html [UNVERIFIED]
- **Rules [SECONDHAND, opened]:** transcription with section numbers at https://raw.githubusercontent.com/alfred1123/Quant_Strategies/2db49183360d0c9dab8fd2572bdad75b30da978a/docs/research/catching-crypto-trends.md ; corroborated by https://raw.githubusercontent.com/rgriesel/pionex/954f889a151107ca0ccf88c6ba07e55bfee09219/pionex_lab/swing/donchian.py , https://raw.githubusercontent.com/metatim89-a11y/solpred/f9a609a8d0f6bcf6bfd2414c5f219a848dfda6b6/scripts/strategy-v4-donchian-replication.js , https://raw.githubusercontent.com/imikerussell/beebots/6cf999a224e67c7e2b6a74be0a064c409523d519/strategies/BREEZY_BEE.md , https://raw.githubusercontent.com/sercanatalik/galata-research/29d35e1ffee5d26d9700de9d890a2f9d0693725a/planning/preregistered/donchian-ensemble.md (all opened; all say they could not open SSRN and worked from the Concretum/CXO summaries, so the rules agree with each other but are not verified against the PDF).
  - §4.1 Nine lookbacks n ∈ {5, 10, 20, 30, 60, 90, 150, 250, 360} days on **daily closes**. Up_n(t) = max close over last n days incl. t; Down_n = min; Mid_n = (Up+Down)/2.
  - Entry: Pos_n = 1 when Close_t = Up_n(t) (a new n-day closing high). Initial stop = Mid_n at entry (fn. 3).
  - Exit: Pos_n = 0 when Close_t ≤ Stop_n(t). Stop ratchets: Stop_n(t+1) = max(Stop_n(t), Mid_n(t)); never moves down. Long-only.
  - §4.2–4.3 Sizing: w_n(t) = min(target_vol / σ_t, cap) × Pos_n(t), σ_t = 90-day annualised vol of the asset (shared by all lookbacks); **target_vol = 25%, cap = 200%** (CXO summary); ensemble w_combo = (1/9) Σ w_n (weights averaged, not voted). Weight set at close t, earns return t+1.
  - §5.1 Cost mitigation = **a rebalance band applied only to vol-driven weight changes; a new breakout or a stop exit trades immediately.** Results net of 10 bps plus band. Sensitivity 0/10/25/50 bps; the band recovers ≈100 bps/yr of CAGR at 50 bps (Fig. 3); the 5-day model's CAGR falls from 34% to 18% at 50 bps. "Bitcoin exchange costs generally below 5 bps."
  - §3 Data: CoinMarketCap daily OHLCV aggregated across exchanges, Jan 2010–Mar 2025, survivorship-bias-free; BTC results 1 Jan 2015–19 Mar 2025; other coins from Jan 2015 or listing.
  - §7 / Table 4 rotation: **top 20 coins by 30-day median USD volume, equal capital, reconstituted monthly; eligibility ≥365 days listed and 30-day median volume ≥ $2M; removal if median volume < $1M or median |daily change| < 0.5%.** Net 10 bps: CAGR 18%, vol 9%, Sharpe 1.57, Sortino 1.97, maxDD 11%, alpha 10.8% vs BTC, beta 0.08.
  - Table 1 BTC gross, Jan 2015–Mar 2025 (CAGR / vol / Sharpe / MDD / trades): 5d 36%/19%/1.66/25%/292; 10d 32%/18%/1.55/27%/156; 20d 34%/18%/1.60/26%/78; 30d 34%/19%/1.61/24%/49; 60d 28%/19%/1.30/19%/28; 90d 27%/20%/1.20/24%/20; 150d 21%/20%/0.99/29%/15; 250d 25%/20%/1.13/33%/9; 360d 29%/20%/1.28/34%/5; **Combo 30%/17%/1.58/19%**. Buy-and-hold BTC drawdown > 80%.
  - Table 3 net of 10 bps + band: BTC 30%/17%/1.56/19%; ETH (from Aug 2015) 27%/16%/1.51/15%; BNB (from Jul 2017) 17%/15%/1.06/17%; 40 coins in the table incl. SOL, XRP, DOGE (numbers not transcribed).
  - Flagged inconsistencies: combo MAR 0.88 (T1) vs 1.15 (T3); Sortino 2.03 gross → 1.23 net while Sharpe barely moves; 5d CAGR 34% vs 36%. Gaps: return type for σ, same-bar entry/exit precedence, whether the band is absolute or relative, what the 10 bps multiplies, slippage, risk-free rate, UTC cut-off.
- **Independent replication [SECONDHAND, opened]** (galata-research pre-registered test, BTC & ETH perps on Hyperliquid, 1,216 days 2023-05-28..2026-09-24, 4.5 bps/side, no funding charged, vol cap 1.0): BTC sized ensemble Sharpe **0.97 vs buy-and-hold 0.975**, net +52.5% vs +214.6%, **maxDD −15.0% vs −53.0%**; ETH 0.72 vs 0.50, maxDD −14.0% vs −67.6%; unsized BTC 0.96 / −20.1%. Verdict "not supported" on Sharpe (DSR 0.92, PBO 0.63); drawdown reduction holds. Tail: sizing did not improve 1% ES/vol.
- **Assessment:** the only trend paper in this sweep with (a) a fully specified daily long-only rule, (b) a survivorship-free universe, (c) explicit costs and a cost-mitigation rule, (d) per-lookback tables. Still in-sample on crypto only (2015–2025 includes the 2015–17 and 2020–21 melt-ups), authored by a vendor (Concretum), and the one out-of-sample re-test (2023–26) shows the Sharpe edge over buy-and-hold gone while the drawdown halving remains — the same picture as the repo rule in 2025–26.

### 1.16 Zarattini & Antonacci, "A Century of Profitable (Industry) Trends" (Dow Award 2025)
- https://cmtassociation.org/wp-content/uploads/2025/09/2025-Dow-Winner-A-Century-of-Profitable-Trends.pdf ; https://concretumgroup.com/a-century-of-profitable-industry-trends/ ; critique https://arxiv.org/html/2412.14361v2 [UNVERIFIED]
- 48 US industry portfolios 1926–2024, Donchian (20d upper / 40d lower) + Keltner breakout long-only: 18.2%/yr, vol 12.6%, Sharpe 1.39 vs market 9.7%/17.1%/0.63; upside beta 1.16, downside beta 0.31. Non-crypto multi-asset support for the Donchian-breakout-with-trailing-exit family. The arXiv critique questions robustness/implementation.

### 1.17 Bui & Nguyen (Talyxion Research), "Systematic Trend-Following with Adaptive Portfolio Construction" — "AdaptiveTrend", arXiv:2602.11708 (12 Feb 2026)
- https://arxiv.org/abs/2602.11708 ; https://arxiv.org/html/2602.11708v1 ; explainer https://antonio-velazquez-bustamante.medium.com/adaptivetrend-a-6-hour-trend-following-system-for-crypto-that-adapts-its-portfolio-every-month-eb114edcbcef ; https://www.quantseeker.com/p/weekly-research-recap-0bf [UNVERIFIED]
- 150+ Binance USDT-M perps, 6-hour bars (1h/4h "excessive turnover", 8h/12h/1d "miss short-lived moves"); dynamic trailing stop tied to intraday vol (credited ≈ +0.7 Sharpe by a summary); monthly asset selection by rolling Sharpe with market-cap screen; fixed 70/30 long-short; **Sharpe 2.41, maxDD −12.7%, Calmar 3.18, "out-of-sample" 2022–2024 (36 months)**; a vol-scaled TSMOM benchmark at 10% target vol reports Sharpe 1.83 in the same paper. Dates inconsistent (Jan 2021–Dec 2024 vs 2022–2024). Not peer-reviewed, vendor authorship, no cost schedule retrieved, 150-pair universe and 6h cadence not implementable on Delta at $1k, includes shorts.
- Usable pieces: none directly. The "TSMOM benchmark Sharpe 1.83 at 10% vol, 2022–24" is a reminder that even the vendor's own baseline on a wide universe is far above what 9 majors produce (repo 2022–23 Sharpe 0.35) — the wide universe is doing the work.

### 1.18 Howden & Andreev, "Risk-Managed Time-Series Momentum in Crypto Majors: Crash-State De-Risking and Drawdown Control" (SSRN 7115459, 30 Jul 2026, 6 pages, not peer-reviewed)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7115459 [UNVERIFIED; abstract described as partly garbled]
- BTC, ETH, BNB, XRP, ADA, SOL, DOGE; **MOP-style long/flat: hold while trailing 30-day return > 0, else cash**; lookback fixed ex ante; net 25 bps: **Sharpe 1.41 vs 0.70 equal-weight buy-and-hold; maxDD −84.4% → −44.6%**. Overlay: **halve gross exposure when the aggregate crypto market is > 15% below its trailing peak**: maxDD → ≈ −28%, Calmar 1.56 → 1.98, Sharpe ≈ 1.53. All 96 grid configurations had smaller maxDD than buy-and-hold. Robust on a frozen long-history universe and at 50 bps round trip. Framed as a drawdown-control result, not alpha.
- Assessment: tiny preprint, in-sample grid, universe includes SOL (hindsight). Confirms 30-day long/flat as the simplest crypto TSM rule; the overlay is a cousin of the repo's rejected regime filters.

### 1.19 Huang, Sangiorgi & Urquhart, "Cryptocurrency Volume-Weighted Time Series Momentum" (SSRN 4825389, 4 Dec 2024)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4825389 ; blog https://aligrithm.com/crypto-tsmom-lives-in-volume-weighted-returns/ [UNVERIFIED]
- 3,192 coins 2014–2023, daily rebalancing: volume-weighted winner-minus-loser TSMOM earns **0.94%/day, Sharpe 2.17**; the equal-weighted version *loses* 1.19%/day; not explained by market/size/momentum/MAX factors, not wash trading. Exact signal definition and lookback not retrieved.
- Assessment: a 3,000-coin daily-rebalanced long-short construction whose sign flips with the weighting scheme is a microstructure/illiquidity result, not a rule for 9 majors on one venue. Not a candidate; recorded for completeness.

### 1.20 Volatility scaling in crypto
- **Habeli, Barakchian & Motavasseli, "Adaptive Risk Allocation in Crypto Markets: Evaluating Volatility-Scaled Portfolios" (SSRN 5090097)**, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5090097 [UNVERIFIED]: scaling the market and seven crypto strategies by recent vol raises Sharpe and produces abnormal returns **concentrated in momentum strategies and the market portfolio**; works under tight leverage limits; gains grow with horizon; not universal across strategies. Window not retrieved.
- **"Cryptocurrency market risk-managed momentum strategies", FRL 2025**, https://www.researchgate.net/publication/393284396_Cryptocurrency_Market_Risk-Managed_Momentum_Strategies [UNVERIFIED]: Barroso–Santa-Clara scaling (target / realised variance of the strategy) on weekly cross-sectional crypto momentum: **mean weekly return 3.18% → 3.47%, annualised Sharpe 1.12 → 1.42**. Drawdown not retrieved.
- Equity reference: Barroso & Santa-Clara 2015 (momentum Sharpe roughly doubles), Moreira & Muir 2017; Lehigh re-test https://www.lehigh.edu/~xuy219/research/COWY.pdf [UNVERIFIED].
- Note: these scale the *strategy's own* return variance (portfolio level), whereas our rule scales each *asset* by its own 60-day vol; the two differ by the correlation term, which in crypto crashes goes to ~0.9 across majors.

### 1.21 Pre/post spot-ETF TSMOM (Zenodo record 19671502, 2026)
- https://zenodo.org/records/19671502 [UNVERIFIED]: vol-scaled TSMOM, monthly rebalance (MOP 2012 template), daily data Jan 2018–Mar 2026 on BTC, ETH, IBIT, FBTC, GLD, SPY: annualised return 18.03% pre-ETF → 28.58% post (11 Jan 2024), **Sharpe 0.82 → 1.22, t-test p = 0.58 (not significant)**; trailed buy-and-hold by 7.67% pre, beat it by 20.95% post. Lookback not retrieved. Small, un-reviewed; the only paper found that reports a post-2024 split.

### 1.22 Factor-zoo / out-of-sample momentum
- **"Taming crypto anomalies: A Lasso-type factor model" (RIBAF 2026)**, https://www.sciencedirect.com/science/article/abs/pii/S0275531926000255 [UNVERIFIED]: 49 anomalies 2014–2023; only 13 significant full-sample; out-of-sample the size effect disappears and a left-tail-risk effect appears; the selected three-factor model is **market + two-week momentum + residual momentum** — i.e. 2-week momentum remains priced through 2023.
- **"Cryptocurrency factor momentum", Quantitative Finance 23(12) 2023**, https://www.tandfonline.com/doi/abs/10.1080/14697688.2023.2269999 [UNVERIFIED]: 3,900+ coins 2014–2022, 34 anomalies; past winners beat losers across sub-periods; momentum "comparatively more resilient as costs increase" (from a related factor-compression paper).
- **"Crypto factor zoo (.Zip)" (IRFA 2026)**, https://www.sciencedirect.com/science/article/abs/pii/S1057521926000645 [UNVERIFIED]: combined selected factors beat the crypto benchmark out of sample.
- All cross-sectional; relevant only as "the 1–4 week horizon keeps showing up after 2021".

### 1.23 Le & Ruthbah (Monash), "Trend-following Strategies for Crypto Investors" (Aug 2023; SSRN 4551518)
- https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4551518 [UNVERIFIED]
- Trend following "performs well"; **65-day momentum beats 20-day for BTC on performance ratios** (one snippet) while the project page says "shorter lookbacks are effective in generating a high Sharpe" — conflicting summaries; "the effect of transaction costs is very substantial". No numbers retrieved. In-sample.

### 1.24 Rozario, Holt, West & Ng, "A Decade of Evidence of Trend Following Investing in Cryptocurrencies" (arXiv:2009.12155, Sep 2020)
- https://arxiv.org/abs/2009.12155 ; code https://github.com/Globe-Research/bittrends (README opened: title only) [UNVERIFIED]
- Walk-forward annualised return 255%, parameters optimised for Sharpe, capacity $323m; crypto behaves like commodities, bear-market diversifier. 2010–2020 sample dominated by early BTC; optimised; no rule retrieved. Not usable.

### 1.25 Gbadebo, "Momentum Trading in Cryptocurrencies: A Comparative Study of Time-Series and Cross-Sectional Strategies", BATP 33 (2026), DOI 10.15388/batp.2026.1
- https://www.journals.vu.lt/BATP/en/article/view/44540 ; PDF https://www.journals.vu.lt/BATP/en/article/download/44540/42590/138419 [UNVERIFIED]
- BTC, ETH, LTC, XRP, BNB, ADA, DOGE, SOL (8 coins incl. SOL — hindsight), 1 Jan 2020–31 Oct 2025, multi-horizon EMA signals normalised by vol: **TSM 31.96%/yr, beats CSM risk-adjusted; CSM maxDD 55%** with lower profitability because majors are highly correlated. No Sharpe, no cost schedule retrieved; accounting-journal venue; single author. In-sample. Confirms TSM > CSM on majors through 2025, nothing more.

### 1.26 Hubrich, "'Know when to hodl 'em, know when to fodl 'em'" (SSRN 3055498, 2017)
- https://www.semanticscholar.org/paper/3a919cb28d1b5a95e66a38e71882280b21685d49 [UNVERIFIED]. Weekly data, momentum = prior-week return; momentum the strongest of momentum/value/carry; 2015–2017. Pre-futures, in-sample.

### 1.27 Wisselink, "Time-series Momentum in the Cryptocurrency Market" (Erasmus BA thesis, 30 Aug 2018)
- https://thesis.eur.nl/pub/44390/Wisselink-NJ-483391-BA-thesis.pdf [UNVERIFIED]. Three TS rules (simple TSMOM, filter, PPO), daily rebalanced, 26 portfolios, each long-short and long-only: **85% of long-only portfolios earn significant positive excess returns; no long-short portfolio does.** Student work, 2018, but the cleanest long-only-vs-long-short decomposition found.

### 1.28 Shen, Urquhart & Wang, "Bitcoin intraday time series momentum", Financial Review 57(2) 2022
- https://onlinelibrary.wiley.com/doi/abs/10.1111/fire.12290 [UNVERIFIED]. First half-hour predicts last half-hour; liquidity-provision driven. **Intraday — outside scope (rejected family).**

### 1.29 Day-of-week / weekend (not intraday seasonality; relevant to a Monday 00:05 UTC weekly decision)
- Caporale & Plastun, "The day of the week effect in the cryptocurrency market", FRL 2019 (SSRN 3056229; CESifo WP 6716): BTC, LTC, XRP, DASH 2013–2017; **Monday effect for BTC only** (higher Monday returns); trading simulation not profitable. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3056229 [UNVERIFIED]
- Dorfleitner & Lung 2018: eight coins 2015–2018, **significantly lower (negative) Sunday returns**, tied to low volume. [UNVERIFIED, via literature review https://www.researchgate.net/publication/385694934]
- Baur, Cahill, Godfrey, Liu, "Bitcoin time-of-day, day-of-week and month-of-year effects": "no consistent or persistent patterns" across seven exchanges (already in repo). [UNVERIFIED]
- Xu 2025, "Bitcoin's Weekend Effect: Returns, Volatility, and Volume (2014–2024)": **no detectable weekend–weekday return gap** in the full sample or 2016–19 / 2020–23 / early-2024; volatility and volume lower at weekends. https://www.researchgate.net/publication/396418897 [UNVERIFIED]
- "Retail weekends, institutional weekdays: liquidity and return asymmetries in cryptocurrency markets", QREF 110 (2026) 102245, top-100 coins 2020–2024: robust **Saturday premium in speculative/low-priced tokens**; benchmark coins show Monday differential and a Wednesday effect; **Tuesday returns weaker, read as partial reversal of weekend price pressure**; Saturday anomaly faded during COVID, returned after. https://www.sciencedirect.com/science/article/abs/pii/S1062976926001407 [UNVERIFIED]
- Aharon & Qadan 2019 "Bitcoin and the day-of-the-week effect" (various effects); Qadan et al 2021 effects in 7 of 8 coins; Yaya & Ogbonna 2019 none in returns. [UNVERIFIED]
- Synthesis: the day-of-week literature is unstable in sign and sample; the only mechanism-consistent thread is **thin weekend liquidity → weekend price pressure → partial Monday/Tuesday reversal**, which would make a Monday-00:00-UTC entry buy into weekend moves. That is consistent with the repo finding that Monday is the worst of the seven decision days (Sharpe 1.12 vs up to 1.34) — but the repo chose not to exploit the weekday on purpose and no paper gives an after-cost rule, so **no candidate**.

### 1.30 Not found
- Swinkels "crypto momentum disappeared after the introduction of bitcoin futures": the Tinbergen abstract cited in the repo (https://utilities.tinbergen.nl/?p=66235) could not be re-found by search; keep as [UNVERIFIED] in the repo memo.
- Liu & Tsyvinski 2021 RFS published-version coefficients (only the NBER figures above).
- Any peer-reviewed paper isolating crypto TSM performance in 2022–2024 specifically; the closest are 1.12 (to Aug 2023), 1.18 (to 2026, preprint), 1.21 (post Jan 2024 split, preprint), and the galata replication (2023–26).

---

## 2. Synthesis by design dimension

| Dimension | What the crypto literature says | Repo evidence | Implication |
|---|---|---|---|
| Lookbacks | Published optimum clusters at **1–4 weeks** (Liu–Tsyvinski 1–4 wk; Han–Kang–Ryu 28d; Howden–Andreev 30d; Dobrynskaya 2–4 wk; Fičura–Colak 1–2 wk for liquid coins; 2-week factor survives OOS to 2023). Kang–Ryu (BTC): slow 12-week beats fast; Zarattini BTC gross: 5–30d Sharpe 1.55–1.66 > 60–360d 0.99–1.30 but the 5d collapses at 50 bps. | T3d: (10,30,60) 1.08 < (20,60,120) 1.12 < nothing slower; (20,) alone 0.90. | Ensemble is right; the 20d leg already carries the short horizon. A 14/28-day vote is the only academically motivated addition and the repo's own faster set did not help. |
| Holding / cadence | Han–Kang–Ryu 5-day holding optimal; Zenodo & MOP monthly; Zarattini daily with band. | Daily 1.25 vs weekly 1.12. | No change implied; the weekly book is close to the 5-day holding optimum. |
| Signal form | Papers use sign(return) (MOP), Donchian breakout + ratcheting mid exit (Zarattini), vol-normalised EMA (Gbadebo), speed-parameterised (Kang–Ryu). Baltas–Kosowski (futures) show continuous/t-stat signals cut turnover. | sign() of 3 lookbacks. | Two testable alternatives: Donchian ensemble; continuous vol-normalised signal. |
| Vol scaling | Per-asset (MOP, Zarattini 90d/25%) and strategy-level (Barroso–Santa-Clara: FRL 2025 1.12→1.42; Habeli: gains concentrated in momentum). Han–Kang–Ryu: TSM gain = downside reduction. | Per-asset 60d; TV leaves Sharpe unchanged; 30d window 1.16 vs 60d 1.12. | Portfolio-level scaling is the untested variant. |
| Filters | Howden–Andreev market-DD>15% halving: DD −44.6→−28%, Sharpe 1.41→1.53 (preprint). Kang–Ryu: adaptive speed adds nothing. | Regime filters rejected (200d: 1.18/−14.4% weekly; vol>70%: 1.02). | Low prior; only the market-drawdown-state version is new. |
| Universe | Momentum lives in large/liquid coins (Fičura–Colak, Zaremba, Begušić); survivor-only universes show no CS momentum (Grobys 2026); Zarattini's liquidity-ranked monthly rotation: Sharpe 1.57, DD 11%, survivorship-free. | Hindsight 9: 1.25 daily; ex-ante 24: 0.86. | A liquidity-ranked ex-ante universe is the honest fix; on Delta today it would drop ADA/LINK/BCH. |
| Long-only | Short leg is the crash source (Grobys 2025); long-only portfolios significant, long-short not (Wisselink). | 0.78 vs 1.25. | Keep long/flat. |
| Costs | Zarattini: 5d CAGR 34→18% at 50 bps; band on vol-changes recovers ~100 bps/yr; Han–Kang–Ryu: frictions wipe many portfolios; Le–Ruthbah: "very substantial". | 7.31 bps/side; fees 0.25–1.14%/yr; funding 2–3.4%/yr. | Fees are not the binding cost here; funding is (no paper models Delta-level funding). |
| Post-2021 | TSM still positive but the Sharpe edge over buy-and-hold is small or gone (galata 0.97 vs 0.975, 2023–26); DD halving persists everywhere; Zenodo post-ETF 1.22 vs 0.82 (n.s.); Barclay crypto CTA index −12.3% in 2025. | 2022–23 0.35; 2025–26 0.26–0.49. | Expect shape (DD control), not Sharpe. Any candidate must be judged on DD/Calmar as much as Sharpe. |

---

## 3. Candidates (exact rules; see structured output for the same list)

C1 Donchian-channel ensemble with ratcheting mid-line exit (signal). C2 Portfolio-level (Barroso–Santa-Clara) variance scaling on top of per-asset scaling (sizing). C3 Continuous vol-normalised trend signal replacing sign() (signal; turnover). C4 Liquidity-ranked ex-ante rotating universe (universe). C5 Add a 14- and 28-day vote to the ensemble (signal; short horizon). C6 Market-drawdown crash-state de-risking (overlay). Prior plausibility: C1 3, C2 3, C3 3, C4 3, C5 2, C6 2.

Warm-up note for C1/C5: Binance USDT-M alts start Jan–Feb 2020; a 360-day channel means the first full ensemble signal is ~Feb 2021, so the 2020 melt-up drops out of the C1 backtest. Run C1 both with the paper's nine lookbacks and with the seven ≤250-day lookbacks, and state both.

---

## 4. Considered and not proposed
- Volume-weighted TSMOM (1.19): definition unknown, 3,000-coin daily long-short, weighting flips the sign — not a rule for 9 majors.
- AdaptiveTrend (1.17): 6h bars, 150 pairs, shorts, vendor OOS claims; the rolling-Sharpe asset filter is signal-of-signal selection (rejected family: signal stacking).
- Slower lookback weighting (Kang–Ryu): T3d (50,100,200) 0.95 already rejects it in our data.
- Weekday / weekend timing (1.29): rejected family; literature unstable; recorded as a mechanism for why Monday is the worst day.
- Short leg: all evidence against.
- Zarattini-style band on vol-driven changes only: the repo already tested a 10% band on the daily book (Sharpe unchanged, trades 1,773→538); the paper's refinement (band only on vol changes, trade signal changes at once) is a minor variant worth a line in the C1 implementation notes, not a candidate on its own.
- Per-position stops: rejected; C1's mid-line exit is a trend-definition exit, flagged as a cousin.

---

## 5. Venue facts checked live (api.india.delta.exchange, 2026-10-21, [VERIFIED])
- `/v2/tickers?contract_types=perpetual_futures`: 237 perpetuals; fields include `turnover_usd`, `volume`, `oi_value_usd`, `contract_value`.
- 24h turnover ≥ $2M: 28 perps; ≥ $1M: 42; ≥ $0.5M: 56. Top by turnover: BTCUSD $1,071M, ETHUSD $714M, XAUTUSD $697M (gold), SOLUSD $150M, PAXGUSD $135M (gold), BRUSD $33M, ARIAUSD $22M, AKEUSD $19M, ZECUSD $16M, XRPUSD $12M, GTCUSD $11M, UNIUSD $10.5M, … DOGEUSD $3.7M (#19), AVAXUSD $2.3M (#25), BNBUSD $2.3M (#26), LTCUSD $1.7M (#29). ADAUSD, LINKUSD, BCHUSD are below $1.67M/day. Several high-turnover perps are commodities/stocks (XAUT, PAXG, OIL, SNDKB, SOXLB, QQQX, TSLAX, SPCXX) or sub-year listings (BR, ARIA, AKE, ARC, ALT, BMT), so a liquidity rotation needs an asset-class filter and a listing-age filter (Zarattini's ≥365 days).
- Daily candles: `/v2/history/candles?resolution=1d` is what `trend_backtest.py::load_delta` already pulls; whether the cache keeps the `volume` field is [UNVERIFIED] (the loader was not run).
