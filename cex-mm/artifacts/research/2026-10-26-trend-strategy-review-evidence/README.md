# Evidence: trend strategy review (2026-10-26)

Memo: `cex-mm/artifacts/research/2026-10-26-trend-strategy-review.md`. Public data and paper journals only; no script places an order or reads a key. Every script was run in the session sandbox on copies of the VM's journals; the VM was read, never changed.

| Path | Contents |
|---|---|
| `DATA.txt` | The data inventory handed to every analyst: what each file holds, where it came from, the hard rules. |
| `daily_journal.jsonl`, `daily_state.json`, `weekly_journal.jsonl`, `daily_mark.txt`, `weekly_mark.txt` | The two paper books as copied from the VM on 26 Oct 2026 at 13:46 UTC (19 daily and 2 weekly rebalances, live marks). |
| `fidelity/` | Fidelity pass: `fidelity1.py` (journal identities, per-coin P&L, costs), `fidelity2.py` (weights recomputed from Delta closes, independent close-to-close backtest, tracking-error decomposition, re-rounding at other capitals, ex-ante vol), `fidelity3.py` (run times, candle-revision check, basket moves), `fetch_delta.py`, the outputs (`*_out.json`, `summary.json`) and the chart (`trend_fidelity_chart.png`, built by `chart_data.py` + `make_chart.py`). |
| `money/` | Money pass: `mc.py` (10,000-path Student-t(4) Monte Carlo at Sharpe 0.3 / 0.5 / 0.8, 12 % and 19 % vol, four capitals, three tax readings), `mc_outcomes.txt` and `mc_summary.json` (the tables), `compare.py` → `compare_realmoney_timetoknow.txt` (comparators, capital for ≥ $500/month, time to know), `verify_facts.py` → `facts_check.txt`. |
| `skeptic/` | Adversarial recomputation with separate code: `skeptic_journal.py`, `skeptic_signal.py` (own implementation of the rule and its own backtest), `skeptic_stats.py` (20,000-path MC, slab tax with carry-forward, per-segment fit, owner time, FD increment), `mm_ledger.py`; outputs `*_recompute.json`, `mm_ledger.txt`, and `skeptic_summary.txt` (what held, what was weakened, what was refuted, what both analysts missed). |
| `comparator/` | The live ADA market maker over the same week: `markout_since20.txt` (the quant-researcher skill's markout report on 6,281 venue fills), `mm_ledger.txt`, `mm_analyses_structured.json` (the attribution and capacity analyses), `market_scan.txt` (every Delta perp by spread, tick, turnover) and `shadow_report.txt` (the ADA + AVAX shadow sweep, partial). |
| `workflow_results.json` | The structured returns of the three trend agents (fidelity, money, skeptic) as the workflow recorded them. |

Not included: the Binance 1 s kline cache and the raw venue fill export (public and re-fetchable; `DATA.txt` says how), the 1.1 MB Delta candle dump the fidelity scripts fetched (re-fetched by `fetch_delta.py`), and the skeptic's `delta_raw/` dump. The scripts use absolute paths under the session scratchpad, which is not kept; edit them before re-running.
