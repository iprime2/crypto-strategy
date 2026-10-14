"""[post hoc] Delta weekday check: weekly rule on Delta 2024-08-10..2026-10-12 for every decision weekday, TV 0.40 and 0.25, unrounded,
plus D3's offset-3-from-start convention reproduced, to identify which weekday D3's 'Delta OOS Sharpe 1.01' refers to."""
import sys, datetime as dt; sys.path.insert(0, "tools")
import qd_t5 as T
print("Delta weekly, unrounded, by decision weekday (candle closing next day 00:00 UTC):")
for wd, nm in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
    print(f"  decision {nm} candle{' [DESIGN]' if wd == 6 else ''}: TV0.40 " + T.run(0.40, None, 0.0, wd=wd)[:80] + " | TV0.25 " + T.run(0.25, None, 0.10, wd=wd)[:80])
import datetime as dt
print("D3 offset convention: first trading day", T.S, "is a", T.S.strftime("%A"), "-> offset 3 => first rebalance nxt =", (T.S + dt.timedelta(3)).strftime("%A"), "decision candle =", (T.S + dt.timedelta(2)).strftime("%A"))
print("Binance window 2020-05-01 is a", dt.date(2020, 5, 1).strftime("%A"), "-> offset 3 => decision candle =", (dt.date(2020, 5, 1) + dt.timedelta(2)).strftime("%A"))
