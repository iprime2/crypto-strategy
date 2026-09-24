# Vanilla GoDark Market-Making Bot

Post-only two-sided quotes on GoDark testnet using `mass_quote` from the official Python SDK.

**Fair price source:** orderbook mid (`MarketDataClient`). Falls back to position `mark_price` if book feed is unavailable.

## Prerequisites

1. GoDark API credentials from onboarding (testnet).
2. Python SDK at `~/gdx/gdx-sdk/gdx-python-sdk` (cloned).
3. Secrets in `~/.cursor/secrets.env` or `bot/.env`.

## Setup

```bash
# Load agent secrets (preferred)
source ~/scripts/source-secrets.sh

cd ~/scripts/mms/bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: copy local overrides
cp .env.example .env
```

### Required env vars (SDK names)

| Variable | Purpose |
|----------|---------|
| `GODARK_API_KEY_ID` | API key id (`gdk_...`) |
| `GODARK_API_SECRET` | API secret |
| `GODARK_PASSPHRASE` | API passphrase |
| `GODARK_EDGE_URL` | Default `wss://api.godark-dex.com` |
| `GODARK_SYMBOL` | e.g. `BTC-USDC-PERP` |

### Strategy tuning

See `.env.example` for `MM_*` params. Defaults are **wide and conservative**.

## Dry run (no orders)

```bash
source ~/scripts/source-secrets.sh
export MM_DRY_RUN=1
export MM_FAIR_OVERRIDE=68000
python main.py
```

## Live (tiny size)

```bash
source ~/scripts/source-secrets.sh
python main.py
```

## Success criteria (vanilla)

- Resting bid + ask visible via order updates
- Logs: fair, bid, ask, inventory, fills, markouts at +1s/+10s/+60s
- You can judge closed round-trips **after fees** from your fill log

## Notes

- One process, one symbol, one API key.
- Quotes pause on stale fair or large jumps — restart after investigating.
- Do not copy production MM params from org repos.
