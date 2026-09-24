---
name: security-mm
description: >-
  Security review for crypto-strategy / cex-mm — API keys, env files, logs,
  WS/REST input validation, kill switch. Use before mainnet or when touching
  auth, credentials, or private streams.
---

# Security (MM)

## Must not happen

- Commit `cex-mm/.env`, PEMs, or API secrets
- Log `BYBIT_API_SECRET`, full auth payloads, or signing preimages
- Enable withdraw on trading keys (user ops — remind in docs if asked)
- Skip cancel-all path when adding new order entry paths

## Code checks

- **Auth:** HMAC only in `mm-bybit`; timestamps/recv window consistent with Bybit v5
- **WS:** parse JSON with fall-through on malformed messages; no panics on bad venue data
- **CLI:** env vars for secrets; clap `env =` is fine; never default real keys
- **Multi-tenant:** N/A — single operator; still avoid world-readable `.env` in shared hosts (mention in runbook if relevant)

## Mainnet gate

Require `docs/MAINNET_GATE.md` checklist; no “go live” without user explicit request and evidence.

## Report format

```markdown
## Security MM
**Verdict:** OK | ISSUES

- Secrets in repo: …
- Logging: …
- Input validation: …
- Kill / cancel path: …
- Required fixes: …
```

## Exit

Verdict with concrete file:line issues or explicit OK for the diff scope.
