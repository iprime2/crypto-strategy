# Local evidence pack (computed in this session, 2026-10-13, Binance USDT-M perp archive via data.binance.vision; no orders placed)

Tools (scratchpad, not yet in the repo): tools/trend_hourly.py (hourly mark-to-market of cex-mm/scripts/trend_backtest.py's fixed rule), tools/prop_sim.py (prop-challenge Monte Carlo: stationary block bootstrap on day boundaries, mean block 20 d, plus --historical real windows; daily loss vs 00:00 UTC equity; static or trailing max DD; optional intraday day-stop that flattens for the rest of the UTC day and charges 7.31 bps on gross). Hourly granularity understates intra-hour breaches. Leverage multiplier k scales every hourly return (0.5 = half the native 40% target vol, i.e. ~10% realized).

## Baseline: repo trend rule (long-only TSMOM, 9 coins, signal mean sign(20/60/120d), 40%/N target vol / 60d vol, taker 5.31 + 2 bps slippage, funding)
```

=== binance  2020-05-01 .. 2026-10-12  coins: BTC, ETH, XRP, BNB, ADA, LTC, LINK, DOGE, BCH
trend long-only                    CAGR  +24.2%  vol  19%  Sharpe  1.25  maxDD -21.9%  fees/yr 1.1%  funding/yr +3.4%  avg gross 0.20x
    by year: 2020:+53%  2021:+47%  2022:-5%  2023:+16%  2024:+47%  2025:+3%  2026:+8%
trend long/short                   CAGR  +17.5%  vol  24%  Sharpe  0.78  maxDD -36.6%  fees/yr 2.3%  funding/yr +3.1%  avg gross 0.39x
    by year: 2020:+41%  2021:+36%  2022:-3%  2023:-7%  2024:+29%  2025:-1%  2026:+28%
buy & hold, equal weight           CAGR  +61.5%  vol  75%  Sharpe  1.01  maxDD -80.2%  fees/yr 0.0%  funding/yr +0.0%  avg gross 1.00x
    by year: 2020:+157%  2021:+608%  2022:-63%  2023:+102%  2024:+120%  2025:-17%  2026:-14%
```
Memo reference: cex-mm/artifacts/research/2026-10-08-trend-following-backtest.md (grid of 18 settings all positive; Sharpe 0.99-1.25).

## Hourly mark-to-market check (matches daily exactly)
```
2020-05-01..2026-09-30 looks=(20, 60, 120) tv=0.4 long-only volfilter=None btcfilter=False
  days 2344  CAGR +24.2%  vol 19%  Sharpe 1.25  maxDD(daily) -21.9%  maxDD(hourly) -22.6%  fees/yr 1.1%  funding/yr +3.4%  hours 56256
  by year: 2020:+53%  2021:+47%  2022:-5%  2023:+16%  2024:+47%  2025:+3%  2026:+8%
```

## Daily tail of the strategy at native vol (1x)
```
days 2344, daily sd 0.98%, worst day -7.31% (2021-05-19); close-to-close < -3%: 30 days, < -5%: 5 days; intraday low vs 00:00 < -3%: 42 days, < -5%: 9 days
worst days: 2021-05-19 -7.3%, 2020-11-26 -5.9%, 2020-09-03 -5.3%, 2025-10-10 -5.0%, 2024-12-09 -5.0%, 2024-03-19 -4.9%, 2024-03-05 -4.7%, 2023-04-19 -4.6%
```

## Prop challenge simulations (fee/split assumptions: Breakout $999 for $100K at 80%; HyroTrader $599 at 70%; CFT $599 at 80%; funded phase 12 months with 80% of profit withdrawn every 30 days)

### Breakout Classic 10% target / 3% daily / 6% static, bootstrap, NO day stop
```
rules: target 10%, daily DD 3% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  53.5%      35.6%    17.4%  11.6%     0.0%  17.5% |      129      297 |       31.6%          7.71%            3,129
0.75   15% |  41.5%      35.5%    48.9%   8.5%     0.0%   1.0% |       74      210 |        2.6%          4.38%              822
1.00   19% |  34.3%      32.3%    58.0%   7.4%     0.0%   0.3% |       48      150 |        0.4%          2.83%              -28
1.50   29% |  32.0%      31.6%    62.7%   5.2%     0.0%   0.0% |       29      106 |        0.1%          1.74%             -441
2.00   39% |  30.1%      29.8%    62.6%   7.2%     0.0%   0.0% |       21       75 |        0.0%          1.08%             -672
```

### Breakout Classic, bootstrap, day stop 1.5%
```
rules: target 10%, daily DD 3% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop 0.015
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  60.7%      38.4%     0.0%  15.3%     0.0%  24.0% |      139      297 |       60.3%         11.24%            5,823
0.75   15% |  63.1%      47.6%     3.0%  27.0%     0.0%   7.0% |       99      257 |       25.1%         10.45%            5,596
1.00   19% |  50.7%      45.2%    22.7%  25.1%     0.0%   1.5% |       64      188 |        6.5%          8.21%            3,166
1.50   29% |  51.0%      48.0%    19.6%  29.1%     0.0%   0.2% |       44      142 |        1.8%          6.28%            2,208
2.00   39% |  43.4%      42.3%    25.0%  31.6%     0.0%   0.1% |       29      103 |        0.4%          3.74%              624
```

### Breakout Classic, bootstrap, day stop 2%
```
rules: target 10%, daily DD 3% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop 0.02
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  58.9%      37.5%     3.7%  16.0%     0.0%  21.5% |      137      300 |       48.4%          9.88%            4,818
0.75   15% |  58.7%      45.9%    14.9%  22.1%     0.0%   4.2% |       91      243 |       17.1%          9.09%            4,340
1.00   19% |  49.6%      44.8%    25.9%  23.5%     0.0%   0.9% |       58      178 |        4.4%          7.83%            2,890
```

### Breakout Classic, HISTORICAL windows (every real start day, 365 d horizon), day stop 1.5%
```
rules: target 10%, daily DD 3% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop 0.015
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  49.7%      39.0%     0.0%   3.3%     0.0%  47.0% |       83      245 |       58.7%         10.79%            4,359
0.75   15% |  58.5%      49.2%     0.6%  12.8%     0.0%  28.0% |       73      235 |       24.6%         10.40%            5,085
1.00   19% |  58.9%      48.8%    17.0%  19.5%     0.0%   4.6% |       66      239 |        7.4%          8.43%            3,962
```

### HyroTrader 1-step 10% / 4% daily / 6% static, bootstrap, day stop 2%
```
rules: target 10%, daily DD 4% vs 00:00 equity, max DD 6% static, time limit none d/phase, min days 0, day stop 0.02
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  58.9%      37.5%     3.7%  16.0%     0.0%  21.5% |      137      300 |       55.0%          8.94%            4,665
0.75   15% |  64.8%      48.9%     0.0%  28.8%     0.0%   6.3% |       97      251 |       47.1%         12.73%            7,648
1.00   19% |  60.2%      51.1%     1.6%  36.4%     0.0%   1.8% |       70      211 |       22.4%         11.00%            6,020
```

### CFT 1-step 10% / 4% daily / 6% TRAILING, bootstrap, day stop 2%
```
rules: target 10%, daily DD 4% vs 00:00 equity, max DD 6% trailing, time limit none d/phase, min days 0, day stop 0.02
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
0.50   10% |  50.0%      35.4%     2.6%  39.3%     0.0%   8.1% |      119      277 |        2.8%          4.72%            1,759
0.75   15% |  45.5%      39.6%     0.0%  53.8%     0.0%   0.8% |       73      196 |        0.2%          4.05%            1,242
1.00   19% |  38.8%      37.4%     1.1%  60.1%     0.0%   0.1% |       46      136 |        0.0%          3.01%              567
```

### Generic 2-step 8%+5% / 5% daily / 10% static, bootstrap, no day stop
```
rules: target 8% then 5%, daily DD 5% vs 00:00 equity, max DD 10% static, time limit none d/phase, min days 0, day stop none
 lev   vol |   pass pass<=180d  dailyDD  maxDD  timeout   open | med days p90 days | funded surv E[payout]/acct EV per challenge
1.00   19% |  55.6%      44.5%    23.0%  17.9%     0.0%   3.5% |       89      237 |       14.9%         10.87%            5,548
1.50   29% |  41.2%      38.8%    48.8%   9.8%     0.0%   0.2% |       52      149 |        0.8%          5.66%            1,831
2.00   39% |  38.6%      37.8%    54.2%   7.1%     0.0%   0.1% |       31      114 |        0.1%          4.28%            1,150
3.00   58% |  36.0%      35.9%    55.9%   8.1%     0.0%   0.0% |       20       73 |        0.0%          2.39%              363
```
