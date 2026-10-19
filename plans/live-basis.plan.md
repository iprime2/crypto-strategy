---
name: Live basis source for the Binance-anchored fair
overview: Make the Binance-anchored fair safe to run live. Its basis must come from a Delta price our own quotes cannot move, and no other term of the fair may read our own quotes. First harden the live path the 13 Oct run exposed, record the candidate sources in the shadow, then judge them with a live-mode replay and a pre-registered gate. The real bot stays off throughout.
todos:
  - id: p0-readonly-checks
    content: "P0 (read-only, VM): confirm why fills arrived 15-30 s late on 13 Oct; 10-min ob_l2 probe on all four shadow symbols"
    status: completed
  - id: pr-a-live-path
    content: "PR A: live-path robustness: private fill feed reconnects; ticker off the hot path (background poller with timeout); clip the adding quote to cap - |q|"
    status: completed
  - id: pr-b-depth-logging
    content: "PR B: ob_l2 depth feed + depth price (mm-core) + candidate logging (depth, mark/index, Binance qty) + raw ob_l2/mark recording; no behaviour change"
    status: completed
  - id: pr-c-source-safety
    content: "PR C: MM_BASIS_SOURCE=book|depth; OFI out of the anchored fair; one live-anchor check with an allowlist across live.sh, the bot and the OEMS; anchor-off pulls quotes live"
    status: completed
  - id: pr-d-replay
    content: "PR D: scripts/basis_replay.py (live-mode replay, pinned gate) + tests; Python unittests in CI"
    status: completed
  - id: pr-e-ghost-orders
    content: "PR E: fills update the OMS by order id (needs one real demo user_trades frame first)"
    status: completed
isProject: false
---

# Live basis source for the Binance-anchored fair

**Why:** `cex-mm/artifacts/research/2026-10-13-shadow-anchor-interim.md`, finding 2. In a live run our quotes are the Delta touch about 95% of the time, so the current basis gate starves the anchor (on only 39–74% of the time) and biases it. STRATEGY.md §4.2 (anchored fair) stays the design source.

**Plan review (2026-10-13):** three adversarial reviews (microstructure, engineering and live safety, evaluation) found must-fix gaps in the first draft. This version includes every must-fix. The main changes:
- a second self-reference (OFI) is removed;
- the success gate no longer uses a yardstick that a perfect predictor fails;
- the live refusal now covers every launcher;
- live-path bugs come first.

## Findings this plan rests on
- **Delta India public websocket** (probed live from the Tokyo VM):
  - `ob_l2` sends a full 15-level snapshot per side every 500 ms, keys `a`, `b`, `sy`, `ts`, `lts`.
  - `mark_price` works with the symbol `MARK:ADAUSD`.
  - `l2_orderbook`, `l2_updates` and `v2/ticker` are rejected.
  - Not yet checked: whether `ob_l2` re-sends an unchanged book (the docs say "at least every 10 s").
- **ADA book:**
  - one 28k–90k-contract ladder on a 0.0002 grid, with a 0.0003 (12.9 bps) touch spread;
  - 1–4-contract dust on the ticks between levels;
  - other makers of about our size (239–300 contracts);
  - a repricing ~3,850-contract bid.
- **Two self-references in the anchored fair today:**
  1. The basis (fixed by this plan).
  2. OFI. The anchored fair is anchor × (1 + OFI), and OFI's denominator is the L1 size, which is our own 200-contract quote live. On the real 13 Oct live book, the OFI term was |p90| 2.5, p99 9.9, max 31 bps, against under 0.1 bps on a clean book. It grows as 1/Q, so smaller live sizes make it worse.
- **Live-path bugs (13 Oct):**
  - The private fill feed can end for good on one send or parse error (`ws.rs` `?` exits).
  - The funding ticker is a REST call awaited every loop with no timeout. If it hangs, the symbol loop freezes while the separate dead man's switch keeps being acked, so resting orders go unmanaged.
  - The adding quote is a full order just below the cap.
  - Fills never update the OMS, which leaves "ghost" orders tracked after a full fill.
- **The OMS cannot subtract our own orders reliably.** It has no sizes, fills don't reach it, and it records the new price at the REST acknowledgement while the book may still show the old one. So the source must not depend on knowing our orders.

## Design
- **Depth price.** The price at which cumulative size first reaches **X contracts**, per side; the depth mid is the midpoint.
  - Pure function in `mm-core`. It returns a reason with `None`: thin (X not reached within 15 levels), stale, crossed, or an empty side.
  - X is set per symbol in **base units** (`MM_BASIS_DEPTH_QTY_<SYM>`) and converted with `contract_value`, following the base-units rule for `mm-core`.
  - The default sits in a **gap** of each symbol's inside-size distribution. ADA: 10,000 contracts, between the 3,850 order and the 28k ladder. The other symbols are chosen from the P0 probe.
    - Chosen (PR B, `config/dism.env`): ADA and BERA 10,000, DUSK 300,000 (3,000 contracts), KITE 100,000 (1,000 contracts) base units. On the 14 Oct probe each is reached on every snapshot within 8 levels. Others' inside size never fell in [X − Q, X) for Q up to 200 contracts (KITE: up to 50).
  - Startup refuses X ≤ 2 × our order, a feed switched off, or an unusable threshold when the depth source is anchored (PR C); a logged-only depth basis warns.
- **Immunity, stated exactly.** Our order of size Q cannot move the depth price unless the other orders priced better than it total between X − Q and X. The replay counts how often that band is hit (the pivot share), using the logged inner size and price.
  - Immunity to **other makers reacting to us** (repricing or pegging to our quote) cannot be shown by any shadow. It is checked on the first live run (below).
- **Feeds.**
  - One reusable reconnect helper in `mm-delta`: connect timeout, subscribe check, silence timeout ≥ 15 s, backoff, a rate-limited WARN on error or unparsed frames, an ERROR when the task ends, and a respawn. Tested against a local websocket server.
  - It carries `ob_l2` for all symbols on one connection, separate from `ob_l1`, so a depth failure cannot touch `BookWatch`.
  - Depth age is measured from the last received frame on the local clock, not from book changes.
- **Mark and index.**
  - A background public ticker poller in `mm-delta`: every 3 s, with a 2 s timeout, lenient parsing, missing → `None`. It runs in dry-runs and live alike.
  - It replaces the per-loop awaited REST call and also feeds funding carry.
  - The mark stays **logged only**; it is not a source until it is scored.
- **Logging (new MM_METRICS fields, no renames, `None` skipped).** Shipped names:
  - PR B:
    - `depth_mid`, `depth_qty` (X in contracts);
    - per side (`bid`/`ask`): `depth_<side>_px`, `_lvl`, `_inner` (size priced better), `_inner_px` (the level just inside), `_nlvl` (levels in the snapshot);
    - `depth_age_ms` (local clock), `depth_ts_us` (venue time: the join key to the book file);
    - `depth_none`: `no_feed`, `stale`, `invalid`, `crossed`, or per side, e.g. `ask_thin`;
    - `binance_bid`, `binance_ask`, `binance_bid_qty`, `binance_ask_qty` (B and A parsed as optional).
  - PR A: `mark_price`, `spot_price`, `ticker_age_ms` (the plan's `mark_age_ms`), `fills_feed_up`, `fills_feed_fills`.
  - PR C: `basis_src`, `basis_updated`, `anchor_off_reason`. The OFI term is rebuilt from logged fields: clamp(`ofi_beta` × `ofi` / (`book_bid_qty` + `book_ask_qty`), ±50 bps).
  - A pivot cannot be read from a live row (`_inner` includes our own size). Count it on clean rows or on the replay's synthetic book, and size the move with the depth price at X − Q.
  
  One EMA, the source in use, stays `basis_bps`; the replay can rebuild any other EMA.
- **Raw recording.** The shadow recorder also writes raw `ob_l2` and `mark_price` for all four symbols to `delta_<env>_book_<day>.jsonl`, apart from the trade files. The `MARK:` prefix is mapped per channel. Unchanged books are skipped (same levels and `lts`) unless 10 s old. Measured 14 Oct: about 190 MB a day before gzip.
- **Source knob.** `MM_BASIS_SOURCE=book|depth`, resolved per symbol. An unknown value fails the start, in a dry-run as well as live.
- **No self-reference while anchored.** With an anchor weight above 0, OFI is off (PR C); computing it on the `ob_l2` depth is a later option. The old fair (`fair_delta`) keeps it, as the replay's baseline.
- **Live safety.**
  - One pure, unit-tested `live_anchor_check`, used by both the Delta and Bybit paths. It resolves per-symbol keys and allows a live anchor only for the source named in `MM_FAIR_ANCHOR_LIVE=depth` (a source name, not `1`).
  - `live.sh` refuses any nonzero `MM_FAIR_ANCHOR_WEIGHT(_SYM)?` and any `MM_FAIR_ANCHOR_LIVE` line until the user lifts it.
  - The OEMS `config_guard` rejects UI overrides of the anchor and basis keys, so they come from the profile file only.
  - In a live run with the anchor on, **the first quotes wait for the anchor, and an anchor off for more than `MM_FAIR_ANCHOR_OFF_PULL_SEC` (default 10) pulls quotes** instead of quoting on the old fair, which reads our own quotes. The depth source has a short basis max age (30 s), so a dead depth feed turns the anchor off fast; a gap past it restarts the 60 s warm-up, so each such gap costs about 90 s of G1's budget. The pull counts contiguous off-time, so a flapping anchor is caught by the `anchor on < 95%` abort, not by the pull.
  - Quotes stay post-only; no new order path; cancel-all coverage is unchanged.

## Gate before asking for real money (ADA, ≥ 24 h shadow on the new build)
Judged by `scripts/basis_replay.py`. Q comes from config, and every term derived from L1 is recomputed on a synthetic live book (the logged book plus our quotes): the mid/microprice blend, OFI, the post-only clamp, the fair-jump check and the fallback.

**Owner's decision, 18 Oct 2026:** G1, G2, G3 and the 60 s lead (G4) decide. G5 exposure and the +5 s slope are diagnostics, printed but not in the verdict. Pick-off is judged only in the small, capped first live run with its pre-set stop (below). G6 is judged outside the replay.

| | Gate | Why |
|---|---|---|
| G1 health | Depth snapshot ≤ 2 s old and anchor on, each on ≥ 95% of Binance-fresh rows. `basis_updated` means "updated this loop from a snapshot ≤ `MM_DEPTH_STALE_MS` old". | Feed uptime. It cannot fail on self-reference by design. |
| G2 equivalence | p90 \|EMA basis_depth − EMA clean-L1 basis\| ≤ 1.5 bps, and pivot share ≤ 1% of rows. | Depth must reproduce the clean-book basis that the memo's evidence is about. |
| G3 no self-reference | In the live-mode replay at the planned Q: p99 \|anchored fair (live book) − anchored fair (clean book)\| ≤ 0.5 bps. | Catches OFI-like leaks. |
| G4 60 s lead | The slope of Delta's mid move at +60 s on (fair − Delta mid) is at least the old fair's, with the difference CI above 0. The +5 s slope is a diagnostic. | Binance-free evidence that the fair leads Delta (memo finding 3). |
| G5 exposure (diagnostic) | Side-averaged exposure at +30 s and +60 s against the bound upper 95% CI ≤ +1 pp vs the clean old fair, per-side +3 pp; +1 s and +5 s too. Not in the verdict. | On every real ADA window (13 Oct 2.65 h, 15 Oct 0.4 h, 15-18 Oct 64 h) a fair that knew Delta's future mid failed these, because Delta lags: they cannot judge a fair. |
| G6 live path | PR A merged; the frozen-book watch merged; PR E merged or its absence accepted by the user. | 13 Oct failure modes, and the 17 Oct Delta freeze that the stale-book guard could not see. |

The replay prints:
- two oracle rows (fair = future mid at +5 s and +60 s), each scored on every component (G4@5, G4@60, G5@30, G5@60). No gate may rely on a metric the oracle fails: if either oracle fails the deciding component G4@60, G4 is n/a and the verdict reads INCOMPLETE; a diagnostic an oracle fails is marked n/a. An oracle never fails its own horizon (its quotes sit 5 bps clear of the mid it knows), so the misses are cross-horizon. On the 13 Oct, 15 Oct and 15-18 Oct ADA windows the oracles failed G4@5, G5@30 and G5@60, never G4@60 (64 h: the +5 s oracle +3.6 / +4.4 pp more exposed at +30 / +60 s than the old fair; the +60 s oracle +4.7 pp at +30 s, and its +5 s slope 0.088 against the old fair's 0.160). That is why those three are diagnostics;
- both baselines (the clean old fair, and the live-mode old fair after the OFI fix);
- a depth-mid yardstick next to the L1-mid one, with recentred exposure;
- a latency sensitivity at 0, 1 and 2 loops;
- a **"not modelled"** block: inventory and side drops, takers arriving when our quote is stale, latency races, ghost orders, other makers reacting.

Conventions the script fixes: the CI is a percentile block bootstrap on 5-min wall-clock blocks from the first row, 1000 reps, seed 1 (on 0.4 h that is 5 blocks); "exposed" is a resting quote within 1 bps of or through Delta's mid at +h; G3 is taken on rows anchored in both replays; G5 on rows where both sides rest in both variants; G1's depth threshold is the 2 s above regardless of the profile's `MM_DEPTH_STALE_MS`; the replay's basis max age follows PR C's default (300 s book, 30 s depth) unless `MM_BASIS_MAX_AGE_SEC` is set.

The verdict reads PROVISIONAL under 24 h (within one loop). Exit 0 means G1-G4 were all evaluated and passed; the diagnostics never change the exit code.

## Pre-registered first live run (only if G1–G4 and G6 pass and the user says go)
This is the only place pick-off is judged (owner's decision, 18 Oct 2026): the shadow cannot see takers reacting to our quotes.
- ADA only. Small and capped: Q and the inventory cap set by the user before the start and written into the run's config; the protocol assumes no more than the 13 Oct run (200 contracts, cap 600). With OFI out of the fair, a smaller Q no longer adds self-reference.
- **The existing stop rule:** PnL per $ < −2.6 bps at 300 fills or < 0 at 1,000, plus the $15 a day loss stop.
- **Anchored aborts:**
  - live vs shadow `basis_depth` over the same period, p99 |difference| > 0.5 bps;
  - live anchor on < 95%;
  - |OFI term| > 0.5 bps;
  - the depth price within one tick of our own price on > 1% of rows (another maker pegging to us).
- **Report (the pick-off verdict):** capture at the fill, bnet60, and the whole-order vs partial 60 s markout split with CIs, against 13 Oct (capture +0.05 bps; whole-order fills −2.77 bps at 60 s, partial +0.71).
- **Only this run can tell:** whether informed takers still pick off the anchored quotes; our requote latency against theirs after each 4.2 bps Binance tick; the inventory path; and whether other makers reprice around us.

## Work, in order

| Step | What | Files (≤ 5 per PR, docs as a separate commit) | Proof |
|---|---|---|---|
| **P0** | Read-only on the VM: grep the 13 Oct live `bot.log` for the private fill feed ending or erroring; a 10-min public `ob_l2` probe of all four shadow symbols (re-sends on quiet books, level counts, size gaps). | none | Command output in the PR description. |
| **PR A** | Fill feed reconnects on every error (auth and error frames logged, task end logged). Ticker moves to the background poller with a timeout, and funding reads from it. The adding quote is clipped to cap − \|q\|. | `mm-delta/src/ws.rs`, `mm-delta/src/rest.rs`, `mm-bot/src/runner.rs`, `mm-core/src/strategy.rs`, `mm-bot/src/exchange.rs` | Tests: the reconnect loop against a local server; a ticker timeout does not block the loop; clip at the cap boundary. `cargo test --workspace --locked`. VM dry-run. |
| **PR B** | Reconnect helper + `ob_l2` feed, depth price + reasons, the candidate fields, raw `ob_l2`/`mark_price` recording. No behaviour change. | `mm-core/src/fair.rs`, `mm-core/src/lib.rs`, `mm-delta/src/book.rs`, `mm-binance/src/lib.rs`, `mm-bot/src/runner.rs` (+ `record_delta.rs`, `shadow.sh` in a second commit) | Tests: the probe frame; dust; our order; the pivot band (others 1,850 + ours 200 at X = 2,000 moves the price); thin, crossed and empty sides; `contract_value` 100; B/A missing. A 30-min run beside the live shadow, joined on `ts_ms`: fair, bid, ask and basis are identical. |
| **PR C** | Source knob, OFI out of the anchored fair, `live_anchor_check`, anchor-off pull, `live.sh` and OEMS guards, shadow profile on `depth` (BERA, DUSK and KITE weight 0, so ADA is the only anchored symbol; DUSK leaves the shadow). | `mm-bot/src/runner.rs`, `mm-core/src/fair.rs`, `scripts/live.sh` + `test_live_sh.py`, `backend/mm-oems/src/config_guard.rs`, `config/dism.env` | Unit tests for the check (per-symbol keys, unknown source, Bybit path) and for "constant own touch gives an OFI contribution of about 0". A 15-min VM dry-run with one forced `ob_l2` reconnect: G1 per symbol. |
| **PR D** | `basis_replay.py` (stdlib), its tests, Python unittests in CI. | `scripts/basis_replay.py`, `scripts/test_basis_replay.py`, `.github/workflows/pr.yml` | Synthetic tests: gate starvation, depth immunity, pivot band, oracle row, block CI, `--exclude`, thin data exits 2, and a parity mode that reproduces livegate's 74.1 / 7.6. Manual QA: replay basis = logged `basis_bps` within 1e-3 bps on a PR C dry-run (the log's `ts_ms` is integer ms while the bot's EMA clock is an `Instant`: a 1 ms error in the time weight at a 120 s half-life moves a 5 bps clamped sample by ~3e-5 bps; measured max 6e-5 bps on 15 Oct, 1e-4 on 13 Oct. Met on the PR C build's own shadow log, 18 Oct run `20261018T141012Z`, first 10 min: 100% of 1,488 ADA rows, max deviation under 1e-5 bps, because the replay runs the average on the logged `basis_t` and seeds and resyncs from `basis_n`; bid, ask and side flags reproduced on 100% of rows); calibration against the real 13 Oct window (touch occupancy ±10 pp, spread p50 ±1 bps, OFI p90 ±1 bps), touch occupancy meaning "a placed quote is within the requote tolerance of the touch" on both books. Result on 13 Oct: touch occupancy real 92.1% vs synthetic 96.6% PASS (a weak measure: the clean book with no order of ours scores 91.1% on it, and the old log has no own-touch flag), spread p50 real 8.42 vs synthetic 7.19 bps FAIL, OFI p90 real 1.85 vs synthetic 3.76 bps FAIL: UNCALIBRATED, so G3 from the synthetic book is n/a on that window (the live bot was two-sided on 86% of rows and its requote latency and fills are not modelled) and the first PR C live log, which logs the own-touch flag, must re-run it. |
| **PR E** | Fills reach the OMS: an mpsc `FillEvent{order_id, contracts}` drained each loop; decrement on a partial fill; clear only when the venue says closed; ignore unknown or replaced ids. | `mm-bot/src/oms.rs`, `mm-bot/src/runner.rs`, `mm-delta/src/ws.rs` | Needs one real `v2/user_trades` frame captured on demo first (user's go-ahead). Tests: partial, full, stale id, unknown id. **Built 19 Oct** on the frame captured on demo (size is a string, fill id `f`, order id `o`). When the fills reach a quote's size the loop asks `GET /v2/orders/{id}` and forgets it only if closed or cancelled; still open resyncs the remainder. A failed cancel asks the same way, then falls back to cancel-all, so no quote is forgotten while it may rest. Delta's edit `size` semantics are unverified; the loop keeps the smaller remainder. Not yet run against real orders. |

**Sequence:**
1. P0 now.
2. PR A and PR B in parallel.
3. Restart the shadow on the new build after the current run's 24 h mark (~07:40Z on 14 Oct), with the user's go-ahead.
4. PR C and PR D during the next 24 h.
5. Run the replay and write the memo.
6. The user decides on the live run under the protocol above.
7. 18 Oct: the 64 h review (memo `2026-10-18-shadow-3day-review.md`) and the owner's gate decision above. PR C merged with ADA the only anchored symbol; the shadow restarted on it without DUSK (run `20261018T141012Z`, 14:10Z). The replay judges its first 24 h (from about 14:10Z on 19 Oct); the frozen-book watch is its own PR.

**Stop:**
- If `depth` fails G2 or G4, score `mark` (with a learned offset) in the replay before changing anything else.
- Do not widen the spread to compensate.

## Risks
- The `ob_l2` cadence adds up to 0.5 s of lag. Measured trend bias at a 120 s half-life is ≤ 0.2 bps.
- The depth mid moves in ladder blocks of 0.0001 (about 4.2 bps, the same as Binance's tick); the EMA absorbs them (the clamp binds on 3% of samples).
- The 15-level cap: KITE reaches 2,000 contracts at level 10 of 15. If thin books starve the basis, move to `ob_updates` (full book, sequence number and CRC).
- Delta renamed its channels once (Apr 2026). A missing or invalid frame means "no update", never zero.
- Log volume grows (about 1 GB a day for 4 symbols before rounding and skip-None), which shortens `live.sh status`'s window.
