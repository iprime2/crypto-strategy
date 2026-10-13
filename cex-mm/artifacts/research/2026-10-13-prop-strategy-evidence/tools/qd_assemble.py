"""Assemble backtest_results.md: pre-registered plan (kept verbatim) + results with every raw output pasted."""
R = "qd_runs"
def raw(path, strip_cmd=False):
    s = open(path).read()
    if strip_cmd:
        s = "\n".join(l for l in s.splitlines() if not l.startswith("$ "))
    return "```\n" + s.rstrip() + "\n```\n"
plan = open("backtest_results.md").read()
assert "## 0. Pre-registered test plan" in plan
body = []
A = body.append

A("""
## 1. Tools and commands

All tools are in `scratchpad/tools/` (nothing in the repo was touched; `trend_backtest.py` is imported read-only):

| File | What |
|---|---|
| `qd_engine.py` | hourly mark-to-market engine; superset of `trend_hourly.py` / `d3_tests2.hourly_mtm` with the design's knobs (weekly/daily cadence, decision weekday, TV, gross cap, no-trade band, whole contracts, execution lag, decision hour H on H-aligned closes, own-account day stop, kill switch, regime filters, Delta or Breakout cost model, always-long basket, per-position stop). Writes hourly rows `ts, ret, gross, unreal` (unrealized PnL of open positions / equity) and per-coin-day PnL. |
| `prop_sim2.py` | `prop_sim.py` + the grafts: funded de-lever, 0.5 % buffer, re-entry room, chop detector, trailing intraday daily reference, balance-based daily reference. **Also fixes a one-hour offset in the original:** `prop_sim.py` sets the "00:00 equity" after hour 0's return (so it is the 01:00 equity and hour 0 can never trip the daily limit); `prop_sim2.py` sets it before. Cross-check below: with identical bootstrap paths the two differ only through that offset (B0 vs B1: pass 61.1 % vs 61.9 %, EV $5,897 vs $6,201). Every D1/D3 prop figure in the designs was produced with the original. |
| `qd_t0.py`, `qd_t1_t3.py` + `qd_t3b.py`, `qd_t4.sh`, `qd_t5.py`, `qd_t5c.py`, `qd_t6.py`, `qd_t6g.py`, `qd_gapfill.py`, `qd_assemble.py` | the test scripts; raw outputs in `scratchpad/qd_runs/T*.txt`; hourly series in `qd_runs/hourly_*.csv` |

Commands (all run from `scratchpad/`):
```
python3 tools/qd_t0.py                       > qd_runs/T0_reproduction.txt
python3 tools/qd_t1_t3.py                    > qd_runs/T1_T3_output.txt      # crashed in T3d on an archive gap (see T7 #4); T1-T3c kept as T1_T3a_output.txt
python3 tools/qd_t3b.py                      > qd_runs/T3b_output.txt        # T3d-T3m + T6 input after the gap-day fix
python3 tools/qd_engine.py --rebal daily --tv 0.40 --band 0 --max-gross 2.0 --pos-stop 0.03 [--cost-bps 4 --funding none --swap 0.00033] --out ...   # per-position-stop series
bash tools/qd_t4.sh                                                          # 4 parallel groups -> qd_runs/T4_g1..g4_*.txt
python3 /home/user/crypto-strategy/cex-mm/scripts/trend_backtest.py --source delta --cache scratchpad/trend-cache --start 2024-08-10 --end 2026-10-12 --capital 500 1000 2500 5000
python3 tools/qd_t5.py; python3 tools/qd_t5c.py; python3 tools/qd_t6.py; python3 tools/qd_t6g.py; python3 tools/qd_gapfill.py
python3 judge_evidence/sharpe_ci.py qd_runs/hourly_daily_tv40.csv qd_runs/hourly_design_weekly_tv25_band10.csv > qd_runs/T6f_sharpe_ci.txt
```
One engine bug was found and fixed during the run and is disclosed here: the first batch crashed in T3d because XRP and LTC have five missing days in the Binance daily archive (2022-02-26..28 and 2022-04-01..02; the hourly archive is missing them too). The repo loop closes and re-opens the position around a gap at a cost; my engine now carries the last price over the gap. Both treatments give the same Sharpe (T7 #4). Nothing else was changed after seeing results; the two [post hoc] additions (Delta weekday check, kill-probability bootstrap) are labelled.

---

## 2. T0 — engine reproduction (pass)

Both references reproduce to the printed precision: baseline daily TV 0.40 Sharpe 1.25 / max DD −21.9 % / hourly −22.6 % / by-year 53/47/−5/16/47/3/8; D3 R3a weekly Monday TV 0.40 Sharpe 1.12 / −26.3 % / by-year 48.8/57.4/−10.7/22.5/38.1/2.4/1.9. The daily archive close equals the 23:00 hourly bar close on 21,883 of 21,885 pairs (the two exceptions are XRP in January 2020, before the test window).
""")
A(raw(f"{R}/T0_reproduction.txt"))

A("""
---

## 3. T1 + T2 — design vs baseline, Binance 2020-05-01..2026-09-30, with the 2020-05..2023-12 / 2024-01..2026-09 split

Summary (full sample; Sharpe with 0 % cash; DD on daily closes / on hourly marks):

| Line | CAGR | Vol | Sharpe | Max DD daily / hourly | Fees/yr | Funding/yr | Trades/yr | Worst day | Worst 7 d | 2020-05..2023-12 CAGR / Sharpe / DD | 2024-01..2026-09 CAGR / Sharpe / DD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Baseline** repo rule, daily, TV 0.40 | +24.2 % | 18.7 % | **1.25** | −21.9 / −22.6 % | 1.14 % | +3.43 % | 1,773 | −7.31 % | −9.5 % | +28.1 % / 1.36 / −21.9 % | +19.1 % / 1.09 / −17.0 % |
| **Design** weekly Mon 00:00 UTC, TV 0.25, 10 % band | +14.1 % | 12.4 % | **1.12** | −16.9 / −17.7 % | 0.25 % | +2.11 % | 192 | −4.88 % | −7.4 % | +17.8 % / 1.29 / −16.9 % | **+9.2 % / 0.86 / −9.3 %** |
| Design without the band | +14.1 % | 12.4 % | 1.12 | −17.0 / −17.8 % | 0.26 % | +2.10 % | 278 | −5.01 % | −7.5 % | +18.0 % / 1.30 | +9.1 % / 0.85 |
| Daily, TV 0.25, no band (cadence isolated) | +15.0 % | 11.7 % | 1.25 | −13.9 / −14.3 % | 0.72 % | +2.14 % | 1,773 | −4.57 % | −6.0 % | +17.3 % / 1.36 | +12.0 % / 1.09 |
| Daily, TV 0.25, 10 % band (the documented upgrade path) | +15.0 % | 11.7 % | 1.25 | −14.1 / −14.5 % | 0.67 % | +2.15 % | 538 | −4.54 % | −5.9 % | +17.1 % / 1.35 | +12.2 % / 1.11 |
| Weekly Mon, TV 0.40 (D3 R3a) | +22.5 % | 19.8 % | 1.12 | −26.3 / −27.4 % | 0.41 % | +3.33 % | 278 | −8.04 % | −12.1 % | +29.2 % / 1.30 | +14.2 % / 0.85 |

By year, design line: 2020 (May–Dec) +29.1 %, 2021 +33.7 %, **2022 −6.9 %**, 2023 +13.6 %, 2024 +23.4 %, **2025 +2.0 %, 2026 (Jan–Sep) +1.3 %**. Baseline: +53.3 / +47.0 / −5.0 / +15.9 / +46.6 / +2.7 / +7.5 %.

What it says: the weekly cadence costs 0.13 of Sharpe against the daily rule at the same vol (1.12 vs 1.25), 3.0 pp of hourly max drawdown (−17.7 vs −14.5 %) and 1.5 pp of worst week, in exchange for 346 fewer orders a year and 0.42 pp/yr of fees. In the second half (2024-01..2026-09) the gap widens: 0.86 vs 1.11, CAGR +9.2 % vs +12.2 %. The design's gross cap of 1.0x never binds (max gross 0.56x), so the on-venue leverage with 30 % of capital on Delta peaks at about 1.9x, inside the 2x graft. Funding at +2.1 %/yr is eight times the fee line and is the strategy's real running cost.
""")
A(raw(f"{R}/T1_T3a_output.txt").replace("=== T3a.", "=== T3a.") )

A("""
---

## 4. T3 — sensitivity of every parameter the design introduces or changes (all settings shown; weekly Monday 00:00 UTC, TV 0.25, 10 % band unless stated)

| Knob | Settings → full-sample Sharpe (max DD daily; 2024-26 Sharpe) | Reading |
|---|---|---|
| **T3a target vol** | 0.15 → 1.12 (−10.5 %; 0.87) · 0.20 → 1.12 (−13.7 %; 0.86) · **0.25 → 1.12 (−16.9 %; 0.86)** · 0.30 → 1.13 (−20.2 %; 0.85) · 0.40 → 1.13 (−26.2 %; 0.85) | linear as expected; worst day −3.0 / −3.9 / −4.9 / −5.9 / −7.8 %. The −20 % kill was **not** reached in-sample at TV 0.25 (hourly DD −17.7 %) and **is** reached at TV 0.30 (−21.1 %). |
| **T3b cadence / weekday** | daily 1.25 (−14.1 %; 1.11) · Mon-candle 1.26 (−16.9 %; 1.04) · Tue 1.18 (−13.2 %; 1.00) · Wed 1.34 (−11.2 %; 1.04) · Thu 1.31 (−9.8 %; 1.12) · Fri 1.23 (−16.3 %; 1.20) · Sat 1.16 (−17.5 %; 1.06) · **Sun-candle = design 1.12 (−16.9 %; 0.86)** | the design's weekday is the **worst of seven** on the full sample and in 2024-26; 7-weekday mean 1.23. 2022 ranges from −0.3 % (Thu) to −7.1 % (Mon-candle). |
| **T3c no-trade band** | 0 % → 1.12, 278 trades/yr · 5 % → 1.12, 221 · **10 % → 1.12, 192** · 20 % → 1.11, 163 | zero evidence cost, as the graft claimed. Daily TV 0.40 with the 10 % band: 1.25, 531 trades/yr (D2's number reproduced). |
| **T3d lookbacks** | **(20,60,120) → 1.12** · (10,30,60) → 1.08 (−15.6 %) · (50,100,200) → 0.95 (−21.7 %) · (20,) → 0.90 (−22.2 %) · (60,) → 0.92 (−28.0 %) · (120,) → 1.21 (−16.7 %, 2025 −3.1 %) | the pre-registered ensemble is second of six; the single 120-day lookback scores higher but lost in 2025, and choosing it would be selection. |
| **T3e vol window** | 30 → 1.16 · **60 → 1.12** · 90 → 1.08 | monotone, small. |
| **T3f universe** | **9 coins → 1.12 (−16.9 %)** · BTC only → 0.85 (−18.0 %; 2021 +2.9 %, 2025 −4.5 %) · BTC+ETH → 0.95 (−17.5 %) · top-5 → 1.27 (−13.1 %) | the 9-coin choice holds against fewer coins; top-5 scores higher but is post hoc and only 5 names. |
| **T3g gross cap** | 1.0 vs 2.0 → identical (max gross 0.56x) | never binds. |
| **T3h kill switch** | none → 1.12 · −15 % weekly → 1.13, fires once (2022-11-14 at −16.0 %), CAGR −0.1 pp · **−20 % weekly (design) → never fires** · −25 %, −30 %, −20 % daily-check → never fire. At native TV 0.40: −20 % fires 2022-09-19 (−20.7 %), −15 % fires 2021-05-24 and 2022-11-14 | at TV 0.25 the kill is 1.13x the backtest hourly DD; see T6g for how often it fires on luck. |
| **T3i own-account day stop** (both legs charged, positions resumed next 00:00) | none → 1.12 (−16.9 %, worst day −4.88 %) · 1.5 % → 1.05 (−14.6 %, −3.32 %, 12.9 trips/yr) · 2 % → 1.02 (−14.9 %, −3.32 %, 7.5/yr) · 3 % → 0.99 (−18.4 %, −5.71 %, 2.3/yr) | costs 0.07–0.13 Sharpe, buys 2 pp of DD and 1.5 pp of worst day at 1.5–2 %. D3's R3a found 2 % → Sharpe 1.20 because it charged only the flatten leg and not the re-entry. |
| **T3j regime filters** (design: none) | none → 1.12 · BTC < 200-day → 1.18 (−14.4 %; 2022 +0.1 %, 2021 +30.5 %) · BTC 30-day vol > 70 % → 1.02 · > 90 % → 1.00 | the 200-day filter helps this weekly line (it was neutral on the daily TV 0.40 line); vol filters hurt. Not adopted. |
| **T3k late execution** (same Monday 00:00 signal) | +0 h → 1.12 · +4 h → 1.09 (−18.6 %) · +8 h → 1.11 · +12 h → 1.09 · +24 h → 1.15 (−16.6 %) | within noise; the 09:30 IST / 04:00 UTC fallback and the next-day fallback both cost nothing measurable. |
| **T3k decision hour H** (signal and execution on H-aligned closes) | **00 → 1.12** · 04 → 1.21 · 08 → 1.24 · 12 → 1.16 · 16 → 1.18 · 20 → 1.32 | the design's 00:00 UTC is the lowest of six hours on the weekly series (D2 found 1.22–1.33 at daily cadence). Dispersion 0.20 of Sharpe is path luck of the same size as the weekday luck. |
| **T3l slippage** | 2 bps → 1.12 · 5 → 1.11 · 10 → 1.10 | immaterial at 0.6x turnover/yr. |
| **T3m cost model** (daily native series) | Delta costs (5.31+2 bps, Binance funding) → CAGR +24.2 %, Sharpe 1.25 · Breakout (4 bps, no funding, 0.033 %/day swap on gross) → +26.1 %, 1.33 (swap 2.38 %/yr, fees 0.63 %) | the Delta-cost series is ~1.5–2 pp/yr conservative for the prop simulation; both are run in T4. |
""")
A(raw(f"{R}/T3b_output.txt"))

A("""
---

## 5. T4 — prop-challenge simulation

**Series.** S_d = daily rule, native TV 0.40, Delta costs (`hourly_daily_tv40.csv`, hourly Sharpe 1.21); S_b = same with Breakout costs (`hourly_daily_tv40_breakout.csv`, 1.29); S_w = D3's weekly Monday series (`hourly_weekly_tv40.csv`, 1.10); `_2025on` = 2025-01-01..2026-09-30 subsets (638 days). k = 0.5 scales every hourly return by 0.5 (TV 0.20, ~10 % realized vol), the design's prop setting. $100k account, $999 fee, 80 % split (Breakout) / $599, 70 % (HyroTrader); funded phase 12 months, 80 % of profit withdrawn every 30 days; 3,000 bootstrap paths (stationary block, mean 20 d, day-aligned, seed 7) and `--historical` (1,979 real 365-day windows).

**Simulator assumptions that matter.** (i) The daily limit is measured against equity at 00:00 UTC (prop_sim2; the original prop_sim used the 01:00 equity, cross-checked in B0 vs B1). Breakout's stated rule [UNVERIFIED] is the 00:30 UTC *balance excluding open positions*: G6 approximates it as 00:00 equity minus the unrealized PnL of open positions. Because a trend follower mostly carries unrealized gains, that reference is usually *below* equity, so the day stop trips less often (5.3 → 0.8 trips/yr) and pass rates are unchanged, while an account carrying a floating loss has less room than it thinks (funded survival 63 → 59 %). (ii) Hourly granularity: a breach between hourly marks is missed; `debug_breach.txt` found three hours in six years that jump from above −1.5 % to below −3 %. (iii) The day stop flattens for the rest of the UTC day at 7.31 bps on gross and the series' positions are resumed at the next 00:00: a daily operator. (iv) The funded max-DD floor stays at 94 % of the initial balance after payouts. (v) The HyroTrader fee/swap schedule is unknown, so S_d (Delta costs) is used for it.

### 5.1 Breakout Classic 10 % / 3 % daily / 6 % static, k = 0.5 (design)

| Run | Series | Day stop | Pass | Pass ≤180 d | Daily breach | Max-DD bust | Open at 365 d | Median / p90 days | Funded 12-m survival | E[payout] / acct | EV per challenge | Trips/yr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 bootstrap | S_d | 1.5 % | **61.9 %** | 38.7 % | 0.0 % | 14.9 % | 23.2 % | 141 / 297 | 62.0 % | 11.6 % | **+$6,201** | 5.4 |
| B0 same, original prop_sim (01:00 ref) | S_d | 1.5 % | 61.1 % | 38.6 % | 0.0 % | 15.6 % | 23.2 % | 139 / 296 | 60.0 % | 11.3 % | +$5,897 | — |
| B2 historical windows | S_d | 1.5 % | 54.6 % | 44.2 % | 0.0 % | 3.2 % | 42.2 % | 86 / 247 | 61.1 % | 11.1 % | +$5,060 | 4.0 |
| B3 no day stop (control) | S_d | none | 52.8 % | 35.2 % | **18.2 %** | 12.2 % | 16.9 % | 131 / 293 | 30.8 % | 7.7 % | +$3,078 | 0 |
| B4 day stop 2 % | S_d | 2.0 % | 58.7 % | 37.0 % | 4.0 % | 15.8 % | 21.5 % | 139 / 296 | 48.1 % | 9.9 % | +$4,818 | 2.6 |
| B5 2025-01..2026-09 bootstrap | S_d | 1.5 % | **18.6 %** | 7.7 % | 0.0 % | 24.9 % | 56.6 % | 203 / 331 | 52.2 % | 4.3 % | **−$202** | 3.0 |
| B6 bootstrap, Breakout costs | S_b | 1.5 % | 63.3 % | 39.9 % | 0.0 % | 14.8 % | 22.0 % | 139 / 296 | 63.1 % | 12.2 % | +$6,725 | 5.3 |
| B7 historical, Breakout costs | S_b | 1.5 % | 52.7 % | 43.9 % | 0.0 % | 3.3 % | 44.1 % | 82 / 214 | 62.2 % | 11.7 % | +$5,135 | 4.0 |
| B8 2025-01..2026-09, Breakout costs | S_b | 1.5 % | 17.1 % | 6.7 % | 0.0 % | 27.1 % | 55.8 % | 206 / 331 | 49.9 % | 4.1 % | −$291 | 3.0 |
| B9 **$25k account, $275 fee** | S_b | 1.5 % | 63.3 % | 39.9 % | 0.0 % | 14.8 % | 22.0 % | 139 / 296 | 63.1 % | 12.2 % | **+$1,656** (≈ −$98 in the 2025-26 regime: 0.171 × 4.14 % × 25,000 − 275) | 5.3 |
| W1 D3's weekly series, bootstrap | S_w | 1.5 % | 59.2 % | 36.8 % | 0.0 % | 18.3 % | 22.4 % | 141 / 298 | 55.2 % | 10.7 % | +$5,352 | 6.4 |
| W2 weekly, historical | S_w | 1.5 % | 50.2 % | 38.9 % | 0.0 % | 4.3 % | 45.5 % | 84 / 263 | 53.8 % | 10.2 % | +$4,135 | 4.9 |
| W3 weekly, 2025-01..2026-09 | S_w | 1.5 % | **9.2 %** | 2.7 % | 0.0 % | 28.3 % | 62.5 % | 225 / 334 | 47.9 % | 3.5 % | **−$680** | 3.7 |
| P2 **per-position stop fallback** (3 % of native gross = 1.5 % at k 0.5), no portfolio stop | S_b | none | 61.1 % | 38.0 % | 0.0 % | 14.4 % | 24.5 % | 141 / 295 | 62.6 % | 11.5 % | +$5,991 | — |
| P3 same, historical | S_b | none | 52.3 % | 43.3 % | 0.0 % | 3.2 % | 44.5 % | 84 / 221 | 62.2 % | 11.0 % | +$4,737 | — |

k = 0.35 and 0.75 are in the raw output for every run (0.75 passes slightly more often but busts 23 % of evaluations and 76 % of funded accounts within a year; 0.35 leaves 45–55 % of paths unresolved after a year).

Reading: the 1.5 % day stop is what makes the 3 % daily limit survivable (daily breaches 18 % → 0 %); daily cadence on the prop account is worth about +$850 of EV over the weekly series in the full sample and halves the loss in the 2025-26 regime (−$202 vs −$680 at $100k). The **per-position resting-stop fallback does the same job without a watcher**: 0 % daily breaches, EV $5,991 vs $6,725 with the portfolio stop (its cost is 90 stops a year, 0.1 of Sharpe on the underlying series: 1.25 → 1.13 at native). In every 2025-26 bootstrap the challenge is negative-EV and 56–62 % of paths are still open after a year.

### 5.2 Grafts, one at a time and together (Breakout, S_b, k = 0.5, day stop 1.5 %, bootstrap unless stated)

| Graft | Pass | Max-DD bust | Open | Funded survival | E[payout] | EV | Trips/yr | What actually changed |
|---|---|---|---|---|---|---|---|---|
| none (B6) | 63.3 % | 14.8 % | 22.0 % | 63.1 % | 12.21 % | +$6,725 | 5.3 | reference |
| G1 funded de-lever clip((eq−0.94)/0.06, 0.33, 1) | 63.3 % | 14.8 % | 22.0 % | **92.8 %** | 11.06 % | +$6,000 | 5.3 | survival +30 pp for −9 % of payout (D1's claim reproduced: ~11 % of EV) |
| G2 de-lever in the evaluation too | 60.9 % | 2.5 % | 36.2 % | 92.8 % | 11.06 % | +$5,738 | 3.9 | busts become unresolved paths |
| G3 0.5 % buffer (stop at max(day0·0.985, 0.945); flat when room < 0.5 %) | 62.2 % | **1.2 %** | **36.6 %** | 98.0 % | 11.72 % | +$6,287 | 4.7 | **busts are relabelled as frozen accounts**: the 13.6 pp of evaluations that no longer bust sit flat near the floor; in the funded phase 35 pp of "survivors" are frozen and pay nothing further |
| G4 re-entry only if room ≥ 1.5 %, else flat to the next 7-day boundary | 63.0 % | 14.6 % | 22.3 % | 62.6 % | 12.11 % | +$6,636 | 5.3 | no measurable effect |
| G5 chop detector 3 trips / 10 d → k/2 for 30 d | 62.9 % | 14.6 % | 22.5 % | 63.3 % | 12.03 % | +$6,565 | 5.1 | fires rarely; no measurable effect |
| G6 balance-based daily reference (eq − unrealized) | 63.3 % | 16.1 % | 20.6 % | 58.6 % | 12.05 % | +$6,632 | **0.8** | fewer stop trips (reference usually below equity); slightly worse funded survival |
| G7 all of the above together | 62.3 % | 1.8 % | 35.9 % | 100 % | 11.23 % | +$6,000 | 1.0 | historical windows (G8): pass 53.8 %, EV +$4,810; 2025-26 (G9): pass 17.3 %, EV **−$404**; $25k (G10): EV **+$1,475** |
| G11 all grafts without the balance reference | 61.9 % | 1.1 % | 37.0 % | 99.2 % | 10.86 % | +$5,726 | 4.6 | same picture |

The honest summary of the grafts: the funded-phase de-lever is the one that changes money (it trades ~10 % of expected payout for a much lower chance of losing the account inside 12 months); the buffer, re-entry and chop rules change labels or nothing; the balance-based reference changes how often the day stop trips, not the outcome. None of them rescues the 2025-26 regime.

### 5.3 HyroTrader 10 % / 4 % daily / 6 % max loss, k = 0.5 (S_d, $599, 70 % split)

| Run | Day stop | Pass | Daily breach | Max-DD bust | Open | Funded survival | E[payout] | EV |
|---|---|---|---|---|---|---|---|---|
| H1 static max loss, bootstrap | 2.0 % | 61.0 % | 0.0 % | 16.4 % | 22.6 % | 66.1 % | 10.0 % | +$5,502 |
| H2 static, day stop 1.5 % | 1.5 % | 61.9 % | 0.0 % | 14.9 % | 23.2 % | 70.0 % | 10.5 % | +$5,888 |
| H3 static, historical | 2.0 % | 54.2 % | 0.0 % | 2.8 % | 43.0 % | 65.2 % | 9.6 % | +$4,614 |
| H4 **trailing** max loss (if the sources that say trailing are right) | 2.0 % | 51.4 % | 0.0 % | **40.8 %** | 7.8 % | **4.2 %** | 4.7 % | +$1,822 |
| H5 static, **trailing intraday daily reference** (graft) | 2.0 % | 57.8 % | 4.0 % | 16.1 % | 22.1 % | 54.1 % | 8.7 % | +$4,440 |
| H6 static, 2025-01..2026-09 | 2.0 % | 18.1 % | 0.0 % | 23.8 % | 58.1 % | 60.1 % | 3.9 % | +$97 |
| H7 static, no day stop (control) | none | 58.7 % | 9.7 % | 12.7 % | 18.9 % | 49.8 % | 8.9 % | +$4,591 |
| H8 static, all grafts + trailing daily ref | 2.0 % | 57.0 % | 3.9 % | 1.3 % | 37.7 % | 87.8 % | 8.1 % | +$4,023 |

Whether the 6 % is static or trailing decides everything (EV $5,502 vs $1,822; survival 66 % vs 4 %); if the daily limit trails intraday, a 2 % day stop no longer keeps breaches at zero (4.0 %) and the stop should be tightened to 1.5 %. These rules are [UNVERIFIED].

Raw outputs:
""")
A(raw(f"{R}/T4_posstop_series.txt"))
for f in ("T4_g1_breakout_delta.txt", "T4_g2_breakout_bkcost.txt", "T4_g3_weekly_hyro.txt", "T4_g4_grafts.txt"):
    A(raw(f"{R}/{f}", strip_cmd=True))

A("""
---

## 6. T5 — small-account rounding on Delta India (2024-08-10..2026-10-12)

### 6.1 The repo command as given (read-only; it used the cached Delta candles and fetched only the public `/v2/products` contract values)
""")
A(raw(f"{R}/T5_repo_rounding.txt"))
A("""
Daily cadence, TV 0.40: unrounded Sharpe 0.99, CAGR +16.5 %, max DD −14.1 %; whole contracts $500 → 1.09, $1,000 → 0.93, $2,500 → 0.97, $5,000 → 1.00. Rounding noise is ±0.08 of Sharpe and non-monotone in capital, so a $500 account is not worse than a $5,000 one on this window.

### 6.2 The design on Delta prices (weekly Monday 00:00 UTC decision, TV 0.25, 10 % band, whole contracts, memo contract values), plus the weekday check that explains the gap to D3's figure
""")
A(raw(f"{R}/T5b_delta_weekly_rounded.txt"))
A(raw(f"{R}/T5c_delta_weekday_check.txt"))
A("""
Two findings. **(a) Rounding is noise from $500 up** at the design's settings: Sharpe 0.72 / 0.81 / 0.70 / 0.69 at $500 / $1,000 / $2,500 / $5,000 vs 0.70 unrounded; the 10 % band removes 7–28 orders a year with no change in Sharpe; at $500 average gross is 0.09x (vs 0.12x) because BTC (~$82/contract) and BNB (~$73) round to zero most weeks. **(b) D3's venue-native number is for the wrong weekday.** D3's R3c/R2b "offset 3" counts rebalance days from the first trading day: on the Binance window (2020-05-01, a Friday) that lands on the Sunday candle (Monday 00:00 UTC decision, the design's slot); on the Delta window (2024-08-10, a Saturday) it lands on the **Monday candle (Tuesday 00:00 UTC decision)**. The Monday-candle line reproduces D3's Delta figures exactly (TV 0.40: CAGR +16.7 %, Sharpe 1.01, DD −13.0 %; TV 0.25: 1.01); the design's actual slot on Delta is **Sharpe 0.69–0.70, CAGR +7.0 % (TV 0.25) / +10.6 % (TV 0.40), max DD −9.1 % / −14.3 %**, the weakest of the seven weekdays there as well (others 0.92–1.15). At $1,000 and TV 0.25 the design made +8.3 %/yr on Delta (+14.5 % in Aug–Dec 2024, +4.5 % in 2025, −0.6 % in 2026 to Oct 12), not the +11.3 % / Sharpe 1.06 D3 quotes.

---

## 7. T6 — the judges' extra checks

""")
A(raw(f"{R}/T6_extra_checks.txt"))
A("""
**T6a edge-decay null (D2 graft).** The vol-scaled always-long 9-coin basket at the same TV, cadence and costs has Sharpe 0.99 full-sample (vol 23 %, max DD −37 %: at TV 0.25 the always-on basket realizes twice the vol of the long/flat rule because the nine coins are highly correlated). On a rolling 24-month basis the rule's Sharpe is **below the basket's on 59 % of days since 2022-04**, including every quarter-end from 2023-06 to 2025-09, i.e. through 2024 when the rule made +23.4 %. The kill as grafted would have stopped the strategy for two and a half years and missed its best recent year. The rule's advantage over the basket is drawdown (−17 % vs −37 %) and 2022 (−6.9 % vs −19.1 %), which a Sharpe-only comparison cannot see. D3's original criterion (24-month return ≤ 0 while BTC's 24-month return > 0) fires on 1 day in 1,615. Neither is a usable kill as written.

**T6b tax split.** On a per-coin-day basis (every day's PnL a separate taxable event) the design's gross gains are 17–127 %/yr of equity against gross losses of 18–97 %, and a 30 % tax on gains with no loss set-off makes **every year negative after tax** (−1.6 % to −15.4 %). On a per-segment basis (PnL realized when a position is changed, which is how a weekly operator's fills look) gains are 4–58 %/yr and losses 6–27 %: after tax 2020 +14.2 %, 2021 +13.3 %, 2022 −7.9 %, 2023 +5.2 %, 2024 +9.4 %, 2025 −2.7 %, 2026 −0.8 %, roughly half the pre-tax result in good years and worse than flat in flat years. Which basis applies is the open CA question; both are below an Indian FD over 2022-26.

**T6c inactivity.** Flat 16 % of days; longest flat streaks 105 d (2022-04-11..07-24), 70 d (2022-01..03), 49 d (2026-06..07), 42 d (2026-03..04); four gaps of more than 30 days between any order. If Breakout has a 30-day inactivity rule [UNVERIFIED], the weekly design would have tripped it four times in six years.

**T6d plumbing kill.** Modelled cost per 30 days is 0.19 % of equity (fees 0.25 %/yr + funding 2.11 %/yr); the 2x threshold is 0.39 % = $3.88 on $1,000, which is 0.11 of one month's standard deviation of the strategy's own return (3.6 %) and of the same size as whole-contract rounding noise at $1,000, so the 30-day tracking kill cannot be measured at $1,000 and needs to be stated in dollars per order (e.g. fills more than 2 × 7.31 bps from the decision price) rather than as equity divergence.

**T6e the 26-week gate.** Rolling 26-week Sharpe of the design line is below zero in 46 % of windows and has a standard deviation of 1.78 across windows; rolling 12-month Sharpe is below 0.5 in 46 % of days and below 0 in 33 %. The live gate measures adherence, not edge.

**T6f Sharpe sampling error** (re-run of `judge_evidence/sharpe_ci.py` on my series):
""")
A(raw(f"{R}/T6f_sharpe_ci.txt"))
A("""
Design line: full-sample Sharpe 1.13, Lo SE 0.50, t = 2.2, block-bootstrap 95 % CI [0.30, 1.92]; 2022-01..2026-09 0.67, CI [−0.28, 1.58]; 2025-01..2026-09 0.26, CI [−1.06, 1.36]; 2020-05..2021-12 2.02. Excess kurtosis 14–15.

**T6g [post hoc] how often the −20 % kill fires on path luck** (block bootstrap of the design's daily returns, 4,000 paths; mean shifted to the design's own forward Sharpe range):
""")
A(raw(f"{R}/T6g_kill_bootstrap.txt"))
A("""
At the design's forward assumption of Sharpe 0.5–0.9 the −20 % kill fires within two years on 11–18 % of paths and within three years on 21–32 %; the −15 % level fires on 34–47 % within two years. At Sharpe 0 (no edge) the kill fires within two years on 45 % of paths and the 3-year total return is negative on 54 %: the kill is a weak detector of a dead edge (it does not fire on most no-edge paths for two years) and a frequent false alarm on a live one.

**[post hoc] archive-gap sensitivity** (the engine crash in T3d):
""")
A(raw(f"{R}/T7_gapfill_posthoc.txt"))

A("""
---

## 8. T7 — red flags: what makes the design's claimed numbers look optimistic

1. **Sample dependence is severe.** Design-line Sharpe 2.02 in 2020-05..2021-12, 1.29 in 2020-05..2023-12, 0.86 in 2024-01..2026-09, 0.67 in 2022-01..2026-09, 0.26 in 2025-01..2026-09; the post-2021 confidence intervals include zero. The money table at TV 0.25 on $1,000 is +$141/yr full-sample but +$92/yr in 2024-26, +$20 in 2025 and +$13 in 2026 to September (Binance); on Delta at the design's weekday +$70–83/yr, with 2026 to date −0.6 % to −1.9 %.
2. **The design sits at the bottom of two path-luck distributions it did not choose.** Its weekday (Sunday candle / Monday 00:00 UTC) is the worst of seven on Binance 2020-26 (1.12 vs 1.16–1.34), the worst in 2024-26 (0.86 vs 1.00–1.20) and the worst of seven on Delta 2024-26 (0.69 vs 0.92–1.15); its decision hour (00:00 UTC) is the lowest of six (1.12 vs 1.16–1.32). Each of these is a Sharpe spread of ~0.2 that a single realized path carries in full. D3 reports the weekday honestly for Binance but not for Delta.
3. **D3's "only venue-native number" is for a different weekday.** The anchoring of "offset 3" to the first trading day gives the Sunday candle on the Binance window and the Monday candle on the Delta window, so D3's Delta figures (Sharpe 1.01 weekly / 1.06 and +11.3 % at $1,000) describe a Tuesday-00:00-UTC decision. The design as specified scores 0.70 / +7.0 % / −9.1 % on Delta (unrounded) and 0.81 / +8.3 % at $1,000.
4. **Archive quirk, also in the pre-registered memo.** XRP and LTC are missing five daily closes (2022-02-26..28, 2022-04-01..02) in both the daily and hourly Binance archives; `target_weights` therefore excludes both coins for 120 days after each gap (most of Feb–Jul 2022). Carrying the previous close over the gaps changes nothing material (Sharpe unchanged, 2022 −0.1 pp), but the exclusion is undocumented and 2022 is the regime the design uses to argue it sits out bear markets.
5. **Date coverage.** Binance ends 2026-09-30 (all "2026" figures are nine months); Delta runs to 2026-10-12; the eight Delta alts begin 2024-04-10 so the Delta window is 2.2 years, of which the first five months (Aug–Dec 2024, +14.5 to +16 %) are a strong trend that carries the whole Delta result (2025 +1.1 to +4.5 %, 2026 negative).
6. **Weekly cadence has fatter tails than the daily rule at the same vol**: hourly max DD −17.7 % vs −14.5 %, worst 7 days −7.4 % vs −5.9 %, worst day −4.9 % vs −4.5 %, 2022 −6.9 % vs −2.8 %. The −20 % kill is 1.13x the backtest hourly DD at TV 0.25 and would have fired in-sample at TV 0.30; under the design's own forward Sharpe range it fires on 11–18 % of two-year paths (T6g).
7. **Bootstrap validity.** Daily excess kurtosis 12–15; a 20-day block bootstrap mixes regimes and treats 2020-21 as representative; the 2025-26 subsample is 638 days re-sampled into 365-day paths, i.e. one regime describing itself; the historical windows overlap heavily (1,979 windows from 6.4 years). The original `prop_sim.py` measured the daily limit against the 01:00 UTC equity (every D1/D3 prop number); the effect is small (EV $5,897 vs $6,201) but it is a bug in the direction of leniency on hour-0 moves.
8. **Costs.** The 2 bps slippage assumption is below the 6–12 bps quoted spreads on the alts (D2) but matters little at 0.6x turnover (10 bps → Sharpe 1.10). Funding is the real cost: +2.1 %/yr on the design line, +3.4 % at native, modelled from Binance 8-hourly rates; Delta's capped funding gave +1.9 %/yr on the repo's own Delta run, so this is not optimistic, but a design that quotes "fees 0.2 %/yr" understates running cost by a factor of ten. The Breakout cost model is 1.5–2 pp/yr cheaper than the Delta one, so prop EVs from S_b are the optimistic end.
9. **Hourly granularity** understates intraday breaches of the 3 % daily limit and the fill level of day stops and resting stops (`debug_breach.txt`: three hours in six years jump from above −1.5 % to below −3 %; 2025-10-10 had a −2.42 % single hour at native). All 0.0 % daily-breach figures are "0.0 % at hourly resolution".
10. **Grafts that change labels, not money.** The 0.5 % buffer and the funded de-lever push "funded survival" to 98–100 % by freezing or shrinking accounts near the floor; expected payout falls 4–9 % and the unresolved share rises from 22 % to 36 %. Reporting survival without payout overstates what a funded account is worth. The re-entry and chop grafts do nothing measurable; the balance-based reference reduces stop trips because a trend follower mostly carries unrealized gains, which is the lenient case, and is harsher on a floating loss.
11. **Kill criteria.** The D2 edge-decay null fires on 59 % of days since 2022 including all of 2024; D3's original fires once; the 30-day plumbing kill threshold ($3.88 on $1,000) is below rounding noise; the 26-week gate has a Sharpe SE of 1.78. Only the operational kills (missed Mondays, unexplained positions) are usable as written.
12. **Tax.** Under the per-transaction VDA reading every year is negative after tax; under the per-segment reading good years keep roughly half and flat years go negative. The gate at step 0 is right; the own-capital leg may be tax-dominated for its entire 26-week record.
13. **Inactivity and firm rules.** Four flat gaps of more than 30 days in six years; every firm fact (00:30 UTC balance rule, 6 % static, swap, inactivity, India eligibility, bot policy, HyroTrader static vs trailing) is [UNVERIFIED]; HyroTrader's EV swings from +$5,502 to +$1,822 on the static/trailing question alone.
14. **Look-ahead.** None found in the signal (closes to day d, position held over d+1; shocking d+1's price does not change d's weights, per the repo self-test). Two minor timing conventions are conservative-neutral: funding for day d+1 is charged from that day's realized rates, and the band compares notional at the decision price. Contract values are today's `/v2/products` figures applied to 2024-26 history.
15. **What the user asked for vs what the numbers are.** At the design's settings the own-capital leg's full-sample expectation is +14 %/yr (Binance) and its post-2021 expectation 6–9 %/yr before tax; the prop leg's EV is +$1,500–1,700 per $25k attempt in the full sample and about −$100 in a 2025-26 regime, with a 56–62 % chance of still being unresolved after a year. Nothing in this run makes the design look better than D3 said; several things (weekday on Delta, decision hour, kill behaviour, tax basis) make it look somewhat worse.
""")
open("backtest_results.md", "w").write(plan.rstrip() + "\n" + "".join(body))
print("written", len(plan) + sum(len(b) for b in body), "chars")
