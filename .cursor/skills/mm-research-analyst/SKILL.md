---
name: mm-research-analyst
description: >-
  Update or extend crypto-strategy research and design (STRATEGY.md, resource/,
  plans crosswalk). Use for literature synthesis, venue comparison, risk
  checklists—not for implementing Rust in cex-mm/.
---

# MM research analyst

## When to use

- Editing `STRATEGY.md` or `resource/0N-*.md`
- Adding citations, failure modes, API notes, or GoDark vs CEX porting analysis
- Aligning build plans in `plans/` with research (R1–R6 crosswalk)

## When not to use

- Implementing or debugging `cex-mm/` Rust → use **mm-rust-engineer**
- Live uP&L, liquidation, flatten vs hold, or a markout experiment → **`/quant-researcher`** (short check: **`/research-desk`**)

## Workflow

1. Read existing section and linked `resource/` file; preserve citation style.
2. State what changed in design terms (fair value, spread floor, kill switch, etc.).
3. If the change implies code work, note a **plan slice** or acceptance criteria — do not implement bot code in the same pass unless the user asked for both.
4. Update `README.md` reading order only when structure changes materially.

## Quality bar

- No unsourced strong claims on fees, rate limits, or exchange behavior.
- Distinguish **design *(start)*** from **implemented in cex-mm** (check `cex-mm/README.md`).
- Keep GoDark analysis in `resource/06`; keep runnable code in `cex-mm/`.

## Exit

Doc diff is coherent, cross-refs valid, and any new parameters tagged *(start)* or tied to R1–R5.
