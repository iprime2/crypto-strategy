# GoDark vanilla MM — full export (2026-09-21)

Complete ops bundle from **`~/scripts/mms`** and **`vanilla-mm-rust`**, copied for CEX strategy work in `crypto-strategy`. Secrets are **not** included.

## Layout

```
godark-mm-bot/
├── README.md                          ← this file
├── docs/
│   └── godark-mm-strategy-cex-porting-guide.md   ← human-facing architecture + porting checklist
└── mms/
    ├── vanilla-mm-rust/               ← production quote bot (Rust)
    │   └── src/
    │       ├── strategy.rs            ← quote math (AS, reservation, markout inputs)
    │       ├── main.rs                ← GoDark loop, fills, markout guard, MM_METRICS
    │       ├── lib.rs                 ← fair price, κ tape, economics, REST helpers
    │       └── bin/mm-admin.rs
    ├── bot/
    │   └── pricing.py                 ← legacy simplified quotes (not used by Rust binary)
    ├── mm-eval.py                     ← log-driven tuning → artifacts/*/mm-tuning.env
    ├── mm-dashboard.py                ← HTML metrics dashboard
    ├── mm-tuning.env                  ← seed defaults
    ├── mm-tuning-testnet.env          ← testnet runtime overlay (not eval-overwritten)
    ├── mm-tuning-devnet.env           ← devnet guardrails overlay
    ├── mm-*.sh                        ← daemons, creds, env loaders
    └── artifacts/                     ← logs, economics JSON, eval reports, archived runs
        ├── mm-tuning.env              ← testnet eval output
        └── devnet/
            └── mm-tuning.env          ← devnet eval output
```

**Excluded from copy (by design):** `vanilla-mm-rust/target/`, `.venv/`, `__pycache__/`.

## File index (strategy-critical)

| Path | Role |
|------|------|
| `docs/godark-mm-strategy-cex-porting-guide.md` | Narrative spec, env reference, iteration history |
| `mms/vanilla-mm-rust/src/strategy.rs` | **Source of truth** for bid/ask math |
| `mms/vanilla-mm-rust/src/main.rs` | Control loop, markout spawn, κ/vol wiring |
| `mms/vanilla-mm-rust/src/lib.rs` | `resolve_fair_price`, external BBO/trades, fill economics |
| `mms/mm-eval.py` | Auto-tune with markout guards |
| `mms/mm_markout.py` | Parse horizon markout lines for eval/dashboard |
| `mms/mm-tuning*.env` | Defaults + overlays + eval outputs |
| `mms/bot/pricing.py` | Historical Python prototype — compare only |

## Analysis in this repo

- **`../06-godark-vanilla-mm-strategy-analysis.md`** — code-grounded breakdown, reuse table, merge list into `STRATEGY.md`
- **`../../STRATEGY.md`** — target CEX design

## Source

Copied from Windows export folder `godark-mm-export-20260921` (WSL: `/mnt/c/Users/kalwa/Downloads/godark-mm-export-20260921`) via:

```bash
rsync -a --exclude 'target' --exclude '.venv' --exclude '__pycache__' \
  /mnt/c/Users/kalwa/Downloads/godark-mm-export-20260921/ \
  /home/iprime2/projects/crypto-strategy/resource/godark-mm-bot/
```

Rebuild Rust locally: `cd mms/vanilla-mm-rust && cargo build --release` (requires GoDark SDK deps from upstream).
