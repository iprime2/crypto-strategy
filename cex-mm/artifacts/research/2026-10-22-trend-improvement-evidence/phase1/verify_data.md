# Adversarial verification: DATA family (DATA-1, DATA-2)

Verifier run 2026-10-21. Read-only on the repo; nothing placed, nothing edited. Evidence files:
- `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research2/s3list/um_symbols.txt` (1,051 S3 prefixes under data/futures/um/monthly/klines/)
- `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research2/s3_probe_e426a2.txt` (raw S3 XML page 1)

## What the repo already tested (the "prior test" search)

| Where | What | Relevance |
|---|---|---|
| `resource/07` "What was considered and rejected" | BTC-only / BTC+ETH universe (T3f); no survivorship or slippage item | neither candidate is on the rejected list |
| `backtest_results.md` T3f | universe cells 9 / BTC / BTC+ETH / top-5 (post hoc) | fixed universes only |
| `backtest_results.md` T3l | slippage 2 / 5 / 10 bps per side on the weekly design line: Sharpe 1.12 / 1.11 / 1.10, fees/yr 0.25 / 0.35 / 0.52% | brackets DATA-2 |
| `backtest_results.md` T6d, T7 #8 | plumbing kill is below rounding noise at $1,000; "2 bps is below the 6-12 bps quoted alt spreads but matters little at 0.6x turnover" | DATA-2 already judged |
| `av_runs/av_universe_9.txt` (`tools/av_universe.py`) | fixed ex-ante cohort: all 24 USDT-M perps listed by 2020-02-20 (+DOGE = 25), daily 0.86 / weekly 0.82; 16 extras 0.62 | **already delisting-inclusive**: EOSUSDT is in `av_cache` 2020-01..2025-05 (its delisting month) and `trend_backtest.backtest` flattens a coin at the last close when `nxt not in close[c]`, charging the taker cost (the weekly variant in av_universe.py drops it without cost, "lenient") |
| `d3_runs/d3_tests2_output.txt` R2b | 7 weekday offsets x three universes (BTC, BTC+ETH, 9) | fixed universes only |
| 2026-10-08 memo `--grid` | lookbacks x TV (18 cells) | no universe or cost cells |

No rolling / point-in-time universe has ever been run in the repo. So DATA-1 is not a duplicate; it is a precondition for UNI-1/3/4/6/7 and the question is whether it is correct and feasible.

## DATA-1: survivorship-free point-in-time Binance perp list

### Claims checked

1. "Delisted perps remain in the archive" — VERIFIED by HEAD probes (HTTP 200): FTTUSDT 2022-10, LUNAUSDT 2022-04 (2022-06 = 404), EOSUSDT 2025-05 (2025-06 = 404), FTTUSDT fundingRate 2022-10, XMRUSDT 2024-03 and 2026-09 (XMR perp is still listed; not delisted).
2. "Open problem: enumerating the historical symbol list; S3 XML untested" — STALE / SOLVED. `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/` returns `application/xml` ListBucketResult, paginates with `marker=<NextMarker>`: 2 pages, 1,051 prefixes, 53 of them quarterly `_YYMMDD` contracts, 900 plain USDT-M names (FTTUSDT, LUNAUSDT, SRMUSDT, BTCSTUSDT, TOMOUSDT, EOSUSDT all present). Per-symbol month listing works too (`...klines/FTTUSDT/1d/` -> 54 zip keys).
3. **The sibling already built the survivorship-free pool.** `scratchpad/universe/fetch_all.py` (03:15, log 03:32) walks that S3 index and fetched 14,772 1d files + 12,999 funding files into `universe/cache_all` (689 symbols with 1d data, 490 with funding), skipping the ~206 symbols already in `universe/cache`, `trend-cache` and `av_cache`. Union of the four dirs: **896 symbols with 1d files**. The DATA-1 text (08:05) still calls the sibling cache survivor-conditioned; that is true only of `universe/cache` (`fetch_universe.py` line 33 keeps a symbol only if a 2026-08/09 file exists: 181 symbols, 0 ending before 2026-08, and all 30 of cache_all's early-ending symbols are absent from it). `cache_all` is the survivorship-free one: LUNAUSDT 2021-01..2022-05 (last close 0.0080 after 82.13 on 2022-05-01), SRMUSDT ..2024-05, TOMOUSDT ..2024-05, BTCSTUSDT ..2026-06.
4. **"A symbol's last file month is its delisting month" is WRONG for most delistings.** Binance keeps publishing zero-volume zombie files after a perp is delisted: FTTUSDT last positive-volume day 2022-11-14 but files to 2026-09-30 (1,416 trailing zero-volume rows, close frozen at 1.59); SCUSDT 2022-06-17 -> 2026-09; RAYUSDT 2022-11-15 -> 2026-09; FTMUSDT 2025-01-06 -> 2026-09; MATICUSDT 2024-09-04 -> 2024-09-11; EOSUSDT ends the day it was delisted (2025-05-21). Across the 896-symbol union: **160 true delistings (last positive-volume day before 2026-09-01), 149 symbols with >= 5 trailing zero-volume days, only ~30 whose files actually stop.** A file-presence rule would carry ~130 zombies: a frozen close gives sign(0)=0 on the 20-day leg but the 60/120-day legs stay positive for up to 60/120 days (signal 2/3 then 1/3), and as frozen days fill the 60-day vol window vol -> 0 -> floored at 5% -> weight (2/3)(TV/N)/0.05, i.e. a huge dead position that absorbs the 2x gross cap and dilutes the live book. Membership must be by positive quote volume, and the delisting day is the last day with quote_volume > 0.
5. Renames (MATIC->POL, FTM->S, RNDR->RENDER, AGIX/OCEAN->FET, KLAY->KAIA) show up as a delisting plus a fresh listing with no history. Under a listing-age floor the new name is out for 121-365 days. Conservative, not wrong; must be stated.
6. Ammann, Burdorf, Liebi, Stoeckl, "Survivorship and Delisting Bias in Cryptocurrency Markets" (SSRN 4287573, WP 2022-11-28) — confirmed from the SSRN abstract and the St. Gallen repository page via search snippets (PDF not opened, so the numbers stay [UNVERIFIED at source]): 3,904 coins 2014-2021, annualized bias 0.93% value-weighted, 62.19% equal-weighted; momentum and market beta show no positive relation to returns once delisting returns are included. Caveats for us: the 62% figure is an equal-weighted cross-section dominated by micro-caps; a top-N-by-turnover perp universe sits between the VW and EW cases, and their momentum result is cross-sectional (which the repo already rejected), not long/flat TSMOM. The sibling's "TV/N is close to equal-risk, i.e. the biased case" is a stretch: equal risk among the 10-15 most liquid perps is not equal weight among 3,904 coins. The mechanism itself is textbook and replicated in equities (CRSP delisting returns, Shumway 1997) and hedge-fund databases; the crypto magnitude is a single study.
7. Owusuk/crypto-stat-arb README (raw.githubusercontent, VERIFIED): V1 = 16 survivors-to-2026, V2 = top 40 by market cap on 2021-01-03 incl. FTT/EOS/MKR exits; TSMOM-with-DVOL-filter hold-out Sharpe 0.30 at 20 bps (2024-01..2026-10), combined book 0.20 vs BTC buy-and-hold 0.61; alpha t = 0.52. Supports "include failures", says nothing about the size of the bias; a hobby repo, no vendor interest.
8. Feasibility on Delta India with public data and $1,000-5,000: the backtest side is Binance-only public data (fine); the live book uses today's Delta list. Nothing here places orders. OK.
9. Is it an exact rule? Yes, a data rule; it is not a P&L candidate and should never be scored as one. Its value is that UNI-* results are uninterpretable without it, and that the fixed-cohort ex-ante number (0.86 / 0.82) is the right benchmark for them, not 1.25 / 1.12.

### Verdict: REFINE (keep as a hard precondition for every UNI-* run; rewrite the rule)

Refined rule: pool = every symbol in the S3 index of `data/futures/um/monthly/klines/` (900 plain USDT-M names; quarterly `_YYMMDD` contracts excluded), prices from the union of `universe/cache_all`, `universe/cache`, `av_cache`, `trend-cache` (896 symbols), funding from the matching fundingRate files (490 symbols; a missing funding file = 0, flagged). A symbol is a member on decision day d only if quote_volume(d) > 0 and the trailing 30-day median turnover passes the UNI floor; its delisting day is the last day with quote_volume > 0 and the position is flattened at that day's close at taker cost (LUNA: 0.0080, i.e. a total loss, as happened). A renamed symbol is a new listing. Loader T0: the 24-perp cohort must reproduce av_universe_9.txt (daily 0.86, weekly 0.82) before any rolling run; report the count of delisting events hit and their P&L separately so the bias is visible, not just absorbed.

Cost: small (one loader over four dirs + a membership function; the data is on disk).

## DATA-2: per-coin measured half-spread instead of flat 2 bps slippage

### Claims checked

1. Journal numbers — VERIFIED by recomputation from `daily-book/journal.jsonl` (11 rebalances 2026-10-08..18, 34 orders): medians BTC 0.03 (n=2), ETH 0.10 (2), BNB 0.21 (3), XRP 0.73 (2), LINK 0.80 (5), LTC 1.62 (2), DOGE 1.76 (3), BCH 2.17 (4), ADA 6.48 (11; mean 6.61) bps. Clip notionals $0.44-$147, so these are top-of-book half-spreads, not impact. `trend_paper.py` walks `/v2/l2orderbook?depth=50` and records `slippage_bps` per order; the model cost it compares against is `TAKER_BPS + SLIPPAGE_BPS` from `trend_backtest.py` (line 32).
2. Delta L2 today (VERIFIED, depth 3): BTC 0.06 bps spread (half 0.03), DOGE 3.66 (1.83), BCH 4.20 (2.10), ADA 4.89 (2.45; best-ask size 200 contracts = $45, so a 246-contract clip walks a level, consistent with 6.5 bps realized). Spreads move; the table is a snapshot.
3. P&L effect — bounded by the repo's own T3l. The table lies inside [0.03, 6.6] bps, inside the tested flat envelope [2, 10] bps, which moved the weekly Sharpe 1.12 -> 1.10 and fees/yr 0.25 -> 0.52%. On the daily line (fees 1.14%/yr at 7.31 bps -> 15.6x traded notional/yr) the turnover-weighted change is (-1.97 -1.90 -1.82 -1.27 -1.21 -0.42 -0.38 +0.18 +4.61)/9 = -0.46 bps/side = -0.07%/yr (the candidate's own "-7 bps/yr"); the worst case (every coin at ADA's 6.6) is +4.6 bps x 15.6 = +0.72%/yr, about -0.04 of Sharpe at 18.7% vol. The candidate itself says "no live P&L change; accounting only".
4. The measurement already exists and is already a gate: `resource/07` week-1 platform check ("slippage <= 2 x 7.31 bps per side on every coin"), Gate A ("measured cost <= 2 x 7.31 bps per side") and kill criterion 3 ("median fill vs the 00:00 UTC decision price worse than 2 x 7.31 bps over the last ten orders"); T6d says the equity-divergence form is below rounding noise and the per-order form is the usable one. DATA-2 adds a backtest knob to a number the plan already measures live.
5. Not a strategy rule: it changes neither signal, sizing, cadence nor universe. Where a per-coin cost could matter (ADA at 6.5 bps vs 0.03 on BTC), the real per-coin running cost is funding (Delta majors 1.8-17x Binance), which UNI-7 already screens; the half-spread is a second-order input to that screen.

### Verdict: DROP (as a Phase 2 candidate)

Keep what already exists: the per-coin median slippage in the journal as the Gate A / kill-3 statistic, refreshed as fills accrue. If UNI-7 or COST-4 runs, pass the table as a per-coin cost input there (one dict lookup), with the flat 2 bps kept as the pre-registered default so results stay comparable with the 2026-10-13 evidence. No separate backtest.

Cost: trivial (a dict in the cost line), but not worth a pre-registered cell.

## Sources
- data.binance.vision HEAD probes (VERIFIED, listed above); S3 index https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/ (VERIFIED, 200, XML)
- Ammann et al. SSRN 4287573 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4287573 ; St. Gallen repository https://www.alexandria.unisg.ch/entities/publication/ed11eb12-4cd1-4e08-b3a4-f577ad6e4a66 (search snippets only, [UNVERIFIED at source])
- Owusuk README https://raw.githubusercontent.com/Owusuk/crypto-stat-arb/main/README.md (VERIFIED, fetched)
- Repo: `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/backtest_results.md` T3f, T3l, T6d, T7; `av_runs/av_universe_9.txt`; `tools/av_universe.py`; `d3_runs/d3_tests2_output.txt` R2b; `resource/07-trend-rule-and-prop-trading-research.md` rejected table, gates, kill criteria; `cex-mm/scripts/trend_backtest.py` lines 35, 125-176; `cex-mm/scripts/trend_paper.py` lines 32, 81, 99, 176-186
- Local: `scratchpad/universe/fetch_all.py`, `fetch_all.log`, `cache_all/`, `fetch_universe.py`; `scratchpad/av_cache/` (EOSUSDT 2020-01..2025-05); `scratchpad/daily-book/journal.jsonl`
