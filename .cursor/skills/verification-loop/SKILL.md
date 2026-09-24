---
name: verification-loop
description: >-
  Gate before claiming crypto-strategy / cex-mm work done — cargo test/build,
  optional testnet smoke, paste evidence. Use before saying done, fixed, or
  ready for QA.
---

# Verification loop (crypto-strategy)

“Seems right” is not done.

## Checklist

1. Re-read acceptance criteria (plan slice or user ask).
2. **mm-core touched?** `cargo test -p mm-core`
3. **Bot/bybit touched?** `cargo test -p mm-bot` and/or `cargo test -p mm-bybit` (respect `--ignored` for keys)
4. **Build:** `cargo build -p mm-bot` from `cex-mm/`
5. **Behavior claim on testnet?** dry-run or documented manual step with log snippet
6. **Docs only?** links and paths still valid

WSL without `gcc`: `export PATH="$HOME/.local/bin-wrappers:$PATH"` if using zig `cc` wrapper.

## Done template

```markdown
## Verification
- AC: all met? yes/no
- Commands: …
- Output: …
- Residual risks: …
```

## Exit

Checklist complete with pasted command results for non-trivial changes.
