# Quant memo: Demo uP&L with long inventory

**Date:** 2026-09-23 · **Venue:** Delta India demo · **Symbols:** BTCUSDT, ETHUSDT

## Question

What should a quant researcher conclude about ~−$10 uP&L, and what is the next experiment?

## Data

- **Venue API:** net equity ~**$196**; uP&L ~**−$10.08**; realized ~**+$0.53**; unrealized ~**−$10.08**.
- **Positions:** BTC **+0.006** @ ~86,773; ETH **+0.18** @ ~2,765 (marks ~85,938 / ~2,737).
- **Bot log (last active ~07:54 UTC):** ETH **hard cap** (0.18 vs env cap ~0.05), both sides off; BTC **ask-only**, `place_bid: false`.
- **Historical issue:** economics often **position 0** while venue long → invalid inference on spread/γ during that window ([performance review](../mm-performance-review-2026-09-23.md)).

## PnL attribution

| Component | Estimate | Share of problem |
|-----------|----------|------------------|
| Unrealized inventory | ~−$5 BTC + ~−$5 ETH | **~100% of visible uP&L** |
| Realized MM edge | ~+$0.53 realized | Small; **not** offsetting inventory |
| Spread / markout failure | **Not identified** | Markout fields largely idle; insufficient fills under clean measurement |
| Ops / sync | **Material confound** | Two-sided quoting while bot thought flat can **increase q** |

**Conclusion:** This is primarily **inventory (q) × Δprice**, not a validated statement that fair value or κ is wrong.

## Control system (Avellaneda–Stoikov view)

- **Target:** reservation skew + caps keep |q| small; earn spread on round-trips.
- **Observed:** |q_ETH| **3.6×** typical cap → limit breach; control eventually **shuts quotes**.
- **BTC:** mild long; skew toward **asks** — consistent with inventory reduction **if** measurement is correct.

## Identification issues

1. Venue vs bot inventory mismatch (fixed in source; **binary rebuild** required).
2. Demo **L3** cancel storms → low useful markout sample ([~44k L3 events](../mm-performance-review-2026-09-23.md)).
3. Log may be **stale** — confirm mm-bot process before live conclusions.

## Quant researcher recommendation

1. **Stop confounded data:** pause bot; cancel stray orders.
2. **Reset state:** **flatten** (~−$10) *or* user accepts **directional overlay** with bot **off**.
3. **Fix estimator:** deploy venue reconcile; `sync_economics_from_venue.py` until then.
4. **Next experiment (pre-registered):**
   - Single symbol or BTC-only; **ETH cap** ≤ ~0.03 for ~$200.
   - Demo: consider **L3 off** (`MM_REGIME_L3_DEPTH_RATIO=0`) to collect fills.
   - Success = **signed markout at 5s** over ≥50 fills, not “green uP&L day.”
5. **Mainnet:** blocked until [MAINNET_GATE.md](../../docs/MAINNET_GATE.md).

## Engineering tasks

- `cargo build -p mm-bot` (linker / build-essential on WSL).
- MM_REJECT + dashboard session stats for reject attribution.

## Skill

Repeat workflow: [quant-researcher](../../../.cursor/skills/quant-researcher/SKILL.md) (`/quant-researcher`).
