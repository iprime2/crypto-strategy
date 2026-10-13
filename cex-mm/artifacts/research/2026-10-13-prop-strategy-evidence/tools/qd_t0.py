"""T0: engine reproduction vs local_evidence.md (daily TV 0.40) and D3 R3a (weekly Monday TV 0.40); daily vs hourly close check."""
import sys, datetime as dt; sys.path.insert(0, "tools")
import qd_engine as E
close, fund, hourly = E.data()
# consistency: archive daily close[d] vs hourly bar (d,23) close
diff = n = 0; bad = []
for c in E.tb.COINS:
    for d, px in close[c].items():
        h = hourly[c].get(dt.datetime(d.year, d.month, d.day, 23))
        if h is None: continue
        n += 1
        if abs(h / px - 1) > 1e-9: diff += 1; bad.append((c, d, px, h))
print(f"daily archive close vs hourly 23:00 bar close: {n} pairs, {diff} differ by >1e-9; examples: {bad[:3]}")
for label, kw, ref in [("T0a daily TV0.40 band0 cap2 (repo baseline)", dict(rebal="daily", tv=0.40, band=0.0, max_gross=2.0), "expect Sharpe 1.25 DD -21.9% hDD -22.6%  by year 53/47/-5/16/47/3/8"),
                       ("T0b weekly Sun-candle TV0.40 band0 cap2 (D3 R3a)", dict(rebal="weekly", decision_wd=6, tv=0.40, band=0.0, max_gross=2.0), "expect Sharpe 1.12 DD -26.3%  by year 48.8/57.4/-10.7/22.5/38.1/2.4/1.9")]:
    res = E.run(close, fund, hourly, E.P(**kw)); dr = E.daily_from_rows(res["rows"]); s = E.stats(dr, res["rows"])
    print(E.line(label, res, s, s["days"] / 365)); print(E.yearline(s)); print("    " + ref)
