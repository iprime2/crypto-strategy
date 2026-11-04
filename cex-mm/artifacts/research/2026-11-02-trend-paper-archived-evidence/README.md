# Evidence: trend paper books archived (2026-11-02)

Memo: `cex-mm/artifacts/research/2026-11-02-trend-paper-archived.md`. Paper books only: public Delta data, no keys, no orders. The VM's `cex-mm/artifacts/trend/` is gitignored, and its files were deleted on 2 Nov 2026 after these copies were md5-checked against them: this folder is the only record of the final state.

| Path | Contents |
|---|---|
| `daily_journal.jsonl`, `daily_state.json` | The daily book (TV 0.40, band 0, $1,000), 26 rebalances from 8 Oct to 2 Nov 2026 00:05 UTC, copied from the VM's `artifacts/trend/paper/` on 2 Nov after its timer was stopped. |
| `weekly_journal.jsonl`, `weekly_state.json` | The weekly book (TV 0.25, 10 % band, Monday 00:00 UTC, $1,000), 3 rebalances on 19 Oct, 26 Oct and 2 Nov 2026, copied from `artifacts/trend/paper-weekly/` the same way. |
| `daily_journal.jsonl.bak-20261009`, `daily_state.json.bak-20261009` | Backups of the daily book after its first two rebalances (8 Oct 16:37 and 9 Oct 00:05 UTC), taken on the VM on 9 Oct 01:46 UTC. |
| `daily_mark.txt`, `weekly_mark.txt` | The last live marks: `trend_paper.py --orders-only` at 14:03 UTC on 2 Nov 2026 (equity at Delta mids after funding, and the orders a rebalance would have sent). |
| `final_card.png` | The last Telegram update sent for both books (2 Nov 2026, 19:33 IST). |

Journal row fields are described in `cex-mm/artifacts/research/2026-10-26-trend-strategy-review-evidence/DATA.txt` (section B); daily rows from 28 Oct and the weekly 2 Nov row also carry the per-exchange funding fields added by `b8178d0`.
