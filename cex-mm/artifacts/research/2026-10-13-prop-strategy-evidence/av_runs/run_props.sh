#!/bin/bash
cd "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/"
P=tools/prop_sim2.py
# Breakout design settings: 10%/3%/6% static, $999, 80% split, k=0.5, day stop 1.5%, Breakout-cost series S_b
for sh in 0.9 0.7 0.5 0.0; do
  echo "--- S_b shifted to daily Sharpe $sh, bootstrap, k 0.35/0.5/0.75, day stop 1.5%"
  python3 $P --returns av_runs/Sb_sh$sh.csv --lev 0.35,0.5,0.75 --day-stop 0.015
done > av_runs/props_shifted.txt 2>&1
echo "--- S_b original, k sweep 0.40..0.60, day stop 1.5%, bootstrap" > av_runs/props_ksweep.txt
python3 $P --returns qd_runs/hourly_daily_tv40_breakout.csv --lev 0.40,0.45,0.50,0.55,0.60 --day-stop 0.015 >> av_runs/props_ksweep.txt 2>&1
echo "--- S_b original, k sweep, day stop 1.5%, HISTORICAL" >> av_runs/props_ksweep.txt
python3 $P --returns qd_runs/hourly_daily_tv40_breakout.csv --lev 0.40,0.45,0.50,0.55,0.60 --day-stop 0.015 --historical >> av_runs/props_ksweep.txt 2>&1
echo "--- S_b original, seeds 1..5 at k 0.5 (bootstrap sampling error)" >> av_runs/props_ksweep.txt
for s in 1 2 3 4 5; do python3 $P --returns qd_runs/hourly_daily_tv40_breakout.csv --lev 0.5 --day-stop 0.015 --seed $s | tail -1 >> av_runs/props_ksweep.txt 2>&1; done
echo "--- S_b original, block 5 / 10 / 40 / 60 days at k 0.5 (block-length sensitivity)" >> av_runs/props_ksweep.txt
for b in 5 10 40 60; do echo "block $b" >> av_runs/props_ksweep.txt; python3 $P --returns qd_runs/hourly_daily_tv40_breakout.csv --lev 0.5 --day-stop 0.015 --block $b | tail -1 >> av_runs/props_ksweep.txt 2>&1; done
echo DONE >> av_runs/props_ksweep.txt
