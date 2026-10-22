# Adversarial verification: "universe" family (UNI-1..UNI-7) — 2026-10-21

Role: refute. Read-only; nothing in the repo modified, no orders. Every number below is either [REPO] (path given),
[LOCAL] (computed here, script inline in the transcript), [VERIFIED] (file opened), or [UNVERIFIED] (search snippet).

## What the repo has already tested on the universe (the prior-test ledger)

| Where | What | Result |
|---|---|---|
| `evidence/av_runs/av_universe_9.txt` (script `tools/av_universe.py`) | STATIC full-period sets, N fixed = set size: 9 / 8 / 7 / DOGE / all 24 listed by 2020-02-20 / 25 / 16 extras / EOS-TRX-ETC-XLM | daily TV0.40: 1.25 / 1.14 / 1.02 / 1.16 / **0.86** / 0.92 / 0.62 / 0.75; weekly TV0.25 band10: 1.12 / 1.03 / 0.91 / 0.83 / **0.82** / 0.87 / 0.62 / 0.68. BNB+DOGE add ~0.2 Sharpe. |
| `backtest_results.md` T3f | 9 / BTC / BTC+ETH / top-5 (post hoc) | 1.12 / 0.85 / 0.95 / 1.27; "fewer coins test worse" |
| `d3_runs/d3_tests2_output.txt` R2b | 7 weekday offsets x {BTC, BTC+ETH, 9} | same shape |
| `backtest_results.md` T5 | whole-contract rounding $500/1k/2.5k/5k on Delta | 0.72/0.81/0.70/0.69 vs 0.70 unrounded; $500 gross 0.09x vs 0.12x |
| `backtest_results.md` T3l | slippage 2/5/10 bps | Sharpe 1.12/1.11/1.10 (slippage worth <= 0.02 Sharpe) |
| `resource/07` universe para | "The cleaner design, a yearly ex-ante re-set to the nine largest Delta perps by 30-day turnover with at least 121 closes, **has not been backtested and must not be adopted without a run**"; exit rule "turnover below $0.5M for 30 consecutive days (start)"; "no coin is ever added for performance reasons"; kill #6 = annual re-run on the ex-ante universe | |
| `resource/07` rejected table | BTC-only / BTC+ETH; funding carry; funding as a directional signal | rejected |
| this round, `research2/sim/funding_grid.txt` + `funding_bucket_diag.txt` (costs_funding angle) [VERIFIED] | skip-coin-while-trailing-funding > X, windows 7/14/30/60 d x 15-50%; Carver proportional cost adjustment (SZ-15) | 7d>15%: 1.25->0.87 (Delta 0.99->0.55); every 60-d cell negative (daily 1.15-1.16, weekly 1.00-1.03); SZ-15 harmful (1.25->1.08/1.20; Delta 0.99->0.54/0.84). Bucket: gross next-day return highest at funding 12-30%/yr (+62..+129 bps/day, t 3-4.5) |
| grep of the whole evidence pack for gold/PAXG/XAUT/listing-age/Carver/hysteresis/rotation | | **no gold test, no rotating-universe test, no listing-age test, no liquidity-floor test exists** |

Data in place for Phase 2 (so test-cost estimates are honest): `scratchpad/universe/cache_all` = 900 USDT-M perp symbols from the
S3 index incl. delisted (fetch_all.log: "900 USDT-M symbols; 1d: 14,772 monthly files; funding for 490 symbols") with
`quote_volume` in every kline row [VERIFIED]; `research2/dl/paxg_spot` = 74 monthly Binance spot PAXGUSDT 1d zips 2020-08..2026-09
[VERIFIED]; `research2/data/delta_daily_turnover_400d.json` = 400 d of Delta daily turnover for 66 perps [VERIFIED]; the engine
`trend_backtest.target_weights(close: dict, ...)` takes any dict of close series and sets N = number of coins with 121 closes that
day, so a universe change is a wrapper that filters the dict per date (no engine change).

## [LOCAL] Delta rolling 30-day median turnover, last 365 days (rows in the json are newest-first; sorted ascending here)

| perp | med30 today | med90 | days (of 365) rolling-30d-median < $2M / < $1M / < $0.5M |
|---|---|---|---|
| BTC | $1,122M | $915M | 0/0/0 |
| ETH | $732M | $622M | 0/0/0 |
| SOL | $179M | $143M | 0/0/0 |
| XRP | $16.2M | $14.5M | 0/0/0 |
| UNI | $14.8M | $9.8M | 280/183/103 |
| ZEC (listed 2025-10-06) | $12.4M | $8.5M | 65/0/0 |
| AAVE | $7.9M | $3.6M | 301/83/0 |
| DOGE | $7.8M | $5.1M | 34/0/0 |
| AVAX | $4.6M | $1.4M | 241/202/29 |
| LTC | $4.0M | $1.8M | 188/56/0 |
| DOT | $3.8M | $0.75M | 338/230/124 |
| LINK | $3.0M | $2.4M | 237/95/0 |
| BNB | $2.5M | $2.5M | 116/0/0 |
| BCH | $1.4M | $0.89M | 215/167/29 |
| ADA | $1.3M | $0.82M | 340/231/75 |
| TRX | $0.11M | $0.10M | 365/365/365 |
| XMR (listed 2026-01-15) | $0.20M | $0.14M | 250/250/246 of 250 |
| XAUT (listed 2026-04-17) | $719M | $560M | 0/0/0 |
| PAXG (listed 2026-02-19) | $142M | $145M | 0/0/0 |

Today's ex-ante top-9 crypto by 30-day median (ex metal): BTC ETH SOL XRP UNI ZEC AAVE DOGE AVAX -> the rule replaces BNB, LTC, LINK,
BCH, ADA with SOL, UNI, ZEC, AAVE, AVAX. Contract notionals SOL $106, ZEC $127, AAVE $156 round to zero at $1,000 weekly TV0.25
(`data/exante_top15.txt` feasibility table).

## [LOCAL] Gold check (Binance spot PAXGUSDT 1d, 2,225 days 2020-08-28..2026-09-30; the repo rule long/flat)
Unit-notional log return rule +0.68 vs B&H +0.77 (matches the candidate). Vol-scaled at TV/N = 0.40/10 over max(vol60, 5%), net of
7.31 bps per side on weight changes and 5.5%/yr funding while long, simple % of equity: 2021 -1.6%, 2022 -1.1%, 2023 +0.3%,
2024 +5.6%, 2025 +9.6%, 2026 (to Sep) +2.6%; total +15.3%, of which 2024-25 = +15.2%. Gold vol60 avg 12-19%, 30% in 2026.
Delta `products.json` [VERIFIED]: XAUTUSD launch 2026-04-17, contract 0.001 oz ($4.12), **maker 0.0001 / taker 0.0001 (1 bp, vs
2 / 5 bps on crypto perps)**, initial margin 1%, funding cap 21.9%/yr (0.02%/8h), realized +5.5%/yr with 0% of samples at the cap;
24h turnover $695M, OI $108M. PAXGUSD same fees, launch 2026-02-19.

## Verdicts

### UNI-1 Ex-ante liquidity-ranked rotating universe — REFINE
- Not a duplicate: every repo universe run is a STATIC set with N fixed for the whole sample; resource 07 names this exact rule
  as untested and forbids adoption without a run; kill criterion #6 already asks for an annual ex-ante re-run. So the test is
  wanted by the repo itself.
- Refutations of the spec as merged: (1) it is a >100-cell grid (N 9/12/15 x reset yearly/quarterly/monthly x window 30/90 x age
  121/180/365 x floor $1M/$2M x hysteresis x |ret| screen) — a garden of forking paths that would make any "winner" uninterpretable;
  (2) at $1,000 the rotation is infeasible: the names it brings in (SOL/ZEC/AAVE) round to zero contracts, so pairing it with UNI-5
  turns "most liquid" into "cheapest contract"; (3) churn: UNI's 30-day median is $14.8M today but was < $1M on 183 of the last
  365 days; Delta quarterly top-15 changes 5-7 names per quarter (universe.md F6) — a monthly or quarterly reset trades the list,
  and the hysteresis (incumbent stays while rank <= 2N) is load-bearing, not optional; (4) the evidence for a Sharpe uplift is
  weak: Zarattini sec. 7 (transcription VERIFIED as a file, SECONDHAND; vendor-authored; Donchian ensemble, 20 coins, monthly,
  2015-2025, Sharpe 1.57 net 10 bps) is a different rule, and the one independent re-test of that paper (galata, BTC/ETH
  2023-26) found the Sharpe edge over buy-and-hold gone; Man AHL "10-15 coins" [UNVERIFIED, asset-manager piece; its mechanism —
  pairwise corr ~0.6 — matches the local 0.62]; Grobys-Sandretto-Aijo FRL 2026 (search snippet) is about CROSS-SECTIONAL momentum
  disappearing in survivor coins, only indirectly relevant to a time-series rule; (5) the candidate's own expectation is "no Sharpe
  uplift (0.8-0.9)", so acceptance must be measured against the static ex-ante 24 line (0.86 daily / 0.82 weekly, maxDD -24.1% /
  -16.8%), never against the hindsight nine.
- Refined rule (one primary cell, three sensitivities, pre-registered): reset once a year on the first decision day of January;
  U = top-9 crypto USDT-M perps by trailing 30-day median USD turnover (Binance quote_volume before 2024-04-10, Delta
  volume x contract_value x close after), eligibility >= 365 closes on Binance or Delta (whichever longer), exclude tags
  metal/xStock/stablecoins/leveraged/pre-launch; incumbent stays while ranked <= 18; delisted coin goes flat and is not replaced
  until the next reset; feasibility gate at the reset (UNI-5): E x (TV/N)/max(vol60,0.05) >= 2 x contract_value x price, with
  N = |U| after the gate; signal, TV/N, band and gross cap unchanged. Sensitivities: (a) age floor 121 instead of 365; (b) quarterly
  reset; (c) N = 12 at $5,000 only. Universe pool = `scratchpad/universe/cache_all` (survivorship-free). Report full sample,
  2022-26, Delta 2024-08+, names changed per year, and whole-contract runs at $1,000 and $5,000. Accept if daily Sharpe >= 0.86 and
  weekly >= 0.82 with maxDD no worse than the static-24 line in both cadences, and 2022-26 not below the static-24 line. Adoption:
  a research number for the annual review at $1,000; a live universe rule only at >= $5,000.
- Test cost: small (rotation wrapper over `target_weights` + a quote-volume ranker; data in place). Evidence quality: single_study.

### UNI-2 Add gold (XAUTUSD, fallback PAXGUSD) — KEEP
- No prior test anywhere in the repo. Resource 07's "no extra coins ... no second strategy for diversification" is a discipline
  rule against discretionary additions; a pre-registered tenth instrument under the identical rule is the documented exception,
  and it must be registered before the run precisely because gold's 2025 (+65%) is in the sample.
- Mechanism + multi-asset evidence: trend following on gold is inside every multi-asset TSMOM study (Moskowitz-Ooi-Pedersen 2012
  58 futures incl. gold; Hurst-Ooi-Pedersen century evidence 67 markets incl. 29 commodities [UNVERIFIED]; AQR Trends Everywhere
  82 securities incl. commodities [UNVERIFIED; search confirms scope, not a gold number]). Local: corr(PAXG, EW nine) 0.14 over
  2020-26 (0.41 in 2026), N_eff 1.50 -> 1.75 if gold's trend Sharpe matched the nine's.
- What refutes part of the pitch: my yearly split shows the gold leg's net return is +15.2 of +15.3 points from 2024-25 and
  negative in 2021-22 (-2.7 points). That is the base rate for one trend market, not a failure, but the acceptance test must
  include the pre-bull window. Venue history is six months (no Delta-native test possible); PAXG spot had thin volume and a premium
  in 2020-21; correlation rose to 0.41 in 2026.
- Costs are BETTER than the candidate assumed: XAUT taker 1 bp (1.18 bps incl. GST) vs the 5.31 + 2 bps modelled; keep 7.31 bps in
  the test as the conservative line and report 1.18 + 2 as the realistic one. Funding 5.5%/yr, never at the cap, vs ~12%/yr gold
  drift 2020-26. Feasible at $1,000: fully long at TV0.40/10 over 15% vol = 0.27x = $270 = 65 contracts.
- Refined rule: exactly as specified (N = 10, same signal/sizing/band/cap); one sensitivity only: w_gold <= 0.25 E. Data: Binance
  spot PAXGUSDT 1d 2020-08-28 (already downloaded) stitched to Delta XAUTUSD from 2026-04-17; synthetic funding 5.5%/yr before
  2026-04, Delta FUNDING:XAUTUSD after. Accept if full-sample Sharpe >= the nine's AND Sharpe on 2020-08..2023-12 is not below the
  nine's on that window AND maxDD not worse; also report 2024-26 and the result with 2025 excluded. Live: XAUTUSD; fall back to
  PAXGUSD if XAUT 30-day median turnover < $10M.
- Test cost: small (spot-zip loader + a 10th series; `target_weights` takes any dict). Evidence quality: replicated_multi_asset.

### UNI-3 Listing-age floor of 365 closes — REFINE (fold into UNI-1 as sensitivity (a))
- No prior test. The stated mechanism is wrong for the repo code: `target_weights` skips a coin unless all 121 closes exist
  (`if any(h is None for h in hist): continue`), so a coin never trades on "the 20-day sign before the 60/120 legs exist"; all three
  legs exist from close 121 (T7 #4 shows the same exclusion after data gaps). What a 365 floor actually removes is closes
  121-364, when the 120-day leg is anchored inside the post-listing window. Whether that costs or earns is empirical; the press
  figures (Messari: Binance 2025 listings bought at day-1 close -71% [UNVERIFIED]; Delphi via secondary: median -82%, 12%
  profitable [UNVERIFIED, not Binance-specific]; BeInCrypto/X: 3 of 27 positive [UNVERIFIED]) describe buy-and-hold from listing,
  which a long/flat rule is mostly flat for (negative 60/120 signs). Zero effect on the live nine (all > 2,000 closes), so it is not
  a change to the live strategy and has no meaning outside UNI-1.
- Refined rule: UNI-1 sensitivity (a): age floor 365 vs 121; report Sharpe, maxDD and coin-years excluded.
- Test cost: trivial. Evidence quality: snippet_only.

### UNI-4 Liquidity floor with hysteresis ($2M entry / $0.5M exit) — DROP
- Prior: the $0.5M-for-30-days exit is already resource 07's universe rule (start); T3l bounds the whole slippage question at
  <= 0.02 Sharpe (10 bps -> 1.10 vs 1.12); T3f says fewer coins test worse; the memo itself says alt slippage is "small at these
  sizes" ($20-300 orders at $1,000-5,000 sit inside top of book).
- Refutation: on the last 365 days of Delta data the $2M entry bar fails ADA (340 days), BCH (215), LINK (237), LTC (188) and BNB
  (116), i.e. it is a 4-5-name universe change made on a cost rationale worth <= 0.02 Sharpe; the $0.5M exit would have flattened ADA
  for ~75 days and BCH ~29 days with re-entry only at the next reset. No before/after number was offered; the AUT $1M filter is a
  universe-construction choice in a factor paper [UNVERIFIED], not a performance result. What survives lives elsewhere: the entry
  threshold is UNI-1's eligibility floor; the exit is already the design's venue-health rule. Nothing to backtest standalone.
- Test cost if someone insists: small (Delta 1d volume loader). Evidence quality: snippet_only.

### UNI-5 Capital-aware N and >= 2 contracts — REFINE (fold into UNI-1 as its feasibility gate)
- Prior: T5 (rounding noise from $500 up on the nine); `data/exante_top15.txt` (at $1,000 weekly N=15 BTC/SOL/ZEC/AAVE round to
  zero; $5,000 N=15 only ZEC); `adv_ops/checks.py` (BTC/BNB $21-23 targets round to zero on weak-signal weeks). Carver's rule
  VERIFIED as text in the AFTS notes README ("set minimum capital so that you can own at least 4 contracts ... scale position without
  having to close it"; "discard any [instrument] that exceeds capital available") — the book itself [UNVERIFIED].
- Refutation: the capital bands (N = 9/12/15 at $2,500/$5,000) are a second parameter set that only restates the contract test;
  on the nine the rule is a no-op by construction ("the original nine are never removed"); its only live effect is inside UNI-1,
  where at $1,000 it would strip SOL/ZEC/AAVE from the liquid top-9 — which argues for not running UNI-1 live below $5,000, not
  for a universe rule.
- Refined rule: drop the bands; keep "eligible at a reset iff E x (TV/N)/max(vol60,0.05) >= 2 x contract_value x price", N = count of
  eligible coins; run inside UNI-1 at $1,000 and $5,000 with whole contracts (`backtest(capital=, cvals=)` already rounds).
- Test cost: trivial. Evidence quality: vendor_or_blog.

### UNI-6 Correlation-aware selection (handcrafting) — DROP
- Prior: none in the repo; local `corr_effn.txt` only. The names that would pass a low-correlation walk are exactly the ones Delta
  cannot trade: TRX (corr 0.47; 30-day median $0.11M, < $0.5M on 365/365 days), XMR (0.53; $0.20M, 246/250 days, listed
  2026-01), ZEC (0.60 at 107% vol). Among liquid large caps pairwise rho is 0.55-0.76, so a 0.80 pairwise threshold almost never
  binds: the rule is either a no-op or an illiquidity selector. Best-case N_eff 1.5 -> 1.8 is a 1.095x Sharpe multiplier before
  costs, and that diversification effect belongs to sizing (IDM / Baltas-Kosowski CF, already candidates SZ-6/SZ-7), not to
  selection. 120-day trailing correlations are unstable (by-year rho 0.55-0.76); Carver's handcrafting uses long-run
  correlations and is [UNVERIFIED]. No crypto backtest; two free parameters (0.80, top-30); the angle's own prior is 2.
- Test cost: small. Evidence quality: snippet_only.

### UNI-7 Funding-cost eligibility gate (Variant A 90 d > 12%/yr yearly; Variant B Carver SR-unit) — DROP
- Prior: resource 07 rejected funding carry and funding as a directional signal; this round's `sim/funding_grid.txt` [VERIFIED]
  tested skip-coin-while-trailing-funding > X across 7/14/30/60-day windows and 15-50%: thresholds below ~30% destroy the strategy
  (7d > 15%: 1.25 -> 0.87, Delta 0.99 -> 0.55) and every 60-day cell is negative (daily 1.15-1.16 vs 1.25; weekly 1.00-1.03 vs
  1.12); the proportional Carver form SZ-15 is harmful (1.25 -> 1.08/1.20; Delta 0.99 -> 0.54/0.84). Variant A (90-day window, 12%)
  is slower than the losing 60-day cells and lower-threshold than the losing 15% cell.
- Mechanism refutation: the bucket diagnostic shows the best trend days are the 12-30%/yr funding days (+62 to +129 bps/day gross,
  t 3-4.5 on both samples) — a 12% gate removes them by construction. On Delta, Variant A would exclude BNB (20.1%/yr in 2026 YTD)
  and DOGE (19.3%) for 2027 — the two names `av_universe_9.txt` shows add ~0.2 Sharpe — while BTC/ETH (capped at 10.95%/yr) can
  never fail it. Variant B with 2025-26 Delta funding: h = funding/sigma -> BTC 8.1%/50% = 0.16, ETH 7.8%/69% = 0.11, BNB 11.6%/56% =
  0.21, SOL 10.2%/~70% = 0.15, plus trading cost 0.03-0.10 SR -> BTC, BNB, SOL (and ETH on the daily book) exceed the 0.13 budget:
  the gate ejects the most liquid names, the opposite of T3f.
- Carver is misapplied: the AFTS notes [VERIFIED text] define holding cost = risk-adjusted cost per trade x rolls per year x 2
  (roll transaction cost), not carry; Carver trades carry as a forecast (Strategy 10) and never deducts expected carry from
  instrument eligibility. Variant B's "holding cost = funding" has no source. A slowly updated per-coin exclusion keyed on funding
  is a slow funding signal (the angle admits this). If a record is wanted, OVL-2's two tail cells on the ex-ante universe close it.
- Test cost: trivial (grid engine exists). Evidence quality: snippet_only.

## External sources touched this pass (all search snippets unless marked)
- Man Group, In Crypto We Trend (2024-12-19): https://www.man.com/insights/in-crypto-we-trend [UNVERIFIED]; third-party:
  https://theideafarm.com/alternative-investment/real-assets/crypto/in-crypto-we-trend/ [UNVERIFIED]
- AQR Trends Everywhere: https://www.aqr.com/insights/research/journal-article/trends-everywhere [UNVERIFIED]; AQR century
  evidence: https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf [UNVERIFIED]
- Grobys, Sandretto, Aijo, On survivor cryptocurrency momentum, FRL 92 (2026) 109602:
  https://osuva.uwasa.fi/items/a1ada573-de45-4b2c-bad7-d7e0db8e189a [UNVERIFIED]
- Listings: Messari via https://ambcrypto.com/messari-data-shows-binances-2025-listings-down-71-on-average/ ; BeInCrypto
  https://beincrypto.com/binance-listed-tokens-negative-return ; 4pillars https://4pillars.io/en/issues/2025-korean-cex-listings-post-mortem [all UNVERIFIED]
- Zarattini transcription (opened, VERIFIED file, SECONDHAND content):
  https://raw.githubusercontent.com/alfred1123/Quant_Strategies/2db49183360d0c9dab8fd2572bdad75b30da978a/docs/research/catching-crypto-trends.md
- Carver AFTS notes (opened, VERIFIED text): https://raw.githubusercontent.com/majkong14/advanced-futures-notes/main/README.md
- Delta products/tickers snapshot 2026-10-20 (`research2/data/products.json`, `delta_perps.csv`) [VERIFIED]
