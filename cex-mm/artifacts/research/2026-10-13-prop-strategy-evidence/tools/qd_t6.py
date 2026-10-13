"""T6: judges' extra checks on the design series (weekly Mon TV 0.25 band 10%): edge-decay null, tax gain/loss split,
inactivity, plumbing-kill cost, rolling Sharpe."""
import csv, math, datetime as dt, collections, numpy as np
R = "qd_runs"
def daily(path):
    by = collections.OrderedDict()
    for r in csv.DictReader(open(path)):
        d = r["ts_utc"][:10]; by.setdefault(d, []).append((float(r["ret"]), float(r["gross"])))
    ds = sorted(by); rets = np.array([math.prod(1 + x for x, _ in by[d]) - 1 for d in ds]); g00 = np.array([by[d][0][1] for d in ds])
    return ds, rets, g00
ds, rule, g00 = daily(f"{R}/hourly_design_weekly_tv25_band10.csv"); _, basket, _ = daily(f"{R}/hourly_alwayslong_weekly_tv25.csv")
_, dly, _ = daily(f"{R}/hourly_daily_tv40.csv")
def rs(x, w): 
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        s = x[i - w + 1:i + 1]; out[i] = s.mean() / s.std(ddof=1) * math.sqrt(365)
    return out
W = 730
r24, b24 = rs(rule, W), rs(basket, W)
ret24 = np.array([np.prod(1 + rule[i - W + 1:i + 1]) - 1 if i >= W - 1 else np.nan for i in range(len(rule))])
print("=== T6a. Edge-decay null: rolling 24-month (730 d) Sharpe, design rule vs vol-scaled always-long 9-coin basket (same TV, cadence, costs) ===")
print(f"  basket full-sample: CAGR {np.prod(1+basket)**(365/len(basket))-1:+.1%} vol {basket.std(ddof=1)*math.sqrt(365):.1%} Sharpe {basket.mean()/basket.std(ddof=1)*math.sqrt(365):.2f}")
m = ~np.isnan(r24)
print(f"  windows: {m.sum()} days with a 24-month history ({ds[np.argmax(m)]}..{ds[-1]}); rule < basket on {(r24[m] < b24[m]).mean():.1%} of days; rule 24m return <= 0 on {(ret24[m] <= 0).mean():.1%} of days")
print(f"  rule rolling 24m Sharpe: min {np.nanmin(r24):.2f} ({ds[int(np.nanargmin(r24))]}) median {np.nanmedian(r24):.2f} max {np.nanmax(r24):.2f}; basket: min {np.nanmin(b24):.2f} median {np.nanmedian(b24):.2f} max {np.nanmax(b24):.2f}")
# month-end snapshots
print("  month-end snapshots (rule 24m Sharpe / basket 24m Sharpe / rule 24m return / kill?):")
seen = set(); line = []
for i, d in enumerate(ds):
    ym = d[:7]
    if i + 1 < len(ds) and ds[i + 1][:7] == ym: continue
    if np.isnan(r24[i]) or ym[-2:] not in ("03", "06", "09", "12"): continue
    line.append(f"{ym}: {r24[i]:.2f}/{b24[i]:.2f}/{ret24[i]:+.0%}{' KILL' if r24[i] < b24[i] else ''}")
print("   " + "  ".join(line))
# D3's original criterion: rule 24m return <= 0 while BTC 24m return > 0 -- needs BTC; use basket as proxy is wrong, load BTC closes
import sys; sys.path.insert(0, "/home/user/crypto-strategy/cex-mm/scripts"); import trend_backtest as tb
close, _ = tb.load_binance("trend-cache", dt.date(2026, 9, 30))
btc = close["BTC"]; k = 0
for i in range(W - 1, len(ds)):
    d1 = dt.date.fromisoformat(ds[i]); d0 = dt.date.fromisoformat(ds[i - W + 1]) - dt.timedelta(1)
    if d0 in btc and d1 in btc and ret24[i] <= 0 and btc[d1] / btc[d0] - 1 > 0: k += 1
print(f"  D3's original kill (24m return <= 0 while BTC 24m return > 0): fires on {k} days of {m.sum()}")

print("\n=== T6b. Tax split (VDA 30% on gross gains, no loss set-off) for the design line, per year ===")
pcd = collections.defaultdict(lambda: collections.defaultdict(float))
for r in csv.DictReader(open(f"{R}/design_pcd.csv")):
    pcd[r["coin"]][r["date"]] += float(r["pnl_frac"])
tl = collections.defaultdict(set)
for r in csv.DictReader(open(f"{R}/design_tlog.csv")):
    tl[r["coin"]].add(r["ts"][:10])
yrs = sorted({d[:4] for c in pcd for d in pcd[c]})
print(f"  {'year':>4} | {'net':>7} | per coin-DAY: {'gains':>7} {'losses':>7} {'after-tax':>9} | per coin-SEGMENT (held between trades): {'gains':>7} {'losses':>7} {'after-tax':>9}")
for y in yrs:
    gd = ld = gs = ls = 0.0
    for c in pcd:
        seg = 0.0; ds_c = sorted(d for d in pcd[c] if d[:4] == y)
        for d in ds_c:
            v = pcd[c][d]; gd += max(v, 0); ld += min(v, 0)
            seg += v
            if d in tl[c]:  # a trade on this day closes the segment that ended at this day's 00:00 (approximation: segment = PnL between trade days)
                gs += max(seg, 0); ls += min(seg, 0); seg = 0.0
        gs += max(seg, 0); ls += min(seg, 0)
    net = gd + ld
    print(f"  {y:>4} | {net:+7.1%} | {gd:7.1%} {ld:7.1%} {0.7*gd+ld:+9.1%} | {gs:7.1%} {ls:7.1%} {0.7*gs+ls:+9.1%}")

print("\n=== T6c. Inactivity and trade gaps (design line) ===")
flat = (g00 == 0); best = cur = 0; st = None; runs = []
for i, f in enumerate(flat):
    if f: cur += 1
    else:
        if cur: runs.append((cur, ds[i - cur], ds[i - 1]))
        cur = 0
if cur: runs.append((cur, ds[len(ds) - cur], ds[-1]))
runs.sort(reverse=True)
print(f"  days flat at 00:00 (gross 0): {flat.sum()} of {len(ds)} ({flat.mean():.1%}); longest flat streaks: " + ", ".join(f"{n}d {a}..{b}" for n, a, b in runs[:5]))
tdays = sorted({r["ts"][:10] for r in csv.DictReader(open(f"{R}/design_tlog.csv"))})
gaps = sorted([((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days, a, b) for a, b in zip(tdays, tdays[1:])], reverse=True)
print(f"  trade days: {len(tdays)}; longest gaps between any trade: " + ", ".join(f"{n}d {a}->{b}" for n, a, b in gaps[:5]) + f"; gaps > 30 d: {sum(1 for n,_,_ in gaps if n > 30)}")
print(f"  trades/yr (orders): {len(list(csv.DictReader(open(f'{R}/design_tlog.csv')))) / (len(ds) / 365):.0f}")

print("\n=== T6d. Plumbing kill: modelled cost per 30 days on the design line ===")
import json; st = json.load(open(f"{R}/t1_t3_store.json"))["D+ design weekly Mon TV0.25 band10% cap1.0"]
c30 = (st["fees"] + max(st["funding"], 0)) * 30 / 365
print(f"  fees/yr {st['fees']:.2%} + funding/yr {st['funding']:+.2%} -> modelled cost per 30 days {c30:.3%} of equity; 2x threshold {2*c30:.3%} = ${2*c30*1000:.2f} on $1,000, ${2*c30*5000:.2f} on $5,000")
sd30 = rule.std(ddof=1) * math.sqrt(30)
print(f"  30-day sd of the design's own return {sd30:.1%}: a tracking kill at {2*c30:.2%} is {2*c30/sd30:.2f} sd of a month's PnL; rounding noise at $1,000 (T5) is of the same order as the threshold")

print("\n=== T6e. Rolling 12-month Sharpe of the design line (how often it sits below the design's own forward range 0.5-0.9) ===")
r12 = rs(rule, 365); m12 = ~np.isnan(r12)
print(f"  12m Sharpe: < 0 on {(r12[m12] < 0).mean():.1%} of days, < 0.5 on {(r12[m12] < 0.5).mean():.1%}, > 0.9 on {(r12[m12] > 0.9).mean():.1%}; min {np.nanmin(r12):.2f} ({ds[int(np.nanargmin(r12))]}) max {np.nanmax(r12):.2f}")
r26 = rs(rule, 182); m26 = ~np.isnan(r26)
print(f"  26-week Sharpe (D3's live gate length): < 0 on {(r26[m26] < 0).mean():.1%} of days, sd across windows {np.nanstd(r26):.2f}, range [{np.nanmin(r26):.2f}, {np.nanmax(r26):.2f}]")
