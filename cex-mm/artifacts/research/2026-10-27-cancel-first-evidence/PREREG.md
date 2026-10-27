# Cancel-first simulation: pre-registered test

Written 27 Oct 2026, before the cancel-first model has been run on any data. The owner asked for the test
after the AVAX +/-6 bps verdict (the 1000 ms leg was -0.08 bps over 417 pooled fills).

## The idea

Today the bot moves a quote with one edit (`PUT /v2/orders`, p50 667 ms on mainnet), and the old price rests on
Delta until the edit lands. Cancel-first: when the fair moves *toward* a resting quote (the bid must go down or
the ask up), cancel it (single cancel p50 66 ms) and place the new price after the cancel answers (place p50
578 ms). Moves away from a quote keep the edit. Mainnet timings: `artifacts/research/2026-10-21-binance-imbalance-pull-replay.md`.

## Model (`shadow_fill_sim.py --cancel-first CANCEL_MS:PLACE_MS`)

An event engine: the bot decides on each logged sample from the price it last asked for; a call's effect lands
after its delay; a side with a call in flight takes no new decision until it lands (the loop waits on its order
calls); an edit or cancel of an order that has already filled out does nothing; after a fill empties a side the
bot places again one loop later. Both rows compared below come from this engine:

- **edit**: every requote is an edit landing after `--latency-ms`.
- **cancel-first**: an adverse requote takes the old quote off after CANCEL_MS and shows the new one after
  CANCEL_MS + PLACE_MS. Everything else is as in the edit row.

The timings are fixed from the measured mainnet figures, not tuned on the results:

| Scenario | edit (`--latency-ms`) | cancel | re-place |
|---|---|---|---|
| base | 700 | 70 | 600 |
| stress | 1000 | 150 | 900 |

## Data

Shadow runs `20261023T082101Z` and `20261025T174640Z` (whole runs as of the time of running), strict fill rule
unless stated, maker fee 2.12 bps (the script default). Pooled = fills summed, net60 weighted by fills, PnL60 =
net60 x notional summed.

## Pass rules

**A. AVAX +/-6 bps** (`--sweep 6`). Cancel-first passes only if all hold, pooled over both runs:
1. net60 > 0 in base (strict), in stress (strict) and in base under `--rule touch`;
2. at least 300 fills in each of those three;
3. in stress (strict), cancel-first's net60 is above the edit row's.

**B. Live ADA** (the `bot quotes` rows: the shadow quotes ADA with the live config). Cancel-first is worth
building for the live bot only if, pooled over both runs, its PnL60 in dollars is at least the edit row's in
both base and stress (strict). Dollars, not bps: cancel-first trades less, so a better net60 can still earn less.

**C. Before any bot change.** Whatever passes A or B must pass the same rule again on shadow data recorded after
this file was written (at least 48 h), before a knob PR, demo QA, the owner's merge and a live trial.

**Fail** on A: AVAX stays out of the live bot. **Fail** on B: no cancel-first for live ADA; record it in a memo.
No new timings, rules or variants are read after seeing the results; anything else is labelled exploratory.
