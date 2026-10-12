# Quant memo: Delta Scalper Offer on DISM ADA
**Date:** 2026-10-09 · **Venue:** Delta India mainnet (offer terms; public data from the shadow test, no orders) · **Strategy:** Delta Inside-Spread Maker (DISM), ADA, fair ±5 bps
**Tool:** `scripts/shadow_fill_sim.py --scalper-window-min N [--scalper-match fifo|flat]`, tests in `scripts/test_shadow_fill_sim.py`.
**Data (added 2026-10-12):** shadow run `20261006T161427Z` on the Tokyo VM (dry-run on commit `9c52120` with `config/dism.env`, ADA/KITE/BERA/DUSK), 133.2 h of quotes from 2026-10-06 16:14Z to 2026-10-12 05:25Z, 22,224 ADAUSD trades ($9.8M). Strict fills, $50 quotes, inventory cap 3 quotes, maker fee 2.12 bps.

## Question
Delta waives the fee on the closing leg of short-held futures trades. Does that lift DISM ADA net60 (spread captured + 60 s markout − fee, bps per fill), and by how much?

## Offer terms
Read from Delta's help article via web search on 9 Oct. The page itself could not be opened from the analysis sandbox, so re-read it before opting in.

| Term | What Delta says | Source |
|---|---|---|
| Benefit | Zero fee on the **closing** leg of a Futures trade opened and closed within the window. Covers fully and partially closed trades. | [Delta help: Scalper Offer](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer) |
| Window | BTCUSD 30 min (a later version lists BTCUSD and ETHUSD at 30 min); other futures 15 min, so **ADAUSD = 15 min**. An earlier BTC/ETH version said 15 min. | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer), [Delta on X](https://x.com/Delta_Exchange/status/1863930029694140429), [Diwali BTC add-on](https://x.com/Delta_Exchange/status/2105637508222775303) |
| Opening leg | Pays the normal fee (maker 2.12 bps incl. GST for our quotes). | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer) |
| Eligibility | KYC users who click "Join Now" on the Futures-page pop-up. Trades before consent do not count. | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer) |
| Excluded | Internal, corporate, **RMM or MM users**; liquidated trades; options. | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer) |
| Opt-out | **Once activated, it cannot be deactivated.** | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer) |
| Duration | Delta may modify or end it without notice. No end date found. | [Delta help](https://www.delta.exchange/support/solutions/articles/80001172745-scalper-offer), [Traders Union](https://tradersunion.com/news/brokers-news/show/3604709-delta-exchange-unveils-scalper-offer/) |

Not stated anywhere we could read:
- How closes are paired with opens: first-in-first-out lots, or the whole position. [UNVERIFIED] Modelled both ways (below).
- Whether **maker** closing fills count. The wording does not distinguish maker from taker; assumed yes. [UNVERIFIED]
- Whether perpetuals count as "Futures". Inferred yes: the BTCUSD named in the offer is Delta India's BTC perpetual. [UNVERIFIED, inferred]
- Whether a retail API account that quotes post-only is an "MM user". [UNVERIFIED] This decides whether the offer applies to us at all.

## Model
Fills, markouts and the normal fee are unchanged; the script adds a second fee per fill.
- A fill first closes up to |inventory| (the closing part), and the rest opens or adds (including the overshoot when a fill flips the position through zero). Opening parts always pay the maker fee.
- **fifo** (default): every opening part becomes a lot with its own fill time. Closing contracts are matched oldest lot first; contracts from lots aged ≤ window pay 0, the rest pay the maker fee.
- **flat** (conservative bound): closing contracts are free only if the position episode (since inventory last left zero) is ≤ window old. Never more generous than fifo.
- Ages use local receive time of the fill; only differences matter, so the ~1 s clock offset to Delta does not.
- Report: columns after `|` show `ofee onet60 onet300 oPnL$ free%` for the same fills under the offer; `free%` = share of fill notional that was a free closing leg. The verdict ignores the offer.

## Results
| ADA, fair ±5 bps, 6 Oct run | net60 | net60 with offer (fifo) | net60 with offer (flat) | free% (fifo / flat) |
|---|---|---|---|---|
| 20 ms latency | **+2.48** (9,403 fills) | **+3.43** (+0.95) | **+3.13** (+0.65) | 45% / 31% |
| 300 ms latency (the 5 Oct memo's setting) | **+2.26** (9,392 fills) | **+3.20** (+0.94) | **+2.90** (+0.64) | 44% / 30% |

Commands: `--latency-ms 20|300 --sweep 5`, each without the offer and with `--scalper-window-min 15` under `--scalper-match fifo` and `flat`. The columns before `|` are identical with and without the offer. Fill counts include 67 (20 ms) and 68 (300 ms) fills at the end of the run with no 300 s markout yet; net60 uses the scored fills only.

| Same fills, simulated PnL over 133.2 h | Without offer | With offer (fifo) | With offer (flat) |
|---|---|---|---|
| 20 ms | +$65.02 (spread +$113.32, inventory +$1.58, fees −$49.89) | +$87.33 | +$80.31 |
| 300 ms | +$58.96 (spread +$114.76, inventory −$5.96, fees −$49.84) | +$81.14 | +$73.98 |

What the run shows:
- **The offer adds +0.95 bps per fill under fifo and +0.65 bps under flat**, inside the ~1.06 bps bound below. At 20 ms that is +$22.31 (fifo) or +$15.29 (flat) over 5.55 days, about $4.00 or $2.75 a day at $50 quotes.
- **fifo and flat differ by 0.30 bps**, about a third of the uplift. Still small next to net60 itself, but enough to be worth asking Delta which rule it uses (see Decision).
- **The gate does not depend on the offer.** Without it, ADA ±5 bps is positive on every full UTC day at both latencies (20 ms: +2.21, +2.11, +2.64, +2.81, +2.79 for 7–11 Oct; 300 ms: +1.90, +1.83, +2.45, +2.57, +2.55). The 7.8 h on 6 Oct read +0.09 (20 ms) and +0.52 (300 ms) over about 235 fills, below the 300-fill minimum. It also holds at 1000 ms (+1.79, 9,456 fills) and under `--rule touch` at 300 ms (+2.30, 10,024 fills).
- The `bot quotes` row equals the `fair +/- 5bps` row exactly at both latencies, so the dry-run is quoting the live rule.

**Bound, not a measurement.** Closing contracts can never exceed opening contracts, so at most about half of fill contracts are free closing legs. (The `free%` column is a notional share averaged over scored fills only, so it can come out slightly above 50%.) The fee saving is at most about 0.5 × 2.12 = **1.06 bps per fill**, and then only if every close lands inside 15 minutes. So at the same latency and quote settings: **net60 with the offer ≤ net60 without + ~1.06 bps.** Compare each row with its own net60, not with the numbers below.
- 5 Oct memo (`2026-10-05-dism-gate-six-coins.md`): ADA fair ±5 bps net60 +1.90 bps over 4,117 fills, fill-weighted over five runs, at **300 ms** latency and $50 quotes. With the offer: at most about **+2.96 bps** at 300 ms.
- 6 Oct run: the user's status of 9 Oct read net60 +1.90 bps over 2,444 ADA fills after 46.5 h, latency not stated. Measured above at 133.2 h: +2.26 at 300 ms and +2.48 at 20 ms. The first two full days at 300 ms read +1.90 and +1.83, so the 9 Oct figure was probably at 300 ms.
- In dollars, the 32 h run in the 5 Oct memo (300 ms) made +$5.40 after −$16.20 of fees. With the offer, that run is bounded at +$13.50 (half the fees back).

## Decision (for the user)
1. **Opt in or not.** The upside is at most ~1 bps per fill; measured +0.65 to +0.95 bps on ADA, about $3–4 a day at $50 quotes. The risks:
   - The terms exclude "MM users", and our account runs a market-making bot.
   - Activation is irreversible.
   - Delta can end the offer at any time.
   Recommendation: ask Delta support in writing (ticket or email) whether a retail KYC account trading over the API with post-only quotes counts as an "MM user", and whether activation changes anything else on the account (fee tier, other offers). Opt in only on a written yes.
2. **The gate stays without the offer.** Mainnet go/no-go and the live stop rule (net60 < 0 after 300 fills; superseded 2026-10-12 by PnL per dollar traded, see `2026-10-12-live-stop-rule.md`) use numbers without the offer, because the offer can be withdrawn without notice. The offer is upside, not a reason to pass `docs/MAINNET_GATE.md`.

## Next
1. Send the support ticket (Decision 1): ask whether we count as an "MM user", and whether closes pair with opens first-in-first-out or by position age. The two rules are 0.30 bps apart.
2. The measurement below was done on 2026-10-12 (Results above). To repeat it on a later run, read-only and with no orders, follow these steps. Copying the 209 MB gzip off the VM took about 15 min over the tailnet. On the Tokyo VM, from `cex-mm/`, first check with `scripts/shadow.sh status` that `current` is the run you want:
```bash
mkdir -p /tmp/scalper
grep -F MM_METRICS artifacts/shadow/current/dry-run.log | gzip -1 > /tmp/scalper/dry-run.log.gz
cp artifacts/shadow/current/delta_mainnet_public_*.jsonl /tmp/scalper/
```
Copy `/tmp/scalper/` off the VM, then from `cex-mm/`:
```bash
python3 scripts/shadow_fill_sim.py --run-dir <dir> --latency-ms 20 --sweep 5 --scalper-window-min 15
python3 scripts/shadow_fill_sim.py --run-dir <dir> --latency-ms 20 --sweep 5 --scalper-window-min 15 --scalper-match flat
# the 5 Oct memo's latency, to compare with its +1.90:
python3 scripts/shadow_fill_sim.py --run-dir <dir> --latency-ms 300 --sweep 5 --scalper-window-min 15
python3 scripts/shadow_fill_sim.py --run-dir <dir> --latency-ms 300 --sweep 5 --scalper-window-min 15 --scalper-match flat
```
- The `fair +/- 5bps` row always uses `--latency-ms`; `--latencies` adds rows only for the bot's own quotes. So the 300 ms row needs its own run.
- Keep the file names. The loader globs `dry-run*.log*` (gzip is fine) and `delta_mainnet_public_*.jsonl`, which must stay uncompressed. It needs `api.india.delta.exchange` for tick size and contract value.
- Alternative on the VM itself: `scripts/shadow.sh report --latency-ms 20 --sweep 5 --scalper-window-min 15`.
- Fill each Results row from the ADAUSDT `fair +/- 5bps` row of the matching run (`net60`, `onet60`, `free%`). If fifo and flat differ materially, the pairing rule matters, so ask Delta which one it uses in the same support ticket.
