# GoDark Vanilla MM — Agent Handoff (devnet)

Copy this entire file into a new Cursor chat on the other machine to continue work.

---

## Agent prompt (paste into Cursor)

```
Continue GoDark vanilla market-making bot work on **devnet**.

### Context
- Goal: post-only two-sided MM on BTC-USDC-PERP via GoDark SDK (HPKE + REST/WS).
- **Proto issue is FIXED** — Rust SDK bindings were regenerated from `gdx-proto` branch `feature/godark-chain-v0` (not `main`).
- **REST place+cancel works** on devnet after regen. Verified: `rest_live_place_then_cancel_by_coid` PASS.
- **Python SDK does NOT work on devnet** for trading — still uses Noise handshake; devnet requires HPKE. Use Rust SDK.

### Auth flow (follow teammate guidance — do not invent values)
1. **HPKE pin** = same as frontend for that host (`VITE_GDX_HPKE_STATIC_PUBKEY` in gdx-web for devnet).
   Devnet pin: `a6807e2f6cd04b54cc19be2fd4faea2a1239f1e2896912d91222678ab54cdd45`
2. **user_uuid** = from connect/auth (`JWT sub` or WS login response). Do not hardcode unless auth omits it.
3. **Order**: connect → HPKE session → encrypt/trade.

### Key paths (on agent VM)
| Item | Path |
|------|------|
| Rust MM bot | `~/scripts/mms/vanilla-mm-rust/` |
| Launcher | `~/scripts/mms/run-vanilla-mm.sh` |
| Auth helper | `~/scripts/mms/godark-resolve-auth.py` |
| Python bot (dry-run / future) | `~/scripts/mms/bot/` |
| gdx meta-repo | `~/gdx` |
| Rust SDK | `~/gdx/gdx-sdk/gdx-rust-sdk` branch `feature/godark-chain-v0` |
| gdx-proto (for regen) | `~/gdx/gdx-proto` branch **`feature/godark-chain-v0`** |
| Secrets | `~/.cursor/secrets.env` (GODARK_DEVNET_* — never commit) |
| Cursor rules | `~/.cursor/rules/godark.mdc`, `godark-mm.mdc` |

### Secrets env vars (devnet)
Fill in `~/.cursor/secrets.env` from `~/scripts/secrets.env.example`:
- `GODARK_ENV=devnet`
- `GODARK_DEVNET_API_KEY_ID`, `GODARK_DEVNET_API_SECRET`, `GODARK_DEVNET_PASSPHRASE`
- `GODARK_DEVNET_REST_URL=https://api.devnet.godark-dex.com`
- `GODARK_DEVNET_EDGE_URL=wss://api.devnet.godark-dex.com`
- `GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY=a6807e2f...` (full 64 hex — see above)
- `GODARK_DEVNET_USER_UUID` — optional fallback only (JWT sub: resolve via helper)
- `GODARK_DEVNET_SYMBOL=BTC-USDC-PERP`

### Setup on new machine
```bash
# 1. Unzip handoff bundle to ~/scripts/mms/
# 2. Clone gdx if missing
git clone https://github.com/gq-godark/gdx.git ~/gdx
cd ~/gdx/gdx-sdk/gdx-rust-sdk && git checkout feature/godark-chain-v0
cd ~/gdx/gdx-proto && git checkout feature/godark-chain-v0

# 3. Apply proto regen patch OR regen fresh:
cd ~/gdx/gdx-sdk/gdx-rust-sdk
GODARK_REGEN_PROTO=1 GDX_PROTO_ROOT=~/gdx/gdx-proto/proto cargo build
# Requires: apt install protobuf-compiler

# 4. Build MM bot
cd ~/scripts/mms/vanilla-mm-rust && cargo build --release

# 5. Auth check
source ~/scripts/source-secrets.sh && export GODARK_ENV=devnet
python3 ~/scripts/mms/godark-resolve-auth.py

# 6. Live REST place test
eval "$(python3 ~/scripts/mms/godark-resolve-auth.py --export)"
export GDX_API_KEY_ID="$GODARK_DEVNET_API_KEY_ID" GDX_API_SECRET="$GODARK_DEVNET_API_SECRET" GDX_PASSPHRASE="$GODARK_DEVNET_PASSPHRASE"
cd ~/gdx/gdx-sdk/gdx-rust-sdk
GDX_LIVE_EDGE=1 cargo test -p godark --test rest_live_integration rest_live_place_then_cancel_by_coid -- --ignored --nocapture
```

### Run MM bot
```bash
bash ~/scripts/mms/run-vanilla-mm.sh
# Stop: pkill -f vanilla-mm-rust
# Log: ~/scripts/mms/vanilla-mm-rust.log
```

### What works
- REST `connect()` + HPKE one-shot place orders on devnet
- `user_uuid` from auth: `be9a29eb-2e42-4704-8948-aaa527457aa7` (example — yours from JWT sub)
- Bid/ask placement at MM_FAIR_OVERRIDE=64000 logged successfully

### Known issues / next tasks
1. **Cancel/replace broken** — `register_client_order_mapping` fails with `REST code=1400 correlation_id required`. Bot stacks orders each loop; cancel-by-coid does not work. Fix in Rust SDK `rest_client.rs` or bot (use non-zero correlation_id in place header / edge mapping API).
2. **order_id=0** in ACK on devnet — orders may still land; investigate proto ACK `order_id` field vs server.
3. **WS mass_quote** — ack times out ~30s on devnet; bot uses REST place instead. Revisit WS once edge stable.
4. **Fair price** — bot uses `MM_FAIR_OVERRIDE`; wire market data (book mid / mark from positions).
5. **Inventory / positions** — REST bot does not yet read positions; add snapshot or WS subscribe.
6. **Python bot** — update when Python SDK gets HPKE on `feature/godark-chain-v0` (currently Noise-only).
7. **Commit SDK proto regen** — uncommitted changes in `gdx-rust-sdk` (see `artifacts/gdx-rust-sdk-proto-regen.patch` in zip). Consider MR to `gq-godark/gdx-rust-sdk`.

### Proto regen command (reference)
```bash
cd ~/gdx/gdx-proto && git checkout feature/godark-chain-v0
cd ~/gdx/gdx-sdk/gdx-rust-sdk
GODARK_REGEN_PROTO=1 GDX_PROTO_ROOT=~/gdx/gdx-proto/proto cargo build
```
`build.rs` includes: `common`, `health`, `edge`, `sequencer` protos (health required on godark-chain-v0 branch).

### Rules to read
- `~/.cursor/rules/godark.mdc` — platform context
- `~/.cursor/rules/godark-mm.mdc` — MM strategy guardrails
- `~/.cursor/rules/vm-ssh-readonly.mdc` — if SSH to VMs

### Branch naming (if committing)
- `sushil/godark-mm-devnet` or `sushil/proto-regen-devnet`
- Do not commit secrets.env
```

---

## Session summary (2026-08-24)

| Milestone | Status |
|-----------|--------|
| Clone gdx + submodules | Done |
| Devnet secrets + auth resolver | Done |
| Proto regen from gdx-proto `feature/godark-chain-v0` | Done (local, uncommitted in gdx-rust-sdk) |
| REST live place+cancel | PASS |
| Rust vanilla MM bot (REST) | Created, places bid/ask |
| WS mass_quote MM | Timeout on devnet |
| Python bot live on devnet | Blocked (Noise vs HPKE) |
| Bot stopped | Yes (`pkill -f vanilla-mm-rust`) |

---

## Files in handoff zip

```
HANDOFF-godark-mm-devnet.md          # this file
godark-resolve-auth.py
run-vanilla-mm.sh
vanilla-mm-rust.log                  # sample run log
vanilla-mm-rust/Cargo.toml
vanilla-mm-rust/Cargo.lock
vanilla-mm-rust/src/main.rs
bot/                                 # Python scaffold (no .venv)
artifacts/gdx-rust-sdk-proto-regen.patch
artifacts/gdx-rust-sdk-build-rs.patch  # if split
```

**Not included (machine-local):** `~/.cursor/secrets.env`, `~/gdx/` full clone, `target/` build dirs.

---

## Transcript reference

Prior chat: agent transcript `dbf0ecc0-1191-47b5-96d1-e50a00e72f97` (if available on same Cursor account).
