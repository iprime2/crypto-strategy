# Forward pre-registration (ADA 200/400 at fair ± 6 bps)

Written 2026-10-30 02:26Z, before any shadow data received after 2026-10-30T02:03:00Z has been simulated. Copied from the memo's last section.

## Next experiment (one config, metric, success, stop)

- **Config:** quote 200, cap 400 (2 orders), fair ± 6 bps. In the live env, that is `MM_FIXED_HALF_SPREAD_BPS=6` and `MM_MAX_INVENTORY_ADAUSDT=400`. No code change.
- **Test:** forward and out of sample, on shadow data received after 2026-10-30T02:03:00Z. It re-prices around the logged fair, so it needs no orders and no shadow restart.
- **Metric:** PnL per $ on the calibrated leg (1000 ms, touch, Scalper Offer 15 min fifo).
- **Pass:**
  - The calibrated leg is ≥ +2.4 bp/$ (+1.0, plus the 1.4 by which this leg overstated the real run).
  - 1000 ms strict is ≥ 0.
  - At least 300 fills over at least 24 h.
  - At least one hour above 2× median vol in the window, so a calm-only stretch cannot pass. If none comes, extend up to 72 h.
- **Stop:** a fail at 72 h keeps ADA off. The next knob is then a volatility pause: stop adding when the trailing 15-minute realized vol exceeds a multiple of its trailing median, defined on past data only.
- **A live restart also needs:**
  - The cap-breach fix merged and demo-QA'd. Proposed fix: a quote found `closed` counts its uncounted contracts as filled until the next position read, and a private-feed reconnect blocks the adding side until fills are caught up.
  - The hourly check reading the venue position against the cap.
  - A calm market: 2 h without an abort trip, and ADA hourly vol back under 2× median. At 01:00Z it was 2.7×.
  - The owner's word.
- **Earliest restart:** 31 Oct about 02:30Z (08:00 IST), if all of the above hold.
