# Angle: signal construction in the academic time-series-momentum literature

Date 2026-10-20 (search run 2026-10-21 UTC). Scope: exact alternatives to the live rule
`signal_i = mean(sign(P_t/P_{t-L} - 1) for L in (20, 60, 120))`, floored at 0, from
`cex-mm/scripts/trend_backtest.py::target_weights` (read, not modified).

Sourcing: WebFetch/curl reached only raw.githubusercontent.com (arxiv, ssrn, aqr, man.com,
cmegroup, duke.edu, cbs.dk, qoppac, quantpedia, alphaarchitect all return proxy 403 — probed with
curl, codes logged below). So every paper-level number comes from search-result summaries and is
tagged [UNVERIFIED] unless the text was read from a raw GitHub file (tagged VERIFIED-CODE).
Numbers from the repo's own evidence (`backtest_results.md`) are tagged REPO.

Proxy probe (curl -m 12, HTTP code): arxiv.org 403, people.duke.edu 403, man.com 403,
qoppac.blogspot.com 403, quantpedia.com 403, alphaarchitect.com 403, cmegroup.com 403,
research.cbs.dk 403, api.semanticscholar.org 403, export.arxiv.org 403,
raw.githubusercontent.com 200.

## 0. What the repo already established (REPO, read-only)

- Rule under test, weekly design TV 0.25 band 10%: Sharpe 1.12 (2020-05..2026-09, Binance proxy),
  maxDD -16.9%; daily TV 0.40: Sharpe 1.25, maxDD -22% (daily -14.1% at TV 0.25 line).
- T3d lookbacks (weekly line): (20,60,120) 1.12 · (10,30,60) 1.08 · (50,100,200) 0.95 ·
  (20,) 0.90 · (60,) 0.92 · (120,) 1.21 (but 2025 -3.1%). T3e vol window 30/60/90: 1.16/1.12/1.08.
- Most of the Sharpe is vol-scaled long beta; the signal adds ~0.1-0.2 Sharpe and halves DD
  (-16.9% vs -36.6% always-long vol-scaled). Ex-2020-21 Sharpe 0.66; 2025-26 0.26.
- Already rejected: single lookback, no vol targeting, regime filters, stops, shorts, ML,
  changing decision day/hour. Not yet tested: continuous signals, EWMA crossovers,
  breakout/channel rules, wider lookback ensembles (250+), skip-recent-days, turning-point
  aggregation. The repo's `practitioner_strategies.md` already cites Zarattini et al. (Donchian
  ensemble) but it was never backtested in-house.
- Practical constraint that dominates this angle: at $1,000 and TV 0.25/9 per coin with coin vol
  ~0.6, the per-coin target is ~$46, below one BTC contract (~$80) and one BNB contract (~$73).
  Any *continuous* signal therefore rounds to 0 or 1 contract on most coins; graded exposure only
  exists at ~$5k+. Binary rules (sign, breakout) lose nothing from rounding that the current rule
  does not already lose.

## 1. Sources, what each says, verification status

### 1.1 Baltas & Kosowski — "Demystifying / Improving Time-Series Momentum Strategies"
- URLs: https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf ;
  https://www.cmegroup.com/education/files/improving-time-series-momentum-strategies.pdf ;
  https://spiral.imperial.ac.uk/server/api/core/bitstreams/93f06c22-150a-4240-8115-912988dd2c67/content ;
  https://www.returnstacked.com/academic-review/demystifying-time-series-momentum-strategies-volatility-estimators-trading-rules-and-pairwise-correlations/
  (all 403; [UNVERIFIED] from search summaries)
- TREND rule (2017 version): Newey-West t-statistic of daily futures log-returns over the past
  12 months; signal = t if |t| < 1, else sign(t) (bounded at ±1). Economic reading: the t-stat is
  the asset's realised 12-month Sharpe, HAC-adjusted. 2015 version used the t-stat of the slope
  of an OLS time trend on daily log prices instead.
- Claimed effect: Sharpe "insignificantly different" from SIGN (one later version says SIGN
  slightly higher); turnover reduction reported as ~24% (returnstacked summary) in one version and
  "about two-thirds" in another search summary — conflicting, both [UNVERIFIED]. Combining
  Yang-Zhang OHLC vol with TREND cuts trading costs ~35% [UNVERIFIED].
- Pairwise-correlation adjustment CF = sqrt(N / (1 + (N-1) rho_bar)) applied to the vol-target
  weights: full-sample Sharpe 1.15 -> 1.19; 2009-2013: 0.14 -> 0.29 [UNVERIFIED]. Vol-window:
  Sharpe maximised at a 3-month estimation window [UNVERIFIED]. Sample: ~75 futures, 1974-2013
  [UNVERIFIED, from memory of the paper].

### 1.2 Garg, Goulding, Harvey, Mazzoleni — "Momentum Turning Points" (JFE 2023) and
### Goulding, Harvey, Mazzoleni — "Breaking Bad Trends" (FAJ 2023/24)
- URLs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3489539 ;
  https://people.duke.edu/~charvey/Research/Published_Papers/P158_Momentum_turning_points.pdf ;
  https://people.duke.edu/~charvey/Research/Published_Papers/P167_Breaking_bad_trends.pdf ;
  https://www.aeaweb.org/conference/2021/preliminary/powerpoint/ihbRDkeH ;
  https://alphaarchitect.com/momentum-trends/ ; https://quantpedia.com/trend-breaks-in-trend-following-strategies/ ;
  https://www.cxoadvisory.com/momentum-investing/handling-reversals-in-price-trend-direction/
  (all 403; [UNVERIFIED])
- Rule: SLOW = sign(12-month return), FAST = sign(1-month return) (one summary says 2-month for
  the futures paper). States: Bull (+,+), Bear (-,-), Correction (SLOW+, FAST-), Rebound (SLOW-,
  FAST+). Static "intermediate speed" = w*FAST + (1-w)*SLOW. Dynamic: after a Correction month
  tilt to SLOW; after a Rebound month tilt to FAST (sign of the tilt set by historical mean return
  in that state).
- Claimed: intermediate-speed Sharpe > average(SLOW, FAST) in all 20 international equity markets
  (Datastream, mostly from 1980); static speed Sharpe table 0.38, 0.41, 0.48, 0.51, 0.44, 0.34
  (MED best, 0.51); DYN 0.52 gross 1969-2018 vs 0.51 static equal weight (cxoadvisory);
  2004-2018 window DYN 0.61 vs best static 0.57; DYN beats best static in most countries;
  "predictably negative returns when both signals are negative" (Bear). Breaking Bad Trends:
  55 futures/forwards/swaps, dynamic strategy earns in months after turning points where the
  static earns ~0; more frequent breaks post-2008 explain weaker trend returns. Multi-asset
  Sharpe for dynamic vs static NOT retrieved. All [UNVERIFIED].
- Reading for us: the paper endorses a static blend of speeds (what the rule already is); the
  dynamic layer adds 0.01-0.06 Sharpe in equities. Kang & Ryu 2026 (BTC, below) find dynamic
  speed adds little beyond a slow rule.

### 1.3 Levine & Pedersen — "Which Trend Is Your Friend?" (FAJ 2016, 72(3) 51-66)
- URLs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2603731 ;
  https://research.cbs.dk/files/60084063/lasse_heje_pedersen_et_al_which_trend_is_your_friend_publishersversion.pdf ;
  https://www.aqr.com/Insights/Research/Journal-Article/Which-Trend-Is-Your-Friend (403; [UNVERIFIED])
- TSMOM and moving-average crossovers are equivalent representations in their most general
  forms (also HP and Kalman filters: all linear filters). Three TSMOM (1, 3, 12 month) vs three
  comparable MACROSS strategies under the same portfolio construction: "perform similarly for all
  horizons" in return, vol and Sharpe; small deviations; some TSMOM alphas vs MACROSS significant.
  Per-horizon Sharpe table not retrieved.

### 1.4 Hurst, Ooi, Pedersen — "A Century of Evidence on Trend-Following Investing" (JPM 2017)
- URLs: https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing ;
  https://fairmodel.econ.yale.edu/ec439/hurst.pdf ; https://static.twentyoverten.com/593e8a9e7299b471eaecf644/SkLoGL67M/A-Century-of-Evidence-on-Trend-Following-Investing.pdf (403; [UNVERIFIED])
- Rule: equal-weighted combination of 1-, 3-, 12-month TSMOM signals, each position vol-scaled,
  67 markets (29 commodities, 11 equity indices, 15 bonds, 12 FX), Jan 1880 - Dec 2016; positive
  in every decade; 8 of 10 largest 60/40 drawdowns. Exhibit 2 gives gross Sharpe per signal and
  per signal lagged one month — values NOT retrieved. Net average Sharpe per market ~0.4.

### 1.5 Moskowitz, Ooi, Pedersen 2012 (JFE 104, 228-250)
- URLs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463 ;
  https://research-api.cbs.dk/ws/portalfiles/portal/58851003/time_series_momentum_lasse_heje.pdf ;
  https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data (403; [UNVERIFIED])
- Rule: sign of past 12-month excess return, position 40%/sigma (ex-ante vol), 1-month hold,
  58 futures 1985-2009. Panel regression: all 12 monthly lags positive (9 significant), lags
  beyond 12 months mostly negative (persistence 1-12 months, partial reversal after). 12-month
  TSMOM positive for every one of 58 contracts. Lookback x holding t-stat table not retrieved;
  secondary: 1- and 3-month lookbacks positive but weaker.

### 1.6 Man AHL — "The Need for Speed in Trend-Following Strategies" (Mackic, 2023)
- URLs: https://www.man.com/insights/need-for-speed-trend-following ;
  https://hedgenordic.com/2023/03/the-need-for-speed-in-trend-following-strategies/ (403; [UNVERIFIED])
- Risk-adjusted return rises with slower speed; skew (crisis alpha) improves with faster speed;
  costs hit fast models' Sharpe "significantly" while skew survives. Across S&P 500 quintiles,
  average return peaks at "Slow", but in the worst quintile "Fast" speeds do best. No exact
  speed-Sharpe table in the summaries.

### 1.7 Carver — EWMAC and breakout rules (pysystemtrade; VERIFIED-CODE)
- https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/systems/provided/rules/ewmac.py
  (fetched): raw_ewmac = price.ewm(span=Lfast).mean() - price.ewm(span=Lslow).mean();
  forecast = raw_ewmac / vol, vol = robust_vol_calc(price.diff(), 35) (35-day vol of daily price
  differences, price units). Defaults Lfast=32, Lslow=128 (with vol) or 16/32 (no-vol variant).
  Unscaled, uncapped in that file.
- https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/systems/provided/rules/breakout.py
  (fetched): roll_max/roll_min over `lookback` closes (min_periods ceil(lookback/2));
  roll_mean = (roll_max + roll_min)/2; output = 40 * (price - roll_mean)/(roll_max - roll_min);
  smoothed with ewm(span = max(int(lookback/4), 1)). Default lookback 10.
- Forecast scalars (secondary, [UNVERIFIED]): Systematic Trading: EWMAC 8/32 = 5.3, 16/64 = 3.75,
  32/128 = 2.65; AFTS: EWMAC2 12.1, 4: 8.53, 8: 5.95, 16: 4.10, 32: 2.79, 64: 1.91. Forecasts
  capped at ±20, average absolute forecast 10 = full vol-target position. Book worked example:
  three EWMAC variations 16/64, 32/128, 64/256 with weights 42/16/42 within trend.
  https://github.com/i-osipchyk/systematic-trading-framework ; https://github.com/majkong14/advanced-futures-notes ;
  https://the7circles.uk/systematic-trading-3-frameworks-and-forecasts/
- Carver blog (https://qoppac.blogspot.com/2016/05/a-simple-breakout-trading-rule.html, 403,
  [UNVERIFIED]): breakout10 vs EWMAC(2,8) correlation ~0.93 at matched lookbacks; average
  cross-correlation breakout x EWMAC 0.58; within-breakout 0.49, within-EWMAC 0.55; expected
  "small, probably not significant" gain from adding breakouts to EWMAC+carry. AFTS summary:
  faster than EWMAC(4,16) too expensive for most instruments; slower than EWMAC(64,256) too
  correlated with long-only [UNVERIFIED].

### 1.8 Baz, Granger, Harvey, Le Roux, Rattray 2015 — MACD trend signal (SSRN 2695101)
- Formula VERIFIED-CODE from https://raw.githubusercontent.com/kieranjwood/trading-momentum-transformer/master/mom_trans/classical_strategies.py
  (the Lim/Zohren/Roberts and Wood et al. reference implementation): pairs (8,24), (16,48),
  (32,96); EWMA with halflife = log(0.5)/log(1 - 1/timescale); macd = ewm_S(P) - ewm_L(P);
  q = macd / rolling_std_63(P); y = q / rolling_std_252(q); signal = y * exp(-y^2/4) / 0.89;
  final = mean over the three pairs. Same file: TSMOM = sign(252-day return), vol target 15%,
  60-day EWM std of daily returns, lagged one day; blended monthly/annual sign variant.
- Lim, Zohren, Roberts 2019 (JFDS 1(4) 19-38; https://arxiv.org/abs/1904.04912 ;
  https://oxford-man.ox.ac.uk/wp-content/uploads/2020/03/Enhancing-Time-Series-Momentum-Strategies-Using-Deep-Neural-Networks.pdf ;
  403, [UNVERIFIED] via https://github.com/jjakimoto/research-issues/issues/1869): 88 futures,
  portfolio vol-scaled to 15%, zero cost: Sgn(12m return) Sharpe 1.392 (ret 0.215, vol 0.154,
  MDD 0.264); MACD trio 1.111 (0.172, 0.155, 0.317); Long-only ~0.6 (0.628 in the 10 bp cost
  table). So the continuous MACD trio UNDERperformed the 12-month sign rule on the same
  universe (note: different speeds, 8-96-day EWMAs vs 12 months).

### 1.9 Sepp & Lucic — "The Science and Practice of Trend-Following Systems" (arXiv 2607.19497,
### SSRN 3167787) and companion repo (VERIFIED-CODE/docs)
- Docs fetched: https://raw.githubusercontent.com/ArturSepp/TrendFollowingSystems/405871df74923634f1b1eb38e53cfcfa7fd7aa60/docs/tsmom_system.md ,
  .../docs/european_system.md , .../docs/case_study_futures_evidence.md ;
  README via https://raw.githubusercontent.com/solknight48/TrendFollowingSystems/main/README.md (fork).
- Three designs: European = continuous, variance-preserving EWMA (single span or long-short
  LS(nu1,nu2)) of z_t = r_t/sigma_{t-1} (EWMA vol span 33), w = S * sigma_target/(sqrt(af) sigma_t),
  signal cap 3, weight cap 5. American = binary fast/slow price-EWMA crossover with ATR entry
  buffer and ATR trailing stop, size fixed at inception. TSMOM = generalised MOP:
  b = sum of L daily sign(r_t/sigma_{t-1}); S = (1/sqrt(ML)) * sum of the last M blocks;
  E[S]=0, Var[S]=1 under independence (Rademacher); w = S * sigma_target/(sqrt(af) sigma);
  rebalanced every L days; defaults L=10, M=10; paper recommends weekly-monthly rebalancing,
  L in 5..30.
- Sign-filter discount (Bussgang): E[sign(S) z] = sqrt(2/pi) E[S z] ~ 0.80: a sign signal keeps
  ~80% of the signal-return covariance of the linear signal at the same variance. Empirically the
  European closed form predicts realised Sharpe across 84 contracts with corr 0.99 / slope 0.96;
  TSMOM corr 0.89 / slope 0.73 (close to the 0.80 benchmark); American corr 0.92 / slope 0.61.
- 84 futures, 7 asset classes, 1959-2026; grid 1997-2026 (long spans 30..500, short 5..100;
  TSMOM M in 3..27): European LS(250,20) "reasonable" with realised costs 1.7%/yr; American best
  ~250/20; TSMOM best ~M=L=10. Vs SG Trend Index 2000-2026 (net of costs and 2/20 fees, monthly):
  European 0.47, American 0.50, TSMOM 0.55, SG Trend 0.47; Ledoit-Wolf p 0.96/0.82/0.62 — no
  significant difference ("failing to reject is not evidence of equivalence"). Correlation of
  each with SG Trend ~0.80; European vs American ~0.95. Vol-normalised turnover 300-400%/yr for
  European and TSMOM vs 125-200% for American (stateful entry/stop design is ~50% cheaper).
  LS(250,20) with 15% portfolio vol target, 1960-2026: Sharpe 1.10 at 15.2% vol, net of costs,
  gross of fees. Autocorrelation channel median 0.55 at 5 days falling to 0.33 at two years;
  drift channel adds up to 0.08, growing with span. Median skewness 2.33 at 55 days.

### 1.10 Zakamulin & Giner — "Trend following with momentum versus moving averages: a tale of
### differences" (Quantitative Finance 2020, 20(6) 985-1007)
- URLs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3293521 ;
  https://www.ingentaconnect.com/content/routledg/quant/2020/00000020/00000006/art00008 (403; [UNVERIFIED])
- MOM rule = sign(P_t - P_{t-n}) (our rule). MA rules have "more robust forecast accuracy of the
  future direction of price trends" and gain under uncertain market dynamics; similarity between
  MOM and MA rises with trend strength; MA indicators have higher maximum correlation with the
  next return except for small n where MOM is higher. Equity-index data (S&P 500 monthly, long
  history) [UNVERIFIED detail].

### 1.11 Etienne, Ohana, Benhamou, Guez, Setrouk, Jacquot — "Revisiting the Structure of Trend
### Premia: When Diversification Hides Redundancy" (arXiv 2510.23150, Oct 2025; Ai For Alpha)
- URLs: https://arxiv.org/abs/2510.23150 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5665752 (403; [UNVERIFIED])
- Horizons 20, 60, 125, 250, 500 days; Bayesian-optimised horizon weights per asset; the 125-day
  layer "contributes very little" once 20/60 and 250/500 are in; excluding it "consistently
  improves Sharpe ratios and drawdown-adjusted performance" at the same benchmark correlation
  ("barbell"). Vendor-affiliated, numbers not retrieved.

### 1.12 Valeyre — "Breaking the Trend: How to Avoid Cherry-Picked Signals" (arXiv 2504.10914)
- https://arxiv.org/abs/2504.10914 (403; [UNVERIFIED]). Empirical Sharpe fits the Grebenkov &
  Serror (2014) closed form; "using only one simple EMA appears optimal to capture the trend";
  large indicator baskets expose to cherry-picking. Single author, not peer reviewed.

### 1.13 Intermediate momentum / skipping recent returns
- Novy-Marx 2012 (12-7 month returns) via Ehsani & Linnainmaa
  https://www.aeaweb.org/conference/2020/preliminary/paper/RHhbnykd and
  https://arxiv.org/pdf/2304.03437 (403; [UNVERIFIED]): intermediate momentum (t-12..t-7) carries
  the premium in US equities; in the factor-momentum paper its t-stat is only 1.64. All
  cross-sectional equities; nothing on futures or crypto.
- Crypto evidence points the other way: Liu & Tsyvinski (NBER w24877): BTC daily return positively
  predicts 1-, 3-, 5-, 6-day-ahead returns; weekly return predicts 1-4 (up to 8) weeks ahead
  [UNVERIFIED]. Dobrynskaya (HSE): cross-sectional momentum up to 2-4 weeks, reversal after ~1
  month (value-weighted, ~2,000 coins, 2014-2020) [UNVERIFIED]. No paper found that tests a
  skip-week in crypto TSMOM.

### 1.14 Crypto-specific speed evidence
- Kang & Ryu, "Time-series momentum and market timing in Bitcoin", Risk Management 28(3), 2026
  https://ideas.repec.org/a/pal/risman/v28y2026i3d10.1057_s41283-026-00234-7.html [UNVERIFIED]:
  slow signals (12-week baseline) outperform intermediate and fast; fast signals overreact to
  noise; dynamic speed adjustment "adds little beyond a simple low-speed rule"; speed acts as an
  endogenous risk-management device.
- Han, Kang & Ryu / AUT working paper (realistic assumptions)
  https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
  [UNVERIFIED]: best TS momentum 28-day lookback / 5-day holding, Sharpe 1.51 vs market 0.84,
  gain mainly from reduced downside; best cross-sectional 14-day/7-day Sharpe 1.28; TS strong,
  CS weak after costs and daily liquidation.
- Le & Ruthbah (Monash, SSRN 4551518) https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf
  [UNVERIFIED]: lookbacks 20, 65, 150, 200 days on MegaCap indexes; 20 and 65 beat 150/200 on
  every ratio; transaction costs "very substantial".
- Rozario et al., "A Decade of Evidence of Trend Following Investing in Cryptocurrencies"
  (arXiv 2009.12155) [UNVERIFIED]: BTC 2011-2019 hourly, walk-forward, no costs: best full-period
  Sharpe SMA 1.09, EMA 1.35, DEMA 1.32; SMA ~10 and ~40 days "consistently perform well";
  255%/yr walk-forward with negligible costs assumed.
- Man Institute "In Crypto We Trend" https://www.man.com/insights/in-crypto-we-trend
  [UNVERIFIED]: MA-crossover model (example 50 vs 200 day), risk shared equally, net of costs:
  optimum ~10-15 coins; individual-market Sharpe positive but small.
- Harvey et al. "An Investor's Guide to Crypto" (JPM 2022) [UNVERIFIED]: vol targeting effective;
  vol-scaled BTC left tail more benign than S&P.
- Zarattini, Pagani, Barbon, "Catching Crypto Trends" (SSRN 5209907, SFI 25-80, Apr 2025)
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907 ;
  https://concretumgroup.substack.com/p/catching-crypto-trends ;
  https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/ (403;
  [UNVERIFIED]). Rule as read by three independent GitHub replications (VERIFIED-CODE that they
  agree; the paper itself not opened):
  https://raw.githubusercontent.com/sercanatalik/galata-research/29d35e1ffee5d26d9700de9d890a2f9d0693725a/planning/preregistered/donchian-ensemble.md ,
  https://raw.githubusercontent.com/rgriesel/pionex/954f889a151107ca0ccf88c6ba07e55bfee09219/pionex_lab/swing/donchian.py ,
  https://raw.githubusercontent.com/imikerussell/beebots/6cf999a224e67c7e2b6a74be0a064c409523d519/strategies/BREEZY_BEE.md :
  L in {5,10,20,30,60,90,150,250,360}; per L: enter long when close = highest close of the last
  L days; stop initialised at Mid_L = (max close + min close)/2 and ratcheted up to max(stop,
  Mid_L); exit when close <= stop (exit checked before entry); signal = fraction of the nine
  channels that are long; size = signal x min(1, 0.25/sigma_90d) (one reading: leverage cap 2x);
  long only; daily closes. Claimed (abstract + Concretum summary): BTC-only from Jan 2015: net
  CAGR 30%, Sharpe 1.56, maxDD 19% vs >80% passive; top-20 liquid rotation: net CAGR 18%, maxDD
  11%, Sharpe >1.5, alpha 10.8%/yr vs BTC; costs 0.10/0.25/0.50% tested. Independent
  pre-registered replication (galata-research, BTC+ETH, traded bars 2023-02-26..2026-10, taker
  4.5 bps, no funding): sized ensemble Sharpe 0.966 vs buy-and-hold 0.975, DSR 0.921 (N=4),
  PBO 0.631 -> "not supported on this record" (3.6-year sample, one cycle).

### 1.15 Other
- Trend-Following via Dynamic Momentum Learning (Levy & Lopes, arXiv 2106.08420) [UNVERIFIED]:
  dynamic combination/selection of lookbacks improves performance, maxDD 13.1% vs 25.3% naive;
  raises turnover. ML-adjacent (rejected family).
- Slow Momentum with Fast Reversion (Wood, Roberts, Zohren, arXiv 2105.13727) [UNVERIFIED]:
  changepoint detection + LSTM; rejected family (ML).
- Liu & Tsyvinski / Liu, Tsyvinski & Wu: see repo notes `academic_factor_evidence.md`.

## 2. Synthesis

1. Signal SHAPE at matched speed is a second-order effect. Levine-Pedersen (equivalence, similar
   Sharpe at every horizon), Sepp-Lucic (three designs indistinguishable by Ledoit-Wolf on 84
   futures 2000-2026), Carver (breakout vs EWMAC 0.93 correlated at matched speed), Baltas-Kosowski
   (TREND ~ SIGN in Sharpe) all agree. The theory (Bussgang) says a linear signal keeps 25% more
   signal-return covariance than its sign, but realised net numbers do not show it (TSMOM 0.55 >
   European 0.47) because turnover, caps and costs eat it.
2. What shape DOES change: turnover (TREND -24% to -66%; stateful breakout-with-stop ~50% lower
   vol-normalised turnover than EWMA/TSMOM), skew (faster/stateful = more positive), and
   exposure in weak trends (continuous signals hold less when t-stat < 1, which also cuts funding
   paid on longs — the real running cost here, 2-3.4%/yr).
3. SPEED: the cross-asset literature says slower = higher Sharpe, faster = better skew/crisis
   alpha and higher costs; combining speeds beats any single speed. Crypto-specific evidence
   clusters at 3-13 weeks (AUT 28d, Monash 20/65d, Kang-Ryu 12-week slow beats fast, Rozario
   10/40-day MAs gross of costs), i.e. inside the live 20/60/120 window. No evidence that 1-4
   week lookbacks dominate net of costs; Kang-Ryu finds the opposite for BTC; the repo's own
   (10,30,60) is 0.04 Sharpe below (20,60,120). Longer (250+) sleeves are endorsed by the
   barbell paper and HOP/MOP for futures, but crypto's momentum horizon is compressed (Liu-
   Tsyvinski persistence 1-8 weeks then partial reversal; Dobrynskaya reversal after ~1 month
   cross-sectionally) and the repo's (50,100,200) set scored worst — so a 250-day sleeve is a
   coin flip with thin data (Delta alts have 250 closes only since 2025-01).
4. SKIPPING recent days: equities-only evidence; crypto daily/weekly autocorrelation is positive
   at 1-6 days and 1-8 weeks, so a skip would delete signal. Do not test unless as a control.
5. TURNING-POINT / dynamic speed: equities gain 0.01-0.06 Sharpe; BTC "adds little". The static
   blend the rule already uses is what this literature recommends. A long-only "long unless all
   signals negative" variant is the natural crypto reading (Han-Kang-Ryu: "losers rebound
   sharply") but is mostly a leverage-up in ambiguous states — expect higher return, worse DD,
   little Sharpe.
6. The one crypto-native rule with a credible cost-aware backtest that the repo never tested is
   the Donchian ensemble (Zarattini). Its independent short-sample replication failed. It is the
   best-defined candidate for Phase 2 precisely because it is binary (survives $1k rounding),
   spans 5-360 days, and has lower turnover by construction.

## 3. Candidate rules (exact) — see StructuredOutput for the one-line specs

C1 TREND t-stat (Baltas-Kosowski) per lookback, averaged, floored at 0.
C2 EWMAC ensemble (Carver 16/64, 32/128, 64/256; optional 8/32), capped, floored at 0.
C3 Donchian ensemble (Zarattini), nine lookbacks, ratcheting midpoint stop, fraction long.
C4 Vol-normalised linear LS(250,20) EWMA of z (Sepp-Lucic European), clip, floor at 0.
C5 Baz MACD trio with response function, floored at 0.
C6 Barbell lookbacks (20, 60, 250) or (20, 60, 120, 250).
C7 Turning-point long-only aggregation: max(signs) instead of mean (or Correction-weighted).
C8 Skip-recent-days (k = 5): documented negative, control only.
C9 (adjacent, sizing) Baltas-Kosowski pairwise-correlation factor CF on the vol-target weights.

## 4. Implementation notes common to all

- All candidates need only daily closes already cached (Binance 2020-05.., Delta 2024-04..);
  none needs OHLC, funding or volume. C9 needs the 9x9 daily return correlation (closes).
- Keep the pre-registered protocol of `backtest_results.md`: Binance 2020-05..2026-09 with the
  2020-05..2023-12 / 2024-01..2026-09 split, the 24-perp ex-ante universe, Delta 2024-08..,
  weekly Monday and daily cadence, same costs (7.31 bps/side, Binance funding), whole contracts
  at $1,000 and $5,000. Count every variant as a trial for the DSR.
- Rounding: at $1,000 the per-coin target (~$46 at TV 0.25) is below one BTC/BNB contract, so
  continuous signals (C1, C2, C4, C5) will behave like binary ones there; judge them at $5,000
  and on the unrounded series, and report turnover and funding/yr, not just Sharpe.
- Expected direction from the literature: C1/C2/C4/C5 = Sharpe within noise of the baseline,
  turnover and funding lower (that is the win to look for); C3 = different speed mix plus lower
  turnover, the only candidate with a crypto-specific claim above the baseline; C6 = unknown,
  data-thin; C7 = higher CAGR and DD, Sharpe ~flat; C8 = worse.
