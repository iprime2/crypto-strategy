"""Delta India option chain snapshot: per expiry ATM IV, ATM quoted spread, OI and 24h
turnover; plus a CBOE-style 30-day variance-swap vol from mid prices (r = 0, forward
from put-call parity), i.e. what the ext repo's VIX Calculator would produce if fixed."""
import json, sys, math, datetime as dt, collections
t = json.load(open(sys.argv[1]))["result"]
p = {x["symbol"]: x for x in json.load(open(sys.argv[2]))["result"]}
now = max(x["timestamp"] for x in t) / 1e6
print("snapshot", dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat())
f = lambda v: float(v) if v not in (None, "") else None
by = collections.defaultdict(lambda: collections.defaultdict(dict))
spot = {}
for x in t:
    if x.get("contract_type") not in ("call_options", "put_options"): continue
    pr = p.get(x["symbol"])
    if not pr: continue
    u = x["underlying_asset_symbol"]; exp = pr["settlement_time"]
    k = float(x["strike_price"]); typ = "C" if x["contract_type"] == "call_options" else "P"
    q = x.get("quotes") or {}
    by[(u, exp)][k][typ] = dict(bid=f(q.get("best_bid")), ask=f(q.get("best_ask")), mark=f(x.get("mark_price")),
                                iv=f(q.get("mark_iv")), oi=f(x.get("oi_value_usd")) or 0, to=f(x.get("turnover_usd")) or 0)
    spot[u] = f(x.get("spot_price"))
def mid(o):
    if o["bid"] and o["ask"] and o["bid"] > 0: return (o["bid"] + o["ask"]) / 2
    return None
def sig2(ch, T, S):
    ks = sorted(k for k in ch if "C" in ch[k] and "P" in ch[k] and mid(ch[k]["C"]) and mid(ch[k]["P"]))
    if len(ks) < 3: return None
    kstar = min(ks, key=lambda k: abs(mid(ch[k]["C"]) - mid(ch[k]["P"])))
    F = kstar + mid(ch[kstar]["C"]) - mid(ch[kstar]["P"])
    K0 = max([k for k in ks if k <= F] or [ks[0]])
    strip = []
    for k in sorted(ch):
        if k < K0 and "P" in ch[k]:
            m = mid(ch[k]["P"])
        elif k > K0 and "C" in ch[k]:
            m = mid(ch[k]["C"])
        elif k == K0:
            m = (mid(ch[k]["C"]) + mid(ch[k]["P"])) / 2
        else: m = None
        if m: strip.append((k, m))
    tot = 0
    for j, (k, q) in enumerate(strip):
        dk = (strip[1][0] - k) if j == 0 else (k - strip[j-1][0]) if j == len(strip) - 1 else (strip[j+1][0] - strip[j-1][0]) / 2
        tot += q * dk / k ** 2
    return 2 / T * tot - (F / K0 - 1) ** 2 / T, F, K0, len(strip)
res = {}
for (u, exp), ch in sorted(by.items()):
    if u not in ("BTC", "ETH", "XAUT"): continue
    T = (dt.datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp() - now) / (365 * 86400)
    S = spot[u]
    katm = min((k for k in ch if "C" in ch[k] and "P" in ch[k]), key=lambda k: abs(k - S))
    c, pp = ch[katm]["C"], ch[katm]["P"]
    def sp(o):
        m = mid(o); return (o["ask"] - o["bid"]) / m * 100 if m else None
    oi = sum(o["oi"] for k in ch for o in ch[k].values()); to = sum(o["to"] for k in ch for o in ch[k].values())
    straddle_mid = (mid(c) or float("nan")) + (mid(pp) or float("nan"))
    st_bps = straddle_mid / S * 1e4
    st_spread_bps = ((c["ask"] or 0) - (c["bid"] or 0) + (pp["ask"] or 0) - (pp["bid"] or 0)) / S * 1e4
    s = sig2(ch, T, S)
    res[(u, exp)] = (T, s)
    print(f"{u:4s} {exp[:16]} T={T*365:6.2f}d strikes={len(ch):3d} ATM K={katm:g} ivC={c['iv']} ivP={pp['iv']} "
          f"sprdC={sp(c) if sp(c) is None else round(sp(c),1)}% sprdP={sp(pp) if sp(pp) is None else round(sp(pp),1)}% "
          f"straddle mid={st_bps:.0f}bps quoted b/a width={st_spread_bps:.1f}bps | OI ${oi/1e6:.2f}M 24h turnover ${to/1e6:.2f}M "
          f"| varswap vol={math.sqrt(s[0])*100 if s and s[0]>0 else float('nan'):.1f}% (n={s[3] if s else 0})")
for u in ("BTC", "ETH"):
    xs = sorted((T, s) for (uu, e), (T, s) in res.items() if uu == u and s and s[0] > 0)
    tgt = 30 / 365
    lo = [x for x in xs if x[0] <= tgt]; hi = [x for x in xs if x[0] > tgt]
    if lo and hi:
        (T1, s1), (T2, s2) = lo[-1], hi[0]
        w = (T2 - tgt) / (T2 - T1)
        v = (T1 * s1[0] * w + T2 * s2[0] * (1 - w)) / tgt
        print(f"{u} 30-day CBOE-style vol from Delta mids: {math.sqrt(v)*100:.1f}% (T1={T1*365:.1f}d, T2={T2*365:.1f}d)")
