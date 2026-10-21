#!/usr/bin/env python3
"""Delta India side of the UNI-1 live lens, from the read-only snapshots in ./dl (fetched 2026-10-21 ~22:30 UTC).
Per coin: contract value, mark, 1-contract notional, 24 h turnover now, 30-day median Delta turnover (1d candles: volume is in
contracts -> x cv x close), Delta 60-day CC vol, L2 spread and depth, taker cost to fill the full-signal position, the minimum
equity for >= 2 contracts at full signal, and a Delta-own-turnover top-9 ranking (age >= 365 days on Delta)."""
import json, os, sys, math, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); DL = f"{HERE}/dl"
live = json.load(open(f"{HERE}/live_out.json"))
tick = {t["symbol"]: t for t in json.load(open(f"{DL}/tickers_now.json"))["result"]}
perps = {p["symbol"]: p for p in json.load(open(f"{HERE}/../../universe/delta_perps.json"))}
N = 9
SETS = {"2026": live["resets"]["daily"][-1]["members"], "2027proxy": live["proxy2027"]["daily"]}
CAND = "HYPE NEAR UNI SUI ENA ADA ARB TAO WLD PUMP FIL AKE TRUMP AAVE".split()  # eligible ranks 6..23 at the 2027 proxy row
NINE = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
TAKER = 5.31  # bps incl. GST (CLAUDE.md); the backtest charges 5.31 + 2.0


def candles(sym, path=None):
    r = json.load(open(path or f"{DL}/c1d_{sym}.json")).get("result") or []
    r = sorted(r, key=lambda b: b["time"])
    today = int(dt.datetime(2026, 10, 21, tzinfo=dt.timezone.utc).timestamp())
    return [b for b in r if b["time"] < today]  # complete days only


def walk(levels, qty):
    """avg price taking qty contracts; None if the book (depth 50) is too thin."""
    got, cost = 0.0, 0.0
    for px, sz in levels:
        take = min(sz, qty - got); got += take; cost += take * px
        if got >= qty - 1e-9:
            return cost / got
    return None


out = {}
coins = sorted(set(sum(SETS.values(), [])) | set(CAND) | set(NINE))
print(f"{'coin':9s} {'cv':>7s} {'mark':>10s} {'1ct$':>7s} {'t24h$M':>7s} {'med30$M':>7s} {'min30$M':>7s} {'dVol60':>6s} {'bVol60':>6s} "
      f"{'sprd':>5s} {'d10bp$':>8s} {'d25bp$':>8s} | full pos $ @E5k TV.40 ct, take cost bps (half-spread+walk) | Emin2ct TV.40 / TV.25")
for c in coins:
    s = f"{c}USD"
    if s not in tick:
        print(f"{c:9s} not on Delta"); continue
    t = tick[s]; cv = float(t["contract_value"]); mark = float(t["mark_price"]); ct = cv * mark
    cd = candles(s)
    tv_d = [b["volume"] * cv * b["close"] for b in cd[-30:]]
    cl = np.array([b["close"] for b in cd], float)
    lr = np.diff(np.log(cl))[-60:]
    dvol = float(np.sqrt(np.mean(lr * lr) * 365)) if len(lr) >= 30 else float("nan")
    bvol = live["delta"].get(c, {}).get("vol60_0930")
    if bvol is None:
        bvol = float("nan")
    vol = bvol if np.isfinite(bvol) else dvol
    book = json.load(open(f"{DL}/l2_{s}.json"))["result"]
    bids = [(float(x["price"]), float(x["size"])) for x in book["buy"]]; asks = [(float(x["price"]), float(x["size"])) for x in book["sell"]]
    mid = (bids[0][0] + asks[0][0]) / 2; spr = (asks[0][0] - bids[0][0]) / mid * 1e4
    d10 = sum(sz * cv * px for px, sz in asks if px <= mid * (1 + 10e-4)) ; d25 = sum(sz * cv * px for px, sz in asks if px <= mid * (1 + 25e-4))
    row = dict(cv=cv, mark=mark, ct_usd=ct, t24h=float(t["turnover_usd"]), med30=float(np.median(tv_d)) if tv_d else float("nan"),
               min30=float(np.min(tv_d)) if tv_d else float("nan"), n_days=len(cd), dvol60=dvol, bvol60=bvol, spread_bps=spr, ask_depth_10bp=d10,
               ask_depth_25bp=d25, launch=perps.get(s, {}).get("launch"))
    take = {}
    for E in (1000, 2500, 5000):
        for tv in (0.25, 0.40):
            pos = E * (tv / N) / max(vol, 0.05); q = round(pos / ct)
            ap = walk(asks, q) if q > 0 else None
            take[f"E{E}_TV{tv}"] = dict(pos=pos, contracts_exact=pos / ct, q=q, cost_bps=(ap / mid - 1) * 1e4 if ap else (None if q > 0 else 0.0))
    row["take"] = take
    row["Emin_2ct"] = {tv: 2 * ct * max(vol, 0.05) * N / tv for tv in (0.25, 0.40)}
    out[c] = row
    k = take["E5000_TV0.4"]
    cb = f"{k['cost_bps']:.1f}" if k["cost_bps"] is not None else "BOOK<q"
    print(f"{c:9s} {cv:7g} {mark:10.4g} {ct:7.2f} {row['t24h']/1e6:7.2f} {row['med30']/1e6:7.2f} {row['min30']/1e6:7.2f} {dvol:6.2f} {bvol:6.2f} "
          f"{spr:5.1f} {d10:8.0f} {d25:8.0f} | ${k['pos']:5.0f} {k['q']:4d} ct {cb:>6s} | ${row['Emin_2ct'][0.40]:7,.0f} / ${row['Emin_2ct'][0.25]:7,.0f}  launch {row['launch']}")

print("\nGate (>= 2 contracts at full signal; plan exempts the live nine) per set and capital, Binance vol60 at 2026-09-30, Delta mark now")
for name, mem in SETS.items():
    for tv in (0.25, 0.40):
        for E in (1000, 2500, 5000):
            fail_all = [c for c in mem if out[c]["take"][f"E{E}_TV{tv}"]["contracts_exact"] < 2]
            zero = [c for c in mem if out[c]["take"][f"E{E}_TV{tv}"]["q"] == 0]
            fail_gate = [c for c in fail_all if c not in NINE]
            print(f"  {name:9s} TV {tv:.2f} ${E:>5,}: <2 ct {fail_all} | gate-relevant (non-nine) {fail_gate} | rounds to 0 ct {zero}")
    em = max(max(out[c]["Emin_2ct"][0.40] for c in mem), 0); em25 = max(out[c]["Emin_2ct"][0.25] for c in mem)
    print(f"  {name:9s} equity for every member >= 2 ct: TV 0.40 ${em:,.0f} ({max(mem, key=lambda c: out[c]['Emin_2ct'][0.40])}), "
          f"TV 0.25 ${em25:,.0f} ({max(mem, key=lambda c: out[c]['Emin_2ct'][0.25])})")

print("\nTaker cost to fill the full-signal position from flat (bps vs mid, walk of the live L2 ask side) vs the backtest's 2.0 bps slippage:")
for name, mem in SETS.items():
    for key in ("E1000_TV0.4", "E5000_TV0.4", "E5000_TV0.25"):
        vals = {c: out[c]["take"][key]["cost_bps"] for c in mem}
        print(f"  {name:9s} {key:13s} " + " ".join(f"{c}:{v:.1f}" if v is not None else f"{c}:THIN" for c, v in vals.items()))

# Delta-own-turnover ranking: 30-day median of daily turnover, perps with >= 365 days on Delta, crypto only
EXCL = set("XAU XAG XPT XPD PAXG XAUT COPPER CL BZ NATGAS AAPL AMZN AVGO BABA COIN CRCL EWJ EWY GOOGL HOOD INTC META MSFT MSTR MU NVDA PLTR QQQ SPY TSLA TSM SNDK USDC USTC BTCDOM DEFI".split())
rk = []
for fn in os.listdir(f"{DL}/c1d_all"):
    s = fn[:-5]; p = perps[s]
    if p["underlying"] in EXCL or "ON" == p["underlying"][-2:] and p["underlying"] not in ("TON", "ONDO", "ZRON"):
        pass
    cd = candles(s, f"{DL}/c1d_all/{fn}")
    if len(cd) < 30:
        continue
    cv = float(p["contract_value"])
    med = float(np.median([b["volume"] * cv * b["close"] for b in cd[-30:]]))
    rk.append((med, p["underlying"], s, p["launch"]))
rk.sort(reverse=True)
print("\nDelta-own 30-day median turnover ranking (launch <= 2025-10-21; metals/xStocks/indices shown, marked X):")
for i, (m, u, s, l) in enumerate(rk[:25]):
    print(f"  {i+1:2d} {u:9s} ${m/1e6:8.2f}M launch {l} {'X' if u in EXCL else ''}")
crypto = [u for m, u, s, l in rk if u not in EXCL]
print("  Delta-own top-9 crypto:", crypto[:9])
json.dump(dict(coins=out, delta_rank=[dict(med30=m, underlying=u, symbol=s, launch=l) for m, u, s, l in rk]), open(f"{HERE}/delta_out.json", "w"), indent=1)
print(f"wrote {HERE}/delta_out.json")
