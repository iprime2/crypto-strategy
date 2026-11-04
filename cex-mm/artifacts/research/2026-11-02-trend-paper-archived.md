# Quant memo: the trend paper books are archived; final record and how to reopen them
**Date:** 2026-11-02 · **Venue:** Delta Exchange India, public data, paper fills (no keys, no orders) · **Books:** daily (TV 0.40, band 0, $1,000, 8 Oct → 2 Nov 2026, 26 rebalances) and weekly (TV 0.25, 10 % band, Monday 00:00 UTC, $1,000, 19 Oct → 2 Nov 2026, 3 rebalances) · **Code on the VM:** `ca140f6` (includes the funding fixes `b8178d0`, `eb24c3b`, `da1e277`) · **Evidence:** `cex-mm/artifacts/research/2026-11-02-trend-paper-archived-evidence/` (the final journals and states, the last live marks, the last Telegram card; see its `README.md`)

## Decision
On 2 Nov 2026 the owner archived the trend strategy, judging that it is not performing as expected. Both paper books stopped after their 2 Nov 00:05 UTC rebalance. The same day, at the owner's request, the books' files were removed from the VM; the evidence folder holds byte-identical copies (md5-checked before deletion), since `cex-mm/artifacts/trend/` is gitignored and lived only on the VM.

Neither gate was reached. The daily book's four-week paper gate would have ended about 5 Nov, and the weekly book's Gate A about 16 Nov (`2026-10-26-trend-strategy-review.md`).

## Final record
Equity on the rebalance marks, from the journals in the evidence folder; the last live mark is the `--orders-only` first line taken at 14:03 UTC on 2 Nov, at Delta mids after funding [SYNTHETIC: arithmetic on the journals].

| | Daily book | Weekly book |
|---|---|---|
| Started | 8 Oct 16:37 UTC, $1,000 | 19 Oct 00:05 UTC, $1,000 |
| Rebalances | 26 | 3 |
| Equity at the last rebalance (2 Nov 00:05 UTC) | **$974.16, −2.58 %** | **$996.77, −0.32 %** |
| Last live mark (2 Nov 14:03 UTC) | $972.21, −2.78 % | $995.87, −0.41 % |
| Backtest model, same path | $978.40; paper − model −0.43 % | $995.32; paper − model +0.15 % |
| Buy-and-hold of the 9 coins, same window | −7.12 % (BTC −3.49 %) | −4.45 % (BTC −4.39 %) |
| Peak, worst drop on rebalance marks | $1,018.61, −4.40 % | $1,000.00, −0.32 % |
| Orders, $ traded | 65, $2,426 | 14, $173 |
| Fees, net funding paid | $1.29, $0.55 | $0.09, $0.20 |
| Costs per $ traded (backtest 7.31 bps, gate 14.62) | 6.16 bps | 6.73 bps |
| Average invested, final holdings (contracts) | 22 %; LTC 4, BCH 16, LINK 2, BTC 1 (17 %) | 6 %; LTC 3, BCH 10, LINK 1 (6 %) |

## What the run showed, and what it could not
- **Plumbing and costs passed.** The paper books tracked the backtest model within half a percent, costs ran below the backtest's assumption, and no daily rebalance was missed (26 in 26 days).
- **The loss came from one day.** The 29→30 Oct rebalance lost 2.37 % at the run's highest exposure (35 % invested, BNB the largest line, the basket down 3.9–10.1 % per coin). The rule then cut exposure to 14 % at the next signal.
- **The rule lost less than holding the coins.** That is its designed shape (resource/07: half the drawdown of holding the same coins vol-scaled), not evidence of edge.
- **Edge was never measurable here.** At the forward Sharpe of 0.3–0.8 that resource/07 expects, rejecting a Sharpe of zero takes about 30, 11 and 4 years of results respectively (`2026-10-26-trend-strategy-review.md`, Time to know). Three and a half weeks say nothing either way.
- **The money case was already weak.** The 26 Oct review found the rule worth pocket money below about $100k of capital, after tax under the unfavourable reading, and 26 pre-registered improvements failed (`resource/08`). Archiving loses the plumbing evidence a few more weeks would have added, and nothing on the return side.

## What was stopped and what was kept
- **Stopped, then removed:** the VM's user timers `cex-mm-trend-paper.timer` and `cex-mm-trend-paper-weekly.timer` (each fired hourly at minute 05 and rebalanced once a day, or on Mondays), stopped on 2 Nov 14:38 UTC. At about 16:33 UTC their installed unit files, their timer stamps (and the stamp of an old one-off `trend-weekly-enable.timer`) and the state folders `artifacts/trend/paper/` and `paper-weekly/` were deleted. The templates stay in `cex-mm/infra/systemd/`, and `cex-mm/infra/vm/setup.sh` now installs them without enabling them.
- **Stopped:** the twice-daily Telegram updates of both books (two scheduled tasks on the owner's Claude account, disabled, not deleted).
- **Left in place:** the units' lines in the VM's user journal (about 2,900 lines in a 33 MB journal shared with the shadow test; journald cannot drop one unit's lines, so they age out with the rest), and the `/trend` page of `shadow_server.py`, which now answers that there is no paper state.
- **Kept in the repo:** `cex-mm/scripts/trend_paper.py`, `trend_backtest.py`, the unit templates and the dated memos, unchanged; `resource/07` and `resource/08` gain only an archive note at the top; the final journals and states are in the evidence folder.
- **Not touched:** the shadow test, the live ADA market maker, the OEMS.

## How to reopen
Install the two units from their templates and enable them; with no state folder, `trend_paper.py` starts new $1,000 books at the next run (`trend_paper.py::init_state`):

```bash
cd ~/crypto-strategy/cex-mm
for u in infra/systemd/cex-mm-trend-paper*.service infra/systemd/cex-mm-trend-paper*.timer; do
  sed "s|@CEX_MM@|$PWD|g" "$u" > ~/.config/systemd/user/$(basename "$u")
done
systemctl --user daemon-reload
systemctl --user enable --now cex-mm-trend-paper.timer cex-mm-trend-paper-weekly.timer
```

To resume the archived books instead, copy the evidence folder's `daily_*` files to `artifacts/trend/paper/` and its `weekly_*` files to `artifacts/trend/paper-weekly/` as `journal.jsonl` and `state.json` first. The first run then marks the positions at that day's prices, so the gap counts as if the coins were held throughout.

Reopen only with a reason the 26 Oct review did not already price in, for example capital near $100k, a written CA opinion on the tax reading, or a different engine that needs this rule as a sleeve. Re-running the same rule at $1,000 would answer nothing that this run left open.
