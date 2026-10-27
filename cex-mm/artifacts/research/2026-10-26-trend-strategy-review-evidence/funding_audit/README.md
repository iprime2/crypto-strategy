# Funding audit of the trend paper trader (26 Oct 2026)

Why `trend_paper.py` journaled $0.3533 of funding for the daily book over 18 intervals (8 to 26 Oct) when the review's recompute from published candles gave $0.5632, what the book actually owed, and the fix. Public data and read-only copies only. Nothing on the VM was started, stopped, restarted or changed.

## Findings

1. **Cause: the candles endpoint truncates a FUNDING series at its first 8-hour stamp.** `/v2/history/candles?resolution=1h&symbol=FUNDING:<sym>` returns hourly candles only from the first 00:00, 08:00 or 16:00 UTC stamp at or after `start`. A start of 00:00:01 or 07:59:59 both give a first candle at 08:00 (`endpoint_probe.txt`). A price series starts at the next hour as usual. The trader asked from its last rebalance at 00:05, received 08:00 to 00:00 (17 candles), and summed them / 8. It charged the 08:00 and 16:00 exchanges in full and 1/8 of the 00:00 one.
2. **That rule reproduces the journal exactly.** It gives all 18 daily and the 1 weekly funding values from candles fetched on 26 Oct 18:35 UTC, with zero relative difference at float precision (`exact_match.txt`). So the trader read the same values that are published now. The provisional-candle hypothesis is refuted for all 19 fetches. The VM's deployed `fetch_funding`, called again on the 18 windows, returns the journal's numbers too (`vm_fetch_funding_3passes.json`).
3. **What Delta charges.** At each 8-hour exchange Delta charges position × mark × the rate on the candle stamped at that exchange. All 13 funding entries of the live ADAUSD market maker on 22–26 Oct match this, 12 within 0.1 % and one within 0.9 %. The candle just before the stamp misses by 2–194 % (`venue_rule_check.txt`, `venue_funding_ada.json`). The bot logged its inventory and mark under a second before each exchange.
4. **Owed versus journaled** (`audit_vm_journals.txt`). The table covers the daily book's 18 intervals and the weekly book's one interval.

   | Book | Journal | Old trader rule | All hours / 8 (review) | Delta's rule (owed) |
   |---|---|---|---|---|
   | Daily, 18 intervals | 0.3533 | 0.3533 | 0.5632 | **0.4447** |
   | Weekly, 1 interval | 0.0899 | 0.0899 | 0.0936 | **0.0933** |

   - The daily journal minus the amount owed ranges from −$0.026 to +$0.048 per interval. It is beyond $0.01 on 6 of 18 intervals.
   - The review's hourly recompute covers 01:00 to 00:00. That puts it one 8-hour block off from the exchanges a 00:05-to-00:05 holding goes through.
5. **A latent defect: empty answers.** These requests sometimes return `{"success": true, "result": []}`.
   - The rate was 9.3 % and 4.6 % of 108 requests from the sandbox, and 40 of 486 coin-windows (8.2 %) through the VM's `fetch_funding`, all on 26 Oct.
   - The old code booked such a coin's funding as zero. That never happened in the 19 journal rows, because the exact match needs no empty answer.
   - One immediate retry recovered 14 of the 15 empty answers seen in the sandbox.

## The fix (`cex-mm/scripts/trend_paper.py`, tests in `test_trend_paper.py`)

- One rate per exchange in (last rebalance, now], read from the candle stamped at that exchange.
- The request starts at last rebalance + 1 s, and pages are keyed by candle time, so nothing is dropped or counted twice.
- A coin missing a stamp is asked again, up to 5 times. If a rate is still missing, the run fails and the hourly timer retries. The old code booked zero instead.
- Every journal row records `funding_window` ([since, until], unix s), `funding_exchanges` (unix s) and `funding_rates` (coin → % per 8 h, one per exchange).
- The fixed code's first rows ran on scratch copies of both books' state on 26 Oct at 19:05 UTC (`fixed_*_rows_2026-10-26T1905Z.json`). Both match an independent recompute from published candles to $0.00 (`audit_fixed_rows.txt`).
- The VM still runs the old code. Deploying the fix needs the owner's go-ahead.

## Boundary check across the 00:00 UTC exchange, 27 Oct (`boundary/`)

The forward test of the provisional-value hypothesis, and the first old-code and fixed-code rows side by side.

- **Method.** `snapshot_loop.py` fetched the nine coins' FUNDING candles and the tickers' `funding_rate` once a minute from 26 Oct 23:52 to 27 Oct 00:20 UTC. It ran here and, piped over ssh, on the VM, printing to stdout only, so nothing was written or started there. `analyze.py` reads the snapshots.
- **No candle is provisional.** No candle changed value after it first appeared, in either series. The 00:00 candle appeared in the first snapshot after the exchange, 36 s after it here and 37 s on the VM, already at its final value. The hypothesis is refuted going forward as well as for the 19 past fetches.
- **The ticker is not the settled rate.** The tickers' `funding_rate` just before 00:00 is a running estimate. For DOGE it was 0.021331 % against the settled 0.021416 %, so it cannot replace the candle.
- **The VM's 00:05:29 row, old code** (`vm_daily_rows_2026-10-27T0005Z.json`). It booked $0.041004601854, equal to the old rule to every digit (`check_rows.txt`). Delta's rule gives $0.059051, so this one interval is $0.018 short. The weekly book was not due.
- **The fixed code, from the same starting state.** It ran on a scratch copy of the 26 Oct 00:05 state, as the VM's run did, and booked $0.059055 (`fixed_daily_rows_2026-10-27T0005Z.json`). Its logged rates equal the published candles of the three exchanges it held through, and the total equals Delta's rule exactly. A scratch weekly book, set due by hand on the copy only, gives the same result. `funding_audit.py` passes both on a fresh fetch (`audit_rows_2026-10-27.txt`).
- **Still open.** The 24 h re-fetch at 00:06 UTC on 28 Oct will be diffed against the last snapshot with `analyze.py --refetch`.

## Files

| File | What |
|---|---|
| `funding_audit.py` | Independent audit of any journal (does not import the trader). Recomputes each row under the three rules. A row that logs rates must log the published ones and match Delta's rule within `--tol` (default $0.01). `python3 funding_audit.py JOURNAL... [--candles DUMP]` |
| `exact_match.py` → `exact_match.txt` | The old rule against all 19 journal values, offline |
| `venue_rule.py` → `venue_rule_check.txt` | Which candle Delta's ledger charges, offline |
| `probe_endpoint.py` → `endpoint_probe.txt` | The endpoint's start and end rules, and the empty-answer rate, online |
| `vm_fetch_runner.py` → `vm_fetch_funding_3passes.json` | The VM's deployed `fetch_funding` on the 18 windows, three passes (stdout only) |
| `candles_2026-10-26T1835Z.json` | FUNDING closes for the nine coins, 7 Oct 00:00 to 26 Oct 18:00 UTC, plus contract values |
| `vm_daily_journal_2026-10-26.json`, `vm_weekly_journal_2026-10-26.json` | The two journals as on the VM on 26 Oct 18:50 UTC (JSON arrays; `*.jsonl` is gitignored here) |
| `venue_funding_ada.json` | The ADAUSD wallet ledger's funding entries (time and amount only) with the bot's last logged inventory and mark before each exchange |
| `fixed_*_rows_2026-10-26T1905Z.json`, `audit_fixed_rows.txt`, `audit_vm_journals.txt` | The fixed code's first rows and the audits |

Run everything from this folder. The offline scripts need only the files here.
