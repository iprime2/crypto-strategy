---
name: using-cs-skills
description: >-
  Routes crypto-strategy work to the right skills (research, lead-engineer,
  mm-rust, testnet ops, security, TDD, verification, QA). Use at the start of
  non-trivial tasks or when unsure which skill applies.
---

# Using crypto-strategy skills

Load this first for non-trivial work, then open **only** the skills you need.

## Decision tree

```text
Task arrives
  ├── Strategy / papers / STRATEGY.md / resource/? → mm-research-analyst
  ├── Live loss, liquidation, flatten vs hold, markout experiment? → /quant-researcher
  ├── Quick "are we in trouble" snapshot? → /research-desk (then quant-researcher if it is not obvious)
  ├── Build plan / multi-slice feature? → lead-engineer (+ plan in plans/)
  ├── Rust bot (cex-mm/quote-bot)? → mm-rust-engineer (+ cex-mm for commands)
  ├── OEMS API / migrations / TCA / reconcile? → oems-rust-backend + oems-api-contract
  ├── OEMS tables or idempotent keys? → oems-schema
  ├── Slippage, markout, or TCA rows? → oems-tca
  ├── Delta wallet or position poll? → oems-delta-snapshot
  ├── Start, stop, or config apply? → oems-supervisor
  ├── OEMS screens (Vite/React)? → oems-frontend (+ oems-ui if the layout is new)
  ├── Testnet smoke / record / universe / fire drill? → testnet-ops
  ├── Quote, markout, risk, OMS behavior? → mm-rust-engineer + mm-trading rule
  ├── Auth, keys, WS payloads, .env? → security-mm
  ├── New logic in mm-core? → tdd-workflow-mm first
  ├── Code written, about to say done? → verification-loop
  ├── Independent sign-off? → qa-mm (not the author)
  └── Typo / one-line config / comment only? → skip full loop; still run targeted tests if code touched
```

## Paths

| Area | Path | Primary skill |
|------|------|----------------|
| Design | `STRATEGY.md`, `resource/` | mm-research-analyst |
| Plans | `plans/*.plan.md` | lead-engineer |
| Bot | `cex-mm/quote-bot/**` | mm-rust-engineer |
| OEMS API | `cex-mm/backend/**` | oems-rust-backend |
| OEMS UI | `cex-mm/web/**` | oems-frontend |
| Agent config | `.cursor/` | (this file) |

## Anti-rationalization

| Excuse | Rebuttal |
|--------|----------|
| “It’s just testnet” | Testnet proves plumbing, not edge — still post-only, kill switch, no secrets |
| “Strategy doc is stale” | Update STRATEGY or resource, or cite plan slice — don’t drift silently |
| “I'll QA later” | Run verification-loop before handoff; qa-mm for non-trivial slices |

## Exit

Match the skill’s exit criteria. Evidence = command output, test counts, or testnet log snippets — not prose alone.
