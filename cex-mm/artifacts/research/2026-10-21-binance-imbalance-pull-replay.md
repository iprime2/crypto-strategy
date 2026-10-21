# Binance queue imbalance: it calls the next 4.5 bps tick, but pulling the threatened quote on it gains little so far

**Date:** 2026-10-21 (out-of-sample result due 22 Oct) · **Venue:** Delta India mainnet, real orders · **Symbol:** ADAUSD · **Runs:** `20261020T110544Z` (stage 1, 100 contracts, 4.9 h), `20261020T155754Z` (stage 2, 200 contracts, 22.6 h), `20261021T143121Z` (c1a8080, concurrent order calls, 200 contracts, 2.5 h); 1,281 real fills in all · **Tape:** shadow recorder `20261020T105953Z`, `20261020T155640Z`, `20261021T143109Z`.

Scripts (read-only, run on the VM, copied verbatim into `2026-10-21-binance-imbalance-evidence/`): `microprice.py` (the signal), `lean_replay.py` (the counterfactual), `refresh_fills.py` (brings a run's `fills.json` up to date from Delta with a signed GET). Follows `2026-10-21-live-stage1-2-tick-pickoff-latency.md`, which found that the remaining losses come right after a Binance tick and listed this study as step 4.

## Question

Binance spot ADAUSDT moves in one 4.5 bps tick at a time, and our losing fills come in the moment after that tick. Does Binance's queue imbalance at its best levels, I = bid_qty / (bid_qty + ask_qty), say which way the next tick goes early enough to move or pull our quote, and would doing so have made money on the live runs?

The bot logs the Binance sizes every loop (`binance_bid_qty`, `binance_ask_qty` in `MM_METRICS`) but does not use them for quoting (`mm-bot/src/runner.rs`: they reach the metrics row only).

## Findings, ranked by money at stake

1. **The imbalance calls the next Binance tick.** Stage 2's log (200,562 loop samples over 22.6 h; Binance spread p50 4.5 bps, so a step is always one tick):

   | I | samples | next move up | median s to it | of the samples within 1 s of a move: n, next move up |
   |---|---|---|---|---|
   | 0.00–0.10 | 8,248 | 19.5% | 4.8 | 1,676, 0.8% |
   | 0.10–0.20 | 25,480 | 31.3% | 9.6 | 1,812, 3.3% |
   | 0.20–0.35 | 41,566 | 38.8% | 11.6 | 1,583, 13.5% |
   | 0.35–0.50 | 21,058 | 44.7% | 13.4 | 555, 28.8% |
   | 0.50–0.65 | 20,823 | 53.2% | 12.8 | 589, 62.6% |
   | 0.65–0.80 | 47,258 | 59.9% | 12.4 | 1,598, 82.4% |
   | 0.80–0.90 | 26,252 | 69.3% | 9.6 | 1,863, 96.2% |
   | 0.90–1.00 | 9,865 | 84.4% | 4.8 | 1,910, 99.6% |

   - The last column picks samples by when the move came, which a quoting bot does not know. It shows that the queue is nearly always lopsided the right way just before a tick. The tradable figures are the unconditional ones: at I < 0.1 the next tick is down 80% of the time and comes in a median 4.8 s.
   - Before 75% (stage 1, 80 of 107) and 80% (stage 2, 48 of 60) of our pick-off fills (a ≥ 3 bps Binance move toward the quote in the 2 s before the fill), I already pointed the right way at the last sample before the move (I < 0.35 before a bid fill, > 0.65 before an ask fill; p50 0.17 and 0.19 for bid fills, 0.83 and 0.87 for ask fills).
   - A threatened side would be off often: in stage 2, I < 0.2 in 16.8% of samples and I > 0.8 in 18.0%, before any re-place delay.

2. **Pulling or moving away the threatened quote would have added a little, not much, and not reliably.** Counterfactual replay of the three live runs against Delta's recorded public trade tape (method below). PnL in dollars, fills valued at the Binance mid × (1 + basis) 60 s and 300 s later, minus the fee paid:

   | Variant | c1a8080, 2.5 h | Stage 1, 4.9 h | Stage 2, 22.6 h | **Sum, PnL60 / PnL300** | $ traded | bps per $ (60 s) |
   |---|---|---|---|---|---|---|
   | Real quotes | +0.37 / −0.34 | +0.13 / −0.56 | +3.70 / +4.83 | **+4.20 / +3.93** | 21,061 | 2.0 |
   | pull 0.2 | +0.45 / −0.59 | +0.90 / +0.95 | +3.18 / +4.53 | **+4.53 / +4.89** | 15,041 | 3.0 |
   | pull 0.1 | +0.48 / −0.62 | +0.38 / −0.71 | +3.41 / +5.86 | +4.27 / +4.53 | 18,832 | 2.3 |
   | pull 0.3 | +0.27 / −0.55 | +0.97 / +1.44 | +2.56 / +3.12 | +3.80 / +4.01 | 11,829 | 3.2 |
   | away 2 | +0.56 / −0.47 | +0.65 / +1.19 | +3.51 / +3.57 | **+4.72 / +4.29** | 14,986 | 3.1 |
   | away 1 | +0.46 / −0.01 | +0.43 / +0.53 | +3.55 / +4.12 | +4.44 / +4.64 | 17,389 | 2.6 |
   | lean 1, read 400 ms early | +0.30 / +0.57 | +0.55 / +0.66 | +3.40 / +3.75 | +4.25 / +4.98 | 20,293 | 2.1 |
   | lean 1, read 850 ms early | −0.00 / −0.10 | +0.45 / +0.23 | +3.53 / +4.24 | +3.98 / +4.37 | 20,041 | 2.0 |
   | lean 3, read 850 ms early | −0.42 / −1.13 | −0.12 / −1.25 | +1.64 / +1.39 | +1.10 / −0.99 | 21,669 | 0.5 |
   | pullfast 0.2 (exploratory) | +0.42 / −0.34 | +0.78 / +0.18 | +3.32 / +4.72 | +4.52 / +4.56 | 18,436 | 2.5 |

   - **pull θ:** the threatened side is not quoted while I < θ (bid) or I > 1 − θ (ask). **away λ:** only the threatened side moves λ·(I − ½)·(Binance spread) away. **lean λ:** both quotes move by that amount. **pullfast:** pull, only when the Binance mid changed at least 6 times in the last 60 s; chosen after seeing the results below, so it is exploratory, and it is also modelled a little more kindly than pull (no re-place delay).
   - The best rules add $0.3–0.5 at 60 s and $0.4–1.0 at 300 s over about 30 hours, on a base of $4.20 / $3.93, while trading about 30% less. Per dollar traded they lift the 60 s figure from 2.0 to about 3 bps. That matters more once size grows (stage 3) than it does in dollars today.
   - **Leaning both quotes is worse**, and worse the harder it leans: moving the far side toward the market buys fills that the 4.5 bps tick then runs over. Do not build it.
   - **The busy-market gate adds nothing:** pullfast 0.2 matches pull 0.2 at 60 s (4.52 vs 4.53) and is worse at 300 s (4.56 vs 4.89).

3. **Why this is not yet an edge: the runs disagree on why it works.** The fills a rule avoids should be the losers. For pull 0.2 they were −$0.08 (c1a8080), −$0.57 (stage 1, with the fast 14–15Z rally and reversal) and **+$0.38** (stage 2, mostly calm) at 60 s. Every variant that avoids fills shows the same split: all negative in stage 1, all positive in stage 2. On the one run with today's concurrent order calls (c1a8080), every pull and away variant is within $0.35 of the real quotes at both horizons, and pull 0.2 is $0.25 behind at 300 s. Part of the gain may already have been taken by faster edits. Three runs of 2.5–23 h, two of them in different regimes, cannot separate a $0.3–1.0 difference from noise. Hence the out-of-sample test below.

4. **Mainnet cancels are about ten times faster than edits, so pulling is feasible.** From the live run `20261021T170240Z` (42b5eef, `MM_REST=debug`), 17:02–18:35Z on 21 Oct:

   | Call | n | p10 / p50 / p90 ms |
   |---|---|---|
   | Edit, `PUT /v2/orders` | 741 | 575 / 667 / 753 |
   | Place, `POST /v2/orders` | 47 | 528 / 578 / 633 |
   | Cancel one order, answered 200 | 3 | 64 / 66 / 67 |
   | Cancel one order, refused 400 (in the cases checked, the order had just filled) | 7 | 13 / 17 / 77 |
   | Cancel all, `DELETE /v2/orders/all` | 1,102 | 14 / 17 / 21 |
   | Signed GETs (order state, positions, fills, balances) | 125–1,072 each | 19–40 / 22–49 / 28–76 |

   - This closes the previous memo's open question ([UNVERIFIED] there).
   - A successful single cancel takes about 66 ms (only 3 samples). Most of the cancel-alls came during the 18:28Z calendar pause, when little or nothing was resting [UNVERIFIED whether a cancel-all with resting orders is as fast].
   - The replay's pull model (signal seen 250 ms before the trade; back 850 ms after it clears) matches a 400 ms timer loop's average wait plus one cancel. A timer-driven bot sees the signal up to 400 ms late in the worst case, so an implementation should wake on the Binance book update rather than the timer.

## Method and its limits

- **Rebuilding our quotes:** each run's resting bid and ask are rebuilt from the bot log (`MM_ORDER` places and edits, at the call's send time = ack − `ms`; runs before c1a8080 have no `ms` and assume 600 ms). While an edit is in flight the resting price is the more passive of old and new. A quote is gone from its order's last fill (exchange time, from `fills.json`), a pull, or a cancel-all.
- **The tape:** Delta's public `trades` channel (exchange trade time `t`; the VM clock is NTP-synced). Trades on the same taker side within 5 ms form one sweep.
- **Fill rule:** a real fill is kept if the sweep's worst price reached the counterfactual quote, at the counterfactual price. A sweep that did not fill us adds a fill only if it printed strictly through the counterfactual quote, for one quote's size.
- **Calibration** (replaying the real quotes should add no fills): 0, 15 and 9 phantom fills against 122, 336 and 823 real ones. Getting there took three fixes: refreshing a stale `fills.json` (`refresh_fills.py`), ending a filled quote at its last fill's exchange time rather than at the later log line, and using the more passive price while an edit is in flight.
- **Valuation:** side × (Binance mid × (1 + basis) at +60 s / +300 s − price) − fee, the fee being what Delta charged that fill (1.15–1.31 bps on average, Scalper Offer).
- **Not modelled:** inventory and the position cap (the real on/off state is kept); queue position lost by a pull and re-place, which makes pull look better than it is; Delta's rate limits; market impact of our own quotes.

## Pre-registered out-of-sample test (fixed before the data exists)

Written at 18:30Z on 21 Oct and committed with this draft. The live run it reads started at 17:02Z.

- **Data:** live run `20261021T170240Z` (42b5eef: concurrent order calls, 200 contracts, cap 600), its first ≥ 20 h. Its `fills.json` is refreshed from Delta first; the tape comes from the shadow recorder directories covering it. `lean_replay.py` is used exactly as committed here.
- **Calibration:** the real-quotes row's "new" fills must be ≤ 3% of real fills, or the result is void (fix the rebuild, do not read the variants).
- **Variants read:** pull 0.2 and away 2 (read 850 ms early) only. No new variants and no parameter changes after seeing the data.
- **A variant passes only if all three hold:**
  1. On this run, PnL60 and PnL300 are both ≥ the real-quotes row.
  2. On this run, the avoided fills' own PnL60 is < 0 (it skips losers).
  3. Pooled over this run and the three above, PnL60 and PnL300 are both ≥ the pooled real-quotes row.
- **Pass:** a default-off knob PR that pulls the threatened side on Binance imbalance, woken by the Binance book update, then a demo QA run, the owner's merge, and a live trial under the existing stop rule.
- **Fail:** drop the idea and record it here.

## Out-of-sample result

Pending: the run reaches 20 h at about 13:00Z on 22 Oct.

## Next experiment

The test above, then (only on a pass) one knob: pull θ = 0.2 on the threatened side.
- **Metric:** net60 per $ traded and the pick-off share (fills within 2 s of a ≥ 3 bps Binance move toward the quote).
- **Success:** net60 per $ above the previous run's at ≥ 300 fills and no rise in rejects.
- **Stop:** the existing stop rule and $15 daily stop.

Hold the half-spread at 5 bps (previous memo).
