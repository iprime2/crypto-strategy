# Quant memo: pre-registration of the ADA size step (200/400 → 300/600)
**Date:** 2026-10-31 (written about 14:00Z, before any shadow data after 12:00Z was simulated) · **Venue:** Delta India mainnet · **Symbol:** ADAUSD · **Decision date:** 2026-11-07 03:00Z (08:30 IST)

## Question

Should the live ADA quote go from 200 contracts (cap 400) to 300 (cap 600)?

The owner asked to raise profit by raising capital. Capital is not the binding limit: the cap of 400 ADA is about $78 against $341 of equity. Quote size is the lever. A bigger quote earns more but loses more on a crash day, so the step needs evidence from a fast market first.

## Where things stand

The current settings (fair ± 6 bps, 200 per quote, cap 400, $10 daily loss stop on UTC days) have run live since 2026-10-30 06:43Z: runs 20261030T064303Z, 20261030T105618Z and 20261031T115939Z (PR #82, frozen-book fix).

- **Live:** 922 fills at +5.42 bp/$ by 31 Oct 13:31Z.
- **Forward test:** `2026-10-30-ada-stop-postmortem.md`, addendum, passed. The worst hour in its window was only 2.0× the 61 bps median. Nothing like 29 Oct (4.9× and 6.2×) has been seen on these settings.

## Exploratory size replay (not a gate; informs this test only)

`/home/user/mm-qa/pm/size_explore.py` and `size_explore_big.py`. Calibrated leg (1000 ms, touch, Scalper Offer 15 min fifo), fair ± 6, cap = 2 quotes. "Worst dip" is the deepest fall of equity marked at each fill.

| Quote / cap | A: 26 Oct 18:30Z–30 Oct 02:03Z, both 29 Oct dumps | Worst dip | B: 30 Oct 02:03Z–31 Oct 02:10Z | Worst dip |
|---|---|---|---|---|
| 200 / 400 | +$11.28 (3.52 bp/$) | −$4.45 | +$7.99 (4.65) | −$1.05 |
| 300 / 600 | +$15.20 (3.34) | −$6.97 | +$10.75 (4.47) | −$2.00 |
| 400 / 800 | +$18.13 (3.16) | −$9.50 | +$13.38 (4.40) | −$3.21 |
| 600 / 1,200 | +$22.07 (2.82) | −$14.20 | +$16.16 (3.88) | −$6.34 |
| 1,000 / 2,000 | +$24.47 (2.17) | −$22.87 | +$19.44 (3.27) | −$13.61 |
| 1,500 / 3,000 | +$32.12 (2.20) | −$31.23 | +$22.95 (2.94) | −$20.83 |
| 2,000 / 4,000 | +$27.65 (1.58) | −$51.06 | +$28.82 (3.05) | −$26.20 |
| 3,000 / 6,000 | +$20.75 (0.92) | −$77.57 | +$44.49 (3.65) | −$31.33 |
| 5,000 / 10,000 | +$9.33 (0.30) | −$141.17 | +$47.74 (2.96) | −$47.15 |

What the table shows:

- Profit grows more slowly than size, and profit per $ falls.
- The worst dip grows faster than profit.
- Over the crash window, profit peaks near 1,500 per quote and then falls while the dip keeps growing.
- The simulator does not model queue position or our own impact, so large sizes are optimistic [UNVERIFIED beyond 200 live].

## Config under test

- Quote 300 contracts (1 contract = 1 ADA), cap 600 (2 orders), fair ± 6 bps.
- Live it would be `MM_ORDER_QTY_ADAUSDT=300`, `MM_MAX_INVENTORY_ADAUSDT=600` and `MM_DAILY_LOSS_LIMIT_USD=15`.
- Nothing else changes, and there is no code change.

## Window

- Shadow data received from **2026-10-31T12:00:00Z** (shadow run 20261031T115906Z, binary 7ffa8fb5a40f817a, and any later shadow run on the same profile).
- Live runs from 2026-10-30T06:43:03Z.
- Evaluated at 2026-11-07 03:00Z.
- Earlier only if gates 1, 2 and 4 already hold and the shadow window has at least 72 h.

## Gates (all four must pass)

1. **Live data.**
   - At least 2,000 real fills over the live runs since 2026-10-30 06:43:03Z on this profile (Delta fills, live dashboard `runs`).
   - PnL per $ traded of at least +2.0 bp.
2. **A fast market survived.**
   - At least one clock hour in the window with ADA realized vol at or above 4 × 61 = 244 bps (1-min L1-mid log returns, at least 50 minutes in the hour; `size_step_eval.py` prints these).
   - Through that day, no daily-loss halt on the live bot.
   - The worst UTC-day net of at least −$10.
   - No live position past the cap (hourly check: no rows over the cap).
3. **Replay.** `size_step_eval.py` (md5 9eddea5a82f3d05e94a747423d357070, simulator md5 a93c1658) on the window:
   - at least 72 h of data;
   - at least 300 fills on the calibrated leg;
   - calibrated leg of at least +2.4 bp/$ (+1.0, plus the 1.4 by which this leg overstated the stopped run);
   - 1000 ms strict at the list fee of at least 0;
   - the calibrated leg's worst dip no worse than −$15.
4. **No open incident.**
   - No unseen fill left unconfirmed.
   - Bot and venue positions agree.
   - No unexplained frozen-book trip with `depth_book=true`.
   - No cap breach.

## Decision

- **All pass:** recommend 300/600 with a $15 daily stop. That is a config PR to `config/dism.env`, then a restart of the shadow and the live bot on the owner's word.
- **Gates 1, 3 and 4 pass, but no stress hour came:** report that the crash case is still untested. The owner chooses: extend to 14 Nov, or step up anyway.
- **Gate 1, 3 or 4 fails:** stay at 200/400 and report which gate failed.

## After a step up (rollback)

Back to 200/400 at once, on the owner's word, if any of these happens:

- The live stop rule fires on the new run: below −2.6 bp/$ after 300 fills, or below 0 after 1,000.
- The $15 daily stop halts the bot.
- A position passes the 600 cap.

## Capacity, for the owner's question (not a gate)

Rule used: the crash-window worst dip should fit inside a daily stop of 3–5% of equity. Order leverage is 2× on Delta, and the bot refuses more than 5×.

- **$341 (now):**
  - 3% = $10 allows up to 400/800.
  - 5% = $17 allows up to 600/1,200.
  - Margin is not binding: 800 ADA is about $154, under 0.5× leverage.
- **₹50,000 (about $590 at ₹84.8 per $, the rate implied by the wallet showing ₹28.67K for $338):**
  - 3% = $17.7 allows up to 600/1,200.
  - 5% = $29.5 allows up to 1,000/2,000.
- **$50,000:** the risk budget stops binding and ADA's market does. Past about 1,000–1,500 per quote, the crash-window profit falls and the worst dip grows quickly.
  - So the useful ADA size is about 1,000–1,500 per quote, about $200–290 a quote and a cap of $400–580.
  - That puts about 1% of the money at work. More money would need more markets, not bigger ADA quotes.
