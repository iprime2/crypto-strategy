#!/usr/bin/env python3
"""Read-only counterfactual: would leaning both ADA quotes against our own inventory have cut inventory losses?

Lean L (bps at the cap): both quotes move by -L * q / cap bps, q = our position as the bot saw it LAG ms earlier
(a fill reaches the loop within one 400 ms tick, then an edit takes ~0.6 s on mainnet). Long -> both quotes
lower (the ask fills sooner, the bid later); short -> both higher. L = 0 replays the real quotes.

Unlike lean_replay.py (2026-10-21 memo), the position is re-simulated: each variant keeps its own q, the cap
switches its adding side off (and clips that side's size to the room), and fills change q. Quote rebuild,
tape and fill rule are lean_replay.py's (calibrated to < 2% phantom fills there):
  - our resting bid/ask come from MM_ORDER places/edits (send time = ack - ms; while an edit is in flight the
    more passive of old and new rests); a quote is gone from its order's last fill (exchange time), a pull or
    a cancel-all;
  - taker sweeps from Delta's public trades (same taker side, within 5 ms);
  - a real fill is kept if the sweep's worst price reached the counterfactual quote, at that price; a sweep
    that did not fill us adds a fill only if it printed strictly through the counterfactual quote (one quote's
    size, then that side is gone for REPLACE_MS while it is placed again).
Added here: when the real bot had a side off only because it sat at the cap and the variant has room, the
variant quotes that side at the bot's planned price (MM_METRICS bid/ask, PLACE_LAG ms old). When a real fill is
avoided, the variant's quote keeps resting at its own price until the real bot next places on that side.

Valuation: ref = Binance mid * (1 + basis). PnL = cash - fees + q * ref - q0 * ref0, marked on a 60 s grid
(max drawdown from it). capture = sum side * (ref at fill - price) * size; inventory = PnL - capture + fees.

  python3 skew_replay.py --scripts CEX_MM/scripts LIVE_RUN_DIR SHADOW_RUN_DIR [...] [--lean 0,2,5] [--lag-ms 850]
                         [--end-at-last-fill] [--json OUT]
"""
import argparse, bisect, datetime, glob, gzip, json, math, re, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("shadow", nargs="+")
ap.add_argument("--scripts", required=True)
ap.add_argument("--lean", default="0,1,2,3,5,8")
ap.add_argument("--lag-ms", type=float, default=850.0)
ap.add_argument("--end-at-last-fill", action="store_true", help="stop at the last fill in fills.json (log newer than it)")
ap.add_argument("--json")
A = ap.parse_args()
sys.path.insert(0, A.scripts)
import live_vs_shadow as lvs  # noqa: E402

run = Path(A.run)
TICK, CV = 1e-5, 1.0  # ADAUSD: tick 0.00001, contract value 1 ADA
cfg = dict(l.split("=", 1) for l in (run / "config.txt").read_text().splitlines() if "=" in l)
QTY = float(cfg.get("MM_ORDER_QTY_ADAUSDT", 200))
CAP = float(cfg.get("MM_MAX_INVENTORY_ADAUSDT", 600))
PLACE_LAG, REPLACE_MS, EDIT_MS = 1000.0, 1000.0, 600.0
H = float(cfg.get("MM_FIXED_HALF_SPREAD_BPS", 5)) / 1e4


def ts_of(line):
    return datetime.datetime.fromisoformat(line[:26].replace("Z", "")).replace(tzinfo=datetime.timezone.utc).timestamp() * 1000


order_done = {}
fills_rows = json.loads((run / "fills.json").read_text())
for r in fills_rows:
    if r.get("product_symbol") == "ADAUSD" and r.get("order_id") is not None:
        t_fill = lvs.parse_iso_ms(r["created_at"])
        order_done[str(r["order_id"])] = max(order_done.get(str(r["order_id"]), 0.0), t_fill)

# --- bot log ------------------------------------------------------------------------------------------------
S = []  # (t, book_bid, book_ask, place_bid, place_ask, plan_bid, plan_ask, inv)
RT, RV = [], []  # reference price samples: t, Binance mid * (1 + basis)
ev = {1: [], -1: []}
log = run / "bot.log.gz"
fh = gzip.open(log, "rt", errors="replace") if log.exists() else open(run / "bot.log", errors="replace")
for line in fh:
    if line[:4] != "2026":
        continue
    try:
        t = ts_of(line)
    except ValueError:
        continue
    if "MM_METRICS" in line and '"symbol":"ADAUSDT"' in line:
        r = json.loads(line[line.index("{"):])
        S.append((r["ts_ms"], r.get("book_bid"), r.get("book_ask"), bool(r.get("place_bid")), bool(r.get("place_ask")),
                  r.get("bid"), r.get("ask"), float(r.get("inventory") or 0.0), r.get("fair")))
        b, a = r.get("binance_bid"), r.get("binance_ask")
        if b and a and r.get("basis_bps") is not None:
            RT.append(r["ts_ms"]); RV.append((a + b) / 2 * (1 + r["basis_bps"] / 1e4))
        for side, key in ((1, "place_bid"), (-1, "place_ask")):
            if not r.get(key):
                ev[side].append((r["ts_ms"], None, r["ts_ms"]))
    elif "MM_ORDER:" in line and ("placed post-only" in line or "edited post-only" in line):
        side = 1 if 'side="buy"' in line else -1
        m_ms = re.search(r" ms=([0-9]+)", line)
        ev[side].append((t, float(re.search(r" price=([0-9.]+)", line).group(1)), t - (float(m_ms.group(1)) if m_ms else EDIT_MS)))
    elif "fill reached the quote's size" in line:
        oid = re.search(r"order_id=(\d+)", line)
        t_done = order_done.get(oid.group(1), t) if oid else t
        ev[1 if "side=Bid" in line else -1].append((t_done, None, t_done))
    elif "cancel all" in line or "account halt" in line:
        ev[1].append((t, None, t)); ev[-1].append((t, None, t))
fh.close()
for side in ev:
    ev[side].sort(key=lambda x: x[0])
evt = {s: [e[0] for e in ev[s]] for s in ev}
St = [s[0] for s in S]
t0, t1 = S[0][0], S[-1][0]
q0 = S[0][7]

real = []
for r in fills_rows:
    if r.get("product_symbol") != "ADAUSD":
        continue
    f = lvs.parse_fill(r, CV)
    if f and f.fill_type == "normal" and t0 <= f.ts <= t1:
        real.append(f)
real.sort(key=lambda f: f.ts)
if A.end_at_last_fill and real:
    t1 = min(t1, real[-1].ts + 1000)
takers = [f for f in real if not f.maker]
real = [f for f in real if f.maker]
fee_rates = [f.fee / (f.contracts * CV * f.price) * 1e4 for f in real]
FEE = sum(fee_rates) / len(fee_rates) if fee_rates else 1.3


def resting(side, t):
    i = bisect.bisect_right(evt[side], t) - 1
    cur = ev[side][i][1] if i >= 0 else None
    j = i + 1
    if j < len(ev[side]) and ev[side][j][2] <= t:
        new = ev[side][j][1]
        if cur is None or new is None:
            return None
        return min(cur, new) if side == 1 else max(cur, new)
    return cur


def origin(side, t):
    """Send time of the order call behind resting(side, t): the bot priced that quote from the fair then."""
    i = bisect.bisect_right(evt[side], t) - 1
    j = i + 1
    if j < len(ev[side]) and ev[side][j][2] <= t and i >= 0 and ev[side][i][1] is not None and ev[side][j][1] is not None:
        cur, new = ev[side][i][1], ev[side][j][1]
        return ev[side][j][2] if (min(cur, new) if side == 1 else max(cur, new)) == new else ev[side][i][2]
    return ev[side][i][2] if i >= 0 else t


def residual(side, base, t_origin):
    """The part of a tick the bot rounded away: bid = floor(fair * (1 - h)), ask = ceil(fair * (1 + h)).
    A lean shifts the raw price before that rounding, so it moves a quote by a whole tick only when it
    crosses a tick boundary. Unknown origin (clamped or planned elsewhere): half a tick."""
    RES[0] += 1
    i = bisect.bisect_right(St, t_origin) - 1
    for smp in S[max(i - 1, 0): i + 2]:  # the loop row that priced it sits within a tick of the send time
        if smp[8]:
            raw = smp[8] * (1 - H) if side == 1 else smp[8] * (1 + H)
            r = raw - base
            if (0.0 <= r < TICK) if side == 1 else (-TICK < r <= 0.0):
                return r
    RES[1] += 1
    return TICK / 2 if side == 1 else -TICK / 2


RES = [0, 0]  # diagnostic: residual lookups, and how many fell back to half a tick


def sample(t):
    i = bisect.bisect_right(St, t) - 1
    return S[i] if i >= 0 else None


def ref(t):
    i = bisect.bisect_right(RT, t) - 1
    return RV[i] if i >= 0 and t - RT[i] < 5000 else None


# --- tape -----------------------------------------------------------------------------------------------------
raw = []
for d in A.shadow:
    for p in sorted(glob.glob(str(Path(d) / "delta_mainnet_public_*.jsonl"))):
        for line in open(p, errors="replace"):
            if '"trades"' not in line or "ADAUSD" not in line:
                continue
            m = json.loads(line).get("msg") or {}
            if m.get("sy") != "ADAUSD" or "t" not in m or m.get("r") not in ("t", "m"):
                continue
            te = m["t"] / 1000.0
            if t0 <= te <= t1:
                raw.append((te, 1 if m["r"] == "t" else -1, float(m["p"]), float(m["s"])))
raw.sort()
SW = []
for te, agg, px, sz in raw:
    last = SW[-1] if SW else None
    if last and last["agg"] == agg and te - last["t_end"] <= 5.0:
        last["prices"].append(px); last["size"] += sz; last["t_end"] = te
    else:
        SW.append({"t": te, "t_end": te, "agg": agg, "prices": [px], "size": sz})
SWt = [x["t"] for x in SW]
by_sweep, unmatched, extra = {}, 0, []
for f in real:
    agg = -f.side
    lo, hi = bisect.bisect_left(SWt, f.ts - 50), bisect.bisect_right(SWt, f.ts + 3)
    cands = [s for s in SW[lo:hi] if s["agg"] == agg and s["t"] - 3 <= f.ts <= s["t_end"] + 3]
    if not cands:
        unmatched += 1
        s = {"t": f.ts, "t_end": f.ts, "agg": agg, "prices": [f.price], "size": f.contracts}
        extra.append(s)
    else:
        s = min(cands, key=lambda x: abs(x["t"] - f.ts))
    by_sweep.setdefault(id(s), []).append(f)
SW.extend(extra)
SW.sort(key=lambda s: s["t"])


def snap(x, side):
    return round((math.floor(x / TICK + 1e-6) if side == 1 else math.ceil(x / TICK - 1e-6)) * TICK, 10)


def room(side, q):
    return max(0.0, CAP - q) if side == 1 else max(0.0, CAP + q)


def simulate(L, lag):
    qt, qv = [t0], [q0]  # position history, for the lagged read
    q, cash, fees, capture, p60, p300 = q0, 0.0, 0.0, 0.0, 0.0, 0.0
    hold, gone = {1: None, -1: None}, {1: -1.0, -1: -1.0}
    n_keep = n_avoid = n_new = 0
    notional = 0.0
    events = []  # (t, q, cash, fees) after each fill

    def q_at(t):
        return qv[bisect.bisect_right(qt, t) - 1]

    def priced(side, t, base, t_origin):
        if base is None:
            return None
        shift = -L * q_at(t - lag) / CAP
        if shift == 0.0:
            return base
        p = snap(base + residual(side, base, t_origin) + base * shift / 1e4, side)
        smp = sample(t)
        if smp and smp[1] and smp[2]:
            p = min(p, round(smp[2] - TICK, 10)) if side == 1 else max(p, round(smp[1] + TICK, 10))
        return p

    def base_at(side, t):
        r, o = resting(side, t), None
        if r is not None:
            o = origin(side, t)
        elif hold[side] and t < hold[side][1]:
            r, o = hold[side][0], hold[side][2]
        else:
            smp = sample(t - PLACE_LAG)
            if smp and not smp[3 if side == 1 else 4] and (smp[7] >= CAP if side == 1 else smp[7] <= -CAP):
                r, o = smp[5 if side == 1 else 6], smp[0]  # off only for the real cap: the bot's planned price
        return r, o

    def fill(side, t, price, size, fee_bps):
        nonlocal q, cash, fees, capture, p60, p300, notional
        n = size * CV * price
        q += side * size
        cash -= side * n
        fee = fee_bps * n / 1e4
        fees += fee
        notional += n
        r0, r60, r300 = ref(t), ref(t + 60_000), ref(t + 300_000)
        if r0:
            capture += side * (r0 - price) * size * CV
        if r60:
            p60 += side * (r60 - price) * size * CV - fee
        if r300:
            p300 += side * (r300 - price) * size * CV - fee
        qt.append(t); qv.append(q)
        events.append((t, q, cash, fees))

    for s in SW:
        t = s["t"]
        side = -s["agg"]
        worst = min(s["prices"]) if side == 1 else max(s["prices"])
        if hold[side] and t >= hold[side][1]:
            hold[side] = None
        mine = by_sweep.get(id(s), [])
        if mine:
            for f in mine:
                o = origin(side, t)
                p = priced(side, t, f.price, o)
                rm = room(side, q)
                if p is not None and rm > 0 and (worst <= p if side == 1 else worst >= p):
                    n_keep += 1
                    fill(side, t, p, min(f.contracts, rm), f.fee / (f.contracts * CV * f.price) * 1e4)
                else:
                    n_avoid += 1
                    if rm > 0:  # our quote was not reached: it keeps resting until the bot next places
                        j = bisect.bisect_right(evt[side], max(t, f.ts) + 5)
                        hold[side] = (f.price, evt[side][j] if j < len(evt[side]) else t1, o)
            continue
        if t < gone[side]:
            continue
        rm = room(side, q)
        if rm <= 0:
            continue
        p = priced(side, t, *base_at(side, t))
        if p is not None and (worst < p if side == 1 else worst > p):
            n_new += 1
            fill(side, t, p, min(QTY, rm), FEE)
            gone[side] = t + REPLACE_MS
            hold[side] = None

    # mark to market on a 60 s grid
    ref0 = ref(t0) or next(v for v in RV if v)
    k, st, mtm, peak, dd, at_cap, absq, ngrid = 0, (t0, q0, 0.0, 0.0), 0.0, 0.0, 0.0, 0, 0.0, 0
    last_ref = ref0
    qgap = 0.0  # diagnostic: |simulated q - the bot's logged inventory|, mean over the grid (L = 0 should be ~0)
    g = t0
    while g <= t1:
        while k < len(events) and events[k][0] <= g:
            st = events[k]; k += 1
        rv = ref(g) or last_ref
        last_ref = rv
        mtm = st[2] - st[3] + st[1] * rv - q0 * ref0
        peak = max(peak, mtm); dd = max(dd, peak - mtm)
        at_cap += abs(st[1]) >= CAP - 1e-9; absq += abs(st[1]); ngrid += 1
        smp = sample(g)
        qgap += abs(st[1] - smp[7]) if smp else 0.0
        g += 60_000
    while k < len(events):
        st = events[k]; k += 1
    end_ref = ref(t1) or last_ref
    pnl = st[2] - st[3] + st[1] * end_ref - q0 * ref0
    return {"L": L, "kept": n_keep, "avoided": n_avoid, "new": n_new, "fills": n_keep + n_new, "notional": notional,
            "pnl": pnl, "capture": capture, "inventory": pnl - capture + fees, "fees": fees, "pnl60": p60, "pnl300": p300,
            "maxdd": dd, "at_cap": at_cap / max(ngrid, 1), "mean_absq": absq / max(ngrid, 1), "q_end": st[1],
            "qgap": qgap / max(ngrid, 1)}


hours = (t1 - t0) / 3.6e6
print(f"run {run.name}: {hours:.1f} h, quote {QTY:g} / cap {CAP:g}, start q {q0:+g}, {len(real)} real maker fills "
      f"({unmatched} not on the tape, {len(takers)} taker), {len(SW)} sweeps, avg fee {FEE:.2f} bps, lag {A.lag_ms:g} ms")
print(f"{'L bps':>5s} | {'kept':>5s} {'avoid':>5s} {'new':>4s} | {'$ traded':>9s} | {'PnL $':>7s} {'capt':>6s} {'inv':>6s} {'fees':>6s} | "
      f"{'PnL60':>6s} {'PnL300':>6s} | {'maxDD':>5s} {'@cap':>5s} {'|q|':>4s} {'q end':>5s}")
out = []
for L in [float(x) for x in A.lean.split(",")]:
    o = simulate(L, A.lag_ms)
    out.append(o)
    print(f"{L:5g} | {o['kept']:5d} {o['avoided']:5d} {o['new']:4d} | {o['notional']:9,.0f} | {o['pnl']:+7.2f} {o['capture']:+6.2f} "
          f"{o['inventory']:+6.2f} {-o['fees']:+6.2f} | {o['pnl60']:+6.2f} {o['pnl300']:+6.2f} | {o['maxdd']:5.2f} "
          f"{100 * o['at_cap']:4.1f}% {o['mean_absq']:4.0f} {o['q_end']:+5.0f}" + (f" | q gap vs log {o['qgap']:.1f}" if L == 0 else ""))
print(f"residual lookups {RES[0]}, half-tick fallbacks {RES[1]} ({100 * RES[1] / max(RES[0], 1):.1f}%)")
if A.json:
    Path(A.json).write_text(json.dumps({"run": run.name, "hours": hours, "real_fills": len(real), "rows": out}))
