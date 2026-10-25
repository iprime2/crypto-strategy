# Inventory-lean replay: pre-registration (written 25 Oct 2026 ~09:00Z, before any variant result)

Knob: both quotes move by -L * q / cap bps (q as the bot saw it 850 ms earlier). L = 0 is today's bot.

Script: scratchpad/skew/skew_replay.py, as written at this point (md5 recorded in the memo).

Calibration (L = 0 must replay the real quotes): on each run, "new" (phantom) fills <= 3% of real maker
fills, or that run is void (fix the rebuild, do not read variants).

In-sample (selection): 20261020T110544Z (stage 1, 100/300), 20261020T155754Z (stage 2), 20261021T143121Z
(c1a8080), 20261021T170240Z (42b5eef, 21-24 Oct). Candidates L in {1, 2, 3, 5, 8}.
Selection: L* = the candidate with the highest pooled in-sample end PnL (marked to market at each run's end).
If no candidate beats L = 0 on pooled in-sample end PnL, stop: the idea fails, no holdout test.

Holdout: 20261024T055444Z (e8256a7, current run), from its start to the last fill in its refreshed fills.json.
L* passes only if all three hold:
  1. holdout end PnL(L*) >= end PnL(L = 0);
  2. holdout max drawdown (60 s marks) of L* <= that of L = 0;
  3. pooled over all five runs, end PnL(L*) >= end PnL(L = 0).
Pass -> propose a default-off knob (MM_FIXED_LEAN_BPS), shadow it next to the live bot, demo QA, owner's
merge, then a live trial under the existing stop rule. Fail -> record it and drop the idea.
Other L values on the holdout may be printed but are not judged.
Sensitivity (reported, not judged): lag 2500 ms instead of 850 ms.
