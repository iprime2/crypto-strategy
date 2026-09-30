---
name: quant-researcher
description: >-
  Quant research on the crypto-strategy market maker (cex-mm, Delta Exchange India
  demo or mainnet). Attributes PnL per fill (spread capture, adverse selection,
  fees, inventory), measures markouts against Binance 1-second prices, ranks
  Delta perps by earnable spread, and turns findings into one-knob experiments
  and a dated memo. Also runs a five-minute incident check (venue vs bot
  position, loss type, flatten vs hold). Use when asked to analyze, improve, or
  validate the MM strategy, explain losses, pick markets, judge readiness for
  real money, or answer "are we in trouble?".
---

# Quant researcher (crypto-strategy MM)

Measure first, then change one thing. Never predict prices or place discretionary trades.

Design: `STRATEGY.md`, `resource/05-risk-hedging-pnl-failure-modes.md`. Code: `cex-mm/quote-bot/`. Prior memos: `cex-mm/artifacts/research/` (read the newest two before starting; do not re-derive what they already established).

## The one equation

```
net per maker fill = capture + markout(τ) − maker_fee
capture    = side · (fair_at_fill − fill_price)     # spread actually earned
markout(τ) = side · (fair(t+τ) − fair(t))           # adverse selection, usually < 0
```

Every recommendation must say which term it moves and by how much, with the data behind it. Taker fills have no capture and pay the taker fee; count them separately.

Delta India retail fees (GST included, 10% referral discount): maker **2.12 bps**, taker **5.31 bps**. A maker round trip costs 4.25 bps. On BTCUSD/ETHUSD mainnet the touch is 1 tick (0.06 / 0.18 bps), so passive quoting there cannot earn the fee back without a rebate.

## Workflow

Scripts live in `.claude/skills/quant-researcher/scripts/` and write to a scratch directory, never to the repo.

1. **Fills and PnL** (read-only, venue is the source of truth; bot `artifacts/economics/*.json` is not):
   ```bash
   python3 .claude/skills/quant-researcher/scripts/fetch_delta_fills.py --out $SCRATCH/fills.json
   python3 .claude/skills/quant-researcher/scripts/markout_report.py --fills $SCRATCH/fills.json --cache $SCRATCH/bn
   ```
   Use `--since <ISO time>` to compare before and after a deploy (`git log --date=iso` gives merge times). Today's fills are skipped: Binance publishes the daily 1s dump the next day.
2. **Read the report in this order:** cash-flow net and the maker/taker fee split → maker `cap` vs `fee` → markouts by side → the pre-fill price path. If most maker fills follow a move toward the quote, the book is being picked off, not earning spread.
3. **Market selection** (public mainnet data):
   ```bash
   python3 .claude/skills/quant-researcher/scripts/scan_delta_markets.py --samples 8 --gap 15
   ```
   A pair is a candidate when its median spread is well above the 4.25 bps round-trip fee and turnover is at least about $1M/day. Spread in ticks matters: many ticks means you can quote inside and be first; one wide tick means queue position decides.
4. **Shadow test before any live change** (mainnet data, no keys, no orders):
   ```bash
   cex-mm/scripts/shadow.sh start ADAUSDT,NEARUSDT   # dry-run quotes + Delta trade recorder
   cex-mm/scripts/shadow.sh status
   cex-mm/scripts/shadow.sh report --sweep 3,4,5,6,8 --latencies 0,300,1000
   ```
   Live view: `cex-mm/scripts/shadow.sh dashboard` → http://127.0.0.1:8788/ (simulator re-runs every 2 min).
   The report replays the logged quotes against recorded mainnet trades (strict "trade prints through our price" fills). `--sweep` re-prices around the logged fair, so one recording tests several widths. Judge by net60 over ≥ 300 fills and check the verdict holds at 1000 ms latency and under `--rule touch`.
5. **Check that the code does what the config claims** before tuning a knob (see Known gaps).
6. **Write the memo** to `cex-mm/artifacts/research/YYYY-MM-DD-<slug>.md` using the template below.

## Known gaps

Code-level gaps (spread model, κ, economics, daily loss) are listed in `.claude/rules/cex-mm.md`; verify each still exists before citing it. Operational gaps:

| Area | Gap |
|------|-----|
| Inventory | With `MM_MAX_INVENTORY` = one order, skew saturates after one fill and the exit quote clamps to fair ± 1 tick |
| Telemetry | A bot started before the 2026-09-29 OEMS upgrade writes to /dev/null: no MM_METRICS until it is restarted from the Strategy page. OEMS fills/TCA now come from the venue sync (`/api/fills`, `/api/tca`, `/api/performance`) |
| Reference price | `fstream.binance.com` does not resolve here, so the Binance lead is silently 0 unless `MM_BINANCE_WS_BASE=wss://data-stream.binance.vision/ws` is set. Check `binance_mid` in `MM_METRICS` before trusting any lead result |
| Account risk | No notional-vs-equity cap and no liquidation-distance stop |

## Incident check (five minutes)

1. **Venue:** `fetch_venue_pnl()` (see `mm-ops`). Record equity, unrealized PnL, and each position's sign and size.
2. **Bot:** `curl -s localhost:8791/api/strategies` (is the pid alive?) and recent fills from `fetch_delta_fills.py`.
3. **Match:** venue size must match what the bot thinks it holds. If not, call it an estimator bug and stop drawing strategy conclusions.
4. **Classify:** inventory loss if unrealized ≈ `q × (mark − entry)`; adverse selection only if fills show negative markout; ops if rejects, a dead process, or hard-cap loops.
5. **Recommend** (the user decides anything that changes the position):

| State | Call |
|-------|------|
| Synced, inside cap, adding side off | Let the reducing quote work, or flatten to reset the demo |
| `\|q\|` above the cap | Stop the bot and flatten or reduce-only |
| Bot flat, venue not | Pause, `scripts/sync_economics_from_venue.py`, then restart |
| User wants to hold for a bounce | Bot off. That is a directional bet, not market making |

## Rules

- Sign the position before advising: `q > 0` loses when price falls.
- Separate inventory PnL from spread PnL. One green day from a directional position is not edge.
- Demo fills do not validate economics. Demo validates plumbing; mainnet public data (or a queue-aware paper simulation on it) validates edge.
- One knob per experiment, a success metric (net60 per maker fill over ≥ 300 fills), and a stop rule.
- Mainnet only through `cex-mm/docs/MAINNET_GATE.md` and with the user's consent. No flatten, cancel, or restart without asking.

## Memo template

```markdown
# Quant memo: <title>
**Date:** · **Venue:** demo|mainnet · **Symbols:** · **Data:** <fills n, dates>

## Question
## PnL attribution (capture / markout / fees / inventory), maker vs taker
## What the code actually does (vs config)
## Findings, ranked by money at stake
## Next experiment (one knob, metric, success, stop)
```
