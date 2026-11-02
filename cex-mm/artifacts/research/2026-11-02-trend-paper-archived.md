# Quant memo: the trend paper books are archived; final record and how to reopen them
**Date:** 2026-11-02 · **Venue:** Delta Exchange India, public data, paper fills (no keys, no orders) · **Books:** daily (TV 0.40, band 0, $1,000, 8 Oct → 2 Nov 2026, 26 rebalances) and weekly (TV 0.25, 10 % band, Monday 00:00 UTC, $1,000, 19 Oct → 2 Nov 2026, 3 rebalances) · **Code on the VM:** `ca140f6` (includes the funding fixes `b8178d0`, `eb24c3b`, `da1e277`) · **Evidence:** `cex-mm/artifacts/research/2026-11-02-trend-paper-archived-evidence/` (the final journals and states, the last live marks, the last Telegram card; see its `README.md`)

## Decision
On 2 Nov 2026 the owner archived the trend strategy, judging that it is not performing as expected. Both paper books stopped after their 2 Nov 00:05 UTC rebalance. Nothing was deleted: the state and journals stay on the VM, and a copy is in the evidence folder because `cex-mm/artifacts/trend/` is gitignored and lives only on the VM.

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
- **Stopped:** the VM's user timers `cex-mm-trend-paper.timer` and `cex-mm-trend-paper-weekly.timer`, both stopped and disabled on 2 Nov 14:38 UTC. Each fired hourly at minute 05 and rebalanced once a day (daily book) or on Mondays (weekly book).
- **Stopped:** the twice-daily Telegram updates of both books (two scheduled tasks on the owner's Claude account, disabled, not deleted).
- **Kept on the VM:** `~/crypto-strategy/cex-mm/artifacts/trend/paper/` and `.../paper-weekly/` (state and journals, frozen at the 2 Nov rebalance), the unit files in `~/.config/systemd/user/`, and the `/trend` page of `shadow_server.py`, which keeps showing the frozen books.
- **Kept in the repo:** `cex-mm/scripts/trend_paper.py`, `trend_backtest.py` and the research in `resource/07`, `resource/08` and the dated memos, all unchanged.
- **Not touched:** the shadow test, the live ADA market maker, the OEMS.

## How to reopen
To run a fresh trial, move the frozen state aside first, so the archived record stays as it is and `trend_paper.py` starts new $1,000 books (an empty state folder starts a new book, `trend_paper.py::init_state`):

```bash
cd ~/crypto-strategy/cex-mm/artifacts/trend
mkdir -p archive-2026-11-02 && mv paper paper-weekly archive-2026-11-02/
systemctl --user enable --now cex-mm-trend-paper.timer cex-mm-trend-paper-weekly.timer
```

Re-enabling the timers without moving the folders resumes the frozen books instead: the first run marks the positions at that day's prices, so the gap counts as if the coins were held throughout.

Reopen only with a reason the 26 Oct review did not already price in, for example capital near $100k, a written CA opinion on the tax reading, or a different engine that needs this rule as a sleeve. Re-running the same rule at $1,000 would answer nothing that this run left open.
