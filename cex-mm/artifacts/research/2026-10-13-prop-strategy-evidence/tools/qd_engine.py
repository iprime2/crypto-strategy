#!/usr/bin/env python3
"""Quant-developer engine: hourly mark-to-market of the repo trend rule (cex-mm/scripts/trend_backtest.py, imported read-only)
with the knobs the D3 design and the judges' grafts introduce. Superset of tools/trend_hourly.py and d3_tests2.hourly_mtm.

Signal/sizing are tb.target_weights unchanged. Knobs: rebalance cadence (daily / weekly on a decision weekday), target vol,
gross cap, no-trade band, whole-contract rounding, execution lag (hours after the 00:00 UTC decision), decision hour H
(signal and execution on H-aligned daily closes built from the hourly files), own-account day stop (flatten for the rest of
the UTC day, resume the series' positions next 00:00, both legs charged), kill switch (x% below peak -> flat 4 weeks, half TV
13 weeks, peak reset at restart), regime filters, cost model (Delta taker+slippage with Binance funding, or Breakout
4 bps/side + 0.033%/day swap on gross at 00:00 with no funding), always-long basket (signal forced to 1) for the edge-decay null.
Writes hourly rows (ts, ret, gross, unreal = unrealized PnL of open positions / equity) and per-coin-day PnL for the tax split.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, math, os, sys, collections, json
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
CACHE = f"{SP}/trend-cache"; HOURLY = f"{SP}/hourly"
CVALS = {"BTC": 0.001, "BNB": 0.1, "ETH": 0.01, "LTC": 0.1, "LINK": 1, "DOGE": 100, "BCH": 0.01, "XRP": 1, "ADA": 1}
TOP5 = ["BTC", "ETH", "XRP", "BNB", "ADA"]


def load_hourly(d: str = HOURLY, coins=tb.COINS) -> dict:
    out = {}
    for c in coins:
        p = os.path.join(d, f"{c}USDT-1h.csv")
        if not os.path.exists(p):
            continue
        m = {}
        for r in csv.DictReader(open(p)):
            ts = int(r["open_time_ms"]); ts = ts / 1000 if ts < 1e14 else ts / 1e6
            m[dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(tzinfo=None)] = float(r["close"])
        out[c] = m
    return out


def h_aligned_closes(hourly: dict, close: dict, H: int) -> dict:
    """Daily close series where close_H[c][d] = price at (d+1) H:00 UTC = close of the hourly bar opening (d+1, H-1).
    H=0 returns the archive closes unchanged."""
    if H == 0:
        return close
    out = {}
    for c, px in close.items():
        m = {}
        for d in px:
            t = dt.datetime(d.year, d.month, d.day) + dt.timedelta(hours=23 + H)
            v = hourly.get(c, {}).get(t)
            if v is not None:
                m[d] = v
        out[c] = m
    return out


def realized_vol(px: dict, d: dt.date, win: int):
    hist = [px.get(d - dt.timedelta(k)) for k in range(win + 1)]
    if any(h is None for h in hist):
        return None
    r = [math.log(hist[k] / hist[k + 1]) for k in range(win)]
    return math.sqrt(sum(x * x for x in r) / win * 365)


class P:
    """Parameters with the design's defaults."""
    def __init__(self, **kw):
        self.coins = list(tb.COINS); self.start = dt.date(2020, 5, 1); self.end = dt.date(2026, 9, 30)
        self.tv = 0.25; self.looks = (20, 60, 120); self.vol_win = 60; self.max_gross = 1.0
        self.rebal = "weekly"; self.decision_wd = 6      # 6 = Sunday UTC candle, i.e. the close at Monday 00:00 UTC
        self.band = 0.10; self.capital = None            # capital -> whole Delta contracts
        self.exec_lag = 0; self.H = 0                    # hours after the decision close; decision hour (H-aligned closes)
        self.day_stop = 0.0; self.kill = 0.0; self.kill_check = "weekly"
        self.btc_filter = False; self.vol_filter = None
        self.cost_bps = tb.TAKER_BPS + tb.SLIPPAGE_BPS; self.funding = "binance"; self.swap = 0.0
        self.always_long = False; self.pos_stop = 0.0      # per-position resting stop at entry*(1 - pos_stop/gross), closed until the next rebalance
        self.__dict__.update(kw)


def run(close: dict, fund: dict, hourly: dict, p: P) -> dict:
    coins = [c for c in p.coins if c in close and c in hourly]
    src = h_aligned_closes(hourly, {c: close[c] for c in coins}, p.H)
    sub = {c: src[c] for c in coins}
    days = sorted(set().union(*[set(close[c]) for c in coins]))
    cost = p.cost_bps / 1e4
    eq = float(p.capital or 1.0); e0 = eq
    units, entry = {}, {}
    pending = []  # (exec datetime, weights)
    rows, pcd = [], []  # hourly rows; per-coin-day pnl
    fees = fpaid = swapp = 0.0; trades = 0; grosses = []; tlog = []
    peak = eq; killed_until = None; half_until = None; kills = []
    stopped_units = None; stop_days = 0
    tv_scale = 1.0; last_px = {}; stop_px = {}; pos_stops = 0
    for d, nxt in zip(days, days[1:]):
        if not (p.start <= nxt <= p.end):
            continue
        t0 = dt.datetime(nxt.year, nxt.month, nxt.day)
        is_dec = p.rebal == "daily" or d.weekday() == p.decision_wd
        if killed_until and nxt >= killed_until and tv_scale == 0.0:
            tv_scale = 0.5; half_until = killed_until + dt.timedelta(days=91); peak = eq  # restart at half size, peak reset
        if half_until and nxt >= half_until and tv_scale == 0.5:
            tv_scale = 1.0; half_until = None
        if is_dec:
            if p.always_long:
                w = {}
                for c in coins:
                    v = realized_vol(sub[c], d, p.vol_win)
                    if v is not None:
                        w[c] = (p.tv / len(coins)) / max(v, 0.05)
            else:
                w = tb.target_weights(sub, d, p.looks, p.vol_win, p.tv, True)
            scale = tv_scale
            if p.btc_filter:
                hist = [close["BTC"].get(d - dt.timedelta(k)) for k in range(200)]
                if all(h is not None for h in hist) and close["BTC"][d] < sum(hist) / 200:
                    scale = 0.0
            if p.vol_filter is not None:
                v = realized_vol(close["BTC"], d, 30)
                if v is not None and v > p.vol_filter:
                    scale = 0.0
            w = {c: x * scale for c, x in w.items()}
            g = sum(abs(x) for x in w.values())
            if g > p.max_gross:
                w = {c: x * p.max_gross / g for c, x in w.items()}
            pending.append((t0 + dt.timedelta(hours=p.H + p.exec_lag), w))
        # kill switch check at the decision (weekly) or every day
        if p.kill and tv_scale > 0 and (is_dec or p.kill_check == "daily") and eq < peak * (1 - p.kill):
            kills.append((nxt, eq / peak - 1)); tv_scale = 0.0; killed_until = nxt + dt.timedelta(days=28)
            pending = [(t0 + dt.timedelta(hours=p.H + p.exec_lag), {})]
        for c in coins:
            if d in close[c]:
                last_px[c] = close[c][d]
        prev = dict(last_px)  # coins with a missing archive day (XRP/LTC Feb-Apr 2022) carry their last price
        px00 = dict(prev)
        day_e0 = eq; day_stopped = False; dpnl = collections.defaultdict(float)
        for h in range(24):
            t = t0 + dt.timedelta(hours=h)
            charge = 0.0
            # resume the series' positions at the next 00:00 after an own-account day stop
            if h == 0 and stopped_units is not None:
                if not any(pw[0] == t for pw in pending):
                    new = {c: u for c, u in stopped_units.items() if c in prev}
                    traded = sum(abs(new.get(c, 0.0)) * prev[c] for c in new)
                    charge += traded * cost; trades += sum(1 for c in new if new[c])
                    units = new; entry = {c: prev[c] for c in new}
                stopped_units = None
            due = [pw for pw in pending if pw[0] == t]
            if due and not day_stopped:
                pending = [pw for pw in pending if pw[0] != t]
                w = due[-1][1]
                new = dict(units)
                for c in set(w) | set(units):
                    if c not in prev:
                        continue
                    tgt = w.get(c, 0.0) * eq / prev[c]
                    if p.capital:
                        tgt = round(tgt / CVALS[c]) * CVALS[c]
                    cur = units.get(c, 0.0)
                    if tgt and p.band and abs(tgt - cur) * prev[c] < p.band * abs(tgt) * prev[c]:
                        tgt = cur  # inside the no-trade band
                    if abs(tgt - cur) > 1e-15:
                        trades += 1; charge += abs(tgt - cur) * prev[c] * cost; tlog.append((t, c, (tgt - cur) * prev[c] / eq))
                        if abs(tgt) > 1e-15:
                            if abs(tgt) > abs(cur) and cur * tgt >= 0:
                                entry[c] = (entry.get(c, prev[c]) * abs(cur) + prev[c] * (abs(tgt) - abs(cur))) / abs(tgt)
                            elif cur * tgt < 0:
                                entry[c] = prev[c]
                        else:
                            entry.pop(c, None)
                    if abs(tgt) > 1e-15:
                        new[c] = tgt
                    else:
                        new.pop(c, None)
                units = new
                if p.pos_stop:
                    gw = sum(abs(u) * prev[c] for c, u in units.items()) / eq
                    stop_px = {c: prev[c] * (1 - p.pos_stop / gw) for c in units} if gw > 0 else {}
            pnl = 0.0
            for c, u in units.items():
                px = hourly[c].get(t)
                if px is None:
                    px = prev[c]
                pnl += u * (px - prev[c]); dpnl[c] += u * (px - prev[c]); prev[c] = px
            last_px.update(prev)
            if p.pos_stop and stop_px:
                hit = [c for c in units if c in stop_px and prev[c] < stop_px[c]]
                for c in hit:
                    fl = abs(units[c]) * prev[c] * cost; pnl -= fl; fees += fl / eq; pos_stops += 1
                    tlog.append((t, c, -units[c] * prev[c] / eq)); units.pop(c); entry.pop(c, None); stop_px.pop(c)
            fp = 0.0
            if p.funding == "binance" and h in (0, 8, 16):
                for c, u in units.items():
                    f = u * px00[c] * fund[c].get(nxt, 0.0) / 3; fp += f; dpnl[c] -= f
            sw = 0.0
            if p.swap and h == 0:
                for c, u in units.items():
                    s = abs(u) * px00[c] * p.swap; sw += s; dpnl[c] -= s
            r = (pnl - fp - sw - charge) / eq
            fees += charge / eq; fpaid += fp / eq; swapp += sw / eq
            eq *= 1 + r
            gross = sum(abs(u) * prev[c] for c, u in units.items()) / eq
            unreal = sum(u * (prev[c] - entry[c]) for c, u in units.items() if c in entry) / eq
            # own-account day stop: flatten now (taker+slippage on gross), stay flat for the rest of the UTC day
            if p.day_stop and not day_stopped and eq / day_e0 - 1 < -p.day_stop and units:
                eq_before = eq / (1 + r)
                fl = sum(abs(u) * prev[c] for c, u in units.items()) * cost
                eq -= fl; fees += fl / eq_before
                rows.append((t, eq / eq_before - 1, 0.0, 0.0)); grosses.append(0.0)
                stopped_units = dict(units); units = {}; entry = {}; day_stopped = True; stop_days += 1
                continue
            rows.append((t, r, gross, unreal))
            grosses.append(gross)
        for c, v in dpnl.items():
            pcd.append((nxt, c, v / day_e0))
        peak = max(peak, eq)
    return dict(rows=rows, pcd=pcd, fees=fees, funding=fpaid, swap=swapp, trades=trades, gross=grosses, kills=kills,
                stop_days=stop_days, final=eq / e0, tlog=tlog, pos_stops=pos_stops)


# ---------------------------------------------------------------- statistics

def daily_from_rows(rows):
    by = collections.OrderedDict()
    for t, r, g, u in rows:
        by.setdefault(t.date(), []).append(r)
    return collections.OrderedDict((d, math.prod(1 + x for x in v) - 1) for d, v in by.items())


def stats(drets: dict, rows=None, a: dt.date | None = None, b: dt.date | None = None) -> dict:
    items = [(d, r) for d, r in drets.items() if (a is None or d >= a) and (b is None or d <= b)]
    if len(items) < 10:
        return {}
    x = [r for _, r in items]; n = len(x); mu = sum(x) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in x) / (n - 1)); tot = math.prod(1 + v for v in x); yrs = n / 365
    peak, mdd, e, eqs = 1.0, 0.0, 1.0, []
    for v in x:
        e *= 1 + v; eqs.append(e); peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    w7 = min(eqs[i + 6] / (eqs[i - 1] if i else 1.0) - 1 for i in range(len(eqs) - 6)) if n > 7 else float("nan")
    out = dict(days=n, cagr=tot ** (1 / yrs) - 1, vol=sd * math.sqrt(365), sharpe=mu / sd * math.sqrt(365) if sd else 0.0,
               mdd=mdd, worst=min(x), worst_day=min(items, key=lambda kv: kv[1])[0], worst7=w7, total=tot - 1)
    if rows is not None:
        hp, hm, he = 1.0, 0.0, 1.0
        for t, r, g, u in rows:
            if (a is None or t.date() >= a) and (b is None or t.date() <= b):
                he *= 1 + r; hp = max(hp, he); hm = min(hm, he / hp - 1)
        out["hmdd"] = hm
    yearly = collections.OrderedDict()
    for d, r in items:
        yearly[d.year] = yearly.get(d.year, 1.0) * (1 + r)
    out["yearly"] = {y: v - 1 for y, v in yearly.items()}
    return out


def line(label: str, res: dict, s: dict, yrs: float) -> str:
    g = res["gross"]
    return (f"{label:40s} CAGR {s['cagr']:+6.1%} vol {s['vol']:5.1%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} "
            f"hDD {s.get('hmdd', float('nan')):6.1%} fees/yr {res['fees'] / yrs:5.2%} fund/yr {res['funding'] / yrs:+5.2%} "
            f"swap/yr {res['swap'] / yrs:5.2%} gross avg {sum(g) / len(g):.2f}x max {max(g):.2f}x trades/yr {res['trades'] / yrs:5.0f} "
            f"worst {s['worst']:+6.2%} ({s['worst_day']}) worst7d {s['worst7']:+6.2%}")


def yearline(s: dict) -> str:
    return "    by year: " + "  ".join(f"{y}:{v:+.1%}" for y, v in s["yearly"].items())


def write_rows(rows, path):
    with open(path, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["ts_utc", "ret", "gross", "unreal"])
        for t, r, g, u in rows:
            wr.writerow([t.isoformat(), f"{r:.10f}", f"{g:.4f}", f"{u:.6f}"])


_DATA = {}
def data(src="binance"):
    if src not in _DATA:
        if src == "binance":
            close, fund = tb.load_binance(CACHE, dt.date(2026, 9, 30)); _DATA[src] = (close, fund)
        else:
            close, fund = tb.load_delta(CACHE, dt.date(2026, 10, 12)); _DATA[src] = (close, fund)
    if "hourly" not in _DATA:
        _DATA["hourly"] = load_hourly()
    return _DATA[src][0], _DATA[src][1], _DATA["hourly"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", type=float, default=0.25); ap.add_argument("--rebal", default="weekly"); ap.add_argument("--wd", type=int, default=6)
    ap.add_argument("--band", type=float, default=0.10); ap.add_argument("--max-gross", type=float, default=1.0)
    ap.add_argument("--looks", default="20,60,120"); ap.add_argument("--vol-win", type=int, default=60)
    ap.add_argument("--coins", default=",".join(tb.COINS)); ap.add_argument("--start", default="2020-05-01"); ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--exec-lag", type=int, default=0); ap.add_argument("--H", type=int, default=0)
    ap.add_argument("--day-stop", type=float, default=0.0); ap.add_argument("--kill", type=float, default=0.0); ap.add_argument("--kill-check", default="weekly")
    ap.add_argument("--btc-filter", action="store_true"); ap.add_argument("--vol-filter", type=float, default=None)
    ap.add_argument("--cost-bps", type=float, default=tb.TAKER_BPS + tb.SLIPPAGE_BPS); ap.add_argument("--funding", default="binance"); ap.add_argument("--swap", type=float, default=0.0)
    ap.add_argument("--capital", type=float, default=None); ap.add_argument("--always-long", action="store_true")
    ap.add_argument("--out", default=None); ap.add_argument("--label", default="run"); ap.add_argument("--pos-stop", type=float, default=0.0)
    a = ap.parse_args()
    close, fund, hourly = data()
    p = P(tv=a.tv, rebal=a.rebal, decision_wd=a.wd, band=a.band, max_gross=a.max_gross, looks=tuple(int(x) for x in a.looks.split(",")),
          vol_win=a.vol_win, coins=a.coins.split(","), start=dt.date.fromisoformat(a.start), end=dt.date.fromisoformat(a.end),
          exec_lag=a.exec_lag, H=a.H, day_stop=a.day_stop, kill=a.kill, kill_check=a.kill_check, btc_filter=a.btc_filter,
          vol_filter=a.vol_filter, cost_bps=a.cost_bps, funding=a.funding, swap=a.swap, capital=a.capital, always_long=a.always_long, pos_stop=a.pos_stop)
    res = run(close, fund, hourly, p)
    dr = daily_from_rows(res["rows"]); s = stats(dr, res["rows"]); yrs = s["days"] / 365
    print(line(a.label, res, s, yrs)); print(yearline(s))
    if res["kills"]:
        print("    kills: " + ", ".join(f"{d} ({x:+.1%})" for d, x in res["kills"]))
    if res["pos_stops"]:
        print(f"    per-position stops hit: {res['pos_stops']} ({res['pos_stops'] / yrs:.1f}/yr)")
    if a.out:
        write_rows(res["rows"], a.out)


if __name__ == "__main__":
    main()
