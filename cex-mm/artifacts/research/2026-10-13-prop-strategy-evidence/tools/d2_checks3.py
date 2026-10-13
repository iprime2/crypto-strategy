#!/usr/bin/env python3
"""D2 checks, part 3 (read-only on the repo): the rule's target positions on the last cached Delta day (2026-10-12),
TV 0.25 and 0.40, per-coin cap 0.25, whole Delta contracts at $1,000 and $5,000. Shows the starting state a user
would see today. Also prints each coin's 20/60/120-day signs, 60-day vol and the resulting weight."""
import sys, datetime as dt, math
sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts")
import trend_backtest as tb  # noqa: E402
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
CVALS = {"BTC": 0.001, "BNB": 0.1, "ETH": 0.01, "LTC": 0.1, "LINK": 1, "DOGE": 100, "BCH": 0.01, "XRP": 1, "ADA": 1}
close, fund = tb.load_delta(f"{SP}/trend-cache", dt.date(2026, 10, 12))
d = max(close["BTC"])
print(f"last Delta close in cache: {d}")
for tv in (0.25, 0.40):
    w = tb.target_weights(close, d, tb.LOOKS, tb.VOL_WIN, tv, True)
    w = {c: max(min(x, 0.25), -0.25) for c, x in w.items()}
    print(f"\n-- target vol {tv:.0%}, per-coin cap 0.25, long-only; weights as a fraction of equity E")
    print(f"{'coin':5s} {'close':>10s} {'r20':>7s} {'r60':>7s} {'r120':>7s} {'sig':>5s} {'vol60':>6s} {'w':>7s} | {'n@$1k':>6s} {'$':>7s} | {'n@$5k':>6s} {'$':>8s}")
    tot1 = tot5 = 0.0
    for c in tb.COINS:
        px = close[c][d]
        def ret(k):
            p0 = close[c].get(d - dt.timedelta(days=k))
            return (px / p0 - 1) if p0 else float("nan")
        r20, r60, r120 = ret(20), ret(60), ret(120)
        sig = sum((1 if r > 0 else -1) for r in (r20, r60, r120)) / 3
        hist = [close[c].get(d - dt.timedelta(k)) for k in range(tb.VOL_WIN + 1)]
        vol = math.sqrt(sum(math.log(hist[k] / hist[k + 1]) ** 2 for k in range(tb.VOL_WIN)) / tb.VOL_WIN * 365) if all(hist) else float("nan")
        wi = w.get(c, 0.0)
        n1 = round(wi * 1000 / (px * CVALS[c])); n5 = round(wi * 5000 / (px * CVALS[c]))
        v1 = n1 * px * CVALS[c]; v5 = n5 * px * CVALS[c]; tot1 += v1; tot5 += v5
        print(f"{c:5s} {px:10.4f} {r20:+7.1%} {r60:+7.1%} {r120:+7.1%} {sig:+5.2f} {vol:6.0%} {wi:7.3f} | {n1:6d} {v1:7.0f} | {n5:6d} {v5:8.0f}")
    print(f"gross target {sum(abs(x) for x in w.values()):.3f}x E; rounded gross ${tot1:.0f} at $1,000 ({tot1/1000:.2f}x), ${tot5:.0f} at $5,000 ({tot5/5000:.2f}x)")
    print(f"day stop at 0.05 x TV = {0.05*tv:.2%} of E -> ${0.05*tv*1000:.0f} at $1,000, ${0.05*tv*5000:.0f} at $5,000")
