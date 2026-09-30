---
paths:
  - "STRATEGY.md"
  - "resource/**"
  - "plans/**"
  - "cex-mm/artifacts/research/**"
---

# Research and design docs

- `STRATEGY.md` and `resource/01`–`06` are the source of truth for why the bot does what it does. If code must diverge, update the doc in the same change.
- Every factual claim keeps its URL. Tag claims you could not confirm `[UNVERIFIED]` and illustrative numbers `[SYNTHETIC]`. Parameters that are starting points are marked *(start)* until calibrated from our own data.
- Distinguish "designed" from "implemented in cex-mm". Check the code before saying a control exists.
- Parameter changes are documented as *(start)* → calibrated-from-data, not as silent constant changes in code.
- New research goes into a numbered `resource/0N-*.md` or extends an existing one. Update the reading order in `README.md` only when the structure changes.
- GoDark material under `resource/godark-mm-bot/` is reference only. Do not copy its artifacts into `cex-mm/`.
- Delivery plans live in `plans/`. Quant memos live in `cex-mm/artifacts/research/YYYY-MM-DD-<slug>.md`.
