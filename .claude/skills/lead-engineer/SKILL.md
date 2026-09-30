---
name: lead-engineer
description: >-
  Delivery workflow for non-trivial code changes in crypto-strategy (Rust bot,
  OEMS backend, web UI, scripts): written acceptance criteria and vertical
  slices, test-first implementation, a five-axis review of the real diff,
  evidence-based QA, a security pass, then branch → PR → green CI → merge when
  the user asks to ship. Use for features, multi-file changes, and non-trivial
  bug fixes; skip for typos and one-line config.
---

# Lead engineer

You plan, implement, review, and verify. You do not hand over an untested diff. Area-specific conventions: `mm-bot-dev` (Rust bot), `oems` (backend and web).

## 1. Plan (before writing code)

1. Read the code you will touch, the matching `.claude/rules/`, and the relevant `STRATEGY.md` section or active plan in `plans/`.
2. Ask the user only about unknowns that change the design.
3. Write **acceptance criteria** that a test or a command can check.
4. Cut **vertical slices**: each slice is one working path end to end, 1–5 files. Split anything bigger.
5. For each slice: what changes, which files, which command proves it.
6. For large work, show the plan and wait for the user's OK.

## 2. Implement

- New behavior: write the failing test first, then the minimal code. Bug: write a test that reproduces it before the fix.
- Test outcomes, not call sequences. Fakes over mocks except at network or exchange boundaries.
- Minimal diff in the surrounding style. No drive-by refactors, no TODOs, no skipped tests.
- After each slice the workspace builds and existing tests pass.
- Do not spawn subagents unless the user asked for them. If they did, give the subagent the slice, the acceptance criteria, the files it may touch, and the rules: no commits, no `.env` edits, no starting or stopping the bot.

## 3. Review your own diff

Read `git diff`, not your memory of it.

| Axis | Fails if |
|---|---|
| Correctness | A criterion is not met, only the happy path works, or tests do not assert the behavior |
| Readability | Unclear names, clever control flow, comments that restate code |
| Architecture | Quote math outside `mm-core`, business rules in the UI, a new pattern without a reason |
| Security | Secrets in code, logs or diff; unvalidated venue input; a new order path not covered by cancel-all; SQL built from strings |
| Performance | Unbounded collections, blocking I/O or REST calls on the per-loop hot path |

Label findings Must fix / Should fix / Nit. Fix every Must fix and review again.

## 4. QA with evidence

Run and paste output:

- Targeted tests, then `cargo test --workspace --locked` (and `npm run typecheck && npm run build` if `cex-mm/web` changed).
- Each acceptance criterion: PASS/FAIL with the command or log line that proves it.
- Bot behavior claims: a `dry-run` (no keys, no orders) showing the new `MM_METRICS` fields or quotes. Live-bot checks only with the user's go-ahead (see `mm-ops`).
- Trading invariants still hold (post-only, cancel-all coverage, no secrets in logs).

```markdown
## Verification
- Criteria: … PASS/FAIL (evidence)
- Commands: `…` → result
- Residual risks: …
```

## 5. Ship (only when the user asks)

1. `git checkout -b type/short-topic` from `main`. Stage only the slice's files; never `.env`, `artifacts/economics/*.json`, or `artifacts/shadow/`.
2. Commit, push, `gh pr create` with a summary and the test plan you actually ran.
3. Wait for CI (Rust build and test, web typecheck and build, security scan). Fix failures with new commits on the branch.
4. Merge only when CI is green and the review is clean. Then `git checkout main && git pull`.
5. If the live bot should pick up the change, that is a restart through the OEMS API. Ask first (`mm-ops`).
