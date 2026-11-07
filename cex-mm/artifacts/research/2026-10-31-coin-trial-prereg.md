# Quant memo: pre-registration of the shadow trial of SOPH, PARTI, RSR and OP
**Date:** 2026-10-31 (written about 17:30Z, before any simulation of the new shadow run) · **Venue:** Delta India mainnet (public data, no orders) · **First evaluation:** 2026-11-04 17:30Z (23:00 IST)

## Question

Can a second coin earn alongside ADA? ADA's useful quote size tops out around 1,500 per quote (`2026-10-31-ada-size-step-prereg.md`), so growth past it needs more markets.

AVAX and NEAR were tried and dropped:

- AVAX: about breakeven at ± 6 bps and 1000 ms, on about 417 fills.
- NEAR: −4.09 bps net60 on 185 fills (`2026-09-30-shadow-dism-ada-avax.md`).

## Candidates (scan of 31 Oct, `scan_delta_markets.py --samples 8 --gap 15`)

| Coin | Delta spread | Ticks in it | Delta 24 h turnover | Binance spot 24 h | Tick, contract (Delta) |
|---|---|---|---|---|---|
| SOPHUSD | 19.8 bps | 3 | $17.3M | $10.6M | 1e-6, 100 SOPH |
| PARTIUSD | 10.4 bps | 5 | $2.8M | $3.2M | 1e-5, 100 PARTI |
| RSRUSD | 31.4 bps | 5 | $1.5M | $6.4M | 1e-6, 100 RSR |
| OPUSD | 26.5 bps | 3 | $0.6M | $7.9M | 1e-4, 0.1 OP |

For comparison, ADAUSD was 12.1 bps, 23.5 ticks and $0.54M on the same scan.

Why these four:

- Each has a Binance spot pair, so the anchored fair can work.
- Each has several ticks inside its spread, so a quote can stand alone inside the touch.
- BLESS and HANA had wide spreads but no Binance pair, so they were left out.

A wide spread can be a sign of informed flow. Only markouts can tell.

## Data

- Shadow run 20261031T172449Z (binary 7ffa8fb5a40f817a, commit ca140f6), started 17:24:49Z on 31 Oct on the owner's word, with symbols ADA, SOPH, PARTI, RSR and OP.
- Any later shadow run on the same profile also counts.
- The profile is `config/dism.env` with no per-coin overrides. The new coins run with anchor weight 1, the depth basis and the default 10,000 base-unit depth threshold. Where that threshold is not reachable, the anchor stays off and the logged fair is unanchored. That is a property of this first look, not a tuned setup.
- The window starts at **2026-10-31T17:30:00Z**, after warm-up.

## Method (`coin_trial_eval.py`, md5 206f59166627b16a6a72fa01db6381ca; simulator md5 a93c1658)

- **Sizing:** $40 per quote, about ADA's 200 contracts, with a cap of 2 quotes.
- **Split:** the window is cut in half by time.
- **Selection half:** each coin's half-spread is picked from ± 6, 8, 10, 12 and 15 bps by calibrated-leg PnL per $ (1000 ms, touch, Scalper Offer 15 min fifo), among half-spreads with at least 100 fills.
- **Test half:** only that half-spread is run. **PASS** needs all of:
  - at least 150 calibrated fills;
  - calibrated leg of at least +2.4 bp/$;
  - 1000 ms strict and 300 ms strict at the list fee of 2.12 bps, each at least 0;
  - calibrated worst dip no worse than −$5.
- **Not enough data:** if either half has too few fills, the coin waits for the final evaluation on 2026-11-07 17:30Z. That is the same rules on the longer window, and there is no third look.
- **Evaluation runs:** at 4 Nov 17:30Z, and on 7 Nov 17:30Z for any coin still without a verdict.

## Decision

- **PASS:**
  - Propose that coin live at about $40 per quote with its own cap of 2 quotes.
  - First, tune its depth threshold (`MM_BASIS_DEPTH_QTY_<COIN>`) from its depth book and check the anchor stays on in the shadow.
  - The live start needs a config PR, demo plumbing on the live build, and the owner's word.
  - The account-wide daily loss stop covers it.
- **FAIL:** drop the coin from the shadow.
- **Several PASS:** start with the one with the best test-half calibrated PnL per $. Add one coin at a time.

## Addendum: first evaluation, 2026-11-04 17:30Z (23:00 IST)

Run as pre-registered: `coin_trial_eval.py` (md5 206f5916…) on shadow run 20261031T172449Z, window 31 Oct 17:30Z to 4 Nov 17:30Z, selection half to 2 Nov 17:30Z, simulator md5 a93c1658. Output: `2026-10-31-coin-trial-prereg-evidence/eval_20261104.txt`.

| Coin | Chosen half-spread | Test calibrated fills | Calibrated bp/$ | 1000 ms strict | 300 ms strict | Worst dip | Verdict |
|---|---|---|---|---|---|---|---|
| SOPH | ± 15 | 176 | −10.62 | −14.93 | −32.75 | −$3.80 | **FAIL** |
| PARTI | ± 15 | 76 | −0.43 | +22.43 | +38.47 | −$5.88 | **NEED MORE DATA** (150 fills needed) |
| RSR | ± 15 | 164 | +10.26 | −38.31 | −0.37 | −$3.94 | **FAIL** (strict legs below 0) |
| OP | ± 12 | 137 | +36.92 | +41.93 | −57.40 | −$3.72 | **NEED MORE DATA** (150 fills needed) |

Context (not part of the rules):

- The recorder stayed healthy. ADA's recorded Delta trades held at 1,600 to 2,500 a day.
- The coins' own activity changed a lot. Recorded trades per day, 1 Nov → 4 Nov (to 17:36Z): RSR 4,533 → 60; SOPH 4,911 → 18,993 (2 Nov) → 626; PARTI 760 → 657; OP 281 → 127.
- RSR's good selection half (+5 to +10 bp/$ at every width) did not carry into the test half, where its market went quiet.
- The strict legs rest on 12 to 45 fills, so they are noisy. The rules are applied as written.

Decision, as pre-registered:

- SOPH and RSR are dropped from the shadow at its next restart. The restart needs the owner's word.
- PARTI and OP get the final evaluation on 2026-11-07 17:30Z: same rules, window 31 Oct 17:30Z to 7 Nov 17:30Z, and no third look.
- No coin is proposed for live yet.

Shadow restarted by the owner at 2026-11-05 16:53:20Z as run 20261105T165320Z, with ADA, PARTI and OP only.

- Same commit (ca140f6). The binary was not rebuilt: it is byte-identical to the live bot's.
- The 7 Nov evaluation joins both runs, as the method allows.

## Addendum: final evaluation, 2026-11-07 17:30Z (23:00 IST)

Same script (md5 206f5916…) and rules, run on shadow runs 20261031T172449Z, 20261105T165320Z and 20261107T044402Z. Window 31 Oct 17:30Z to 7 Nov 17:30Z; the selection half ends 4 Nov 05:30Z. Output: `2026-10-31-coin-trial-prereg-evidence/eval_20261107.txt`. Only PARTI and OP were open. SOPH and RSR failed on 4 Nov and left the shadow on 5 Nov; their lines in the output are not a second look.

| Coin | Chosen half-spread | Test calibrated fills | Calibrated bp/$ | 1000 ms strict | 300 ms strict | Worst dip | Verdict |
|---|---|---|---|---|---|---|---|
| PARTI | ± 15 | 232 | −9.38 | −18.91 | −10.92 | −$10.54 | **FAIL** |
| OP | ± 12 | 256 | −14.00 | +22.32 | −25.36 | −$9.58 | **FAIL** |

Decision, as pre-registered:

- No coin from this trial goes live; ADA stays the only market.
- PARTI and OP leave the shadow at its next restart. That restart needs the owner's word.
- Any further market needs a fresh scan and a new pre-registration.
