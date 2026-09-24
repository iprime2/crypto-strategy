# crypto-strategy — Agent North Star

Research, design, and implementation of **CEX USDT-perp market making** (Bybit-first). This folder is the **agent root** for MM work—not the multi-project `projects/` workspace alone, and not only `cex-mm/` code.

## Layout (agent vs code)

| Path | Purpose |
|------|---------|
| `STRATEGY.md`, `resource/` | Research and design (source of truth for *what* to build) |
| `plans/` | Build plans and milestones (Cursor plans live here as files—edit copies here, not only in `~/.cursor/plans/`) |
| `.cursor/rules/` | Scope, git, and stack rules for this tree |
| `.cursor/skills/` | Lead Engineer and CEX-MM delivery skills |
| `cex-mm/` | Rust bot implementation only (no duplicate plans/skills under `cex-mm/`) |
| `.cursor/skills/quant-researcher` | `/quant-researcher` — live PnL, risk, experiments |
| `.cursor/skills/research-desk` | `/research-desk` — short incident check |

## How to work here

1. **Route:** `.cursor/skills/using-cs-skills/SKILL.md` → pick research vs Rust vs testnet vs QA.
2. Read `STRATEGY.md` and the relevant `resource/` note before changing behavior.
3. For non-trivial bot work: **lead-engineer** + active plan in `plans/`.
4. Implement from **`cex-mm/`**; verify with **verification-loop**; independent **qa-mm** for slices.
5. Rules: `.cursor/rules/` (`orchestration` is always on in this folder).
6. Git: never pull/push/commit unless the user explicitly asks in the conversation.

## Opening in Cursor

Prefer opening **`crypto-strategy/`** as the workspace root so rules and skills apply automatically. If the workspace is `projects/`, rules still apply via globs on `crypto-strategy/**` (see `.cursor/rules/context.mdc`).

## Verify (cex-mm)

```bash
cd cex-mm
cargo test -p mm-core
cargo test -p mm-bot
```

Testnet/live requires gitignored `cex-mm/.env` (Bybit keys).
