#!/usr/bin/env python3
"""Trend-following backtest on Delta India perps (daily bars, no orders, public data only).

Rule (fixed before testing, from the time-series momentum literature):
  signal_i  = mean of sign(return over 20, 60, 120 days) at day t close   (long-only: max(signal, 0))
  weight_i  = signal_i * (TARGET_VOL / N) / realized 60-day vol_i, gross exposure capped at 2x
  The position is set at day t close and held over day t+1 (no look-ahead).
Costs: taker fee + slippage on traded notional; funding is paid on longs and received on shorts.

Data sources:
  binance  data.binance.vision USDT-M perp daily klines + funding (2020 onward; a proxy for Delta)
  delta    api.india.delta.exchange daily candles + FUNDING:<sym> hourly rates (2024 onward)

    python3 scripts/trend_backtest.py                       # Binance 2020-, long-only and long/short
    python3 scripts/trend_backtest.py --source delta --capital 280
    python3 scripts/trend_backtest.py --grid                # every lookback/vol setting, all reported
    python3 scripts/trend_backtest.py --selftest
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import math
import os
import urllib.request
import zipfile

COINS = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()  # large caps with perps in Jan 2020, all on Delta India
LOOKS, VOL_WIN, TARGET_VOL, MAX_GROSS = (20, 60, 120), 60, 0.40, 2.0
TAKER_BPS, SLIPPAGE_BPS = 5.31, 2.0  # Delta India taker incl. GST (10% referral discount)
UA = {"User-Agent": "cex-mm-trend/0.1"}
DELTA = "https://api.india.delta.exchange"


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


# ---------------------------------------------------------------- data

def load_binance(cache: str, end: dt.date) -> tuple[dict, dict]:
    months = []
    y, m = 2019, 9
    while (y, m) <= (end.year, end.month):
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    def fetch(kind: str, coin: str, ym: str) -> None:
        sym = coin + "USDT"
        path = os.path.join(cache, f"binance-{sym}-{kind}-{ym}.csv")
        if os.path.exists(path):
            return
        sub = f"klines/{sym}/1d" if kind == "1d" else f"fundingRate/{sym}"
        try:
            z = get(f"https://data.binance.vision/data/futures/um/monthly/{sub}/{sym}-{kind}-{ym}.zip")
        except Exception:
            return  # month before listing, or not published yet
        with zipfile.ZipFile(io.BytesIO(z)) as f:
            open(path, "wb").write(f.read(f.namelist()[0]))

    with cf.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: fetch(*j), [(k, c, ym) for c in COINS for k in ("1d", "fundingRate") for ym in months]))
    close, fund = collections.defaultdict(dict), collections.defaultdict(lambda: collections.defaultdict(float))
    for fn in os.listdir(cache):
        if not fn.startswith("binance-"):
            continue
        coin = fn.split("-")[1][:-4]
        for row in csv.reader(open(os.path.join(cache, fn))):
            if not row[0].isdigit():
                continue  # header
            d = dt.datetime.fromtimestamp(int(row[0]) / 1000, dt.timezone.utc).date()
            if "-1d-" in fn:
                close[coin][d] = float(row[4])
            else:
                fund[coin][d] += float(row[2])  # fraction per funding interval, summed per day
    return close, fund


def load_delta(cache: str, end: dt.date) -> tuple[dict, dict]:
    path = os.path.join(cache, f"delta-{end}.json")
    if os.path.exists(path):
        raw = json.load(open(path))
    else:
        t0, t1 = int(dt.datetime(2023, 12, 1, tzinfo=dt.timezone.utc).timestamp()), int(
            dt.datetime.combine(end, dt.time(), dt.timezone.utc).timestamp())
        raw = {}
        for c in COINS:
            sym = c + "USD"
            bars = json.loads(get(f"{DELTA}/v2/history/candles?resolution=1d&symbol={sym}&start={t0}&end={t1}"))["result"]
            rates = []
            for s in range(t0, t1, 1999 * 3600):  # hourly rates, under the per-request candle cap
                q = f"{DELTA}/v2/history/candles?resolution=1h&symbol=FUNDING:{sym}&start={s}&end={min(s + 1999 * 3600, t1)}"
                rates += json.loads(get(q))["result"]
            raw[c] = {"close": [[b["time"], b["close"]] for b in bars], "funding": [[r["time"], r["close"]] for r in rates]}
        json.dump(raw, open(path, "w"))
    close, fund = collections.defaultdict(dict), collections.defaultdict(lambda: collections.defaultdict(float))
    hourly = collections.defaultdict(lambda: collections.defaultdict(list))
    for c, v in raw.items():
        for t, px in v["close"]:
            close[c][dt.datetime.fromtimestamp(t, dt.timezone.utc).date()] = float(px)
        for t, pct in v["funding"]:
            hourly[c][dt.datetime.fromtimestamp(t, dt.timezone.utc).date()].append(float(pct))
        for d, xs in hourly[c].items():
            fund[c][d] = sum(xs) / len(xs) / 100 * 3  # % per 8 h -> fraction per day
    return close, fund


def contract_values() -> dict[str, float]:
    prods = json.loads(get(f"{DELTA}/v2/products"))["result"]
    by_sym = {p["symbol"]: float(p["contract_value"]) for p in prods}
    return {c: by_sym[c + "USD"] for c in COINS}


# ---------------------------------------------------------------- strategy

def sign(x: float) -> int:
    return (x > 0) - (x < 0)


def target_weights(close: dict, d: dt.date, looks, vol_win: int, target_vol: float, long_only: bool) -> dict[str, float]:
    """Weights decided at day d close, using prices up to and including d only."""
    sig, vol = {}, {}
    span = max(max(looks), vol_win) + 1
    for c, px in close.items():
        hist = [px.get(d - dt.timedelta(k)) for k in range(span)]
        if any(h is None for h in hist):
            continue
        s = sum(sign(hist[0] / hist[L] - 1) for L in looks) / len(looks)
        sig[c] = max(s, 0.0) if long_only else s
        r = [math.log(hist[k] / hist[k + 1]) for k in range(vol_win)]
        vol[c] = math.sqrt(sum(x * x for x in r) / vol_win * 365)
    n = len(sig) or 1
    w = {c: sig[c] * (target_vol / n) / max(vol[c], 0.05) for c in sig}
    g = sum(abs(x) for x in w.values())
    return {c: x * MAX_GROSS / g for c, x in w.items()} if g > MAX_GROSS else w


def backtest(close, fund, start, end, *, long_only=True, looks=LOOKS, vol_win=VOL_WIN, target_vol=TARGET_VOL,
             capital=None, cvals=None) -> dict:
    """Daily rebalance. With `capital` (USD), positions are whole Delta contracts sized off current equity."""
    cost = (TAKER_BPS + SLIPPAGE_BPS) / 1e4
    days = sorted(set().union(*[set(v) for v in close.values()]))
    eq = capital or 1.0
    units = {}  # coin units held (contracts * contract value)
    rets, yearly, fees, funding, gross = [], collections.defaultdict(lambda: 1.0), 0.0, 0.0, []
    peak, mdd = eq, 0.0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        w = target_weights(close, d, looks, vol_win, target_vol, long_only)
        new = {}
        for c, x in w.items():
            u = x * eq / close[c][d]
            if capital:
                u = round(u / cvals[c]) * cvals[c]
            if u and nxt in close[c]:
                new[c] = u
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * close[c][d] for c in set(new) | set(units))
        pnl = sum(u * (close[c][nxt] - close[c][d]) for c, u in new.items())
        fpay = sum(u * close[c][d] * fund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * cost) / eq
        fees += traded * cost / eq
        funding += fpay / eq
        gross.append(sum(abs(u) * close[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r
        peak, mdd = max(peak, eq), min(mdd, eq / peak - 1)
        rets.append(r)
        yearly[nxt.year] *= 1 + r
        units = new
    return summarize(rets, yearly, mdd, fees, funding, gross)


def buy_and_hold(close, start, end) -> dict:
    days = sorted(set().union(*[set(v) for v in close.values()]))
    rets, yearly, eq, peak, mdd = [], collections.defaultdict(lambda: 1.0), 1.0, 1.0, 0.0
    for d, nxt in zip(days, days[1:]):
        if not (start <= nxt <= end):
            continue
        cs = [c for c in close if d in close[c] and nxt in close[c]]
        r = sum(close[c][nxt] / close[c][d] - 1 for c in cs) / len(cs)
        eq *= 1 + r
        peak, mdd = max(peak, eq), min(mdd, eq / peak - 1)
        rets.append(r)
        yearly[nxt.year] *= 1 + r
    return summarize(rets, yearly, mdd, 0.0, 0.0, [1.0])


def summarize(rets, yearly, mdd, fees, funding, gross) -> dict:
    n = len(rets)
    if n < 2:
        return {}
    mu = sum(rets) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    total = math.prod(1 + x for x in rets)
    yrs = n / 365
    return dict(days=n, cagr=total ** (1 / yrs) - 1, vol=sd * math.sqrt(365), sharpe=mu / sd * math.sqrt(365) if sd else 0.0,
                mdd=mdd, fees=fees / yrs, funding=funding / yrs, gross=sum(gross) / len(gross),
                yearly={y: v - 1 for y, v in sorted(yearly.items())}, rets=rets)


def line(label: str, s: dict) -> str:
    return (f"{label:34s} CAGR {s['cagr']:+7.1%}  vol {s['vol']:4.0%}  Sharpe {s['sharpe']:5.2f}  maxDD {s['mdd']:6.1%}  "
            f"fees/yr {s['fees']:4.1%}  funding/yr {s['funding']:+5.1%}  avg gross {s['gross']:.2f}x")


# ---------------------------------------------------------------- self-check

def selftest() -> None:
    d0 = dt.date(2024, 1, 1)
    days = [d0 + dt.timedelta(i) for i in range(200)]
    up = {d: 100 * 1.01 ** i * (1 + 0.02 * (-1) ** i) for i, d in enumerate(days)}  # trending, with noise
    down = {d: 100 * 0.99 ** i * (1 + 0.02 * (-1) ** i) for i, d in enumerate(days)}
    w = target_weights({"UP": up, "DN": down}, days[150], LOOKS, VOL_WIN, TARGET_VOL, long_only=False)
    assert w["UP"] > 0 > w["DN"], w
    assert target_weights({"DN": down}, days[150], LOOKS, VOL_WIN, TARGET_VOL, long_only=True)["DN"] == 0
    # No look-ahead: changing tomorrow's price must not change today's decision.
    shocked = {**up, days[151]: up[days[151]] * 3}
    assert target_weights({"UP": shocked}, days[150], LOOKS, VOL_WIN, TARGET_VOL, False) == \
        target_weights({"UP": up}, days[150], LOOKS, VOL_WIN, TARGET_VOL, False)
    s = backtest({"UP": up}, {"UP": {}}, days[121], days[-1])
    assert s["cagr"] > 0 and s["fees"] > 0, s
    print("selftest ok")


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["binance", "delta", "both"], default="binance")
    ap.add_argument("--start", default="2020-05-01", help="first trading day (needs 120 days of history before it)")
    ap.add_argument("--end", default=None, help="last day, default yesterday")
    ap.add_argument("--capital", type=float, nargs="*", help="USD; round positions to whole Delta contracts")
    ap.add_argument("--grid", action="store_true", help="report every lookback/target-vol setting (no selection)")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/cex-mm/trend"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    os.makedirs(args.cache, exist_ok=True)
    end = dt.date.fromisoformat(args.end) if args.end else dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(1)
    start = dt.date.fromisoformat(args.start)
    srcs = {"binance": lambda: load_binance(args.cache, end), "delta": lambda: load_delta(args.cache, end)}
    data = {k: f() for k, f in srcs.items() if args.source in (k, "both")}
    for name, (close, fund) in data.items():
        print(f"\n=== {name}  {start} .. {end}  coins: {', '.join(c for c in COINS if close.get(c))}")
        for lo, label in ((True, "trend long-only"), (False, "trend long/short")):
            s = backtest(close, fund, start, end, long_only=lo)
            print(line(label, s))
            print("    by year: " + "  ".join(f"{y}:{v:+.0%}" for y, v in s["yearly"].items()))
        bh = buy_and_hold(close, start, end)
        print(line("buy & hold, equal weight", bh))
        print("    by year: " + "  ".join(f"{y}:{v:+.0%}" for y, v in bh["yearly"].items()))
        if args.grid:
            print("  sensitivity, long-only (all settings shown):")
            for looks in ((10, 30, 60), (20, 60, 120), (50, 100, 200), (20,), (60,), (120,)):
                for tv in (0.25, 0.40, 0.60):
                    s = backtest(close, fund, start, end, looks=looks, target_vol=tv)
                    print("  " + line(f"looks {looks} target vol {tv:.0%}", s))
        if args.capital:
            cvals = contract_values()
            print(f"  whole Delta contracts (contract values {cvals}):")
            for cap in args.capital:
                s = backtest(close, fund, start, end, capital=cap, cvals=cvals)
                print("  " + line(f"long-only, ${cap:,.0f} capital", s))
    if len(data) == 2:
        a = backtest(*data["binance"], start, end)["rets"]
        b = backtest(*data["delta"], start, end)["rets"]
        n = min(len(a), len(b))
        a, b = a[-n:], b[-n:]
        ma, mb = sum(a) / n, sum(b) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        corr = cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
        print(f"\nlong-only daily returns, Binance vs Delta over the same {n} days: correlation {corr:.3f}")


if __name__ == "__main__":
    main()
