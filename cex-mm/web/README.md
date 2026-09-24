# OEMS web (operator book)

Vite + React + React Router + Tailwind client for the cex-mm OEMS API.

## Run

```bash
cd crypto-strategy/cex-mm/web
npm install
npm run dev
```

Dev server: `http://127.0.0.1:5179`

API base: `VITE_OEMS_URL` or `http://127.0.0.1:8788`

```bash
VITE_OEMS_URL=http://127.0.0.1:8788 npm run dev
```

## Build / typecheck

```bash
npm run typecheck
npm run build
```

## Routes

| Path | Screen |
|------|--------|
| `/` | Overview (latest snapshot + PnL chart) |
| `/positions` | Positions |
| `/orders` | Orders and fills |
| `/reconcile` | Reconcile |
| `/tca` | TCA |
| `/control` | Start / stop / config |

No API keys in the client. Do not point this UI at secrets in `cex-mm/.env`.
