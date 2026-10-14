"""[post hoc] Archive-gap sensitivity: XRP and LTC daily closes are missing 2022-02-26..28 and 2022-04-01..02 in the Binance archive,
which makes tb.target_weights drop both coins for 120 days after each gap. Fill the gaps by carrying the previous close and re-run
the baseline and the design line."""
import sys, datetime as dt; sys.path.insert(0, "tools")
import qd_engine as E
close, fund, hourly = E.data()
filled = {c: dict(px) for c, px in close.items()}
for c in ("XRP", "LTC"):
    ds = sorted(filled[c]); n = 0
    for a, b in zip(ds, ds[1:]):
        d = a + dt.timedelta(1)
        while d < b:
            filled[c][d] = filled[c][a]; d += dt.timedelta(1); n += 1
    print(f"{c}: filled {n} days")
for label, kw in (("baseline daily TV0.40", dict(rebal="daily", tv=0.40, band=0.0, max_gross=2.0)), ("design weekly Mon TV0.25 band10", dict())):
    for nm, cl in (("archive as-is", close), ("gaps filled", filled)):
        res = E.run(cl, fund, hourly, E.P(**kw)); dr = E.daily_from_rows(res["rows"]); s = E.stats(dr, res["rows"])
        print(E.line(f"{label} [{nm}]", res, s, s["days"] / 365)); print(E.yearline(s))
