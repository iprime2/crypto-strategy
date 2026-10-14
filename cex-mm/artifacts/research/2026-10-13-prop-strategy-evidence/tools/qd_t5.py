"""T5b: the design (weekly Mon TV 0.25, 10% notional band, whole Delta contracts) on Delta India prices 2024-08-10..2026-10-12
at $500/$1,000/$2,500/$5,000, daily-bar engine (Delta has no hourly archive here). Also band 0 and TV 0.40 for comparison,
and the unrounded line. Contract values: from the repo's live /v2/products call in T5 (same as the memo)."""
import sys, datetime as dt, collections, math; sys.path.insert(0, "tools")
import qd_engine as E
tb = E.tb
CV = E.CVALS; COST = (tb.TAKER_BPS + tb.SLIPPAGE_BPS) / 1e4
dclose, dfund = tb.load_delta(E.CACHE, dt.date(2026, 10, 12))
S, END = dt.date(2024, 8, 10), dt.date(2026, 10, 12)

def run(tv, capital, band, wd=6, rebal="weekly"):
    days = sorted(set().union(*[set(dclose[c]) for c in tb.COINS]))
    eq, units, out = float(capital or 1.0), {}, collections.OrderedDict(); fees = 0.0; gross = []; trades = 0; e0 = eq
    for d, nxt in zip(days, days[1:]):
        if not (S <= nxt <= END): continue
        if rebal == "daily" or d.weekday() == wd:
            w = tb.target_weights(dclose, d, tb.LOOKS, tb.VOL_WIN, tv, True)
            g = sum(w.values()); w = {c: x / g for c, x in w.items()} if g > 1.0 else w
            new = dict(units)
            for c in set(w) | set(units):
                if nxt not in dclose[c]: new.pop(c, None); continue
                tgt = w.get(c, 0.0) * eq / dclose[c][d]
                if capital: tgt = round(tgt / CV[c]) * CV[c]
                cur = units.get(c, 0.0)
                if tgt and band and abs(tgt - cur) < band * abs(tgt): tgt = cur
                if abs(tgt - cur) > 1e-15: trades += 1
                if tgt: new[c] = tgt
                else: new.pop(c, None)
        else:
            new = {c: u for c, u in units.items() if nxt in dclose[c]}
        traded = sum(abs(new.get(c, 0) - units.get(c, 0)) * dclose[c][d] for c in set(new) | set(units))
        pnl = sum(u * (dclose[c][nxt] - dclose[c][d]) for c, u in new.items())
        fpay = sum(u * dclose[c][d] * dfund[c].get(nxt, 0.0) for c, u in new.items())
        r = (pnl - fpay - traded * COST) / eq; fees += traded * COST / eq
        gross.append(sum(abs(u) * dclose[c][d] for c, u in new.items()) / eq)
        eq *= 1 + r; out[nxt] = r; units = new
    s = E.stats(out); yrs = len(out) / 365
    return (f"CAGR {s['cagr']:+6.1%} vol {s['vol']:5.1%} Sharpe {s['sharpe']:5.2f} maxDD {s['mdd']:6.1%} worst {s['worst']:+6.2%} "
            f"gross avg {sum(gross)/len(gross):.2f}x max {max(gross):.2f}x trades/yr {trades/yrs:4.0f} fees/yr {fees/yrs:.2%} "
            f"final ${eq:,.0f} (${e0:,.0f}) " + " ".join(f"{y}:{v:+.1%}" for y, v in s["yearly"].items()))

print("Delta India 2024-08-10..2026-10-12, weekly Monday 00:00 UTC decision, taker 5.31 + 2 bps, Delta funding")
for tv in (0.25, 0.40):
    for band in (0.10, 0.0):
        print(f"-- TV {tv:.2f} band {band:.0%}")
        for cap in (500, 1000, 2500, 5000):
            print(f"  ${cap:>5,} whole contracts: " + run(tv, cap, band))
        print(f"  unrounded          : " + run(tv, None, band))
print("-- daily cadence TV 0.40 band 0 (repo rule) unrounded, for reference: " + run(0.40, None, 0.0, rebal="daily"))
print("-- daily cadence TV 0.25 band 10% $1,000: " + run(0.25, 1000, 0.10, rebal="daily"))
