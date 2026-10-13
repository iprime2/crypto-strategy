#!/usr/bin/env python3
"""D2 design checks (read-only on the repo; data from the scratchpad cache).

1. Day-stop (intraday circuit breaker) effect on the OWN-account Sharpe/CAGR/maxDD, on the hourly series.
2. Daily rule variants on Binance 2020-05-01..2026-09-30 and Delta 2024-08-10..2026-09-30:
   target vol 0.40 vs 0.25, per-coin weight cap 0.25, no-trade band 0 / 10% / 25% of target, whole-contract rounding.
3. Sub-period stats at the chosen settings.
4. Binance-vs-Delta daily-return correlation over the common window (the session's earlier -0.036 needs explaining).
Every setting run is printed; nothing is dropped.
"""
import sys, os, csv, math, datetime as dt, collections
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
CACHE = f"{SP}/trend-cache"
# Delta contract values from cex-mm/artifacts/research/2026-10-08-trend-following-backtest.md (not fetched live here)
CVALS = {"BTC": 0.001, "BNB": 0.1, "ETH": 0.01, "LTC": 0.1, "LINK": 1, "DOGE": 100, "BCH": 0.01, "XRP": 1, "ADA": 1}
COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4


def stats(rets):
    n = len(rets)
    mu = sum(rets) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    tot = math.prod(1 + x for x in rets)
    yrs = n / 365
    peak, mdd, e = 1.0, 0.0, 1.0
    for x in rets:
        e *= 1 + x; peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    return dict(n=n, cagr=tot ** (1 / yrs) - 1, vol=sd * math.sqrt(365), sharpe=mu / sd * math.sqrt(365) if sd else 0, mdd=mdd,
                worst=min(rets), p1=sorted(rets)[max(0, int(0.01 * n))])


def fmt(label, s, extra=""):
    return (f"{label:52s} CAGR {s['cagr']:+6.1%} vol {s['vol']:4.0%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} "
            f"worst day {s['worst']:+6.2%} p1 {s['p1']:+6.2%} {extra}")


def run(close, fund, start, end, target_vol, coin_cap=None, band=0.0, capital=None, long_only=True, looks=tb.LOOKS):
    days = sorted(set().union(*[set(v) for v in close.values()]))
    eq = capital or 1.0
    units = {}
    out = []
    fees = fpaid = 0.0; gross = []; trades = 0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        w = tb.target_weights(close, d, looks, tb.VOL_WIN, target_vol, long_only)
        if coin_cap is not None:
            w = {c: max(min(x, coin_cap), -coin_cap) for c, x in w.items()}
        new = {}
        for c, x in w.items():
            if nxt not in close[c]:
                continue
            u = x * eq / close[c][d]
            if capital:
                u = round(u / CVALS[c]) * CVALS[c]
            old = units.get(c, 0.0)
            if band > 0 and old != 0 and u != 0 and abs(u - old) <= band * abs(u):
                u = old  # inside the no-trade band: keep the old position
            if u:
                new[c] = u
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        trades += sum(1 for c in set(new) | set(units) if abs(new.get(c, 0) - units.get(c, 0)) > 1e-12)
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * COST) / eq
        fees += traded * COST / eq; fpaid += fpay / eq
        gross.append(sum(abs(u) * close[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r
        out.append((nxt, r))
        units = new
    yrs = len(out) / 365
    return out, dict(fees=fees / yrs, funding=fpaid / yrs, gross=sum(gross) / len(gross), trades_per_yr=trades / yrs)


def by_year(out):
    y = collections.defaultdict(lambda: 1.0)
    for d, r in out:
        y[d.year] *= 1 + r
    return "  ".join(f"{k}:{v - 1:+.0%}" for k, v in sorted(y.items()))


def section(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


# ------------------------------------------------------------------ 1. day stop on the hourly series
section("1. Intraday day-stop on the hourly series (native 40% target vol, long-only, 2020-05-01..2026-09-30)")
rows = list(csv.DictReader(open(f"{SP}/hourly_lo_tv40.csv")))
hours = [(dt.datetime.fromisoformat(r["ts_utc"]), float(r["ret"]), float(r["gross"])) for r in rows]
days = collections.OrderedDict()
for t, r, g in hours:
    days.setdefault(t.date(), []).append((r, g))
for stop in (None, 0.015, 0.02, 0.03, 0.04):
    drets, nstop, stopyr = [], 0, collections.Counter()
    for d, hs in days.items():
        e = 1.0; tripped = False
        for r, g in hs:
            if tripped:
                continue
            e *= 1 + r
            if stop is not None and e < 1 - stop:
                e *= 1 - g * 7.31e-4; tripped = True; nstop += 1; stopyr[d.year] += 1
        drets.append(e - 1)
    s = stats(drets)
    print(fmt(f"day stop {stop if stop else 'none'}", s, f"stop days {nstop} ({dict(sorted(stopyr.items()))})"))
    print("   by year: " + "  ".join(f"{y}:{v - 1:+.0%}" for y, v in sorted(
        {yy: math.prod(1 + r for (d, r) in zip(days, drets) if d.year == yy) for yy in sorted({d.year for d in days})}.items())))

# ------------------------------------------------------------------ 2. daily rule variants
end_b = dt.date(2026, 9, 30)
close_b, fund_b = tb.load_binance(CACHE, end_b)  # all months to 2026-09 are cached: no network
close_d, fund_d = tb.load_delta(CACHE, dt.date(2026, 10, 12))  # cached json
start_b, start_d = dt.date(2020, 5, 1), dt.date(2024, 8, 10)

section("2a. Binance 2020-05-01..2026-09-30, long-only: target vol, per-coin cap, no-trade band")
base = {}
for tv in (0.40, 0.25):
    for cap in (None, 0.25):
        for band in (0.0, 0.10, 0.25):
            out, x = run(close_b, fund_b, start_b, end_b, tv, coin_cap=cap, band=band)
            s = stats([r for _, r in out])
            print(fmt(f"tv {tv:.2f} coin cap {cap} band {band:.2f}", s,
                      f"fees/yr {x['fees']:.1%} funding/yr {x['funding']:+.1%} gross {x['gross']:.2f}x trades/yr {x['trades_per_yr']:.0f}"))
            print("   by year: " + by_year(out))
            base[(tv, cap, band)] = out

section("2b. Delta 2024-08-10..2026-09-30 (and ..2026-10-12), long-only: same variants")
for end_d in (dt.date(2026, 9, 30), dt.date(2026, 10, 12)):
    for tv in (0.40, 0.25):
        for cap in (None, 0.25):
            for band in (0.0, 0.10):
                out, x = run(close_d, fund_d, start_d, end_d, tv, coin_cap=cap, band=band)
                s = stats([r for _, r in out])
                print(fmt(f"to {end_d} tv {tv:.2f} cap {cap} band {band:.2f}", s,
                          f"fees/yr {x['fees']:.1%} funding/yr {x['funding']:+.1%} gross {x['gross']:.2f}x trades/yr {x['trades_per_yr']:.0f}"))
                print("   by year: " + by_year(out))

section("2c. Delta 2024-08-10..2026-10-12, whole Delta contracts, per-coin cap 0.25, band 0.10 (and band 0 for comparison)")
for tv in (0.40, 0.25):
    for band in (0.0, 0.10):
        for capital in (500, 1000, 2000, 5000, 20000):
            out, x = run(close_d, fund_d, start_d, dt.date(2026, 10, 12), tv, coin_cap=0.25, band=band, capital=capital)
            s = stats([r for _, r in out])
            print(fmt(f"tv {tv:.2f} band {band:.2f} capital ${capital:,}", s,
                      f"fees/yr {x['fees']:.1%} gross {x['gross']:.2f}x trades/yr {x['trades_per_yr']:.0f}"))

# ------------------------------------------------------------------ 3. sub-periods at the candidate settings
section("3. Sub-periods, Binance long-only, per-coin cap 0.25, band 0.10, tv 0.25 and 0.40")
for tv in (0.25, 0.40):
    out = base[(tv, 0.25, 0.10)]
    print(f"-- tv {tv:.2f}")
    for a, b in ((dt.date(2020, 5, 1), dt.date(2021, 12, 31)), (dt.date(2022, 1, 1), dt.date(2022, 12, 31)),
                 (dt.date(2023, 1, 1), dt.date(2023, 12, 31)), (dt.date(2024, 1, 1), dt.date(2024, 12, 31)),
                 (dt.date(2025, 1, 1), dt.date(2025, 12, 31)), (dt.date(2026, 1, 1), dt.date(2026, 9, 30)),
                 (dt.date(2025, 1, 1), dt.date(2026, 9, 30)), (dt.date(2022, 1, 1), dt.date(2026, 9, 30))):
        rs = [r for d, r in out if a <= d <= b]
        s = stats(rs)
        print(fmt(f"  {a}..{b}", s))

# ------------------------------------------------------------------ 4. Binance vs Delta correlation on the common window
section("4. Binance vs Delta long-only daily returns, 2024-08-10..2026-09-30, tv 0.40, no cap/band (memo says 0.999)")
ob, _ = run(close_b, fund_b, start_d, end_b, 0.40)
od, _ = run(close_d, fund_d, start_d, end_b, 0.40)
mb, md = dict(ob), dict(od)
common = sorted(set(mb) & set(md))
a = [mb[d] for d in common]; b = [md[d] for d in common]
ma, mb_ = sum(a) / len(a), sum(b) / len(b)
cov = sum((x - ma) * (y - mb_) for x, y in zip(a, b))
corr = cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb_) ** 2 for y in b))
print(f"common days {len(common)}  Binance days {len(mb)}  Delta days {len(md)}  corr {corr:.3f}")
print(f"Delta daily series first/last: {min(md)} {max(md)}; Binance: {min(mb)} {max(mb)}")
missing = sorted(set(mb) - set(md))
print(f"days in Binance but not Delta: {len(missing)} e.g. {missing[:5]}")
# the earlier session run started Delta at 2020-05-01 (so from 2023-12) and compared the LAST n of each series by index:
od_full, _ = run(close_d, fund_d, dt.date(2020, 5, 1), end_b, 0.40)
print(f"Delta series when started 2020-05-01: {len(od_full)} days from {od_full[0][0]} (BTC/ETH only before alts listed)")
