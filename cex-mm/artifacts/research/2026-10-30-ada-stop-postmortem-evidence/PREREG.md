# Pre-registration: smaller size or cap for ADA after the 30 Oct stop

Written 2026-10-30 02:11Z, before any variant below has been run on any data. The only result already seen is the
live run itself: −1.14 bps per $ over 1,829 fills (stop rule STOP), stopped 02:02:52Z and flattened.

## Question

Live run `20261028T164352Z` (binary 05c87578, PR 74 edit-size fix, quote 200 / cap 600 contracts) lost money in
two ADA dumps (29 Oct ~20:00–21:00Z and ~00:00–00:30Z 30 Oct) with the position at the 600 cap. Would a smaller
quote size or a smaller inventory cap have kept PnL per dollar traded at +1 bp or better? One knob family (size/cap);
spread, skew and everything else unchanged.

## Variants (contracts: quote / cap)

| id | quote | cap |
|---|---|---|
| A | 200 | 600 (live config, baseline) |
| B | 200 | 400 |
| C | 200 | 200 |
| D | 150 | 300 |
| E | 100 | 300 |
| F | 100 | 200 |

## Metric

PnLbp = (cash flows of all fills + final inventory marked − fees) / sum of fill notional × 1e4.
Maker fee 2.12 bps. Funding is excluded (reported separately).

## Test 1: real-fill clip replay (primary)

Replay the live run's real Delta fills in time order (1,930 ADAUSD fills inside the run, 28 Oct 16:43:52Z –
30 Oct 02:02:52Z). Each fill's size is scaled by quote/200. A fill that adds to the position is cut to the room left
under the cap (dropped if none); a fill that reduces may cross zero but is cut so |position| stays within the cap.
Final inventory is closed at the flatten fill price (0.1861) and pays the taker fee (5.31 bps).

- Sanity check (gates the test): variant A must reproduce the venue's trading PnL for the run (fills + flatten,
  fees as charged, funding excluded) within $1.00. If it does not, Test 1 is void.
- Gate T1: PnLbp ≥ +1.0 with ≥ 300 fills.
- Known bias: with a smaller position the live bot's inventory skew and pulled sides would have been different,
  so some later fills would not have happened at those prices. The replay keeps them. It answers "same tape, less
  inventory", not "what the bot would have done".

## Test 2: shadow simulator (robustness)

`scripts/shadow_fill_sim.py` (md5 a93c1658…, commit 5c6f456), classic engine, the shadow's logged ADA quotes
("bot quotes" row), run `20261025T174640Z`, quotes and Delta public trades received from 2026-10-26T18:30:00Z
(00:00 IST 27 Oct) to 2026-10-30T02:03:00Z, both dumps inside. Quote size set so the simulator's contract count
equals the variant's quote; cap = quote × max-inv-orders (all variants are whole multiples).

Legs: 300 ms strict, 1000 ms strict (its own `--latency-ms 1000` run), 300 ms touch.

- Gate T2: PnLbp ≥ +1.0 with ≥ 300 fills on every leg.
- Known bias: the live bot was quoting ADA for the whole window, so the tape holds our own fills at our price
  (strict under-counts, touch over-counts) and the shadow's quotes carry no inventory skew.

## Decision rule

- A variant is a restart candidate only if it passes T1 (with the sanity check holding) and T2.
- Among candidates: the highest Test 1 PnL$; if two are within $0.50, the one with the smaller cap.
- If no variant passes: no restart proposal for ADA at these settings; the bot stays off and the shadow keeps
  recording.
- Descriptive only (not gates): per-window attribution for W1 = 29 Oct 19:30–21:30Z and
  W2 = 29 Oct 23:30Z – 30 Oct 01:30Z (spread capture, 60 s markout, inventory, fees), and each variant's PnL in
  W1 and W2.
- A restart, if any, also needs a calm market (no abort trip for 2 h, ADA 1 h realized vol back near its median)
  and the owner's explicit word.
