# Leaning both quotes against our inventory: it halves time at the cap and trims drawdown, but does not add PnL; the pre-registered test fails

**Date:** 2026-10-25 · **Venue:** Delta India mainnet, real orders · **Symbol:** ADAUSD · **Runs:** `20261020T110544Z` (stage 1, 100 / 300, 4.9 h), `20261020T155754Z` (stage 2, 200 / 600, 22.6 h), `20261021T143121Z` (c1a8080, 2.5 h), `20261021T170240Z` (42b5eef, 60.9 h), `20261024T055444Z` (e8256a7, holdout, first 35.4 h); 5,009 real maker fills in all · **Tape:** shadow recorder `20261020T105953Z`, `20261020T155640Z`, `20261021T143109Z`, `20261021T170231Z`, `20261023T082101Z`.

Scripts (read-only, run in the session sandbox on copies of the VM's logs, fills and tapes; copied into `2026-10-25-inventory-lean-evidence/`): `skew_replay.py` (md5 811281fb…), `PREREG.md` (md5 def81b5e…, written at 08:48Z, before any variant result). Owner approved the replay on 25 Oct. Follows `2026-10-21-live-stage1-2-tick-pickoff-latency.md` finding 6 (inventory lean deferred) and `2026-10-21-binance-imbalance-pull-replay.md` (whose replay this extends).

## Question

The bot sits at its 600-contract cap for long stretches while ADA drifts against the position: on 24 Oct, for example, it was long 600 from 06:00 and gave back $0.42 in an hour, and it sat long 600 for 76 minutes that evening. In fixed (DISM) mode the quotes ignore inventory (`mm-core/src/lib.rs`, test `fixed_mode_quotes_fair_plus_minus_half_and_ignores_inventory_skew`). Would moving both quotes by −L·q/cap bps have cut those inventory losses by more than the spread it gives up?

## PnL attribution, real quotes vs lean 1 bps (L = 0 / L = 1, dollars)

| Run | Fills | End PnL (Δ) | Capture | Inventory | Fees | Max drawdown | Time at cap |
|---|---|---|---|---|---|---|---|
| stage 1 (100/300), 4.9 h | 343 / 316 | +0.27 / +0.98 (+0.71) | +1.49 / +1.58 | −0.73 / −0.15 | −0.49 / −0.45 | 1.26 / 0.84 | 24% / 14% |
| stage 2, 22.6 h | 824 / 697 | +7.56 / +6.93 (−0.63) | +6.71 / +6.32 | +2.70 / +2.28 | −1.84 / −1.67 | 1.11 / 0.95 | 14% / 7% |
| c1a8080, 2.5 h | 122 / 105 | −0.11 / +0.44 (+0.56) | +1.14 / +0.99 | −0.97 / −0.34 | −0.28 / −0.21 | 1.13 / 0.75 | 14% / 7% |
| 42b5eef, 60.9 h | 2,088 / 1,824 | +11.94 / +12.09 (+0.15) | +17.40 / +16.94 | −0.81 / −0.42 | −4.64 / −4.43 | 3.26 / 2.59 | 18% / 11% |
| **holdout** e8256a7, 35.4 h | 1,632 / 1,435 | **+8.22 / +7.79 (−0.44)** | +13.17 / +12.56 | −1.56 / −1.68 | −3.39 / −3.10 | 1.90 / 1.65 | 20% / 14% |
| Pooled, 126 h | 5,009 / 4,377 | +27.89 / +28.23 (+0.34) | | | | | |

Capture is valued against the anchored fair (Binance mid × (1 + basis)) at the fill; inventory is the rest of the marked-to-market PnL; all maker fills. The L = 0 row is the replay of the real quotes; for the holdout it gives +$8.22, against +$9.94 in the live report over the same run (`live_vs_shadow.py`, its own valuation and window), so compare variants with each other, not with the report.

## What the code actually does

- Fixed mode quotes `floor(fair·(1−h))` and `ceil(fair·(1+h))` with h = 5 bps and ignores inventory, apart from the cap: at |q| = 600 the adding side is off; below it, that side's size is clipped to the room (`side_order_qty`, `requote_qty`). Checked against `MM_METRICS` rows (e.g. fair 0.211246 → bid 0.21114, ask 0.21136).
- ADA's tick is 0.00001, about 0.49 bps. A lean of 1 bps at the cap moves a quote by up to two ticks, and any lean that crosses a tick boundary moves the adding quote off the level where most sweeps stop.

## Findings, ranked by money at stake

1. **The lean does not add PnL.** Per-run differences at L = 1 are +0.71, −0.63, +0.56, +0.15 and −0.44 dollars, mixed in sign and small next to each run's total. Larger leans lose money steadily: pooled in-sample end PnL +19.66 (L 0), +20.45 (1), +18.72 (2), +16.82 (3), +15.86 (5), +11.49 (8). The reducing quote gives up edge on every fill (capture falls with L), and the inventory term does not improve to match: holdout inventory PnL is −1.56 at L 0 and −1.68 to −2.18 at L 1–8.
2. **It is a risk reducer.** At L = 1, time at the cap roughly halves on every run (e.g. 20% → 14% on the holdout), mean |q| falls by 10–30%, and max drawdown on the 60 s marks is lower on all five runs (by 13–34%). Fees fall about 7% pooled because about 12% fewer fills happen.
3. **Moving the adding quote one tick away removes about a sixth of all fills.** At L = 1, 278 of the holdout's 1,633 real fills would not have happened (the sweep stopped at our level), and 80 new ones would have, on the reducing side. Queue position at the touch is most of what fills us, consistent with the 21 Oct finding that taker sweeps reach the quote the moment it is exposed.

## Method and its limits

- **Rebuild and fill rule:** as in `lean_replay.py` (21 Oct memo): resting quotes from `MM_ORDER`, a quote gone at its order's last fill, a cancel-all or a pull; a real fill kept if its sweep reached the counterfactual price; a new fill only on a print strictly through it, then that side is away for 1 s.
- **New here:** each variant keeps its own position. The cap switches its adding side off and clips its size. Where the real bot was off only because of its own cap and the variant has room, the variant quotes the bot's planned price, read 1 s earlier. A real fill the variant avoids leaves its quote resting until the bot next places on that side. The lean reads q 850 ms back: one loop tick plus a mainnet edit.
- **Rounding:** the lean shifts the raw `fair·(1∓h)` before the bot's floor/ceil. The rounding remainder comes from the loop row that priced the order; it falls back to half a tick for 4–7% of lookups.
- **Calibration** (L = 0 must reproduce the real quotes): new fills 0, 10, 8, 44 and 21 against 122, 336, 823, 2,081 and 1,633 real fills (0–3.0%; the pre-registered limit was 3%). The mean gap between the simulated and logged position was 0 to 35 contracts.
- **Changes made after the pre-registration, all before any holdout variant was run:**
  - The first version applied the lean to the already-rounded price. Any lean then moved the adding quote a whole tick, which over-stated the effect: in-sample L = 1 avoided 566 of 2,081 fills on 42b5eef, against 386 after the fix. Found in the in-sample output, fixed, and the in-sample selection was run again (the v1 md5 is ce5433eb…).
  - Two diagnostics were added that do not change any result: the position gap and the residual fallback rate.
  - The holdout's fills were refreshed, which extended it from 26.7 h to 35.4 h before it was read.
- **Not modelled:** the requote tolerance (3 bps; the bot edits on most Binance ticks anyway). A sensitivity run with a 2.5 s lag gives the holdout L = 1 +$7.95 against +$8.22, so the verdict holds. Also not modelled: queue position lost by an edit, our own impact on the book, and Delta's rate limits. The marks come from the anchored fair, not Delta's mid.

## Pre-registered test (PREREG.md) and result

- Candidates L ∈ {1, 2, 3, 5, 8}. L* = the best pooled in-sample end PnL = **L = 1** (+20.45 vs +19.66).
- Holdout conditions for L* = 1:

| Condition | Result |
|---|---|
| 1. Holdout end PnL ≥ L = 0 | **fail** (+7.79 < +8.22) |
| 2. Holdout max drawdown ≤ L = 0 | pass (1.65 ≤ 1.90) |
| 3. Pooled five-run end PnL ≥ L = 0 | pass (+28.23 ≥ +27.89) |
| **Verdict** | **fail: no lean knob is built** |

## Next experiment

None from this memo for PnL. The measurement worth keeping is finding 2: at today's size the lean buys about a third less drawdown and half the time at the cap for roughly zero PnL. If the owner later wants to raise the size or the cap and values drawdown over PnL, a drawdown-first lean (L ≈ 1) would need its own pre-registered test on new data. It cannot be judged on these runs, which chose it.

Hold the half-spread at 5 bps and fixed mode as is.
