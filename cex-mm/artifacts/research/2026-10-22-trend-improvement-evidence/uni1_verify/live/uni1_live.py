#!/usr/bin/env python3
"""Live-feasibility lens on UNI-1 (read-only on tools2/research2/universe; writes only stdout + live_out.json in this folder).

1. UNI-1 universes per reset (daily = Jan 1 row, weekly = first Sunday of January), 2020..2026, from variants_universe._membership.
2. 2027 proxy: _select at the panel's last row (2026-09-30) with the 2026 members as incumbents, floor 365 (same code path).
3. Delta India listing, contract value, 24 h turnover, mark price and top-of-book spread (universe/delta_perps.json, tickers.json,
   products.json, fetched 2026-10-20/21).
4. Full-signal position E x (TV/N)/max(vol60, 0.05) vs one contract's notional at $1,000 / $2,500 / $5,000, TV 0.25 and 0.40, N 9.
"""
import json, os, sys, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
sys.path.insert(0, f"{SP}/tools2")
sys.dont_write_bytecode = True
import data, rules, variants_universe as vu  # noqa: E402

OUT = f"{SP}/uni1_verify/live"
P = vu.load_pool(); ctx = vu._ctx(P)
T = ctx.T; last = T - 1
print(f"pool {len(P.coins)} symbols, rows {P.dates[0]}..{P.dates[-1]}")

res = {"resets": {}, "proxy2027": {}, "delta": {}, "sizing": {}}
spec = vu.SPECS["UNI-1"]
logs = {}
for cad in (vu.DAILY, vu.WEEKLY):
    U, log = vu._membership(ctx, cad, spec)
    logs[cad["name"]] = (U, log)
    print(f"\n== UNI-1 {cad['name']} resets")
    for e in log:
        r = P.idx[dt.date.fromisoformat(e["date"])]
        med = {}
        for m in e["members"]:
            j = ctx.coins.index(m)
            med[m] = float(np.nanmedian(ctx.Qc[max(r - 29, 0):r + 1, j]))
        print(f"  {e['date']}: " + " ".join(f"{m}({rk},${med[m]/1e6:.0f}M)" for m, rk in zip(e["members"], e["ranks"]))
              + f" | +{e['entrants']} -{e['leavers']}")
    res["resets"][cad["name"]] = [dict(date=e["date"], members=e["members"], ranks=e["ranks"], entrants=e["entrants"], leavers=e["leavers"]) for e in log]

# does a 2026 member delist / leave before 2026-09-30?
for cad in ("daily", "weekly"):
    U, log = logs[cad]
    mem26 = log[-1]["members"]
    alive = [m for m in mem26 if U[last, ctx.coins.index(m)]]
    print(f"{cad}: 2026 members still in U on {P.dates[last]}: {len(alive)}/{len(mem26)} {sorted(set(mem26)-set(alive))}")

# 2027 proxy: incumbents = 2026 members (daily log; weekly identical check below)
def proxy(log):
    inc = {ctx.coins.index(m): int(ctx.LIFE[last, ctx.coins.index(m)]) for m in log[-1]["members"]}
    sel, rank = vu._select(ctx, last, inc, spec["N"], spec["H"], spec["age"])
    return [ctx.coins[j] for j in sel], rank, inc

for cad in ("daily", "weekly"):
    sel, rank, inc = proxy(logs[cad][1])
    print(f"\n== 2027 proxy ({cad} incumbents) at {P.dates[last]}: {' '.join(sel)}")
    res["proxy2027"][cad] = sel
# full top-25 eligible list at the proxy row, plus a no-floor shadow (who is young but big)
sel, rank, inc = proxy(logs["daily"][1])
inv = sorted(rank.items(), key=lambda x: x[1])[:25]
print("  eligible ranking at 2026-09-30 (rank symbol median30 $M age incumbent):")
for j, rk in inv:
    med = float(np.nanmedian(ctx.Qc[last - 29:last + 1, j]))
    print(f"   {rk:2d} {ctx.coins[j]:10s} {med/1e6:9.1f} age {int(ctx.AGE[last, j]):5d} {'INC' if j in inc else ''}")
base = ctx.pos[last] & ~ctx.excl & (ctx.AGE[last] >= 30)
cols = np.flatnonzero(base)
med = np.nanmedian(ctx.Qc[last - 29:last + 1][:, cols], axis=0)
o = np.argsort(-med)[:20]
print("  no-age-floor ranking (top 20; age < 365 marked YOUNG):")
young_big = []
for i in o:
    j = cols[i]
    tag = "YOUNG" if ctx.AGE[last, j] < 365 else ""
    if tag: young_big.append(ctx.coins[j])
    print(f"   {ctx.coins[j]:10s} {med[i]/1e6:9.1f} age {int(ctx.AGE[last, j]):5d} {tag}")
res["young_in_top20_nofloor"] = young_big

# ---------------------------------------------------------------- Delta India
perps = json.load(open(f"{SP}/universe/delta_perps.json"))
tick = {t["symbol"]: t for t in json.load(open(f"{SP}/universe/tickers.json"))["result"]}
prods = {p["symbol"]: p for p in json.load(open(f"{SP}/universe/products.json"))["result"] if p.get("contract_type") == "perpetual_futures"}
by_under = {}
for p in perps:
    by_under.setdefault(p["underlying"], []).append(p)

def delta_for(coin):
    """Delta USD perp for a Binance base symbol (also try stripping 1000/1000000 prefixes)."""
    cands = [coin]
    for pre in ("1000000", "1000", "1M"):
        if coin.startswith(pre):
            cands.append(coin[len(pre):])
    for c in cands:
        if c in by_under:
            for p in by_under[c]:
                if p["symbol"] == f"{c}USD" or len(by_under[c]) == 1:
                    return p, c
            return by_under[c][0], c
        # products not in delta_perps (e.g. not USD-settled)
        s = f"{c}USD"
        if s in prods:
            pr = prods[s]
            return dict(symbol=s, underlying=c, contract_value=float(pr["contract_value"]), turnover_usd=float(tick.get(s, {}).get("turnover_usd") or 0),
                        launch=pr.get("launch_time", "")[:10]), c
    return None, None

coins_needed = sorted(set(res["resets"]["daily"][-1]["members"]) | set(res["resets"]["weekly"][-1]["members"]) |
                      set(res["proxy2027"]["daily"]) | set(res["proxy2027"]["weekly"]) | set(data.NINE))
print(f"\n== Delta India listing for 2026 members, 2027 proxy and the live nine (tickers snapshot {tick['BTCUSD']['time']})")
print(f"  {'coin':8s} {'delta':10s} {'cv':>8s} {'mark':>10s} {'1ct $':>8s} {'turn24h $M':>10s} {'OI $M':>7s} {'sprd bp':>7s} {'bid$':>7s} {'ask$':>7s} launch state taker maker")
for c in coins_needed:
    p, u = delta_for(c)
    j = ctx.coins.index(c)
    vol = float(ctx.vol[last, j]); bpx = float(ctx.Cc[last, j])
    row = dict(coin=c, vol60_0930=vol, binance_close_0930=bpx, binance_med30_usd=float(np.nanmedian(ctx.Qc[last - 29:last + 1, j])))
    if p is None:
        print(f"  {c:8s} NOT LISTED on Delta India (USD perp)   vol60 {vol:.2f}")
        row["listed"] = False
    else:
        t = tick.get(p["symbol"], {}); pr = prods.get(p["symbol"], {})
        mark = float(t.get("mark_price") or 0) or float('nan')
        q = t.get("quotes") or {}
        bb, ba = float(q.get("best_bid") or 'nan'), float(q.get("best_ask") or 'nan')
        sp = (ba - bb) / ((ba + bb) / 2) * 1e4 if np.isfinite(bb) and np.isfinite(ba) else float('nan')
        cv = float(p["contract_value"])
        bid_usd = float(q.get("bid_size") or 0) * cv * mark; ask_usd = float(q.get("ask_size") or 0) * cv * mark
        oi = float(t.get("oi_value_usd") or 0)
        print(f"  {c:8s} {p['symbol']:10s} {cv:8g} {mark:10.4g} {cv*mark:8.2f} {p['turnover_usd']/1e6:10.2f} {oi/1e6:7.2f} {sp:7.2f} {bid_usd:7.0f} {ask_usd:7.0f} "
              f"{p['launch']} {pr.get('state','?')}/{pr.get('trading_status','?')} {pr.get('taker_commission_rate','?')} {pr.get('maker_commission_rate','?')}  vol60 {vol:.2f} binance px {bpx:.4g}")
        row.update(listed=True, delta_symbol=p["symbol"], cv=cv, mark=mark, ct_usd=cv * mark, turnover24h=p["turnover_usd"], oi_usd=oi, spread_bps=sp,
                   bid_usd=bid_usd, ask_usd=ask_usd, launch=p["launch"], state=pr.get("state"), trading_status=pr.get("trading_status"),
                   taker=pr.get("taker_commission_rate"), maker=pr.get("maker_commission_rate"),
                   position_notional_limit=pr.get("position_notional_limit"), fallback_cv_coin=float(ctx.cv[j]),
                   fallback_ct_usd=float(ctx.cv[j]) * mark)
    res["delta"][c] = row

# ---------------------------------------------------------------- sizing vs one contract
N = 9
print("\n== Full-signal position (USD) and contracts = pos / (cv x mark), N 9; vol60 at 2026-09-30 (floor 0.05)")
for setname, members in (("2026 daily", res["resets"]["daily"][-1]["members"]), ("2026 weekly", res["resets"]["weekly"][-1]["members"]),
                         ("2027 proxy", res["proxy2027"]["daily"])):
    print(f"  -- {setname}: {' '.join(members)}")
    res["sizing"][setname] = {}
    for tv in (0.25, 0.40):
        for E in (1000, 2500, 5000):
            fails = []; line = []
            for c in members:
                d = res["delta"][c]
                pos = E * (tv / N) / max(d["vol60_0930"], 0.05)
                if not d.get("listed"):
                    fails.append(f"{c}(not listed)"); line.append(f"{c}:NA"); continue
                k = pos / d["ct_usd"]
                line.append(f"{c}:{k:.1f}")
                if k < 2:
                    fails.append(f"{c}({k:.2f})")
            res["sizing"][setname][f"TV{tv}_E{E}"] = dict(fails=fails, contracts=line)
            print(f"   TV {tv:.2f} E ${E:>5,}: contracts {' '.join(line)} | <2 ct: {fails if fails else 'none'}")
    # position $ vs Delta turnover
    print(f"   position $ at TV 0.40 E $5,000 vs Delta 24h turnover:")
    for c in members:
        d = res["delta"][c]
        pos = 5000 * (0.40 / N) / max(d["vol60_0930"], 0.05)
        if d.get("listed"):
            print(f"     {c:8s} pos ${pos:7.0f}  turnover ${d['turnover24h']/1e6:8.2f}M  pos/turnover {pos/d['turnover24h']:.2e}  {'< $0.5M/day' if d['turnover24h'] < 5e5 else ''}")

# what the backtest's whole-contract fallback cv implied vs the real Delta cv
print("\n== backtest whole-contract cv (data.CVALS else $25 / first Binance close) vs Delta's real cv, at today's mark")
for c in coins_needed:
    d = res["delta"][c]
    if d.get("listed"):
        print(f"   {c:8s} backtest cv {d['fallback_cv_coin']:10.4g} coin (${d['fallback_ct_usd']:8.2f}/ct today)  Delta cv {d['cv']:g} (${d['ct_usd']:.2f}/ct)  ratio {d['fallback_cv_coin']/d['cv']:.2f}")

# who moved in/out across resets: count names that would not be on Delta at each reset (Delta launch dates vs reset dates)
print("\n== Delta listing at each historical reset date (launch <= reset date?)")
for e in res["resets"]["daily"]:
    on = []
    for m in e["members"]:
        p, u = delta_for(m)
        on.append(f"{m}:{'Y' if p and p['launch'] <= e['date'] else ('later ' + p['launch'] if p else 'never')}")
    print(f"   {e['date']}: {' '.join(on)}")

json.dump(res, open(f"{OUT}/live_out.json", "w"), indent=1, default=float)
print(f"\nwrote {OUT}/live_out.json")
