"""Re-derive OPT-W1 coin-weeks by hand from the cached raw Delta candles and the product list (own code, no network)."""
import json, os, sys, urllib.parse, statistics as st
from datetime import datetime, timezone
O = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/ext_repo/review/screens/OPT-W1 weekly short ATM straddle on Delta BTC/ETH"
CA = os.path.join(O, "cache", "candles")
IDX = {"BTC": ".DEXBTUSD", "ETH": ".DEETHUSD"}
def raw(params):
    k = os.path.join(CA, urllib.parse.urlencode(params).replace("/", "_").replace(":", "_").replace("%", "_")[:200] + ".json")
    return sorted(json.load(open(k)).get("result") or [], key=lambda c: c["time"])
def tsz(s): return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
prods = json.load(open(os.path.join(O, "cache", "expired_options.json")))
weeks = {(w["underlying"], w["expiry"]): w for w in json.load(open(os.path.join(O, "out", "weeks.json")))}
def one(u, day, h=0.05):
    T = int(datetime.fromisoformat(day + "T12:00:00+00:00").timestamp()); E = T - 7 * 86400
    ie = raw({"resolution": "1m", "symbol": IDX[u], "start": E - 300, "end": E + 60})
    s0 = next((c["open"] for c in ie if c["time"] == E), None)
    isx = [c for c in raw({"resolution": "1m", "symbol": IDX[u], "start": T - 1800, "end": T - 60}) if T - 1800 <= c["time"] <= T - 60]
    ST = st.mean(c["close"] for c in isx)
    cs = [p for p in prods if p["underlying"] == u and p.get("settlement_time") == datetime.fromtimestamp(T, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") and p["launch_time"] and tsz(p["launch_time"]) <= E]
    C = {p["strike"]: p["symbol"] for p in cs if p["type"] == "C"}; P = {p["strike"]: p["symbol"] for p in cs if p["type"] == "P"}
    Ks = sorted(set(C) & set(P), key=lambda k: (abs(k - s0), k))
    for K in Ks[:3]:
        mc = [r for r in raw({"resolution": "1h", "symbol": "MARK:" + C[K], "start": E - 3600, "end": T}) if r["time"] == E]
        mp = [r for r in raw({"resolution": "1h", "symbol": "MARK:" + P[K], "start": E - 3600, "end": T}) if r["time"] == E]
        if mc and mp: mc, mp = mc[0]["open"], mp[0]["open"]; break
    pc, pp = mc * (1 - h), mp * (1 - h)
    ic, ip = max(ST - K, 0), max(K - ST, 0)
    fee = min(1e-4 * s0, 0.035 * pc) * 1.18 + min(1e-4 * s0, 0.035 * pp) * 1.18 + (1e-4 * ST * 1.18 if ic > 0 else 0) + (1e-4 * ST * 1.18 if ip > 0 else 0)
    pnl = (pc + pp - ic - ip - fee) / s0 * 1e4
    w = weeks[(u, T)]
    print(f"{u} exp {day}: S0 {s0} (rep {w['s0']}) ST {ST:.2f} (rep {w['settle']:.2f}, n {len(isx)}) K {K} (rep {w['K']}) |K/S0-1| {abs(K/s0-1)*1e4:.0f} bps"
          f" mc {mc} mp {mp} (rep {w['mc']} {w['mp']}) credit@{h} {(pc+pp)/s0*1e4:.1f} payout {(ic+ip)/s0*1e4:.1f} fees {fee/s0*1e4:.2f} pnl {pnl:+.1f}")
    return pnl
for u, day in [("BTC", "2025-10-17"), ("ETH", "2025-10-17"), ("BTC", "2025-11-28"), ("BTC", "2026-08-21"), ("ETH", "2026-08-21"), ("ETH", "2026-02-06"), ("BTC", "2024-03-01"), ("ETH", "2025-10-10")]:
    one(u, day)
