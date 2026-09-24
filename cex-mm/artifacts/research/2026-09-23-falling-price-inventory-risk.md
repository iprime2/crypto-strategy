# Quant memo: Falling price vs a long book

**Date:** 2026-09-23 · **Venue:** Delta India demo (cross) · **Symbols:** BTCUSDT, ETHUSDT

## Question

How do we stop a continued selloff from liquidating the account, and what is the next strategy change?

## Position sign and venue snapshot

Pulled from `fetch_venue_pnl` at ~16:34 UTC. Both positions are **long** (`q > 0`). A falling mark loses money.

| | BTC | ETH | Account |
|--|-----|-----|---------|
| q | +0.012 | +0.09 | |
| Entry → mark | 85,786 → 84,230 | 2,733 → 2,666 | |
| uP&L | −$18.64 | −$6.07 | **−$24.72** |
| Realized | 0 | +$0.27 | +$0.27 |
| Notional at mark | ~$1,011 | ~$240 | **~$1,251** |
| Equity / available | | | **$172** / **$20** available, **$177** blocked |

uP&L matches `q × (mark − entry)` (BTC −$18.7, ETH −$6.0). This is inventory mark-to-market, not a spread-model failure (`resource/05` §1).

**Shock (no new fills):** gross notional / equity ≈ **7.3×**. Equity reaches ~0 after about a **14%** further drop in both marks (`172 / 1251`). Maintenance margin liquidates **before** that. A 10% drop is about **−$125**, leaving ~$47.

Caps in `.env`: BTC `MM_MAX_INVENTORY=0.01` (~$840 at this mark, **~5× equity**), ETH `0.05` (~$133). Live size is already over both (0.012 and 0.09). Coin caps do not bound dollar risk.

## Bot snapshot

- Process `mm-bot` PID 9490 still running. Log mtime is current.
- Last `MM_METRICS` (~09:22 UTC): **`inventory: 0`** on both symbols, **`place_bid: true`**, while the venue was already long. Estimator failed. Do not treat those quotes as inventory control.
- From then until 16:35 UTC the log is only `kill switch / L3 — cancel all`. The running binary’s message text does not match current `runner.rs` (`risk kill` / `regime L3`), so this process is an **older build**.
- Kill path **cancels orders**. It does not flatten. The long stays on while quotes are pulled (`resource/05` §7 K2 says FLATTEN; `STRATEGY.md` §9 same).

## PnL attribution

| Bucket | This session |
|--------|----------------|
| Inventory MTM | **≈ −$24.7** (the whole loss) |
| Realized spread / fees | **+$0.27** |
| Funding / hedge | Not separated; no hedge leg |

Markouts in the 09:22 metrics were already adverse (`rolling_adverse_bps` ~9 BTC, ~12 ETH) while the bot still bid, because it thought `q = 0`.

## Controls engaged vs gaps

| Control | Engaged now? | Gap |
|---------|----------------|-----|
| Skew / one-sided | No — bot sees q = 0 | Venue reconcile not in the running binary, or stuck before quote |
| Hard cap | Size is over cap | Over cap **cancels both sides** and leaves q (`runner.rs`). Guéant–Lehalle–Fernandez-Tapia and Hummingbot remove only the **adding** side ([inventory skew](https://hummingbot.org/strategies/v1-strategies/strategy-configs/inventory-skew/)) |
| Daily loss $150 | Not firing | `daily_pnl_usd` stays 0. Limit is also ~87% of equity; R5 §6.2 uses **1–2% of capital** on realized+MTM. Hummingbot’s kill switch stops on session return and **does** move when mark moves with no new trades ([kill switch](https://hummingbot.org/client/global-configs/kill-switch/)) |
| Liq distance | None | |
| Dollar cap | None | 0.01 BTC is already several times this account |

## How a quant manages a falling price

Layered, in this order (`resource/05` §2.1–2.3, §6.2, §7):

1. **Size q in dollars of equity**, not only coins. Soft ≈ 20–30% of allocated capital, hard ≈ 40–50%, and never more than you can exit in about a minute. On ~$170 that is tens of dollars of notional, not $1,000 of BTC.
2. **Inside the band:** skew the reservation price against q (Avellaneda–Stoikov / linear `skew_bps = −k × q/Q`). Cheap if the other side fills.
3. **At the hard band:** stop the side that **adds** inventory. Keep the reducing side. Hummingbot emits no bids once base value is above the range.
4. **If still outside for T_flat (30–60s), or loss/drawdown hits:** **reduce-only taker flatten**, not a silent cancel. Cancelling into a trend is how the inventory death spiral works (§2.3, §5).
5. **Loss limit on realized + unrealized**, about 1–2% of equity for an MM book, with no same-day auto-resume (K1). Hummingbot’s own switch is session PnL and can ignore unrealized; R5 says include MTM because that is what liquidates you.
6. **One net bet.** BTC and ETH longs are the same selloff. Cap portfolio delta in USDT, not two independent coin caps.

A hedge (short perp elsewhere) does not fit this single-account demo. Same-venue reduce-only is the hedge.

## Conclusion

Loss is a **levered long in a down move**, made possible because the bot quoted as if flat and because coin caps allow notional several times equity. The live process is cancelling, not exiting, so the next 10% down still hits the account.

## Recommendation now

Stop the bot and flatten (`scripts/flatten_delta.py`) if you do not want this long. Leaving it on does not work the inventory off while it is stuck in cancel-all. I have not flattened; that needs your go-ahead.

## Next experiment (one knob)

**Hypothesis:** replacing “over cap → cancel all and continue” with “over cap → reduce-only on the exit side until `|q| ≤ cap`” cuts inventory within one minute without new risk.

**Change:** only the hard-cap branch in `crates/mm-bot/src/runner.rs`. Wire it to venue `q` (the running binary must be rebuilt).

**Success:** after a forced over-cap position on demo, `|q|` back inside cap within 60s, no orders that increase `|q|`, and a log line per reduce fill.

**Stop:** any reduce that increases `|q|`, or three rejects.

**Not in this experiment** (follow-ups, do not mix): set `MM_MAX_INVENTORY` from equity (BTC cap on this account is about 0.001, not 0.01); feed venue uP&L into `daily_pnl_usd` and flatten at about −2% equity; stop treating loop REST time as a 500ms stale book (`risk.rs` `last_book_ts`), which is a likely cause of the endless cancel loop.

## Sources

- `crypto-strategy/resource/05-risk-hedging-pnl-failure-modes.md` §2, §6.2, §7
- `crypto-strategy/STRATEGY.md` §9–10
- [Hummingbot inventory skew](https://hummingbot.org/strategies/v1-strategies/strategy-configs/inventory-skew/)
- [Hummingbot kill switch](https://hummingbot.org/client/global-configs/kill-switch/)
- [Guéant–Lehalle–Fernandez-Tapia, inventory-bounded quotes](https://arxiv.org/html/1105.3115v5)
