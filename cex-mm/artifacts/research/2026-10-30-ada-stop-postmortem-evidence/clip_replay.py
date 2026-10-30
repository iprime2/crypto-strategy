#!/usr/bin/env python3
"""Test 1 of PREREG.md (real-fill clip replay) and the per-window attribution of the live run.

  python3 -I clip_replay.py DATA_DIR
DATA_DIR holds live_fills.json (Delta /v2/fills rows) and series.json (from make_series.py: shadow fair and
Delta L1 mid at 1 s, local receive time). Read-only, no network.
"""
import bisect, datetime as dt, json, os, sys

D = sys.argv[1]
CHARGED = "--fees-as-charged" in sys.argv  # exploratory: each real fill's own fee rate (Scalper Offer included)
RUN0, RUN1 = "2026-10-28T16:43:52Z", "2026-10-30T02:03:12Z"  # live.sh stop at 02:02:52Z, +20 s for late fills
FLAT_PX, TAKER_BPS, MAKER_BPS = 0.1861, 5.31, 2.12
WINDOWS = {"W1 29 Oct 19:30-21:30Z": ("2026-10-29T19:30:00Z", "2026-10-29T21:30:00Z"),
           "W2 29 Oct 23:30-01:30Z": ("2026-10-29T23:30:00Z", "2026-10-30T01:30:00Z")}
VARIANTS = [("A", 200, 600), ("B", 200, 400), ("C", 200, 200), ("D", 150, 300), ("E", 100, 300), ("F", 100, 200)]


def ms(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000


rows = [r for r in json.load(open(os.path.join(D, "live_fills.json"))) if r.get("product_symbol") == "ADAUSD"]
rows.sort(key=lambda r: r["created_at"])
run = [r for r in rows if ms(RUN0) <= ms(r["created_at"]) <= ms(RUN1)]
flat = [r for r in rows if r.get("role") == "taker" and ms(r["created_at"]) > ms(RUN1)]
assert len(flat) == 1 and float(flat[0]["size"]) == 18, flat
fills = [(ms(r["created_at"]), 1 if r["side"] == "buy" else -1, float(r["size"]), float(r["price"]),
          float(r["commission"]), r.get("role")) for r in run]
rate = {f[0]: f[4] / (f[2] * f[3]) * 1e4 for f in fills}  # bps actually charged on each fill
signed = sum(s * q for _, s, q, _, _, _ in fills) + 18  # flatten bought 18
q0 = -signed  # position the run inherited at its start
print(f"run fills {len(fills)} ({sum(f[5] == 'taker' for f in fills)} taker) + flatten 18 @ {flat[0]['price']}; "
      f"inherited position at start {q0:+.0f}")

S = json.load(open(os.path.join(D, "series.json")))
TS, FAIR, MID = S["ts"], S["fair"], S["mid"]
OFFSET = S["recv_minus_exch_ms"]  # move exchange times onto the VM receive clock


def at(series, t):
    i = bisect.bisect_right(TS, t + OFFSET) - 1
    return series[max(i, 0)]


# ---------------------------------------------------------------- venue sanity figure (variant A, as charged)
cash = sum(-s * q * p for _, s, q, p, _, _ in fills) + (-18 * float(flat[0]["price"]))
fees = sum(c for *_, c, _ in fills) + float(flat[0]["commission"])
start_mark = at(MID, ms(RUN0))
venue_pnl = cash - fees - q0 * start_mark  # inherited position valued at the start mid, closed flat at the end
notional = sum(q * p for _, _, q, p, _, _ in fills)
print(f"venue (as charged): cash {cash:+.4f}  fees {fees:.4f}  start mark {start_mark:.5f}  PnL {venue_pnl:+.2f}  "
      f"notional ${notional:,.0f}  PnLbp {venue_pnl / notional * 1e4:+.2f}")


# ---------------------------------------------------------------- Test 1
def replay(quote, cap, t0=None, t1=None, verbose=False):
    k = quote / 200
    inv = max(-cap, min(cap, q0 * k))
    cash = fees = notl = 0.0
    n = 0
    inv_at = {}
    path = []
    for t, s, q, p, _, role in fills:
        q = q * k
        if s * inv >= 0:
            q = min(q, cap - abs(inv))
        else:
            q = min(q, abs(inv) + cap)
        if q <= 1e-9:
            path.append((t, inv)); continue
        bps = rate[t] if CHARGED else (TAKER_BPS if role == "taker" else MAKER_BPS)
        cash -= s * q * p; fees += q * p * bps / 1e4; notl += q * p; n += 1
        inv += s * q
        path.append((t, inv))
    # close at the flatten price as a taker
    cash += inv * FLAT_PX; fees += abs(inv) * FLAT_PX * TAKER_BPS / 1e4
    start_inv = max(-cap, min(cap, q0 * k))
    pnl = cash - fees - start_inv * start_mark
    return dict(fills=n, notional=notl, pnl=pnl, bp=pnl / notl * 1e4 if notl else 0.0, path=path, start_inv=start_inv)


def window_pnl(path_fills, quote, cap, w0, w1):
    """Mark-to-market PnL of a variant inside [w0, w1]: fills in the window + position revaluation, fees."""
    k = quote / 200
    inv = max(-cap, min(cap, q0 * k))
    cash = fees = 0.0
    inv0 = None
    for t, s, q, p, _, role in fills:
        if t >= w0 and inv0 is None:
            inv0 = inv
        if t > w1:
            break
        q = q * k
        q = min(q, cap - abs(inv)) if s * inv >= 0 else min(q, abs(inv) + cap)
        if q <= 1e-9:
            continue
        if t >= w0:
            cash -= s * q * p; fees += q * p * (rate[t] if CHARGED else (TAKER_BPS if role == "taker" else MAKER_BPS)) / 1e4
        inv += s * q
    inv0 = inv if inv0 is None else inv0
    return cash - fees + inv * at(MID, w1) - inv0 * at(MID, w0)


print("\nTest 1: real-fill clip replay (gate PnLbp >= +1.0 over >= 300 fills)")
print(f"{'var':3s} {'quote':>5s} {'cap':>4s} {'fills':>6s} {'notional':>9s} {'PnL$':>7s} {'PnLbp':>6s} "
      + " ".join(f"{w.split()[0]:>7s}" for w in WINDOWS) + "  T1")
res = {}
for vid, quote, cap in VARIANTS:
    r = replay(quote, cap)
    ws = [window_pnl(None, quote, cap, ms(a), ms(b)) for a, b in WINDOWS.values()]
    ok = r["bp"] >= 1.0 and r["fills"] >= 300
    res[vid] = dict(quote=quote, cap=cap, fills=r["fills"], notional=r["notional"], pnl=r["pnl"], bp=r["bp"],
                    windows=dict(zip(WINDOWS, ws)), t1=ok)
    print(f"{vid:3s} {quote:5d} {cap:4d} {r['fills']:6d} {r['notional']:9,.0f} {r['pnl']:7.2f} {r['bp']:6.2f} "
          + " ".join(f"{x:7.2f}" for x in ws) + f"  {'PASS' if ok else 'fail'}")
# Delta wallet ledger over the run (mm-dash tx.json, 16:43:52Z-02:06Z): balance 332.59963 -> 330.82620, of which
# cashflow +2.25454, commission -3.94743, funding -0.08053; the position was 0 at the start (status at 16:45:05Z).
LEDGER = 2.25454 - 3.94743
print(f"sanity: variant A replay {res['A']['pnl']:+.2f} vs Delta ledger (cashflow + commission) {LEDGER:+.2f} "
      f"(diff {res['A']['pnl'] - LEDGER:+.2f}; the test is void if |diff| > 1.00); fills as charged {venue_pnl:+.2f}")


# ---------------------------------------------------------------- attribution of the real run per window
def attribute(w0, w1):
    inv = q0
    for t, s, q, *_ in fills:
        if t >= w0:
            break
        inv += s * q
    inv0 = inv
    capt = mo60 = fee = cash = notl = 0.0
    n = 0
    cap_ms = 0.0
    last_t = w0
    for t, s, q, p, c, role in fills:
        if t < w0:
            continue
        if t > w1:
            break
        if abs(inv) >= 600 - 1e-9:
            cap_ms += t - last_t
        last_t = t
        f = at(FAIR, t)
        capt += s * q * (f - p)
        mo60 += s * q * (at(FAIR, t + 60_000) - f)
        fee += c; cash -= s * q * p; notl += q * p; n += 1
        inv += s * q
    if abs(inv) >= 600 - 1e-9:
        cap_ms += w1 - last_t
    total = cash - fee + inv * at(MID, w1) - inv0 * at(MID, w0)
    hold = total - capt - mo60 + fee
    move = (at(MID, w1) / at(MID, w0) - 1) * 1e4
    return dict(fills=n, notional=notl, inv0=inv0, inv1=inv, total=total, capture=capt, mo60=mo60, fees=-fee,
                holding=hold, cap_share=cap_ms / (w1 - w0), move_bps=move)


print("\nReal run attribution, $ (capture and 60 s markout against the shadow's anchored fair; holding = the rest, "
      "i.e. position revaluation beyond 60 s)")
print(f"{'window':24s} {'fills':>5s} {'inv0':>5s} {'inv1':>5s} {'move':>6s} {'@cap':>5s} {'total':>7s} {'capt':>7s} "
      f"{'mo60':>7s} {'hold':>7s} {'fees':>7s}")
spans = dict(WINDOWS)
spans["whole run"] = (RUN0, RUN1)
att = {}
for name, (a, b) in spans.items():
    x = attribute(ms(a), ms(b))
    att[name] = x
    print(f"{name:24s} {x['fills']:5d} {x['inv0']:5.0f} {x['inv1']:5.0f} {x['move_bps']:6.0f} {x['cap_share']:5.0%} "
          f"{x['total']:7.2f} {x['capture']:7.2f} {x['mo60']:7.2f} {x['holding']:7.2f} {x['fees']:7.2f}")
json.dump(dict(venue_pnl=venue_pnl, q0=q0, test1=res, attribution=att), open(os.path.join(D, "test1_charged.json" if CHARGED else "test1.json"), "w"),
          indent=1)
