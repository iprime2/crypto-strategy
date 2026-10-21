#!/usr/bin/env python3
"""Universe family of research2/phase1_plan.md (frozen 2026-10-21, sections 6.0 and 6.3): D-0 survivorship-free loader logic and
UNI-1 yearly ex-ante liquidity-ranked universe with its three neighbors. Every parameter is the plan's; nothing was tuned on results.

Cells (ids as registered; neighbors are '<id>__<label>'). All of them run on the Bw panel only (`harness.py <ids> --panels Bw`);
on any other panel they raise, so a stray A/B/C run cannot be mistaken for a result.
  D-0               the static 24 ex-ante cohort (data.EXANTE24) through the D-0 masking logic on the full pool; precondition and
                    harness-level proof of the gate (its Delta vs the harness's static-24 baseline must be 0.000 on every window)
  UNI-1             N = 9, yearly reset, 30-day median USD turnover, age >= 365 closes, incumbents stay while rank <= 18
  UNI-1__age121     neighbor (a): age floor 121
  UNI-1__quarterly  neighbor (b): reset on the first decision day of each quarter
  UNI-1__N12        neighbor (c): N = 12 (incumbent rank <= 24); its whole-contract line is run at $5,000
Comparison (research-number class, plan section 5): extra["base_coins"] = data.EXANTE24, i.e. the harness's baseline on the Bw
panel restricted to the static 24 (bit-identical to panel B: checked, max diff 0 on O/H/L/C/V/F/Q).

Common to all cells (the baseline's pieces, unchanged): signal = max(mean_L sign(P_t/P_{t-L} - 1), 0), L in (20, 60, 120);
vol = uncentred CC60; w_i = sig_i (TV/N_t)/max(vol_i, 0.05) with N_t = universe members with 121 consecutive closes on row t;
gross cap, band and cadence from the harness. W row t uses rows <= t only (truncation test in `check`).

Interpretations (rules the plan leaves open; each picks the reading closest to the cited source):

D-0 (plan 6.0; master_candidates DATA-1)
  I-D0.1 Candidacy: a coin is a candidate on row t iff it has a close and Binance quote_volume Q(t) > 0. Rows with Q <= 0 (the
         zombie rows with frozen prices that FTT, SC, RAY, FTM, ... keep for years, and pre-launch rows) are removed from the panel
         for every purpose (signal, vol, 121-close history, age, turnover rank, P&L): O/H/L/C/V/Q -> NaN, funding -> 0.
  I-D0.2 Listing lives and delisting: a life starts at a symbol's first Q > 0 row and again at the first Q > 0 row after any
         zero-volume row; the delisting day of a life is its last Q > 0 row when that row is before the panel's last row
         (2026-09-30). On the cleaned panel the next row has no close, so sim.simulate flattens the position at that close at the
         taker cost on both cadences (the plan's rule, and the same mechanism panel B applies to EOS on 2025-05-21). This is the
         plan's one-row look-ahead at a delisting; W itself never looks ahead.
  I-D0.3 Missing rows (no kline at all) are data gaps, not delistings: they do not end a life. They are the 2022-02-26..28 and
         2022-04-01..02 file gaps on XRP/LTC/TRX/XLM/ZEC/IOTA/VET and five month-long gaps (NMR, DASH, TLM, ICP, BNX). The
         simulator flattens across them and the 121-close rule restarts after them, exactly as in the baseline (T7 #4).
  I-D0.4 Same-ticker relistings (11 symbols with a mid-life zero-volume run of 19-898 rows: CVC, CTK, CVX, LIT, SLP, TLM, ICP,
         MAVIA, AERGO, AIA, PUMP) are treated like renamed symbols: a new listing with no history (age restarts, universe
         membership does not carry over). Renamed symbols (MATIC->POL, FTM->S, RNDR->RENDER, KLAY->KAIA, and EOS->A, MKR->SKY,
         FXS->FRAX in the same archive) are separate symbols, so they are new listings by construction; no series is stitched.
  I-D0.5 Funding is the panel's archive funding (fundingRate files; 0 where a symbol has none, reported by `report` as the
         flagged list). Q is USD quote volume for every symbol (0 NaN-Q rows in the pool).
  I-D0.6 Gate (run by `python3 variants_universe.py check`): the static 24 cohort (each coin's first listing life) through this
         logic, both standalone on Bw.sub(EXANTE24) and inside the full 696-symbol pool through the same code path as UNI-1,
         must give FULL Sharpe in [0.85, 0.86] daily and [0.81, 0.82] weekly and equal the harness's raw static-24 line to 1e-12.
         It does: 0.8512 / 0.8101 (= phase2/baseline.json B). Delisting events hit by the cohort: one (EOS, 2025-05-21).

UNI-1 (plan 6.3; verify_universe.md refined rule; master_candidates UNI-1/UNI-3/UNI-5)
  I-U1.1 Reset rows: the 2020 universe is chosen at the close of 2020-04-30 (plan: "2020 starts from the top-9 on 2020-04-30") on
         both cadences. After that it is reset on the first decision row of each January: daily = the Jan 1 row; weekly = the
         first Sunday-candle row of January, which is the weekly book's first decision day. Neighbor (b) resets on the first
         decision row of Jan/Apr/Jul/Oct, from July 2020. Membership is frozen between resets.
  I-U1.2 Turnover = median Binance daily quote volume (USD) over the 30 rows ending at the reset row, on the cleaned panel (so
         zero-volume rows are excluded as untradeable and missing rows are skipped). A coin is ranked only if it is a candidate
         on the reset row, has >= 30 closes in its current life (so a 30-day median exists), and is not excluded (I-U1.5).
  I-U1.3 Age = closes with Q > 0 in the current listing life, up to and including the reset row. The floor is an ENTRY
         condition (UNI-3's exact rule: "a coin may enter U at a reset only if it has >= 365 daily closes"), so incumbents are
         not re-tested. At the 2020-04-30 start no USDT-M perp had 365 closes (the oldest, BTCUSDT, listed 2019-09-08, had about
         235; the panel itself starts 2020-01-01), so the literal floor would leave the start universe empty, contradicting the
         plan's start clause. The start universe is therefore the top-N by turnover among ranked coins with NO age floor, in
         every cell (the start is the plan's fixed initial condition). Members trade from their 121st close, as in the baseline;
         panel B starts the same way. Consequence: at the 2021-01-01 reset only BTC/ETH/BCH have 365 closes (XRP has 362), so
         2021 keeps the start universe. The floor first binds on 2022-01-01 (neighbor (a): 2021-01-01; neighbor (b): 2021-01).
  I-U1.4 Hysteresis: ranks are computed within the eligible list, i.e. age-eligible candidates plus the incumbents that are still
         candidates in the same listing life (the index-provider buffer-zone convention). An incumbent with rank <= H stays; the
         free slots go to the best-ranked non-incumbents. H = 18 for N = 9. For the N = 12 neighbor H = 24, which is 2N, the
         verifier's "incumbent stays while rank <= 2N"; the plan states only 18 for N = 9. Ties are broken by symbol.
  I-U1.5 Exclusions: the plan says "metal/xStock/stablecoin/leveraged/pre-launch". The archive has no tags, so exclusion is by
         symbol, identified from listing date and price level:
         - metals/commodities: XAU XAG XPT XPD PAXG XAUT COPPER CL BZ NATGAS
         - equity/ETF perps: AAPL AMZN AVGO BABA COIN CRCL EWJ EWY GOOGL HOOD INTC META MSFT MSTR MU NVDA PLTR QQQ SPY TSLA TSM
           SNDK
         - stablecoins: USDC, and USTC (a failed algorithmic stablecoin)
         - composite indices: BTCDOM DEFI. These are not a single crypto; the plan's tag list does not name them, so this is
           recorded, but it is moot because they never rank inside the top 18 (`report` prints the check).
         The archive has no leveraged products and no identifiable pre-launch ones; the age floor covers pre-launch. Every
         stock/commodity listing is from 2026 and never meets an age floor. Only PAXG (quarterly neighbor, 2026-04/07),
         USDC, USTC, BTCDOM and DEFI ever do.
         Checked with a shadow ranking that has no exclusions (`report` prints any hit): in every cell and on both cadences,
         no excluded product ranks <= H at any reset except PAXG at the quarterly neighbor's 2026-04 reset (rank 11). It would
         not have entered: all 9 incumbents were kept, so there was no free slot. So the exclusions, including the two indices
         the plan does not name, change nothing in the unrounded lines.
  I-U1.6 A delisted member goes flat at its delisting close (I-D0.2), leaves U (its life ends) and is not replaced until the next
         reset. N_t = members with 121 consecutive closes on row t. This is the engine's own N ("signal, TV/N, band, cap
         unchanged"; verify_universe.md: "a universe change is a wrapper that filters the dict per date", and the engine sets N
         = coins with 121 closes that day), so a delisting or a data gap shrinks N_t exactly as in the baseline. The alternative
         literal reading, N = |U| fixed at the reset, is not used.
  I-U1.7 Feasibility gate (UNI-5), applied on whole-contract lines only:
         - Rule: at each reset, after selection, a member outside the live nine stays iff
           E_r x (TV/N_pre)/max(vol60, 0.05) >= 2 x cv x P_r.
         - E_r is the book's running equity at the reset close (sequential re-simulation; E = initial capital at the 2020
           start). The plan's E is account equity, as in COST-2's u = w E/(P cv).
         - N_pre = |U| before the gate. This is a single pass: a member that passes at N_pre also passes at the larger
           post-gate budget.
         - vol60 is the rule's CC60 at the reset row; an undefined vol60 fails the gate. P_r = the reset-row close.
         - cv = data.CVALS where known, else $25 / the coin's first close in the panel (coin units), as instructed.
         Gated-out names are not replaced; N_t follows I-U1.6. The unrounded lines (all the harness runs on Bw) have no
         contract constraint and no gate.
  I-U1.8 Whole-contract lines round with that same cv table (sim.CVALS is rebound for the call and restored; no file is changed).
         They are compared with the static 24 rounded with the same table, both through D-0.

Deviations forced (reported in the structured result as well):
  - harness.py writes no summary line for Bw rows (summary_line looks for B/B25/B25G keys and prints "(no B panel)"), and it runs
    neither capital nor Delta-funding-stress lines on Bw. The JSON rows (FULL/POST/H1/H2 vs the static 24, bootstrap, matched vol,
    after-tax) are complete. The plan's whole-contract lines at $1,000 / $5,000 (UNI-1, (a), (b); (c) at $5,000), names changed per
    reset and delisting events hit are produced by `python3 variants_universe.py report [--cells ...] [--cadences ...]`, which
    prints to stdout and writes nothing.
  - Self-test on Bw (daily only) instead of panel A, because these cells are defined on the pool only.
  - The whole-contract cv table is installed by rebinding sim.CVALS for the duration of one sim.simulate call (try/finally restore),
    because sim.simulate reads cv from that module global and falls back to 1 coin unit for coins without a Delta contract. No file
    is modified, and the unrounded lines are unaffected.
  - The harness's matched-vol re-run, bootstrap and after-tax lines work unchanged through custom_sim, which returns
    sim.simulate's own result dict plus a 'cols' key naming the simulated columns.

Self-test evidence (2026-10-21, Bw, daily, unrounded; numbers are results, never used to set a parameter):
  D-0 Delta vs static 24: 0.000 on FULL/POST/H1/H2. UNI-1 FULL 1.050 vs 0.851, POST 0.862 vs 0.586.

CLI: python3 variants_universe.py check   (D-0 gate + truncation look-ahead test + static-mask equivalence)
     python3 variants_universe.py report [--cells UNI-1,UNI-1__age121,...] [--cadences daily,weekly] [--capitals default|none|1000,5000]
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, os, sys, weakref
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import data, rules, sim
from registry import variant

SPAN = 121
MED_WIN = 30
START = dt.date(2020, 4, 30)
A0, A1 = dt.date(2020, 5, 1), dt.date(2026, 9, 30)
POST = dt.date(2022, 1, 1)
WINDOWS = {"full": (None, None), "post": (POST, None), "h1": (A0, dt.date(2023, 12, 31)), "h2": (dt.date(2024, 1, 1), A1)}
DAILY = dict(name="daily", tv=0.40, max_gross=2.0, band=0.0, weekly=False)    # = harness.DAILY
WEEKLY = dict(name="weekly", tv=0.25, max_gross=1.0, band=0.10, weekly=True)  # = harness.WEEKLY
CV_DEFAULT_USD = 25.0
POOL_FILE = f"{data.SP}/universe/pool_all.json"
NINE = frozenset(data.NINE)

EXCL_METAL = "XAU XAG XPT XPD PAXG XAUT COPPER CL BZ NATGAS".split()
EXCL_XSTOCK = "AAPL AMZN AVGO BABA COIN CRCL EWJ EWY GOOGL HOOD INTC META MSFT MSTR MU NVDA PLTR QQQ SPY TSLA TSM SNDK".split()
EXCL_STABLE = "USDC USTC".split()
EXCL_INDEX = "BTCDOM DEFI".split()
EXCLUDE = frozenset(EXCL_METAL + EXCL_XSTOCK + EXCL_STABLE + EXCL_INDEX)

SPECS = {
    "UNI-1": dict(N=9, H=18, age=365, reset="yearly"),
    "UNI-1__age121": dict(N=9, H=18, age=121, reset="yearly"),
    "UNI-1__quarterly": dict(N=9, H=18, age=365, reset="quarterly"),
    "UNI-1__N12": dict(N=12, H=24, age=365, reset="yearly"),
}
CAPITALS = {"UNI-1": (1000, 5000), "UNI-1__age121": (1000, 5000), "UNI-1__quarterly": (1000, 5000), "UNI-1__N12": (5000,)}


# ---------------------------------------------------------------- D-0: survivorship-free masking

def _lives(C, Q):
    """pos[t, j] = candidate (close and Q > 0); LIFE[t, j] = listing-life id (0 before the first Q > 0 row; +1 at the first Q > 0
    row after any zero-volume row); AGE[t, j] = Q > 0 closes in the current life up to t; LAST[t, j] = last Q > 0 row of a life."""
    T, N = C.shape
    fin = np.isfinite(C)
    pos = fin & np.isfinite(Q) & (Q > 0)
    zero = fin & ~pos
    life = np.zeros(N, np.int32); age = np.zeros(N, np.int32); gap = np.zeros(N, bool)
    LIFE = np.zeros((T, N), np.int32); AGE = np.zeros((T, N), np.int32)
    for t in range(T):
        new = pos[t] & ((life == 0) | gap)
        life = np.where(new, life + 1, life)
        age = np.where(new, 0, age)
        gap = gap & ~new
        age = np.where(pos[t], age + 1, age)
        gap = gap | (zero[t] & (life > 0))
        LIFE[t] = life; AGE[t] = age
    LAST = np.zeros((T, N), bool)
    nxt = np.zeros(N, np.int32)  # life id of the next Q > 0 row after t (0 = none)
    for t in range(T - 1, -1, -1):
        LAST[t] = pos[t] & (nxt != LIFE[t])
        nxt = np.where(pos[t], LIFE[t], nxt)
    return pos, LIFE, AGE, LAST


def d0_clean(p, pos=None):
    """The panel with every non-candidate row (no close, or Q <= 0) removed: O/H/L/C/V/Q -> NaN, funding -> 0."""
    if pos is None:
        pos = np.isfinite(p.C) & np.isfinite(p.Q) & (p.Q > 0)
    m = lambda X: np.where(pos, X, np.nan)
    return data.Panel(p.dates, list(p.coins), m(p.O), m(p.H), m(p.L), m(p.C), m(p.V), np.where(pos, p.F, 0.0), m(p.Q))


class _Ctx:
    """Everything the cells need from one raw panel, computed once (cached per panel object)."""
    def __init__(self, p):
        self.raw = p
        self.dates, self.coins, self.idx = p.dates, list(p.coins), p.idx
        self.T, self.N = p.C.shape
        self.pos, self.LIFE, self.AGE, self.LAST = _lives(p.C, p.Q)
        self.pc = d0_clean(p, self.pos)
        self.Cc, self.Qc = self.pc.C, self.pc.Q
        self.excl = np.array([c in EXCLUDE for c in self.coins])
        self.nine = np.array([c in NINE for c in self.coins])
        self.vol = rules.vol_cc(self.Cc, 60)
        self.volf = np.nan_to_num(self.vol, nan=np.inf)
        self.sig = np.maximum(np.nan_to_num(rules.sig_sign_mean(self.Cc)), 0.0)
        self.valid = rules.rolling_valid(self.Cc, SPAN)
        first = np.full(self.N, np.nan)
        for j in range(self.N):
            f = np.flatnonzero(self.pos[:, j])
            if len(f):
                first[j] = self.Cc[f[0], j]
        self.first_close = first
        self.cv = np.array([data.CVALS.get(c, CV_DEFAULT_USD / first[j] if np.isfinite(first[j]) else 1.0) for j, c in enumerate(self.coins)])
        self.cache = {}


_CTX = weakref.WeakKeyDictionary()


def _ctx(p):
    c = _CTX.get(p)
    if c is None:
        c = _Ctx(p); _CTX[p] = c
    return c


def _is_pool(p):
    return len(p.coins) >= 100 and bool(np.isfinite(p.Q).any())


def _ctx_pool(p, cell):
    if not _is_pool(p):
        raise ValueError(f"{cell} is defined on the survivorship-free pool only (plan 6.0/6.3): run harness.py {cell} --panels Bw")
    return _ctx(p)


def _weights(ctx, cad, U):
    """The baseline sizing restricted to the universe mask U: N_t = members with 121 consecutive closes (I-U1.6)."""
    return rules.size_per_asset(ctx.sig, ctx.volf, ctx.valid & U, cad["tv"], cad["max_gross"])


def _sim(ctx, W, kw):
    """sim.simulate on the cleaned panel, restricted to the columns that ever carry weight (the others contribute nothing). With a
    capital, whole contracts use cv = data.CVALS else $25 / first close (I-U1.8): sim.CVALS is rebound for the call and restored."""
    cols = np.flatnonzero(np.abs(W).sum(axis=0) > 0)
    if len(cols) == 0:
        cols = np.array([0])
    names = [ctx.coins[j] for j in cols]
    sub = ctx.pc.sub(names)
    saved = sim.CVALS
    try:
        if kw.get("capital"):
            sim.CVALS = {c: float(ctx.cv[j]) for c, j in zip(names, cols)}
        res = sim.simulate(sub, W[:, cols], **kw)
    finally:
        sim.CVALS = saved
    res["cols"] = names
    return res


def _static_mask(ctx, coins):
    """A static cohort: each coin's first listing life (life id 1), all rows."""
    U = np.zeros((ctx.T, ctx.N), bool)
    for c in coins:
        if c not in ctx.coins:
            continue
        j = ctx.coins.index(c)
        U[:, j] = ctx.LIFE[:, j] == 1
    return U


# ---------------------------------------------------------------- UNI-1: ex-ante liquidity-ranked universe

def _reset_rows(ctx, weekly, reset):
    """The 2020-04-30 start row, then the first decision row of each January (yearly) or of each Jan/Apr/Jul/Oct (quarterly)."""
    r0 = ctx.idx.get(START)
    if r0 is None:
        return []
    months = (1,) if reset == "yearly" else (1, 4, 7, 10)
    rows, seen = [r0], set()
    for t in range(r0 + 1, ctx.T):
        d = ctx.dates[t]
        if d.month in months and (d.year, d.month) not in seen and (not weekly or d.weekday() == 6):
            seen.add((d.year, d.month)); rows.append(t)
    return rows


def _select(ctx, r, inc, N, H, floor, excl=None):
    """Top-N by trailing 30-row median USD turnover with incumbent hysteresis (rank <= H). inc = {col: life id} of the current U.
    floor None = no age floor (the 2020 start, I-U1.3). excl = exclusion mask (default ctx.excl; an all-False mask gives the shadow
    ranking used only to check that exclusions matter). Returns (members in rank order, {col: rank} of the eligible list)."""
    pos = ctx.pos[r]
    base = pos & ~(ctx.excl if excl is None else excl) & (ctx.AGE[r] >= MED_WIN)
    inc_ok = np.zeros(ctx.N, bool)
    for j, L in inc.items():
        inc_ok[j] = base[j] and ctx.LIFE[r, j] == L
    elig = base & (ctx.AGE[r] >= floor) if floor else base.copy()
    elig |= inc_ok
    cols = np.flatnonzero(elig)
    if len(cols) == 0:
        return [], {}
    med = np.nanmedian(ctx.Qc[max(r - MED_WIN + 1, 0):r + 1][:, cols], axis=0)
    order = [int(j) for _, _, j in sorted(zip(-med, [ctx.coins[j] for j in cols], cols))]
    rank = {j: i + 1 for i, j in enumerate(order)}
    kept = [j for j in order if inc_ok[j] and rank[j] <= H]
    fill = [j for j in order if j not in kept][:max(N - len(kept), 0)]
    return sorted(kept + fill, key=rank.get), rank


def _gate(ctx, r, sel, E, tv):
    """UNI-5 feasibility at the reset (I-U1.7): E x (TV/N_pre)/max(vol60, 0.05) >= 2 x cv x P; the live nine are exempt."""
    n = max(len(sel), 1); kept, out = [], []
    for j in sel:
        if ctx.nine[j]:
            kept.append(j); continue
        v, px = ctx.vol[r, j], ctx.Cc[r, j]
        ok = bool(np.isfinite(v) and np.isfinite(px) and E * (tv / n) / max(v, 0.05) >= 2.0 * ctx.cv[j] * px)
        (kept if ok else out).append(j)
    return kept, out


def _excluded_in_top_h(ctx, r, inc, spec, floor):
    """Excluded products (I-U1.5) that would have ranked <= H in the eligible list had they not been excluded: {symbol: rank}."""
    _, shadow = _select(ctx, r, inc, spec["N"], spec["H"], floor, excl=np.zeros(ctx.N, bool))
    return {str(ctx.coins[j]): rk for j, rk in shadow.items() if ctx.excl[j] and rk <= spec["H"]}


def _equity_at(ctx, cad, U, r, capital, kw):
    """Running equity at the close of reset row r, before r's trade: the book simulated with the memberships fixed so far."""
    kk = dict(kw); kk["end"] = ctx.dates[r]; kk["capital"] = capital
    return float(_sim(ctx, _weights(ctx, cad, U), kk)["final"])


def _membership(ctx, cad, spec, capital=None, kw=None):
    """(U mask (T, N) bool, per-reset log). With a capital the UNI-5 gate is applied at each reset with the running equity."""
    key = (spec["N"], spec["H"], spec["age"], spec["reset"], bool(cad["weekly"]))
    if capital is None and key in ctx.cache:
        return ctx.cache[key]
    if capital and kw is None:
        kw = dict(decide=rules.decide_weekly(ctx.dates, 6) if cad["weekly"] else None, band=cad["band"], start=A0, end=A1)
    rows = _reset_rows(ctx, cad["weekly"], spec["reset"])
    U = np.zeros((ctx.T, ctx.N), bool); log = []; inc = {}
    for k, r in enumerate(rows):
        sel, rank = _select(ctx, r, inc, spec["N"], spec["H"], None if k == 0 else spec["age"])
        E, gated = None, []
        if capital:
            E = float(capital) if k == 0 else _equity_at(ctx, cad, U, r, capital, kw)
            sel, gated = _gate(ctx, r, sel, E, cad["tv"])
        prev, inc_prev = set(inc), dict(inc)
        inc = {j: int(ctx.LIFE[r, j]) for j in sel}
        end = rows[k + 1] if k + 1 < len(rows) else ctx.T
        for j, L in inc.items():
            U[r:end, j] = ctx.LIFE[r:end, j] == L
        log.append(dict(date=str(ctx.dates[r]), members=[str(ctx.coins[j]) for j in sel], ranks=[rank[j] for j in sel],
                        entrants=sorted(str(ctx.coins[j]) for j in set(sel) - prev), leavers=sorted(str(ctx.coins[j]) for j in prev - set(sel)),
                        gated_out=[str(ctx.coins[j]) for j in gated], equity=E,
                        excluded_in_top_h=_excluded_in_top_h(ctx, r, inc_prev, spec, None if k == 0 else spec["age"])))
    out = (U, log)
    if capital is None:
        ctx.cache[key] = out
    return out


def _custom(cad, spec=None):
    """custom_sim: the cleaned panel (delisting flatten at the last Q > 0 close); with a capital, the gated membership (I-U1.7)."""
    def run_it(pp, W, kw):
        ctx = _ctx(pp)
        if not kw.get("capital") or spec is None:
            return _sim(ctx, W, kw)
        U, _ = _membership(ctx, cad, spec, capital=kw["capital"], kw=kw)
        return _sim(ctx, _weights(ctx, cad, U), kw)
    return run_it


def _uni1(p, cad, name):
    ctx = _ctx_pool(p, name)
    U, _ = _membership(ctx, cad, SPECS[name])
    return _weights(ctx, cad, U), {"base_coins": list(data.EXANTE24), "custom_sim": _custom(cad, SPECS[name])}


@variant("D-0")
def d0(p, cad):
    """Precondition: the static 24 ex-ante cohort through the D-0 masking on the full pool (same code path as UNI-1)."""
    ctx = _ctx_pool(p, "D-0")
    return _weights(ctx, cad, _static_mask(ctx, data.EXANTE24)), {"base_coins": list(data.EXANTE24), "custom_sim": _custom(cad)}


@variant("UNI-1")
def uni1(p, cad):
    return _uni1(p, cad, "UNI-1")


@variant("UNI-1__age121")
def uni1_age121(p, cad):
    return _uni1(p, cad, "UNI-1__age121")


@variant("UNI-1__quarterly")
def uni1_quarterly(p, cad):
    return _uni1(p, cad, "UNI-1__quarterly")


@variant("UNI-1__N12")
def uni1_n12(p, cad):
    return _uni1(p, cad, "UNI-1__N12")


# ---------------------------------------------------------------- reporting (stdout only)

def load_pool():
    return data.load_binance(coins=json.load(open(POOL_FILE)))


def _kw(ctx, cad, capital=None):
    return dict(decide=rules.decide_weekly(ctx.dates, 6) if cad["weekly"] else None, band=cad["band"], start=A0, end=A1, capital=capital)


def delisting_events(ctx, U, res, W, decide=None):
    """Delistings (I-D0.2) of universe members inside the backtest window: held into the delisting close or not, the coin's P&L
    (fraction of equity, price net of funding, before costs) over the 30 days up to the delisting day and over the whole run, and
    the approximate flatten cost (|weight held| x 7.31 bps; weight held = the target at the last decision row before the delisting
    day drifted with the price, so it ignores band skips)."""
    out = []
    rd = {d: i for i, d in enumerate(res["dates"])}
    cols = res["cols"]
    for t, j in zip(*np.nonzero(ctx.LAST & U)):
        if t >= ctx.T - 1 or not (A0 <= ctx.dates[t] <= A1):
            continue
        c = ctx.coins[j]; d = ctx.dates[t]
        k = cols.index(c) if c in cols else None
        i = rd.get(d)
        held = bool(k is not None and i is not None and res["coin_pnl"][i, k] != 0)
        p30 = float(sum(res["coin_pnl"][rd[x], k] for x in rd if d - dt.timedelta(days=29) <= x <= d)) if k is not None else 0.0
        tot = float(res["coin_pnl"][:, k].sum()) if k is not None else 0.0
        td = t - 1
        while decide is not None and td >= 0 and not decide[td]:
            td -= 1
        w_held = float(W[td, j] * ctx.Cc[t, j] / ctx.Cc[td, j]) if held and td >= 0 and np.isfinite(ctx.Cc[td, j]) else 0.0
        out.append(dict(coin=c, date=str(d), close=float(ctx.Cc[t, j]), held=held, w_held=w_held, pnl_30d=p30, pnl_total=tot,
                        flatten_cost=abs(w_held) * sim.COST_BPS / 1e4))
    return out


def _ev_line(e):
    return (f"   delisting hit: {e['coin']} {e['date']} close {e['close']:.4g} held {e['held']} w {e['w_held']:.4f} "
            f"pnl30d {e['pnl_30d']:+.4%} total {e['pnl_total']:+.4%} flatten cost ~{e['flatten_cost']:.5%}")


def _stats_line(r, b, wa=None, wb=None):
    s, bs = sim.stats(r, wa, wb), sim.stats(b, wa, wb)
    d = np.array(r["dates"]); m = np.ones(len(d), bool)
    if wa: m &= d >= wa
    if wb: m &= d <= wb
    boot = sim.block_bootstrap_diff(r["rets"][m], b["rets"][m])
    return s, bs, boot


def check():
    """D-0 gate (I-D0.6), static-mask equivalence inside the pool, and the truncation look-ahead test on UNI-1's W."""
    P = load_pool()
    sub = P.sub(data.EXANTE24)
    ctxP = _ctx(P); ctx24 = _ctx(sub)
    ok = True
    print(f"pool: {len(P.coins)} symbols, {len(P.dates)} rows {P.dates[0]}..{P.dates[-1]}; zero-volume rows removed: "
          f"{int((np.isfinite(P.C) & ~ctxP.pos).sum())}; delisted lives (last Q>0 before {P.dates[-1]}): {int(ctxP.LAST[:-1].sum())}; "
          f"relisted symbols (life id > 1): {sorted(c for j, c in enumerate(ctxP.coins) if ctxP.LIFE[:, j].max() > 1)}")
    print(f"LUNA last candidate close {P.dates[np.flatnonzero(ctxP.pos[:, ctxP.coins.index('LUNA')])[-1]]} at "
          f"{ctxP.Cc[np.flatnonzero(ctxP.pos[:, ctxP.coins.index('LUNA')])[-1], ctxP.coins.index('LUNA')]:.4f}")
    rng = {"daily": (0.845, 0.865), "weekly": (0.805, 0.825)}
    for cad in (DAILY, WEEKLY):
        kw = _kw(ctx24, cad)
        raw = sim.simulate(sub, rules.baseline_weights(sub.C, tv=cad["tv"], max_gross=cad["max_gross"]), **kw)
        U24 = _static_mask(ctx24, data.EXANTE24)
        W24 = _weights(ctx24, cad, U24)
        a = _sim(ctx24, W24, kw)
        bpool = _sim(ctxP, _weights(ctxP, cad, _static_mask(ctxP, data.EXANTE24)), _kw(ctxP, cad))
        s_raw, s_a, s_b = (sim.stats(x)["sharpe"] for x in (raw, a, bpool))
        d1 = float(np.max(np.abs(a["rets"] - raw["rets"]))); d2 = float(np.max(np.abs(bpool["rets"] - a["rets"])))
        lo, hi = rng[cad["name"]]
        good = lo <= s_a <= hi and lo <= s_b <= hi and d1 < 1e-12 and d2 < 1e-12
        ok &= good
        ev = delisting_events(ctx24, U24, a, W24, kw["decide"])
        print(f"D-0 gate {cad['name']:6s}: cohort-through-D0 {s_a:.4f}, inside-pool {s_b:.4f}, harness raw static-24 {s_raw:.4f}; "
              f"max|diff| {d1:.1e} / {d2:.1e}; MDD {sim.stats(a)['mdd']:.1%}; target [{lo:.3f},{hi:.3f}] -> {'PASS' if good else 'FAIL'}")
        for e in ev:
            print(_ev_line(e))
    # truncation test: W[t] from the panel cut at t equals W[t] from the full panel
    full = {(cad["name"], name): _uni1(P, cad, name)[0] for cad in (DAILY, WEEKLY) for name in ("UNI-1", "UNI-1__quarterly")}
    look_ok = True
    for d in (dt.date(2021, 1, 3), dt.date(2022, 11, 14), dt.date(2025, 5, 21), dt.date(2026, 7, 5)):
        t = P.idx[d]
        Pt = data.Panel(P.dates[:t + 1], list(P.coins), P.O[:t + 1], P.H[:t + 1], P.L[:t + 1], P.C[:t + 1], P.V[:t + 1], P.F[:t + 1], P.Q[:t + 1])
        for cad in (DAILY, WEEKLY):
            for name in ("UNI-1", "UNI-1__quarterly"):
                Wt, _ = _uni1(Pt, cad, name)
                Wf = full[(cad["name"], name)]
                same = np.array_equal(Wt[t], Wf[t]) and np.array_equal(Wt[:t + 1], Wf[:t + 1])
                look_ok &= same
                if not same:
                    print(f"LOOK-AHEAD {name} {cad['name']} {d}: max diff {np.max(np.abs(Wt[:t + 1] - Wf[:t + 1])):.3e}")
    print("truncation test (W rows <= t identical when the panel is cut at t; 4 cut dates x 2 cadences x 2 cells):", "PASS" if look_ok else "FAIL")
    return ok and look_ok


def report(cells, cads, capitals="default"):
    P = load_pool(); ctx = _ctx(P)
    nofund = [c for j, c in enumerate(ctx.coins) if ctx.pos[:, j].any() and not (P.F[:, j] != 0).any()]
    print(f"funding flagged (no fundingRate rows, funding = 0): {len(nofund)} symbols")
    sub = P.sub(data.EXANTE24); ctx24 = _ctx(sub)
    for name in cells:
        spec = SPECS[name]
        for cad in cads:
            U, log = _membership(ctx, cad, spec)
            kw = _kw(ctx, cad)
            Wu = _weights(ctx, cad, U)
            r = _sim(ctx, Wu, kw)
            b = _sim(ctx24, _weights(ctx24, cad, _static_mask(ctx24, data.EXANTE24)), _kw(ctx24, cad))
            print(f"\n== {name} {cad['name']} (N {spec['N']}, H {spec['H']}, age {spec['age']}, {spec['reset']}) unrounded vs static 24")
            for w, (wa, wb) in WINDOWS.items():
                s, bs, boot = _stats_line(r, b, wa, wb)
                print(f"   {w:4s} Sharpe {s['sharpe']:.3f} vs {bs['sharpe']:.3f} delta {boot[0]:+.3f} [{boot[1]:+.2f},{boot[2]:+.2f}] P<=0 {boot[3]:.2f} "
                      f"MDD {s['mdd']:.1%} vs {bs['mdd']:.1%} CAGR {s['cagr']:+.1%} vs {bs['cagr']:+.1%} turn {s['turnover']:.1f}x")
            nchg = 0
            for e in log:
                nchg += len(e["entrants"]) if e is not log[0] else 0
                idx_note = f" | EXCLUDED but in top-{spec['H']}: {e['excluded_in_top_h']}" if e["excluded_in_top_h"] else ""
                print(f"   reset {e['date']}: {' '.join(f'{m}({rk})' for m, rk in zip(e['members'], e['ranks']))} | +{e['entrants']} -{e['leavers']}{idx_note}")
            print(f"   names changed after the start: {nchg} entrants over {len(log) - 1} resets")
            ev = delisting_events(ctx, U, r, Wu, kw["decide"])
            print(f"   delisting events hit: {len(ev)} (held into the delisting close: {sum(e['held'] for e in ev)}); their P&L total "
                  f"{sum(e['pnl_total'] for e in ev):+.4%} of equity, last 30 days {sum(e['pnl_30d'] for e in ev):+.4%}")
            for e in ev:
                print(_ev_line(e))
            caps = CAPITALS[name] if capitals == "default" else (() if capitals == "none" else tuple(float(x) for x in capitals.split(",")))
            for cap in caps:
                kc = _kw(ctx, cad, cap)
                Ug, lg = _membership(ctx, cad, spec, capital=cap, kw=kc)
                rc = _sim(ctx, _weights(ctx, cad, Ug), kc)
                bc = _sim(ctx24, _weights(ctx24, cad, _static_mask(ctx24, data.EXANTE24)), _kw(ctx24, cad, cap))
                yrs = len(rc["rets"]) / 365
                print(f"   -- whole contracts ${cap:,.0f} (cv = CVALS else $25/first close), vs the static 24 rounded the same way")
                for w in ("full", "post"):
                    s, bs, boot = _stats_line(rc, bc, *WINDOWS[w])
                    print(f"      {w:4s} Sharpe {s['sharpe']:.3f} vs {bs['sharpe']:.3f} delta {boot[0]:+.3f} [{boot[1]:+.2f},{boot[2]:+.2f}] "
                          f"MDD {s['mdd']:.1%} vs {bs['mdd']:.1%} gross {s['gross']:.3f} vs {bs['gross']:.3f}")
                print(f"      orders/yr {rc['orders'] / yrs:.0f} vs {bc['orders'] / yrs:.0f}; fees/yr {rc['fees'] / yrs:.2%} vs {bc['fees'] / yrs:.2%}")
                for e in lg:
                    print(f"      reset {e['date']} E ${e['equity']:,.0f}: {' '.join(e['members'])} | gated out {e['gated_out']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "report"])
    ap.add_argument("--cells", default=",".join(SPECS)); ap.add_argument("--cadences", default="daily,weekly")
    ap.add_argument("--capitals", default="default")
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(0 if check() else 1)
    report(a.cells.split(","), [{"daily": DAILY, "weekly": WEEKLY}[c] for c in a.cadences.split(",")], a.capitals)
