# crypto-strategy

Market-making strategy for crypto CEXs (OKX, Binance, Bybit) driven through their APIs.

## Layout

```
crypto-strategy/
├── README.md                 this file
├── AGENTS.md                 Cursor agent entry (rules, skills, plans)
├── STRATEGY.md               strategy design document (synthesis of the research)
├── plans/                    build plans (canonical; not under cex-mm/)
├── .cursor/                  rules + skills (start: skills/using-cs-skills)
├── cex-mm/                   Rust MM bot implementation
└── resource/                 research knowledge base
    ├── 01-academic-papers.md
    ├── 02-practitioner-articles.md
    ├── 03-exchange-apis-okx-binance-bybit.md
    ├── 04-open-source-tools-and-data.md
    ├── 05-risk-hedging-pnl-failure-modes.md
    ├── 06-godark-vanilla-mm-strategy-analysis.md   prior GoDark MM vs STRATEGY.md
    ├── godark-mm-bot/        export + porting guide from vanilla-mm-rust
    └── papers/               33 open-access PDFs referenced by 01-academic-papers.md
```

## Where to start

1. `STRATEGY.md` — the design: thesis, architecture, fair value, GLFT quote model, inventory bands, order management, risk controls, venue choice, rollout gates, parameter starting points.
1b. `resource/06-godark-vanilla-mm-strategy-analysis.md` — if continuing from the **GoDark vanilla MM** bot: what to reuse (markout guard, AS bps math, eval guards) vs what changes on CEX.
2. `resource/01-academic-papers.md` §13–14 — what the literature says a good MM must do, and a reading order.
3. `resource/02-practitioner-articles.md` — "Cross-source consensus" and the parameter table at the end.
4. `resource/03-exchange-apis-okx-binance-bybit.md` — comparison table and recommendations before touching any API.
5. `resource/05-risk-hedging-pnl-failure-modes.md` — risk-control checklist and failure-mode catalogue; these are the go-live requirements.

## Conventions in the research notes

- Every claim carries a URL. Items that could not be opened or confirmed are tagged `[UNVERIFIED]` / `unverified`; illustrative numbers from sources are tagged `[SYNTHETIC]`.
- Numbers quoted are the sources' numbers. Anything marked *(start)* in `STRATEGY.md` is a starting point to be recalibrated from our own recorded data and markouts.
- Research date: 2026-09-20. Exchange fees, rate limits and API details change often; re-verify against the official docs before implementing.

## Status

Research, design, and **`cex-mm/`** Rust bot (Bybit testnet-first). Build plan: `plans/cex_mm_rust_bot.plan.md`. Runbook: `cex-mm/README.md`.

## Cursor

Open **`crypto-strategy/`** as the workspace when possible so `.cursor/rules` and `.cursor/skills` apply. Plans live in `plans/`, not inside `cex-mm/`.
