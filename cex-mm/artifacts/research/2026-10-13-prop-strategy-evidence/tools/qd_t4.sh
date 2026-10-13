#!/bin/bash
# T4 prop batch. S_d = daily native TV0.40 Delta costs; S_b = same with Breakout costs; S_w = weekly Monday native (D3). 3000 paths, seed 7.
cd /tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad
P2="python3 tools/prop_sim2.py"; P1="python3 tools/prop_sim.py"
SD=qd_runs/hourly_daily_tv40.csv; SD25=qd_runs/hourly_daily_tv40_2025on.csv; SB=qd_runs/hourly_daily_tv40_breakout.csv; SB25=qd_runs/hourly_daily_tv40_breakout_2025on.csv
SW=qd_runs/hourly_weekly_tv40.csv; SW25=qd_runs/hourly_weekly_tv40_2025on.csv; SP=qd_runs/hourly_daily_tv40_posstop03.csv; SBP=qd_runs/hourly_daily_tv40_breakout_posstop03.csv
BK="--target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --fee 999 --account 100000 --split 0.8 --paths 3000"
HY="--target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type static --fee 599 --account 100000 --split 0.7 --paths 3000"
L="--lev 0.35,0.5,0.75"
run() { echo "--- $1"; echo "\$ $2"; eval "$2"; echo; }
{
run "B0 Breakout, S_d, day stop 1.5%, bootstrap, ORIGINAL prop_sim.py (day ref = 01:00 equity)" "$P1 --returns $SD --target 0.10 --daily-dd 0.03 --max-dd 0.06 --max-dd-type static --day-stop 0.015 $L --paths 3000 --fee 999 --account 100000 --split 0.8"
run "B1 Breakout, S_d, day stop 1.5%, bootstrap" "$P2 --returns $SD $BK --day-stop 0.015 $L"
run "B2 Breakout, S_d, day stop 1.5%, HISTORICAL" "$P2 --returns $SD $BK --day-stop 0.015 $L --historical"
run "B3 Breakout, S_d, NO day stop, bootstrap (control)" "$P2 --returns $SD $BK --day-stop 0 $L"
run "B4 Breakout, S_d, day stop 2.0%, bootstrap" "$P2 --returns $SD $BK --day-stop 0.02 $L"
run "B5 Breakout, S_d 2025-01..2026-09 only, day stop 1.5%, bootstrap" "$P2 --returns $SD25 $BK --day-stop 0.015 $L"
} > qd_runs/T4_g1_breakout_delta.txt 2>&1 &
{
run "B6 Breakout, S_b (Breakout costs), day stop 1.5%, bootstrap" "$P2 --returns $SB $BK --day-stop 0.015 $L"
run "B7 Breakout, S_b, day stop 1.5%, HISTORICAL" "$P2 --returns $SB $BK --day-stop 0.015 $L --historical"
run "B8 Breakout, S_b 2025-01..2026-09, day stop 1.5%, bootstrap" "$P2 --returns $SB25 $BK --day-stop 0.015 $L"
run "B9 Breakout \$25k (\$275 fee), S_b, day stop 1.5%, bootstrap, k 0.5" "$P2 --returns $SB --target 0.10 --daily-dd 0.03 --max-dd 0.06 --fee 275 --account 25000 --split 0.8 --paths 3000 --day-stop 0.015 --lev 0.5"
run "B10 Breakout, S_b, NO day stop, bootstrap (control)" "$P2 --returns $SB $BK --day-stop 0 $L"
run "P1 Breakout, per-position stop fallback (stop 3% of native gross = 1.5% at k 0.5), NO portfolio day stop, S_d" "$P2 --returns $SP $BK --day-stop 0 --lev 0.5"
run "P2 Breakout, per-position stop fallback, S_b, NO portfolio day stop, bootstrap" "$P2 --returns $SBP $BK --day-stop 0 --lev 0.5"
run "P3 Breakout, per-position stop fallback, S_b, NO portfolio day stop, HISTORICAL" "$P2 --returns $SBP $BK --day-stop 0 --lev 0.5 --historical"
} > qd_runs/T4_g2_breakout_bkcost.txt 2>&1 &
{
run "W1 Breakout, S_w (D3 weekly Monday), day stop 1.5%, bootstrap" "$P2 --returns $SW $BK --day-stop 0.015 $L"
run "W2 Breakout, S_w, day stop 1.5%, HISTORICAL" "$P2 --returns $SW $BK --day-stop 0.015 $L --historical"
run "W3 Breakout, S_w 2025-01..2026-09, day stop 1.5%, bootstrap" "$P2 --returns $SW25 $BK --day-stop 0.015 $L"
run "W4 Breakout, S_w, NO day stop, bootstrap" "$P2 --returns $SW $BK --day-stop 0 $L"
run "H1 HyroTrader static, S_d, day stop 2.0%, bootstrap" "$P2 --returns $SD $HY --day-stop 0.02 $L"
run "H2 HyroTrader static, S_d, day stop 1.5%, bootstrap" "$P2 --returns $SD $HY --day-stop 0.015 $L"
run "H3 HyroTrader static, S_d, day stop 2.0%, HISTORICAL" "$P2 --returns $SD $HY --day-stop 0.02 $L --historical"
run "H4 HyroTrader TRAILING max DD (sensitivity), S_d, day stop 2.0%, bootstrap" "$P2 --returns $SD --target 0.10 --daily-dd 0.04 --max-dd 0.06 --max-dd-type trailing --fee 599 --account 100000 --split 0.7 --paths 3000 --day-stop 0.02 $L"
run "H5 HyroTrader static, trailing INTRADAY daily ref (graft), S_d, day stop 2.0%, bootstrap" "$P2 --returns $SD $HY --day-stop 0.02 $L --trailing-daily"
run "H6 HyroTrader static, S_d 2025-01..2026-09, day stop 2.0%, bootstrap" "$P2 --returns $SD25 $HY --day-stop 0.02 $L"
run "H7 HyroTrader static, NO day stop, bootstrap (control)" "$P2 --returns $SD $HY --day-stop 0 $L"
run "H8 HyroTrader static, all grafts (delever funded 0.33, buffer 0.5%, re-entry 1.5%, chop 3/10/30) + trailing daily, day stop 2.0%, bootstrap" "$P2 --returns $SD $HY --day-stop 0.02 $L --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30 --trailing-daily"
} > qd_runs/T4_g3_weekly_hyro.txt 2>&1 &
{
run "G1 Breakout S_b ds1.5, graft: de-lever 0.33 funded phase only" "$P2 --returns $SB $BK --day-stop 0.015 $L --delever 0.33"
run "G2 Breakout S_b ds1.5, graft: de-lever 0.33 in evaluation too" "$P2 --returns $SB $BK --day-stop 0.015 $L --delever 0.33 --delever-eval"
run "G3 Breakout S_b ds1.5, graft: 0.5% buffer (stop at max(day0*0.985, 0.945); flat when room < 0.5%)" "$P2 --returns $SB $BK --day-stop 0.015 $L --buffer 0.005"
run "G4 Breakout S_b ds1.5, graft: re-entry only if room >= 1.5%, else flat to next 7-day boundary" "$P2 --returns $SB $BK --day-stop 0.015 $L --reentry-room 0.015"
run "G5 Breakout S_b ds1.5, graft: chop detector 3 trips/10 d -> k/2 for 30 d" "$P2 --returns $SB $BK --day-stop 0.015 $L --chop 3 10 30"
run "G6 Breakout S_b ds1.5, balance-based daily reference (00:00 equity minus unrealized PnL)" "$P2 --returns $SB $BK --day-stop 0.015 $L --balance-ref"
run "G7 Breakout S_b ds1.5, ALL grafts (de-lever funded, buffer, re-entry, chop) + balance ref, bootstrap" "$P2 --returns $SB $BK --day-stop 0.015 $L --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30 --balance-ref"
run "G8 same as G7, HISTORICAL" "$P2 --returns $SB $BK --day-stop 0.015 $L --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30 --balance-ref --historical"
run "G9 same as G7, 2025-01..2026-09 bootstrap" "$P2 --returns $SB25 $BK --day-stop 0.015 $L --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30 --balance-ref"
run "G10 same as G7, \$25k account \$275 fee, k 0.5" "$P2 --returns $SB --target 0.10 --daily-dd 0.03 --max-dd 0.06 --fee 275 --account 25000 --split 0.8 --paths 3000 --day-stop 0.015 --lev 0.5 --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30 --balance-ref"
run "G11 Breakout S_b ds1.5, ALL grafts without balance ref (if Breakout measures on equity)" "$P2 --returns $SB $BK --day-stop 0.015 $L --delever 0.33 --buffer 0.005 --reentry-room 0.015 --chop 3 10 30"
} > qd_runs/T4_g4_grafts.txt 2>&1 &
wait
echo "T4 batch done"
