#!/usr/bin/env python3
"""Read-only counterfactual: would leaning ADA quotes on Binance's queue imbalance have avoided pick-offs?

For one live run it rebuilds our resting bid and ask over time from the bot log (MM_ORDER places and edits; a
quote is gone after a full fill, a pull, or a cancel-all), then replays Delta's recorded public trade tape
(exchange trade time `t`; the VM clock is NTP-synced) against counterfactual quotes:

  lean λ:   both quotes shift by λ·(I − ½)·(Binance spread), I = bid_qty / (bid_qty + ask_qty) at Binance's
            best levels, read L ms before the trade (an edit takes ~650 ms on mainnet, plus loop sampling).
  away λ:   only the threatened side moves away (the bid down when I < ½, the ask up when I > ½).
  pull θ:   the threatened side is not quoted while I < θ (bid) or I > 1 − θ (ask), read 250 ms before the
            trade (a cancel answers in ~20 ms), and it comes back 850 ms after the signal clears (a place).

Fill rule per taker sweep (trades with the same exchange time and taker side): a real fill of ours is kept if
the sweep's worst price reached the counterfactual quote (non-strict), at the counterfactual price; a sweep that
did not fill us adds a fill only if it printed strictly through the counterfactual quote (the whole level was
taken), for one quote's size. λ = 0 replays the real quotes: its "new" fills measure the rebuild's error.
Value of a fill: side · (Binance mid × (1 + basis) at +60 s / +300 s − price) − fee, in bps and dollars.
Inventory and the cap are not re-simulated (the real quoting on/off state is kept).

  python3 lean_replay.py LIVE_RUN_DIR SHADOW_RUN_DIR [SHADOW_RUN_DIR ...]
"""
import bisect, datetime, glob, json, re, sys
from pathlib import Path

run = Path(sys.argv[1])
sys.path.insert(0, str(run.parents[2] / "scripts"))
import live_vs_shadow as lvs  # noqa: E402
import shadow_fill_sim as sim  # noqa: E402

TICK, CV = sim.product_meta("ADAUSD")
cfg = dict(l.split("=", 1) for l in (run / "config.txt").read_text().splitlines() if "=" in l)
QTY = float(cfg.get("MM_ORDER_QTY_ADAUSDT", 200))  # base units = contracts for ADA (contract value 1)


def ts_of(line):
    return datetime.datetime.fromisoformat(line[:26].replace("Z", "")).replace(tzinfo=datetime.timezone.utc).timestamp() * 1000


# --- the last fill of each order (exchange time): a quote is gone from then on, not from the log line -----
order_done = {}
for r in json.loads((run / "fills.json").read_text()):
    if r.get("product_symbol") == "ADAUSD" and r.get("order_id") is not None:
        t_fill = lvs.parse_iso_ms(r["created_at"])
        order_done[str(r["order_id"])] = max(order_done.get(str(r["order_id"]), 0.0), t_fill)

# --- bot log: samples and our resting quotes --------------------------------------------------------------
S = []  # (t, I, bspread, bmid, basis_bps, book_bid, book_ask, place_bid, place_ask)
ev = {1: [], -1: []}  # side (+1 bid, -1 ask) -> [(ack_t, price or None, send_t)]
EDIT_MS = 600.0  # runs before c1a8080 log no `ms`: mainnet order writes took ~0.6 s
for line in open(run / "bot.log", errors="replace"):
    if line[:4] != "2026":
        continue
    try:
        t = ts_of(line)
    except ValueError:
        continue
    if "MM_METRICS" in line and '"symbol":"ADAUSDT"' in line:
        r = json.loads(line[line.index("{"):])
        b, a, bq, aq = r.get("binance_bid"), r.get("binance_ask"), r.get("binance_bid_qty"), r.get("binance_ask_qty")
        if not (b and a and bq and aq and r.get("basis_bps") is not None):
            continue
        S.append((r["ts_ms"], bq / (bq + aq), a - b, (a + b) / 2, r["basis_bps"], r["book_bid"], r["book_ask"],
                  bool(r.get("place_bid")), bool(r.get("place_ask"))))
        for side, key in ((1, "place_bid"), (-1, "place_ask")):
            if not r.get(key):
                ev[side].append((r["ts_ms"], None, r["ts_ms"]))
    elif "MM_ORDER:" in line and ("placed post-only" in line or "edited post-only" in line):
        side = 1 if 'side="buy"' in line else -1
        m_ms = re.search(r" ms=([0-9]+)", line)
        sent = t - (float(m_ms.group(1)) if m_ms else EDIT_MS)
        ev[side].append((t, float(re.search(r" price=([0-9.]+)", line).group(1)), sent))
    elif "fill reached the quote's size" in line:
        oid = re.search(r"order_id=(\d+)", line)
        t_done = order_done.get(oid.group(1), t) if oid else t
        ev[1 if "side=Bid" in line else -1].append((t_done, None, t_done))
    elif "cancel all" in line or "account halt" in line:
        ev[1].append((t, None, t))
        ev[-1].append((t, None, t))
for side in ev:
    ev[side].sort(key=lambda x: x[0])
evt = {s: [e[0] for e in ev[s]] for s in ev}
St = [s[0] for s in S]


def resting(side, t):
    i = bisect.bisect_right(evt[side], t) - 1
    cur = ev[side][i][1] if i >= 0 else None
    j = i + 1
    if j < len(ev[side]) and ev[side][j][2] <= t:  # the next change was already sent: in flight
        new = ev[side][j][1]
        if cur is None or new is None:
            return None
        return min(cur, new) if side == 1 else max(cur, new)
    return cur


def sample(t):
    i = bisect.bisect_right(St, t) - 1
    return S[i] if i >= 0 else None


def ref(t, basis):
    s = sample(t)
    return s[3] * (1 + basis / 1e4) if s and t - s[0] < 5000 else None


t0, t1 = S[0][0], S[-1][0]

# --- tape: taker sweeps (same taker side, trades within 5 ms of the previous one) ------------------------------
raw = []
for d in sys.argv[2:]:
    if d.startswith("--"):
        continue
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

# --- our real fills, matched to sweeps --------------------------------------------------------------------
real = []
fees = []
for r in json.loads((run / "fills.json").read_text()):
    if r.get("product_symbol") != "ADAUSD":
        continue
    f = lvs.parse_fill(r, CV)
    if not f or f.fill_type != "normal" or not t0 <= f.ts <= t1:
        continue
    real.append(f)
    fees.append(f.fee / (f.contracts * CV * f.price) * 1e4)
FEE = sum(fees) / len(fees) if fees else 1.2
by_sweep = {}
unmatched = 0
for f in real:
    agg = -f.side  # our bid filled by a seller
    best = None
    for k in ((round(f.ts * 1000), agg),):
        pass
    lo = bisect.bisect_left([x["t"] for x in SW], f.ts - 50)
    hi = bisect.bisect_right([x["t"] for x in SW], f.ts + 3)
    cands = [s for s in SW[lo:hi] if s["agg"] == agg and s["t"] - 3 <= f.ts <= s["t_end"] + 3]
    if not cands:
        unmatched += 1
        cands = [{"t": f.ts, "t_end": f.ts, "agg": agg, "prices": [f.price], "size": f.contracts, "synthetic": True}]
        SW.append(cands[0])
    s = min(cands, key=lambda x: abs(x["t"] - f.ts))
    by_sweep.setdefault(id(s), []).append(f)
SW.sort(key=lambda s: s["t"])


def threatened(side, imb, theta):
    return imb < theta if side == 1 else imb > 1 - theta


def quote_at(side, t, mode, k, at=None):
    """Counterfactual resting price of `side` at t, or None. `at`: where our order really was (a real fill)."""
    q = resting(side, t) if at is None else at
    if q is None:
        return None
    if mode == "real":
        return q
    if mode == "pullfast":
        theta = k
        now = sample(t - 250)
        if now and busy(t - 250) and threatened(side, now[1], theta):
            return None
        return q
    if mode == "pull":
        theta = k
        for lag in (250, 850):  # signal seen 250 ms ago, or not yet re-placed (850 ms)
            s = sample(t - lag)
            if s and threatened(side, s[1], theta):
                return None
        return q
    s = sample(t - L)
    if not s:
        return q
    shift = k * (s[1] - 0.5) * s[2] * (1 + s[4] / 1e4)
    if mode == "away":
        shift = min(shift, 0.0) if side == 1 else max(shift, 0.0)
    q2 = q + round(shift / TICK) * TICK
    now = sample(t)
    if now:
        q2 = min(q2, now[6] - TICK) if side == 1 else max(q2, now[5] + TICK)  # post-only against Delta's book
    return round(q2, 10)


# Binance mid changes per sample index, for a "busy market" gate (exploratory)
_chg = [0]
for i in range(1, len(S)):
    _chg.append(_chg[-1] + (1 if S[i][3] != S[i - 1][3] else 0))
FAST_N = 6


def busy(t):
    i = bisect.bisect_right(St, t) - 1
    j = bisect.bisect_right(St, t - 60_000) - 1
    return i >= 0 and j >= 0 and _chg[i] - _chg[j] >= FAST_N


def value(side, price, t, fee_bps, h):
    s = sample(t)
    if not s:
        return None
    r = ref(t + h * 1000, s[4])
    return None if r is None else side * (r - price) / price * 1e4 - fee_bps


def replay(mode, k):
    out = {"kept": [0, 0.0, 0.0, 0.0], "avoided": [0, 0.0, 0.0, 0.0], "new": [0, 0.0, 0.0, 0.0]}
    for s in SW:
        side = -s["agg"]  # the side of ours that this sweep hits
        worst = min(s["prices"]) if side == 1 else max(s["prices"])
        mine = by_sweep.get(id(s), [])
        q = None if mine else quote_at(side, s["t"], mode, k)
        if mine:
            for f in mine:
                q = quote_at(side, s["t"], mode, k, at=f.price)
                notional = f.contracts * CV * f.price
                fee = f.fee / notional * 1e4
                hit = q is not None and (worst <= q if side == 1 else worst >= q)
                price = q if hit else f.price
                v60, v300 = value(side, price, s["t"], fee, 60), value(side, price, s["t"], fee, 300)
                if v60 is None or v300 is None:
                    continue
                key = "kept" if hit else "avoided"
                n = f.contracts * CV * price
                o = out[key]
                o[0] += 1; o[1] += n; o[2] += v60 * n / 1e4; o[3] += v300 * n / 1e4
        elif q is not None and (worst < q if side == 1 else worst > q):
            v60, v300 = value(side, q, s["t"], FEE, 60), value(side, q, s["t"], FEE, 300)
            if v60 is None or v300 is None:
                continue
            n = QTY * CV * q
            o = out["new"]
            o[0] += 1; o[1] += n; o[2] += v60 * n / 1e4; o[3] += v300 * n / 1e4
    return out


hours = (t1 - t0) / 3.6e6
print(f"run {run.name}: {hours:.1f} h, quote {QTY:g} contracts, {len(real)} real fills ({unmatched} not found on the tape), "
      f"{len(SW)} taker sweeps, avg fee {FEE:.2f} bps")
print(f"{'variant':16s} | {'kept':>4s} {'avoided':>7s} {'new':>4s} | {'fills':>5s} {'$ traded':>9s} | {'PnL60 $':>8s} {'bps/$':>6s} | {'PnL300 $':>8s} {'bps/$':>6s} | avoided fills' own PnL60 $")
base = None
for mode, ks, lag in (("real", [0], 0), ("lean", [1.0, 1.5, 2.0, 3.0], 850), ("lean", [1.0, 2.0], 400),
                      ("away", [1.0, 2.0, 3.0], 850), ("pull", [0.1, 0.2, 0.3], 0), ("pullfast", [0.2, 0.3], 0)):
    for k in ks:
        L = lag
        o = replay(mode, k)
        n = o["kept"][0] + o["new"][0]
        notional = o["kept"][1] + o["new"][1]
        p60 = o["kept"][2] + o["new"][2]
        p300 = o["kept"][3] + o["new"][3]
        label = "real quotes" if mode == "real" else (f"{mode} {k:g}" + (f" L{lag}" if mode in ("lean", "away") else ""))
        print(f"{label:16s} | {o['kept'][0]:4d} {o['avoided'][0]:7d} {o['new'][0]:4d} | {n:5d} {notional:9,.0f} | "
              f"{p60:+8.2f} {p60 / notional * 1e4 if notional else 0:+6.2f} | {p300:+8.2f} {p300 / notional * 1e4 if notional else 0:+6.2f} | "
              f"{o['avoided'][2]:+.2f}")


# --- diagnostic: where phantom prints and real fills fall relative to in-flight order calls ---------------
if "--diag" in sys.argv:
    def window(side, t):
        """(phase, ms since send) if t is inside a send->ack window of `side`, else None."""
        for e in ev[side][max(0, bisect.bisect_right(evt[side], t) - 3): bisect.bisect_right(evt[side], t) + 3]:
            ack, price, sent = e
            if price is not None and sent <= t <= ack:
                return t - sent
        return None
    ph_in, ph_out, ph_off, rf_in, rf_off = 0, 0, [], 0, []
    for s in SW:
        side = -s["agg"]
        worst = min(s["prices"]) if side == 1 else max(s["prices"])
        mine = by_sweep.get(id(s), [])
        if mine:
            w = window(side, s["t"])
            if w is not None:
                rf_in += 1; rf_off.append(w)
            continue
        q = resting(side, s["t"])
        if q is not None and (worst < q if side == 1 else worst > q):
            w = window(side, s["t"])
            if w is None:
                ph_out += 1
            else:
                ph_in += 1; ph_off.append(w)
    srt = lambda xs: sorted(xs)
    print(f"\nphantom prints: {ph_in + ph_out}; inside an in-flight order call: {ph_in}; outside: {ph_out}")
    if ph_off:
        x = srt(ph_off); print(f"  ms after send: p10 {x[len(x)//10]:.0f} p50 {x[len(x)//2]:.0f} p90 {x[9*len(x)//10]:.0f}")
    print(f"real fills inside an in-flight order call on their side: {rf_in} of {len(real)}")
    if rf_off:
        x = srt(rf_off); print(f"  ms after send: p10 {x[len(x)//10]:.0f} p50 {x[len(x)//2]:.0f} p90 {x[9*len(x)//10]:.0f}; under 60 ms: {sum(1 for v in x if v < 60)}")
    # the phantoms outside any window: show a few with context
    shown = 0
    for s in SW:
        side = -s["agg"]
        if by_sweep.get(id(s)):
            continue
        worst = min(s["prices"]) if side == 1 else max(s["prices"])
        q = resting(side, s["t"])
        if q is not None and (worst < q if side == 1 else worst > q) and window(side, s["t"]) is None and shown < 6:
            i = bisect.bisect_right(evt[side], s["t"]) - 1
            last = ev[side][i]
            nxt = ev[side][i + 1] if i + 1 < len(ev[side]) else None
            print(f"  {datetime.datetime.utcfromtimestamp(s['t']/1000).strftime('%H:%M:%S.%f')[:12]} side {side:+d} sweep worst {worst} size {s['size']:g} | "
                  f"resting {q} since {(s['t'] - last[0]):.0f} ms | next change {'+%.0f ms -> %s' % (nxt[2] - s['t'], nxt[1]) if nxt else 'none'}")
            shown += 1

if "--debug-at" in sys.argv:
    at = float(sys.argv[sys.argv.index("--debug-at") + 1])
    for f in real:
        if abs(f.ts - at) < 1500:
            print("fill", f.ts, f.side, f.price, f.contracts)
    for s in SW:
        if abs(s["t"] - at) < 1500:
            print("sweep", s["t"], s["t_end"], s["agg"], s["size"], min(s["prices"]), max(s["prices"]), "mine" if by_sweep.get(id(s)) else "-", s.get("synthetic", ""))
