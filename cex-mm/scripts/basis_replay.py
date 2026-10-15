#!/usr/bin/env python3
"""Live-mode replay of the Binance-anchored fair, and the pre-registered gate of plans/live-basis.plan.md.

The bot anchors its fair to Binance: fair = binance_mid x (1 + basis), basis = EMA of Delta mid / Binance mid.
In a live run our own resting quotes are the Delta touch most of the time, so a basis read from the L1 book
starves (own-touch gate) or reads our own fair back (artifacts/research/2026-10-13-shadow-anchor-interim.md,
finding 2). This script replays a shadow run's MM_METRICS rows through the bot's own arithmetic, twice:

  --mode shadow  the basis and fair from the clean logged book, exactly as the bot computed them
                 (checked against the logged basis_bps and anchored flag);
  --mode live    the synthetic live book: the logged book plus our two replayed resting quotes of size q,
                 with every L1-derived term recomputed on it (the mid/microprice blend, OFI, the post-only
                 clamp, the own-touch gate when --source book, the fair-jump side drop and the fallback to the
                 old fair), the quotes delayed by --latency loops.

  --source book  basis sample = L1 mid (mm-bot runner.rs: basis.update(lead_now, top.mid(), binance_mid),
                 skipped while our own resting quote is the touch);
  --source depth basis sample = the ob_l2 depth mid (mm-core depth.rs: the price where cumulative size
                 reaches X contracts per side), taken when the snapshot is <= MM_DEPTH_STALE_MS old. In live
                 mode our order is inserted into the recorded ladder (--book / run dir), so a pivot
                 (others' inside size in [X - q, X)) or the 15-level cap can move it, as on the venue.

Gates (PASS/FAIL with numbers; see the plan for the reasons):
  G1 health        depth snapshot <= 2 s old, and anchor on, each on >= 95% of Binance-fresh rows
  G2 equivalence   p90 |EMA basis(depth) - EMA basis(clean L1)| <= 1.5 bps; pivot share <= 1% of rows
  G3 self-ref      live mode at q: p99 |anchored fair(live book) - anchored fair(clean book)| <= 0.5 bps
  G4 information   slope of Delta's mid move at +5 s / +60 s on (fair - mid) >= the clean old fair's, and the
                   60 s difference's block-bootstrap 95% CI (5-min blocks) above 0
  G5 exposure      side-averaged exposure at +30 s / +60 s: upper 95% CI <= +1 pp vs the clean old fair;
                   per-side guard +3 pp (+1 s / +5 s are diagnostics only: there Delta's lag fails even an
                   oracle)
Also printed: two oracle rows (fair = the future mid at +5 s and +60 s), each scored on every gate component
(G4@5, G4@60, G5@30, G5@60). The plan's rule "no gate may rely on a metric the oracle fails" is applied across
horizons: a component either oracle fails is marked n/a and the gate cannot PASS on it (an oracle never fails
its own horizon: its quotes sit 5 bps clear of the mid it knows, so the rule's bite is cross-horizon, e.g.
the +60 s oracle's exposure at +30 s). Both baselines (clean old fair; live-mode old fair with the OFI term
removed), a depth-mid yardstick in its own frame (x = fair - depth mid, y = future depth mid - depth mid,
recentred), the latency sensitivity, and a "not modelled" block. The verdict reads PROVISIONAL under 24 h of
covered data (the --exclude'd span does not count). --parity prints the livegate-equivalent numbers (basis
updated %, anchored %) with the settings the replica used.

Exit code: 0 every gate G1-G5 evaluated and passed; 1 a gate fails; 2 thin data (under --min-hours /
--min-rows of covered data) or unusable input / options; 3 INCOMPLETE (a gate was not evaluated: shadow mode
has no G3, a log without depth fields has no G1/G2, an oracle-failed component, or an uncalibrated synthetic
live book under --calibrate). With several symbols: 2 if any symbol is thin, else 1 if any gate fails, else 3
if any gate is unevaluated, else 0. Stdlib only.

    python3 scripts/basis_replay.py --run-dir artifacts/shadow/<run> --symbol ADAUSDT --mode live --source depth
    python3 scripts/basis_replay.py --metrics dry-run.log --config config.txt --book delta_mainnet_book_*.jsonl \\
        --symbol ADAUSDT --mode live --source book --latency 0,1,2 --json out.json
    python3 scripts/basis_replay.py --metrics shadow_13oct_ada.log --config shadow_13oct_config.txt \\
        --symbol ADAUSDT --parity --from 2026-10-13T07:41:00Z --to 2026-10-13T10:19:51Z
"""
from __future__ import annotations

import argparse
import bisect
import collections
import datetime as dt
import glob
import gzip
import json
import math
import os
import random
import statistics
import sys
from array import array
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from shadow_fill_sim import delta_symbol, iter_lines  # noqa: E402  (dry-run.log and .gz, tolerant of a live gzip)
except ImportError:  # pragma: no cover - the script is normally run from its own directory
    def delta_symbol(mm_symbol: str) -> str:
        return mm_symbol[:-1] if mm_symbol.endswith("USDT") else mm_symbol

    def iter_lines(path: str):
        f = gzip.open(path, "rt", errors="replace") if path.endswith(".gz") else open(path, errors="replace")
        try:
            yield from f
        except EOFError:
            pass
        finally:
            f.close()

LN2 = math.log(2.0)
NAN = float("nan")
REGIME_MULT = {0: 1.0, 1: 1.5, 2: 2.25}
DEPTH_LEVELS = 15  # ob_l2 carries 15 levels a side
OFI_WINDOW = 128  # OfiTracker::new(128)
OFI_CLAMP_BPS = 50.0  # OfiTracker::drift_bps
MICRO_W = 0.3  # resolve_fair_cex: 0.7 mid + 0.3 microprice
GATE_H = (30, 60)
DIAG_H = (1, 5)
SLOPE_H = (5, 60)
ORACLE_H = (5, 60)  # the plan's oracle row: fair = the future mid at +5 s and +60 s
FUTURE_TOL_MS = 2000.0
BLOCK_MS = 300_000.0
EXPOSED_BPS = 1.0
G1_DEPTH_MS = 2000.0  # the plan's G1 threshold, fixed; MM_DEPTH_STALE_MS only governs the bot's sampling
BASIS_MAX_AGE_DEFAULT = {"book": 300.0, "depth": 30.0}  # PR C runner.rs basis_max_age_default per source
NOT_MODELLED = (
    "inventory and the sides it drops (the replay quotes both sides at a constant size)",
    "takers arriving while our quote is stale (a quote the market moved through is dropped for that loop, "
    "not filled)",
    "latency races between our requote and the takers' (the quote appears in the book --latency loops late, "
    "the fills do not)",
    "ghost orders (the OMS state is assumed to match the venue)",
    "other makers reacting to us (repricing or pegging to our quote): only a live run can show this",
    "the vol and regime engines read the logged regime_level, not the live mid",
    "the queue guard (runner.rs should_place_limit, MM_QUEUE_MAX_FRONT_FRAC 0.9: a new order is not placed at "
    "a touch level where more than 90% of the size is ahead); the replay always joins the touch",
    "the order rate budget (oms.rs OrderRateBudget, 7 order ops/s): every requote is assumed to reach the venue",
)
# Keys the Rust reads with a plain env_f64 (strategy.rs), never per symbol; every other key goes through
# env_f64_for_symbol (MM_X_<SYM> first, then MM_X).
GLOBAL_ONLY_KEYS = frozenset({"MM_FIXED_HALF_SPREAD_BPS", "MM_FAIR_JUMP_BPS", "MM_FAIR_JUMP_DEFENSIVE"})


# ---------------------------------------------------------------- settings

@dataclass
class Settings:
    """The bot's knobs that the replay mirrors (defaults = runner.rs / strategy.rs defaults)."""

    loop_sec: float = 0.4
    half_life_sec: float = 120.0  # MM_BASIS_HALFLIFE_SEC
    clamp_bps: float = 5.0  # MM_BASIS_CLAMP_BPS
    warmup_sec: float = 60.0  # MM_BASIS_WARMUP_SEC
    max_age_sec: float = 300.0  # MM_BASIS_MAX_AGE_SEC (default 300 s for the book source, 30 s for depth)
    binance_stale_ms: float = 5000.0  # MM_BINANCE_STALE_MS
    depth_stale_ms: float = 2000.0  # MM_DEPTH_STALE_MS
    lead_lookback_sec: float = 3.0  # MM_LEAD_LOOKBACK_SEC
    lead_beta: float = 0.8  # MM_LEAD_BETA
    lead_max_bps: float = 15.0  # MM_LEAD_MAX_BPS
    ofi_beta: float = 0.01  # MM_OFI_BETA
    half_bps: float = 5.0  # MM_FIXED_HALF_SPREAD_BPS
    tol_bps: float = 3.0  # MM_REQUOTE_TOL_BPS
    jump_bps: float = 12.0  # MM_FAIR_JUMP_BPS
    jump_defensive: bool = True  # MM_FAIR_JUMP_DEFENSIVE
    anchor_weight: float = 1.0  # MM_FAIR_ANCHOR_WEIGHT
    ofi_anchored: bool = False  # PR C design: no OFI term while anchored (True = as coded on main today)

    @property
    def max_step_sec(self) -> float:
        return 2.0 * self.loop_sec  # new_basis(): with_max_step(2 loops)

    @classmethod
    def from_config(cls, cfg: dict[str, str], symbol: str, loop_ms: float = 400.0, source: str = "book") -> "Settings":
        """`source` picks the basis max age default (runner.rs on feat/basis-source: 300 s book, 30 s depth, so a
        dead depth feed turns the anchor off fast)."""
        def f(key: str, default: float) -> float:
            v = cfg_get(cfg, key, symbol, per_symbol=key not in GLOBAL_ONLY_KEYS)
            try:
                return float(v) if v is not None else default
            except ValueError:
                return default

        return cls(
            loop_sec=max(loop_ms, 100.0) / 1000.0,  # runner.rs: args.loop_ms.max(100)
            half_life_sec=max(f("MM_BASIS_HALFLIFE_SEC", 120.0), 0.0),
            clamp_bps=f("MM_BASIS_CLAMP_BPS", 5.0),
            warmup_sec=max(f("MM_BASIS_WARMUP_SEC", 60.0), 0.0),
            max_age_sec=max(f("MM_BASIS_MAX_AGE_SEC", BASIS_MAX_AGE_DEFAULT.get(source, 300.0)), 0.0),
            binance_stale_ms=max(f("MM_BINANCE_STALE_MS", 5000.0), 0.0),
            depth_stale_ms=min(max(f("MM_DEPTH_STALE_MS", 2000.0), 100.0), 3_600_000.0),
            lead_lookback_sec=max(f("MM_LEAD_LOOKBACK_SEC", 3.0), 0.0),
            lead_beta=f("MM_LEAD_BETA", 0.8),
            lead_max_bps=f("MM_LEAD_MAX_BPS", 15.0),
            ofi_beta=f("MM_OFI_BETA", 0.01),
            half_bps=f("MM_FIXED_HALF_SPREAD_BPS", 5.0),
            tol_bps=f("MM_REQUOTE_TOL_BPS", 3.0),
            jump_bps=f("MM_FAIR_JUMP_BPS", 12.0),
            jump_defensive=f("MM_FAIR_JUMP_DEFENSIVE", 1.0) >= 0.5,
            anchor_weight=min(max(f("MM_FAIR_ANCHOR_WEIGHT", 0.0), 0.0), 1.0),  # the bot's default: off
        )


def cfg_get(cfg: dict[str, str], key: str, symbol: str, per_symbol: bool = True) -> str | None:
    """Per-symbol key first (`MM_X_ADAUSDT`), then the global one, like env_f64_for_symbol; with
    `per_symbol=False` only the global name, like the plain env_f64 of strategy.rs (GLOBAL_ONLY_KEYS)."""
    v = cfg.get(f"{key}_{symbol}") if per_symbol else None
    return v if v is not None else cfg.get(key)


def load_config(path: str | None) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return cfg
    for line in iter_lines(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


# ---------------------------------------------------------------- loading

@dataclass(slots=True)
class Row:
    ts: float  # ts_ms (local wall clock)
    bb: float
    ba: float
    bq: float
    aq: float
    bn: float  # Binance mid, 0 when absent
    bn_age: float | None  # binance_age_ms
    fair: float
    fair_delta: float | None
    basis: float | None  # logged basis_bps
    anchored: bool | None
    bid: float
    ask: float
    place_bid: bool
    place_ask: bool
    regime: int
    ofi: float | None
    depth_mid: float | None
    depth_age: float | None
    depth_qty: float | None
    dbp: float | None  # depth_bid_px
    dap: float | None
    dbi: float | None  # depth_bid_inner
    dai: float | None
    dbip: float | None  # depth_bid_inner_px
    daip: float | None
    dts: int | None  # depth_ts_us
    basis_src: str | None

    @property
    def mid(self) -> float:
        return (self.bb + self.ba) / 2.0


def is_fresh(r: Row, st: "Settings") -> bool:
    """runner.rs binance_fresh: a Binance mid whose last message is within MM_BINANCE_STALE_MS (an old log
    without binance_age_ms counts as fresh whenever it has a mid)."""
    return r.bn > 0 and (r.bn_age is None or r.bn_age <= st.binance_stale_ms)


def _opt(m: dict, key: str) -> float | None:
    v = m.get(key)
    return float(v) if v is not None else None


def parse_metrics_row(line: str) -> tuple[str, Row] | None:
    """One MM_METRICS line -> (symbol, Row), or None when it is not usable (no book, no ts)."""
    if "MM_METRICS" not in line:
        return None
    start, end = line.find("{"), line.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        m = json.loads(line[start : end + 1])
    except json.JSONDecodeError:
        return None
    if "ts_ms" not in m or not m.get("book_bid") or not m.get("book_ask"):
        return None
    bb, ba = float(m["book_bid"]), float(m["book_ask"])
    if bb <= 0 or ba <= bb:
        return None  # the bot skips such a loop too
    anchored = m.get("anchored")
    return m["symbol"], Row(
        ts=float(m["ts_ms"]),
        bb=bb,
        ba=ba,
        bq=float(m.get("book_bid_qty") or 0.0),
        aq=float(m.get("book_ask_qty") or 0.0),
        bn=float(m.get("binance_mid") or 0.0),
        bn_age=_opt(m, "binance_age_ms"),
        fair=float(m["fair"]),
        fair_delta=_opt(m, "fair_delta"),
        basis=_opt(m, "basis_bps"),
        anchored=bool(anchored) if anchored is not None else None,
        bid=float(m.get("bid") or 0.0),
        ask=float(m.get("ask") or 0.0),
        place_bid=bool(m.get("place_bid", True)),
        place_ask=bool(m.get("place_ask", True)),
        regime=int(m.get("regime_level", 0)),
        ofi=_opt(m, "ofi"),
        depth_mid=_opt(m, "depth_mid"),
        depth_age=_opt(m, "depth_age_ms"),
        depth_qty=_opt(m, "depth_qty"),
        dbp=_opt(m, "depth_bid_px"),
        dap=_opt(m, "depth_ask_px"),
        dbi=_opt(m, "depth_bid_inner"),
        dai=_opt(m, "depth_ask_inner"),
        dbip=_opt(m, "depth_bid_inner_px"),
        daip=_opt(m, "depth_ask_inner_px"),
        dts=int(m["depth_ts_us"]) if m.get("depth_ts_us") is not None else None,
        basis_src=m.get("basis_src"),
    )


def line_symbol(line: str) -> str | None:
    """The `"symbol"` value of a log line without parsing its JSON (None when there is none)."""
    start = line.find('"symbol"')
    if start < 0:
        return None
    try:
        return line[start:].split('"')[3]
    except IndexError:
        return None


def load_metrics(paths: list[str], skipped: dict[str, int] | None = None,
                 symbols: set[str] | None = None) -> dict[str, list[Row]]:
    """MM_METRICS rows per symbol. `skipped` (if given) counts the MM_METRICS lines dropped per symbol (no
    ts_ms, no usable book, or unparseable JSON under the key '?'). With `symbols`, other symbols' lines are
    skipped before the JSON parse (a 4-symbol 24 h log holds ~800 MB of rows; one symbol a quarter of that)."""
    out: dict[str, list[Row]] = collections.defaultdict(list)
    for path in paths:
        for line in iter_lines(path):
            if "MM_METRICS" not in line:
                continue
            if symbols is not None and line_symbol(line) not in symbols:
                continue
            parsed = parse_metrics_row(line)
            if parsed:
                out[parsed[0]].append(parsed[1])
            elif skipped is not None:
                sym = line_symbol(line) or "?"
                skipped[sym] = skipped.get(sym, 0) + 1
    for rows in out.values():
        rows.sort(key=lambda r: r.ts)
    return dict(out)


class BookFile:
    """Recorded `ob_l2` frames per Delta symbol, each side a flat array (p0, s0, p1, s1, ...), best first.

    The bot logs `depth_ts_us` = the frame's venue `ts`. The recorder thins unchanged frames, so the join is
    as-of: the last recorded frame at or before that `ts`.
    """

    def __init__(self) -> None:
        self.ts: dict[str, list[int]] = collections.defaultdict(list)
        self.bids: dict[str, list[array]] = collections.defaultdict(list)
        self.asks: dict[str, list[array]] = collections.defaultdict(list)

    def load(self, path: str, symbols: set[str] | None = None) -> None:
        for line in iter_lines(path):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = rec.get("msg") if isinstance(rec, dict) else None
            if not isinstance(m, dict) or m.get("type") != "ob_l2":
                continue
            sy = m.get("sy")
            if symbols is not None and sy not in symbols:
                continue
            try:
                ts = int(m["ts"])
                b = array("d", (float(x) for lv in m.get("b", []) for x in lv[:2]))
                a = array("d", (float(x) for lv in m.get("a", []) for x in lv[:2]))
            except (KeyError, TypeError, ValueError):
                continue
            self.ts[sy].append(ts)
            self.bids[sy].append(b)
            self.asks[sy].append(a)
        for sy in self.ts:
            order = sorted(range(len(self.ts[sy])), key=self.ts[sy].__getitem__)
            self.ts[sy] = [self.ts[sy][i] for i in order]
            self.bids[sy] = [self.bids[sy][i] for i in order]
            self.asks[sy] = [self.asks[sy][i] for i in order]

    def asof(self, sy: str, ts_us: int) -> tuple[array, array] | None:
        ts = self.ts.get(sy)
        if not ts:
            return None
        i = bisect.bisect_right(ts, ts_us) - 1
        return (self.bids[sy][i], self.asks[sy][i]) if i >= 0 else None

    def frames(self, sy: str) -> int:
        return len(self.ts.get(sy, ()))


# ---------------------------------------------------------------- mm-core ports

class BasisEma:
    """Port of mm_core::fair::BasisEma."""

    __slots__ = ("half_life", "max_step", "clamp", "value", "samples", "first_t", "last_t")

    def __init__(self, half_life_sec: float, max_step_sec: float = math.inf, clamp_bps: float = math.inf):
        self.half_life = half_life_sec
        self.max_step = max_step_sec if max_step_sec > 0 else math.inf
        self.clamp = clamp_bps if clamp_bps > 0 else math.inf
        self.value: float | None = None
        self.samples = 0
        self.first_t = 0.0
        self.last_t = 0.0

    def reset(self) -> None:
        self.value = None
        self.samples = 0

    def update(self, t: float, delta_mid: float, binance_mid: float) -> float | None:
        valid = delta_mid > 0 and binance_mid > 0 and math.isfinite(delta_mid) and math.isfinite(binance_mid)
        if not valid or not math.isfinite(t):
            return self.value
        x = (delta_mid / binance_mid - 1.0) * 10_000.0
        v = self.value
        if v is None:
            self.value = x
            self.samples = 1
            self.first_t = t
            self.last_t = t
        elif t < self.last_t:
            pass
        else:
            delta_t = min(t - self.last_t, self.max_step)
            time_w = 1.0 - math.exp(-LN2 * delta_t / self.half_life) if self.half_life > 0 else 1.0
            self.samples += 1
            alpha = max(time_w, 1.0 / self.samples)
            x = min(max(x, v - self.clamp), v + self.clamp)
            self.value = v + alpha * (x - v)
            self.last_t = t
        return self.value

    def warm_sec(self, now: float) -> float:
        return max(now - self.first_t, 0.0) if self.value is not None else 0.0

    def last_update(self) -> float | None:
        return self.last_t if self.value is not None else None


class OfiTracker:
    """Port of mm_core::ofi::OfiTracker (window of L1 events)."""

    __slots__ = ("window", "capacity", "last_bid", "last_ask", "sum_ofi")

    def __init__(self, capacity: int = OFI_WINDOW):
        self.capacity = max(capacity, 4)
        self.window: collections.deque[float] = collections.deque()
        self.last_bid = (0.0, 0.0)
        self.last_ask = (0.0, 0.0)
        self.sum_ofi = 0.0

    def on_book(self, bid: float, bid_qty: float, ask: float, ask_qty: float) -> None:
        if self.last_bid[0] > 0.0:
            pb, b, pa, a = self.last_bid, (bid, bid_qty), self.last_ask, (ask, ask_qty)
            e = 0.0
            if b[0] >= pb[0]:
                e += b[1]
            if b[0] <= pb[0]:
                e -= pb[1]
            if a[0] <= pa[0]:
                e -= a[1]
            if a[0] >= pa[0]:
                e += pa[1]
            if len(self.window) >= self.capacity:
                self.sum_ofi -= self.window.popleft()
            self.window.append(e)
            self.sum_ofi += e
        self.last_bid = (bid, bid_qty)
        self.last_ask = (ask, ask_qty)

    def drift_bps(self, beta: float, depth: float) -> float:
        if depth <= 0.0:
            return 0.0
        return min(max(beta * self.sum_ofi / depth, -OFI_CLAMP_BPS), OFI_CLAMP_BPS)


def move_bps(history, now: float, lookback: float) -> float:
    """mm_core::fair::move_bps on (time_sec, mid) samples in ascending time."""
    if not history:
        return 0.0
    mid_now = history[-1][1]
    cutoff = now - lookback
    mid_ref = None
    for t, m in reversed(history):
        if t <= cutoff:
            mid_ref = m
            break
    if mid_ref is None or mid_now <= 0.0 or mid_ref <= 0.0:
        return 0.0
    return (mid_now - mid_ref) / mid_ref * 10_000.0


def microprice(bb: float, ba: float, bq: float, aq: float) -> float:
    bq, aq = max(bq, 0.0), max(aq, 0.0)
    if bq + aq <= 0.0:
        return (bb + ba) / 2.0
    return (bb * aq + ba * bq) / (bq + aq)


def resolve_fair(mid: float, micro: float, anchor: float | None, anchor_weight: float, lead_weight: float,
                 move: float, lead_max_bps: float, ofi_drift_bps: float) -> float:
    """mm_core::fair::resolve_fair_cex in fixed mode (funding carry left out, as quote_fair does)."""
    fair = (1.0 - MICRO_W) * mid + MICRO_W * micro
    aw = 0.0
    if anchor is not None and math.isfinite(anchor) and anchor > 0.0 and math.isfinite(anchor_weight):
        aw = min(max(anchor_weight, 0.0), 1.0)
    if aw > 0.0:
        fair = (1.0 - aw) * fair + aw * anchor
    shift = (1.0 - aw) * lead_weight * move
    if lead_max_bps > 0.0:
        shift = min(max(shift, -lead_max_bps), lead_max_bps)
    return fair * (1.0 + (shift + ofi_drift_bps) / 10_000.0)


def round_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(round(price / tick) * tick * 1e10) / 1e10


# floor_tick / ceil_tick follow strategy.rs's rounding (x 1e10, round, / 1e10), not shadow_fill_sim's
# round(.., 12): the replay must reproduce the bot's quotes to the tick.
def floor_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(math.floor(price / tick + 1e-9) * tick * 1e10) / 1e10


def ceil_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(math.ceil(price / tick - 1e-9) * tick * 1e10) / 1e10


def fixed_quotes(fair: float, tick: float, half_bps: float, regime_mult: float, bb: float, ba: float) -> tuple[float, float]:
    """mm_core::strategy::fixed_spread_quotes: fair +/- half bps, rounded away, kept inside the book."""
    h = half_bps * max(regime_mult, 1.0) / 10_000.0
    bid = floor_tick(fair * (1.0 - h), tick)
    ask = ceil_tick(fair * (1.0 + h), tick)
    if bb > 0.0 and ba > bb:
        bid = min(bid, round_tick(ba - tick, tick))
        ask = max(ask, round_tick(bb + tick, tick))
    return bid, ask


@dataclass(slots=True)
class SidePrice:
    price: float
    level: int
    inner: float  # size priced better than `price`
    inner_px: float | None  # the level just inside; None at the touch


def side_depth_price(levels: array | list, qty: float, is_bid: bool) -> tuple[SidePrice | None, str | None]:
    """mm_core::depth::side_depth_price on a flat (p, s, p, s, ...) side; (price, None) or (None, reason)."""
    if not (math.isfinite(qty) and qty > 0.0):
        return None, "invalid"
    n = len(levels) // 2
    if n == 0:
        return None, "empty_side"
    cum = 0.0
    prev: float | None = None
    for i in range(n):
        p, s = levels[2 * i], levels[2 * i + 1]
        if not (math.isfinite(p) and p > 0.0 and math.isfinite(s) and s > 0.0):
            return None, "invalid"
        if prev is not None and not (p < prev if is_bid else p > prev):
            return None, "invalid"
        if cum + s >= qty:
            return SidePrice(p, i, cum, prev), None
        prev = p
        cum += s
    return None, "thin"


def insert_order(levels: array | list, price: float, size: float, is_bid: bool, cap: int = DEPTH_LEVELS) -> array:
    """The side with our order of `size` at `price` added, kept to the venue's `cap` levels (a level inside the
    touch pushes the last one out of the snapshot, depth.rs 'level cap')."""
    out = array("d")
    placed = False
    n = len(levels) // 2
    for i in range(n):
        p, s = levels[2 * i], levels[2 * i + 1]
        if not placed:
            if abs(p - price) <= 1e-12 * max(abs(p), 1.0):
                out.extend((p, s + size))
                placed = True
                continue
            if (price > p) if is_bid else (price < p):
                out.extend((price, size))
                placed = True
        out.extend((p, s))
    if not placed:
        out.extend((price, size))
    return out[: 2 * cap]


# ---------------------------------------------------------------- the replay

@dataclass
class Seed:
    """The EMA state the log implies at its first row (the bot started earlier)."""

    value: float
    samples: int
    first_t: float
    note: str


def infer_seed(rows: list[Row], st: Settings) -> Seed | None:
    """Seed the EMA from the first logged basis_bps: the sample count from the first update's alpha, the
    warm-up start from the first logged `anchored` flip (warm_sec >= warmup there)."""
    first = next((i for i, r in enumerate(rows) if r.basis is not None), None)
    if first is None:
        return None
    r0 = rows[first]
    samples = 1_000_000  # past the warm-up: alpha is the time weight alone
    note = "warm-up over"
    updates = 0
    prev = r0
    for r in rows[first + 1 : first + 400]:
        if r.basis is None:
            break
        if is_fresh(r, st):
            updates += 1
            x = (r.mid / r.bn - 1.0) * 1e4
            x = min(max(x, prev.basis - st.clamp_bps), prev.basis + st.clamp_bps)
            if abs(x - prev.basis) > 0.05 and r.basis != prev.basis:
                alpha = (r.basis - prev.basis) / (x - prev.basis)
                delta_t = min((r.ts - prev.ts) / 1000.0, st.max_step_sec)
                time_w = 1.0 - math.exp(-LN2 * delta_t / st.half_life_sec) if st.half_life_sec > 0 else 1.0
                if 0 < alpha <= time_w * 1.02:
                    break
                if alpha > 0:
                    samples = max(int(round(1.0 / alpha)) - updates, 1)
                    note = f"n0={samples} from the first update"
                break
        prev = r
    flip = next((r for r in rows[first:] if r.anchored), None)
    first_t = (flip.ts / 1000.0 - st.warmup_sec) if flip is not None else r0.ts / 1000.0
    return Seed(r0.basis, samples, first_t, note)


@dataclass
class Replay:
    mode: str
    fair: list[float] = field(default_factory=list)  # the fair under test (OFI per Settings.ofi_anchored)
    fair_asis: list[float] = field(default_factory=list)  # as coded on main: OFI term also while anchored
    fair_old: list[float] = field(default_factory=list)  # no anchor, on this mode's book (as coded)
    fair_old_noofi: list[float] = field(default_factory=list)  # no anchor, OFI term removed
    anchored: list[bool] = field(default_factory=list)
    basis: list[float] = field(default_factory=list)  # NAN before the first sample
    updated: list[bool] = field(default_factory=list)
    own_touch: list[bool] = field(default_factory=list)  # the OMS price is this row's L1 (the basis gate)
    plan_touch: list[bool] = field(default_factory=list)  # a placed plan quote within MM_REQUOTE_TOL_BPS of this row's L1 (live_own_touch, for the calibration)
    qbid: list[float] = field(default_factory=list)  # OMS state after this row (NAN = side off)
    qask: list[float] = field(default_factory=list)
    pbid_asis: list[float] = field(default_factory=list)  # the plan's quotes from the as-coded fair (= the log's bid/ask)
    pask_asis: list[float] = field(default_factory=list)
    ofi_sum: list[float] = field(default_factory=list)
    place_bid: list[bool] = field(default_factory=list)
    place_ask: list[bool] = field(default_factory=list)
    place_bid_asis: list[bool] = field(default_factory=list)  # the side flags from the as-coded fair
    place_ask_asis: list[bool] = field(default_factory=list)
    warming: list[bool] = field(default_factory=list)  # EMA has a value but warm_sec < MM_BASIS_WARMUP_SEC
    live_mid: list[float] = field(default_factory=list)  # the book the fair was computed from
    live_spread_bps: list[float] = field(default_factory=list)  # its touch spread
    live_bq: list[float] = field(default_factory=list)  # its L1 sizes (ours included in live mode)
    live_aq: list[float] = field(default_factory=list)
    ofi_drift: list[float] = field(default_factory=list)  # the OFI term on that book, bps
    depth_mid: list[float] = field(default_factory=list)  # depth mid on this mode's ladder (NAN = none)
    pivot: list[bool] = field(default_factory=list)  # clean inner size in [X - q, X) on either side
    depth_moved: list[bool] = field(default_factory=list)  # our order moved the depth price (live)
    depth_move_bps: list[float] = field(default_factory=list)
    crossed_stale: int = 0  # loops where a stale quote of ours sat through the market (dropped)
    ladder_rows: int = 0  # rows priced on the recorded ladder (live depth)
    ladder_fallback: int = 0  # rows priced from the logged depth fields instead
    gaps: int = 0  # log gaps longer than 1.5 loops (loops the bot ran but did not log, e.g. an L3 pause)
    gap_loops: int = 0
    resyncs: int = 0  # gaps after which the EMA (and the OFI sum) were taken from the log


def replay(rows: list[Row], st: Settings, tick: float, q: float, mode: str = "shadow", source: str = "book",
           latency: int = 0, book: BookFile | None = None, symbol: str = "", seed: Seed | None = None,
           resync: bool = False) -> Replay:
    """Walk the rows through the bot's loop (runner.rs ~920-1090, strategy.rs compute_quote fixed mode).

    `resync`: after a gap in the log the bot's state is unknown (it updated its EMA and OFI on loops it did not
    log), so take the logged basis_bps and ofi at the first row after the gap."""
    live = mode == "live"
    out = Replay(mode)
    prev_ts: float | None = None
    gap_ms = 1.5 * st.loop_sec * 1000.0
    ema = BasisEma(st.half_life_sec, st.max_step_sec, st.clamp_bps)
    skip_first_update = False
    if seed is not None:
        ema.value, ema.samples, ema.first_t, ema.last_t = seed.value, seed.samples, seed.first_t, rows[0].ts / 1000.0
        skip_first_update = True
    ofi = OfiTracker(OFI_WINDOW)
    hist: collections.deque[tuple[float, float]] = collections.deque()
    oms_bid: float | None = None  # the OMS's view (updated at the decision, like oms.live)
    oms_ask: float | None = None
    pending: collections.deque[tuple[int, float | None, float | None]] = collections.deque()
    book_bid: float | None = None  # what the venue book shows (the decision, `latency` + 1 loops later)
    book_ask: float | None = None
    dsym = delta_symbol(symbol)
    half_tick = tick * 0.5

    for i, r in enumerate(rows):
        t = r.ts / 1000.0
        gap = prev_ts is not None and r.ts - prev_ts > gap_ms
        prev_gap_ts = prev_ts if prev_ts is not None else r.ts
        if gap:
            out.gaps += 1
            out.gap_loops += max(int(round((r.ts - prev_ts) / (st.loop_sec * 1000.0))) - 1, 0)
        prev_ts = r.ts
        while pending and pending[0][0] <= i:
            _, book_bid, book_ask = pending.popleft()
        bb, ba, bq, aq = r.bb, r.ba, r.bq, r.aq
        our_bid = our_ask = None
        if live:
            if book_bid is not None:
                if book_bid >= ba - half_tick:
                    out.crossed_stale += 1  # the market traded through it: a fill, not modelled
                elif book_bid > bb + half_tick:
                    our_bid, bb, bq = book_bid, book_bid, q
                else:
                    our_bid = book_bid
                    if abs(book_bid - bb) < half_tick:
                        bq += q
            if book_ask is not None:
                if book_ask <= bb + half_tick:
                    out.crossed_stale += 1
                elif book_ask < ba - half_tick:
                    our_ask, ba, aq = book_ask, book_ask, q
                else:
                    our_ask = book_ask
                    if abs(book_ask - ba) < half_tick:
                        aq += q
        ofi.on_book(bb, bq, ba, aq)
        native = (bb + ba) / 2.0
        micro = microprice(bb, ba, bq, aq)

        fresh = r.bn > 0 and (r.bn_age is None or r.bn_age <= st.binance_stale_ms)
        if fresh:
            hist.append((t, r.bn))
        else:
            hist.clear()
        while hist and hist[0][0] < t - 2.0 * st.lead_lookback_sec:
            hist.popleft()
        move = move_bps(hist, t, st.lead_lookback_sec) if r.bn > 0 else 0.0

        # Depth mid on this mode's ladder.
        depth_ok = r.depth_mid is not None and r.depth_age is not None and r.depth_age <= st.depth_stale_ms
        dmid = r.depth_mid if depth_ok else NAN
        pivot = False
        moved = False
        move_bps_depth = 0.0
        if r.depth_qty and r.dbi is not None and r.dai is not None:
            x = r.depth_qty
            pivot = (x - q <= r.dbi < x) or (x - q <= r.dai < x)
        if live and depth_ok and (our_bid is not None or our_ask is not None) and r.depth_qty:
            x = r.depth_qty
            ladder = book.asof(dsym, r.dts) if (book is not None and r.dts is not None) else None
            priced = False
            if ladder is not None:
                cb, _ = side_depth_price(ladder[0], x, True)
                ca, _ = side_depth_price(ladder[1], x, False)
                # Trust the ladder only when it reproduces the logged depth prices (the recorder's feed is
                # not the bot's: a frame can arrive on one before the other).
                if cb and ca and r.dbp is not None and r.dap is not None and abs(cb.price - r.dbp) < 1e-9 and abs(ca.price - r.dap) < 1e-9:
                    bids = insert_order(ladder[0], our_bid, q, True) if our_bid is not None else ladder[0]
                    asks = insert_order(ladder[1], our_ask, q, False) if our_ask is not None else ladder[1]
                    lb, _ = side_depth_price(bids, x, True)
                    la, _ = side_depth_price(asks, x, False)
                    priced = True
                    out.ladder_rows += 1
                    if lb is None or la is None:
                        depth_ok, dmid, moved = False, NAN, True
                    else:
                        dmid = (lb.price + la.price) / 2.0
                        moved = lb.price != cb.price or la.price != ca.price
            if not priced:
                out.ladder_fallback += 1
                # Logged fields only: a pivot moves that side to the level just inside the depth price.
                pb = r.dbp if r.dbp is not None else NAN
                pa = r.dap if r.dap is not None else NAN
                if our_bid is not None and r.dbi is not None and x - q <= r.dbi < x and r.dbip is not None:
                    pb, moved = r.dbip, True
                if our_ask is not None and r.dai is not None and x - q <= r.dai < x and r.daip is not None:
                    pa, moved = r.daip, True
                if math.isfinite(pb) and math.isfinite(pa):
                    dmid = (pb + pa) / 2.0
            if moved and r.depth_mid and math.isfinite(dmid):
                move_bps_depth = (dmid / r.depth_mid - 1.0) * 1e4

        # Basis: reset when too old, sample when the gate allows.
        lu = ema.last_update()
        if lu is not None and t - lu > st.max_age_sec:
            ema = BasisEma(st.half_life_sec, st.max_step_sec, st.clamp_bps)
        own = False
        if live:
            own = (oms_bid is not None and abs(oms_bid - bb) < half_tick) or (oms_ask is not None and abs(oms_ask - ba) < half_tick)
        updated = False
        if skip_first_update:
            skip_first_update = False
        elif source == "book":
            if fresh and not own:
                ema.update(t, native, r.bn)
                updated = True
        else:
            if fresh and depth_ok and math.isfinite(dmid):
                ema.update(t, dmid, r.bn)
                updated = True
        if resync and gap and r.basis is not None and ema.value is not None:
            ema.value = r.basis
            ema.last_t = t
            # The hidden loops also counted as warm-up samples (alpha = max(time weight, 1/n)).
            ema.samples += max(int(round((r.ts - prev_gap_ts) / (st.loop_sec * 1000.0))) - 1, 0)
            out.resyncs += 1  # the OFI window stays a plain replica: its entries are not logged, only its sum
        lu = ema.last_update()
        warm = ema.warm_sec(t) >= st.warmup_sec
        basis_fresh = warm and lu is not None and t - lu <= st.max_age_sec
        anchor = None
        if st.anchor_weight > 0.0 and fresh and basis_fresh and ema.value is not None and math.isfinite(ema.value):
            anchor = r.bn * (1.0 + ema.value / 10_000.0)
        anchored = anchor is not None

        ofi_drift = ofi.drift_bps(st.ofi_beta, bq + aq)
        fair_asis = resolve_fair(native, micro, anchor, st.anchor_weight, st.lead_beta, move, st.lead_max_bps, ofi_drift)
        if st.anchor_weight > 0.0 and not st.ofi_anchored:
            # PR C: with an anchor weight above 0 the OFI term never reads our own L1, in the fallback either.
            fair = resolve_fair(native, micro, anchor, st.anchor_weight, st.lead_beta, move, st.lead_max_bps, 0.0)
        else:
            fair = fair_asis
        fair_old = resolve_fair(native, micro, None, 0.0, st.lead_beta, move, st.lead_max_bps, ofi_drift)
        fair_old_noofi = resolve_fair(native, micro, None, 0.0, st.lead_beta, move, st.lead_max_bps, 0.0)

        # Quotes (fixed mode) and the fair-jump defence, then the OMS requote rule. The bot sets
        # last_fair = fair_native of the SAME loop before compute_quote (runner.rs:1082 then :1156), so the
        # defence (strategy.rs:750) tests |fair / this loop's L1 mid - 1| >= MM_FAIR_JUMP_BPS, on the
        # (synthetic) book the fair was computed from.
        bid, ask = fixed_quotes(fair, tick, st.half_bps, REGIME_MULT.get(r.regime, 1.0), bb, ba)
        place_bid, place_ask = jump_flags(fair, native, st)
        abid, aask = fixed_quotes(fair_asis, tick, st.half_bps, REGIME_MULT.get(r.regime, 1.0), bb, ba)
        place_bid_asis, place_ask_asis = jump_flags(fair_asis, native, st)
        if not place_bid:
            oms_bid = None
        elif oms_bid is None or abs(oms_bid - bid) / bid * 10_000.0 > st.tol_bps:
            oms_bid = bid
        if not place_ask:
            oms_ask = None
        elif oms_ask is None or abs(oms_ask - ask) / ask * 10_000.0 > st.tol_bps:
            oms_ask = ask
        pending.append((i + 1 + latency, oms_bid, oms_ask))

        out.fair.append(fair)
        out.fair_asis.append(fair_asis)
        out.fair_old.append(fair_old)
        out.fair_old_noofi.append(fair_old_noofi)
        out.anchored.append(anchored)
        out.basis.append(ema.value if ema.value is not None else NAN)
        out.updated.append(updated)
        out.own_touch.append(own)
        out.plan_touch.append((place_bid and abs(bid / bb - 1.0) * 1e4 <= st.tol_bps)
                              or (place_ask and abs(ask / ba - 1.0) * 1e4 <= st.tol_bps))
        out.qbid.append(oms_bid if oms_bid is not None else NAN)
        out.qask.append(oms_ask if oms_ask is not None else NAN)
        out.pbid_asis.append(abid)
        out.pask_asis.append(aask)
        out.ofi_sum.append(ofi.sum_ofi)
        out.place_bid.append(place_bid)
        out.place_ask.append(place_ask)
        out.place_bid_asis.append(place_bid_asis)
        out.place_ask_asis.append(place_ask_asis)
        out.warming.append(ema.value is not None and not warm)
        out.live_mid.append(native)
        out.live_spread_bps.append((ba / bb - 1.0) * 1e4)
        out.live_bq.append(bq)
        out.live_aq.append(aq)
        out.ofi_drift.append(ofi_drift)
        out.depth_mid.append(dmid)
        out.pivot.append(pivot)
        out.depth_moved.append(moved)
        out.depth_move_bps.append(move_bps_depth)
    return out


def jump_flags(fair: float, native: float, st: Settings) -> tuple[bool, bool]:
    """strategy.rs compute_quote fixed mode with MM_FAIR_JUMP_DEFENSIVE: the side the fair jumped away from
    is dropped when |fair / last_fair - 1| >= MM_FAIR_JUMP_BPS, where last_fair is this loop's L1 mid
    (runner.rs:1082 stores fair_native before the call at :1156)."""
    if not (st.jump_defensive and native > 0.0):
        return True, True
    jump = (fair / native - 1.0) * 10_000.0
    if abs(jump) < st.jump_bps:
        return True, True
    return (jump <= 0.0, jump >= 0.0)


def quote_series(rows: list[Row], fairs: list[float], st: Settings, tick: float) -> tuple[list[float], list[float]]:
    """Resting quotes for any fair series under the bot's rule (clean-book clamp, fair-jump drop against the
    row's own L1 mid, requote tolerance), latency 0: the OMS state after each row. NAN where the fair is NAN
    or the side is off."""
    qb: list[float] = []
    qa: list[float] = []
    ob = oa = None
    for r, f in zip(rows, fairs):
        if not math.isfinite(f) or f <= 0:
            ob = oa = None
            qb.append(NAN)
            qa.append(NAN)
            continue
        bid, ask = fixed_quotes(f, tick, st.half_bps, REGIME_MULT.get(r.regime, 1.0), r.bb, r.ba)
        pb, pa = jump_flags(f, r.mid, st)
        if not pb:
            ob = None
        elif ob is None or abs(ob - bid) / bid * 1e4 > st.tol_bps:
            ob = bid
        if not pa:
            oa = None
        elif oa is None or abs(oa - ask) / ask * 1e4 > st.tol_bps:
            oa = ask
        qb.append(ob if ob is not None else NAN)
        qa.append(oa if oa is not None else NAN)
    return qb, qa


def parity_replay(rows: list[Row], tick: float, max_age: float = 300.0, warm: float = 60.0, hl: float = 120.0,
                  clamp: float = 5.0, max_step: float = 0.8, tol: float = 3.0, half: float = 5.0,
                  stale_ms: float = 5000.0, st: Settings | None = None) -> dict:
    """The memo's livegate replica (verify/crit/livegate.py run_gated), kept separate so its two numbers are
    reproducible to the digit: rows with a Binance mid, the old fair = logged fair_delta (or fair), quotes
    clamped against the clean book, own touch = a resting quote at or inside the clean touch. With `st` the
    knobs come from the run's Settings (the defaults are the 13 Oct config's values); the ones used are
    returned under 'settings'."""
    if st is not None:
        max_age, warm, hl, clamp = st.max_age_sec, st.warmup_sec, st.half_life_sec, st.clamp_bps
        max_step, tol, half, stale_ms = st.max_step_sec, st.tol_bps, st.half_bps, st.binance_stale_ms
    used = {"max_age_sec": max_age, "warmup_sec": warm, "half_life_sec": hl, "clamp_bps": clamp,
            "max_step_sec": max_step, "tol_bps": tol, "half_bps": half, "stale_ms": stale_ms}
    rows = [r for r in rows if r.bn > 0]
    if not rows:
        return {"n": 0, "updated_pct": NAN, "anchored_pct": NAN, "settings": used}
    has_age = any(r.bn_age is not None for r in rows)
    has_fd = any(r.fair_delta is not None for r in rows)
    v = None
    cnt = 0
    tf = tl = 0.0
    rbid = rask = NAN
    upd = anch = 0
    for r in rows:
        t = r.ts / 1000.0
        fresh = ((r.bn_age or 0.0) <= stale_ms) if has_age else True
        own = (not math.isnan(rbid) and rbid >= r.bb - tick / 2) or (not math.isnan(rask) and rask <= r.ba + tick / 2)
        if v is not None and t - tl > max_age:
            v, cnt = None, 0
        if fresh and not own:
            x = (r.mid / r.bn - 1.0) * 1e4
            if v is None:
                v, cnt, tf, tl = x, 1, t, t
            else:
                d = min(t - tl, max_step)
                cnt += 1
                al = max(1.0 - math.exp(-LN2 * d / hl), 1.0 / cnt)
                v = v + al * (min(max(x, v - clamp), v + clamp) - v)
                tl = t
            upd += 1
        ok = v is not None and fresh and (t - tf) >= warm and (t - tl) <= max_age
        old = (r.fair_delta if has_fd and r.fair_delta is not None else r.fair)
        f = r.bn * (1 + v / 1e4) if ok else old
        anch += ok
        b = math.floor(f * (1 - half / 1e4) / tick + 1e-9) * tick
        a = math.ceil(f * (1 + half / 1e4) / tick - 1e-9) * tick
        b = min(b, r.ba - tick)
        a = max(a, r.bb + tick)
        if math.isnan(rbid) or abs(b / rbid - 1) * 1e4 > tol:
            rbid = b
        if math.isnan(rask) or abs(a / rask - 1) * 1e4 > tol:
            rask = a
    n = len(rows)
    return {"n": n, "updated_pct": 100.0 * upd / n, "anchored_pct": 100.0 * anch / n, "settings": used}


# ---------------------------------------------------------------- statistics

def percentile(values: list[float], p: float) -> float:
    if not values:
        return NAN
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def future_index(ts: list[float], h_sec: float, tol_ms: float = FUTURE_TOL_MS) -> list[int]:
    """Index of the first row at or after t + h (within tol), else -1 (expo.future_mid)."""
    n = len(ts)
    out = []
    for t in ts:
        target = t + h_sec * 1000.0
        j = bisect.bisect_left(ts, target)
        out.append(j if j < n and ts[j] - target < tol_ms else -1)
    return out


def slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return NAN
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return NAN
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


class BlockBoot:
    """Block bootstrap over fixed time blocks: statistics are sums per block, resampled with replacement."""

    def __init__(self, blocks: list[int], reps: int = 1000, seed: int = 1):
        self.blocks = blocks  # block id per scored row
        self.ids = sorted(set(blocks))
        self.reps = reps
        self.seed = seed

    def _group(self, values: list[tuple]) -> dict[int, list[float]]:
        acc: dict[int, list[float]] = {b: [0.0] * len(values[0]) for b in self.ids} if values else {}
        for b, v in zip(self.blocks, values):
            a = acc[b]
            for k, x in enumerate(v):
                a[k] += x
        return acc

    def ci(self, values: list[tuple], stat, level: float = 95.0) -> tuple[float, float]:
        """`values[i]` = the per-row sums (tuple); `stat(sums)` -> float on summed tuples. Returns the CI."""
        if not values or len(self.ids) < 2:
            return NAN, NAN
        acc = self._group(values)
        rng = random.Random(self.seed)
        ids = self.ids
        stats = []
        k = len(values[0])
        for _ in range(self.reps):
            pick = rng.choices(ids, k=len(ids))
            tot = [0.0] * k
            for b in pick:
                a = acc[b]
                for j in range(k):
                    tot[j] += a[j]
            s = stat(tot)
            if math.isfinite(s):
                stats.append(s)
        if not stats:
            return NAN, NAN
        half = (100.0 - level) / 2.0
        return percentile(stats, half), percentile(stats, 100.0 - half)


def slope_from_sums(s: list[float]) -> float:
    n, sx, sy, sxx, sxy = s[:5]
    if n < 3:
        return NAN
    den = sxx - sx * sx / n
    return (sxy - sx * sy / n) / den if den > 0 else NAN


def slope_sums(x: float, y: float) -> tuple:
    return (1.0, x, y, x * x, x * y)


# ---------------------------------------------------------------- evaluation

@dataclass
class Variant:
    name: str
    fair: list[float]
    qbid: list[float]
    qask: list[float]


def exposure_rows(v: Variant, ref: list[float], fut: list[int], mask: list[bool]) -> dict[int, tuple[float, float]]:
    """Row -> (bid exposed, ask exposed) where both sides rest, the future ref exists and the row is masked in."""
    out = {}
    for i, j in enumerate(fut):
        if j < 0 or not mask[i]:
            continue
        b, a, r = v.qbid[i], v.qask[i], ref[j]
        if math.isnan(b) or math.isnan(a) or not (r > 0):
            continue
        out[i] = (float((r / b - 1.0) * 1e4 < EXPOSED_BPS), float((a / r - 1.0) * 1e4 < EXPOSED_BPS))
    return out


def slope_rows(v: Variant, base: list[float], ref: list[float], fut: list[int], mask: list[bool], recentre: float = 0.0) -> dict[int, tuple[float, float]]:
    """Row -> (x, y): x = (fair - base)/base bps (recentred), y = (ref(t+h) - base)/base bps."""
    out = {}
    for i, j in enumerate(fut):
        if j < 0 or not mask[i]:
            continue
        f, b, r = v.fair[i], base[i], ref[j]
        if not (math.isfinite(f) and f > 0 and b > 0 and r > 0):
            continue
        out[i] = ((f / b - 1.0) * 1e4 - recentre, (r / b - 1.0) * 1e4)
    return out


def score_variant(v: Variant, old: Variant, ts: list[float], mid: list[float], mask: list[bool], boot: BlockBoot,
                  blocks: list[int], horizons=(1, 5, 30, 60), slope_h=SLOPE_H, ref: list[float] | None = None,
                  recentre: float = 0.0, base: list[float] | None = None) -> dict:
    """Slopes at the slope horizons and side-averaged exposure at every horizon, each with the difference
    against `old` and its block-bootstrap CI. `ref` (default the mid) is the yardstick series and `base`
    (default the mid) the frame both x = fair - base and y = ref(t+h) - base are measured in: pass the same
    series as both to keep one frame (the depth-mid yardstick)."""
    ref = mid if ref is None else ref
    base = mid if base is None else base
    res: dict = {"slope": {}, "expo": {}}
    for h in slope_h:
        fut = future_index(ts, h)
        a = slope_rows(v, base, ref, fut, mask, recentre)
        b = slope_rows(old, base, ref, fut, mask, recentre)
        common = sorted(set(a) & set(b))
        xs, ys = [a[i][0] for i in common], [a[i][1] for i in common]
        xo = [b[i][0] for i in common]
        s_new, s_old = slope(xs, ys), slope(xo, ys)
        vals = [slope_sums(*a[i]) + slope_sums(*b[i]) for i in common]
        bb = BlockBoot([blocks[i] for i in common], boot.reps, boot.seed)
        lo, hi = bb.ci(vals, lambda s: slope_from_sums(s[:5]) - slope_from_sums(s[5:]))
        res["slope"][h] = {"n": len(common), "new": s_new, "old": s_old, "diff": s_new - s_old, "ci": (lo, hi)}
    for h in horizons:
        fut = future_index(ts, h)
        a = exposure_rows(v, ref, fut, mask)
        b = exposure_rows(old, ref, fut, mask)
        common = sorted(set(a) & set(b))
        n = len(common)
        if n == 0:
            res["expo"][h] = {"n": 0}
            continue
        eb = sum(a[i][0] for i in common) / n * 100
        ea = sum(a[i][1] for i in common) / n * 100
        ob = sum(b[i][0] for i in common) / n * 100
        oa = sum(b[i][1] for i in common) / n * 100
        d = [((a[i][0] + a[i][1]) - (b[i][0] + b[i][1])) / 2.0 for i in common]
        bb = BlockBoot([blocks[i] for i in common], boot.reps, boot.seed)
        lo, hi = bb.ci([(x, 1.0) for x in d], lambda s: s[0] / s[1] * 100 if s[1] else NAN)
        res["expo"][h] = {
            "n": n, "bid": eb, "ask": ea, "avg": (eb + ea) / 2, "old_bid": ob, "old_ask": oa, "old_avg": (ob + oa) / 2,
            "diff": sum(d) / n * 100, "ci": (lo, hi), "diff_bid": eb - ob, "diff_ask": ea - oa,
        }
    return res


def fmt_ci(ci: tuple[float, float], unit: str = "") -> str:
    return f"[{ci[0]:+.2f}, {ci[1]:+.2f}]{unit}"


def infer_tick(rows: list[Row]) -> float:
    """The smallest price decimal the bot's quotes and the book use (quotes are rounded to the tick)."""
    dec = 0
    for r in rows[: min(len(rows), 5000)]:
        for x in (r.bid, r.ask, r.bb, r.ba):
            s = repr(x)
            if "e" in s or "." not in s:
                continue
            dec = max(dec, len(s.split(".")[1]))
    return 10.0 ** (-dec) if dec else 1.0


def parse_time(s: str) -> float:
    """ISO-8601 (Z or offset; naive = UTC) or a Unix ms integer -> ms."""
    s = s.strip()
    if s.lstrip("-").isdigit():
        return float(s)
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp() * 1000.0


def iso(ms: float) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_window(rows: list[Row], t0: float | None, t1: float | None, excludes: list[tuple[float, float]]) -> list[Row]:
    out = []
    for r in rows:
        if t0 is not None and r.ts < t0:
            continue
        if t1 is not None and r.ts >= t1:
            continue
        if any(a <= r.ts < b for a, b in excludes):
            continue
        out.append(r)
    return out


def book_stats(spreads: list[float], bqs: list[float], aqs: list[float], ofi_terms: list[float], q: float,
               own_touch: list[bool]) -> dict:
    """The three calibration statistics of a book: touch occupancy (our order is the touch, on either side), the
    touch spread's p50, and the p90 of |OFI term|. `dust_pct` (an L1 size no larger than our order on either
    side) is reported next to it: a clean book scores that one too, so it cannot discriminate."""
    n = len(spreads)
    occ = 100.0 * sum(own_touch) / n if n else NAN
    dust = 100.0 * sum(1 for b, a in zip(bqs, aqs) if 0 < b <= q or 0 < a <= q) / n if n else NAN
    return {"n": n, "touch_pct": occ, "dust_pct": dust, "spread_p50_bps": percentile(spreads, 50),
            "ofi_p90_bps": percentile([abs(x) for x in ofi_terms], 90)}


def live_own_touch(r: Row, tol_bps: float) -> bool:
    """A live log row where our quote is the touch: a placed side's plan quote within the requote tolerance of
    the L1 (the resting order is within MM_REQUOTE_TOL_BPS of the plan quote unless this row requotes, so an
    own touch satisfies this; the same measure is taken on the synthetic book, Replay.plan_touch)."""
    return ((r.place_bid and r.bid > 0 and r.bb > 0 and abs(r.bid / r.bb - 1.0) * 1e4 <= tol_bps)
            or (r.place_ask and r.ask > 0 and r.ba > 0 and abs(r.ask / r.ba - 1.0) * 1e4 <= tol_bps))


def calibrate(live_rows: list[Row], rep: Replay, q: float, st: Settings, ts: list[float] | None = None) -> dict:
    """The real live book (a live run's MM_METRICS: our orders are in book_bid/book_ask and their sizes) against
    the replay's synthetic live book, by the same three statistics. Tolerances from plans/live-basis.plan.md
    PR D: touch occupancy +/- 10 pp, spread p50 +/- 1 bps, OFI p90 +/- 1 bps. Touch occupancy is "our order is
    the touch", measured the same way on both books: a placed plan quote within MM_REQUOTE_TOL_BPS of the L1
    (live_own_touch on the live log, Replay.plan_touch on the synthetic book). With `ts` (the replay
    rows' clocks) the synthetic rows are clipped to the live log's span [min ts, max ts], so both books cover
    the same time. Also reports the live log's two-sided share (place_bid and place_ask both on): the replay is
    two-sided on every row, so a one-sided live bot explains part of a touch-occupancy gap."""
    if not live_rows:
        return {"real": book_stats([], [], [], [], q, []), "synthetic": book_stats([], [], [], [], q, []), "touch_ok": False,
                "spread_ok": False, "ofi_ok": False, "ok": False, "span": None, "live_two_sided_pct": NAN}
    lo, hi = min(r.ts for r in live_rows), max(r.ts for r in live_rows)
    idx = list(range(len(rep.live_spread_bps))) if ts is None else [i for i, t in enumerate(ts) if lo <= t <= hi]
    real = book_stats(
        [(r.ba / r.bb - 1.0) * 1e4 for r in live_rows], [r.bq for r in live_rows], [r.aq for r in live_rows],
        [min(max(st.ofi_beta * r.ofi / (r.bq + r.aq), -OFI_CLAMP_BPS), OFI_CLAMP_BPS) if r.ofi is not None and r.bq + r.aq > 0 else 0.0
         for r in live_rows], q, [live_own_touch(r, st.tol_bps) for r in live_rows])
    synth = book_stats([rep.live_spread_bps[i] for i in idx], [rep.live_bq[i] for i in idx], [rep.live_aq[i] for i in idx],
                       [rep.ofi_drift[i] for i in idx], q, [rep.plan_touch[i] for i in idx])
    synth["oms_touch_pct"] = 100.0 * sum(rep.own_touch[i] for i in idx) / len(idx) if idx else NAN
    out = {"real": real, "synthetic": synth, "span": (lo, hi),
           "live_two_sided_pct": 100.0 * sum(1 for r in live_rows if r.place_bid and r.place_ask and r.bid > 0 and r.ask > 0) / len(live_rows)}
    out["touch_ok"] = abs(real["touch_pct"] - synth["touch_pct"]) <= 10.0
    out["spread_ok"] = abs(real["spread_p50_bps"] - synth["spread_p50_bps"]) <= 1.0
    out["ofi_ok"] = abs(real["ofi_p90_bps"] - synth["ofi_p90_bps"]) <= 1.0
    out["ok"] = bool(synth["n"] and out["touch_ok"] and out["spread_ok"] and out["ofi_ok"])
    return out


def covered_hours(rows: list[Row], excludes: list[tuple[float, float]],
                  span: tuple[float, float] | None = None) -> tuple[float, float]:
    """(covered, excluded) hours: the wall span minus the part of it the --exclude windows remove. `span` is
    the windowed log's [first row, last row] before the exclusions (default the kept rows' span, which
    under-counts an exclusion that overlaps the window's edge)."""
    if len(rows) < 2:
        return 0.0, 0.0
    lo, hi = span if span is not None else (rows[0].ts, rows[-1].ts)
    cut: list[tuple[float, float]] = []
    for a, b in sorted((max(a, lo), min(b, hi)) for a, b in excludes):
        if b <= a:
            continue
        if cut and a <= cut[-1][1]:
            cut[-1] = (cut[-1][0], max(cut[-1][1], b))
        else:
            cut.append((a, b))
    excluded = sum(b - a for a, b in cut)
    return (hi - lo - excluded) / 3.6e6, excluded / 3.6e6


def enough_hours(hours: float, need: float, loop_sec: float) -> bool:
    """`hours` (a first-to-last row span: n - 1 loops) covers `need` hours within one loop, so a log of exactly
    24 h of loops (216 000 rows at 400 ms = 23.9999 h) is not PROVISIONAL on a rounding artefact."""
    return hours + loop_sec / 3600.0 >= need


def agreement(rows: list[Row], rep: Replay, tol_bps: float = 1e-3) -> dict:
    """How well a shadow replay matches the log: basis_bps within tol, the anchored flag, and diagnostics.

    The quote and side-flag checks use the as-coded fair (`fair_asis`, the one the bot quoted). The fallback
    fair's deviation is split: the first OFI_WINDOW rows (the replay has no Binance history for the 3 s move
    lead and no OFI window before the first logged row, while the bot already had both from its unlogged
    warm-up loops) and the rest."""
    n_b = ok_b = 0
    max_dev = 0.0
    n_a = ok_a = 0
    fair_dev = fair_dev_start = fair_dev_anch = fd_dev = 0.0
    n_q = ok_qb = ok_qa = ok_pl = 0
    n_o = ok_o = 0
    for i, r in enumerate(rows):
        if r.basis is not None and math.isfinite(rep.basis[i]):
            n_b += 1
            d = abs(rep.basis[i] - r.basis)
            max_dev = max(max_dev, d)
            ok_b += d <= tol_bps
        if r.anchored is not None:
            n_a += 1
            ok_a += rep.anchored[i] == r.anchored
        if r.fair > 0:
            d = abs(rep.fair_asis[i] / r.fair - 1.0) * 1e4
            if r.anchored:
                fair_dev_anch = max(fair_dev_anch, d)
            elif i < OFI_WINDOW:
                fair_dev_start = max(fair_dev_start, d)
            else:
                fair_dev = max(fair_dev, d)
        if r.fair_delta and i >= OFI_WINDOW:
            fd_dev = max(fd_dev, abs(rep.fair_old[i] / r.fair_delta - 1.0) * 1e4)
        if r.bid > 0 and r.ask > 0:
            n_q += 1
            ok_qb += abs(rep.pbid_asis[i] - r.bid) < 1e-9
            ok_qa += abs(rep.pask_asis[i] - r.ask) < 1e-9
            ok_pl += (rep.place_bid_asis[i], rep.place_ask_asis[i]) == (r.place_bid, r.place_ask)
        if r.ofi is not None and i >= OFI_WINDOW:
            n_o += 1
            ok_o += abs(rep.ofi_sum[i] - r.ofi) < 1e-6
    return {
        "basis_rows": n_b, "basis_agree_pct": 100.0 * ok_b / n_b if n_b else NAN, "basis_max_dev_bps": max_dev,
        "anchored_rows": n_a, "anchored_agree_pct": 100.0 * ok_a / n_a if n_a else NAN,
        "fair_max_dev_bps_anchored": fair_dev_anch, "fair_max_dev_bps_fallback": fair_dev,
        "fair_max_dev_bps_fallback_start": fair_dev_start, "fair_delta_max_dev_bps": fd_dev,
        "quote_rows": n_q, "bid_exact_pct": 100.0 * ok_qb / n_q if n_q else NAN,
        "ask_exact_pct": 100.0 * ok_qa / n_q if n_q else NAN, "place_flags_pct": 100.0 * ok_pl / n_q if n_q else NAN,
        "ofi_rows": n_o, "ofi_exact_pct": 100.0 * ok_o / n_o if n_o else NAN,
    }


def expo_ok(e: dict) -> bool:
    """The G5 bound on one exposure record: upper 95% CI <= +1 pp, per side <= +3 pp."""
    return bool(e.get("n")) and e["ci"][1] <= 1.0 and e["diff_bid"] <= 3.0 and e["diff_ask"] <= 3.0


def gate_components(sc: dict) -> dict[str, bool]:
    """The four gate components of a scored variant: G4@5 (slope >= old), G4@60 (slope >= old and the difference
    CI above 0), G5@30 and G5@60 (expo_ok)."""
    s5, s60 = sc["slope"][5], sc["slope"][60]
    return {"G4@5": bool(s5["new"] >= s5["old"]), "G4@60": bool(s60["new"] >= s60["old"] and s60["ci"][0] > 0),
            "G5@30": expo_ok(sc["expo"][30]), "G5@60": expo_ok(sc["expo"][60])}


def gate_verdict(comps: dict[str, bool | None]) -> bool | None:
    """A gate from its components: FAIL if any evaluable component fails, else n/a if any component is ruled
    out (None), else PASS."""
    if any(v is False for v in comps.values()):
        return False
    if any(v is None for v in comps.values()):
        return None
    return True


def pf(v: bool | None, na: str = "n/a") -> str:
    return "PASS" if v else na if v is None else "FAIL"


def json_safe(o):
    """NaN / inf -> None recursively, so --json is strict JSON (json.dump(allow_nan=False) then cannot emit
    a bare NaN token, which Node and serde reject)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {str(k): json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    return o


def evaluate(symbol: str, rows: list[Row], st: Settings, tick: float, q: float, source: str, args,
             book: BookFile | None, out_lines: list[str], excludes: list[tuple[float, float]] = (),
             calibrate_rows: list[Row] | None = None, skipped: int = 0,
             span: tuple[float, float] | None = None) -> dict:
    """Run every replay the gates need and print the report for one symbol. Returns the JSON record."""
    say = out_lines.append
    ts = [r.ts for r in rows]
    mid = [r.mid for r in rows]
    hours, excluded_h = covered_hours(rows, list(excludes), span)
    blocks = [int((t - ts[0]) // BLOCK_MS) for t in ts]
    fresh = [is_fresh(r, st) for r in rows]
    latencies = args.latencies
    primary_lat = latencies[0]
    x_contracts = next((r.depth_qty for r in rows if r.depth_qty), None)
    has_depth = any(r.depth_mid is not None for r in rows)
    logged_src = next((r.basis_src for r in rows if r.basis_src), None) or "book"
    seed = infer_seed(rows, st) if not args.cold_start else None

    say(f"=== {symbol}  rows {len(rows)} ({hours:.2f} h covered"
        + (f", {excluded_h:.2f} h excluded" if excluded_h else "") + f") {iso(ts[0])}..{iso(ts[-1])}"
        + (f"  skipped {skipped} unusable MM_METRICS lines" if skipped else "")
        + f"  tick {tick:g}  q {q:g} contracts  X {x_contracts if x_contracts else 'n/a'}  mode {args.mode}  source {source}  "
        f"latency {primary_lat}  loop {st.loop_sec * 1000:.0f} ms  anchor weight {st.anchor_weight:g}  basis max age "
        f"{st.max_age_sec:g} s  OFI while anchored: {'on (as coded)' if st.ofi_anchored else 'off (PR C)'}")
    rec: dict = {"symbol": symbol, "rows": len(rows), "hours": hours, "excluded_hours": excluded_h, "skipped_lines": skipped,
                 "tick": tick, "q": q, "depth_qty": x_contracts, "mode": args.mode, "source": source, "latency": primary_lat,
                 "settings": st.__dict__.copy()}

    # Clean (shadow) replays for both sources; the logged source is checked against the log. The other source's
    # EMA takes the same seed when the log carries that source (the depth and book bases differ by under 1 bps
    # and the EMA forgets in a few half-lives), so a short window does not carry the replay's own 60 s warm-up
    # into G1 and G2; a log without depth fields leaves the depth EMA cold (it would hold the seed unchanged).
    seed_for = {"book": seed, "depth": seed if has_depth else None}
    clean = {src: replay(rows, st, tick, q, "shadow", src, 0, None, symbol, seed_for[src], resync=(src == logged_src))
             for src in ("book", "depth")}
    agr = agreement(rows, clean[logged_src])
    rec["agreement"] = agr
    cl = clean[logged_src]
    rec["log_gaps"] = {"gaps": cl.gaps, "loops": cl.gap_loops, "resyncs": cl.resyncs}
    seed_note = (f"EMA seeded from the first logged basis ({seed.note}"
                 + ("" if source == logged_src or not seed_for[source] else f"; the {source} EMA from the same value") + ")") if seed else "cold start"
    gap_note = (f"; {cl.gaps} log gaps (~{cl.gap_loops} unlogged loops, e.g. L3 pauses), EMA re-read from the "
                f"log after {cl.resyncs} of them") if cl.gaps else "; no log gaps"
    say(f"Replay vs log (shadow, source={logged_src}, {seed_note}{gap_note}): basis within 1e-3 bps on "
        f"{agr['basis_agree_pct']:.2f}% of {agr['basis_rows']} rows (max dev {agr['basis_max_dev_bps']:.5f} bps); "
        f"anchored flag agrees on {agr['anchored_agree_pct']:.2f}% of {agr['anchored_rows']} rows")
    if cl.resyncs:
        nr = agreement(rows, replay(rows, st, tick, q, "shadow", logged_src, 0, None, symbol, seed))
        rec["agreement_no_resync"] = nr
        say(f"  without the gap resync: basis within 1e-3 bps on {nr['basis_agree_pct']:.2f}% (max dev "
            f"{nr['basis_max_dev_bps']:.3f} bps): the bot updated its EMA on the unlogged loops")
    say(f"  diagnostics (vs the as-coded fair the bot quoted): fair max dev {agr['fair_max_dev_bps_anchored']:.4f} bps on "
        f"anchored rows, {agr['fair_max_dev_bps_fallback']:.3f} bps on fallback rows after row {OFI_WINDOW} "
        f"({agr['fair_max_dev_bps_fallback_start']:.3f} bps on the first {OFI_WINDOW}: start-of-log, no Binance history for "
        f"the move lead / no OFI window before the first logged row); fair_delta max dev {agr['fair_delta_max_dev_bps']:.3f} bps "
        f"(after row {OFI_WINDOW}); OFI window sum exact on {agr['ofi_exact_pct']:.1f}% of rows (after {OFI_WINDOW}); "
        f"plan bid/ask reproduced {agr['bid_exact_pct']:.1f}% / {agr['ask_exact_pct']:.1f}%; side flags {agr['place_flags_pct']:.1f}%")
    if seed and not args.cold_start:
        cold = replay(rows, st, tick, q, "shadow", logged_src, 0, None, symbol, None)
        cagr = agreement(rows, cold)
        rec["agreement_cold"] = cagr
        say(f"  cold start instead: basis within 1e-3 bps on {cagr['basis_agree_pct']:.2f}% (max dev "
            f"{cagr['basis_max_dev_bps']:.3f} bps; the bot's EMA began before the first logged row)")

    # Live replays (one per latency) when asked.
    lives: dict[int, Replay] = {}
    if args.mode == "live":
        for lat in latencies:
            lives[lat] = replay(rows, st, tick, q, "live", source, lat, book, symbol, seed_for[source])
        if book is not None:
            lr = lives[primary_lat]
            say(f"  live depth: {lr.ladder_rows} rows priced on the recorded ladder, {lr.ladder_fallback} from the "
                f"logged depth fields; our order moved the depth price on {sum(lr.depth_moved)} rows; stale quotes "
                f"the market moved through: {lr.crossed_stale}")
    under = lives[primary_lat] if args.mode == "live" else clean[source]
    old_clean = clean["book"]  # the old fair does not depend on the source

    gates: dict[str, bool | None] = {}
    notes: dict[str, str] = {}  # why a gate is n/a

    # G1 health.
    nf = sum(fresh)
    n = len(rows)
    depth_ok_pct = 100.0 * sum(1 for i, r in enumerate(rows) if fresh[i] and r.depth_age is not None and r.depth_age <= G1_DEPTH_MS) / nf if nf else NAN
    anchor_pct = 100.0 * sum(1 for i in range(n) if fresh[i] and under.anchored[i]) / nf if nf else NAN
    warm_pct = 100.0 * sum(1 for i in range(n) if fresh[i] and under.warming[i]) / nf if nf else NAN
    updated_pct = 100.0 * sum(under.updated) / n
    g1 = (depth_ok_pct >= 95.0 and anchor_pct >= 95.0) if (has_depth and nf) else None
    gates["G1"] = g1
    if g1 is None:
        notes["G1"] = "no depth fields logged" if not has_depth else "no Binance-fresh rows"
    warm_src = "the bot's own at the log start" if seed else "the replay's cold start"
    say(f"G1 health: depth snapshot <= {G1_DEPTH_MS:.0f} ms on {depth_ok_pct:.1f}% of {nf} Binance-fresh rows"
        f"{'' if has_depth else ' (no depth fields logged: not evaluated)'}{'' if nf else ' (none: not evaluated)'}"
        f"; anchor on {anchor_pct:.1f}% (of the rest, "
        f"{warm_pct:.1f} pp is the {st.warmup_sec:.0f} s EMA warm-up, {warm_src}; basis updated on "
        f"{updated_pct:.1f}% of rows, own touch {100.0 * sum(under.own_touch) / n:.1f}%)  "
        f"[>= 95% each]  {pf(g1)}"
        + (f"  WARNING: the profile's MM_DEPTH_STALE_MS={st.depth_stale_ms:.0f} differs from G1's fixed 2000 ms "
           f"(it governs the bot's sampling only)" if st.depth_stale_ms != G1_DEPTH_MS else ""))
    rec["G1"] = {"depth_fresh_pct": depth_ok_pct, "anchor_pct": anchor_pct, "warmup_pct": warm_pct, "updated_pct": updated_pct,
                 "own_touch_pct": 100.0 * sum(under.own_touch) / n, "pass": g1}

    # G2 equivalence: depth EMA vs clean-L1 EMA, both on clean rows; pivot share on clean rows.
    diffs = [abs(clean["depth"].basis[i] - clean["book"].basis[i]) for i in range(n)
             if math.isfinite(clean["depth"].basis[i]) and math.isfinite(clean["book"].basis[i])]
    p90 = percentile(diffs, 90)
    n_depth_rows = sum(1 for r in rows if r.dbi is not None and r.dai is not None)
    pivot_pct = 100.0 * sum(clean["book"].pivot) / n_depth_rows if n_depth_rows else NAN
    g2 = (p90 <= 1.5 and pivot_pct <= 1.0) if (diffs and n_depth_rows) else None
    gates["G2"] = g2
    if g2 is None:
        notes["G2"] = "no depth fields logged"
    say(f"G2 equivalence: p90 |EMA basis(depth) - EMA basis(clean L1)| {p90:.3f} bps over {len(diffs)} rows [<= 1.5]; "
        f"pivot share {pivot_pct:.3f}% of {n_depth_rows} rows with depth (others' inside size in [X - q, X)) [<= 1%]  "
        f"{pf(g2, 'n/a (no depth fields logged)')}")
    rec["G2"] = {"p90_bps": p90, "rows": len(diffs), "pivot_pct": pivot_pct, "pivot_rows": n_depth_rows, "pass": g2}

    # G3 no self-reference.
    if args.mode == "live":
        live = lives[primary_lat]
        ref = clean[source]
        d3 = [abs(live.fair[i] / ref.fair[i] - 1.0) * 1e4 for i in range(n)]
        d3a = [abs(live.fair_asis[i] / ref.fair_asis[i] - 1.0) * 1e4 for i in range(n)]
        both_idx = [i for i in range(n) if live.anchored[i] and ref.anchored[i]]
        both = [d3[i] for i in both_idx]
        both_asis = [d3a[i] for i in both_idx]
        mismatch = 100.0 * sum(1 for i in range(n) if live.anchored[i] != ref.anchored[i]) / n
        p99, p99a = percentile(both, 99), percentile(both_asis, 99)
        g3 = (p99 <= 0.5) if both else None
        gates["G3"] = g3
        if g3 is None:
            notes["G3"] = "no row anchored in both replays"
        say(f"G3 no self-reference (live, q={q:g}, latency {primary_lat}; the anchored fair, i.e. rows anchored in both "
            f"replays, n {len(both)}): p99 |fair(live book) - fair(clean book)| {p99:.3f} bps [<= 0.5] (p50 "
            f"{percentile(both, 50):.3f}, max {max(both) if both else NAN:.3f}); all rows p99 {percentile(d3, 99):.3f} "
            f"(the fallback old fair reads our own mid live; PR C pulls quotes after {10} s anchor-off); anchored "
            f"flags differ on {mismatch:.2f}% of rows; as coded today with the OFI term in the anchored fair: p99 "
            f"{p99a:.3f} bps  {pf(g3)}")
        rec["G3"] = {"p99_bps": p99, "p50_bps": percentile(both, 50), "max_bps": max(both) if both else NAN, "n": len(both),
                     "all_rows_p99_bps": percentile(d3, 99), "anchored_mismatch_pct": mismatch, "p99_as_coded_bps": p99a, "pass": g3}
    else:
        gates["G3"] = None
        notes["G3"] = "shadow mode"
        say("G3 no self-reference: not evaluated in --mode shadow (run --mode live)")

    # Variants for G4/G5.
    boot = BlockBoot(blocks, args.boot, args.seed)
    old_v = Variant("clean old fair", old_clean.fair_old, *quote_series(rows, old_clean.fair_old, st, tick))
    new_v = Variant(f"new fair ({args.mode}, {source})", under.fair, under.qbid, under.qask)
    sc = score_variant(new_v, old_v, ts, mid, fresh, boot, blocks)

    # Oracle rows first (the plan: fair = the future mid at +5 s and +60 s), each scored on every gate component;
    # a component either oracle fails is ruled out of its gate (the plan's "no gate may rely on a metric the
    # oracle fails"). An oracle cannot fail its own horizon (its quotes sit 5 bps clear of the mid it knows, its
    # slope there is 1), so the rule bites across horizons: the +60 s oracle's exposure at +30 s, the +5 s
    # oracle's at +60 s, and the +60 s oracle's +5 s slope. The +1 s / +5 s exposures are diagnostics only.
    ruled_out: dict[str, str] = {}  # component -> the oracle(s) that fail it
    oracle_lines = []
    rec["oracle"] = {}
    for h in ORACLE_H:
        fut = future_index(ts, h)
        of = [mid[j] if j >= 0 else NAN for j in fut]
        ov = Variant(f"oracle +{h} s", of, *quote_series(rows, of, st, tick))
        osc = score_variant(ov, old_v, ts, mid, fresh, boot, blocks)
        comps = gate_components(osc)
        fails = [k for k, v in comps.items() if not v]
        for f in fails:
            ruled_out[f] = f"{ruled_out[f]}, oracle+{h}" if f in ruled_out else f"oracle+{h}"
        o5, o60 = osc["slope"][5], osc["slope"][60]
        e30, e60 = osc["expo"][30], osc["expo"][60]
        oracle_lines.append(
            f"  oracle (fair = mid +{h} s): slope +5 s {o5['new']:.3f} (old {o5['old']:.3f}), +60 s {o60['new']:.3f} "
            f"(old {o60['old']:.3f}, diff CI {fmt_ci(o60['ci'])}); exposure diff vs old +30 s {e30.get('diff', NAN):+.2f} pp "
            f"CI {fmt_ci(e30.get('ci', (NAN, NAN)))} per side {e30.get('diff_bid', NAN):+.2f}/{e30.get('diff_ask', NAN):+.2f}, "
            f"+60 s {e60.get('diff', NAN):+.2f} pp CI {fmt_ci(e60.get('ci', (NAN, NAN)))} per side "
            f"{e60.get('diff_bid', NAN):+.2f}/{e60.get('diff_ask', NAN):+.2f} (diagnostics +1 s "
            f"{osc['expo'][1].get('diff', NAN):+.1f} +5 s {osc['expo'][5].get('diff', NAN):+.1f} pp); "
            f"fails: {', '.join(fails) or 'none'}")
        rec["oracle"][str(h)] = {"slope": osc["slope"], "expo": osc["expo"], "components": comps, "fails": fails}
    rec["ruled_out"] = ruled_out

    s5, s60 = sc["slope"][5], sc["slope"][60]
    comps_new = gate_components(sc)
    c4 = {k: None if k in ruled_out else comps_new[k] for k in ("G4@5", "G4@60")}
    g4 = gate_verdict(c4)
    gates["G4"] = g4
    if g4 is None:
        notes["G4"] = "oracle fails " + ", ".join(k for k, v in c4.items() if v is None)

    def comp(k: str, v: bool | None) -> str:
        return pf(v, f"n/a ({ruled_out[k]} fails it)" if k in ruled_out else "n/a")

    say(f"G4 information (slope of Delta's mid move on fair - mid, n {s60['n']}): +5 s new {s5['new']:.3f} old "
        f"{s5['old']:.3f} [new >= old] {comp('G4@5', c4['G4@5'])}; +60 s new {s60['new']:.3f} old {s60['old']:.3f}, diff "
        f"{s60['diff']:+.3f} CI {fmt_ci(s60['ci'])} [new >= old; CI60 > 0] {comp('G4@60', c4['G4@60'])}  =>  "
        f"{pf(g4, 'n/a (' + notes.get('G4', '') + ')')}")
    rec["G4"] = {str(h): sc["slope"][h] for h in SLOPE_H}
    rec["G4"]["components"] = c4
    rec["G4"]["pass"] = g4

    c5: dict[str, bool | None] = {}
    parts = []
    for h in GATE_H:
        e = sc["expo"][h]
        k = f"G5@{h}"
        c5[k] = None if k in ruled_out else comps_new[k]
        if e["n"] == 0:
            parts.append(f"+{h} s: no scored rows {comp(k, c5[k])}")
            continue
        parts.append(f"+{h} s new {e['avg']:.2f}% (bid {e['bid']:.2f} ask {e['ask']:.2f}) old {e['old_avg']:.2f}% "
                     f"diff {e['diff']:+.2f} pp CI {fmt_ci(e['ci'])}, per side {e['diff_bid']:+.2f}/{e['diff_ask']:+.2f} pp "
                     f"{comp(k, c5[k])}")
    g5 = gate_verdict(c5)
    gates["G5"] = g5
    if g5 is None:
        notes["G5"] = "oracle fails " + ", ".join(k for k, v in c5.items() if v is None)
    say(f"G5 exposure (side-averaged, within {EXPOSED_BPS:g} bps of or through the future mid, vs the clean old fair): "
        + "; ".join(parts) + f" [upper CI <= +1 pp; per side <= +3 pp]  =>  {pf(g5, 'n/a (' + notes.get('G5', '') + ')')}")
    diag = []
    for h in DIAG_H:
        e = sc["expo"][h]
        if e["n"]:
            diag.append(f"+{h} s new {e['avg']:.2f}% old {e['old_avg']:.2f}% diff {e['diff']:+.2f} pp CI {fmt_ci(e['ci'])}")
    say("  diagnostics only (Delta lags; an oracle fails here): " + "; ".join(diag))
    rec["G5"] = {str(h): sc["expo"][h] for h in (1, 5, 30, 60)}
    rec["G5"]["components"] = c5
    rec["G5"]["pass"] = g5
    out_lines.extend(oracle_lines)
    if ruled_out:
        say(f"  RULE (plan): no gate may rely on a metric the oracle fails: " + "; ".join(f"{k} ({v})" for k, v in ruled_out.items())
            + " cannot judge a fair on this window and are marked n/a above")

    # Baselines.
    say("Baselines (slope +5/+60 s; exposure +30/+60 s side-averaged):")
    base_list = [("clean old fair (as coded, OFI in)", old_v)]
    if args.mode == "live":
        lv = lives[primary_lat]
        base_list.append(("live-mode old fair, OFI term removed", Variant("live old no-OFI", lv.fair_old_noofi, *quote_series(rows, lv.fair_old_noofi, st, tick))))
        base_list.append(("live-mode old fair, as coded (OFI on our own L1)", Variant("live old", lv.fair_old, *quote_series(rows, lv.fair_old, st, tick))))
    rec["baselines"] = {}
    for name, bv in base_list:
        bsc = score_variant(bv, old_v, ts, mid, fresh, boot, blocks, horizons=GATE_H)
        say(f"  {name:48s} slope {bsc['slope'][5]['new']:.3f} / {bsc['slope'][60]['new']:.3f}; exposure "
            f"{bsc['expo'][30].get('avg', NAN):.2f}% / {bsc['expo'][60].get('avg', NAN):.2f}%"
            + ("" if bv is old_v else f" (diff vs clean old {bsc['expo'][30].get('diff', NAN):+.2f} / {bsc['expo'][60].get('diff', NAN):+.2f} pp)"))
        rec["baselines"][name] = {"slope": bsc["slope"], "expo": bsc["expo"]}

    # Depth-mid yardstick in its own frame: x = fair - depth mid, y = future depth mid - depth mid, both on
    # the depth mid recentred by its mean offset from the L1 mid (the plan's G4 text is the L1-mid frame
    # above; this one is the same test with the depth mid as both base and reference).
    if has_depth:
        offs = [(r.depth_mid / r.mid - 1.0) * 1e4 for r in rows if r.depth_mid]
        c = statistics.fmean(offs) if offs else 0.0
        dref = [r.depth_mid / (1.0 + c / 1e4) if r.depth_mid else NAN for r in rows]
        dmask = [fresh[i] and math.isfinite(dref[i]) for i in range(n)]
        dsc = score_variant(new_v, old_v, ts, mid, dmask, boot, blocks, horizons=GATE_H, ref=dref, base=dref)
        say(f"Depth-mid yardstick (one frame: depth mid recentred by {c:+.2f} bps as base and reference; not the plan's "
            f"L1-mid frame): slope +5 s new {dsc['slope'][5]['new']:.3f} old {dsc['slope'][5]['old']:.3f}; +60 s new "
            f"{dsc['slope'][60]['new']:.3f} old {dsc['slope'][60]['old']:.3f} CI {fmt_ci(dsc['slope'][60]['ci'])}; exposure "
            f"+30 s diff {dsc['expo'][30].get('diff', NAN):+.2f} pp CI {fmt_ci(dsc['expo'][30].get('ci', (NAN, NAN)))}, "
            f"+60 s diff {dsc['expo'][60].get('diff', NAN):+.2f} pp CI {fmt_ci(dsc['expo'][60].get('ci', (NAN, NAN)))}")
        rec["depth_yardstick"] = {"recentre_bps": c, "frame": "depth mid (base and reference)", "slope": dsc["slope"], "expo": dsc["expo"]}

    # Latency sensitivity.
    if args.mode == "live" and len(latencies) > 1:
        say("Latency sensitivity (live):")
        rec["latency"] = {}
        for lat in latencies:
            lv = lives[lat]
            ref = clean[source]
            d3 = [abs(lv.fair[i] / ref.fair[i] - 1.0) * 1e4 for i in range(n) if lv.anchored[i] and ref.anchored[i]]
            a_pct = 100.0 * sum(1 for i in range(n) if fresh[i] and lv.anchored[i]) / nf if nf else NAN
            lvv = Variant("l", lv.fair, lv.qbid, lv.qask)
            lsc = score_variant(lvv, old_v, ts, mid, fresh, boot, blocks, horizons=GATE_H, slope_h=(60,))
            say(f"  {lat} loop(s): anchor on {a_pct:.1f}%, basis updated {100.0 * sum(lv.updated) / n:.1f}%, "
                f"G3 p99 {percentile(d3, 99):.3f} bps, slope60 {lsc['slope'][60]['new']:.3f}, exposure diff +30 s "
                f"{lsc['expo'][30].get('diff', NAN):+.2f} +60 s {lsc['expo'][60].get('diff', NAN):+.2f} pp, "
                f"depth moved {sum(lv.depth_moved)} rows, stale-through {lv.crossed_stale}")
            rec["latency"][str(lat)] = {"anchor_pct": a_pct, "updated_pct": 100.0 * sum(lv.updated) / n,
                                        "g3_p99": percentile(d3, 99), "slope60": lsc["slope"][60]["new"],
                                        "expo_diff_30": lsc["expo"][30].get("diff"), "expo_diff_60": lsc["expo"][60].get("diff")}

    cal = None
    if args.mode == "live" and calibrate_rows is not None:
        cal = calibrate(calibrate_rows, lives[primary_lat], q, st, ts)
        r_, s_ = cal["real"], cal["synthetic"]
        if cal["span"]:
            lo_, hi_ = cal["span"]
            cidx = [i for i in range(n) if lo_ <= ts[i] <= hi_]
            # The same measure on the clean book, with no order of ours: what the spread geometry alone scores.
            cal["clean_touch_pct"] = 100.0 * sum(clean[source].plan_touch[i] for i in cidx) / len(cidx) if cidx else NAN
        else:
            cal["clean_touch_pct"] = NAN
        rec["calibration"] = cal
        span = f"{iso(cal['span'][0])}..{iso(cal['span'][1])}" if cal["span"] else "empty"
        say(f"Calibration vs the real live book ({r_['n']} live rows, {s_['n']} synthetic rows clipped to the live log's "
            f"span {span}): touch occupancy (a placed quote within {st.tol_bps:g} bps of the L1) real {r_['touch_pct']:.1f}% "
            f"synthetic {s_['touch_pct']:.1f}% [+/- 10 pp] {'PASS' if cal['touch_ok'] else 'FAIL'} (the clean book with no "
            f"order of ours scores {cal['clean_touch_pct']:.1f}% on that measure, so it discriminates only above that; OMS at "
            f"the synthetic touch {s_['oms_touch_pct']:.1f}%; dust, an L1 size <= q on either side: real {r_['dust_pct']:.1f}% "
            f"synthetic {s_['dust_pct']:.1f}%); spread p50 real {r_['spread_p50_bps']:.2f} synthetic "
            f"{s_['spread_p50_bps']:.2f} bps [+/- 1] {'PASS' if cal['spread_ok'] else 'FAIL'}; |OFI term| p90 real "
            f"{r_['ofi_p90_bps']:.2f} synthetic {s_['ofi_p90_bps']:.2f} bps [+/- 1] {'PASS' if cal['ofi_ok'] else 'FAIL'}"
            f"  =>  {'CALIBRATED' if cal['ok'] else 'UNCALIBRATED'}")
        say(f"  the live bot was two-sided on {cal['live_two_sided_pct']:.1f}% of its rows (place_bid and place_ask on); "
            f"the replay is two-sided at a constant q on every row and models no fills, so a touch-occupancy gap "
            f"beyond that share is unexplained by the synthetic book")
        gates["CAL"] = cal["ok"]
        if not cal["ok"] and gates.get("G3"):
            # A pass on an unvalidated synthetic book is not evidence; a fail on it still stands (fail beats n/a).
            notes["G3"] = "synthetic live book uncalibrated"
            gates["G3"] = None

    if args.parity:
        par = parity_replay(rows, tick, st=st)
        rec["parity"] = par
        ps = par["settings"]
        say(f"Parity (livegate-equivalent, n={par['n']}): basis updated on {par['updated_pct']:.1f}% of samples; "
            f"anchored {par['anchored_pct']:.1f}%  (replica settings: half-life {ps['half_life_sec']:g} s, clamp "
            f"{ps['clamp_bps']:g} bps, warm-up {ps['warmup_sec']:g} s, max age {ps['max_age_sec']:g} s, max step "
            f"{ps['max_step_sec']:g} s, requote tol {ps['tol_bps']:g} bps, half spread {ps['half_bps']:g} bps, Binance "
            f"stale {ps['stale_ms']:g} ms)")

    say("Not modelled: " + "; ".join(NOT_MODELLED) + ".")
    main_gates = ("G1", "G2", "G3", "G4", "G5")
    failed = [k for k in main_gates if gates.get(k) is False]
    unevaluated = [k for k in main_gates if gates.get(k) is None]
    if failed:
        verdict = "FAIL (" + ", ".join(failed) + ")"
        code = 1
    elif unevaluated:
        verdict = "INCOMPLETE"
        code = 3
    else:
        verdict = "PASS"
        code = 0
    if not enough_hours(hours, 24.0, st.loop_sec):
        verdict = f"PROVISIONAL {verdict} ({hours:.2f} h covered < 24 h)"
    if unevaluated:
        verdict += "; not evaluated: " + ", ".join(f"{k} ({notes.get(k, '')})" for k in unevaluated)
    if cal is not None and not cal["ok"]:
        verdict += "; synthetic live book UNCALIBRATED: G3 and the live-mode rows are provisional"
    verdict += "; G6 (live path: PR A merged, PR E merged or waived) is judged outside this script"
    say(f"Verdict: {verdict}")
    rec["gates"] = gates
    rec["gate_notes"] = notes
    rec["verdict"] = verdict
    rec["exit"] = code
    return rec


# ---------------------------------------------------------------- main

class _HelpFormatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    """Keeps the docstring's layout and prints every option's default (none for the options without one)."""

    def _get_help_string(self, action):
        if action.default in (None, False, []):
            return action.help
        return super()._get_help_string(action)


def main(argv: list[str] | None = None) -> int:
    paragraphs = __doc__.split("\n\n")
    ap = argparse.ArgumentParser(description=paragraphs[0], formatter_class=_HelpFormatter,
                                 epilog=next(p for p in paragraphs if p.startswith("Exit code:")))
    src = ap.add_argument_group("inputs")
    src.add_argument("--run-dir", help="shadow run dir: dry-run*.log[.gz], config.txt, delta_*_book_*.jsonl")
    src.add_argument("--metrics", action="append", help="MM_METRICS log (repeatable)")
    src.add_argument("--config", help="config.txt (key=value lines, the shadow's profile)")
    src.add_argument("--book", action="append", help="recorded ob_l2 book file (repeatable)")
    ap.add_argument("--symbol", help="comma list; default every symbol in the log")
    ap.add_argument("--from", dest="t0", help="ISO time or ts_ms (inclusive)")
    ap.add_argument("--to", dest="t1", help="ISO time or ts_ms (exclusive)")
    ap.add_argument("--exclude", nargs=2, action="append", default=[], metavar=("T0", "T1"),
                    help="window removed from every statistic (repeatable), e.g. a live run's; its span does not count as covered data")
    ap.add_argument("--q", type=float, help="our order size in contracts (default MM_ORDER_QTY_<SYM> / contract value)")
    ap.add_argument("--tick", type=float, help="price tick (default inferred from the logged prices)")
    ap.add_argument("--source", choices=["book", "depth"], help="basis source to replay (default MM_BASIS_SOURCE_<SYM> or book)")
    ap.add_argument("--mode", choices=["shadow", "live"], default="shadow", help="shadow: the clean logged book; live: the synthetic live book (G3)")
    ap.add_argument("--latency", default="0,1,2", help="loops of delay on the replayed quotes; the first is the one judged")
    ap.add_argument("--loop-ms", type=float, default=400.0, help="the bot's --loop-ms (max_step = 2 loops, gap detection); shadow.sh uses 400")
    ap.add_argument("--anchor-weight", type=float, help="override MM_FAIR_ANCHOR_WEIGHT (0 = the old fair, as a run without the key)")
    ap.add_argument("--ofi-anchored", action="store_true", help="keep the OFI term in the anchored fair (as coded on main today); default = PR C's design, OFI out while anchored")
    ap.add_argument("--cold-start", action="store_true", help="do not seed the EMA from the first logged basis")
    ap.add_argument("--parity", action="store_true", help="print the livegate-equivalent numbers (basis updated %%, anchored %%)")
    ap.add_argument("--calibrate", metavar="LIVE_LOG", help="a real live run's MM_METRICS log: compare its book with the synthetic "
                    "live book over the live log's span (touch occupancy, spread p50, OFI p90); --mode live")
    ap.add_argument("--json", help="write the results here (strict JSON: undefined statistics are null)")
    ap.add_argument("--min-hours", type=float, default=1.0, help="covered hours needed per symbol (else exit 2)")
    ap.add_argument("--min-rows", type=int, default=500, help="rows needed per symbol (else exit 2)")
    ap.add_argument("--boot", type=int, default=1000, help="bootstrap replications")
    ap.add_argument("--seed", type=int, default=1, help="bootstrap seed")
    args = ap.parse_args(argv)

    try:
        args.latencies = [int(x) for x in args.latency.split(",")]
        if not args.latencies or any(x < 0 for x in args.latencies):
            raise ValueError("latencies must be non-negative loop counts")
        t0 = parse_time(args.t0) if args.t0 else None
        t1 = parse_time(args.t1) if args.t1 else None
        excludes = [(parse_time(a), parse_time(b)) for a, b in args.exclude]
        if any(b <= a for a, b in excludes):
            raise ValueError("--exclude T0 T1 needs T0 < T1")
        if args.loop_ms <= 0:
            raise ValueError("--loop-ms must be positive")
        if args.mode != "live" and (args.calibrate or args.book):
            raise ValueError("--calibrate and --book need --mode live (the synthetic live book)")
    except ValueError as e:
        print(f"unusable option: {e}", file=sys.stderr)
        return 2

    metric_paths = list(args.metrics or [])
    book_paths = list(args.book or [])
    config_path = args.config
    if args.run_dir:
        metric_paths += sorted(glob.glob(os.path.join(args.run_dir, "dry-run*.log*")))
        book_paths += sorted(glob.glob(os.path.join(args.run_dir, "delta_*_book_*.jsonl*")))
        config_path = config_path or os.path.join(args.run_dir, "config.txt")
    if not metric_paths:
        print("no metrics input: pass --run-dir or --metrics", file=sys.stderr)
        return 2
    missing = [p for p in metric_paths + book_paths if not os.path.exists(p)]
    if args.config and not os.path.exists(args.config):
        missing.append(args.config)  # an explicit --config must exist; the --run-dir default stays optional
    if missing:
        print(f"input not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    cfg = load_config(config_path)
    skipped: dict[str, int] = {}
    metrics = load_metrics(metric_paths, skipped, set(args.symbol.split(",")) if args.symbol else None)
    if not metrics:
        print(f"no MM_METRICS rows in {metric_paths}" + (f" for {args.symbol}" if args.symbol else ""), file=sys.stderr)
        return 2
    symbols = args.symbol.split(",") if args.symbol else sorted(metrics)

    book = None
    if book_paths and args.mode == "live":
        book = BookFile()
        wanted = {delta_symbol(s) for s in symbols}
        for p in book_paths:
            book.load(p, wanted)

    lines: list[str] = []
    results = []
    codes: list[int] = []
    thin = False
    calibrate_all: dict[str, list[Row]] | None = None
    if args.calibrate:
        if not os.path.exists(args.calibrate):
            print(f"input not found: {args.calibrate}", file=sys.stderr)
            return 2
        calibrate_all = load_metrics([args.calibrate])
    for sym in symbols:
        windowed = apply_window(metrics.pop(sym, []), t0, t1, [])  # popped: a symbol's rows are freed after its report
        span = (windowed[0].ts, windowed[-1].ts) if len(windowed) > 1 else None
        rows = apply_window(windowed, None, None, excludes)
        del windowed
        cal_rows = apply_window(calibrate_all.get(sym, []), t0, t1, excludes) if calibrate_all is not None else None
        hours, excluded_h = covered_hours(rows, excludes, span)
        if len(rows) < args.min_rows or not enough_hours(hours, args.min_hours, max(args.loop_ms, 100.0) / 1000.0):
            lines.append(f"=== {sym}: thin data: {len(rows)} rows, {hours:.2f} h covered"
                         + (f" ({excluded_h:.2f} h excluded)" if excluded_h else "")
                         + f" (need >= {args.min_rows} rows and >= {args.min_hours:g} h)")
            thin = True
            results.append({"symbol": sym, "rows": len(rows), "hours": hours, "excluded_hours": excluded_h, "exit": 2})
            continue
        source = args.source or cfg_get(cfg, "MM_BASIS_SOURCE", sym) or "book"
        if source not in ("book", "depth"):
            print(f"{sym}: unknown MM_BASIS_SOURCE {source!r}", file=sys.stderr)
            return 2
        st = Settings.from_config(cfg, sym, args.loop_ms, source)
        st.ofi_anchored = args.ofi_anchored
        if args.anchor_weight is not None:
            st.anchor_weight = min(max(args.anchor_weight, 0.0), 1.0)
        if st.anchor_weight <= 0.0:
            if args.anchor_weight is not None:
                why = f"--anchor-weight {args.anchor_weight:g}"
            elif cfg_get(cfg, "MM_FAIR_ANCHOR_WEIGHT", sym) is None:
                why = "no MM_FAIR_ANCHOR_WEIGHT in the config"
            else:
                why = f"MM_FAIR_ANCHOR_WEIGHT={cfg_get(cfg, 'MM_FAIR_ANCHOR_WEIGHT', sym)} in the config"
            lines.append(f"WARNING {sym}: anchor weight 0 ({why}): the fair under test is the old fair; pass "
                         f"--anchor-weight 1 to judge the anchored one")
        tick = args.tick or infer_tick(rows)
        x_contracts = next((r.depth_qty for r in rows if r.depth_qty), None)
        depth_base = cfg_get(cfg, "MM_BASIS_DEPTH_QTY", sym)
        cv = (float(depth_base) / x_contracts) if (depth_base and x_contracts) else 1.0
        q = args.q
        q_note = "--q"
        if q is None:
            oq = cfg_get(cfg, "MM_ORDER_QTY", sym)
            if oq:
                q = float(oq) / cv
                q_note = f"MM_ORDER_QTY{'_' + sym if f'MM_ORDER_QTY_{sym}' in cfg else ''}={oq} base units / contract value {cv:g}"
            else:
                px = statistics.median(r.mid for r in rows[:: max(1, len(rows) // 1000)])
                q = max(1.0, round(50.0 / (px * cv)))
                q_note = f"no MM_ORDER_QTY_{sym} in the config: a $50 quote at {px:.5g} with contract value {cv:g}"
        lines.append("")
        lines.append(f"[{sym}] q = {q:g} contracts ({q_note}); tick {tick:g}" + (" (--tick)" if args.tick else " (inferred)"))
        rec = evaluate(sym, rows, st, tick, q, source, args, book, lines, excludes, cal_rows, skipped.get(sym, 0), span)
        results.append(rec)
        del rows
        codes.append(rec["exit"])
    print("\n".join(lines))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(json_safe({"args": vars(args), "results": results}), f, indent=1, allow_nan=False)
    # Precedence: thin data anywhere (2) > a failed gate (1) > an unevaluated gate (3) > all passed (0).
    if thin:
        return 2
    if 1 in codes:
        return 1
    if 3 in codes:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
