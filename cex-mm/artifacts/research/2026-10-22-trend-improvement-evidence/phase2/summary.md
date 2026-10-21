# Phase 2 summary

Plan frozen 2026-10-21T14:08:16Z after amendment A-2026-10-21, sha256 9ad0a829f7bc269f5ce99e7c4e57a09ef89ffe1699776b479abe9b291418c095

baseline         weekly  | B post Δ +0.000 [+0.00,+0.00] P≤0 1.00 sd 0.000 hurdle 0.050 | B full 0.81 vs 0.81 DD -17.0%/-17.0% | h1 +0.00 h2 +0.00 | A post +0.00 full +0.00 | C +0.00 | turn 2.9x fund 1.93% tax(seg) +3.9% vs +3.9%
tranche7_smoke   weekly  | B post Δ +0.152 [+0.00,+0.31] P≤0 0.03 sd 0.079 hurdle 0.197 | B full 0.91 vs 0.81 DD -15.2%/-17.0% | h1 +0.04 h2 +0.18 | A post +0.16 full +0.13 | C +0.29 | turn 2.9x fund 1.93% tax(seg) +4.8% vs +3.9%
baseline         daily   | (no B panel)
TIME-1           tranche | B post Δ +0.176 [+0.03,+0.33] P≤0 0.01 sd 0.077 hurdle 0.193 | B full 0.92 vs 0.81 DD -14.3%/-17.0% | h1 +0.05 h2 +0.20 | A post +0.16 full +0.12 | C +0.27 | turn 2.9x fund 1.85% tax(seg) +5.0% vs +3.9%
TIME-1__K3       tranche | B post Δ +0.196 [+0.00,+0.40] P≤0 0.03 sd 0.103 hurdle 0.256 | B full 0.94 vs 0.81 DD -14.0%/-17.0% | h1 +0.06 h2 +0.23 | A post +0.26 full +0.19 | C +0.32 | turn 4.5x fund 1.93% tax(seg) +4.6% vs +3.9%
TIME-1__K5       tranche | B post Δ +0.151 [-0.01,+0.33] P≤0 0.04 sd 0.087 hurdle 0.218 | B full 0.90 vs 0.81 DD -14.9%/-17.0% | h1 +0.03 h2 +0.17 | A post +0.17 full +0.12 | C +0.28 | turn 3.5x fund 1.88% tax(seg) +4.6% vs +3.9%
TIME-1__TIME5_partial tranche | B post Δ +0.186 [+0.04,+0.36] P≤0 0.01 sd 0.082 hurdle 0.205 | B full 0.93 vs 0.81 DD -14.1%/-17.0% | h1 +0.06 h2 +0.22 | A post +0.19 full +0.15 | C +0.28 | turn 3.1x fund 1.85% tax(seg) +5.0% vs +3.9%

## Diagnostic outcomes (recorded before the trial results were read)
- D-1: SIG-9 does not run (Correction < Bull on the 24-coin panel); OVL-3 runs (Correction next-7-day return −0.31 % / −0.79 % with t −1.2 / −3.1 full / post). Note for the memo: conditional on the rule being long (sig > 0) the Correction state is +0.61 % / +0.09 %, so the veto cuts a state the book earns in.
- D-3: 00:00 → 00:05 UTC drift on the nine (2024-01..2026-09, Binance 5 m): buys +0.05 bps (t 0.07), sells +3.79 bps (t 3.55), no-trade days +0.51 bps. The drift is in the SELLER's favour (prices rise before the book sells) and nil for buys. Decision (conservative): no cost is added and no gain is credited; daily-executed cells keep the 7.31 bps line. The effect is reported as "fill drift, favourable, not credited" in the memo.
- D-4: Delta MARK vs last-trade closes: sleeve sign agreement 99.61 / 99.86 / 99.89 %; |diff| median 2.5 bps, 95th pct 27.6 bps; daily rule Sharpe 0.994 (last-trade) vs 0.985 (MARK), weekly 0.704 vs 0.709. A third book may compute its signal from MARK closes (fewer outlier prints); the running books are not changed.
TIME-1__TIME2_signal_smooth tranche | B post Δ +0.147 [-0.03,+0.33] P≤0 0.05 sd 0.091 hurdle 0.227 | B full 0.90 vs 0.81 DD -13.9%/-17.0% | h1 +0.03 h2 +0.18 | A post +0.10 full +0.07 | C +0.21 | turn 2.9x fund 1.77% tax(seg) +4.3% vs +3.9%
TIME-1__K1_control tranche | B post Δ +0.105 [-0.19,+0.38] P≤0 0.23 sd 0.146 hurdle 0.364 | B full 0.86 vs 0.81 DD -16.0%/-17.0% | h1 -0.05 h2 +0.18 | A post +0.19 full +0.13 | C +0.31 | turn 8.0x fund 1.97% tax(seg) +2.7% vs +3.9%
SZ-1             daily   | B post Δ -0.058 [-0.15,+0.02] P≤0 0.93 sd 0.042 hurdle 0.105 | B full 0.80 vs 0.85 DD -24.2%/-24.7% | h1 -0.04 h2 -0.08 | A post -0.05 full -0.07 | C -0.12 | turn 12.5x fund 2.92% tax(seg) +3.2% vs +4.1%
SZ-1             weekly  | B post Δ -0.045 [-0.12,+0.02] P≤0 0.90 sd 0.036 hurdle 0.089 | B full 0.76 vs 0.81 DD -16.4%/-17.0% | h1 -0.04 h2 -0.07 | A post -0.03 full -0.06 | C -0.09 | turn 2.6x fund 1.80% tax(seg) +3.3% vs +3.9%
SZ-1__COM45      daily   | B post Δ -0.050 [-0.12,+0.01] P≤0 0.93 sd 0.033 hurdle 0.081 | B full 0.81 vs 0.85 DD -24.3%/-24.7% | h1 -0.03 h2 -0.06 | A post -0.05 full -0.07 | C -0.11 | turn 12.8x fund 2.96% tax(seg) +3.2% vs +4.1%
SZ-1__COM45      weekly  | B post Δ -0.047 [-0.10,+0.01] P≤0 0.95 sd 0.028 hurdle 0.070 | B full 0.77 vs 0.81 DD -16.5%/-17.0% | h1 -0.02 h2 -0.06 | A post -0.02 full -0.05 | C -0.08 | turn 2.7x fund 1.82% tax(seg) +3.3% vs +3.9%
SZ-1__COM90      daily   | B post Δ -0.072 [-0.20,+0.03] P≤0 0.90 sd 0.059 hurdle 0.146 | B full 0.78 vs 0.85 DD -24.0%/-24.7% | h1 -0.05 h2 -0.11 | A post -0.06 full -0.08 | C -0.12 | turn 12.0x fund 2.85% tax(seg) +3.1% vs +4.1%
SZ-1__COM90      weekly  | B post Δ -0.060 [-0.17,+0.04] P≤0 0.89 sd 0.053 hurdle 0.131 | B full 0.74 vs 0.81 DD -16.4%/-17.0% | h1 -0.05 h2 -0.09 | A post -0.02 full -0.07 | C -0.09 | turn 2.5x fund 1.76% tax(seg) +3.2% vs +3.9%
~~COST-2           daily   | B post Δ -0.356 [-1.10,+0.50] P≤0 0.78 sd 0.409 hurdle 1.020 | B full 0.33 vs 0.85 DD -2.9%/-24.7% | h1 -0.39 h2 -0.73 | A post -0.84 full -1.25 | C -0.99 | turn 0.2x fund 0.27% tax(seg) +0.3% vs +4.1%~~ (INVALID: simulator buffer bug, see engine note)
~~COST-2__m1       daily   | B post Δ -0.343 [-1.07,+0.52] P≤0 0.77 sd 0.407 hurdle 1.015 | B full 0.30 vs 0.85 DD -2.5%/-24.7% | h1 -0.43 h2 -0.72 | A post -0.84 full -1.25 | C -0.99 | turn 0.2x fund 0.22% tax(seg) +0.2% vs +4.1%~~ (INVALID: simulator buffer bug, see engine note)
~~COST-2__b025     daily   | B post Δ -0.346 [-1.10,+0.51] P≤0 0.77 sd 0.411 hurdle 1.026 | B full 0.34 vs 0.85 DD -2.9%/-24.7% | h1 -0.39 h2 -0.71 | A post -0.84 full -1.25 | C -0.99 | turn 0.2x fund 0.26% tax(seg) +0.3% vs +4.1%~~ (INVALID: simulator buffer bug, see engine note)
~~COST-2__COST1_F010 daily   | B post Δ +0.043 [-0.01,+0.10] P≤0 0.08 sd 0.029 hurdle 0.072 | B full 0.88 vs 0.85 DD -24.6%/-24.7% | h1 +0.02 h2 +0.05 | A post +0.04 full +0.02 | C +0.03 | turn 9.8x fund 3.13% tax(seg) +6.0% vs +4.1%~~ (INVALID: simulator buffer bug, see engine note)
~~COST-2__COST1_F020 daily   | B post Δ +0.046 [-0.08,+0.17] P≤0 0.24 sd 0.066 hurdle 0.164 | B full 0.87 vs 0.85 DD -24.0%/-24.7% | h1 +0.01 h2 +0.04 | A post +0.05 full +0.02 | C +0.07 | turn 7.0x fund 3.05% tax(seg) +6.6% vs +4.1%~~ (INVALID: simulator buffer bug, see engine note)
D_band10         daily   | B post Δ +0.005 [-0.01,+0.02] P≤0 0.31 sd 0.008 hurdle 0.050 | B full 0.85 vs 0.85 DD -24.8%/-24.7% | h1 -0.01 h2 +0.01 | A post +0.01 full +0.00 | C +0.03 | turn 12.8x fund 3.14% tax(seg) +4.4% vs +4.1%
UNI-2            daily   | B post Δ +0.093 [+0.01,+0.20] P≤0 0.01 sd 0.047 hurdle 0.118 | B full 0.96 vs 0.91 DD -23.9%/-24.0% | h1 -0.02 h2 +0.15 | A post +0.21 full +0.11 | C +0.00 | turn 15.6x fund 3.28% tax(seg) +5.3% vs +5.0%
UNI-2            weekly  | B post Δ +0.088 [+0.02,+0.18] P≤0 0.01 sd 0.042 hurdle 0.106 | B full 0.91 vs 0.86 DD -16.9%/-17.1% | h1 -0.02 h2 +0.14 | A post +0.20 full +0.10 | C +0.00 | turn 3.5x fund 2.02% tax(seg) +4.6% vs +4.4%
UNI-2__goldcap025 daily   | B post Δ +0.093 [+0.01,+0.20] P≤0 0.01 sd 0.047 hurdle 0.118 | B full 0.96 vs 0.91 DD -23.9%/-24.0% | h1 -0.02 h2 +0.15 | A post +0.17 full +0.09 | C +0.00 | turn 15.6x fund 3.28% tax(seg) +5.3% vs +5.0%
UNI-2__goldcap025 weekly  | B post Δ +0.088 [+0.02,+0.18] P≤0 0.01 sd 0.042 hurdle 0.106 | B full 0.91 vs 0.86 DD -16.9%/-17.1% | h1 -0.02 h2 +0.14 | A post +0.20 full +0.10 | C +0.00 | turn 3.5x fund 2.02% tax(seg) +4.6% vs +4.4%
~~COMBO-A          tranche | B post Δ -0.422 [-1.05,+0.34] P≤0 0.85 sd 0.354 hurdle 0.882 | B full 0.14 vs 0.81 DD -3.5%/-17.0% | h1 -0.68 h2 -0.78 | A post -0.66 full -1.12 | C -0.70 | turn 0.0x fund 0.15% tax(seg) +0.1% vs +3.9%~~ (INVALID: simulator buffer bug, see engine note)
~~COMBO-A__no_buffer tranche | B post Δ +0.115 [-0.06,+0.28] P≤0 0.08 sd 0.087 hurdle 0.216 | B full 0.87 vs 0.81 DD -13.7%/-17.0% | h1 +0.01 h2 +0.13 | A post +0.12 full +0.06 | C +0.19 | turn 2.6x fund 1.72% tax(seg) +4.3% vs +3.9%~~ (INVALID: simulator buffer bug, see engine note)
~~COMBO-A__cc60    tranche | B post Δ -0.392 [-1.07,+0.42] P≤0 0.81 sd 0.378 hurdle 0.942 | B full 0.18 vs 0.81 DD -4.1%/-17.0% | h1 -0.63 h2 -0.76 | A post -0.66 full -1.12 | C -0.70 | turn 0.0x fund 0.19% tax(seg) +0.1% vs +3.9%~~ (INVALID: simulator buffer bug, see engine note)

## Engine note 2026-10-21 (bug fix, not a plan change)
The first COST-2 / COMBO-A runs applied the 0.75-contract floor on unrounded lines (equity 1.0, so the floor dwarfed every target and the book almost never traded) and centred the buffer on the rounded target instead of the unrounded u. Fixed in sim.simulate to the plan's rule (B = max(b|u|, m contracts) on whole-contract lines, b|u| unrounded; edge to the nearest integer inside the band, else round(u); u = 0 closes). Baseline reproduction re-verified (1e-15). COST-2 and COMBO-A rerun below.

COST-2           daily   | B post Δ +0.030 [-0.01,+0.07] P≤0 0.06 sd 0.019 hurdle 0.050 | B full 0.87 vs 0.85 DD -24.6%/-24.7% | h1 +0.00 h2 +0.04 | A post +0.03 full +0.02 | C +0.03 | turn 11.0x fund 3.13% tax(seg) +5.4% vs +4.1%
COST-2__m1       daily   | B post Δ +0.030 [-0.01,+0.07] P≤0 0.06 sd 0.019 hurdle 0.050 | B full 0.87 vs 0.85 DD -24.6%/-24.7% | h1 +0.00 h2 +0.04 | A post +0.03 full +0.02 | C +0.03 | turn 11.0x fund 3.13% tax(seg) +5.4% vs +4.1%
COST-2__b025     daily   | B post Δ +0.034 [-0.07,+0.13] P≤0 0.27 sd 0.052 hurdle 0.130 | B full 0.84 vs 0.85 DD -23.6%/-24.7% | h1 -0.05 h2 +0.04 | A post +0.04 full -0.00 | C +0.07 | turn 8.3x fund 2.97% tax(seg) +5.6% vs +4.1%
COST-2__COST1_F010 daily   | B post Δ +0.043 [-0.01,+0.10] P≤0 0.08 sd 0.029 hurdle 0.072 | B full 0.88 vs 0.85 DD -24.6%/-24.7% | h1 +0.02 h2 +0.05 | A post +0.04 full +0.02 | C +0.03 | turn 9.8x fund 3.13% tax(seg) +6.0% vs +4.1%
COST-2__COST1_F020 daily   | B post Δ +0.046 [-0.08,+0.17] P≤0 0.24 sd 0.066 hurdle 0.164 | B full 0.87 vs 0.85 DD -24.0%/-24.7% | h1 +0.01 h2 +0.04 | A post +0.05 full +0.02 | C +0.07 | turn 7.0x fund 3.05% tax(seg) +6.6% vs +4.1%
D_band10         daily   | B post Δ +0.005 [-0.01,+0.02] P≤0 0.31 sd 0.008 hurdle 0.050 | B full 0.85 vs 0.85 DD -24.8%/-24.7% | h1 -0.01 h2 +0.01 | A post +0.01 full +0.00 | C +0.03 | turn 12.8x fund 3.14% tax(seg) +4.4% vs +4.1%
COMBO-A          tranche | B post Δ +0.123 [-0.05,+0.29] P≤0 0.07 sd 0.087 hurdle 0.216 | B full 0.87 vs 0.81 DD -14.0%/-17.0% | h1 +0.02 h2 +0.13 | A post +0.13 full +0.08 | C +0.19 | turn 2.2x fund 1.72% tax(seg) +4.6% vs +3.9%
COMBO-A__no_buffer tranche | B post Δ +0.115 [-0.06,+0.28] P≤0 0.08 sd 0.087 hurdle 0.216 | B full 0.87 vs 0.81 DD -13.7%/-17.0% | h1 +0.01 h2 +0.13 | A post +0.12 full +0.06 | C +0.19 | turn 2.6x fund 1.72% tax(seg) +4.3% vs +3.9%
COMBO-A__cc60    tranche | B post Δ +0.170 [+0.04,+0.33] P≤0 0.01 sd 0.074 hurdle 0.185 | B full 0.91 vs 0.81 DD -14.6%/-17.0% | h1 +0.04 h2 +0.19 | A post +0.16 full +0.13 | C +0.27 | turn 2.4x fund 1.85% tax(seg) +5.2% vs +3.9%
SIG-2_selftest   daily   | (no B panel)
SIG-2__d0.5_selftest daily   | (no B panel)
SIG-2__d1.5_selftest daily   | (no B panel)
SIG-2__SIG1A_form_selftest daily   | (no B panel)
SIG-1B_selftest  daily   | (no B panel)
SIG-1B__t0.75_selftest daily   | (no B panel)
SIG-1B__t1.25_selftest daily   | (no B panel)
SIG-3a_selftest  daily   | (no B panel)
SIG-3a__speed_x0.75_selftest daily   | (no B panel)
SIG-3a__speed_x1.25_selftest daily   | (no B panel)
SIG-3b_selftest  daily   | (no B panel)
SIG-3b__denom15_selftest daily   | (no B panel)
SIG-3b__denom30_selftest daily   | (no B panel)
SIG-4_selftest   daily   | (no B panel)
SIG-4__7_lookbacks_selftest daily   | (no B panel)
SIG-4__paper_sizing_selftest daily   | (no B panel)
SIG-4__same_day_norm_selftest daily   | (no B panel)
SIG-7A_selftest  daily   | (no B panel)
SIG-7A__L200_selftest daily   | (no B panel)
SIG-7A__L300_selftest daily   | (no B panel)
SIG-10_selftest  daily   | (no B panel)
SIG-10__map_0_25_50_100_selftest daily   | (no B panel)
SIG-10__map_0_50_75_100_selftest daily   | (no B panel)
SIG-11_selftest  daily   | (no B panel)
SIG-11__control_breakout_only_selftest daily   | (no B panel)
SIG-11__looks_20_80_160_selftest daily   | (no B panel)
SIG-11__smooth_L8_selftest daily   | (no B panel)
SIG-13_selftest  daily   | (no B panel)
SIG-13__sleeve120_only_selftest daily   | (no B panel)
SIG-13__funding_x2_selftest daily   | (no B panel)
SZ-3_selftest    daily   | (no B panel)
SZ-3__wfast06_selftest daily   | (no B panel)
SZ-3__wfast08_selftest daily   | (no B panel)
SZ-6b_selftest   daily   | (no B panel)
SZ-6b__ref060_selftest daily   | (no B panel)
SZ-6b__ref080_selftest daily   | (no B panel)
SZ-13_selftest   daily   | (no B panel)
SZ-13__thr2_exit16_selftest daily   | (no B panel)
SZ-13__exit09_selftest daily   | (no B panel)
SZ-17_selftest   daily   | (no B panel)
SZ-17__COM30_selftest daily   | (no B panel)
SZ-17__COM90_selftest daily   | (no B panel)
SZ-13_selftest   daily   | (no B panel)
SZ-13__thr2_exit16_selftest daily   | (no B panel)
SZ-13__exit09_selftest daily   | (no B panel)
OVL-2_selftest   daily   | (no B panel)
OVL-2__14d40_selftest daily   | (no B panel)
OVL-2__30d40_selftest daily   | (no B panel)
OVL-3_selftest   daily   | (no B panel)
TIME-3_selftest  daily   | (no B panel)
TIME-3__all24_selftest daily   | (no B panel)
TIME-3__h0_8_16_selftest daily   | (no B panel)
COMBO-B_selftest daily   | (no B panel)
COMBO-B__no_buffer_selftest daily   | (no B panel)
COMBO-B__cc60_selftest daily   | (no B panel)
COMBO-C_selftest daily   | (no B panel)
COMBO-C__h0_8_16_K7_selftest daily   | (no B panel)
COMBO-C__six_K5_selftest daily   | (no B panel)
TIME-4_selftest  weekly  | (no B panel)
TIME-4__mon_fri_selftest weekly  | (no B panel)
TIME-4__full_gap_selftest weekly  | (no B panel)
D-0_selftest     daily   | (no B panel)
UNI-1_selftest   daily   | (no B panel)
UNI-1__age121_selftest daily   | (no B panel)
UNI-1__quarterly_selftest daily   | (no B panel)
UNI-1__N12_selftest daily   | (no B panel)
SZ-3             daily   | B post Δ -0.060 [-0.15,+0.04] P≤0 0.89 sd 0.050 hurdle 0.124 | B full 0.81 vs 0.85 DD -24.1%/-24.7% | h1 -0.01 h2 -0.07 | A post -0.06 full -0.05 | C -0.14 | turn 13.1x fund 3.03% tax(seg) +3.1% vs +4.1%
SZ-3             weekly  | B post Δ -0.066 [-0.15,+0.03] P≤0 0.93 sd 0.044 hurdle 0.110 | B full 0.77 vs 0.81 DD -16.5%/-17.0% | h1 -0.01 h2 -0.08 | A post -0.03 full -0.03 | C -0.12 | turn 2.8x fund 1.87% tax(seg) +3.3% vs +3.9%
SIG-2            daily   | B post Δ +0.016 [-0.17,+0.23] P≤0 0.44 sd 0.101 hurdle 0.253 | B full 0.81 vs 0.85 DD -24.3%/-24.7% | h1 -0.10 h2 +0.04 | A post -0.07 full -0.10 | C -0.14 | turn 9.4x fund 2.83% tax(seg) +4.0% vs +4.1%
SIG-2            weekly  | B post Δ -0.128 [-0.33,+0.04] P≤0 0.93 sd 0.093 hurdle 0.233 | B full 0.69 vs 0.81 DD -16.7%/-17.0% | h1 -0.13 h2 -0.11 | A post -0.22 full -0.15 | C -0.23 | turn 2.3x fund 1.70% tax(seg) +2.7% vs +3.9%
SZ-3__wfast06    daily   | B post Δ -0.072 [-0.17,+0.03] P≤0 0.93 sd 0.050 hurdle 0.125 | B full 0.80 vs 0.85 DD -24.2%/-24.7% | h1 -0.02 h2 -0.10 | A post -0.06 full -0.06 | C -0.14 | turn 12.8x fund 3.01% tax(seg) +3.0% vs +4.1%
SZ-3__wfast06    weekly  | B post Δ -0.080 [-0.16,+0.01] P≤0 0.96 sd 0.044 hurdle 0.109 | B full 0.75 vs 0.81 DD -16.6%/-17.0% | h1 -0.02 h2 -0.11 | A post -0.04 full -0.04 | C -0.12 | turn 2.7x fund 1.86% tax(seg) +3.2% vs +3.9%
SIG-2__d0.5      daily   | B post Δ +0.014 [-0.23,+0.26] P≤0 0.47 sd 0.124 hurdle 0.309 | B full 0.84 vs 0.85 DD -27.3%/-24.7% | h1 -0.06 h2 +0.05 | A post -0.06 full -0.10 | C -0.09 | turn 11.9x fund 3.29% tax(seg) +4.8% vs +4.1%
SIG-2__d0.5      weekly  | B post Δ -0.133 [-0.34,+0.06] P≤0 0.92 sd 0.101 hurdle 0.253 | B full 0.72 vs 0.81 DD -18.6%/-17.0% | h1 -0.06 h2 -0.13 | A post -0.19 full -0.11 | C -0.17 | turn 2.8x fund 2.02% tax(seg) +3.5% vs +3.9%
SZ-3__wfast08    daily   | B post Δ -0.048 [-0.14,+0.06] P≤0 0.83 sd 0.051 hurdle 0.128 | B full 0.83 vs 0.85 DD -24.1%/-24.7% | h1 -0.00 h2 -0.05 | A post -0.05 full -0.05 | C -0.14 | turn 13.4x fund 3.06% tax(seg) +3.2% vs +4.1%
SZ-3__wfast08    weekly  | B post Δ -0.057 [-0.14,+0.05] P≤0 0.89 sd 0.048 hurdle 0.119 | B full 0.79 vs 0.81 DD -16.4%/-17.0% | h1 +0.01 h2 -0.07 | A post -0.02 full -0.02 | C -0.12 | turn 2.9x fund 1.89% tax(seg) +3.3% vs +3.9%
SZ-6b            daily   | B post Δ +0.011 [-0.03,+0.05] P≤0 0.32 sd 0.021 hurdle 0.052 | B full 0.85 vs 0.85 DD -26.9%/-24.7% | h1 -0.01 h2 +0.00 | A post -0.01 full -0.02 | C -0.01 | turn 14.8x fund 3.41% tax(seg) +4.4% vs +4.1%
SZ-6b            weekly  | B post Δ +0.001 [-0.04,+0.04] P≤0 0.51 sd 0.020 hurdle 0.050 | B full 0.79 vs 0.81 DD -18.5%/-17.0% | h1 -0.02 h2 -0.02 | A post -0.01 full -0.02 | C -0.01 | turn 3.2x fund 2.09% tax(seg) +4.2% vs +3.9%
SIG-2__d1.5      daily   | B post Δ +0.019 [-0.15,+0.23] P≤0 0.41 sd 0.097 hurdle 0.241 | B full 0.78 vs 0.85 DD -20.9%/-24.7% | h1 -0.15 h2 +0.05 | A post -0.06 full -0.09 | C -0.13 | turn 7.5x fund 2.35% tax(seg) +3.3% vs +4.1%
SIG-2__d1.5      weekly  | B post Δ -0.123 [-0.33,+0.05] P≤0 0.92 sd 0.097 hurdle 0.241 | B full 0.67 vs 0.81 DD -13.6%/-17.0% | h1 -0.16 h2 -0.11 | A post -0.22 full -0.16 | C -0.26 | turn 1.9x fund 1.41% tax(seg) +2.2% vs +3.9%
SIG-2__SIG1A_form daily   | B post Δ -0.008 [-0.20,+0.21] P≤0 0.52 sd 0.104 hurdle 0.260 | B full 0.79 vs 0.85 DD -24.5%/-24.7% | h1 -0.12 h2 +0.02 | A post -0.09 full -0.11 | C -0.16 | turn 9.6x fund 2.84% tax(seg) +3.7% vs +4.1%
SIG-2__SIG1A_form weekly  | B post Δ -0.135 [-0.35,+0.07] P≤0 0.91 sd 0.108 hurdle 0.268 | B full 0.69 vs 0.81 DD -16.5%/-17.0% | h1 -0.12 h2 -0.11 | A post -0.22 full -0.15 | C -0.25 | turn 2.4x fund 1.72% tax(seg) +2.7% vs +3.9%
SZ-6b__ref060    daily   | B post Δ +0.012 [-0.03,+0.05] P≤0 0.30 sd 0.022 hurdle 0.054 | B full 0.85 vs 0.85 DD -25.2%/-24.7% | h1 -0.01 h2 +0.00 | A post -0.01 full -0.02 | C -0.00 | turn 13.9x fund 3.18% tax(seg) +4.1% vs +4.1%
SZ-6b__ref060    weekly  | B post Δ -0.001 [-0.04,+0.04] P≤0 0.55 sd 0.021 hurdle 0.052 | B full 0.79 vs 0.81 DD -17.3%/-17.0% | h1 -0.01 h2 -0.02 | A post -0.01 full -0.02 | C -0.00 | turn 3.0x fund 1.95% tax(seg) +3.9% vs +3.9%
SZ-6b__ref080    daily   | B post Δ +0.009 [-0.03,+0.05] P≤0 0.34 sd 0.020 hurdle 0.051 | B full 0.84 vs 0.85 DD -28.4%/-24.7% | h1 -0.01 h2 -0.00 | A post -0.01 full -0.02 | C -0.01 | turn 15.7x fund 3.63% tax(seg) +4.7% vs +4.1%
SZ-6b__ref080    weekly  | B post Δ +0.003 [-0.04,+0.04] P≤0 0.47 sd 0.020 hurdle 0.050 | B full 0.80 vs 0.81 DD -19.6%/-17.0% | h1 -0.01 h2 -0.01 | A post -0.01 full -0.02 | C -0.01 | turn 3.4x fund 2.22% tax(seg) +4.5% vs +3.9%
SIG-1B           daily   | B post Δ -0.115 [-0.39,+0.22] P≤0 0.76 sd 0.154 hurdle 0.384 | B full 0.59 vs 0.85 DD -18.3%/-24.7% | h1 -0.39 h2 -0.08 | A post -0.13 full -0.22 | C -0.33 | turn 8.0x fund 1.90% tax(seg) +0.1% vs +4.1%
SIG-1B           weekly  | B post Δ -0.157 [-0.46,+0.16] P≤0 0.83 sd 0.157 hurdle 0.392 | B full 0.56 vs 0.81 DD -11.6%/-17.0% | h1 -0.33 h2 -0.13 | A post -0.22 full -0.21 | C -0.40 | turn 1.8x fund 1.12% tax(seg) +0.9% vs +3.9%
SIG-1B__t0.75    daily   | B post Δ -0.032 [-0.25,+0.22] P≤0 0.58 sd 0.119 hurdle 0.296 | B full 0.70 vs 0.85 DD -21.1%/-24.7% | h1 -0.24 h2 -0.01 | A post -0.15 full -0.18 | C -0.38 | turn 9.6x fund 2.36% tax(seg) +1.5% vs +4.1%
SIG-1B__t0.75    weekly  | B post Δ -0.034 [-0.29,+0.22] P≤0 0.59 sd 0.131 hurdle 0.327 | B full 0.72 vs 0.81 DD -14.9%/-17.0% | h1 -0.20 h2 +0.06 | A post -0.25 full -0.16 | C -0.35 | turn 2.2x fund 1.41% tax(seg) +2.2% vs +3.9%
SZ-13            daily   | (no B panel)
SZ-13            weekly  | (no B panel)
SIG-1B__t1.25    daily   | B post Δ -0.000 [-0.35,+0.43] P≤0 0.46 sd 0.200 hurdle 0.500 | B full 0.69 vs 0.85 DD -9.7%/-24.7% | h1 -0.25 h2 -0.04 | A post -0.13 full -0.18 | C -0.44 | turn 6.2x fund 1.40% tax(seg) +0.8% vs +4.1%
SIG-1B__t1.25    weekly  | B post Δ -0.322 [-0.77,+0.09] P≤0 0.92 sd 0.219 hurdle 0.546 | B full 0.49 vs 0.81 DD -6.5%/-17.0% | h1 -0.33 h2 -0.32 | A post -0.31 full -0.30 | C -0.55 | turn 1.4x fund 0.82% tax(seg) +0.3% vs +3.9%
SZ-13__thr2_exit16 daily   | (no B panel)
SZ-13__thr2_exit16 weekly  | (no B panel)
SIG-3a           daily   | B post Δ -0.105 [-0.48,+0.30] P≤0 0.65 sd 0.200 hurdle 0.497 | B full 0.79 vs 0.85 DD -28.9%/-24.7% | h1 +0.06 h2 -0.25 | A post -0.28 full -0.22 | C -0.46 | turn 4.6x fund 3.61% tax(seg) +6.5% vs +4.1%
SIG-3a           weekly  | B post Δ -0.074 [-0.42,+0.33] P≤0 0.60 sd 0.190 hurdle 0.474 | B full 0.76 vs 0.81 DD -21.2%/-17.0% | h1 -0.01 h2 -0.11 | A post -0.15 full -0.09 | C -0.11 | turn 1.6x fund 2.33% tax(seg) +4.9% vs +3.9%
SIG-3a__speed_x0.75 daily   | B post Δ -0.036 [-0.36,+0.31] P≤0 0.55 sd 0.172 hurdle 0.429 | B full 0.83 vs 0.85 DD -26.6%/-24.7% | h1 +0.09 h2 -0.18 | A post -0.20 full -0.15 | C -0.28 | turn 5.3x fund 3.67% tax(seg) +7.4% vs +4.1%
SIG-3a__speed_x0.75 weekly  | B post Δ -0.046 [-0.30,+0.26] P≤0 0.58 sd 0.142 hurdle 0.354 | B full 0.78 vs 0.81 DD -21.4%/-17.0% | h1 -0.03 h2 -0.05 | A post -0.16 full -0.09 | C -0.07 | turn 2.0x fund 2.32% tax(seg) +5.0% vs +3.9%
SZ-13__exit09    daily   | (no B panel)
SZ-13__exit09    weekly  | (no B panel)
SIG-3a__speed_x1.25 daily   | B post Δ -0.148 [-0.55,+0.31] P≤0 0.70 sd 0.219 hurdle 0.545 | B full 0.79 vs 0.85 DD -27.7%/-24.7% | h1 +0.09 h2 -0.30 | A post -0.34 full -0.25 | C -0.47 | turn 4.2x fund 3.56% tax(seg) +6.6% vs +4.1%
SIG-3a__speed_x1.25 weekly  | B post Δ -0.141 [-0.52,+0.30] P≤0 0.71 sd 0.210 hurdle 0.524 | B full 0.75 vs 0.81 DD -19.5%/-17.0% | h1 +0.03 h2 -0.20 | A post -0.28 full -0.16 | C -0.27 | turn 1.4x fund 2.30% tax(seg) +4.7% vs +3.9%
SIG-3b           daily   | B post Δ -0.127 [-0.53,+0.35] P≤0 0.65 sd 0.224 hurdle 0.559 | B full 0.73 vs 0.85 DD -10.9%/-24.7% | h1 -0.04 h2 -0.25 | A post -0.37 full -0.35 | C -0.62 | turn 1.6x fund 1.31% tax(seg) +1.8% vs +4.1%
SIG-3b           weekly  | B post Δ -0.091 [-0.50,+0.43] P≤0 0.57 sd 0.236 hurdle 0.587 | B full 0.71 vs 0.81 DD -7.6%/-17.0% | h1 -0.04 h2 -0.18 | A post -0.20 full -0.19 | C -0.32 | turn 0.6x fund 0.83% tax(seg) +1.5% vs +3.9%
SZ-17            daily   | (no B panel)
SZ-17            weekly  | (no B panel)
SZ-17__COM30     daily   | (no B panel)
SZ-17__COM30     weekly  | (no B panel)
SIG-3b__denom15  daily   | B post Δ -0.129 [-0.53,+0.34] P≤0 0.66 sd 0.221 hurdle 0.552 | B full 0.73 vs 0.85 DD -14.4%/-24.7% | h1 -0.04 h2 -0.25 | A post -0.36 full -0.34 | C -0.61 | turn 2.1x fund 1.73% tax(seg) +2.5% vs +4.1%
SIG-3b__denom15  weekly  | B post Δ -0.096 [-0.50,+0.42] P≤0 0.58 sd 0.234 hurdle 0.584 | B full 0.71 vs 0.81 DD -10.0%/-17.0% | h1 -0.04 h2 -0.18 | A post -0.21 full -0.19 | C -0.30 | turn 0.8x fund 1.09% tax(seg) +2.0% vs +3.9%
SZ-17__COM90     daily   | (no B panel)
SZ-17__COM90     weekly  | (no B panel)
SIG-3b__denom30  daily   | B post Δ -0.127 [-0.53,+0.35] P≤0 0.65 sd 0.224 hurdle 0.559 | B full 0.73 vs 0.85 DD -7.4%/-24.7% | h1 -0.04 h2 -0.25 | A post -0.37 full -0.35 | C -0.62 | turn 1.1x fund 0.87% tax(seg) +1.2% vs +4.1%
SIG-3b__denom30  weekly  | B post Δ -0.093 [-0.50,+0.43] P≤0 0.57 sd 0.236 hurdle 0.590 | B full 0.71 vs 0.81 DD -5.1%/-17.0% | h1 -0.04 h2 -0.18 | A post -0.21 full -0.20 | C -0.32 | turn 0.4x fund 0.56% tax(seg) +1.0% vs +3.9%
SIG-4            daily   | B post Δ +0.008 [-0.28,+0.32] P≤0 0.49 sd 0.154 hurdle 0.383 | B full 0.83 vs 0.85 DD -19.6%/-24.7% | h1 -0.05 h2 +0.03 | A post -0.20 full -0.14 | C -0.37 | turn 8.8x fund 2.76% tax(seg) +3.7% vs +4.1%
SIG-4            weekly  | B post Δ -0.049 [-0.34,+0.22] P≤0 0.63 sd 0.143 hurdle 0.357 | B full 0.72 vs 0.81 DD -12.0%/-17.0% | h1 -0.06 h2 -0.14 | A post -0.27 full -0.18 | C -0.40 | turn 2.9x fund 1.63% tax(seg) +2.3% vs +3.9%
SIG-4__7_lookbacks daily   | B post Δ +0.040 [-0.29,+0.36] P≤0 0.42 sd 0.165 hurdle 0.412 | B full 0.86 vs 0.85 DD -22.6%/-24.7% | h1 -0.08 h2 +0.12 | A post -0.17 full -0.13 | C -0.36 | turn 11.0x fund 2.88% tax(seg) +4.1% vs +4.1%
SIG-4__7_lookbacks weekly  | B post Δ -0.023 [-0.36,+0.27] P≤0 0.57 sd 0.161 hurdle 0.400 | B full 0.74 vs 0.81 DD -12.0%/-17.0% | h1 -0.06 h2 -0.08 | A post -0.25 full -0.17 | C -0.44 | turn 3.6x fund 1.68% tax(seg) +2.6% vs +3.9%
SIG-4__paper_sizing daily   | B post Δ -0.013 [-0.31,+0.25] P≤0 0.53 sd 0.141 hurdle 0.351 | B full 0.80 vs 0.85 DD -21.4%/-24.7% | h1 -0.10 h2 +0.02 | A post -0.23 full -0.21 | C -0.36 | turn 8.3x fund 2.65% tax(seg) +3.3% vs +4.1%
SIG-4__paper_sizing weekly  | B post Δ -0.056 [-0.37,+0.21] P≤0 0.66 sd 0.149 hurdle 0.371 | B full 0.69 vs 0.81 DD -12.8%/-17.0% | h1 -0.09 h2 -0.16 | A post -0.28 full -0.26 | C -0.39 | turn 2.8x fund 1.56% tax(seg) +2.1% vs +3.9%
SIG-4__same_day_norm daily   | B post Δ +0.008 [-0.28,+0.32] P≤0 0.49 sd 0.154 hurdle 0.383 | B full 0.70 vs 0.85 DD -19.6%/-24.7% | h1 -0.31 h2 +0.03 | A post -0.20 full -0.49 | C -0.94 | turn 7.6x fund 1.92% tax(seg) +2.1% vs +4.1%
SIG-4__same_day_norm weekly  | B post Δ -0.049 [-0.34,+0.22] P≤0 0.63 sd 0.143 hurdle 0.357 | B full 0.53 vs 0.81 DD -12.0%/-17.0% | h1 -0.38 h2 -0.14 | A post -0.27 full -0.61 | C -1.01 | turn 2.5x fund 1.12% tax(seg) +0.9% vs +3.9%
SIG-7A           daily   | B post Δ -0.229 [-0.46,+0.02] P≤0 0.96 sd 0.124 hurdle 0.308 | B full 0.74 vs 0.85 DD -24.8%/-24.7% | h1 -0.03 h2 -0.24 | A post -0.19 full -0.10 | C -0.06 | turn 11.8x fund 3.11% tax(seg) +2.2% vs +4.1%
SIG-7A           weekly  | B post Δ -0.061 [-0.27,+0.20] P≤0 0.65 sd 0.120 hurdle 0.299 | B full 0.83 vs 0.81 DD -14.8%/-17.0% | h1 +0.07 h2 -0.06 | A post -0.00 full +0.04 | C +0.04 | turn 2.5x fund 1.95% tax(seg) +3.8% vs +3.9%
SIG-7A__L200     daily   | B post Δ -0.195 [-0.41,+0.03] P≤0 0.95 sd 0.112 hurdle 0.280 | B full 0.76 vs 0.85 DD -24.6%/-24.7% | h1 +0.00 h2 -0.22 | A post -0.19 full -0.08 | C -0.37 | turn 12.1x fund 3.01% tax(seg) +2.6% vs +4.1%
SIG-7A__L200     weekly  | B post Δ -0.031 [-0.22,+0.20] P≤0 0.58 sd 0.108 hurdle 0.269 | B full 0.86 vs 0.81 DD -13.7%/-17.0% | h1 +0.14 h2 -0.09 | A post -0.00 full +0.07 | C -0.18 | turn 2.5x fund 1.91% tax(seg) +4.2% vs +3.9%
SIG-7A__L300     daily   | B post Δ -0.019 [-0.21,+0.21] P≤0 0.54 sd 0.107 hurdle 0.266 | B full 0.86 vs 0.85 DD -22.7%/-24.7% | h1 +0.09 h2 -0.11 | A post -0.05 full -0.02 | C -0.04 | turn 11.4x fund 3.12% tax(seg) +4.1% vs +4.1%
SIG-7A__L300     weekly  | B post Δ +0.010 [-0.19,+0.26] P≤0 0.41 sd 0.114 hurdle 0.284 | B full 0.86 vs 0.81 DD -15.1%/-17.0% | h1 +0.12 h2 -0.07 | A post +0.04 full +0.05 | C +0.09 | turn 2.4x fund 1.95% tax(seg) +4.1% vs +3.9%
SIG-10           daily   | B post Δ -0.063 [-0.37,+0.24] P≤0 0.65 sd 0.154 hurdle 0.385 | B full 0.82 vs 0.85 DD -31.2%/-24.7% | h1 -0.04 h2 -0.03 | A post -0.09 full -0.07 | C -0.11 | turn 15.0x fund 3.69% tax(seg) +4.5% vs +4.1%
SIG-10           weekly  | B post Δ -0.149 [-0.39,+0.11] P≤0 0.86 sd 0.125 hurdle 0.313 | B full 0.71 vs 0.81 DD -21.7%/-17.0% | h1 -0.05 h2 -0.17 | A post -0.08 full -0.05 | C -0.07 | turn 3.3x fund 2.28% tax(seg) +3.7% vs +3.9%
SIG-10__map_0_25_50_100 daily   | B post Δ -0.071 [-0.29,+0.14] P≤0 0.73 sd 0.110 hurdle 0.275 | B full 0.82 vs 0.85 DD -28.9%/-24.7% | h1 -0.03 h2 -0.04 | A post -0.08 full -0.05 | C -0.10 | turn 14.3x fund 3.46% tax(seg) +4.0% vs +4.1%
SIG-10__map_0_25_50_100 weekly  | B post Δ -0.119 [-0.30,+0.06] P≤0 0.89 sd 0.093 hurdle 0.232 | B full 0.74 vs 0.81 DD -20.2%/-17.0% | h1 -0.04 h2 -0.12 | A post -0.05 full -0.03 | C -0.03 | turn 3.1x fund 2.13% tax(seg) +3.6% vs +3.9%
SIG-10__map_0_50_75_100 daily   | B post Δ -0.116 [-0.50,+0.27] P≤0 0.72 sd 0.195 hurdle 0.487 | B full 0.78 vs 0.85 DD -34.2%/-24.7% | h1 -0.07 h2 -0.07 | A post -0.15 full -0.12 | C -0.18 | turn 15.4x fund 3.88% tax(seg) +4.1% vs +4.1%
SIG-10__map_0_50_75_100 weekly  | B post Δ -0.208 [-0.51,+0.12] P≤0 0.88 sd 0.160 hurdle 0.399 | B full 0.66 vs 0.81 DD -23.8%/-17.0% | h1 -0.09 h2 -0.23 | A post -0.11 full -0.08 | C -0.09 | turn 3.4x fund 2.38% tax(seg) +3.3% vs +3.9%
SIG-11           daily   | B post Δ +0.011 [-0.07,+0.10] P≤0 0.36 sd 0.044 hurdle 0.111 | B full 0.86 vs 0.85 DD -18.5%/-24.7% | h1 +0.01 h2 +0.02 | A post -0.08 full -0.05 | C -0.12 | turn 8.0x fund 2.50% tax(seg) +4.2% vs +4.1%
SIG-11           weekly  | B post Δ -0.020 [-0.10,+0.07] P≤0 0.67 sd 0.043 hurdle 0.108 | B full 0.78 vs 0.81 DD -13.6%/-17.0% | h1 -0.06 h2 +0.02 | A post -0.08 full -0.05 | C -0.06 | turn 2.1x fund 1.53% tax(seg) +3.0% vs +3.9%
SIG-11__control_breakout_only daily   | B post Δ +0.001 [-0.23,+0.25] P≤0 0.45 sd 0.122 hurdle 0.304 | B full 0.85 vs 0.85 DD -12.9%/-24.7% | h1 -0.02 h2 +0.03 | A post -0.24 full -0.17 | C -0.37 | turn 3.6x fund 1.86% tax(seg) +3.5% vs +4.1%
SIG-11__control_breakout_only weekly  | B post Δ -0.072 [-0.30,+0.16] P≤0 0.71 sd 0.118 hurdle 0.294 | B full 0.73 vs 0.81 DD -10.5%/-17.0% | h1 -0.18 h2 +0.05 | A post -0.25 full -0.15 | C -0.14 | turn 1.6x fund 1.12% tax(seg) +1.8% vs +3.9%
SIG-11__looks_20_80_160 daily   | B post Δ -0.014 [-0.11,+0.08] P≤0 0.56 sd 0.050 hurdle 0.125 | B full 0.84 vs 0.85 DD -19.0%/-24.7% | h1 -0.02 h2 +0.00 | A post -0.11 full -0.07 | C -0.18 | turn 7.8x fund 2.40% tax(seg) +3.7% vs +4.1%
SIG-11__looks_20_80_160 weekly  | B post Δ -0.027 [-0.12,+0.07] P≤0 0.67 sd 0.050 hurdle 0.124 | B full 0.77 vs 0.81 DD -13.4%/-17.0% | h1 -0.07 h2 +0.01 | A post -0.08 full -0.04 | C -0.08 | turn 1.9x fund 1.47% tax(seg) +2.8% vs +3.9%
SIG-11__smooth_L8 daily   | B post Δ +0.048 [-0.04,+0.14] P≤0 0.15 sd 0.046 hurdle 0.115 | B full 0.89 vs 0.85 DD -18.7%/-24.7% | h1 +0.01 h2 +0.07 | A post -0.04 full -0.03 | C -0.09 | turn 8.9x fund 2.63% tax(seg) +4.6% vs +4.1%
SIG-11__smooth_L8 weekly  | B post Δ +0.010 [-0.09,+0.11] P≤0 0.43 sd 0.050 hurdle 0.124 | B full 0.81 vs 0.81 DD -13.4%/-17.0% | h1 -0.03 h2 +0.05 | A post -0.09 full -0.04 | C -0.07 | turn 2.3x fund 1.59% tax(seg) +3.3% vs +3.9%
SIG-13           daily   | B post Δ -0.036 [-0.09,+0.04] P≤0 0.83 sd 0.034 hurdle 0.085 | B full 0.79 vs 0.85 DD -24.2%/-24.7% | h1 -0.07 h2 -0.06 | A post -0.03 full -0.07 | C -0.11 | turn 13.4x fund 2.83% tax(seg) +2.6% vs +4.1%
SIG-13           weekly  | B post Δ -0.016 [-0.10,+0.06] P≤0 0.73 sd 0.039 hurdle 0.097 | B full 0.80 vs 0.81 DD -15.9%/-17.0% | h1 -0.03 h2 +0.02 | A post -0.03 full -0.05 | C +0.00 | turn 2.9x fund 1.74% tax(seg) +3.5% vs +3.9%
SIG-13__sleeve120_only daily   | B post Δ -0.024 [-0.07,+0.03] P≤0 0.78 sd 0.025 hurdle 0.063 | B full 0.84 vs 0.85 DD -23.5%/-24.7% | h1 +0.01 h2 -0.03 | A post +0.01 full +0.00 | C -0.01 | turn 13.4x fund 3.02% tax(seg) +3.8% vs +4.1%
SIG-13__sleeve120_only weekly  | B post Δ -0.014 [-0.06,+0.03] P≤0 0.76 sd 0.023 hurdle 0.056 | B full 0.80 vs 0.81 DD -16.6%/-17.0% | h1 -0.01 h2 -0.01 | A post -0.01 full -0.00 | C +0.03 | turn 2.9x fund 1.86% tax(seg) +3.7% vs +3.9%
SIG-13__funding_x2 daily   | B post Δ -0.018 [-0.12,+0.11] P≤0 0.61 sd 0.057 hurdle 0.141 | B full 0.77 vs 0.85 DD -23.2%/-24.7% | h1 -0.12 h2 -0.04 | A post +0.01 full -0.06 | C -0.12 | turn 13.3x fund 2.47% tax(seg) +2.0% vs +4.1%
SIG-13__funding_x2 weekly  | B post Δ -0.019 [-0.13,+0.08] P≤0 0.66 sd 0.055 hurdle 0.136 | B full 0.78 vs 0.81 DD -14.5%/-17.0% | h1 -0.05 h2 +0.01 | A post -0.08 full -0.05 | C -0.04 | turn 2.8x fund 1.49% tax(seg) +3.1% vs +3.9%
D-0              daily   | (no B panel)
D-0              weekly  | (no B panel)
UNI-1            daily   | (no B panel)
UNI-1            weekly  | (no B panel)
UNI-1__age121    daily   | (no B panel)
UNI-1__age121    weekly  | (no B panel)
UNI-1__quarterly daily   | (no B panel)
UNI-1__quarterly weekly  | (no B panel)
UNI-1__N12       daily   | (no B panel)
UNI-1__N12       weekly  | (no B panel)
OVL-2            daily   | B post Δ +0.138 [-0.04,+0.46] P≤0 0.12 sd 0.129 hurdle 0.321 | B full 0.91 vs 0.85 DD -15.5%/-24.7% | h1 -0.13 h2 +0.26 | A post +0.12 full +0.12 | C +0.10 | turn 12.4x fund 1.25% tax(seg) +3.6% vs +4.1%
OVL-2            weekly  | B post Δ +0.105 [-0.05,+0.32] P≤0 0.13 sd 0.095 hurdle 0.237 | B full 0.85 vs 0.81 DD -11.6%/-17.0% | h1 -0.07 h2 +0.20 | A post +0.08 full +0.07 | C +0.14 | turn 2.8x fund 0.83% tax(seg) +3.2% vs +3.9%
OVL-2__14d40     daily   | B post Δ +0.120 [-0.07,+0.45] P≤0 0.19 sd 0.133 hurdle 0.332 | B full 0.91 vs 0.85 DD -17.6%/-24.7% | h1 -0.08 h2 +0.23 | A post +0.12 full +0.16 | C +0.05 | turn 13.2x fund 1.38% tax(seg) +3.3% vs +4.1%
OVL-2__14d40     weekly  | B post Δ +0.075 [-0.07,+0.32] P≤0 0.27 sd 0.100 hurdle 0.250 | B full 0.87 vs 0.81 DD -11.6%/-17.0% | h1 +0.01 h2 +0.15 | A post +0.08 full +0.15 | C +0.11 | turn 2.9x fund 0.92% tax(seg) +3.3% vs +3.9%
OVL-2__30d40     daily   | B post Δ +0.117 [-0.02,+0.39] P≤0 0.15 sd 0.104 hurdle 0.260 | B full 0.81 vs 0.85 DD -18.3%/-24.7% | h1 -0.26 h2 +0.20 | A post +0.07 full -0.03 | C +0.02 | turn 12.9x fund 1.58% tax(seg) +2.7% vs +4.1%
OVL-2__30d40     weekly  | B post Δ +0.043 [-0.04,+0.13] P≤0 0.13 sd 0.046 hurdle 0.114 | B full 0.76 vs 0.81 DD -11.4%/-17.0% | h1 -0.14 h2 +0.08 | A post +0.01 full -0.04 | C +0.03 | turn 2.8x fund 1.03% tax(seg) +2.8% vs +3.9%
OVL-3            daily   | B post Δ -0.075 [-0.19,+0.02] P≤0 0.95 sd 0.053 hurdle 0.132 | B full 0.81 vs 0.85 DD -22.4%/-24.7% | h1 -0.03 h2 -0.06 | A post -0.09 full -0.05 | C -0.08 | turn 14.6x fund 2.97% tax(seg) +2.6% vs +4.1%
OVL-3            weekly  | B post Δ -0.029 [-0.13,+0.05] P≤0 0.78 sd 0.045 hurdle 0.112 | B full 0.78 vs 0.81 DD -16.5%/-17.0% | h1 -0.06 h2 +0.01 | A post -0.03 full -0.03 | C -0.03 | turn 3.2x fund 1.80% tax(seg) +3.1% vs +3.9%
TIME-3           daily   | B post Δ +0.059 [-0.05,+0.17] P≤0 0.13 sd 0.055 hurdle 0.137 | B full 0.89 vs 0.85 DD -23.4%/-24.7% | h1 +0.03 h2 +0.05 | A post +0.02 full +0.01 | C -0.02 | turn 11.1x fund 3.07% tax(seg) +5.3% vs +4.1%
TIME-3           weekly  | B post Δ +0.007 [-0.13,+0.12] P≤0 0.47 sd 0.064 hurdle 0.159 | B full 0.82 vs 0.81 DD -18.9%/-17.0% | h1 -0.07 h2 +0.11 | A post -0.05 full -0.01 | C +0.04 | turn 2.9x fund 1.90% tax(seg) +4.1% vs +3.9%
TIME-3__all24    daily   | B post Δ +0.057 [-0.06,+0.17] P≤0 0.15 sd 0.061 hurdle 0.151 | B full 0.89 vs 0.85 DD -23.3%/-24.7% | h1 +0.03 h2 +0.04 | A post +0.03 full +0.02 | C +0.00 | turn 10.9x fund 3.07% tax(seg) +5.3% vs +4.1%
TIME-3__all24    weekly  | B post Δ +0.007 [-0.14,+0.13] P≤0 0.47 sd 0.069 hurdle 0.173 | B full 0.82 vs 0.81 DD -19.1%/-17.0% | h1 -0.07 h2 +0.12 | A post -0.05 full -0.01 | C +0.05 | turn 2.9x fund 1.90% tax(seg) +4.1% vs +3.9%
TIME-3__h0_8_16  daily   | B post Δ +0.028 [-0.07,+0.13] P≤0 0.28 sd 0.053 hurdle 0.133 | B full 0.86 vs 0.85 DD -23.9%/-24.7% | h1 +0.00 h2 +0.03 | A post -0.00 full +0.00 | C +0.00 | turn 11.4x fund 3.08% tax(seg) +4.8% vs +4.1%
TIME-3__h0_8_16  weekly  | B post Δ +0.002 [-0.12,+0.10] P≤0 0.49 sd 0.056 hurdle 0.140 | B full 0.81 vs 0.81 DD -18.8%/-17.0% | h1 -0.06 h2 +0.09 | A post -0.07 full -0.04 | C -0.00 | turn 2.9x fund 1.90% tax(seg) +4.0% vs +3.9%
TIME-4           weekly  | B post Δ +0.159 [+0.03,+0.31] P≤0 0.01 sd 0.071 hurdle 0.178 | B full 0.89 vs 0.81 DD -15.1%/-17.0% | h1 +0.02 h2 +0.18 | A post +0.13 full +0.13 | C +0.25 | turn 2.7x fund 1.90% tax(seg) +4.9% vs +3.9%
TIME-4__mon_fri  weekly  | B post Δ +0.217 [+0.09,+0.36] P≤0 0.00 sd 0.069 hurdle 0.173 | B full 0.94 vs 0.81 DD -14.1%/-17.0% | h1 +0.07 h2 +0.22 | A post +0.17 full +0.14 | C +0.22 | turn 2.7x fund 1.88% tax(seg) +5.4% vs +3.9%
TIME-4__full_gap weekly  | B post Δ +0.150 [+0.01,+0.32] P≤0 0.02 sd 0.081 hurdle 0.202 | B full 0.91 vs 0.81 DD -15.4%/-17.0% | h1 +0.04 h2 +0.19 | A post +0.14 full +0.13 | C +0.22 | turn 4.1x fund 1.96% tax(seg) +4.5% vs +3.9%
COMBO-B          daily   | B post Δ -0.045 [-0.25,+0.14] P≤0 0.69 sd 0.100 hurdle 0.248 | B full 0.77 vs 0.85 DD -23.3%/-24.7% | h1 -0.11 h2 -0.04 | A post -0.12 full -0.15 | C -0.25 | turn 5.3x fund 2.57% tax(seg) +4.8% vs +4.1%
COMBO-B__no_buffer daily   | B post Δ -0.042 [-0.24,+0.14] P≤0 0.69 sd 0.097 hurdle 0.243 | B full 0.77 vs 0.85 DD -24.2%/-24.7% | h1 -0.13 h2 -0.02 | A post -0.12 full -0.14 | C -0.24 | turn 8.4x fund 2.62% tax(seg) +3.4% vs +4.1%
COMBO-B__cc60    daily   | B post Δ +0.011 [-0.18,+0.22] P≤0 0.47 sd 0.101 hurdle 0.252 | B full 0.81 vs 0.85 DD -23.5%/-24.7% | h1 -0.08 h2 +0.03 | A post -0.08 full -0.10 | C -0.17 | turn 6.0x fund 2.79% tax(seg) +5.5% vs +4.1%
COMBO-C          tranche | B post Δ +0.165 [+0.02,+0.32] P≤0 0.01 sd 0.078 hurdle 0.193 | B full 0.91 vs 0.81 DD -14.1%/-17.0% | h1 +0.04 h2 +0.19 | A post +0.14 full +0.11 | C +0.27 | turn 2.7x fund 1.81% tax(seg) +4.9% vs +3.9%
COMBO-C__h0_8_16_K7 tranche | B post Δ +0.165 [+0.02,+0.33] P≤0 0.01 sd 0.079 hurdle 0.196 | B full 0.91 vs 0.81 DD -14.2%/-17.0% | h1 +0.04 h2 +0.19 | A post +0.15 full +0.11 | C +0.27 | turn 2.7x fund 1.82% tax(seg) +4.9% vs +3.9%
COMBO-C__six_K5  tranche | B post Δ +0.156 [-0.00,+0.32] P≤0 0.03 sd 0.082 hurdle 0.205 | B full 0.90 vs 0.81 DD -14.4%/-17.0% | h1 +0.04 h2 +0.17 | A post +0.14 full +0.10 | C +0.26 | turn 3.2x fund 1.84% tax(seg) +4.6% vs +3.9%
