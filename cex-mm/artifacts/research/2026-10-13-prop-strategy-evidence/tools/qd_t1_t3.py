"""T1-T3 (+ prop series for T4, + T6 inputs). Every setting listed in the pre-registered plan is run and printed; nothing is selected."""
import sys, datetime as dt, json, math, csv, collections; sys.path.insert(0, "tools")
import qd_engine as E
close, fund, hourly = E.data()
H1 = (dt.date(2020, 5, 1), dt.date(2023, 12, 31)); H2 = (dt.date(2024, 1, 1), dt.date(2026, 9, 30))
OUT = "qd_runs"; store = {}

def report(label, halves=True, **kw):
    p = E.P(**kw); res = E.run(close, fund, hourly, p); dr = E.daily_from_rows(res["rows"]); s = E.stats(dr, res["rows"])
    yrs = s["days"] / 365
    print(E.line(label, res, s, yrs)); print(E.yearline(s))
    if res["kills"]:
        print("    kills: " + ", ".join(f"{d} ({x:+.1%})" for d, x in res["kills"]))
    if res["stop_days"]:
        print(f"    day-stop trips: {res['stop_days']} ({res['stop_days'] / yrs:.1f}/yr)")
    if halves:
        for nm, (a, b) in (("2020-05..2023-12", H1), ("2024-01..2026-09", H2)):
            h = E.stats(dr, res["rows"], a, b)
            print(f"    {nm}: CAGR {h['cagr']:+6.1%} vol {h['vol']:5.1%} Sharpe {h['sharpe']:5.2f} maxDD {h['mdd']:6.1%} hDD {h['hmdd']:6.1%} total {h['total']:+.1%} worst {h['worst']:+.2%} worst7d {h['worst7']:+.2%}")
    store[label] = dict(s={k: v for k, v in s.items() if k != "worst_day"}, fees=res["fees"] / yrs, funding=res["funding"] / yrs, trades=res["trades"] / yrs,
                        gross_avg=sum(res["gross"]) / len(res["gross"]), gross_max=max(res["gross"]), kills=[(str(d), x) for d, x in res["kills"]])
    return res, s

def sub_csv(src, dst, since):
    with open(src) as f, open(dst, "w", newline="") as g:
        rd = csv.reader(f); wr = csv.writer(g); wr.writerow(next(rd))
        for row in rd:
            if row[0] >= since: wr.writerow(row)

print("=== T1. Design vs baseline, Binance 2020-05-01..2026-09-30 (T2 halves under each line) ===")
base, _ = report("B  baseline daily TV0.40 band0 cap2.0", rebal="daily", tv=0.40, band=0.0, max_gross=2.0)
d0, _ = report("D  design weekly Mon TV0.25 band0 cap1.0", tv=0.25, band=0.0)
dsg, sd = report("D+ design weekly Mon TV0.25 band10% cap1.0", tv=0.25, band=0.10)
report("   daily TV0.25 band0 cap2.0 (cadence isolated)", rebal="daily", tv=0.25, band=0.0, max_gross=2.0)
report("   daily TV0.25 band10% cap2.0 (upgrade path)", rebal="daily", tv=0.25, band=0.10, max_gross=2.0)
w40, _ = report("   weekly Mon TV0.40 band0 cap2.0 (D3 R3a)", tv=0.40, band=0.0, max_gross=2.0)
E.write_rows(dsg["rows"], f"{OUT}/hourly_design_weekly_tv25_band10.csv")
E.write_rows(base["rows"], f"{OUT}/hourly_daily_tv40.csv"); sub_csv(f"{OUT}/hourly_daily_tv40.csv", f"{OUT}/hourly_daily_tv40_2025on.csv", "2025-01-01")
E.write_rows(w40["rows"], f"{OUT}/hourly_weekly_tv40.csv"); sub_csv(f"{OUT}/hourly_weekly_tv40.csv", f"{OUT}/hourly_weekly_tv40_2025on.csv", "2025-01-01")
with open(f"{OUT}/design_pcd.csv", "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["date", "coin", "pnl_frac"]); [wr.writerow([d, c, f"{v:.8f}"]) for d, c, v in dsg["pcd"]]
with open(f"{OUT}/design_tlog.csv", "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["ts", "coin", "dnotional_frac"]); [wr.writerow([t.isoformat(), c, f"{v:.6f}"]) for t, c, v in dsg["tlog"]]

print("\n=== T3a. Target vol (weekly Mon, band 10%, cap 1.0) ===")
for tv in (0.15, 0.20, 0.25, 0.30, 0.40):
    report(f"TV {tv:.2f}", tv=tv)
print("\n=== T3b. Cadence / decision weekday (TV 0.25, band 10%) ===")
report("daily", rebal="daily", max_gross=2.0)
for wd, nm in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
    report(f"weekly, decision candle {nm} (closes {['Tue','Wed','Thu','Fri','Sat','Sun','Mon'][wd]} 00:00 UTC){' [DESIGN]' if wd == 6 else ''}", decision_wd=wd)
print("\n=== T3c. No-trade band (weekly Mon TV 0.25) + daily TV0.40 band for the record ===")
for b in (0.0, 0.05, 0.10, 0.20):
    report(f"band {b:.0%}", band=b)
report("daily TV0.40 band10% cap2.0 (D2's banded daily)", rebal="daily", tv=0.40, band=0.10, max_gross=2.0)
print("\n=== T3d. Lookbacks (weekly Mon TV 0.25 band 10%) ===")
for lk in ((20, 60, 120), (10, 30, 60), (50, 100, 200), (20,), (60,), (120,)):
    report(f"looks {lk}", looks=lk)
print("\n=== T3e. Vol window ===")
for vw in (30, 60, 90):
    report(f"vol window {vw}", vol_win=vw)
print("\n=== T3f. Universe ===")
for nm, cs in (("9 coins [DESIGN]", list(E.tb.COINS)), ("BTC only", ["BTC"]), ("BTC+ETH", ["BTC", "ETH"]), ("top5 BTC ETH XRP BNB ADA", E.TOP5)):
    report(nm, coins=cs)
print("\n=== T3g. Gross cap ===")
for mg in (1.0, 2.0):
    report(f"max gross {mg}", max_gross=mg)
print("\n=== T3h. Kill switch (flat 4 weeks, half TV 13 weeks, peak reset at restart) ===")
report("no kill [reference]", kill=0.0)
for k in (0.15, 0.20, 0.25, 0.30):
    report(f"kill {k:.0%} checked weekly{' [DESIGN]' if k == 0.20 else ''}", kill=k)
report("kill 20% checked daily", kill=0.20, kill_check="daily")
for k in (0.15, 0.20):
    report(f"kill {k:.0%} weekly at native TV 0.40 band0 cap2 (D3 R3a line)", kill=k, tv=0.40, band=0.0, max_gross=2.0)
print("\n=== T3i. Own-account day stop (weekly Mon TV 0.25 band 10%; resumes the week's positions next 00:00, both legs charged) ===")
for ds in (0.0, 0.015, 0.02, 0.03):
    report(f"day stop {ds or 'none'}", day_stop=ds)
print("\n=== T3j. Regime filters (design: none) ===")
report("none [DESIGN]"); report("BTC < 200d mean -> flat", btc_filter=True); report("BTC 30d vol > 70% -> flat", vol_filter=0.70); report("BTC 30d vol > 90% -> flat", vol_filter=0.90)
print("\n=== T3k. Late execution (Monday 00:00 UTC signal executed later) and decision hour H (signal+execution on H-aligned closes) ===")
for lag in (0, 4, 8, 12, 24):
    report(f"exec lag +{lag}h (same 00:00 signal)", exec_lag=lag)
for H in (0, 4, 8, 12, 16, 20):
    report(f"decision+exec hour {H:02d}:00 UTC", H=H)
print("\n=== T3l. Slippage per side (taker 5.31 bps fixed) ===")
for sl in (2.0, 5.0, 10.0):
    report(f"slippage {sl:.0f} bps", cost_bps=E.tb.TAKER_BPS + sl)
print("\n=== T3m. Cost model on the daily native series (prop leg): Delta vs Breakout ===")
report("daily TV0.40 Delta costs (5.31+2 bps, Binance funding)", rebal="daily", tv=0.40, band=0.0, max_gross=2.0)
bk, _ = report("daily TV0.40 Breakout costs (4 bps/side, no funding, 0.033%/day swap on gross)", rebal="daily", tv=0.40, band=0.0, max_gross=2.0, cost_bps=4.0, funding="none", swap=0.00033)
E.write_rows(bk["rows"], f"{OUT}/hourly_daily_tv40_breakout.csv"); sub_csv(f"{OUT}/hourly_daily_tv40_breakout.csv", f"{OUT}/hourly_daily_tv40_breakout_2025on.csv", "2025-01-01")
report("weekly Mon TV0.25 band10 Breakout costs", cost_bps=4.0, funding="none", swap=0.00033)
print("\n=== T6 input: vol-scaled always-long 9-coin basket (no signal), weekly Mon TV 0.25 band 10%, same costs ===")
al, _ = report("always-long basket weekly TV0.25", always_long=True)
E.write_rows(al["rows"], f"{OUT}/hourly_alwayslong_weekly_tv25.csv")
json.dump(store, open(f"{OUT}/t1_t3_store.json", "w"), indent=1, default=str)
print("done")
