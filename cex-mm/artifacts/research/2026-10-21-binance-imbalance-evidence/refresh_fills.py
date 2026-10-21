#!/usr/bin/env python3
"""Read-only: bring a live run's fills.json up to date from Delta (signed GET /v2/fills; key never printed).

  python3 refresh_fills.py LIVE_RUN_DIR [...]
"""
import glob, json, sys
from pathlib import Path

for d in sys.argv[1:]:
    run = Path(d).resolve()
    sys.path.insert(0, str(run.parents[2] / "scripts"))
    import live_vs_shadow as lvs
    import shadow_fill_sim as sim
    span = lvs.live_span(sorted(glob.glob(str(run / "bot*.log*"))), "ADAUSDT")
    path = run / "fills.json"
    cached = json.loads(path.read_text()) if path.exists() else []
    pid, _, _ = lvs.product("ADAUSD")
    new = lvs.fetch_fills(lvs.Delta(lvs.CEX_MM / "quote-bot" / ".env").get, pid, span[0] - 120_000,
                          {str(r.get("id")) for r in cached})
    rows = lvs.merge_fills(cached, new)
    path.write_text(json.dumps(rows))
    inrun = [r for r in rows if span[0] <= lvs.parse_iso_ms(r["created_at"]) <= span[1] + 20_000 and r.get("product_symbol") == "ADAUSD"]
    print(f"{run.name}: {len(cached)} cached + {len(new)} new rows; {len(inrun)} ADAUSD fills inside the run")
