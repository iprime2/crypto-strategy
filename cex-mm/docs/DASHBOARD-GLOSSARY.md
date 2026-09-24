# CEX-MM dashboard — plain-language glossary

This doc explains what you see on the live telemetry dashboard (`./scripts/run_dashboard.sh` → http://127.0.0.1:8787/). No trading or math background required.

---

## Big picture: what is this bot doing?

Imagine you run a **stall on Delta Exchange** that always shows a **buy price (bid)** and a **sell price (ask)** for BTC.

- You earn when someone trades against you and the price **does not immediately run away** from you (you keep part of the **spread**).
- You lose when someone **knows something you don’t** and fills you right before a big move (**adverse selection**).

The dashboard shows: **what prices the bot thinks are “fair”**, **how wide it quotes**, **how much inventory it holds**, and **how that compares to Binance** (a bigger, faster market used only as a **reference clock**, not where you trade).

---

## Cross-venue benchmark table (one row per symbol)

| Term | Simple meaning |
|------|----------------|
| **Symbol** | The pair, e.g. BTCUSDT. |
| **Status — live** | The bot is configured to quote this symbol (`MM_SYMBOLS`). |
| **Status — inactive** | Shown for history only (e.g. SOL); the bot is **not** quoting it. |
| **Fair** | The bot’s best guess of “true” price **right now**, mixing Delta’s book, Binance’s move, order-flow hints, funding, etc. Quotes are built around this. |
| **Binance mid** | The middle of Binance’s best bid and ask (USDT perpetuals). **You are not trading here** — it’s a **speedometer from the largest market**. |
| **Venue mid** | Middle of the bot’s **planned bid and ask on Delta** (where it wants to quote). Usually close to Fair. |
| **Lead skew** | How far **Fair** is above or below **Binance**, in **bps** (0.01%). Example: **+8 bps** means Fair is about **0.08% higher** than Binance — not “$8 cheaper.” |
| **Spread** | How **wide** the bot’s quotes are, in bps (bid distance + ask distance from the center). Wider = safer, fewer fills; narrower = more fills, more risk. |
| **Last order** | Last post-only order the dashboard saw: side, price, time. Proof the bot is actually sending orders. |

**Tip:** **Lead skew** and **Spread** are both in **bps**. Price columns (Fair, Binance mid, Venue mid) are in **dollars** (or USDT).

---

## Symbol card KPIs (your screenshot)

| Term | Simple meaning |
|------|----------------|
| **Fair** | Same as the table — anchor price for the strategy. |
| **Spread** | Total quote width in bps (see chart orange line on the right axis). |
| **Bid / Ask** | Exact prices the bot last computed for post-only orders on **Delta**. |
| **Venue mid** | `(Bid + Ask) / 2` — center of your quote band on Delta. |
| **Inventory** | Net position in the asset (e.g. BTC). **0** = flat. Positive = long; negative = short. The bot skews quotes to avoid building too much inventory. |
| **Regime (L0–L3)** | “How stressed is the market?” **L0** = calm; higher = more vol/toxicity. **L3** = emergency: cancel all quotes (kill switch). |
| **Lead skew** | Same as table — Fair vs Binance in bps. |
| **Vol** | Short-term volatility estimate (bps). Higher vol → bot tends to **widen** spread. |
| **Markout adj** | Extra spread the bot adds on bid/ask because recent fills **moved against** it (adverse selection protection). **0 bps** = no extra penalty yet. |
| **Snipe** | Share of recent fills that looked like **toxic / sniping** flow. High → bot gets more defensive. |
| **Quoting — B / A** | **B** = willing to post a **bid**; **A** = willing to post an **ask**. Blue = on; gray dot = that side is off (inventory, regime, guardrails, etc.). |

---

## Chart lines (BTCUSDT card)

| Line | Color | Simple meaning |
|------|-------|----------------|
| **Fair** | Blue | Bot’s fair value over the last ~80 samples (~80 seconds if metrics are 1 Hz). |
| **Binance mid** | Green | Binance reference mid over the same window. |
| **Venue mid** | Purple dashed | Center of your Delta quotes over time. |
| **Spread bps** | Orange (right axis) | Quote width over time — often flat if config is fixed (e.g. 24 bps). |

**Reading your chart:** Blue and purple track together near **~86,210**. Green sits lower near **~86,142**. That gap is normal when **Delta’s ecosystem prices BTC a bit “richer” than Binance** at that moment. The bot is **not** ignoring Binance — it **pulls Fair partly toward Binance** (see below) while still quoting **on Delta**.

---

## Summary strip (top)

| Term | Simple meaning |
|------|----------------|
| **Orders placed** | Count of successful **MM_ORDER** placements since the dashboard started. |
| **L3 cancel-all** | How often the bot hit **regime L3** and cancelled everything. |
| **Rejects** | Exchange said “no” to an order (size, margin, post-only would cross, etc.). |
| **Venue** | Where you trade (e.g. **DELTA**). |

---

## Events & economics (bottom tables)

| Term | Simple meaning |
|------|----------------|
| **Events** | Recent log lines: orders, rejects, L3 warnings — a short audit trail. |
| **Economics — Pos** | Position from fill tracking. |
| **Realized** | Realized PnL from closed piece of trades (when fills exist). |
| **Fees** | Fees paid. |
| **Fills** | Number of fills recorded in economics files. |

---

## Why Binance for the “mid” reference? Why not Bybit, OKX, or Hyperliquid?

**Short answer:** Binance USDT-M perps are usually the **deepest and fastest** price-discovery venue globally. Many strategies (and research in this repo) treat Binance as the **lead** market: when Binance moves, other venues often follow with a small lag.

| Choice | Role in *this* project |
|--------|----------------------|
| **Binance** | **Reference only** (`mm-binance` WebSocket `bookTicker`). Feeds **fair value** via `lead_weight` (default **0.5** in the bot). |
| **Delta / Bybit** | **Where orders actually go** — adapters (`mm-delta`, `mm-bybit`), fees, margin, post-only rules. |
| **OKX / Hyperliquid** | Not wired as benchmark yet. Could be added as alternate feeds; same idea: pick the venue you trust as **lead** for the pairs you trade. |

**Why not Bybit as benchmark while trading Delta?** You *could* use Bybit mid if you quoted on Bybit or if Bybit led your symbol more than Binance. Here, Binance is a **convention from the strategy doc and GoDark port**: one stable global reference, same for every symbol card. **Execution venue and benchmark venue are allowed to differ.**

**Future:** Adding `MM_BENCHMARK=bybit|okx` would be a product choice (correlation, latency, which market leads *your* venue). The code today is Binance-specific in `mm-binance`.

---

## “Binance price is cheaper — should we MM on Binance instead?”

**Important:** Binance is **not cheaper in the sense of “better profits because the number is lower.”** It’s the **same BTC**; exchanges show **slightly different prices** at the same time (**basis** / **premium**).

Example from a live snapshot:

- Binance mid ≈ **86,142**
- Fair / Delta quotes ≈ **86,210**
- Difference ≈ **~68 USDT** ≈ **~8 bps** → shows up as **Lead skew ~+8 bps**

That means: **on Delta, the market (and your fair value) is priced a bit above Binance**, not that you should buy on Binance and magically market-make “for less.”

### What market making actually earns

Profit is roughly:

**spread captured + rebates − fees − adverse selection (markout)**

It does **not** come from picking the exchange with the **smallest dollar number** on the screen.

### Would MM work “better” on Binance?

**Different venue = different game:**

| Factor | On Binance (hypothetical) | On Delta (what you run) |
|--------|---------------------------|-------------------------|
| Competition | Very fierce; tight spreads; fast players | Often wider; fewer HFTs |
| Fees & programs | Maker rebates / VIP tiers matter a lot | Delta India fee schedule |
| Adverse selection | High on liquid pairs at tight touch | Depends on flow; demo ≠ mainnet |
| Your edge | Harder without scale and low latency | Cross-venue fair + wider quote may fit **small capital** |

Moving to Binance because the **green line is lower** would **not** copy your current edge. You’d face **new** spreads, queues, and toxicity. The **lead skew** line is there so the bot **doesn’t quote blind** when Delta and Binance **disagree** — it nudges Fair toward the leader so you’re less likely to be **picked off** when Binance jumps.

### When a big Binance vs Delta gap is worrying

- **Small steady gap (few–20 bps on BTC):** often normal **basis** between venues/products.
- **Huge or jumping gap (especially on illiquid symbols):** fair value is uncertain; regime may widen or L3; **don’t** assume “arb = free MM profit.”
- **Demo books:** Delta testnet depth can be **misleading**; use mainnet liquidity reports for sizing expectations (`artifacts/liquidity-comparison-report.md`).

---

## How Fair uses Binance (one sentence + picture)

The bot starts from **Delta’s book**, then **pulls Fair toward Binance** by a fraction (`lead_weight`, e.g. 50%):

```text
Fair ≈ Delta-native price  +  lead_weight × (Binance mid − Delta-native price)  +  other tweaks (OFI, funding, …)
```

So when Binance is **below** Delta, Fair is **pulled down a bit** vs Delta alone — but your **orders still rest on Delta** at bid/ask around that Fair.

---

## Quick cheat sheet

- **Dollar columns** = levels (Fair, Binance, Venue mid, Bid/Ask).
- **bps columns** = small percentages (Spread, Lead skew, Vol, Markout adj).
- **Green below blue** = Delta/fair **rich** vs Binance, not “go trade Binance for cheap BTC.”
- **Binance** = reference; **Delta** = where you make markets.
- **L3** = stop quoting; **Rejects** = fix config/size/margin.

---

## Related files

- Bot strategy design: [../../STRATEGY.md](../../STRATEGY.md)
- Run dashboard: [../README.md](../README.md) (Live dashboard section)
- Liquidity comparison (Bybit vs Delta): [../artifacts/liquidity-comparison-report.md](../artifacts/liquidity-comparison-report.md)
