# Angle: volatility targeting and risk sizing — research notes (2026-10-21)

Scope: exact alternatives to the live rule's `weight_i = sig_i * (TV/N) / max(vol60_i, 0.05)`, gross cap 2x.
Proxy for fetchability: arxiv/ssrn/blogs/journals are all BLOCKED by the sandbox proxy; only raw.githubusercontent.com,
data.binance.vision and api.india.delta.exchange open. Everything from a search snippet is tagged [UNVERIFIED].

## 0. Local facts (verified, read from the repo)

- `cex-mm/scripts/trend_backtest.py::target_weights` (lines 125-140): vol_i = sqrt(365 * mean of 60 squared daily log returns)
  (no mean subtraction, no EWMA), floor 0.05, weight = sig * (TV/n)/vol, n = number of coins with full history,
  gross cap MAX_GROSS=2.0 rescales proportionally.
- `backtest_results.md` (2026-10-13 evidence):
  - T3e vol window 30/60/90 (weekly Mon TV0.25 band10): Sharpe 1.16 / 1.12 / 1.08; DD -15.6 / -16.9 / -17.0; 2024-26 Sharpe 0.91/0.86/0.83.
    Shorter is monotonically better, by a small margin, in both halves of the sample.
  - T3g gross cap 1.0 vs 2.0: identical (max gross 0.56x at TV0.25, 0.88x at TV0.40) -> cap never binds.
  - T3a TV 0.15..0.40: Sharpe flat 1.12-1.13; DD and worst day linear in TV. Realized vol at TV0.25 is 12.4% (TV0.40: 18.7%),
    i.e. ~half the nominal target because the rule is flat 16% of days and signals are often 1/3 or 2/3.
  - T6: vol-scaled always-long 9-coin basket at the same nominal TV0.25 realizes 23.0% vol, Sharpe 0.99, DD -36.6%
    -> with all nine long the per-asset-sum method realizes ~0.92x nominal TV, so average pairwise correlation is ~0.85.
  - T3j regime filters (BTC<200d, BTC 30d vol >70%/>90% -> flat): rejected (1.18 same DD-ish / 1.02 / 1.00).
  - calc/d2_checks2_output.txt: drawdown de-leveraging mult=clip(1-dd/dd_max,0.25,1): Sharpe 1.13-1.23 vs 1.25 -> rejected.
  - 2026-10-08 memo: TV does not change Sharpe (25/40/60% -> 1.25 each); single lookback / no vol targeting rejected
    (no vol targeting Sharpe 1.04-1.08, DD -35..-54%).
- Implication: the sizing layer is where most of the Sharpe lives (signal adds 0.1-0.2); vol targeting's job here is
  drawdown control, not alpha. Any candidate must be judged on DD / tail / turnover at equal Sharpe, not on Sharpe alone.

## 1. Core literature (all from search snippets unless marked; PDFs at duke.edu / cmegroup / ssrn / arxiv did NOT open: ENOTFOUND via proxy)

### 1.1 Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, van Hemert (2018) "The Impact of Volatility Targeting", JPM 45(1) 14-33
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538 ; https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf (fetch failed) [UNVERIFIED]
- 60+ assets, daily data from 1926 to 2017. Rule: position = target vol / forecast vol (1/sigma, not 1/sigma^2).
- Sharpe: rises only for "risk assets" (equities, credit) and portfolios heavy in them (60/40, risk parity); negligible for bonds, FX,
  commodities. US equities 0.40 unscaled -> 0.48-0.51 scaled [UNVERIFIED snippet]. Attributed to the leverage effect (vol up after losses).
- Tails: across ALL asset classes vol targeting cuts the probability of extreme returns and the vol-of-vol; both tails are cut.
- Window: the snippets did not give the window comparison. Quantpedia/Man summaries describe a short (about 1-month) realized-vol window
  as the standard; the paper's own window table could not be opened [UNVERIFIED].
- Follow-up critique (Bongaerts et al 2020): conventional vol targeting raised expected shortfall in 8/10 international equity markets, blamed on ex-post scaling.
- RELEVANCE: crypto has an INVERTED leverage effect (Baur & Dimpfl 2018 below), so the Sharpe channel is doubtful; the tail channel is what we have (local: DD halves).

### 1.2 Moreira & Muir (2017) "Volatility-Managed Portfolios", JF
- https://www.nber.org/system/files/working_papers/w22208/w22208.pdf [UNVERIFIED]
- w_t = c / RV^2_{t-1} where RV^2 is the realized VARIANCE of daily returns in the previous month (about 22 days); c set so unconditional vol matches buy-and-hold.
- Sharpe up 50-100% of the factor Sharpe for market, value, momentum, profitability, ROE, investment, FX carry (in-sample spanning regressions).
- Cederburg, O'Doherty, Wang & Yan (2020, JFE 138 95-117): over 103 equity strategies, spanning alphas are positive but the real-time
  (out-of-sample) implementation earns LOWER Sharpe and CER than the unmanaged portfolio for most factors; momentum, profitability and
  BAB are the exceptions where vol management still helps OOS. https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html [UNVERIFIED]
- Liu, Tang & Zhou (2019) "Volatility-managed portfolio: does it really work?" same conclusion (look-ahead in c, drawdowns) [UNVERIFIED].
- Wang & Yan (2021, JBF) "Downside risk and the performance of volatility-managed portfolios": scaling by DOWNSIDE vol beats scaling by total vol
  https://www.sciencedirect.com/science/article/abs/pii/S0378426621001576 [UNVERIFIED].
- 1/sigma^2 vs 1/sigma: no head-to-head found; theory: 1/sigma^2 is optimal only if expected return is constant in vol (mean-variance investor);
  1/sigma if expected return is proportional to vol (constant Sharpe). In crypto 1/sigma^2 would swing exposure ~25x over a 30%-150% vol range vs 5x for 1/sigma.

### 1.3 Barroso & Santa-Clara (2015) "Momentum Has Its Moments", JFE 116 111-120
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429 [UNVERIFIED]
- w_t = sigma_target / sigma_hat_t with sigma_hat^2 = 21 * (1/126) * sum of squared daily WML returns over the previous 6 months (126 days); sigma_target = 12%/yr.
- Equity WML 1927-2011: Sharpe 0.53 -> 0.97, excess kurtosis 18.24 -> 2.68, skew -2.47 -> -0.42 (figures from the paper via secondary copies) [UNVERIFIED].
- Applied to crypto: Yang (2025) "Cryptocurrency market risk-managed momentum strategies", Finance Research Letters 85, 107879:
  cross-sectional crypto momentum weekly return 3.18% -> 3.47%, Sharpe 1.12 -> 1.42; the gain is from HIGHER RETURN, not smaller tails,
  and crypto "lacks extended momentum crashes". https://www.sciencedirect.com/science/article/abs/pii/S1544612325011377 [UNVERIFIED, cross-sectional long/short, not our rule]
- Grobys et al (2025) "Cryptocurrency momentum has (not) its moments", Fin Mkts & Portf Mgmt: vol scaling improves payoffs but does NOT
  reduce tail risk in crypto momentum; a single outlier coin drives much of the compounded return. https://link.springer.com/article/10.1007/s11408-025-00474-9 [UNVERIFIED]
- Howden & Andreev (2026 SSRN 7115459) "Risk-managed TSMOM in crypto majors": 30-day long/cash TSMOM on 7 majors (MOP-style), Sharpe 1.41 vs
  0.70 B&H net 25 bps, DD -44.6% vs -84.4%; a x0.5 de-risk when the market is >15% off its peak takes DD to -28%, Sharpe ~1.53. They report that
  vol targeting / Kelly sizing layered on the sleeve was a NULL ("de-levers the payoff engine"). [UNVERIFIED; preprint dated 2026-07-14; the off-peak
  overlay is the already-rejected regime/drawdown-filter family].

### 1.4 Daniel & Moskowitz (2016) "Momentum Crashes", JFE 122 221-247
- https://www.nber.org/system/files/working_papers/w20439/w20439.pdf [UNVERIFIED]
- Dynamic weight w_t = (1/2gamma) * mu_hat_{t-1} / sigma_hat^2_{t-1}: exposure proportional to conditional Sharpe, with mu_hat from a
  bear-market x market-variance regression (fitted in sample). Dynamic Sharpe 1.19 vs constant-vol ~1.04 vs static ~0.68-0.82 [UNVERIFIED, mixed snippets].
- Needs a fitted return model -> overlaps the rejected "ML/signal stacking" and "regime filter" families. Not a candidate here.

### 1.5 Kim, Tse & Wald (2016) "Time series momentum and volatility scaling", J. Fin. Markets 30 103-124
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2786955 [UNVERIFIED]
- 55 futures: MOP's TSMOM profits are "largely driven by volatility scaling"; without vol scaling TSMOM is no better than buy-and-hold.
- Matches the local finding (signal adds 0.1-0.2 Sharpe; always-long vol-scaled basket Sharpe 0.99 vs rule 1.12).

### 1.6 Moskowitz, Ooi & Pedersen (2012) "Time Series Momentum", JFE 104 228-250 (the reference TSMOM sizing)
- https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf [UNVERIFIED; formula well known]
- sigma^2_t = 261 * sum_{i>=0} (1-delta) delta^i (r_{t-1-i} - rbar_t)^2 with delta/(1-delta) = 60 days -> delta = 60/61 = 0.9836 (EWMA, centre of mass 60 d).
- Position = 40% / sigma_{t-1} per instrument ("the choice of 40% is inconsequential"), then 1/N across instruments.
- Our rule uses a flat 60-day window instead of the EWMA with 60-day centre of mass; otherwise it is MOP sizing with TV/N.

### 1.7 Baltas & Kosowski (2013/2020) "Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and Pairwise Correlations"
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2140091 ; CME PDF https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf (fetch failed) [UNVERIFIED]
- 1974-2013 futures. Yang-Zhang OHLC vol estimator in place of close-to-close: turnover -17% (t = 5.33) with no statistically significant
  performance change; a Return Stacked review says the same ("about 17% lower turnover"). Abstract-level claim: up to one third of turnover.
- Correlation factor (QuantConnect replication): CF(rho_bar) = sqrt( N / (1 + (N-1) rho_bar) ), rho_bar = signal-weighted average pairwise
  correlation over the past 3 months; portfolio weights multiplied by CF so that the ex-ante portfolio vol hits the target when assets co-move.
  Motivation: post-2008 TSMOM underperformance from higher correlations. Sharpe numbers not in snippets.
- ARITHMETIC for our book: N = 9 coins, rho_bar 0.6-0.9 -> CF = sqrt(9/(1+8 rho)) = 1.26 (rho 0.6), 1.10 (0.8), 1.05 (0.9). With only 3 coins long:
  sqrt(3/(1+2 rho)) = 1.17 / 1.07 / 1.04. The factor barely moves because crypto correlations are always high -> small effect expected.

### 1.8 Bongaerts, Kang & van Dijk (2020) "Conditional Volatility Targeting", FAJ 76(4)
- https://repub.eur.nl/pub/130215/Bongaerts-Kang-van-Dijk-Conditional-volatility-targeting-2020-FAJ.pdf [UNVERIFIED]
- Scale exposure only when vol is in an extreme state (high -> cut, low -> raise), otherwise hold the unscaled exposure. 10 equity markets:
  conventional vol targeting improves Sharpe in 8/10 and RAISES expected shortfall in 8/10; conditional improves Sharpe in all 10, biggest for
  the momentum factor, with half the turnover (1.2 vs 2.4). OOS 1977-2020 net Sharpe 1.062 vs 0.940 (secondary) [UNVERIFIED].
- Footnote: monthly realized vol did "somewhat better" than EWMA or GARCH as the estimator [UNVERIFIED].

### 1.9 Perchet, de Carvalho, Heckel & Moulin (2016) "Predicting the success of volatility targeting strategies", J. Alt. Inv. 18(3) 21-38
- Vol targeting raises Sharpe when (a) volatility clusters (GARCH persistence) and (b) returns are negatively related to vol (leverage effect);
  the gain is proportional to the strength of clustering. Crypto has (a) strongly and (b) inverted -> expect tail/DD benefit, little Sharpe benefit.

### 1.10 Dreyer & Hubrich (2017/2019) "Tail risk mitigation with managed volatility strategies", J. Inv. Strategies 8(1)
- S&P 500 1960-2016: exposure = long-run vol / trailing 20-day realized vol; Sharpe up in all three sub-periods but the 10-year rolling
  "hit rate" is not high; tail risk and skew improve. [UNVERIFIED]

### 1.11 Cui, Zhao & Cui (2025) "Mitigating left-tail risk in volatility scaling: introducing a volatility floor correction", SAGE Open 15(4)
- https://journals.sagepub.com/doi/10.1177/21582440251388777 [UNVERIFIED]
- US equities 1962-2018: a floor on the vol input (limits leverage when vol is low) improves the sub-1st-percentile expected return from -0.144 to -0.120
  log return, robust across sub-samples; cost is a cap on returns. Mechanism: low-vol periods precede crashes, and 1/sigma over-levers into them.

### 1.12 Kelly / fractional Kelly (continuous-time, GBM)
- Full-Kelly leverage f* = SR / sigma -> the Kelly portfolio's vol EQUALS its Sharpe ratio (vol target = SR). Half-Kelly: 75% of the growth
  rate at half the vol; quarter-Kelly: ~44% of growth at a quarter of the vol. Sources: qoppac.blogspot.com Kelly-vs-classical (Carver),
  epchan.blogspot.com how-much-leverage, arXiv 1311.2550 [all UNVERIFIED snippets; the formulas are standard].
- Applied here: ex-ante Sharpe 0.3-0.7 (post-2021 0.26-0.66, ex-ante-universe 0.82-0.86) -> full-Kelly realized vol 30-70%, half 15-35%,
  quarter 8-17%. The live books realize 12.4% (TV0.25) and 18.7% (TV0.40): TV0.25 is quarter-Kelly at SR 0.5, TV0.40 is ~0.4 Kelly.
  Realized/nominal TV ratio is ~0.5 (partial signals, 16% flat days), so "TV" is not the book's vol: any Kelly statement must use realized vol.


### 1.13 Other sources touched (snippets only)
- Baur & Dimpfl (2018) "Asymmetric volatility in cryptocurrencies", Econ. Letters 173 148-151: TGARCH on the 20 largest coins; vol rises MORE after
  positive shocks than negative ones (inverted leverage effect; later work: significant in only 3/20 coins, time-varying). [UNVERIFIED]
  -> total-vol scaling in crypto cuts longs after rallies (anti-trend); the Sharpe channel of vol targeting (Harvey et al; Hood & Raughtigan
  2025 "Volatility targeting is trendy", JPM 52(1): vol-targeting alpha is trend exposure via the leverage effect, absent in commodities/FI/FX) is doubtful here.
- GARCH persistence for BTC: alpha+beta ~0.987 (2020-25 daily), half-life ~53 days; other fits 0.95-0.98 [UNVERIFIED]. HAR-RV beats GARCH(1,1) on QLIKE for 3/5 coins [UNVERIFIED].
  -> vol is strongly predictable; GARCH h-step forecast sigma^2_{t+h} = sigma_bar^2 + (a+b)^h (sigma_t^2 - sigma_bar^2) is itself a short/long BLEND:
  weight on current = 0.987^7 = 0.91 for a 1-week horizon, 0.987^30 = 0.68 for a month.
- Range estimators in crypto: Kristoufek (2024, "Beyond GARCH in cryptocurrency volatility modelling", 5-min Binance 2019-22): Garman-Klass clearly beats
  GARCH-family forecasts [UNVERIFIED]; Lama (Vaasa thesis, 5 coins): Parkinson best in-sample R^2, Rogers-Satchell worst [UNVERIFIED]; one BTC study
  reports daily vol 3.37% CC vs 5.56% Parkinson vs 7.44% GK (2012-21) [UNVERIFIED, suspiciously large gap]. 24/7 trading: no open/close effects, so the
  Yang-Zhang overnight term is ~0 and YZ collapses to k*CC + (1-k)*RS with k = 0.34/(1.34 + (n+1)/(n-1)).
- Zarattini, Pagani & Barbon (2025) "Catching Crypto Trends" SSRN 5209907: Donchian ensemble (5..360 d), position = 25% target / 90-day realized vol,
  leverage cap 200%; BTC from 2015 Sharpe 1.56, DD -19%; top-20 rotational portfolio Sharpe > 1.5 [UNVERIFIED, vendor].
- Summitward crypto trend test 2017-2025: vol scaling alone (12% target, 21-day lookback, no leverage) took BTC DD from -84% to -17% with Sharpe 0.73 -> 0.74;
  adding the trend rule: Sharpe 0.79, DD -15% [UNVERIFIED blog]. Same decomposition as the local T6 basket test.
- Man Group "In Crypto We Trend": "the key lies in volatility scaling"; optimal Sharpe with 10-15 coins [UNVERIFIED].
- Platanakis & Urquhart (2018/2019): 1/N vs Markowitz in 4 coins: difference small and insignificant; 14 models on 7 datasets: none beats 1/N on Sharpe/CER/turnover
  [UNVERIFIED] -> covariance-optimised (ERC/HRP/min-var) sizing has no crypto evidence of beating inverse-vol 1/N; HRP studies report high turnover.
- Carver / pysystemtrade (VERIFIED, raw.githubusercontent.com robcarver17/pysystemtrade/master/sysquant/estimators/vol.py and diversification_multipliers.py):
  robust_vol_calc: EWMA std span 35 (min_periods 10), vol floor = rolling 5% quantile over 500 days; mixed_vol_calc: 0.7 * EWMA35 + 0.3 * EWMA(span = 20 years) of the
  vol series; diversification multiplier = 1/sqrt(w' H w) (H = correlation matrix), capped at 2.5, EWMA-smoothed span 125. Carver's half-Kelly rule (vol target
  ~ SR/2) is from his books/blog [UNVERIFIED snippet].
- QuantConnect replication of Baltas-Kosowski (VERIFIED, raw.githubusercontent.com santoshlite/StrategyLibraryQC/master "Improved Momentum Strategy on
  Commodities Futures.py"): weight = signal * TV * CF / (N * vol_YZ); CF = sqrt(N/(1+(N-1) rho_bar)); rho_bar = 2/(N(N-1)) * sum_{i<j} X_i X_j rho_ij over 90 days;
  YZ on one month of OHLC with k as above. Third-party notes (VERIFIED file, UNVERIFIED content: dungchu2810/gator-quant-hacks build_candidates.py) quote the
  2015 B&K draft: 75 futures 1974-2013, TSMOM Sharpe 1.04 -> 1.05 with CF full sample; post-GFC 2009-01..2013-02 0.14 -> 0.29 gross (0.12 -> 0.26 at 10 bp,
  0.05 -> 0.14 at 50 bp); YZ cuts turnover ~8% (17% in the later version), YZ+TREND rule > one third.
- Northstar Capital vol-targeting note: EWMA forecast of next-month vol about equally accurate for spans 20-120, so the span is a turnover choice [UNVERIFIED]; consistent with my diagnostics.

## 2. Local diagnostics on the cached Binance daily klines (VERIFIED, my own computation; scripts diag_sizing.py / diag_sizing2.py in this folder, outputs copied here)
Data: binance-{COIN}USDT-1d monthly CSVs in the scratchpad trend-cache, 9 coins, common window 2020-07-10..2026-09-30 (2,269 days), OHLC present.

Per-coin 60-day CC vol (annualised) percentiles / share of days below 0.30 / 0.40 / 0.50:
  BTC  p5 0.32 p25 0.40 p50 0.54 p75 0.65 p95 0.90   4% / 25% / 45%
  ETH  p5 0.40 p25 0.56 p50 0.71 p75 0.86 p95 1.24   0% /  5% / 13%
  BNB  p5 0.30 p25 0.45 p50 0.56 p75 0.79 p95 1.82   5% / 17% / 37%
  XRP/ADA/LTC/LINK/DOGE/BCH: p50 0.77-0.89, below 0.40 on 0-4% of days.
  -> the 0.05 floor in target_weights NEVER binds; a 0.40 floor would bind on BTC 29% / BNB 20% of days and almost never elsewhere.
Average pairwise 60-day correlation rho_bar: p5 0.48, p25 0.63, p50 0.72, p75 0.77, p95 0.85 -> B&K CF = sqrt(9/(1+8 rho)): p5 1.07, p50 1.15, p95 1.37.
CC60 / own 1-year average vol: p5 0.58, p25 0.73, p50 0.88, p75 1.07, p95 1.51 (vol sits >27% under its 1-year mean a quarter of the time).

Estimator comparison (medians over the 9 coins). wk-noise = sd of the weekly log change of the estimate (turnover proxy for the weekly book);
RMSE7 / RMSE30 = RMSE of log(estimate / realized CC vol over the next 7 / 30 days); level = median ratio to CC60.
  CC60                 noise 0.113  RMSE7 0.563  RMSE30 0.425  level 1.000
  CC30                 noise 0.192  RMSE7 0.539  RMSE30 0.424  level 0.972
  CC20                 noise 0.267  RMSE7 0.558  RMSE30 0.449  level 0.950
  Parkinson 30         noise 0.175  RMSE7 0.578  RMSE30 0.440  level 1.081
  Parkinson 20         noise 0.236  RMSE7 0.588  RMSE30 0.442  level 1.038
  Garman-Klass 30      noise 0.178  RMSE7 0.597  RMSE30 0.456  level 1.096
  EWMA span 35         noise 0.177  RMSE7 0.531  RMSE30 0.407  level 0.973
  EWMA span 60         noise 0.119  RMSE7 0.539  RMSE30 0.393  level 1.015
  EWMA span 121 (COM 60, MOP) noise 0.067 RMSE7 0.553 RMSE30 0.384 level 1.041
  blend 0.7*EWMA35 + 0.3*mean(EWMA35, 365 d)  noise 0.114  RMSE7 0.524  RMSE30 0.373  bias30 +0.08  (best forecaster at CC60's turnover)
  max(EWMA35, 0.8*LR365)                      noise 0.132  RMSE7 0.544  RMSE30 0.381  binds 41%
  max(CC60, 0.40)                             noise 0.101  RMSE7 0.554  RMSE30 0.404  binds 3% pooled (BTC 29%, BNB 20%)
  max(CC60, 0.7*LR365)                        noise 0.089  RMSE7 0.556  RMSE30 0.401  binds 16% (XRP 31%, DOGE 30%, BNB 27%, BTC 9%)
Readings:
  (a) EWMA at equal memory beats the flat window on both noise and accuracy; COM-60 EWMA has 40% less weekly noise than CC60 with better 30-day accuracy.
  (b) Shorter memory (30 d) forecasts the next week slightly better (0.539 vs 0.563) at +70% noise; T3e's Sharpe 1.16 vs 1.12 is consistent with that.
  (c) Daily-range estimators run 8-10% ABOVE close-to-close vol in crypto (wide intraday wicks vs. close-to-close moves) and forecast CC vol WORSE; their
      only edge is ~9% less noise than CC at the same window, which EWMA gets more cheaply. B&K's YZ gain was turnover, not Sharpe.
  (d) The short/long blend is the best forecaster and costs no turnover; it also over-estimates vol by ~8% on average (= slightly smaller positions).
  (e) Funding drag implied by the evidence line D+: 2.11%/yr of equity at 0.12x average gross = 17.6% of long notional per year. Any candidate that raises
      gross (CF, portfolio-level targeting) pays this on the increment.

## 3. Candidates (exact rules; see the structured output for the full fields)
C1 EWMA vol, centre of mass 60 d (MOP exact)            prior 4
C2 30-day memory (CC30 or EWMA span 35)                 prior 3   (T3e already shows 1.16 vs 1.12 in-sample; adopt only via the ex-ante-universe pre-registration)
C3 Carver blend 0.7*EWMA35 + 0.3*1-year mean vol        prior 3
C4 Fractional-Kelly rule for TV and the gross cap       prior 3   (sets TV from SR_hat; no Sharpe change by construction)
C5 Vol floor (absolute 0.40 or relative 0.7*LR365)      prior 2
C6 Baltas-Kosowski correlation factor CF                prior 2
C7 Second-layer book vol targeting (Barroso on the book) prior 2
C8 Downside semi-deviation scaling (Wang & Yan)         prior 2
C9 Conditional vol targeting (Bongaerts et al)          prior 2
C10 Range-based estimator (Parkinson/GK 30 d)           prior 2   (asked for explicitly; the data say no)
Not candidates: Daniel-Moskowitz dynamic weights (needs a fitted return model: rejected ML/regime family); Howden-Andreev x0.5 below 15%-off-peak (rejected
regime/drawdown family); Moreira-Muir 1/sigma^2 (fails OOS per Cederburg et al; 25x exposure swing over crypto's 30-150% vol range; inverted leverage effect);
covariance-optimised ERC/HRP/min-var (no crypto evidence over inverse-vol 1/N, high turnover); the "vol-of-vol"/GARCH forecast as such (the blend C3 is its cheap form).

## 4. What could not be verified
Every journal/SSRN/arXiv/blog number above is from a search snippet (hosts blocked: people.duke.edu, cmegroup.com, ssrn, arxiv, sciencedirect, springer,
tandfonline, alphaarchitect, quantpedia, summitward, man.com, qoppac). Verified items: the repo files and evidence pack; the Binance cache diagnostics;
the four raw.githubusercontent.com files (pysystemtrade vol.py and diversification_multipliers.py; the QuantConnect B&K replication; the gator-quant-hacks notes,
whose quoted B&K numbers are themselves second-hand).
