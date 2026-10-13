# Quant memo: the first real-money DISM run was picked off
**Date:** 2026-10-13 · **Venue:** Delta India mainnet, real money (`scripts/live.sh`) · **Symbols:** ADAUSD, fair ±5 bps, 200-contract quotes, cap 600 · **Data:** live run `20261013T031435Z` (03:14:35Z to the stop at 05:51:51Z), 172 Delta fills to 05:33Z; shadow run `20261012T173401Z` (dry-run on the same binary, 5233708e) · **Tools:** `scripts/live.sh report` (`live_vs_shadow.py`); per-fill attribution and the counterfactual below were one-off scripts on copies of the logs

## Question
The simulator predicted net60 of about +4.7 bps per fill on ADA. What did the real bot earn, where did the money go, and why did the simulator miss it?

## Outcome
- 172 fills by 05:33Z, all maker, $3,975 traded. Fill rate 1,785 a day, the same as the simulator's 1,660–1,806 on the 2.3 h before the start.
- PnL by 05:33Z: **−$1.77, −4.46 bps per dollar traded** (cash flows plus inventory at the bot's last mid, minus fees). The stop rule still read CONTINUE (172 of 300 fills).
- The operator stopped the bot at 05:51:51Z on the attribution below, before the 300-fill check, and closed the remaining 316 ADA short with one reduce-only market buy at 0.2398 ($0.040 fee). Equity went from $293.989 to **$292.162 (−$1.83)** including the close. The account is flat with no open orders.

## PnL attribution
Measured against the Binance spot mid, which our orders cannot move. Capture uses no basis assumption: buys filled 5.01 bps below Binance and sells 4.90 bps below it, so the Delta–Binance basis on these fills was −4.95 bps and capture is the average of the two sides.

| bps per fill (notional-weighted) | Real | Simulator, 2.3 h before the start (20 / 300 ms) |
|---|---|---|
| Capture at the fill | **+0.05** | +4.51 / +4.24 |
| 60 s markout | −1.64 | +2.29 / +2.74 |
| Maker fee | −2.12 | −2.12 |
| net60 | **−3.6** | +4.7 / +4.9 |

- Unweighted per fill, with 95% intervals: capture +1.22 ± 0.69, 60 s markout −0.25 ± 1.95, net60 −1.17 ± 2.24. Capture is far below the simulator's ~4.5 either way; that gap is not noise.
- In dollars, against the bot's own fair: spread +$1.31, inventory −$2.24, fees −$0.84. The bot was short 90% of the time (time-average −324 ADA) while ADA rose 1.46%. The spread it booked against its own fair was mostly an illusion, because that fair lagged the market (below).

## Findings, ranked by money at stake

1. **The bot gets filled when its quotes are stale.**
   - The 2 s before a fill, Binance moved 1.97 bps toward our price on average. 27% of fills came after a move of more than 2 bps in those 2 s.
   - At the fill, the bot's own fair sat 2.11 ± 0.88 bps on the wrong side of the Binance-implied price.
   - Fills that took a whole 200-ADA order (47 fills, 56% of volume) had capture −1.20, a −2.23 pre-fill move and a −2.77 60 s markout. Partial fills (125) had +2.13, −0.77 and +0.71. Takers who clear the whole quote are the informed ones.

2. **The fair lags the external price whether or not our orders are in the book.**
   - The fair is the Delta L1 mid blended 30% toward the microprice, plus 0.8 × the Binance move over the last 3 s (clamped at 15 bps). Once a move is older than 3 s the lead term drops out, and the fair falls back to the Delta book, which trails Binance.
   - Gap between the fair and Binance × (1 + basis):

     | | Median | p90 |
     |---|---|---|
     | Shadow before the start (no real orders) | 2.97 bps | 7.48 bps |
     | Live | 2.07 bps | 6.05 bps |

   - In both, a resting quote sat within 1 bp of that price, or through it, about 15% of the time.
   - Correction to the first read of this run: the lag is **not** mainly the bot reading its own quotes off the book. It is the same without them.

3. **Why the shadow test could not see it.**
   - The simulator fills a quote only when a recorded trade prints through its price. Hypothetical quotes are never hit by takers reacting to them.
   - So a stale quote costs nothing in the shadow, while live, faster traders hit it as soon as the price reaches it.
   - The shadow measures the fill rate correctly (1.0x) but not who fills us. Any quoting change must also be judged on how often its resting quotes are exposed, not on simulated net60 alone.

4. **The 600-contract cap overshoots** (operational, not PnL).
   - Venue inventory reached −811.
   - The bot quotes a full 200 contracts whenever |q| < 600, so it can overshoot to 799.
   - Many fills reach the bot only through the venue reconcile (15–30 s later, corrections of up to 200 contracts).
   - At |q| ≥ 600 it never quoted the adding side (0 of 2,505 samples), so the gate itself works.

5. **Rejects:** 13 of 3,247 placements and edits, all `immediate_execution_post_only`. That is the post-only guard working, not a fault.

## Counterfactual: anchor the fair to the Binance level
- Setup: on the shadow before the start (00:00–03:14Z, 11,187 samples, no real orders), the fair is replaced by Binance mid × (1 + basis).
  - The basis is a causal EMA of the Delta book mid over Binance.
  - Quotes are fair ±5 bps, resting until the new quote is more than 3 bps away.
- Scoring reference: Binance × (1 + a centred 20-minute rolling median of the same basis).
  - That is an estimate of the true basis, and it looks ahead, so these are estimates.

| Fair | Gap to the true price, median / p90 (bps) | Resting quote within 1 bp of it (bid / ask) | Order moves per hour |
|---|---|---|---|
| Current (Delta book + 3 s Binance lead) | 3.11 / 7.56 | 16.4% / 20.8% | 6,433 |
| Binance-anchored, basis EMA 60 s | 1.38 / 2.80 | 1.2% / 0.8% | 2,991 |
| Binance-anchored, basis EMA 120 s | 1.42 / 2.62 | 0.7% / 0.0% | 2,991 |
| Binance-anchored, basis EMA 300 s | 1.26 / 2.83 | 4.3% / 0.0% | 2,991 |
| Binance-anchored, basis EMA 600 s | 1.48 / 4.41 | 14.9% / 0.0% | 2,991 |

- A requote tolerance of 1 bps instead of 3 leaves the current fair at 17% exposed. The tolerance is not the problem.
- Basis averages slower than a few minutes leave one side exposed: the basis moved several bps within hours (−10.9 bps before the start, about −5 during the run).

## Also found
- **The Binance feed task could die silently.**
  - In `mm-binance`, a websocket read error was returned with `?`, which ended the task. The bot then kept the last Binance price for good.
  - That fits the 8–12 Oct freeze [UNVERIFIED: the task logged nothing when it ended].
  - Fixed with the draft below: reconnect on errors, on end of stream, and after 30 s of silence. Each message is counted, so a silent feed is visible.
- **How the fair-jump defence interacts with the anchor.** It compares the fair with the current Delta mid (12 bps). With the anchor on, it fires only when Delta's book trails the anchor by 12 bps or more, and then drops the side that book would cross. Fixed quotes are clamped inside the Delta book in any case. The shadow test counts the one-sided time.

## Next experiment (shadow only, no real money)
- **One knob:** `MM_FAIR_ANCHOR_WEIGHT` 0 → 1 (fair = Binance mid × (1 + basis EMA)), with the basis EMA half-life at 120 s *(start)*. The Binance 3 s lead is scaled by (1 − weight), so it is not counted twice. The bot falls back to the Delta-book fair while the Binance feed is silent for more than 5 s or the basis is not yet warm.
- **Metrics, from the shadow over at least 24 h:**
  - the gap between the fair and Binance × rolling-median basis (median and p90);
  - the share of time a resting quote is within 1 bp of that price;
  - simulator bnet60 and fills a day over at least 300 fills, at 300 ms and under `--rule touch`.
- **Success:**
  - p90 gap below 3 bps;
  - exposure below 3% on both sides;
  - one-sided below 5% of the time;
  - bnet60 at least +2 bps;
  - fills a day within 30% of the current shadow.
- **How:**
  1. Merge the draft. On the VM, `git pull`, then `systemctl --user restart cex-mm-shadow`. The restart rebuilds, starts a new run on `config/dism.env` with the anchor on, and needs the user's go-ahead.
  2. After 24 h, run `python3 scripts/fair_exposure.py --run-dir artifacts/shadow/current --hours 24`. It scores the logged (anchored) fair and `fair_delta` (the old fair on the same data) side by side.
  3. Run `scripts/shadow.sh report --latency-ms 300` and the same with `--rule touch` for the simulated fills.
- **Stop:** any of those missed after 24 h. Then try the basis half-life at 60 s, not a wider spread.
- **Before any live run with the anchor:**
  - **Basis source.** In live, the Delta book mid is mostly our own quotes, so a basis EMA fed from it stops learning. The draft fix only updates the basis while neither touch is our resting order, and falls back to the Delta fair once the basis is older than 300 s *(start)*. That fallback may switch the anchor off most of the time in live. Delta's index or mark price is the candidate replacement [UNVERIFIED: not yet checked whether it leads Delta's book].
  - **The cap overshoot.** Clip the adding quote to cap − |q|, and count fills when they happen rather than only at the reconcile.
  - **Size.** The next live run starts smaller than 200 contracts.
