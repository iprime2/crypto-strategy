# QA note: PR E (fills reach the OMS) on Delta demo
**Date:** 2026-10-19 · **Venue:** Delta India demo (testnet), real orders on the demo account · **Symbol:** BTCUSDT (demo BTCUSD: 0.5 bps spread, a trade every few seconds; demo ADAUSD had a 277 bps spread and no trade for 35 min on 15 Oct, so it would see no fills) · **Build:** c5a753b (PR E merged), release, Tokyo VM · **Run:** 17:29:45–17:44:45Z, `mm-bot run --env testnet`, 2-contract quotes, cap 4 contracts, fixed half-spread 1 bp, requote tolerance 1 bp, loop 400 ms, anchor off, dead man's switch off (see finding 4) · **Data:** bot log, Delta `/v2/fills`, and a read-only poll of open orders every 3 s (301 polls).

## Question
Does PR E work against real venue behaviour: do fills reach the loop by order id, are partial and full fills booked right, is a filled quote re-quoted, and does the bot ever leave two quotes resting on one side?

## Outcome
- **Fill routing passes.** Delta booked 54 fills (93 contracts, all maker); the bot's feed delivered the same 54 fills, 93 contracts, same order ids. Final bot inventory +0.002 BTC = venue position +2 contracts.
- **No ghost orders.** At most 1 buy and 1 sell open in every poll; cancel-all at the end left 0 open orders.
- **Partial fills pass.** 5 partial fills (1 of 2 contracts), each booked as 1 left.
- **Delta's order state trails the fills feed.** Of 45 fills that completed a quote, 32 read `closed` on the first check (about 150 ms after the fill) and the side was cleared; 13 still read `open` with the pre-fill size. Those quotes stayed tracked until the requote path asked again (0.45–0.74 s later when the price moved; once 29 s, while the bid was wanted).
- **Edit size is the order's total.** Order 2175777835: 1 of 2 filled, edited to size 2; the venue then showed size 2, unfilled 1. One observation.

## Findings
1. **Stale `open` after a full fill (13 of 45).** About 43 s of the 900 s had a wanted side unquoted after a stale answer, 29 s of it in one case (17:41:57). Longer gaps at 17:36 and 17:38 were the inventory cap switching the side off, as designed. Fix: ask the venue again each loop for up to 5 s before believing an `open` answer (`SETTLE_PATIENCE`, PR after #46).
2. **The requote path healed every case.** Each stale quote was later forgotten through `pull_quote` (its cancel failed and the venue then read the order closed). The cancel-all fallback never ran, and the run logged no `cancel failed` warning.
3. **Post-only rejects:** 5 `immediate_execution_post_only` on places after the book moved; no risk kill, halt or taker fill.
4. **Dead man's switch:** the first start refused with `heartbeat create: bad_schema`. Delta now requires `default_ttl` on create (PR #47). This run therefore ran without the switch (the demo default).

## Caveats
- Demo flow is not mainnet flow; this proves plumbing, not edge.
- The edit-size reading is one observation.
- The stale-`open` fix and the heartbeat fix are not yet run against real orders.
