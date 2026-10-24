"""OPT-W1 data step: per (coin, Friday expiry) collect S0, settlement TWAP, the ATM strike pair and its MARKs,
daily 12:00 UTC MARKs for the daily-P&L Sharpe, and the labelled strangle neighbour's strikes and MARKs.
Spec: ../spec.md (sha256 in ../spec_sha256.txt). Public Delta India API only; no orders, no keys.
Usage: python3 -I fetch_weeks.py <screen_dir>"""
import json, os, sys, time, urllib.parse, urllib.request, statistics as st
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

B = "https://api.india.delta.exchange"
DIR = sys.argv[1]
CACHE = os.path.join(DIR, "cache", "candles")
os.makedirs(CACHE, exist_ok=True)
INDEX = {"BTC": ".DEXBTUSD", "ETH": ".DEETHUSD"}
FIRST = int(datetime(2023, 12, 1, tzinfo=timezone.utc).timestamp())
LAST = int(datetime(2026, 10, 23, 12, tzinfo=timezone.utc).timestamp())
WEEK, DAY, HOUR = 7 * 86400, 86400, 3600


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def get(params):
    key = os.path.join(CACHE, urllib.parse.urlencode(params).replace("/", "_").replace(":", "_").replace("%", "_")[:200] + ".json")
    if os.path.exists(key):
        with open(key) as f:
            return json.load(f)
    url = f"{B}/v2/history/candles?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            if not d.get("success", True):
                raise RuntimeError(str(d)[:200])
            with open(key, "w") as f:
                json.dump(d, f)
            return d
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def candles(symbol, res, start, end):
    d = get({"resolution": res, "symbol": symbol, "start": start, "end": end})
    return sorted(d.get("result") or [], key=lambda c: c["time"])


def mark_at(rows, t, lookback=HOUR):
    """open of the 1h candle stamped t, else close of the latest candle in [t - lookback, t)."""
    at = [r for r in rows if r["time"] == t]
    if at:
        return at[0]["open"]
    before = [r for r in rows if t - lookback <= r["time"] < t]
    return before[-1]["close"] if before else None


def mark_series(symbol, E, T):
    return candles("MARK:" + symbol, "1h", E - HOUR, T)


def week(und, T, contracts):
    E = T - WEEK
    rec = {"underlying": und, "expiry": T, "entry": E}
    idx_e = candles(INDEX[und], "1m", E - 300, E + 60)
    at = [c for c in idx_e if c["time"] == E]
    pre = [c for c in idx_e if E - 300 <= c["time"] < E]
    s0 = at[0]["open"] if at else (pre[-1]["close"] if pre else None)
    if s0 is None:
        return rec | {"skip": "no index at entry"}
    idx_s = candles(INDEX[und], "1m", T - 1800, T - 60)
    idx_s = [c for c in idx_s if T - 1800 <= c["time"] <= T - 60]
    if len(idx_s) < 20:
        return rec | {"s0": s0, "skip": f"settle candles {len(idx_s)} < 20"}
    settle = st.mean(c["close"] for c in idx_s)
    rec |= {"s0": s0, "settle": settle, "n_settle": len(idx_s)}
    live = [c for c in contracts if c["launch_time"] and ts(c["launch_time"]) <= E]
    calls = {c["strike"]: c for c in live if c["type"] == "C"}
    puts = {c["strike"]: c for c in live if c["type"] == "P"}
    both = sorted(set(calls) & set(puts), key=lambda k: (abs(k - s0), k))
    rec["n_live_strikes_both"] = len(both)
    series = {}
    chosen = None
    tried = []
    for K in both[:3]:
        cs, ps = calls[K]["symbol"], puts[K]["symbol"]
        for s in (cs, ps):
            if s not in series:
                series[s] = mark_series(s, E, T)
        mc, mp = mark_at(series[cs], E), mark_at(series[ps], E)
        tried.append({"K": K, "mc": mc, "mp": mp})
        if mc and mp and mc > 0 and mp > 0:
            chosen = (K, cs, ps, mc, mp)
            break
    rec["tried"] = tried
    if chosen is None:
        return rec | {"skip": "no ATM strike with both marks"}
    K, cs, ps, mc, mp = chosen
    daily = []
    for k in range(1, 7):
        t = E + k * DAY
        daily.append({"t": t, "mc": mark_at(series[cs], t, lookback=DAY), "mp": mark_at(series[ps], t, lookback=DAY)})
    rec |= {"K": K, "call": cs, "put": ps, "mc": mc, "mp": mp, "daily": daily}
    # labelled neighbour: strangle at S0 +/- m, m = (mc + mp) / 2
    m = (mc + mp) / 2
    nb = {"m": m}
    ck = sorted(calls, key=lambda k: (abs(k - (s0 + m)), -k))
    pk = sorted(puts, key=lambda k: (abs(k - (s0 - m)), k))
    for typ, ordered, book in (("C", ck, calls), ("P", pk, puts)):
        if not ordered:
            nb[typ] = None
            continue
        first = ordered[0]
        cands = [first] + (sorted(k for k in book if k > first)[:2] if typ == "C" else sorted((k for k in book if k < first), reverse=True)[:2])
        got = None
        for kk in cands:
            sym = book[kk]["symbol"]
            if sym not in series:
                series[sym] = mark_series(sym, E, T)
            mk = mark_at(series[sym], E)
            if mk and mk > 0:
                got = {"K": kk, "symbol": sym, "mark": mk}
                break
        nb[typ] = got
    rec["strangle"] = nb
    return rec


def main():
    products = json.load(open(os.path.join(DIR, "cache", "expired_options.json")))
    by = {}
    for c in products:
        s = c.get("settlement_time")
        if not s or not s.endswith("12:00:00Z"):
            continue
        T = ts(s)
        if not (FIRST <= T <= LAST) or datetime.fromtimestamp(T, timezone.utc).weekday() != 4:
            continue
        by.setdefault((c["underlying"], T), []).append(c)
    keys = sorted(k for k, cs in by.items() if any(c["launch_time"] and ts(c["launch_time"]) <= k[1] - WEEK for c in cs))
    allfri = sorted(by)
    step0 = {u: {"friday_12utc_expiries_listed": sum(1 for k in allfri if k[0] == u),
                 "with_contract_live_168h_before": sum(1 for k in keys if k[0] == u),
                 "first": min((datetime.fromtimestamp(k[1], timezone.utc).strftime("%Y-%m-%d") for k in keys if k[0] == u), default=None),
                 "last": max((datetime.fromtimestamp(k[1], timezone.utc).strftime("%Y-%m-%d") for k in keys if k[0] == u), default=None)}
             for u in ("BTC", "ETH")}
    missing = {u: [datetime.fromtimestamp(k[1], timezone.utc).strftime("%Y-%m-%d") for k in allfri if k[0] == u and k not in set(keys)] for u in ("BTC", "ETH")}
    step0["fridays_without_168h_contract"] = missing
    print(json.dumps(step0, indent=1), file=sys.stderr)
    json.dump(step0, open(os.path.join(DIR, "out", "step0.json"), "w"), indent=1)
    out = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(week, u, T, by[(u, T)]) for u, T in keys]
        for i, f in enumerate(futs):
            try:
                out.append(f.result())
            except Exception as e:
                u, T = keys[i]
                out.append({"underlying": u, "expiry": T, "entry": T - WEEK, "skip": f"error {e}"})
            if i % 25 == 0:
                print("loaded", i, "/", len(futs), file=sys.stderr, flush=True)
    out.sort(key=lambda r: (r["underlying"], r["expiry"]))
    json.dump(out, open(os.path.join(DIR, "out", "weeks.json"), "w"))
    print("weeks", len(out), "skipped", sum(1 for r in out if r.get("skip")), file=sys.stderr)


if __name__ == "__main__":
    main()
