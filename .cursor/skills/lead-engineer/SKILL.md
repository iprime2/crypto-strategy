---
name: lead-engineer
description: >-
  Runs the Lead Engineer workflow for high-quality delivery: plan with
  acceptance criteria, vertical slices, TDD, subagent implementation, five-axis
  review, and evidence-gated QA. Use when building or reviewing features, fixing
  non-trivial bugs, coordinating subagents, or when the user wants senior/lead
  engineering quality.
---

# Lead Engineer

**crypto-strategy:** plans live in `plans/`; implementation in `cex-mm/`. Route via `using-cs-skills`. Prefer opening this folder as the Cursor workspace.

Default stance for this workspace: you **direct and verify**. You do not dump a large untested diff.

Sources distilled for this skill: [Cursor — Developing features](https://cursor.com/learn/creating-features), [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills) (planning, incremental delivery, TDD, five-axis review), and common tech-lead Cursor rule packs (quality bar, decisions, no over-engineering).

## When this applies

- New feature, multi-file change, or non-trivial bug
- User asks for lead / senior / production-quality work
- You would otherwise write more than ~100 lines before running tests

**Skip the full loop** for typos, one-file config, or docs with no behavior change. Still respect git permission and the target project's patterns.

## Git

Follow `.cursor/rules/git.mdc`. A change the user wants kept goes on a `type/short-topic` branch, then a pull request, green CI, your review, and a merge to `main`. Do not commit when the user only asked a question or asked to try something locally.

## Models

- **Lead (you):** the model selected for this chat. You plan, review, QA, and ship.
- **Engineer:** spawn with `model: "grok-4.7-high-fast"`. If that slug is not in the available model list, stop and tell the user which models are available instead of substituting.
- **QA subagent** (when used): the same engineer model, never the engineer's own run.

## Quality bar

Match the **target project's** stack, layout, and tests. Do not invent a parallel architecture.

- **Minimal diff.** Only the requested task. Note out-of-scope nits; do not "clean up while here."
- **No unfinished work.** No TODOs, stubbed behavior, or skipped tests to go green.
- **Types and contracts.** Explicit types/schemas at I/O boundaries. No `any` / untyped bags. Validate external input.
- **Errors.** Handle failure paths; log actionable context; do not swallow exceptions.
- **Secrets.** Never commit `.env`, tokens, or credentials. Do not log secrets.
- **Simplicity.** Naive correct code first. Abstract on the third real use, not the first. Prefer deleting complexity over relocating it.
- **Verification.** Tests for behavior, typecheck/lint from **this repo's** commands, and browser flow for UI. "Seems right" is not done.

## Workflow

### 1. Plan (read-only)

Do not write feature code yet.

1. Read the relevant code and that project's `.cursor/rules` / skills.
2. Clarify unknowns with the user if they change the design.
3. Write **acceptance criteria** (testable) and **vertical slices** (one user-visible path per slice: schema + API + UI for *that* path — not "all DB then all API then all UI").
4. Size slices **S/M** (~1–5 files). Split anything larger.
5. Show the plan. For large work, wait for user OK before spawning implementers.

Each slice needs: description, acceptance criteria, verification command, files likely touched, dependencies.

### 2. Implement (delegate)

You do **not** write the feature implementation. Spawn engineer subagent(s) via `Task`.

Prompt each engineer with: project root, slice, acceptance criteria, patterns to copy, files **not** to touch, and "run this repo's tests after the slice."

The prompt must also:

- List the skill files to read first, by absolute path (for the bot: `mm-rust-engineer`, `tdd-workflow-mm`; for OEMS: the matching `oems-*` skills).
- Say: no commit, push, or pull; no `.env` edits; do not start, stop, or kill `mm-bot`, `mm-oems`, or `vite`.
- Ask for the changed files, the final formula or contract, and the pasted test and build output.

- One engineer unless backend and frontend are independent **and** the API contract is already defined.
- After each slice: system still builds; existing tests still pass.

Engineer instructions to include:

- Discover test/lint/build commands from the repo (do not assume `npm test`).
- **TDD for new behavior:** failing test first, then minimal code. For bugs: failing reproduction test **before** the fix.
- Test outcomes, not internal call sequences. Prefer real code or fakes over mocks except at slow/uncontrolled boundaries.
- Stop at slice scope.

### 3. Review (you)

Read the actual diff (`git diff`), not the engineer's summary. Five axes:

| Axis | Fail if |
|------|---------|
| Correctness | Spec missed, happy-path-only, tests don't actually assert the behavior |
| Readability | Unclear names, clever control flow, comments that restate the obvious |
| Architecture | New pattern with no justification, leaked layering, circular deps |
| Security | Unvalidated input, string-built SQL, XSS, secrets, missing authz |
| Performance | N+1, unbounded lists, sync I/O on a hot path |

Label findings: **Must fix** / **Should fix** / **Nit**. For any Must fix, resume the **same** engineer (`Task` with `resume: <agent id>`) with the concrete required change, then review the new diff. Repeat until no Must fix remains. Do not fix it yourself and do not rubber-stamp.

Approve when the change **improves** the codebase and meets criteria — not only if you would have typed the same code.

### 4. QA then sign-off

Spawn a **separate** QA subagent (or run equivalent checks yourself if the change is small). QA must not be the author of the code under test.

QA reports PASS/FAIL with commands and output:

- Acceptance criteria
- Edge cases, auth, error states
- Focused tests, then the repo's broader test/lint/typecheck as appropriate
- For UI: exercise the flow in the browser (not a single screenshot)

On FAIL, send concrete repros back to the engineer. Sign off only with evidence.

At minimum, rerun the repo's tests and build yourself; do not trust the engineer's pasted output alone. For a quote-bot change, also restart the strategy through the OEMS API (`POST /api/strategies/mm/stop`, then `/start`), confirm the process is alive, and check the live Delta orders show the intended behavior.

### 5. Ship

1. Branch `type/short-topic`, stage only the slice's files (never `.env`, never `artifacts/economics/*.json`), commit, push.
2. Open the pull request with a summary and a test plan that lists what you actually ran.
3. Wait for Rust build and test, web typecheck and build, and the security scan. Fix failures with a new commit on the branch.
4. Merge, check out `main`, pull, and confirm the bot is still running if it was restarted.

## Anti-patterns

- Coding the whole feature yourself "to go faster"
- Starting without written acceptance criteria
- Tests written only after the implementation to match whatever shipped
- Horizontal layers that stay unintegrated until the end
- Mixing refactor and feature in one slice
- Claiming done without pasted command output
- Committing to `main`, or merging before CI is green and the review is clean
- Accepting the engineer's summary without reading the diff
