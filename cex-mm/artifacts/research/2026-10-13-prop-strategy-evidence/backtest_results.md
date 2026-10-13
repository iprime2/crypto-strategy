# Backtest of the winning design (D3 "One Rule, Once a Week" + judges' grafts) on local data

**Role:** quant developer. **Date:** 2026-10-13. **Status:** nothing under `/home/user/crypto-strategy` modified, no orders, no live system touched, no `.env` read. All code in `scratchpad/tools/qd_*.py`, all raw outputs in `scratchpad/qd_runs/`. Every number below is [SYNTHETIC] (my computation on the local Binance USDT-M / Delta India archives) unless tagged otherwise.

**Data:** Binance USDT-M perp daily klines + funding (cache ends **2026-09-30**) and hourly klines (`scratchpad/hourly/<SYM>USDT-1h.csv`, to 2026-10-12 but only usable to 2026-09-30 because the daily archive that drives the signal ends there); Delta India daily candles + FUNDING candles to **2026-10-12** (BTC from 2023-12-29, the eight alts only from 2024-04-10, so the first Delta day with 120 closes for all nine coins is 2024-08-10). Delta fees used: taker 5.31 bps incl. GST (referral tier) + 2 bps slippage = 7.31 bps per side, as in the repo. Funding: Binance 8-hourly archive summed per day, charged in thirds at 00:00/08:00/16:00 UTC (Delta's schedule 05:30/13:30/21:30 IST).

---

## 0. Pre-registered test plan (written before any run; nothing below this block was edited after the runs started)

**Rule under test ("D3+grafts", own-capital leg):** repo signal `mean(sign(P/P-20), sign(P/P-60), sign(P/P-120))`, long/flat, 60-day realized vol, weight `sig_i × (TV/N) / max(vol_i, 0.05)`, N = 9 fixed coins (BTC ETH XRP BNB ADA LTC LINK DOGE BCH), **TV = 0.25**, gross cap 1.0x, **weekly rebalance at the Monday 00:00 UTC close** (decision candle = the UTC Sunday candle, D3 "offset 3"), taker 5.31 + 2 bps slippage per side, Binance funding, **10% notional no-trade band** (graft), no intraday stop, 20%-from-peak kill switch (flat 4 weeks, then half TV for 13 weeks). **Prop leg:** same signal and sizing at **daily cadence**, k = 0.5 of the native TV 0.40 series (TV 0.20), 1.5% portfolio day-stop, plus the grafts (funded de-lever, 0.5% buffer, re-entry room, chop detector, Breakout cost model).
**Baseline:** repo rule as pre-registered, daily rebalance, TV 0.40, same costs (memo 2026-10-08: Sharpe 1.25, max DD −21.9%).

Metrics (all on daily UTC returns unless stated): CAGR, annualized vol, Sharpe = mean/sd × √365 with 0% cash (repo convention), max DD on daily closes and on hourly marks, fees/yr and funding/yr as % of equity, average and max gross, trades/yr, calendar-year returns, worst day / worst 7-day. Sub-period statistics are computed on the sub-window of the same return series (equity not restarted).

| # | Test | Settings (ALL reported, none selected) | Acceptance / what I will say |
|---|---|---|---|
| T0 | Engine reproduction | my engine `qd_engine.py` vs (a) `local_evidence.md` baseline daily TV 0.40 (Sharpe 1.25, DD −21.9% / −22.6% hourly, by-year 53/47/−5/16/47/3/8) and (b) D3 R3a weekly Monday TV 0.40 (1.12, −26.3%, by-year 48.8/57.4/−10.7/22.5/38.1/2.4/1.9) | Sharpe within ±0.01, DD within ±0.3 pp, else fix the engine before any other test |
| T1 | Design vs baseline, Binance 2020-05-01..2026-09-30 | baseline daily TV 0.40; design weekly Mon TV 0.25 no band; design + 10% band; daily TV 0.25 (isolates cadence from vol); weekly Mon TV 0.40 | report all metrics + by year; no acceptance threshold, it is a description |
| T2 | Split | 2020-05-01..2023-12-31 vs 2024-01-01..2026-09-30 for every T1 line | same metrics per half |
| T3a | Target vol | 0.15 / 0.20 / 0.25 / 0.30 / 0.40 (weekly Mon, band 10%) | Sharpe should be flat in TV (vol targeting is linear); DD and worst day scale ~linearly; report where the −20% kill would have fired |
| T3b | Cadence / weekday | daily; weekly with decision weekday Mon..Sun (7 lines), TV 0.25 band 10% | report dispersion; design's Sunday-candle line labelled; the 7-day mean vs daily |
| T3c | No-trade band | 0 / 5 / 10 / 20 % of target notional | trades/yr, fees/yr, Sharpe, DD |
| T3d | Lookbacks | (20,60,120) [design] / (10,30,60) / (50,100,200) / (20,) / (60,) / (120,) | all reported |
| T3e | Vol window | 30 / 60 [design] / 90 | all reported |
| T3f | Universe | 9 [design] / BTC / BTC+ETH / BTC+ETH+XRP+BNB+ADA | all reported |
| T3g | Gross cap | 1.0 [design] vs 2.0 [repo]; also max gross reached | states whether the cap ever binds at TV 0.25 |
| T3h | Kill switch | none / −15 / −20 [design] / −25 / −30 % from peak, checked weekly at the rebalance (and daily as a variant), 4-week flat then half TV for 13 weeks | number of fires, dates, cost in CAGR/Sharpe |
| T3i | Own-account day stop (judges' concern) | none [design] / 1.5 / 2 / 3 % on the weekly TV 0.25 hourly series | report Sharpe, DD, worst day, stop days |
| T3j | Regime filters (design has none) | none / BTC < 200-day mean → flat / BTC 30-day vol > 70 % / > 90 % → flat | all reported |
| T3k | Late execution / decision hour | same Monday 00:00 signal executed at +0/+4/+8/+12/+24 h (missed-slot rule); and decision+execution hour H = 0/4/8/12/16/20 UTC using H-aligned daily closes from the hourly files | cost of the late-execution rule and hour dispersion on the weekly series |
| T3l | Slippage | 2 [design] / 5 / 10 bps per side | all reported |
| T3m | Cost model | Delta (5.31+2 bps, Binance funding) vs Breakout (4 bps/side, no funding, 0.033 %/day swap on gross at 00:00 UTC) on the daily native series | difference in CAGR, used for the prop series |
| T4 | Prop simulation (`prop_sim.py` and my `prop_sim2.py` with the grafts) | Series: daily native TV 0.40 (design's prop cadence per the graft) and weekly Monday (D3's original) for comparison; Breakout Classic 10 % / 3 % daily / 6 % static ($999 at $100k, $275 at $25k, 80 % split) and HyroTrader 10 % / 4 % / 6 % static ($599, 70 % split) [+ trailing max-DD variant as sensitivity]; k = 0.35 / 0.5 [design] / 0.75; day stop none / 1.5 % [design] / 2 %; bootstrap (3000 paths, mean block 20 d, seed 7) AND `--historical` (every real start day, 365 d); full sample and 2025-01-01..2026-09-30 bootstrap; funded phase 12 months, 80 % of profit withdrawn every 30 days. Grafts tested one at a time then together: funded de-lever clip((eq−0.94)/0.06, 0.33, 1); 0.5 % buffer (stop at max(day0×0.985, 0.945); flat if room to the 6 % floor < 0.5 % at the reset); re-entry only if room ≥ 1.5 % else flat to the next 7-day boundary; chop detector (3 trips in 10 days → k/2 for 30 days); Breakout cost series; balance-based daily reference (00:00 equity minus unrealized PnL of open positions); HyroTrader trailing intraday daily limit | pass, pass ≤ 180 d, daily/max-DD breach shares, unresolved, median/p90 days, 12-month funded survival, E[payout], EV per challenge; every row printed |
| T5 | Small-account rounding | the exact repo command (`--source delta --start 2024-08-10 --end 2026-10-12 --capital 500 1000 2500 5000`, read-only); plus my weekly TV 0.25 + band whole-contract run at the same capitals on Delta | comment on rounding noise, 0-or-1-contract coins, trades/yr |
| T6 | Judges' extra checks | edge-decay null (rolling 24-month Sharpe, rule vs vol-scaled always-long 9-coin basket at the same TV and cadence; how often the kill would have fired); tax gross-gain / gross-loss split per year (per coin-week and per coin-day); inactivity (longest flat streak, longest gap between trades); modelled cost per 30 days for the plumbing kill; Sharpe sampling error (cite `judge_evidence/sharpe_ci.py`) | report |
| T7 | Red flags | everything that makes the design's numbers look optimistic | list |

**Selection rule:** none. The design's parameters are fixed by D3 and the grafts; I report every setting I run and change nothing based on results. Where I add a test not listed here (because a result needs a follow-up), it is labelled **[post hoc]**.

**Simulator assumptions to carry into every prop number:** daily loss is measured against equity at 00:00 UTC (not Breakout's 00:30 UTC balance excluding open positions [UNVERIFIED]); hourly granularity misses intra-hour wicks; the day stop flattens for the rest of the UTC day at 7.31 bps on gross and the series' positions resume at the next 00:00 (a daily operator); payouts withdraw 80 % of profit every 30 days; the funded max DD stays static at 94 % of the initial balance after payouts; bootstrap blocks start on day boundaries so 00:00 checks stay aligned; one-sided test of the firms' rules, which are themselves [UNVERIFIED] snippet facts.

---

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
```
daily archive close vs hourly 23:00 bar close: 21885 pairs, 2 differ by >1e-9; examples: [('XRP', datetime.date(2020, 1, 16), 0.227, 0.229), ('XRP', datetime.date(2020, 1, 17), 0.2284, 0.2393)]
T0a daily TV0.40 band0 cap2 (repo baseline) CAGR +24.2% vol 18.7% Sharpe  1.25 maxDD -21.9% hDD -22.6% fees/yr 1.14% fund/yr +3.43% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr  1773 worst -7.31% (2021-05-19) worst7d -9.51%
    by year: 2020:+53.3%  2021:+47.0%  2022:-5.0%  2023:+15.9%  2024:+46.6%  2025:+2.7%  2026:+7.5%
    expect Sharpe 1.25 DD -21.9% hDD -22.6%  by year 53/47/-5/16/47/3/8
T0b weekly Sun-candle TV0.40 band0 cap2 (D3 R3a) CAGR +22.5% vol 19.8% Sharpe  1.12 maxDD -26.3% hDD -27.4% fees/yr 0.41% fund/yr +3.33% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr   278 worst -8.04% (2021-05-19) worst7d -12.07%
    by year: 2020:+48.8%  2021:+57.4%  2022:-10.7%  2023:+22.5%  2024:+38.1%  2025:+2.4%  2026:+1.9%
    expect Sharpe 1.12 DD -26.3%  by year 48.8/57.4/-10.7/22.5/38.1/2.4/1.9
```

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
```
=== T1. Design vs baseline, Binance 2020-05-01..2026-09-30 (T2 halves under each line) ===
B  baseline daily TV0.40 band0 cap2.0    CAGR +24.2% vol 18.7% Sharpe  1.25 maxDD -21.9% hDD -22.6% fees/yr 1.14% fund/yr +3.43% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr  1773 worst -7.31% (2021-05-19) worst7d -9.51%
    by year: 2020:+53.3%  2021:+47.0%  2022:-5.0%  2023:+15.9%  2024:+46.6%  2025:+2.7%  2026:+7.5%
    2020-05..2023-12: CAGR +28.1% vol 19.6% Sharpe  1.36 maxDD -21.9% hDD -22.6% total +148.0% worst -7.31% worst7d -9.43%
    2024-01..2026-09: CAGR +19.1% vol 17.4% Sharpe  1.09 maxDD -17.0% hDD -18.2% total +61.8% worst -5.05% worst7d -9.51%
D  design weekly Mon TV0.25 band0 cap1.0 CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -17.0% hDD -17.8% fees/yr 0.26% fund/yr +2.10% swap/yr 0.00% gross avg 0.12x max 0.57x trades/yr   278 worst -5.01% (2021-05-19) worst7d -7.54%
    by year: 2020:+28.8%  2021:+34.2%  2022:-6.8%  2023:+13.9%  2024:+23.1%  2025:+1.8%  2026:+1.3%
    2020-05..2023-12: CAGR +18.0% vol 13.4% Sharpe  1.30 maxDD -17.0% hDD -17.8% total +83.6% worst -5.01% worst7d -7.54%
    2024-01..2026-09: CAGR  +9.1% vol 11.0% Sharpe  0.85 maxDD  -9.4% hDD  -9.8% total +27.0% worst -3.51% worst7d -5.92%
D+ design weekly Mon TV0.25 band10% cap1.0 CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
   daily TV0.25 band0 cap2.0 (cadence isolated) CAGR +15.0% vol 11.7% Sharpe  1.25 maxDD -13.9% hDD -14.3% fees/yr 0.72% fund/yr +2.14% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr  1773 worst -4.57% (2021-05-19) worst7d -6.00%
    by year: 2020:+31.4%  2021:+28.0%  2022:-3.1%  2023:+10.1%  2024:+27.7%  2025:+2.0%  2026:+4.7%
    2020-05..2023-12: CAGR +17.3% vol 12.3% Sharpe  1.36 maxDD -13.9% hDD -14.3% total +79.4% worst -4.57% worst7d -5.93%
    2024-01..2026-09: CAGR +12.0% vol 10.9% Sharpe  1.09 maxDD -10.9% hDD -11.7% total +36.4% worst -3.15% worst7d -6.00%
   daily TV0.25 band10% cap2.0 (upgrade path) CAGR +15.0% vol 11.7% Sharpe  1.25 maxDD -14.1% hDD -14.5% fees/yr 0.67% fund/yr +2.15% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   538 worst -4.54% (2021-05-19) worst7d -5.90%
    by year: 2020:+30.7%  2021:+27.9%  2022:-2.8%  2023:+10.0%  2024:+27.8%  2025:+2.3%  2026:+4.9%
    2020-05..2023-12: CAGR +17.1% vol 12.2% Sharpe  1.35 maxDD -14.1% hDD -14.5% total +78.5% worst -4.54% worst7d -5.89%
    2024-01..2026-09: CAGR +12.2% vol 10.9% Sharpe  1.11 maxDD -10.6% hDD -11.4% total +37.1% worst -3.20% worst7d -5.90%
   weekly Mon TV0.40 band0 cap2.0 (D3 R3a) CAGR +22.5% vol 19.8% Sharpe  1.12 maxDD -26.3% hDD -27.4% fees/yr 0.41% fund/yr +3.33% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr   278 worst -8.04% (2021-05-19) worst7d -12.07%
    by year: 2020:+48.8%  2021:+57.4%  2022:-10.7%  2023:+22.5%  2024:+38.1%  2025:+2.4%  2026:+1.9%
    2020-05..2023-12: CAGR +29.2% vol 21.4% Sharpe  1.30 maxDD -26.3% hDD -27.4% total +156.0% worst -8.04% worst7d -12.07%
    2024-01..2026-09: CAGR +14.2% vol 17.5% Sharpe  0.85 maxDD -14.6% hDD -15.2% total +44.1% worst -5.57% worst7d -9.37%

=== T3a. Target vol (weekly Mon, band 10%, cap 1.0) ===
TV 0.15                                  CAGR  +8.5% vol  7.5% Sharpe  1.12 maxDD -10.5% hDD -11.0% fees/yr 0.15% fund/yr +1.27% swap/yr 0.00% gross avg 0.07x max 0.34x trades/yr   194 worst -2.97% (2021-05-19) worst7d -4.50%
    by year: 2020:+16.9%  2021:+19.6%  2022:-4.1%  2023:+8.2%  2024:+13.9%  2025:+1.3%  2026:+0.8%
    2020-05..2023-12: CAGR +10.6% vol  8.1% Sharpe  1.29 maxDD -10.5% hDD -11.0% total +44.9% worst -2.97% worst7d -4.50%
    2024-01..2026-09: CAGR  +5.7% vol  6.6% Sharpe  0.87 maxDD  -5.7% hDD  -5.9% total +16.3% worst -2.14% worst7d -3.57%
TV 0.20                                  CAGR +11.3% vol 10.0% Sharpe  1.12 maxDD -13.7% hDD -14.4% fees/yr 0.20% fund/yr +1.69% swap/yr 0.00% gross avg 0.10x max 0.45x trades/yr   193 worst -3.93% (2021-05-19) worst7d -5.94%
    by year: 2020:+22.9%  2021:+26.6%  2022:-5.5%  2023:+10.9%  2024:+18.7%  2025:+1.7%  2026:+1.0%
    2020-05..2023-12: CAGR +14.2% vol 10.8% Sharpe  1.29 maxDD -13.7% hDD -14.4% total +63.1% worst -3.93% worst7d -5.94%
    2024-01..2026-09: CAGR  +7.5% vol  8.8% Sharpe  0.86 maxDD  -7.5% hDD  -7.8% total +21.9% worst -2.84% worst7d -4.73%
TV 0.25                                  CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
TV 0.30                                  CAGR +17.0% vol 15.0% Sharpe  1.13 maxDD -20.2% hDD -21.1% fees/yr 0.30% fund/yr +2.52% swap/yr 0.00% gross avg 0.15x max 0.67x trades/yr   191 worst -5.86% (2021-05-19) worst7d -8.82%
    by year: 2020:+35.7%  2021:+42.4%  2022:-8.3%  2023:+16.4%  2024:+28.3%  2025:+2.2%  2026:+1.5%
    2020-05..2023-12: CAGR +21.8% vol 16.2% Sharpe  1.30 maxDD -20.2% hDD -21.1% total +106.2% worst -5.86% worst7d -8.82%
    2024-01..2026-09: CAGR +10.9% vol 13.2% Sharpe  0.85 maxDD -11.1% hDD -11.5% total +33.0% worst -4.21% worst7d -7.13%
TV 0.40                                  CAGR +22.7% vol 19.9% Sharpe  1.13 maxDD -26.2% hDD -27.4% fees/yr 0.40% fund/yr +3.34% swap/yr 0.00% gross avg 0.20x max 0.87x trades/yr   190 worst -7.82% (2021-05-19) worst7d -11.73%
    by year: 2020:+49.6%  2021:+58.6%  2022:-11.0%  2023:+22.1%  2024:+37.6%  2025:+2.7%  2026:+2.0%
    2020-05..2023-12: CAGR +29.4% vol 21.5% Sharpe  1.31 maxDD -26.2% hDD -27.4% total +157.9% worst -7.82% worst7d -11.73%
    2024-01..2026-09: CAGR +14.2% vol 17.5% Sharpe  0.85 maxDD -14.6% hDD -15.1% total +44.2% worst -5.55% worst7d -9.37%

=== T3b. Cadence / decision weekday (TV 0.25, band 10%) ===
daily                                    CAGR +15.0% vol 11.7% Sharpe  1.25 maxDD -14.1% hDD -14.5% fees/yr 0.67% fund/yr +2.15% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   538 worst -4.54% (2021-05-19) worst7d -5.90%
    by year: 2020:+30.7%  2021:+27.9%  2022:-2.8%  2023:+10.0%  2024:+27.8%  2025:+2.3%  2026:+4.9%
    2020-05..2023-12: CAGR +17.1% vol 12.2% Sharpe  1.35 maxDD -14.1% hDD -14.5% total +78.5% worst -4.54% worst7d -5.89%
    2024-01..2026-09: CAGR +12.2% vol 10.9% Sharpe  1.11 maxDD -10.6% hDD -11.4% total +37.1% worst -3.20% worst7d -5.90%
weekly, decision candle Mon (closes Tue 00:00 UTC) CAGR +16.2% vol 12.5% Sharpe  1.26 maxDD -16.9% hDD -17.4% fees/yr 0.24% fund/yr +2.13% swap/yr 0.00% gross avg 0.13x max 0.52x trades/yr   185 worst -4.72% (2021-05-19) worst7d -7.16%
    by year: 2020:+35.1%  2021:+35.2%  2022:-7.1%  2023:+14.4%  2024:+25.3%  2025:+4.3%  2026:+3.6%
    2020-05..2023-12: CAGR +19.8% vol 13.5% Sharpe  1.41 maxDD -16.9% hDD -17.4% total +94.1% worst -4.72% worst7d -7.16%
    2024-01..2026-09: CAGR +11.6% vol 11.2% Sharpe  1.04 maxDD  -9.1% hDD  -9.7% total +35.4% worst -3.44% worst7d -5.84%
weekly, decision candle Tue (closes Wed 00:00 UTC) CAGR +14.5% vol 12.0% Sharpe  1.18 maxDD -13.2% hDD -13.9% fees/yr 0.25% fund/yr +2.08% swap/yr 0.00% gross avg 0.12x max 0.53x trades/yr   194 worst -4.59% (2020-09-03) worst7d -6.99%
    by year: 2020:+28.0%  2021:+30.4%  2022:-5.6%  2023:+13.9%  2024:+26.0%  2025:+2.6%  2026:+2.5%
    2020-05..2023-12: CAGR +17.3% vol 12.8% Sharpe  1.31 maxDD -13.2% hDD -13.9% total +79.5% worst -4.59% worst7d -6.99%
    2024-01..2026-09: CAGR +10.8% vol 10.9% Sharpe  1.00 maxDD -11.8% hDD -12.7% total +32.7% worst -4.46% worst7d -6.38%
weekly, decision candle Wed (closes Thu 00:00 UTC) CAGR +16.9% vol 12.3% Sharpe  1.34 maxDD -11.2% hDD -11.7% fees/yr 0.24% fund/yr +2.12% swap/yr 0.00% gross avg 0.13x max 0.52x trades/yr   187 worst -5.16% (2021-05-19) worst7d -6.58%
    by year: 2020:+33.5%  2021:+33.7%  2022:-4.1%  2023:+17.8%  2024:+26.8%  2025:+4.4%  2026:+2.2%
    2020-05..2023-12: CAGR +21.0% vol 13.0% Sharpe  1.53 maxDD -11.2% hDD -11.7% total +101.6% worst -5.16% worst7d -6.58%
    2024-01..2026-09: CAGR +11.6% vol 11.2% Sharpe  1.04 maxDD -10.0% hDD -10.9% total +35.3% worst -3.95% worst7d -5.76%
weekly, decision candle Thu (closes Fri 00:00 UTC) CAGR +16.8% vol 12.4% Sharpe  1.31 maxDD  -9.8% hDD -10.6% fees/yr 0.24% fund/yr +2.10% swap/yr 0.00% gross avg 0.12x max 0.50x trades/yr   187 worst -4.89% (2021-05-19) worst7d -5.93%
    by year: 2020:+32.0%  2021:+33.8%  2022:-0.3%  2023:+10.6%  2024:+33.6%  2025:+1.9%  2026:+2.1%
    2020-05..2023-12: CAGR +19.9% vol 13.2% Sharpe  1.44 maxDD  -9.8% hDD -10.6% total +94.8% worst -4.89% worst7d -5.57%
    2024-01..2026-09: CAGR +12.7% vol 11.2% Sharpe  1.12 maxDD  -8.8% hDD  -9.3% total +39.0% worst -3.80% worst7d -5.93%
weekly, decision candle Fri (closes Sat 00:00 UTC) CAGR +15.3% vol 12.2% Sharpe  1.23 maxDD -16.3% hDD -16.9% fees/yr 0.25% fund/yr +2.13% swap/yr 0.00% gross avg 0.12x max 0.50x trades/yr   190 worst -4.78% (2021-05-19) worst7d -6.30%
    by year: 2020:+29.5%  2021:+30.3%  2022:-5.0%  2023:+9.0%  2024:+33.4%  2025:+3.5%  2026:+3.3%
    2020-05..2023-12: CAGR +16.4% vol 12.9% Sharpe  1.25 maxDD -16.3% hDD -16.9% total +74.7% worst -4.78% worst7d -6.30%
    2024-01..2026-09: CAGR +13.8% vol 11.3% Sharpe  1.20 maxDD  -8.6% hDD  -9.4% total +42.7% worst -3.54% worst7d -5.75%
weekly, decision candle Sat (closes Sun 00:00 UTC) CAGR +14.5% vol 12.3% Sharpe  1.16 maxDD -17.5% hDD -18.0% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.53x trades/yr   187 worst -4.83% (2021-05-19) worst7d -6.59%
    by year: 2020:+28.4%  2021:+31.1%  2022:-5.7%  2023:+11.1%  2024:+32.1%  2025:-0.8%  2026:+3.1%
    2020-05..2023-12: CAGR +16.7% vol 13.2% Sharpe  1.24 maxDD -17.5% hDD -18.0% total +76.3% worst -4.83% worst7d -6.59%
    2024-01..2026-09: CAGR +11.6% vol 10.9% Sharpe  1.06 maxDD  -8.8% hDD  -9.5% total +35.1% worst -3.73% worst7d -5.33%
weekly, decision candle Sun (closes Mon 00:00 UTC) [DESIGN] CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%

=== T3c. No-trade band (weekly Mon TV 0.25) + daily TV0.40 band for the record ===
band 0%                                  CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -17.0% hDD -17.8% fees/yr 0.26% fund/yr +2.10% swap/yr 0.00% gross avg 0.12x max 0.57x trades/yr   278 worst -5.01% (2021-05-19) worst7d -7.54%
    by year: 2020:+28.8%  2021:+34.2%  2022:-6.8%  2023:+13.9%  2024:+23.1%  2025:+1.8%  2026:+1.3%
    2020-05..2023-12: CAGR +18.0% vol 13.4% Sharpe  1.30 maxDD -17.0% hDD -17.8% total +83.6% worst -5.01% worst7d -7.54%
    2024-01..2026-09: CAGR  +9.1% vol 11.0% Sharpe  0.85 maxDD  -9.4% hDD  -9.8% total +27.0% worst -3.51% worst7d -5.92%
band 5%                                  CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -17.0% hDD -17.8% fees/yr 0.25% fund/yr +2.10% swap/yr 0.00% gross avg 0.12x max 0.57x trades/yr   221 worst -5.00% (2021-05-19) worst7d -7.54%
    by year: 2020:+28.9%  2021:+34.4%  2022:-6.8%  2023:+13.8%  2024:+23.0%  2025:+1.9%  2026:+1.3%
    2020-05..2023-12: CAGR +18.0% vol 13.4% Sharpe  1.30 maxDD -17.0% hDD -17.8% total +83.6% worst -5.00% worst7d -7.54%
    2024-01..2026-09: CAGR  +9.1% vol 11.0% Sharpe  0.85 maxDD  -9.4% hDD  -9.8% total +27.0% worst -3.51% worst7d -5.99%
band 10%                                 CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
band 20%                                 CAGR +14.1% vol 12.6% Sharpe  1.11 maxDD -17.2% hDD -17.9% fees/yr 0.24% fund/yr +2.14% swap/yr 0.00% gross avg 0.13x max 0.56x trades/yr   163 worst -4.64% (2021-05-19) worst7d -7.03%
    by year: 2020:+29.6%  2021:+35.0%  2022:-7.1%  2023:+13.9%  2024:+22.6%  2025:+1.6%  2026:+1.3%
    2020-05..2023-12: CAGR +18.3% vol 13.6% Sharpe  1.30 maxDD -17.2% hDD -17.9% total +85.2% worst -4.64% worst7d -7.03%
    2024-01..2026-09: CAGR  +8.8% vol 11.1% Sharpe  0.82 maxDD  -9.6% hDD  -9.8% total +26.1% worst -3.44% worst7d -6.09%
daily TV0.40 band10% cap2.0 (D2's banded daily) CAGR +24.2% vol 18.7% Sharpe  1.25 maxDD -22.4% hDD -23.1% fees/yr 1.07% fund/yr +3.42% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr   531 worst -7.36% (2021-05-19) worst7d -9.57%
    by year: 2020:+52.1%  2021:+46.6%  2022:-4.8%  2023:+15.7%  2024:+46.8%  2025:+3.3%  2026:+7.8%
    2020-05..2023-12: CAGR +27.7% vol 19.6% Sharpe  1.35 maxDD -22.4% hDD -23.1% total +145.6% worst -7.36% worst7d -9.57%
    2024-01..2026-09: CAGR +19.6% vol 17.5% Sharpe  1.11 maxDD -16.9% hDD -18.1% total +63.5% worst -5.05% worst7d -9.50%

=== T3d. Lookbacks (weekly Mon TV 0.25 band 10%) ===
looks (20, 60, 120)                      CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
looks (10, 30, 60)                       CAGR +13.5% vol 12.4% Sharpe  1.08 maxDD -15.6% hDD -16.7% fees/yr 0.35% fund/yr +2.10% swap/yr 0.00% gross avg 0.13x max 0.67x trades/yr   229 worst -4.48% (2021-09-07) worst7d -5.63%
    by year: 2020:+27.0%  2021:+40.9%  2022:-9.9%  2023:+14.7%  2024:+23.7%  2025:+1.7%  2026:-2.9%
    2020-05..2023-12: CAGR +18.2% vol 13.5% Sharpe  1.31 maxDD -15.6% hDD -16.7% total +84.9% worst -4.48% worst7d -5.63%
    2024-01..2026-09: CAGR  +7.5% vol 10.9% Sharpe  0.72 maxDD -12.2% hDD -12.7% total +22.1% worst -4.35% worst7d -4.64%
looks (50, 100, 200)                     CAGR +11.3% vol 12.1% Sharpe  0.95 maxDD -21.7% hDD -22.2% fees/yr 0.21% fund/yr +2.21% swap/yr 0.00% gross avg 0.13x max 0.49x trades/yr   164 worst -5.05% (2021-05-19) worst7d -7.67%
    by year: 2020:+26.4%  2021:+33.8%  2022:-4.2%  2023:+3.1%  2024:+20.4%  2025:-2.8%  2026:+1.8%
    2020-05..2023-12: CAGR +15.0% vol 12.7% Sharpe  1.17 maxDD -21.7% hDD -22.2% total +67.0% worst -5.05% worst7d -7.67%
    2024-01..2026-09: CAGR  +6.6% vol 11.3% Sharpe  0.62 maxDD -11.6% hDD -11.9% total +19.1% worst -4.16% worst7d -6.04%
  File "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools/qd_t1_t3.py", line 58, in <module>
    report(f"looks {lk}", looks=lk)
    ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools/qd_t1_t3.py", line 9, in report
    p = E.P(**kw); res = E.run(close, fund, hourly, p); dr = E.daily_from_rows(res["rows"]); s = E.stats(dr, res["rows"])
                         ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/tools/qd_engine.py", line 174, in run
```

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
```
D+ design weekly Mon TV0.25 band10% cap1.0 CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%

=== T3d. Lookbacks (weekly Mon TV 0.25 band 10%) ===
looks (20, 60, 120)                      CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
looks (10, 30, 60)                       CAGR +13.5% vol 12.4% Sharpe  1.08 maxDD -15.6% hDD -16.7% fees/yr 0.35% fund/yr +2.10% swap/yr 0.00% gross avg 0.13x max 0.67x trades/yr   229 worst -4.48% (2021-09-07) worst7d -5.63%
    by year: 2020:+27.0%  2021:+40.9%  2022:-9.9%  2023:+14.7%  2024:+23.7%  2025:+1.7%  2026:-2.9%
    2020-05..2023-12: CAGR +18.2% vol 13.5% Sharpe  1.31 maxDD -15.6% hDD -16.7% total +84.9% worst -4.48% worst7d -5.63%
    2024-01..2026-09: CAGR  +7.5% vol 10.9% Sharpe  0.72 maxDD -12.2% hDD -12.7% total +22.1% worst -4.35% worst7d -4.64%
looks (50, 100, 200)                     CAGR +11.3% vol 12.1% Sharpe  0.95 maxDD -21.7% hDD -22.2% fees/yr 0.21% fund/yr +2.21% swap/yr 0.00% gross avg 0.13x max 0.49x trades/yr   164 worst -5.05% (2021-05-19) worst7d -7.67%
    by year: 2020:+26.4%  2021:+33.8%  2022:-4.2%  2023:+3.1%  2024:+20.4%  2025:-2.8%  2026:+1.8%
    2020-05..2023-12: CAGR +15.0% vol 12.7% Sharpe  1.17 maxDD -21.7% hDD -22.2% total +67.0% worst -5.05% worst7d -7.67%
    2024-01..2026-09: CAGR  +6.6% vol 11.3% Sharpe  0.62 maxDD -11.6% hDD -11.9% total +19.1% worst -4.16% worst7d -6.04%
looks (20,)                              CAGR +13.5% vol 15.3% Sharpe  0.90 maxDD -22.2% hDD -23.1% fees/yr 0.43% fund/yr +2.46% swap/yr 0.00% gross avg 0.19x max 0.68x trades/yr   203 worst -5.16% (2022-11-09) worst7d -7.44%
    by year: 2020:+34.4%  2021:+37.8%  2022:-15.5%  2023:+16.8%  2024:+20.5%  2025:+6.6%  2026:-4.2%
    2020-05..2023-12: CAGR +17.9% vol 16.2% Sharpe  1.09 maxDD -22.2% hDD -23.1% total +82.9% worst -5.16% worst7d -7.44%
    2024-01..2026-09: CAGR  +7.8% vol 13.9% Sharpe  0.61 maxDD -17.0% hDD -17.6% total +23.0% worst -3.51% worst7d -7.16%
looks (60,)                              CAGR +14.7% vol 16.2% Sharpe  0.92 maxDD -28.0% hDD -28.7% fees/yr 0.28% fund/yr +2.57% swap/yr 0.00% gross avg 0.18x max 0.67x trades/yr   153 worst -5.61% (2020-09-03) worst7d -7.56%
    by year: 2020:+32.0%  2021:+38.1%  2022:-14.8%  2023:+20.9%  2024:+27.1%  2025:+0.7%  2026:+0.2%
    2020-05..2023-12: CAGR +18.7% vol 17.4% Sharpe  1.07 maxDD -28.0% hDD -28.7% total +87.9% worst -5.61% worst7d -7.56%
    2024-01..2026-09: CAGR  +9.5% vol 14.5% Sharpe  0.70 maxDD -15.6% hDD -16.8% total +28.3% worst -4.47% worst7d -6.56%
looks (120,)                             CAGR +19.5% vol 15.8% Sharpe  1.21 maxDD -16.7% hDD -17.8% fees/yr 0.18% fund/yr +2.58% swap/yr 0.00% gross avg 0.18x max 0.53x trades/yr   131 worst -6.30% (2025-10-10) worst7d -8.32%
    by year: 2020:+37.1%  2021:+43.7%  2022:-3.4%  2023:+27.0%  2024:+30.6%  2025:-3.1%  2026:+2.6%
    2020-05..2023-12: CAGR +27.2% vol 16.4% Sharpe  1.55 maxDD -16.7% hDD -17.8% total +141.7% worst -5.61% worst7d -8.32%
    2024-01..2026-09: CAGR +10.0% vol 14.9% Sharpe  0.71 maxDD -12.5% hDD -13.2% total +29.9% worst -6.30% worst7d -7.01%

=== T3e. Vol window ===
vol window 30                            CAGR +14.6% vol 12.5% Sharpe  1.16 maxDD -15.6% hDD -16.0% fees/yr 0.28% fund/yr +2.14% swap/yr 0.00% gross avg 0.13x max 0.53x trades/yr   209 worst -4.72% (2021-05-19) worst7d -7.08%
    by year: 2020:+30.5%  2021:+36.2%  2022:-7.2%  2023:+12.7%  2024:+24.1%  2025:+2.6%  2026:+1.5%
    2020-05..2023-12: CAGR +18.4% vol 13.6% Sharpe  1.31 maxDD -15.6% hDD -16.0% total +85.9% worst -4.72% worst7d -7.08%
    2024-01..2026-09: CAGR  +9.8% vol 10.9% Sharpe  0.91 maxDD  -9.5% hDD  -9.8% total +29.3% worst -3.67% worst7d -5.36%
vol window 60                            CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
vol window 90                            CAGR +13.1% vol 12.1% Sharpe  1.08 maxDD -17.0% hDD -17.8% fees/yr 0.23% fund/yr +2.03% swap/yr 0.00% gross avg 0.12x max 0.52x trades/yr   184 worst -4.87% (2021-05-19) worst7d -7.27%
    by year: 2020:+26.5%  2021:+29.7%  2022:-6.7%  2023:+13.8%  2024:+23.2%  2025:+1.7%  2026:+1.1%
    2020-05..2023-12: CAGR +16.3% vol 12.8% Sharpe  1.25 maxDD -17.0% hDD -17.8% total +74.3% worst -4.87% worst7d -7.27%
    2024-01..2026-09: CAGR  +9.0% vol 11.1% Sharpe  0.83 maxDD  -9.5% hDD  -9.7% total +26.7% worst -3.61% worst7d -5.98%

=== T3f. Universe ===
9 coins [DESIGN]                         CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
BTC only                                 CAGR +13.0% vol 15.9% Sharpe  0.85 maxDD -18.0% hDD -19.4% fees/yr 0.34% fund/yr +3.46% swap/yr 0.00% gross avg 0.20x max 0.93x trades/yr    21 worst -5.69% (2025-10-10) worst7d -8.01%
    by year: 2020:+58.3%  2021:+2.9%  2022:-6.8%  2023:+20.2%  2024:+25.7%  2025:-4.5%  2026:+0.1%
    2020-05..2023-12: CAGR +17.8% vol 16.6% Sharpe  1.07 maxDD -18.0% hDD -19.4% total +82.4% worst -4.64% worst7d -7.85%
    2024-01..2026-09: CAGR  +6.9% vol 15.0% Sharpe  0.52 maxDD -17.9% hDD -18.8% total +20.2% worst -5.69% worst7d -8.01%
BTC+ETH                                  CAGR +13.9% vol 14.7% Sharpe  0.95 maxDD -17.5% hDD -17.9% fees/yr 0.29% fund/yr +3.39% swap/yr 0.00% gross avg 0.18x max 0.71x trades/yr    43 worst -4.61% (2024-03-19) worst7d -9.09%
    by year: 2020:+47.3%  2021:+16.9%  2022:-5.7%  2023:+16.0%  2024:+14.8%  2025:+7.5%  2026:-0.8%
    2020-05..2023-12: CAGR +18.8% vol 16.0% Sharpe  1.16 maxDD -14.2% hDD -15.3% total +88.2% worst -4.55% worst7d -6.98%
    2024-01..2026-09: CAGR  +7.6% vol 12.8% Sharpe  0.63 maxDD -17.5% hDD -17.9% total +22.3% worst -4.61% worst7d -9.09%
top5 BTC ETH XRP BNB ADA                 CAGR +17.2% vol 13.2% Sharpe  1.27 maxDD -13.1% hDD -13.3% fees/yr 0.28% fund/yr +2.32% swap/yr 0.00% gross avg 0.15x max 0.72x trades/yr   109 worst -4.34% (2021-05-19) worst7d -7.01%
    by year: 2020:+35.8%  2021:+36.4%  2022:-6.5%  2023:+20.9%  2024:+24.2%  2025:+5.9%  2026:+0.5%
    2020-05..2023-12: CAGR +22.3% vol 14.3% Sharpe  1.48 maxDD -12.6% hDD -13.3% total +109.6% worst -4.34% worst7d -7.01%
    2024-01..2026-09: CAGR +10.7% vol 11.6% Sharpe  0.93 maxDD -13.1% hDD -13.3% total +32.1% worst -3.91% worst7d -6.47%

=== T3g. Gross cap ===
max gross 1.0                            CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
max gross 2.0                            CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%

=== T3h. Kill switch (flat 4 weeks, half TV 13 weeks, peak reset at restart) ===
no kill [reference]                      CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 15% checked weekly                  CAGR +14.0% vol 12.3% Sharpe  1.13 maxDD -17.3% hDD -17.8% fees/yr 0.24% fund/yr +2.09% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   191 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-7.1%  2023:+13.3%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    kills: 2022-11-14 (-16.0%)
    2020-05..2023-12: CAGR +17.7% vol 13.1% Sharpe  1.30 maxDD -17.3% hDD -17.8% total +81.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 20% checked weekly [DESIGN]         CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 25% checked weekly                  CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 30% checked weekly                  CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 20% checked daily                   CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
kill 15% weekly at native TV 0.40 band0 cap2 (D3 R3a line) CAGR +22.1% vol 19.4% Sharpe  1.13 maxDD -27.8% hDD -28.4% fees/yr 0.39% fund/yr +3.26% swap/yr 0.00% gross avg 0.19x max 0.88x trades/yr   274 worst -8.04% (2021-05-19) worst7d -12.07%
    by year: 2020:+48.8%  2021:+55.2%  2022:-11.1%  2023:+21.8%  2024:+38.1%  2025:+2.4%  2026:+1.9%
    kills: 2021-05-24 (-15.6%), 2022-11-14 (-18.5%)
    2020-05..2023-12: CAGR +28.4% vol 20.8% Sharpe  1.31 maxDD -27.8% hDD -28.4% total +150.1% worst -8.04% worst7d -12.07%
    2024-01..2026-09: CAGR +14.2% vol 17.5% Sharpe  0.85 maxDD -14.6% hDD -15.2% total +44.1% worst -5.57% worst7d -9.37%
kill 20% weekly at native TV 0.40 band0 cap2 (D3 R3a line) CAGR +22.9% vol 19.5% Sharpe  1.15 maxDD -24.8% hDD -25.6% fees/yr 0.40% fund/yr +3.33% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr   277 worst -8.04% (2021-05-19) worst7d -12.07%
    by year: 2020:+48.8%  2021:+57.4%  2022:-7.8%  2023:+20.5%  2024:+38.1%  2025:+2.4%  2026:+1.9%
    kills: 2022-09-19 (-20.7%)
    2020-05..2023-12: CAGR +29.8% vol 20.9% Sharpe  1.35 maxDD -24.8% hDD -25.6% total +160.2% worst -8.04% worst7d -12.07%
    2024-01..2026-09: CAGR +14.2% vol 17.5% Sharpe  0.85 maxDD -14.6% hDD -15.2% total +44.1% worst -5.57% worst7d -9.37%

=== T3i. Own-account day stop (weekly Mon TV 0.25 band 10%; resumes the week's positions next 00:00, both legs charged) ===
day stop none                            CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
day stop 0.015                           CAGR +12.7% vol 12.1% Sharpe  1.05 maxDD -14.6% hDD -15.0% fees/yr 0.77% fund/yr +2.03% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   294 worst -3.32% (2020-08-02) worst7d -7.64%
    by year: 2020:+28.2%  2021:+30.0%  2022:-4.3%  2023:+12.2%  2024:+16.9%  2025:+2.6%  2026:+0.5%
    day-stop trips: 83 (12.9/yr)
    2020-05..2023-12: CAGR +17.2% vol 13.1% Sharpe  1.28 maxDD -14.6% hDD -15.0% total +79.0% worst -3.32% worst7d -7.64%
    2024-01..2026-09: CAGR  +7.0% vol 10.8% Sharpe  0.68 maxDD -11.5% hDD -11.7% total +20.6% worst -2.33% worst7d -6.62%
day stop 0.02                            CAGR +12.6% vol 12.4% Sharpe  1.02 maxDD -14.9% hDD -15.3% fees/yr 0.55% fund/yr +2.06% swap/yr 0.00% gross avg 0.12x max 0.57x trades/yr   251 worst -3.32% (2020-08-02) worst7d -7.41%
    by year: 2020:+27.7%  2021:+31.8%  2022:-5.3%  2023:+12.7%  2024:+16.1%  2025:+1.2%  2026:+1.3%
    day-stop trips: 48 (7.5/yr)
    2020-05..2023-12: CAGR +17.3% vol 13.2% Sharpe  1.27 maxDD -14.9% hDD -15.3% total +79.7% worst -3.32% worst7d -6.29%
    2024-01..2026-09: CAGR  +6.5% vol 11.1% Sharpe  0.62 maxDD -13.1% hDD -13.3% total +19.0% worst -2.83% worst7d -7.41%
day stop 0.03                            CAGR +12.5% vol 12.8% Sharpe  0.99 maxDD -18.4% hDD -18.8% fees/yr 0.34% fund/yr +2.08% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   210 worst -5.71% (2024-03-05) worst7d -8.01%
    by year: 2020:+29.9%  2021:+26.0%  2022:-7.8%  2023:+13.6%  2024:+20.5%  2025:+2.0%  2026:+1.3%
    day-stop trips: 15 (2.3/yr)
    2020-05..2023-12: CAGR +15.8% vol 13.7% Sharpe  1.14 maxDD -18.4% hDD -18.8% total +71.4% worst -5.54% worst7d -8.01%
    2024-01..2026-09: CAGR  +8.3% vol 11.3% Sharpe  0.76 maxDD  -9.3% hDD  -9.7% total +24.4% worst -5.71% worst7d -5.96%

=== T3j. Regime filters (design: none) ===
none [DESIGN]                            CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
BTC < 200d mean -> flat                  CAGR +14.5% vol 12.1% Sharpe  1.18 maxDD -14.4% hDD -15.1% fees/yr 0.22% fund/yr +2.09% swap/yr 0.00% gross avg 0.11x max 0.56x trades/yr   156 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+30.5%  2022:+0.1%  2023:+10.0%  2024:+22.8%  2025:+2.3%  2026:+2.2%
    2020-05..2023-12: CAGR +18.4% vol 12.9% Sharpe  1.37 maxDD -14.4% hDD -15.1% total +85.6% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.5% vol 10.9% Sharpe  0.89 maxDD  -9.8% hDD -10.2% total +28.5% worst -3.52% worst7d -5.99%
BTC 30d vol > 70% -> flat                CAGR +11.6% vol 11.4% Sharpe  1.02 maxDD -14.0% hDD -14.5% fees/yr 0.24% fund/yr +1.50% swap/yr 0.00% gross avg 0.11x max 0.56x trades/yr   168 worst -4.32% (2020-11-26) worst7d -5.99%
    by year: 2020:+28.4%  2021:+17.9%  2022:-7.8%  2023:+13.6%  2024:+22.2%  2025:+2.1%  2026:+2.1%
    2020-05..2023-12: CAGR +13.4% vol 11.7% Sharpe  1.13 maxDD -14.0% hDD -14.5% total +58.6% worst -4.32% worst7d -5.27%
    2024-01..2026-09: CAGR  +9.2% vol 10.9% Sharpe  0.86 maxDD -10.3% hDD -10.6% total +27.3% worst -3.52% worst7d -5.99%
BTC 30d vol > 90% -> flat                CAGR +12.1% vol 12.1% Sharpe  1.00 maxDD -17.1% hDD -17.9% fees/yr 0.25% fund/yr +1.82% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   182 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+19.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +14.3% vol 12.9% Sharpe  1.10 maxDD -17.1% hDD -17.9% total +63.6% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%

=== T3k. Late execution (Monday 00:00 UTC signal executed later) and decision hour H (signal+execution on H-aligned closes) ===
exec lag +0h (same 00:00 signal)         CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
exec lag +4h (same 00:00 signal)         CAGR +13.8% vol 12.6% Sharpe  1.09 maxDD -18.6% hDD -19.4% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   193 worst -5.45% (2021-05-19) worst7d -8.28%
    by year: 2020:+29.8%  2021:+33.7%  2022:-7.6%  2023:+12.5%  2024:+23.5%  2025:+1.2%  2026:+1.7%
    2020-05..2023-12: CAGR +17.4% vol 13.6% Sharpe  1.25 maxDD -18.6% hDD -19.4% total +80.5% worst -5.45% worst7d -8.28%
    2024-01..2026-09: CAGR  +9.1% vol 11.1% Sharpe  0.84 maxDD  -9.9% hDD -10.3% total +26.9% worst -3.52% worst7d -6.08%
exec lag +8h (same 00:00 signal)         CAGR +14.1% vol 12.6% Sharpe  1.11 maxDD -18.1% hDD -18.7% fees/yr 0.25% fund/yr +2.10% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   194 worst -5.07% (2021-05-19) worst7d -7.71%
    by year: 2020:+29.9%  2021:+35.1%  2022:-7.3%  2023:+12.0%  2024:+24.0%  2025:+1.5%  2026:+1.7%
    2020-05..2023-12: CAGR +17.8% vol 13.6% Sharpe  1.27 maxDD -18.1% hDD -18.7% total +82.2% worst -5.07% worst7d -7.71%
    2024-01..2026-09: CAGR  +9.4% vol 11.1% Sharpe  0.87 maxDD  -9.8% hDD -10.2% total +28.0% worst -3.50% worst7d -5.89%
exec lag +12h (same 00:00 signal)        CAGR +13.9% vol 12.6% Sharpe  1.09 maxDD -18.3% hDD -18.9% fees/yr 0.25% fund/yr +2.09% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   194 worst -5.08% (2021-05-19) worst7d -7.71%
    by year: 2020:+29.4%  2021:+34.8%  2022:-7.3%  2023:+11.8%  2024:+23.1%  2025:+1.7%  2026:+1.5%
    2020-05..2023-12: CAGR +17.5% vol 13.7% Sharpe  1.25 maxDD -18.3% hDD -18.9% total +81.0% worst -5.08% worst7d -7.71%
    2024-01..2026-09: CAGR  +9.1% vol 11.0% Sharpe  0.85 maxDD  -9.6% hDD -10.0% total +27.1% worst -3.49% worst7d -5.79%
exec lag +24h (same 00:00 signal)        CAGR +14.6% vol 12.6% Sharpe  1.15 maxDD -16.6% hDD -17.4% fees/yr 0.25% fund/yr +2.06% swap/yr 0.00% gross avg 0.12x max 0.55x trades/yr   193 worst -5.25% (2021-05-19) worst7d -8.17%
    by year: 2020:+29.9%  2021:+35.2%  2022:-6.8%  2023:+12.1%  2024:+27.0%  2025:+2.5%  2026:+0.6%
    2020-05..2023-12: CAGR +18.0% vol 13.6% Sharpe  1.28 maxDD -16.6% hDD -17.4% total +83.6% worst -5.25% worst7d -8.17%
    2024-01..2026-09: CAGR +10.3% vol 11.1% Sharpe  0.94 maxDD  -8.9% hDD  -9.4% total +31.0% worst -3.39% worst7d -6.01%
decision+exec hour 00:00 UTC             CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
decision+exec hour 04:00 UTC             CAGR +15.2% vol 12.3% Sharpe  1.21 maxDD -16.3% hDD -16.8% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   188 worst -4.72% (2025-10-10) worst7d -6.52%
    by year: 2020:+30.1%  2021:+37.9%  2022:-7.9%  2023:+13.6%  2024:+25.4%  2025:+1.0%  2026:+4.2%
    2020-05..2023-12: CAGR +18.7% vol 13.2% Sharpe  1.37 maxDD -16.3% hDD -16.8% total +87.6% worst -4.32% worst7d -6.52%
    2024-01..2026-09: CAGR +10.6% vol 11.0% Sharpe  0.97 maxDD  -9.1% hDD  -9.5% total +32.0% worst -4.72% worst7d -5.87%
decision+exec hour 08:00 UTC             CAGR +16.1% vol 12.6% Sharpe  1.24 maxDD -16.7% hDD -17.2% fees/yr 0.25% fund/yr +2.13% swap/yr 0.00% gross avg 0.13x max 0.55x trades/yr   188 worst -4.63% (2025-10-10) worst7d -6.65%
    by year: 2020:+32.0%  2021:+37.2%  2022:-7.2%  2023:+15.1%  2024:+24.6%  2025:+3.5%  2026:+4.7%
    2020-05..2023-12: CAGR +19.7% vol 13.5% Sharpe  1.39 maxDD -16.7% hDD -17.2% total +93.3% worst -4.53% worst7d -6.65%
    2024-01..2026-09: CAGR +11.5% vol 11.3% Sharpe  1.02 maxDD  -9.9% hDD -10.3% total +35.0% worst -4.63% worst7d -6.54%
decision+exec hour 12:00 UTC             CAGR +14.5% vol 12.4% Sharpe  1.16 maxDD -18.9% hDD -19.3% fees/yr 0.26% fund/yr +2.14% swap/yr 0.00% gross avg 0.13x max 0.52x trades/yr   193 worst -4.46% (2021-05-19) worst7d -6.71%
    by year: 2020:+31.3%  2021:+30.0%  2022:-9.0%  2023:+13.9%  2024:+24.2%  2025:+4.2%  2026:+4.2%
    2020-05..2023-12: CAGR +16.8% vol 13.3% Sharpe  1.24 maxDD -18.9% hDD -19.3% total +76.9% worst -4.46% worst7d -6.71%
    2024-01..2026-09: CAGR +11.5% vol 11.1% Sharpe  1.04 maxDD  -9.2% hDD  -9.6% total +34.9% worst -3.80% worst7d -5.91%
decision+exec hour 16:00 UTC             CAGR +15.6% vol 13.0% Sharpe  1.18 maxDD -18.5% hDD -19.0% fees/yr 0.26% fund/yr +2.23% swap/yr 0.00% gross avg 0.13x max 0.63x trades/yr   192 worst -5.11% (2021-05-19) worst7d -7.83%
    by year: 2020:+40.6%  2021:+27.6%  2022:-8.1%  2023:+15.7%  2024:+24.4%  2025:+2.7%  2026:+4.0%
    2020-05..2023-12: CAGR +19.2% vol 14.0% Sharpe  1.33 maxDD -18.5% hDD -19.0% total +90.8% worst -5.11% worst7d -7.83%
    2024-01..2026-09: CAGR +10.9% vol 11.5% Sharpe  0.95 maxDD  -9.6% hDD  -9.8% total +32.9% worst -4.80% worst7d -6.29%
decision+exec hour 20:00 UTC             CAGR +17.7% vol 12.9% Sharpe  1.32 maxDD -17.3% hDD -18.1% fees/yr 0.25% fund/yr +2.17% swap/yr 0.00% gross avg 0.13x max 0.55x trades/yr   196 worst -5.22% (2021-05-19) worst7d -7.96%
    by year: 2020:+37.9%  2021:+38.5%  2022:-8.9%  2023:+17.7%  2024:+26.3%  2025:+4.3%  2026:+5.4%
    2020-05..2023-12: CAGR +21.6% vol 14.0% Sharpe  1.46 maxDD -17.3% hDD -18.1% total +104.9% worst -5.22% worst7d -7.96%
    2024-01..2026-09: CAGR +12.7% vol 11.3% Sharpe  1.11 maxDD  -8.7% hDD  -9.2% total +38.8% worst -4.47% worst7d -5.24%

=== T3l. Slippage per side (taker 5.31 bps fixed) ===
slippage 2 bps                           CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
    2020-05..2023-12: CAGR +17.8% vol 13.4% Sharpe  1.29 maxDD -16.9% hDD -17.7% total +82.7% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.2% vol 11.0% Sharpe  0.86 maxDD  -9.3% hDD  -9.7% total +27.5% worst -3.52% worst7d -5.99%
slippage 5 bps                           CAGR +14.0% vol 12.4% Sharpe  1.11 maxDD -17.1% hDD -17.8% fees/yr 0.35% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.0%  2021:+33.6%  2022:-6.9%  2023:+13.4%  2024:+23.3%  2025:+1.9%  2026:+1.2%
    2020-05..2023-12: CAGR +17.7% vol 13.4% Sharpe  1.28 maxDD -17.1% hDD -17.8% total +82.0% worst -4.88% worst7d -7.35%
    2024-01..2026-09: CAGR  +9.1% vol 11.0% Sharpe  0.85 maxDD  -9.4% hDD  -9.8% total +27.2% worst -3.53% worst7d -5.99%
slippage 10 bps                          CAGR +13.8% vol 12.4% Sharpe  1.10 maxDD -17.3% hDD -17.9% fees/yr 0.52% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.36%
    by year: 2020:+28.8%  2021:+33.4%  2022:-7.0%  2023:+13.2%  2024:+23.0%  2025:+1.8%  2026:+1.1%
    2020-05..2023-12: CAGR +17.5% vol 13.4% Sharpe  1.27 maxDD -17.3% hDD -17.9% total +80.9% worst -4.88% worst7d -7.36%
    2024-01..2026-09: CAGR  +8.9% vol 11.0% Sharpe  0.83 maxDD  -9.5% hDD  -9.9% total +26.6% worst -3.53% worst7d -6.00%

=== T3m. Cost model on the daily native series (prop leg): Delta vs Breakout ===
daily TV0.40 Delta costs (5.31+2 bps, Binance funding) CAGR +24.2% vol 18.7% Sharpe  1.25 maxDD -21.9% hDD -22.6% fees/yr 1.14% fund/yr +3.43% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr  1773 worst -7.31% (2021-05-19) worst7d -9.51%
    by year: 2020:+53.3%  2021:+47.0%  2022:-5.0%  2023:+15.9%  2024:+46.6%  2025:+2.7%  2026:+7.5%
    2020-05..2023-12: CAGR +28.1% vol 19.6% Sharpe  1.36 maxDD -21.9% hDD -22.6% total +148.0% worst -7.31% worst7d -9.43%
    2024-01..2026-09: CAGR +19.1% vol 17.4% Sharpe  1.09 maxDD -17.0% hDD -18.2% total +61.8% worst -5.05% worst7d -9.51%
daily TV0.40 Breakout costs (4 bps/side, no funding, 0.033%/day swap on gross) CAGR +26.1% vol 18.8% Sharpe  1.33 maxDD -22.3% hDD -23.0% fees/yr 0.63% fund/yr +0.00% swap/yr 2.38% gross avg 0.20x max 0.88x trades/yr  1773 worst -7.39% (2021-05-19) worst7d -9.47%
    by year: 2020:+59.0%  2021:+57.8%  2022:-5.3%  2023:+15.0%  2024:+48.9%  2025:+1.7%  2026:+7.1%
    2020-05..2023-12: CAGR +31.5% vol 19.7% Sharpe  1.49 maxDD -22.3% hDD -23.0% total +173.4% worst -7.39% worst7d -9.47%
    2024-01..2026-09: CAGR +19.2% vol 17.5% Sharpe  1.09 maxDD -16.8% hDD -18.1% total +62.2% worst -5.05% worst7d -9.32%
weekly Mon TV0.25 band10 Breakout costs  CAGR +14.9% vol 12.5% Sharpe  1.18 maxDD -17.7% hDD -18.2% fees/yr 0.14% fund/yr +0.00% swap/yr 1.50% gross avg 0.12x max 0.56x trades/yr   191 worst -4.93% (2021-05-19) worst7d -7.40%
    by year: 2020:+31.7%  2021:+40.0%  2022:-7.2%  2023:+12.5%  2024:+24.2%  2025:+1.1%  2026:+0.9%
    2020-05..2023-12: CAGR +19.5% vol 13.5% Sharpe  1.39 maxDD -17.7% hDD -18.2% total +92.6% worst -4.93% worst7d -7.40%
    2024-01..2026-09: CAGR  +9.0% vol 11.0% Sharpe  0.84 maxDD  -9.4% hDD  -9.7% total +26.8% worst -3.44% worst7d -5.85%

=== T6 input: vol-scaled always-long 9-coin basket (no signal), weekly Mon TV 0.25 band 10%, same costs ===
always-long basket weekly TV0.25         CAGR +22.4% vol 23.0% Sharpe  0.99 maxDD -36.6% hDD -37.7% fees/yr 0.11% fund/yr +3.20% swap/yr 0.00% gross avg 0.36x max 0.73x trades/yr   181 worst -6.56% (2026-02-05) worst7d -13.14%
    by year: 2020:+44.3%  2021:+53.9%  2022:-19.1%  2023:+45.1%  2024:+42.2%  2025:+1.7%  2026:-2.8%
    2020-05..2023-12: CAGR +29.8% vol 22.7% Sharpe  1.26 maxDD -31.5% hDD -33.1% total +160.4% worst -5.59% worst7d -10.24%
    2024-01..2026-09: CAGR +13.2% vol 23.4% Sharpe  0.64 maxDD -36.6% hDD -37.7% total +40.5% worst -6.56% worst7d -13.14%
done
```

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
```
daily TV0.40 per-position stop 3%/gross (Delta costs) CAGR +21.1% vol 18.4% Sharpe  1.13 maxDD -18.5% hDD -19.2% fees/yr 1.65% fund/yr +3.32% swap/yr 0.00% gross avg 0.19x max 0.88x trades/yr  1766 worst -5.55% (2024-03-05) worst7d -9.50%
    by year: 2020:+49.6%  2021:+42.7%  2022:-3.8%  2023:+13.0%  2024:+33.4%  2025:+3.2%  2026:+7.0%
    per-position stops hit: 579 (90.2/yr)
daily TV0.40 per-position stop 3%/gross (Breakout costs) CAGR +23.1% vol 18.5% Sharpe  1.22 maxDD -18.7% hDD -19.5% fees/yr 0.91% fund/yr +0.00% swap/yr 2.38% gross avg 0.19x max 0.88x trades/yr  1766 worst -5.41% (2024-03-05) worst7d -9.26%
    by year: 2020:+55.4%  2021:+53.3%  2022:-4.1%  2023:+12.4%  2024:+35.7%  2025:+2.5%  2026:+6.6%
    per-position stops hit: 579 (90.2/yr)
```
```
--- B0 Breakout, S_d, day stop 1.5%, bootstrap, ORIGINAL prop_sim.py (day ref = 01:00 equity)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 3% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop 0.015
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.35    7% |  46.9%      21.4%     0.0%   7.0%     0.0%  46.1% |      195      325 |       80.6%          8.55%            3,010
0.50   10% |  61.1%      38.6%     0.0%  15.6%     0.0%  23.2% |      139      296 |       60.0%         11.28%            5,897
0.75   15% |  63.1%      48.2%     3.0%  26.7%     0.0%   7.3% |       98      246 |       26.8%         10.82%            5,826

--- B1 Breakout, S_d, day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  46.2%      20.8%     0.0%   6.9%     0.0%  46.9% |   196   324 |       80.3%       8.47%        2,915 |         81.9%      2.6
0.50   10% |  61.9%      38.7%     0.0%  14.9%     0.0%  23.2% |   141   297 |       62.0%      11.63%        6,201 |         83.4%      5.4
0.75   15% |  63.9%      48.7%     6.5%  22.9%     0.0%   6.7% |    96   251 |       23.9%      10.79%        5,901 |         88.2%     11.0

--- B2 Breakout, S_d, day stop 1.5%, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  44.8%      26.3%     0.0%   0.3%     0.0%  54.9% |   149   316 |       79.8%       8.20%        2,678 |         77.3%      2.1
0.50   10% |  54.6%      44.2%     0.0%   3.2%     0.0%  42.2% |    86   247 |       61.1%      11.10%        5,060 |         81.1%      4.0
0.75   15% |  57.2%      49.2%     1.7%  12.1%     0.0%  29.0% |    70   203 |       23.6%      10.30%        4,894 |         83.0%      8.3

--- B3 Breakout, S_d, NO day stop, bootstrap (control)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  42.2%      20.5%    16.8%   4.8%     0.0%  36.2% |   185   318 |       60.4%       7.42%        2,135 |          0.0%      0.0
0.50   10% |  52.8%      35.2%    18.2%  12.2%     0.0%  16.9% |   131   293 |       30.8%       7.73%        3,078 |          0.0%      0.0
0.75   15% |  42.0%      36.3%    48.5%   8.2%     0.0%   1.3% |    73   201 |        2.5%       4.27%          793 |          0.0%      0.0

--- B4 Breakout, S_d, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.02, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  45.1%      21.1%    10.0%   5.0%     0.0%  40.0% |   190   323 |       71.0%       8.09%        2,647 |         32.1%      0.5
0.50   10% |  58.7%      37.0%     4.0%  15.8%     0.0%  21.5% |   139   296 |       48.1%       9.91%        4,818 |         66.9%      2.6
0.75   15% |  55.6%      43.8%    19.9%  20.4%     0.0%   4.1% |    89   240 |       15.1%       9.06%        4,038 |         76.1%      6.1

--- B5 Breakout, S_d 2025-01..2026-09 only, day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 638 days, base Sharpe 0.46 base vol 15%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    5% |   6.7%       1.3%     0.0%   7.6%     0.0%  85.7% |   264   346 |       84.0%       3.31%         -776 |         74.5%      1.3
0.50    7% |  18.6%       7.7%     0.0%  24.9%     0.0%  56.6% |   203   331 |       52.2%       4.29%         -202 |         86.8%      3.0
0.75   11% |  32.8%      20.1%     0.0%  38.6%     0.0%  28.6% |   140   299 |       32.6%       5.50%          807 |         84.4%      7.3
```
```
--- B6 Breakout, S_b (Breakout costs), day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.7%      23.1%     0.0%   6.6%     0.0%  44.7% |   190   321 |       81.8%       8.86%        3,318 |         80.4%      2.6
0.50   10% |  63.3%      39.9%     0.0%  14.8%     0.0%  22.0% |   139   296 |       63.1%      12.21%        6,725 |         82.1%      5.3
0.75   15% |  64.6%      49.3%     6.3%  22.6%     0.0%   6.5% |    95   251 |       24.4%      11.14%        6,199 |         87.9%     10.9

--- B7 Breakout, S_b, day stop 1.5%, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  45.3%      27.3%     0.0%   0.3%     0.0%  54.4% |   141   313 |       80.4%       8.59%        2,893 |         74.4%      2.0
0.50   10% |  52.7%      43.9%     0.0%   3.3%     0.0%  44.1% |    82   214 |       62.2%      11.65%        5,135 |         79.6%      4.0
0.75   15% |  55.4%      49.2%     1.7%  12.4%     0.0%  30.5% |    67   187 |       24.6%      10.73%        4,945 |         82.8%      8.6

--- B8 Breakout, S_b 2025-01..2026-09, day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 638 days, base Sharpe 0.41 base vol 15%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    5% |   6.1%       1.1%     0.0%   8.5%     0.0%  85.4% |   264   347 |       82.2%       3.22%         -803 |         74.6%      1.3
0.50    7% |  17.1%       6.7%     0.0%  27.1%     0.0%  55.8% |   206   331 |       49.9%       4.14%         -291 |         87.0%      3.0
0.75   11% |  31.9%      19.5%     0.0%  40.3%     0.0%  27.8% |   140   301 |       30.5%       5.29%          689 |         84.4%      7.3

--- B9 Breakout $25k ($275 fee), S_b, day stop 1.5%, bootstrap, k 0.5
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $275 acct $25,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.50   10% |  63.3%      39.9%     0.0%  14.8%     0.0%  22.0% |   139   296 |       63.1%      12.21%        1,656 |         82.1%      5.3

--- B10 Breakout, S_b, NO day stop, bootstrap (control)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  45.4%      23.4%    15.9%   4.7%     0.0%  34.0% |   177   316 |       60.8%       7.75%        2,523 |          0.0%      0.0
0.50   10% |  54.6%      36.6%    17.2%  12.0%     0.0%  16.2% |   128   290 |       30.9%       8.02%        3,375 |          0.0%      0.0
0.75   15% |  42.4%      36.7%    48.2%   8.2%     0.0%   1.2% |    72   201 |        2.5%       4.36%          852 |          0.0%      0.0

--- P1 Breakout, per-position stop fallback (stop 3% of native gross = 1.5% at k 0.5), NO portfolio day stop, S_d
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.15 base vol 18%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.50    9% |  58.9%      36.3%     0.0%  15.2%     0.0%  25.9% |   143   297 |       61.0%      10.81%        5,370 |          0.0%      0.0

--- P2 Breakout, per-position stop fallback, S_b, NO portfolio day stop, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.24 base vol 18%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.50    9% |  61.1%      38.0%     0.0%  14.4%     0.0%  24.5% |   141   295 |       62.6%      11.45%        5,991 |          0.0%      0.0

--- P3 Breakout, per-position stop fallback, S_b, NO portfolio day stop, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.50    9% |  52.3%      43.3%     0.0%   3.2%     0.0%  44.5% |    84   221 |       62.2%      10.97%        4,737 |          0.0%      0.0
```
```
--- W1 Breakout, S_w (D3 weekly Monday), day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.10 base vol 20%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  41.1%      19.2%     9.3%   8.5%     0.0%  41.1% |   191   321 |       65.0%       7.37%        2,031 |         80.2%      2.9
0.50   10% |  59.2%      36.8%     0.0%  18.3%     0.0%  22.4% |   141   298 |       55.2%      10.72%        5,352 |         90.3%      6.4
0.75   15% |  62.3%      47.1%     3.8%  26.8%     0.0%   7.1% |    95   256 |       22.1%       9.71%        5,048 |         84.7%     11.7

--- W2 Breakout, S_w, day stop 1.5%, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  39.7%      26.7%     6.2%   0.5%     0.0%  53.7% |   132   285 |       66.6%       7.26%        1,882 |         77.2%      2.2
0.50   10% |  50.2%      38.9%     0.0%   4.3%     0.0%  45.5% |    84   263 |       53.8%      10.22%        4,135 |         93.3%      4.9
0.75   15% |  55.3%      46.6%     0.7%  15.1%     0.0%  28.9% |    69   245 |       19.1%       9.28%        4,133 |         76.5%      9.2

--- W3 Breakout, S_w 2025-01..2026-09, day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 638 days, base Sharpe 0.25 base vol 14%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    5% |   2.1%       0.4%     0.0%   8.3%     0.0%  89.6% |   272   358 |       82.3%       2.74%         -942 |         75.2%      1.3
0.50    7% |   9.2%       2.7%     0.0%  28.3%     0.0%  62.5% |   225   334 |       47.9%       3.45%         -680 |         89.0%      3.7
0.75   10% |  23.2%      13.3%     0.0%  47.0%     0.0%  29.8% |   159   305 |       23.8%       4.16%          -32 |         88.6%      8.1

--- W4 Breakout, S_w, NO day stop, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.10 base vol 20%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop none, fee $999 acct $100,000 split 80%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  37.7%      19.1%    24.7%   5.2%     0.0%  32.4% |   179   318 |       49.9%       6.51%        1,456 |          0.0%      0.0
0.50   10% |  49.5%      33.1%    25.4%  11.3%     0.0%  13.8% |   126   289 |       27.0%       7.38%        2,651 |          0.0%      0.0
0.75   15% |  39.5%      34.3%    49.3%   9.9%     0.0%   1.3% |    70   199 |        2.5%       3.91%          545 |          0.0%      0.0

--- H1 HyroTrader static, S_d, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  47.5%      21.5%     0.0%   6.9%     0.0%  45.7% |   195   323 |       84.5%       7.61%        3,011 |         32.1%      0.5
0.50   10% |  61.0%      38.3%     0.0%  16.4%     0.0%  22.6% |   140   296 |       66.1%      10.01%        5,502 |         66.9%      2.7
0.75   15% |  63.3%      48.3%     4.0%  26.2%     0.0%   6.5% |    96   248 |       41.4%      12.32%        7,201 |         76.1%      6.2

--- H2 HyroTrader static, S_d, day stop 1.5%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.015, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  46.2%      20.8%     0.0%   6.9%     0.0%  46.9% |   196   324 |       84.7%       7.50%        2,864 |         81.9%      2.6
0.50   10% |  61.9%      38.7%     0.0%  14.9%     0.0%  23.2% |   141   297 |       70.0%      10.47%        5,888 |         83.4%      5.4
0.75   15% |  67.3%      50.7%     0.0%  25.0%     0.0%   7.7% |    99   254 |       52.4%      13.67%        8,604 |         88.2%     11.2

--- H3 HyroTrader static, S_d, day stop 2.0%, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  45.8%      27.3%     0.0%   0.3%     0.0%  53.9% |   143   312 |       84.4%       7.43%        2,806 |         16.8%      0.2
0.50   10% |  54.2%      43.4%     0.0%   2.8%     0.0%  43.0% |    88   240 |       65.2%       9.61%        4,614 |         63.8%      2.0
0.75   15% |  58.0%      49.3%     0.8%  13.4%     0.0%  27.8% |    72   225 |       39.1%      11.61%        6,138 |         66.5%      4.9

--- H4 HyroTrader TRAILING max DD (sensitivity), S_d, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% trailing, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  45.4%      21.4%     0.0%  22.8%     0.0%  31.8% |   189   319 |       22.6%       5.16%        1,740 |         30.2%      0.5
0.50   10% |  51.4%      36.1%     0.0%  40.8%     0.0%   7.8% |   121   277 |        4.2%       4.71%        1,822 |         64.0%      2.5
0.75   15% |  44.6%      39.7%     2.6%  52.0%     0.0%   0.8% |    71   186 |        0.4%       3.86%        1,124 |         74.6%      5.8

--- H5 HyroTrader static, trailing INTRADAY daily ref (graft), S_d, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: trailing intraday daily ref
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  47.3%      21.5%     0.0%   7.2%     0.0%  45.5% |   195   324 |       84.2%       7.61%        3,001 |         51.4%      0.9
0.50   10% |  57.8%      36.5%     4.0%  16.1%     0.0%  22.1% |   138   296 |       54.1%       8.72%        4,440 |         77.7%      3.4
0.75   15% |  61.4%      46.8%     5.5%  26.1%     0.0%   7.0% |    98   246 |       34.0%      10.21%        5,668 |         85.3%      9.9

--- H6 HyroTrader static, S_d 2025-01..2026-09, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 638 days, base Sharpe 0.46 base vol 15%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    5% |   7.4%       1.4%     0.0%   8.0%     0.0%  84.6% |   265   346 |       85.8%       2.97%         -379 |          0.0%      0.0
0.50    7% |  18.1%       7.1%     0.0%  23.8%     0.0%  58.1% |   207   330 |       60.1%       3.85%           97 |         67.7%      1.2
0.75   11% |  30.0%      19.3%     0.0%  47.4%     0.0%  22.6% |   132   294 |       29.4%       4.24%          673 |         70.9%      3.3

--- H7 HyroTrader static, NO day stop, bootstrap (control)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop none, fee $599 acct $100,000 split 70%; grafts: none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  49.0%      22.8%     0.0%   6.3%     0.0%  44.6% |   191   321 |       85.8%       7.87%        3,259 |          0.0%      0.0
0.50   10% |  58.7%      38.7%     9.7%  12.7%     0.0%  18.9% |   134   293 |       49.8%       8.85%        4,591 |          0.0%      0.0
0.75   15% |  58.4%      46.3%    12.4%  24.5%     0.0%   4.8% |    89   239 |       19.7%       8.50%        4,363 |          0.0%      0.0

--- H8 HyroTrader static, all grafts (delever funded 0.33, buffer 0.5%, re-entry 1.5%, chop 3/10/30) + trailing daily, day stop 2.0%, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.21 base vol 19%
rules: target 10%, daily DD 4%, max DD 6% static, time limit none, day stop 0.02, fee $599 acct $100,000 split 70%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d, trailing intraday daily ref
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  47.1%      21.5%     0.0%   0.6%     0.0%  52.3% |   195   323 |      100.0%       6.95%        2,674 |         54.3%      1.0
0.50   10% |  57.0%      36.3%     3.9%   1.3%     0.0%  37.7% |   137   295 |       87.8%       8.10%        4,023 |         79.3%      3.1
0.75   15% |  59.5%      44.8%     5.0%   2.4%     0.0%  33.1% |   100   253 |       81.8%       9.23%        4,895 |         85.8%      6.3
```
```
--- G1 Breakout S_b ds1.5, graft: de-lever 0.33 funded phase only
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (funded only)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.7%      23.1%     0.0%   6.6%     0.0%  44.7% |   190   321 |       99.6%       7.95%        2,873 |         80.4%      2.6
0.50   10% |  63.3%      39.9%     0.0%  14.8%     0.0%  22.0% |   139   296 |       92.8%      11.06%        6,000 |         82.1%      5.3
0.75   15% |  64.6%      49.3%     6.3%  22.6%     0.0%   6.5% |    95   251 |       43.8%      10.76%        5,951 |         87.9%     10.9

--- G2 Breakout S_b ds1.5, graft: de-lever 0.33 in evaluation too
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (eval too)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  46.7%      22.2%     0.0%   0.0%     0.0%  53.3% |   190   318 |       99.6%       7.95%        2,709 |         74.3%      2.0
0.50   10% |  60.9%      38.0%     0.4%   2.5%     0.0%  36.2% |   141   299 |       92.8%      11.06%        5,738 |         79.8%      3.9
0.75   15% |  64.3%      48.0%     7.0%  12.8%     0.0%  16.0% |    99   266 |       43.8%      10.76%        5,915 |         85.1%      7.6

--- G3 Breakout S_b ds1.5, graft: 0.5% buffer (stop at max(day0*0.985, 0.945); flat when room < 0.5%)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: buffer 0.005
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.4%      23.1%     0.0%   0.3%     0.0%  51.3% |   188   319 |       99.2%       8.76%        3,237 |         80.9%      2.5
0.50   10% |  62.2%      39.6%     0.0%   1.2%     0.0%  36.6% |   138   295 |       98.0%      11.72%        6,287 |         82.3%      4.7
0.75   15% |  62.5%      48.3%     5.9%   2.5%     0.0%  29.1% |    92   248 |       69.5%      10.59%        5,617 |         88.0%      7.9

--- G4 Breakout S_b ds1.5, graft: re-entry only if room >= 1.5%, else flat to next 7-day boundary
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: re-entry room 0.015
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.7%      23.1%     0.0%   6.4%     0.0%  44.9% |   190   321 |       82.0%       8.85%        3,316 |         80.4%      2.6
0.50   10% |  63.0%      39.9%     0.0%  14.6%     0.0%  22.3% |   139   295 |       62.6%      12.11%        6,636 |         82.1%      5.3
0.75   15% |  65.1%      49.5%     6.5%  22.2%     0.0%   6.2% |    96   252 |       24.6%      11.06%        6,206 |         87.9%     10.9

--- G5 Breakout S_b ds1.5, graft: chop detector 3 trips/10 d -> k/2 for 30 d
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: chop 3 trips/10 d -> k/2 for 30 d
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.8%      23.1%     0.0%   6.6%     0.0%  44.6% |   190   321 |       81.8%       8.86%        3,320 |         80.4%      2.6
0.50   10% |  62.9%      39.7%     0.0%  14.6%     0.0%  22.5% |   139   296 |       63.3%      12.03%        6,565 |         82.1%      5.1
0.75   15% |  64.1%      48.2%     6.2%  21.6%     0.0%   8.0% |   100   260 |       27.0%      10.74%        5,892 |         87.9%      9.9

--- G6 Breakout S_b ds1.5, balance-based daily reference (00:00 equity minus unrealized PnL)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: balance-based daily ref (eq - unrealized)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  52.0%      25.5%     0.0%   6.6%     0.0%  41.4% |   183   321 |       82.5%       9.28%        3,826 |          9.1%      0.1
0.50   10% |  63.3%      40.7%     0.0%  16.1%     0.0%  20.6% |   136   293 |       58.6%      12.05%        6,632 |         34.6%      0.8
0.75   15% |  64.5%      50.3%     3.6%  26.2%     0.0%   5.7% |    91   240 |       34.2%      14.82%        8,553 |         42.1%      1.8

--- G7 Breakout S_b ds1.5, ALL grafts (de-lever funded, buffer, re-entry, chop) + balance ref, bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d, balance-based daily ref (eq - unrealized)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  51.7%      25.5%     0.0%   0.6%     0.0%  47.7% |   182   320 |      100.0%       8.39%        3,335 |         15.3%      0.2
0.50   10% |  62.3%      40.5%     0.0%   1.8%     0.0%  35.9% |   135   292 |      100.0%      11.23%        6,000 |         41.9%      1.0
0.75   15% |  62.5%      49.3%     3.3%   4.6%     0.0%  29.7% |    88   235 |       95.1%      14.61%        8,128 |         51.3%      1.7

--- G8 same as G7, HISTORICAL
historical windows: 1979 starts, 365 days each
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d, balance-based daily ref (eq - unrealized)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.2%      32.3%     0.0%   0.0%     0.0%  51.8% |   118   285 |      100.0%       8.08%        2,898 |          2.7%      0.0
0.50   10% |  53.8%      44.3%     0.0%   0.1%     0.0%  46.2% |    83   220 |      100.0%      10.80%        4,810 |         41.8%      0.7
0.75   15% |  55.1%      49.4%     1.3%   0.8%     0.0%  42.7% |    63   184 |       95.9%      14.03%        6,734 |         49.9%      1.7

--- G9 same as G7, 2025-01..2026-09 bootstrap
bootstrap: 3000 paths x 365 days, mean block 20 d, series 638 days, base Sharpe 0.41 base vol 15%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d, balance-based daily ref (eq - unrealized)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    5% |   6.7%       1.3%     0.0%   0.2%     0.0%  93.2% |   263   346 |      100.0%       2.66%         -822 |         12.6%      0.1
0.50    7% |  17.3%       6.8%     0.0%   1.0%     0.0%  81.6% |   205   329 |      100.0%       3.43%         -404 |         56.0%      0.9
0.75   11% |  28.1%      19.2%     0.0%   5.7%     0.0%  66.2% |   123   280 |       99.8%       4.35%          224 |         74.5%      1.8

--- G10 same as G7, $25k account $275 fee, k 0.5
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $275 acct $25,000 split 80%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d, balance-based daily ref (eq - unrealized)
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.50   10% |  62.3%      40.5%     0.0%   1.8%     0.0%  35.9% |   135   292 |      100.0%      11.23%        1,475 |         41.9%      1.0

--- G11 Breakout S_b ds1.5, ALL grafts without balance ref (if Breakout measures on equity)
bootstrap: 3000 paths x 365 days, mean block 20 d, series 2344 days, base Sharpe 1.29 base vol 19%
rules: target 10%, daily DD 3%, max DD 6% static, time limit none, day stop 0.015, fee $999 acct $100,000 split 80%; grafts: delever min 0.33 (funded only), buffer 0.005, re-entry room 0.015, chop 3 trips/10 d -> k/2 for 30 d
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med d p90 d | funded surv E[pay]/acct EV/challenge | paths>=1 trip trips/yr
0.35    7% |  48.3%      23.0%     0.0%   0.3%     0.0%  51.4% |   188   319 |      100.0%       7.94%        2,834 |         80.9%      2.5
0.50   10% |  61.9%      39.4%     0.0%   1.1%     0.0%  37.0% |   138   294 |       99.2%      10.86%        5,726 |         82.3%      4.6
0.75   15% |  62.3%      47.3%     5.9%   2.2%     0.0%  29.6% |    96   252 |       72.5%      10.31%        5,418 |         88.0%      7.4
```

---

## 6. T5 — small-account rounding on Delta India (2024-08-10..2026-10-12)

### 6.1 The repo command as given (read-only; it used the cached Delta candles and fetched only the public `/v2/products` contract values)
```
$ python3 /home/user/crypto-strategy/cex-mm/scripts/trend_backtest.py --source delta --cache /tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/trend-cache --start 2024-08-10 --end 2026-10-12 --capital 500 1000 2500 5000

=== delta  2024-08-10 .. 2026-10-12  coins: BTC, ETH, XRP, BNB, ADA, LTC, LINK, DOGE, BCH
trend long-only                    CAGR  +16.5%  vol  17%  Sharpe  0.99  maxDD -14.1%  fees/yr 1.1%  funding/yr +1.9%  avg gross 0.19x
    by year: 2024:+32%  2025:+3%  2026:+3%
trend long/short                   CAGR  +18.1%  vol  25%  Sharpe  0.80  maxDD -17.3%  fees/yr 2.5%  funding/yr +0.3%  avg gross 0.43x
    by year: 2024:+16%  2025:-2%  2026:+26%
buy & hold, equal weight           CAGR  +13.1%  vol  62%  Sharpe  0.51  maxDD -66.3%  fees/yr 0.0%  funding/yr +0.0%  avg gross 1.00x
    by year: 2024:+100%  2025:-17%  2026:-21%
  whole Delta contracts (contract values {'BTC': 0.001, 'ETH': 0.01, 'XRP': 1.0, 'BNB': 0.1, 'ADA': 1.0, 'LTC': 0.1, 'LINK': 1.0, 'DOGE': 100.0, 'BCH': 0.01}):
  long-only, $500 capital            CAGR  +18.5%  vol  17%  Sharpe  1.09  maxDD -14.4%  fees/yr 1.2%  funding/yr +1.9%  avg gross 0.18x
  long-only, $1,000 capital          CAGR  +15.3%  vol  17%  Sharpe  0.93  maxDD -15.2%  fees/yr 1.1%  funding/yr +1.9%  avg gross 0.20x
  long-only, $2,500 capital          CAGR  +16.1%  vol  17%  Sharpe  0.97  maxDD -14.6%  fees/yr 1.1%  funding/yr +1.9%  avg gross 0.19x
  long-only, $5,000 capital          CAGR  +16.5%  vol  17%  Sharpe  1.00  maxDD -13.7%  fees/yr 1.1%  funding/yr +1.9%  avg gross 0.19x
exit 0
```

Daily cadence, TV 0.40: unrounded Sharpe 0.99, CAGR +16.5 %, max DD −14.1 %; whole contracts $500 → 1.09, $1,000 → 0.93, $2,500 → 0.97, $5,000 → 1.00. Rounding noise is ±0.08 of Sharpe and non-monotone in capital, so a $500 account is not worse than a $5,000 one on this window.

### 6.2 The design on Delta prices (weekly Monday 00:00 UTC decision, TV 0.25, 10 % band, whole contracts, memo contract values), plus the weekday check that explains the gap to D3's figure
```
Delta India 2024-08-10..2026-10-12, weekly Monday 00:00 UTC decision, taker 5.31 + 2 bps, Delta funding
-- TV 0.25 band 10%
  $  500 whole contracts: CAGR  +6.8% vol  9.8% Sharpe  0.72 maxDD  -9.1% worst -2.61% gross avg 0.09x max 0.56x trades/yr  101 fees/yr 0.23% final $577 ($500) 2024:+16.1% 2025:+1.1% 2026:-1.7%
  $1,000 whole contracts: CAGR  +8.3% vol 10.5% Sharpe  0.81 maxDD  -9.5% worst -4.14% gross avg 0.11x max 0.50x trades/yr  131 fees/yr 0.25% final $1,188 ($1,000) 2024:+14.5% 2025:+4.5% 2026:-0.6%
  $2,500 whole contracts: CAGR  +7.0% vol 10.4% Sharpe  0.70 maxDD  -9.2% worst -3.11% gross avg 0.12x max 0.49x trades/yr  152 fees/yr 0.24% final $2,896 ($2,500) 2024:+15.3% 2025:+2.5% 2026:-1.9%
  $5,000 whole contracts: CAGR  +6.8% vol 10.4% Sharpe  0.69 maxDD  -9.1% worst -3.28% gross avg 0.12x max 0.49x trades/yr  159 fees/yr 0.24% final $5,775 ($5,000) 2024:+15.6% 2025:+1.7% 2026:-1.8%
  unrounded          : CAGR  +7.0% vol 10.4% Sharpe  0.70 maxDD  -9.1% worst -3.20% gross avg 0.12x max 0.48x trades/yr  165 fees/yr 0.24% final $1 ($1) 2024:+15.5% 2025:+2.1% 2026:-1.9%
-- TV 0.25 band 0%
  $  500 whole contracts: CAGR  +6.8% vol  9.8% Sharpe  0.72 maxDD  -9.1% worst -2.61% gross avg 0.09x max 0.56x trades/yr  103 fees/yr 0.23% final $577 ($500) 2024:+16.1% 2025:+1.1% 2026:-1.7%
  $1,000 whole contracts: CAGR  +8.0% vol 10.5% Sharpe  0.78 maxDD  -9.5% worst -4.15% gross avg 0.11x max 0.50x trades/yr  138 fees/yr 0.25% final $1,183 ($1,000) 2024:+14.5% 2025:+4.1% 2026:-0.8%
  $2,500 whole contracts: CAGR  +6.9% vol 10.4% Sharpe  0.70 maxDD  -9.2% worst -3.11% gross avg 0.12x max 0.49x trades/yr  168 fees/yr 0.24% final $2,893 ($2,500) 2024:+15.3% 2025:+2.4% 2026:-1.9%
  $5,000 whole contracts: CAGR  +6.9% vol 10.4% Sharpe  0.69 maxDD  -9.0% worst -3.28% gross avg 0.12x max 0.49x trades/yr  187 fees/yr 0.24% final $5,779 ($5,000) 2024:+15.7% 2025:+1.7% 2026:-1.8%
  unrounded          : CAGR  +6.9% vol 10.3% Sharpe  0.70 maxDD  -9.1% worst -3.15% gross avg 0.12x max 0.48x trades/yr  243 fees/yr 0.24% final $1 ($1) 2024:+15.5% 2025:+1.9% 2026:-1.8%
-- TV 0.40 band 10%
  $  500 whole contracts: CAGR +12.6% vol 16.3% Sharpe  0.81 maxDD -15.8% worst -5.92% gross avg 0.17x max 0.78x trades/yr  117 fees/yr 0.38% final $647 ($500) 2024:+25.7% 2025:+5.2% 2026:-2.0%
  $1,000 whole contracts: CAGR +11.2% vol 16.9% Sharpe  0.71 maxDD -15.1% worst -5.57% gross avg 0.19x max 0.84x trades/yr  146 fees/yr 0.40% final $1,261 ($1,000) 2024:+27.4% 2025:+3.0% 2026:-3.9%
  $2,500 whole contracts: CAGR +10.5% vol 16.5% Sharpe  0.69 maxDD -14.2% worst -5.29% gross avg 0.19x max 0.76x trades/yr  156 fees/yr 0.38% final $3,105 ($2,500) 2024:+24.9% 2025:+2.7% 2026:-3.2%
  $5,000 whole contracts: CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.5% worst -5.18% gross avg 0.19x max 0.75x trades/yr  164 fees/yr 0.38% final $6,227 ($5,000) 2024:+25.3% 2025:+2.5% 2026:-3.0%
  unrounded          : CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.6% worst -5.11% gross avg 0.19x max 0.78x trades/yr  163 fees/yr 0.38% final $1 ($1) 2024:+24.6% 2025:+3.0% 2026:-3.1%
-- TV 0.40 band 0%
  $  500 whole contracts: CAGR +12.7% vol 16.3% Sharpe  0.81 maxDD -15.7% worst -5.87% gross avg 0.17x max 0.78x trades/yr  122 fees/yr 0.38% final $648 ($500) 2024:+25.8% 2025:+5.1% 2026:-2.0%
  $1,000 whole contracts: CAGR +11.2% vol 16.9% Sharpe  0.71 maxDD -15.0% worst -5.58% gross avg 0.19x max 0.83x trades/yr  156 fees/yr 0.40% final $1,259 ($1,000) 2024:+27.5% 2025:+2.8% 2026:-3.9%
  $2,500 whole contracts: CAGR +10.5% vol 16.5% Sharpe  0.69 maxDD -14.2% worst -5.17% gross avg 0.19x max 0.76x trades/yr  179 fees/yr 0.38% final $3,108 ($2,500) 2024:+25.0% 2025:+2.8% 2026:-3.2%
  $5,000 whole contracts: CAGR +10.8% vol 16.5% Sharpe  0.70 maxDD -14.5% worst -5.17% gross avg 0.19x max 0.77x trades/yr  200 fees/yr 0.39% final $6,244 ($5,000) 2024:+25.3% 2025:+2.8% 2026:-3.0%
  unrounded          : CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.3% worst -5.04% gross avg 0.19x max 0.77x trades/yr  243 fees/yr 0.39% final $1 ($1) 2024:+25.1% 2025:+2.6% 2026:-3.1%
-- daily cadence TV 0.40 band 0 (repo rule) unrounded, for reference: CAGR +16.5% vol 16.8% Sharpe  0.99 maxDD -14.1% worst -5.04% gross avg 0.19x max 0.80x trades/yr 1556 fees/yr 1.08% final $1 ($1) 2024:+32.0% 2025:+2.8% 2026:+2.7%
-- daily cadence TV 0.25 band 10% $1,000: CAGR +12.9% vol 10.5% Sharpe  1.21 maxDD  -8.3% worst -3.32% gross avg 0.11x max 0.54x trades/yr  399 fees/yr 0.70% final $1,302 ($1,000) 2024:+19.4% 2025:+5.6% 2026:+3.2%
```
```
Delta India 2024-08-10..2026-10-12, weekly Monday 00:00 UTC decision, taker 5.31 + 2 bps, Delta funding
-- TV 0.25 band 10%
  $  500 whole contracts: CAGR  +6.8% vol  9.8% Sharpe  0.72 maxDD  -9.1% worst -2.61% gross avg 0.09x max 0.56x trades/yr  101 fees/yr 0.23% final $577 ($500) 2024:+16.1% 2025:+1.1% 2026:-1.7%
  $1,000 whole contracts: CAGR  +8.3% vol 10.5% Sharpe  0.81 maxDD  -9.5% worst -4.14% gross avg 0.11x max 0.50x trades/yr  131 fees/yr 0.25% final $1,188 ($1,000) 2024:+14.5% 2025:+4.5% 2026:-0.6%
  $2,500 whole contracts: CAGR  +7.0% vol 10.4% Sharpe  0.70 maxDD  -9.2% worst -3.11% gross avg 0.12x max 0.49x trades/yr  152 fees/yr 0.24% final $2,896 ($2,500) 2024:+15.3% 2025:+2.5% 2026:-1.9%
  $5,000 whole contracts: CAGR  +6.8% vol 10.4% Sharpe  0.69 maxDD  -9.1% worst -3.28% gross avg 0.12x max 0.49x trades/yr  159 fees/yr 0.24% final $5,775 ($5,000) 2024:+15.6% 2025:+1.7% 2026:-1.8%
  unrounded          : CAGR  +7.0% vol 10.4% Sharpe  0.70 maxDD  -9.1% worst -3.20% gross avg 0.12x max 0.48x trades/yr  165 fees/yr 0.24% final $1 ($1) 2024:+15.5% 2025:+2.1% 2026:-1.9%
-- TV 0.25 band 0%
  $  500 whole contracts: CAGR  +6.8% vol  9.8% Sharpe  0.72 maxDD  -9.1% worst -2.61% gross avg 0.09x max 0.56x trades/yr  103 fees/yr 0.23% final $577 ($500) 2024:+16.1% 2025:+1.1% 2026:-1.7%
  $1,000 whole contracts: CAGR  +8.0% vol 10.5% Sharpe  0.78 maxDD  -9.5% worst -4.15% gross avg 0.11x max 0.50x trades/yr  138 fees/yr 0.25% final $1,183 ($1,000) 2024:+14.5% 2025:+4.1% 2026:-0.8%
  $2,500 whole contracts: CAGR  +6.9% vol 10.4% Sharpe  0.70 maxDD  -9.2% worst -3.11% gross avg 0.12x max 0.49x trades/yr  168 fees/yr 0.24% final $2,893 ($2,500) 2024:+15.3% 2025:+2.4% 2026:-1.9%
  $5,000 whole contracts: CAGR  +6.9% vol 10.4% Sharpe  0.69 maxDD  -9.0% worst -3.28% gross avg 0.12x max 0.49x trades/yr  187 fees/yr 0.24% final $5,779 ($5,000) 2024:+15.7% 2025:+1.7% 2026:-1.8%
  unrounded          : CAGR  +6.9% vol 10.3% Sharpe  0.70 maxDD  -9.1% worst -3.15% gross avg 0.12x max 0.48x trades/yr  243 fees/yr 0.24% final $1 ($1) 2024:+15.5% 2025:+1.9% 2026:-1.8%
-- TV 0.40 band 10%
  $  500 whole contracts: CAGR +12.6% vol 16.3% Sharpe  0.81 maxDD -15.8% worst -5.92% gross avg 0.17x max 0.78x trades/yr  117 fees/yr 0.38% final $647 ($500) 2024:+25.7% 2025:+5.2% 2026:-2.0%
  $1,000 whole contracts: CAGR +11.2% vol 16.9% Sharpe  0.71 maxDD -15.1% worst -5.57% gross avg 0.19x max 0.84x trades/yr  146 fees/yr 0.40% final $1,261 ($1,000) 2024:+27.4% 2025:+3.0% 2026:-3.9%
  $2,500 whole contracts: CAGR +10.5% vol 16.5% Sharpe  0.69 maxDD -14.2% worst -5.29% gross avg 0.19x max 0.76x trades/yr  156 fees/yr 0.38% final $3,105 ($2,500) 2024:+24.9% 2025:+2.7% 2026:-3.2%
  $5,000 whole contracts: CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.5% worst -5.18% gross avg 0.19x max 0.75x trades/yr  164 fees/yr 0.38% final $6,227 ($5,000) 2024:+25.3% 2025:+2.5% 2026:-3.0%
  unrounded          : CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.6% worst -5.11% gross avg 0.19x max 0.78x trades/yr  163 fees/yr 0.38% final $1 ($1) 2024:+24.6% 2025:+3.0% 2026:-3.1%
-- TV 0.40 band 0%
  $  500 whole contracts: CAGR +12.7% vol 16.3% Sharpe  0.81 maxDD -15.7% worst -5.87% gross avg 0.17x max 0.78x trades/yr  122 fees/yr 0.38% final $648 ($500) 2024:+25.8% 2025:+5.1% 2026:-2.0%
  $1,000 whole contracts: CAGR +11.2% vol 16.9% Sharpe  0.71 maxDD -15.0% worst -5.58% gross avg 0.19x max 0.83x trades/yr  156 fees/yr 0.40% final $1,259 ($1,000) 2024:+27.5% 2025:+2.8% 2026:-3.9%
  $2,500 whole contracts: CAGR +10.5% vol 16.5% Sharpe  0.69 maxDD -14.2% worst -5.17% gross avg 0.19x max 0.76x trades/yr  179 fees/yr 0.38% final $3,108 ($2,500) 2024:+25.0% 2025:+2.8% 2026:-3.2%
  $5,000 whole contracts: CAGR +10.8% vol 16.5% Sharpe  0.70 maxDD -14.5% worst -5.17% gross avg 0.19x max 0.77x trades/yr  200 fees/yr 0.39% final $6,244 ($5,000) 2024:+25.3% 2025:+2.8% 2026:-3.0%
  unrounded          : CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.3% worst -5.04% gross avg 0.19x max 0.77x trades/yr  243 fees/yr 0.39% final $1 ($1) 2024:+25.1% 2025:+2.6% 2026:-3.1%
-- daily cadence TV 0.40 band 0 (repo rule) unrounded, for reference: CAGR +16.5% vol 16.8% Sharpe  0.99 maxDD -14.1% worst -5.04% gross avg 0.19x max 0.80x trades/yr 1556 fees/yr 1.08% final $1 ($1) 2024:+32.0% 2025:+2.8% 2026:+2.7%
-- daily cadence TV 0.25 band 10% $1,000: CAGR +12.9% vol 10.5% Sharpe  1.21 maxDD  -8.3% worst -3.32% gross avg 0.11x max 0.54x trades/yr  399 fees/yr 0.70% final $1,302 ($1,000) 2024:+19.4% 2025:+5.6% 2026:+3.2%
Delta weekly, unrounded, by decision weekday (candle closing next day 00:00 UTC):
  decision Mon candle: TV0.40 CAGR +16.7% vol 16.8% Sharpe  1.01 maxDD -13.0% worst -5.45% gross avg 0.19x max | TV0.25 CAGR +10.6% vol 10.5% Sharpe  1.01 maxDD  -8.3% worst -3.44% gross avg 0.12x max
  decision Tue candle: TV0.40 CAGR +15.0% vol 16.1% Sharpe  0.95 maxDD -13.0% worst -5.26% gross avg 0.19x max | TV0.25 CAGR  +9.5% vol 10.0% Sharpe  0.96 maxDD  -8.2% worst -3.31% gross avg 0.12x max
  decision Wed candle: TV0.40 CAGR +17.7% vol 16.7% Sharpe  1.06 maxDD -12.2% worst -5.23% gross avg 0.20x max | TV0.25 CAGR +11.2% vol 10.4% Sharpe  1.07 maxDD  -7.8% worst -3.30% gross avg 0.12x max
  decision Thu candle: TV0.40 CAGR +17.9% vol 17.0% Sharpe  1.05 maxDD -13.8% worst -5.25% gross avg 0.19x max | TV0.25 CAGR +11.3% vol 10.7% Sharpe  1.06 maxDD  -8.7% worst -3.35% gross avg 0.12x max
  decision Fri candle: TV0.40 CAGR +20.1% vol 17.1% Sharpe  1.15 maxDD -12.0% worst -5.08% gross avg 0.19x max | TV0.25 CAGR +12.5% vol 10.8% Sharpe  1.14 maxDD  -7.6% worst -3.20% gross avg 0.12x max
  decision Sat candle: TV0.40 CAGR +15.1% vol 16.7% Sharpe  0.93 maxDD -13.7% worst -5.92% gross avg 0.19x max | TV0.25 CAGR  +9.5% vol 10.5% Sharpe  0.92 maxDD  -8.7% worst -3.72% gross avg 0.12x max
  decision Sun candle [DESIGN]: TV0.40 CAGR +10.6% vol 16.5% Sharpe  0.69 maxDD -14.3% worst -5.04% gross avg 0.19x max | TV0.25 CAGR  +7.0% vol 10.4% Sharpe  0.70 maxDD  -9.1% worst -3.20% gross avg 0.12x max
D3 offset convention: first trading day 2024-08-10 is a Saturday -> offset 3 => first rebalance nxt = Tuesday decision candle = Monday
Binance window 2020-05-01 is a Friday -> offset 3 => decision candle = Sunday
```

Two findings. **(a) Rounding is noise from $500 up** at the design's settings: Sharpe 0.72 / 0.81 / 0.70 / 0.69 at $500 / $1,000 / $2,500 / $5,000 vs 0.70 unrounded; the 10 % band removes 2–28 orders a year at the rounded sizes (78 unrounded) with no change in Sharpe; at $500 average gross is 0.09x (vs 0.12x) because BTC (~$82/contract) and BNB (~$73) round to zero most weeks. **(b) D3's venue-native number is for the wrong weekday.** D3's R3c/R2b "offset 3" counts rebalance days from the first trading day: on the Binance window (2020-05-01, a Friday) that lands on the Sunday candle (Monday 00:00 UTC decision, the design's slot); on the Delta window (2024-08-10, a Saturday) it lands on the **Monday candle (Tuesday 00:00 UTC decision)**. The Monday-candle line reproduces D3's Delta figures exactly (TV 0.40: CAGR +16.7 %, Sharpe 1.01, DD −13.0 %; TV 0.25: 1.01); the design's actual slot on Delta is **Sharpe 0.69–0.70, CAGR +7.0 % (TV 0.25) / +10.6 % (TV 0.40), max DD −9.1 % / −14.3 %**, the weakest of the seven weekdays there as well (others 0.92–1.15). At $1,000 and TV 0.25 the design made +8.3 %/yr on Delta (+14.5 % in Aug–Dec 2024, +4.5 % in 2025, −0.6 % in 2026 to Oct 12), not the +11.3 % / Sharpe 1.06 D3 quotes.

---

## 7. T6 — the judges' extra checks

```
=== T6a. Edge-decay null: rolling 24-month (730 d) Sharpe, design rule vs vol-scaled always-long 9-coin basket (same TV, cadence, costs) ===
  basket full-sample: CAGR +22.4% vol 23.0% Sharpe 0.99
  windows: 1615 days with a 24-month history (2022-04-30..2026-09-30); rule < basket on 58.8% of days; rule 24m return <= 0 on 14.4% of days
  rule rolling 24m Sharpe: min -0.80 (2023-05-11) median 0.75 max 1.83; basket: min -0.35 median 0.97 max 1.80
  month-end snapshots (rule 24m Sharpe / basket 24m Sharpe / rule 24m return / kill?):
   2022-06: 1.81/1.31/+71%  2022-09: 1.47/1.13/+48%  2022-12: 0.94/0.60/+25%  2023-03: 0.28/0.26/+5%  2023-06: -0.31/0.07/-6% KILL  2023-09: -0.39/-0.10/-7% KILL  2023-12: 0.35/0.47/+6% KILL  2024-03: 0.77/0.92/+18% KILL  2024-06: 0.64/1.25/+15% KILL  2024-09: 0.64/1.07/+15% KILL  2024-12: 1.37/1.68/+40% KILL  2025-03: 1.19/1.23/+31% KILL  2025-06: 1.32/1.33/+35% KILL  2025-09: 1.46/1.63/+45% KILL  2025-12: 0.95/0.90/+25%  2026-03: 0.56/0.22/+11%  2026-06: 0.69/0.04/+14%  2026-09: 0.98/0.67/+22%
  D3's original kill (24m return <= 0 while BTC 24m return > 0): fires on 1 days of 1615

=== T6b. Tax split (VDA 30% on gross gains, no loss set-off) for the design line, per year ===
  year |     net | per coin-DAY:   gains  losses after-tax | per coin-SEGMENT (held between trades):   gains  losses after-tax
  2020 |  +26.9% |   95.1%  -68.2%     -1.6% |   42.4%  -15.5%    +14.2%
  2021 |  +30.6% |  127.2%  -96.6%     -7.6% |   57.7%  -27.1%    +13.3%
  2022 |   -6.8% |   17.4%  -24.1%    -12.0% |    3.6%  -10.4%     -7.9%
  2023 |  +13.8% |   86.0%  -72.2%    -12.0% |   28.8%  -15.0%     +5.2%
  2024 |  +22.4% |   99.9%  -77.5%     -7.6% |   43.4%  -21.0%     +9.4%
  2025 |   +2.8% |   60.4%  -57.7%    -15.4% |   18.3%  -15.5%     -2.7%
  2026 |   +1.5% |   19.5%  -18.0%     -4.3% |    7.9%   -6.4%     -0.8%

=== T6c. Inactivity and trade gaps (design line) ===
  days flat at 00:00 (gross 0): 381 of 2344 (16.3%); longest flat streaks: 105d 2022-04-11..2022-07-24, 70d 2022-01-17..2022-03-27, 49d 2026-06-08..2026-07-26, 42d 2026-03-02..2026-04-12, 14d 2026-02-02..2026-02-15
  trade days: 289; longest gaps between any trade: 105d 2022-04-11->2022-07-25, 70d 2022-01-17->2022-03-28, 49d 2026-06-08->2026-07-27, 42d 2026-03-02->2026-04-13, 21d 2025-03-17->2025-04-07; gaps > 30 d: 4
  trades/yr (orders): 192

=== T6d. Plumbing kill: modelled cost per 30 days on the design line ===
  fees/yr 0.25% + funding/yr +2.11% -> modelled cost per 30 days 0.194% of equity; 2x threshold 0.388% = $3.88 on $1,000, $19.38 on $5,000
  30-day sd of the design's own return 3.6%: a tracking kill at 0.39% is 0.11 sd of a month's PnL; rounding noise at $1,000 (T5) is of the same order as the threshold

=== T6e. Rolling 12-month Sharpe of the design line (how often it sits below the design's own forward range 0.5-0.9) ===
  12m Sharpe: < 0 on 33.0% of days, < 0.5 on 45.5%, > 0.9 on 46.3%; min -2.00 (2022-11-09) max 3.45
  26-week Sharpe (D3's live gate length): < 0 on 46.0% of days, sd across windows 1.78, range [-3.89, 4.58]
```

**T6a edge-decay null (D2 graft).** The vol-scaled always-long 9-coin basket at the same TV, cadence and costs has Sharpe 0.99 full-sample (vol 23 %, max DD −37 %: at TV 0.25 the always-on basket realizes twice the vol of the long/flat rule because the nine coins are highly correlated). On a rolling 24-month basis the rule's Sharpe is **below the basket's on 59 % of days since 2022-04**, including every quarter-end from 2023-06 to 2025-09, i.e. through 2024 when the rule made +23.4 %. The kill as grafted would have stopped the strategy for two and a half years and missed its best recent year. The rule's advantage over the basket is drawdown (−17 % vs −37 %) and 2022 (−6.9 % vs −19.1 %), which a Sharpe-only comparison cannot see. D3's original criterion (24-month return ≤ 0 while BTC's 24-month return > 0) fires on 1 day in 1,615. Neither is a usable kill as written.

**T6b tax split.** On a per-coin-day basis (every day's PnL a separate taxable event) the design's gross gains are 17–127 %/yr of equity against gross losses of 18–97 %, and a 30 % tax on gains with no loss set-off makes **every year negative after tax** (−1.6 % to −15.4 %). On a per-segment basis (PnL realized when a position is changed, which is how a weekly operator's fills look) gains are 4–58 %/yr and losses 6–27 %: after tax 2020 +14.2 %, 2021 +13.3 %, 2022 −7.9 %, 2023 +5.2 %, 2024 +9.4 %, 2025 −2.7 %, 2026 −0.8 %, roughly half the pre-tax result in good years and worse than flat in flat years. Which basis applies is the open CA question; both are below an Indian FD over 2022-26.

**T6c inactivity.** Flat 16 % of days; longest flat streaks 105 d (2022-04-11..07-24), 70 d (2022-01..03), 49 d (2026-06..07), 42 d (2026-03..04); four gaps of more than 30 days between any order. If Breakout has a 30-day inactivity rule [UNVERIFIED], the weekly design would have tripped it four times in six years.

**T6d plumbing kill.** Modelled cost per 30 days is 0.19 % of equity (fees 0.25 %/yr + funding 2.11 %/yr); the 2x threshold is 0.39 % = $3.88 on $1,000, which is 0.11 of one month's standard deviation of the strategy's own return (3.6 %) and of the same size as whole-contract rounding noise at $1,000, so the 30-day tracking kill cannot be measured at $1,000 and needs to be stated in dollars per order (e.g. fills more than 2 × 7.31 bps from the decision price) rather than as equity divergence.

**T6e the 26-week gate.** Rolling 26-week Sharpe of the design line is below zero in 46 % of windows and has a standard deviation of 1.78 across windows; rolling 12-month Sharpe is below 0.5 in 46 % of days and below 0 in 33 %. The live gate measures adherence, not edge.

**T6f Sharpe sampling error** (re-run of `judge_evidence/sharpe_ci.py` on my series):
```

=== daily rule (D1/D2 base, TV 0.40): file hourly_daily_tv40.csv cols=['ts_utc', 'ret', 'gross', 'unreal'] ret_col=ret days=2344 2020-05-01..2026-09-30
  full 2020-05..2026-09        days 2344 Sharpe  1.26  Lo-SE 0.53  t= 2.4  block-boot 95% [ 0.40,  2.08]  ann.vol 18.7%  skew -0.10  kurt  12.4
  OOS-ish 2022-01..2026-09     days 1734 Sharpe  0.85  Lo-SE 0.54  t= 1.6  block-boot 95% [-0.20,  1.82]  ann.vol 16.1%  skew  0.07  kurt  14.0
  recent 2025-01..2026-09      days  638 Sharpe  0.46  Lo-SE 0.80  t= 0.6  block-boot 95% [-0.91,  1.75]  ann.vol 14.6%  skew  0.15  kurt  14.8
  2020-05..2021-12             days  610 Sharpe  2.10  Lo-SE 1.39  t= 1.5  block-boot 95% [ 0.48,  3.60]  ann.vol 24.6%  skew -0.32  kurt   8.6

=== weekly Monday rule (D3 base, TV 0.40): file hourly_design_weekly_tv25_band10.csv cols=['ts_utc', 'ret', 'gross', 'unreal'] ret_col=ret days=2344 2020-05-01..2026-09-30
  full 2020-05..2026-09        days 2344 Sharpe  1.13  Lo-SE 0.50  t= 2.2  block-boot 95% [ 0.30,  1.92]  ann.vol 12.4%  skew  0.00  kurt  13.9
  OOS-ish 2022-01..2026-09     days 1734 Sharpe  0.67  Lo-SE 0.51  t= 1.3  block-boot 95% [-0.28,  1.58]  ann.vol 10.4%  skew  0.07  kurt  14.9
  recent 2025-01..2026-09      days  638 Sharpe  0.26  Lo-SE 0.77  t= 0.3  block-boot 95% [-1.06,  1.36]  ann.vol  8.7%  skew -0.07  kurt  15.4
  2020-05..2021-12             days  610 Sharpe  2.02  Lo-SE 1.35  t= 1.5  block-boot 95% [ 0.41,  3.55]  ann.vol 16.9%  skew -0.16  kurt   9.5
```

Design line: full-sample Sharpe 1.13, Lo SE 0.50, t = 2.2, block-bootstrap 95 % CI [0.30, 1.92]; 2022-01..2026-09 0.67, CI [−0.28, 1.58]; 2025-01..2026-09 0.26, CI [−1.06, 1.36]; 2020-05..2021-12 2.02. Excess kurtosis 14–15.

**T6g [post hoc] how often the −20 % kill fires on path luck** (block bootstrap of the design's daily returns, 4,000 paths; mean shifted to the design's own forward Sharpe range):
```
design daily series: 2344 days, Sharpe 1.12, ann vol 12.4%
         drift  horizon | P(DD<=-15%) P(DD<=-20%) P(DD<=-25%) | median DD  p90 DD | P(total<0) median ret
         as-is      1 y |        4.1%        0.4%        0.0% |     -7.9%  -12.8% |      17.6%     +12.4%
         as-is      2 y |       13.8%        2.5%        0.3% |    -10.3%  -16.1% |       7.6%     +27.6%
         as-is      3 y |       22.8%        5.5%        1.0% |    -11.8%  -17.9% |       4.1%     +48.2%
    Sharpe 0.7      1 y |        9.4%        1.4%        0.1% |     -9.5%  -14.8% |      29.3%      +7.2%
    Sharpe 0.7      2 y |       33.7%       11.1%        2.3% |    -12.9%  -20.4% |      21.1%     +16.2%
    Sharpe 0.7      3 y |       51.7%       21.1%        6.8% |    -15.2%  -23.5% |      16.8%     +25.6%
    Sharpe 0.5      1 y |       16.6%        3.1%        0.2% |    -10.5%  -16.7% |      38.3%      +4.2%
    Sharpe 0.5      2 y |       46.7%       17.8%        5.5% |    -14.5%  -22.4% |      29.9%     +10.1%
    Sharpe 0.5      3 y |       65.3%       32.4%       14.3% |    -17.0%  -26.9% |      25.8%     +17.8%
    Sharpe 0.0      1 y |       37.5%       10.5%        1.8% |    -13.3%  -20.2% |      56.4%      -2.3%
    Sharpe 0.0      2 y |       74.7%       45.0%       22.7% |    -19.1%  -29.4% |      54.7%      -2.7%
    Sharpe 0.0      3 y |       90.2%       67.7%       43.6% |    -23.5%  -35.8% |      54.3%      -2.6%
```

At the design's forward assumption of Sharpe 0.5–0.9 the −20 % kill fires within two years on 11–18 % of paths and within three years on 21–32 %; the −15 % level fires on 34–47 % within two years. At Sharpe 0 (no edge) the kill fires within two years on 45 % of paths and the 3-year total return is negative on 54 %: the kill is a weak detector of a dead edge (it does not fire on most no-edge paths for two years) and a frequent false alarm on a live one.

**[post hoc] archive-gap sensitivity** (the engine crash in T3d):
```
XRP: filled 5 days
LTC: filled 5 days
baseline daily TV0.40 [archive as-is]    CAGR +24.2% vol 18.7% Sharpe  1.25 maxDD -21.9% hDD -22.6% fees/yr 1.14% fund/yr +3.43% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr  1773 worst -7.31% (2021-05-19) worst7d -9.51%
    by year: 2020:+53.3%  2021:+47.0%  2022:-5.0%  2023:+15.9%  2024:+46.6%  2025:+2.7%  2026:+7.5%
baseline daily TV0.40 [gaps filled]      CAGR +24.1% vol 18.7% Sharpe  1.25 maxDD -22.1% hDD -22.8% fees/yr 1.14% fund/yr +3.43% swap/yr 0.00% gross avg 0.20x max 0.88x trades/yr  1780 worst -7.31% (2021-05-19) worst7d -9.51%
    by year: 2020:+53.3%  2021:+47.0%  2022:-5.3%  2023:+15.9%  2024:+46.6%  2025:+2.7%  2026:+7.5%
design weekly Mon TV0.25 band10 [archive as-is] CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -16.9% hDD -17.7% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-6.9%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
design weekly Mon TV0.25 band10 [gaps filled] CAGR +14.1% vol 12.4% Sharpe  1.12 maxDD -17.0% hDD -17.8% fees/yr 0.25% fund/yr +2.11% swap/yr 0.00% gross avg 0.12x max 0.56x trades/yr   192 worst -4.88% (2021-05-19) worst7d -7.35%
    by year: 2020:+29.1%  2021:+33.7%  2022:-7.0%  2023:+13.6%  2024:+23.4%  2025:+2.0%  2026:+1.3%
```

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
