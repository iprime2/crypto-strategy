#!/usr/bin/env python3
"""Engineering checks for RESID-1 (spec.md section 'Engineering checks'), run before reading any result."""
import datetime as dt, math, sys
sys.path.insert(0, "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/RESID-1")
import numpy as np
import resid1_lib as L

NINE = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
K5 = f"{L.SP}/universe/klines5m"


def load_nine():
    return {c: L.load_5m_dir(K5, "binance-", f"{c}USDT", c) for c in NINE}


def check_daily_vs_1d(coins):
    sys.path.insert(0, f"{L.SP}/tools2")
    import data
    P = data.load_binance()
    worst, n, miss = 0.0, 0, 0
    for c in NINE:
        j = P.ci[c]
        for i, d in enumerate(P.dates):
            if not (dt.date(2020, 4, 30) <= d <= dt.date(2026, 9, 29)):
                continue
            ref = P.C[i, j]
            if not np.isfinite(ref):
                continue
            mine = coins[c].C(d + dt.timedelta(days=1))
            if mine is None:
                miss += 1; continue
            worst = max(worst, abs(mine / ref - 1)); n += 1
    print(f"[1] daily close from 5m vs 1d kline close, nine 2020-05..2026-09: {n} pairs, max rel diff {worst:.2e}, 5m-missing {miss}")


def check_ols():
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(200):
        x = np.cumsum(rng.normal(0, 0.03, 50)) + 10
        y = 0.3 + 1.4 * x + rng.normal(0, 0.05, 50)
        a, b, r2, sg = L.ols(y, x)
        A = np.c_[np.ones(50), x]
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        e = y - A @ coef
        r2r = 1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum()
        worst = max(worst, abs(a - coef[0]), abs(b - coef[1]), abs(r2 - r2r), abs(sg - e.std()))
    print(f"[2] OLS vs lstsq on 200 random windows: max abs diff {worst:.2e}")


class FakeCoin(L.Coin):
    def __init__(self, name, closes: dict):
        self.name, self.bar = name, 300_000
        days = sorted(closes)
        self.first_t = L.day_ms(days[0]) - L.DAY
        self.last_close_t = L.day_ms(days[-1]) + 2 * L.H
        self._C = dict(closes); self._P01 = dict(closes)
        self.t = np.array([L.day_ms(d) for d in days], dtype=np.int64); self.o = np.array([closes[d] for d in days]); self.c = self.o.copy()
        self.fund_t = np.zeros(0, dtype=np.int64); self.fund_r = np.zeros(0); self.fund_months = set()

    def fill(self, d):
        p = self._P01.get(d)
        return (p, L.day_ms(d) + L.H, False) if p is not None else None


def check_synthetic():
    rng = np.random.default_rng(5)
    d0 = dt.date(2021, 1, 1)
    days = [d0 + dt.timedelta(days=i) for i in range(200)]
    lx = np.cumsum(rng.normal(0, 0.03, 200)) + math.log(30000)
    noise = rng.uniform(-0.01, 0.01, 200)  # bounded: sd 0.577%, 2 sigma 1.15% > max |noise|, so no chance breaks
    for sign, tag in ((1, "up"), (-1, "down")):
        ly = lx + noise - math.log(30000) + math.log(100)
        ly[120:] += sign * 0.10  # +-10% persistent break (about 10 sigma of the 1% noise)
        X = FakeCoin("BTC", {d: float(math.exp(v)) for d, v in zip(days, lx)})
        Y = FakeCoin("ALT", {d: float(math.exp(v)) for d, v in zip(days, ly)})
        res = L.simulate([Y], X, days[0], days[-1], L.Params(cost_bps=0.0), n_alts=1)
        t1 = [t for t in res["trades"] if t["entry_date"] == days[120]]
        if t1:
            t = t1[0]
            print(f"[4] synthetic {tag}: trade at the break day side {t['side']:+d} (want {sign:+d}), held {(t['exit_date'] - t['entry_date']).days} d, "
                  f"net {t['net_bps']:+.1f} bps (break was planted at the decision close; fill at the same day's 01:00 price -> ~0 unless the residual moves)")
        else:
            print(f"[4] synthetic {tag}: NO trade on the break day; trades {[(t['entry_date'], t['side']) for t in res['trades']]}")
    # break that develops after entry: entry on a 2.5 sigma break, then a further move in the same direction is earned
    ly = lx + noise - math.log(30000) + math.log(100)
    ly[120] += 0.04; ly[121:] += 0.12
    X = FakeCoin("BTC", {d: float(math.exp(v)) for d, v in zip(days, lx)})
    Y = FakeCoin("ALT", {d: float(math.exp(v)) for d, v in zip(days, ly)})
    res = L.simulate([Y], X, days[0], days[-1], L.Params(cost_bps=0.0), n_alts=1)
    t1 = [t for t in res["trades"] if t["entry_date"] == days[120]]
    print(f"[4] synthetic follow-through: trade {[(t['side'], round(t['net_bps'], 1)) for t in t1]} (want side +1, about +800 bps from the residual 0.04 -> 0.12)")


def check_lookahead_and_accounting(coins):
    alts = [coins[c] for c in NINE[1:]]
    s, e = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
    full = L.simulate(alts, coins["BTC"], s, e, L.Params(), n_alts=8)
    diff = abs(sum(t["net"] for t in full["trades"]) - full["pnl"].sum())
    print(f"[5] accounting: |sum trade net - sum daily pnl| = {diff:.2e} (equity units), trades {len(full['trades'])}")
    cut = dt.date(2023, 6, 30)
    # truncated data: bars at or after 01:00 of the day after the cut are removed
    tcut = L.day_ms(cut + dt.timedelta(days=1))
    tr_coins = {}
    for c, co in coins.items():
        m = co.t < tcut
        nc = L.Coin(c, co.t[m], co.o[m], co.c[m], co.bar)
        nc.fund_t, nc.fund_r = co.fund_t[co.fund_t < tcut], co.fund_r[co.fund_t < tcut]
        tr_coins[c] = nc
    part = L.simulate([tr_coins[c] for c in NINE[1:]], tr_coins["BTC"], s, cut, L.Params(), n_alts=8)
    A = {(t["alt"], t["entry_date"]): t for t in full["trades"] if t["exit_date"] < cut}
    B = {(t["alt"], t["entry_date"]): t for t in part["trades"] if t["exit_how"] != "end"}
    mism = [k for k in A if k not in B or B[k]["exit_date"] != A[k]["exit_date"] or abs(B[k]["net_bps"] - A[k]["net_bps"]) > 1e-9]
    extra = [k for k in B if k not in A]
    print(f"[3] look-ahead: {len(A)} trades closed before {cut} in the full run; truncated run matches {len(A) - len(mism)}, mismatches {len(mism)}, extra {len(extra)}")
    eqd = max(abs(a - b) for a, b in zip(full["equity"][: len(part["equity"]) - 1], part["equity"][:-1]))
    print(f"    equity path before the cut day, max |diff| {eqd:.2e}")
    return full


if __name__ == "__main__":
    coins = load_nine()
    for c, co in coins.items():
        print(f"  {c}: bars {len(co.t)} {L.ms_day(co.t[0])}..{L.ms_day(co.t[-1])}  funding stamps {len(co.fund_t)}")
    check_daily_vs_1d(coins)
    check_ols()
    check_synthetic()
    check_lookahead_and_accounting(coins)
