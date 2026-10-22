# UNI-1 verification: synthesis (2026-10-21)

Inputs: the frozen plan (`research2/phase1_plan.md`, sha 9ad0a829...), `phase2/verdicts.md`, `phase2/summary.md`, and the four
verifier notes `uni1_verify/{rebuild,audit,robust,live}/notes.md`. My own check: I re-ran the audit's four-clause script on the
original and gap-patched panels. Output: `uni1_verify/synth/rerun_patched_clauses.txt`, identical to `audit/patched_clauses_out.txt`.
I also confirmed the plan's quoted static-24 gate figures in `scratchpad/av_runs/av_universe_9.txt`.

## 1. Verdict: the PASS is refuted; the number survives as a research number

- **The reported numbers are real.** An independent rebuild that never opened `variants_universe.py` reproduces every figure to 4
  decimals. Other checks found nothing:
  - look-ahead: 480 of 480 truncation and perturbation tests identical;
  - bad prints: none;
  - delisting P&L inside U: 0;
  - funding stresses: at most -0.02 on the delta.
- **The PASS rests on a data defect.** `universe/fetch_all.py` drops failed downloads without a trace. Two gaps result:
  - DASHUSDT-1d-2022-10 is missing (DASH is in the static 24);
  - Binance's monthly files lack 2022-02-26..28 and 2022-04-01..02 for 51 symbols, including XRP, LTC and SOL.

  Each gap restarts the 121-close rule and takes the coin out for about 4 months. Filling the 71 coin-rows from Binance's own files
  leaves UNI-1 membership unchanged. It moves static-24 to **0.860 / 0.819 with maxDD -24.01 % / -16.75 %**. That is the plan's own
  D-0 gate (0.86 / 0.82, -24.1 % / -16.8 %, `av_universe_9.txt`).
- **The D-0 gate was missed, then waived.** The gate requires static-24 to reproduce 0.86 / 0.82 "before any rolling run". The
  harness gave 0.8512 / 0.8101, and `verdicts.md` waived the gap as an engine difference. It was a data defect. The plan treats fixes
  like this as bug fixes, not plan changes (the COST-2 engine note sets the precedent). On the data that satisfies the gate, UNI-1's
  daily book fails clause R3.

Daily R3 (maxDD no worse than static-24; the matched-vol re-run is the decision line because vol is 10 % higher):

| data | reference | UNI-1 matched-vol maxDD | reference maxDD | R3 |
|---|---|---|---|---|
| original (as judged) | harness static-24 | -24.19 % | -24.74 % | pass (+0.55 pp) |
| original | plan's quoted static-24 | -24.19 % | -24.1 % | **fail (-0.09 pp)** |
| gap-patched | patched static-24 | -24.51 % | -24.01 % | **fail (-0.50 pp)** |
| gap-patched | plan's quoted static-24 | -24.51 % | -24.1 % | **fail (-0.41 pp)** |
| any | raw maxDD (not vol-matched) | -26.49 % / -26.82 % | -24.74 % / -24.01 % | **fail** |

Weekly R3 passes on corrected data (-16.59 % vs -16.75 %). The cell's target is "both", so all four clauses must hold on both books.
Under section 5, a variant that fails any item is "do nothing".

Corrected-data scorecard (R1, R2 and R4 still pass):

| book | FULL Sharpe vs static-24 | POST delta [95 % CI], P(delta <= 0) | H1 / H2 delta | matched-vol maxDD vs static-24 | raw maxDD |
|---|---|---|---|---|---|
| daily | 1.046 vs 0.860 (+0.186) | +0.256 [-0.24, +0.73], P 0.13 | +0.161 / +0.231 | -24.51 % vs -24.01 % **FAIL** | -26.82 % vs -24.01 % |
| weekly | 0.984 vs 0.819 (+0.165) | +0.273 [-0.24, +0.77], P 0.13 | +0.083 / +0.296 | -16.59 % vs -16.75 % ok | -18.20 % vs -16.75 % |

The rebuild found the R3 clause fragile even on the original data:
- the matched-vol margins were 0.55 pp daily and 0.35 pp weekly;
- R3 failed under 2 of 6 alternative implementation readings;
- all four clauses passed on both books in only 3 of 12 reset months (January, March, June).

## 2. What survives (all four lenses agree)

- **Reproduction.** Daily 1.0497 vs 0.8512 and weekly 0.9838 vs 0.8101, matched by the rebuild and by the shipped module. The literal
  "N = |U|" reading gives 1.027 / 0.975. Across 6 defensible readings: daily 0.99-1.12, weekly 0.92-1.00, POST delta +0.19..+0.29.
- **Not a lucky draw.** The placebo of 9 random coins drawn from the eligible top 18 each January puts UNI-1 at the 96.5th
  (daily) and 100th (weekly) percentile on POST. Static-24 itself sits at the 89th-90th percentile of the uniform placebo, so it is
  not a weak comparator.
- **Sign is robust.** POST delta stays positive under every perturbation tried except weekly with SOL removed from the world (-0.008):
  - reset shifted -28..+56 days: +0.16..+0.41 daily, +0.16..+0.32 weekly;
  - N 5-12: +0.09..+0.38;
  - turnover window 14-90 days: +0.19..+0.34;
  - Delta-funding stress (the A6 line, never run on Bw in Phase 2): +0.25..+0.28.
- **Not a start-set or delisting artefact.** A hybrid that runs static-24 to 2021 and UNI-1 after gets FULL 1.028 / 0.992. Restarting
  both books on 2022-01-01 gives the same +0.276 / +0.285. MATIC's delisting came while the book was flat. LUNA, FTT and SRM never
  entered.

## 3. What narrows the number

- **Mostly 2023-24.**
  - Vol-matched yearly return gap (daily): 2022 -0.1 %, 2023 +11.6 %, 2024 +5.9 %, 2025 +2.8 %, 2026 +0.6 %.
  - The 2022 Sharpe "gain" is an artefact of higher vol on a negative mean.
  - POST delta over 2025-26 alone: +0.095 daily, **+0.002 weekly**.
- **It is concentration plus two entrants.**
  - The 9 shared coins earn +1.038 in UNI-1 vs +0.421 in static-24, at about 2.7x the weight.
  - Coins only UNI-1 holds add +0.271, of which SOL +0.128 and DOGE +0.109.
  - About half the POST gain sits in 3 coin-years: DOGE 2024, SOL 2023 and BTC 2023.
- **Knife edges in fixed parameters.** These are not errors.
  - At the 2023 reset EOS was 2.5 % of turnover short of rank 18. Raising it +3 % cuts the POST delta to +0.181 daily / +0.103 weekly.
  - LUNA missed the 365-close floor by 26 days. Any floor of 335 or less gives 0.968 / 0.922.
  - With no hysteresis (H = 9) the weekly delta is +0.025.
  - 10 % turnover noise puts the 5th percentile of POST Sharpe at 0.704 daily and 0.543 weekly.
- **Against the books that actually run (the live nine).**
  - 2024-05..2026-09: daily +0.04 (P 0.42), weekly +0.14 (P 0.14), correlation 0.96, tracking error 4.4 %/yr.
  - FULL 2020-26: UNI-1 trails the hindsight nine by -0.20 daily and -0.14 weekly.
  - The plan compares UNI-1 only with static-24, so this is context, not a clause.

## 4. Defects found (fix before any Phase 3 use)

1. **Silent download failures** (`universe/fetch_all.py`) plus the rows missing from Binance's monthly files. This affects panel B in
   every Phase 2 cell, because D-0 reproduces `baseline.json` B exactly: static-24 moves 0.851 -> 0.860 and 0.810 -> 0.819. By my
   reading of `verdicts.md`, no other verdict flips, because each failing cell also fails a condition that does not use B:
   - TIME-1 6b, TIME-4 6c, COMBO-C 6b, COST-2 cond 3, UNI-2's missing neighbor;
   - A-panel cond 2 for the signal and sizing cells.

   The B numbers in the memo should still be recomputed on patched data.
2. **Wrong contract values for the new names.** The whole-contract and UNI-5 gate code uses `data.CVALS` (the nine only) and
   $25 / first close for everything else. Against Delta's real contract sizes that is 7.65x too large for SOL, 7.1x for AVAX, 6.7x for
   1000PEPE and 3.5x for ZEC. The gate therefore wrongly drops SOL at every capital up to $5,000.
3. **A4's reference line is not usable for this cell.** A4 names the $1,000 whole-contract line, which contradicts "live only at
   >= $5,000"; at $1,000 the book is not the tested universe. That line also uses Binance funding, while Delta funding ran 2.0x
   Binance's at book level in 2026-Q3 (3.09 % vs 1.54 %/yr). A4(b) would fail on funding for any book judged against a
   Binance-funded line.
4. **Code limit.** `cex-mm/scripts/trend_paper.py` is hard-wired to `tb.COINS` (the nine). A third book needs a universe input,
   per-coin Delta product lookup and a reset job.
5. **Report items never saved.** The 6.3 report items (names changed per reset, delisting events, whole-contract lines) exist only
   in the audit and live verifier outputs.

## 5. Recommendation

### Third paper book: **no, not now**

- **The plan rules it out.** On corrected data UNI-1 fails its pass line on the daily book, so section 5 says "do nothing":
  - its numbers go into the memo and the considered-and-rejected table in resource/07;
  - it is revisited at the annual review (kill criterion #6) with one more year of data.

  A third paper book is for a passing variant (A4).
- **It would not be justified even granting the pass:**
  - The paper books run at $1,000. There UNI-1 is not the tested universe: SOL has 0.42 / 0.66 contracts at full signal.
  - An 8-week run cannot separate it from the live nine (56-day tracking error 1.7 %, t about 0). A4 is fidelity-only, so the run
    would teach nothing about the edge.
  - The 2027-01-01 reset will change membership. On the proxy, AVAX leaves and ZEC enters, and ZEC fails the gate at $5,000. A book
    started now would test the 2026 list for about 10 weeks, then a different, gate-shortened list.
  - Defects 2-4 have to be fixed first.
- **Weekly UNI-1** is not recommended below about $13.3k at any review: SOL has 2.05 contracts against a floor of 2, ZEC needs
  $13,306, and the weekly gain is the fragile one (H = 9 +0.025; 2025-26 +0.002).

### What to do instead (zero risk, no orders)

1. **Memo and resource/07.**
   - Record UNI-1 as a FAIL on daily R3 after the D-0 data fix, with the corrected scorecard above and the caveats in sections 3-4.
   - Correct the D-0 note in `verdicts.md`: the 0.01 gap was a data defect, not an engine difference.
2. **Annual review re-test, fixed now so nothing new is tuned.** Re-run UNI-1 exactly as frozen:
   - settings: N 9, January reset, 30-day median, age 365, keep-rank 18, start top-9 on 2020-04-30;
   - data: the gap-patched Bw panel extended through the latest quarter;
   - clauses: all four 6.3 clauses on both books, matched-vol R3 against the patched static-24;
   - also report raw maxDD and the A6 Delta-funding line;
   - the comparator stays static-24, never the nine.

   A third paper book starts only if every clause passes on both books, and only with the user's go-ahead.
3. **Optional out-of-sample record.** On the 2027-01-01 candle, compute and archive the UNI-1 reset with the spec below:
   ranking, ages, ranks of the incumbents, and the gate at $5,000 with Delta contract values. Do not trade it. This gives the annual
   review a membership list that was truly ex ante.

### Parked spec (use only if the annual review passes, or on the user's explicit override)

- **Book.** Third paper book, daily only. State dir `cex-mm/artifacts/trend/paper-uni1`. **Paper capital $5,000.** No orders, no
  keys; paper fills only.
- **Rule.** Identical to the daily VM book except the universe:
  - signal: mean of sign(P_t/P_{t-L} - 1) over L in (20, 60, 120), floored at 0;
  - vol: uncentered 60-day close-to-close;
  - weight: w = sig x (0.40/N_t)/max(vol, 0.05);
  - gross cap 2x, band 0;
  - decision at the 00:00 UTC daily close, taker fills walked through Delta L2 at 00:05 UTC;
  - N_t = members with >= 121 consecutive Delta daily closes and a live Delta product.
  - Signal from Delta last-trade daily closes. D-4 favours last-trade on the daily rule (0.994 vs 0.985 for MARK), and this keeps
    the universe as the only difference from the daily book.
- **2026 universe** (both cadences, unchanged since 2025-01-01): BTC ETH SOL XRP DOGE BNB 1000PEPE AVAX LINK.
  - Delta symbols: BTCUSD ETHUSD SOLUSD XRPUSD DOGEUSD BNBUSD 1000PEPEUSD AVAXUSD LINKUSD.
  - All are live. At $5,000 and TV 0.40 every member has >= 2 contracts at full signal (SOL is the thinnest, 3.3).
- **Reset rule** (yearly; the backtest's row convention):
  - Timing: Binance daily candle dated Jan 1 (open time), which closes at 00:00 UTC on Jan 2. Execute at 00:05 UTC on Jan 2. The
    Dec-31 row changes results by <= 0.006.
  - Ranking: rank crypto USDT-M perps by the median daily quote_volume over the 30 candles ending at the reset candle. Skip
    zero-volume and missing rows. A coin needs >= 30 closes in its current listing life.
  - Exclusions: metals/commodities, stock/ETF perps, stablecoins (USDC, USTC), indices (BTCDOM, DEFI) and leveraged/pre-launch
    products (the I-U1.5 list).
  - Entry: an entrant needs >= 365 closes with quote_volume > 0 in its current listing life. A renamed symbol (MATIC -> POL) is a
    new listing.
  - Keep and fill: rank within (age-eligible candidates + incumbents). An incumbent stays while its rank is <= 18. Free slots go to
    the best-ranked non-incumbents until there are 9. Ties break by symbol.
  - Gate (UNI-5): keep a member outside the live nine only if E x (0.40/N_pre)/max(vol60, 0.05) >= 2 x Delta contract value x
    price, where E is paper equity at the reset. A coin that fails the gate, or has no live Delta USD perp, is dropped and not
    replaced.
  - Delisting: a delisted member is flattened at its last close and not replaced until the next reset.
- **Expected 2027 reset** (proxy at 2026-09-30; unstable across windows):
  - AVAX out (rank 25); ZEC in (rank 3) but gated out at $5,000 (1.28 contracts; needs $8,316).
  - Result: 8 names, BTC ETH SOL XRP DOGE BNB 1000PEPE LINK.
  - LINK sits exactly at rank 18. HYPE is the entrant instead of ZEC in 2 of 5 windows, and it is feasible at any capital.
- **Data sources:**
  - Ranking and age: Binance USDT-M daily klines from data.binance.vision (`data/futures/um/daily/klines/<SYM>/1d/`), with monthly
    files for age. Run at the first hourly timer after all 30 daily files exist. **Fail loudly and skip the reset** if any file for
    a top-30 candidate is missing, checked against the S3 listing.
  - Delta: prices, signal and vol from Delta daily candles; funding from Delta FUNDING:<sym>; contract value and state from Delta
    `/v2/products` (`contract_value`, `state`, `trading_status`, `only_reduce_only_orders_allowed`).
  - Do not rank on Delta's own turnover: it produces a different, untested top 9.
- **Monitoring and fidelity.**
  - Log, but do not act on, any member under $0.5M 30-day median turnover on Delta. Today that is 1000PEPE: $0.13M median, $0.02M
    minimum, 10.7 bp spread.
  - A4 fidelity reference: the $5,000 whole-contract line rebuilt with Delta contract values and Delta funding. This changes A4's
    "$1,000 line", so it must be recorded as a dated section-10 amendment and marked post hoc.
  - Run 8 weeks minimum, chosen so the window includes a January reset. The reset is the only operation unique to this book.
- **Build.** `trend_paper.py` needs a universe file, per-coin product lookup and a reset job. Build them through the lead-engineer
  flow (branch, PR, CI, review) and only on the user's request.

## 6. Files

- Verifier notes: `uni1_verify/rebuild/notes.md`, `uni1_verify/audit/notes.md`, `uni1_verify/robust/notes.md`,
  `uni1_verify/live/notes.md`.
- Pivotal evidence: `uni1_verify/audit/patched_clauses_out.txt`, `uni1_verify/audit/patch_attr_out.txt`, and my re-run
  `uni1_verify/synth/rerun_patched_clauses.txt`.
- Gate source: `scratchpad/av_runs/av_universe_9.txt` (static-24 at 0.86 / -24.1 % daily and 0.82 / -16.8 % weekly).
- Membership and gate tables: `uni1_verify/live/live_out.txt`, `uni1_verify/live/contracts_out.txt`.
