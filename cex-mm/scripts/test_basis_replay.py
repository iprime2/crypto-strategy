#!/usr/bin/env python3
"""Tests for basis_replay.py (stdlib only, synthetic data built here; fast).

    cd cex-mm/scripts && python3 -m unittest -v test_basis_replay

The real-data tests need the PR D data pack (the 15 Oct 4-symbol shadow's MM_METRICS log and config,
shadow_now_metrics.log / shadow_now_config.txt, and the 13 Oct anchored ADA shadow's shadow_13oct_ada_metrics.log;
not in the repo) and run only when BASIS_REPLAY_DATA names its directory; otherwise they are skipped with the
expected files in the reason.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basis_replay as br  # noqa: E402

TICK = 1e-5
LOOP_MS = 400.0
DATA = os.environ.get("BASIS_REPLAY_DATA")  # directory of the PR D data pack; unset = skip the real-data tests
DATA_FILES = ("shadow_now_metrics.log", "shadow_now_config.txt", "shadow_13oct_ada_metrics.log")


def settings(**kw) -> br.Settings:
    st = br.Settings()
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def make_rows(n: int, spread_bps: float = 12.0, basis_bps: float = -8.0, mid0: float = 0.24, seed: int = 7,
              vol_bps: float = 0.0, depth: bool = True, depth_qty: float = 10_000.0, inner: float = 0.0,
              start_ms: float = 1_700_000_000_000.0, spread_fn=None, dts: bool = False,
              size_jitter: float = 0.0) -> list[br.Row]:
    """Synthetic MM_METRICS rows one loop apart: a Delta book of `spread_bps` around a random-walk mid, Binance
    at mid / (1 + basis). With `depth`, a depth mid equal to the L1 mid and inner sizes `inner` per side; with
    `dts`, a depth_ts_us (= the row's clock in us) so a recorded ob_l2 frame with that `ts` joins the row.
    `size_jitter` varies the L1 sizes (50 000 +/- that), so the OFI term is not zero."""
    rng = random.Random(seed)
    rows = []
    mid = mid0
    for i in range(n):
        if vol_bps:
            mid *= 1.0 + rng.gauss(0.0, vol_bps) / 1e4
        sp = spread_fn(i) if spread_fn else spread_bps
        half = mid * sp / 2e4
        bb = br.floor_tick(mid - half, TICK)
        ba = br.ceil_tick(mid + half, TICK)
        m = (bb + ba) / 2
        bn = m / (1.0 + basis_bps / 1e4)
        bq = 50_000.0 + (rng.uniform(-size_jitter, size_jitter) if size_jitter else 0.0)
        aq = 50_000.0 + (rng.uniform(-size_jitter, size_jitter) if size_jitter else 0.0)
        rows.append(br.Row(
            ts=start_ms + i * LOOP_MS, bb=bb, ba=ba, bq=bq, aq=aq, bn=bn, bn_age=100.0,
            fair=m, fair_delta=m, basis=None, anchored=None, bid=bb, ask=ba, place_bid=True, place_ask=True,
            regime=0, ofi=None,
            depth_mid=m if depth else None, depth_age=300.0 if depth else None, depth_qty=depth_qty if depth else None,
            dbp=bb if depth else None, dap=ba if depth else None, dbi=inner if depth else None, dai=inner if depth else None,
            dbip=None, daip=None, dts=int((start_ms + i * LOOP_MS) * 1000) if (depth and dts) else None, basis_src=None,
        ))
    return rows


def row_json(r: br.Row, symbol: str = "ADAUSDT") -> str:
    m = {
        "symbol": symbol, "fair": r.fair, "reservation": r.fair, "bid": r.bid, "ask": r.ask, "spread_bps": 10.0,
        "vol_bps": 1.0, "inventory": 0.0, "effective_kappa": 1.5, "markout_extra_bid_bps": 0.0,
        "markout_extra_ask_bps": 0.0, "regime_level": r.regime, "ofi": 0.0, "ofi_beta": 0.01, "alpha_mu_bps": 0.0,
        "snipe_rate": 0.0, "place_bid": r.place_bid, "place_ask": r.place_ask, "binance_mid": r.bn,
        "venue_mid": r.mid, "rolling_adverse_bps": 0.0, "ts_ms": int(r.ts), "book_bid": r.bb, "book_ask": r.ba,
        "book_bid_qty": r.bq, "book_ask_qty": r.aq, "book_age_ms": 0, "fair_delta": r.fair_delta,
        "anchored": False, "binance_age_ms": int(r.bn_age or 0),
    }
    if r.basis is not None:
        m["basis_bps"] = r.basis
    if r.depth_mid is not None:
        m.update(depth_mid=r.depth_mid, depth_age_ms=int(r.depth_age), depth_qty=r.depth_qty, depth_bid_px=r.dbp,
                 depth_ask_px=r.dap, depth_bid_inner=r.dbi, depth_ask_inner=r.dai)
        if r.dbip is not None:
            m["depth_bid_inner_px"] = r.dbip
        if r.daip is not None:
            m["depth_ask_inner_px"] = r.daip
        if r.dts is not None:
            m["depth_ts_us"] = r.dts
    return f"2026-01-01T00:00:00.000000Z  INFO MM_METRICS: {json.dumps(m)}\n"


def write_log(rows: list[br.Row], path: str) -> None:
    with open(path, "w") as f:
        for r in rows:
            f.write(row_json(r))


def write_book(rows: list[br.Row], path: str, ladder, symbol: str = "ADAUSD", every: int = 1) -> None:
    """A recorded ob_l2 file: one frame per `every` rows whose venue `ts` is the row's depth_ts_us, with
    `ladder(r)` -> (bids, asks) as [[price, size], ...] best first."""
    with open(path, "w") as f:
        for i, r in enumerate(rows):
            if i % every:
                continue
            b, a = ladder(r)
            msg = {"type": "ob_l2", "sy": symbol, "ts": r.dts, "lts": r.dts, "b": b, "a": a}
            f.write(json.dumps({"recv_us": r.dts, "msg": msg}) + "\n")


def _no_nan(c):
    raise ValueError(f"non-JSON constant {c}")


def read_json(path: str) -> dict:
    """Strict: a bare NaN / Infinity token fails the test."""
    with open(path) as f:
        return json.loads(f.read(), parse_constant=_no_nan)


def run_main(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = br.main(argv)
    return code, buf.getvalue()


class BasisEmaPort(unittest.TestCase):
    """The Rust unit tests of mm_core::fair::BasisEma, rerun on the port."""

    def test_starts_at_the_first_sample_and_moves_halfway_per_half_life(self):
        b = br.BasisEma(120.0)
        self.assertIsNone(b.value)
        self.assertEqual(b.warm_sec(5.0), 0.0)
        self.assertAlmostEqual(b.update(100.0, 0.999, 1.0), -10.0, places=9)
        self.assertAlmostEqual(b.update(220.0, 0.9996, 1.0), -7.0, places=9)
        self.assertAlmostEqual(b.warm_sec(230.0), 130.0)
        self.assertEqual(b.last_update(), 220.0)

    def test_warm_up_is_the_mean_not_the_first_sample(self):
        b = br.BasisEma(120.0)
        b.update(0.0, 1 - 17.5e-4, 1.0)
        for i in range(1, 151):
            b.update(i * 0.4, 1 - 10e-4, 1.0)
        self.assertLess(abs(b.value + 10.0), 0.1)

    def test_step_cap_and_clamp_stop_one_sample_resetting_it(self):
        b = br.BasisEma(120.0, 0.8, 5.0)
        for i in range(1000):
            b.update(i * 0.4, 1 - 10e-4, 1.0)
        b.update(760.0, 1 - 17.5e-4, 1.0)
        self.assertLess(abs(b.value + 10.0), 0.05)
        b.update(760.4, 1 + 40e-4, 1.0)
        self.assertLess(abs(b.value + 10.0), 0.05)

    def test_bad_inputs_and_clock_steps_back(self):
        b = br.BasisEma(120.0)
        self.assertIsNone(b.update(1.0, 0.0, 1.0))
        self.assertIsNone(b.update(1.0, 1.0, float("nan")))
        b.update(10.0, 0.999, 1.0)
        self.assertAlmostEqual(b.update(5.0, 0.9996, 1.0), -10.0, places=9)


class QuoteMath(unittest.TestCase):
    def test_fixed_quotes_round_away_and_stay_inside_the_book(self):
        bid, ask = br.fixed_quotes(0.25, 1e-5, 5.0, 1.0, 0.2497, 0.2503)
        self.assertEqual((bid, ask), (0.24987, 0.25013))
        # A wide quote is pulled one tick inside the book it was computed from.
        bid, ask = br.fixed_quotes(0.25, 1e-5, 5.0, 1.0, 0.24990, 0.25010)
        self.assertEqual((bid, ask), (0.24987, 0.25013))
        bid, ask = br.fixed_quotes(0.25, 1e-5, 50.0, 1.0, 0.24990, 0.25010)
        self.assertEqual((bid, ask), (0.24875, 0.25125))
        bid, ask = br.fixed_quotes(0.25, 1e-5, 0.1, 1.0, 0.24990, 0.25010)
        self.assertEqual((bid, ask), (0.24999, 0.25001))

    def test_resolve_fair_matches_the_rust_cases(self):
        base = br.resolve_fair(2700.0, 2700.0, None, 0.0, 0.8, 0.0, 15.0, 0.0)
        self.assertAlmostEqual(br.resolve_fair(2700.0, 2700.0, None, 0.0, 0.8, 5.0, 15.0, 0.0), base * (1 + 4e-4), places=9)
        self.assertAlmostEqual(br.resolve_fair(2700.0, 2700.0, None, 0.0, 0.8, 50.0, 15.0, 0.0), base * (1 + 15e-4), places=9)
        self.assertAlmostEqual(br.resolve_fair(2700.0, 2700.0, 2710.0, 1.0, 0.8, 5.0, 15.0, 0.0), 2710.0, places=9)
        self.assertAlmostEqual(br.resolve_fair(2700.0, 2700.0, 2710.0, 0.5, 0.8, 5.0, 15.0, 0.0), 2705.0 * (1 + 0.5 * 4e-4), places=9)
        self.assertEqual(br.resolve_fair(2700.0, 2700.0, 0.0, 1.0, 0.8, 0.0, 15.0, 0.0), base)

    def test_move_bps(self):
        hist = [(5.0, 2690.0), (7.0, 2700.0), (8.5, 2705.0), (10.0, 2701.35)]
        self.assertAlmostEqual(br.move_bps(hist, 10.0, 3.0), 5.0, places=9)
        self.assertEqual(br.move_bps([(9.0, 2700.0), (10.0, 2701.0)], 10.0, 3.0), 0.0)
        self.assertEqual(br.move_bps([], 10.0, 3.0), 0.0)

    def test_ofi_tracker_accumulates_bid_pressure_and_clamps(self):
        t = br.OfiTracker(16)
        t.on_book(100.0, 1.0, 101.0, 1.0)
        t.on_book(100.0, 3.0, 101.0, 1.0)
        self.assertGreater(t.sum_ofi, 0.0)
        self.assertGreater(t.drift_bps(0.01, 4.0), 0.0)
        self.assertEqual(t.drift_bps(1e9, 1.0), 50.0)
        self.assertEqual(t.drift_bps(0.01, 0.0), 0.0)


class DepthImmunity(unittest.TestCase):
    """mm_core::depth tests on the port, then our order added to a synthetic ladder."""

    ADA_BIDS = [0.23207, 2.0, 0.23206, 1.0, 0.23201, 2.0, 0.23200, 47_081.0, 0.23180, 63_846.0]

    def test_skips_dust_and_lands_on_the_ladder(self):
        sp, why = br.side_depth_price(self.ADA_BIDS, 8_600.0, True)
        self.assertIsNone(why)
        self.assertEqual((sp.price, sp.level, sp.inner, sp.inner_px), (0.23200, 3, 5.0, 0.23201))
        self.assertEqual(br.side_depth_price([], 1.0, True), (None, "empty_side"))
        self.assertEqual(br.side_depth_price(self.ADA_BIDS, 1e9, True), (None, "thin"))
        self.assertEqual(br.side_depth_price([1.0, 1.0, 2.0, 1.0], 5.0, True), (None, "invalid"))

    def test_our_quote_inside_the_spread_does_not_move_the_depth_price(self):
        with_us = br.insert_order(self.ADA_BIDS, 0.23229, 200.0, True)
        a, _ = br.side_depth_price(with_us, 8_600.0, True)
        b, _ = br.side_depth_price(self.ADA_BIDS, 8_600.0, True)
        self.assertEqual(a.price, b.price)
        self.assertEqual(a.inner, 205.0)
        # Joining an existing level adds to it.
        joined = br.insert_order(self.ADA_BIDS, 0.23200, 200.0, True)
        self.assertEqual(list(joined[6:8]), [0.23200, 47_281.0])

    def test_the_pivot_band_is_the_only_place_our_order_moves_it(self):
        x, q = 2_000.0, 200.0
        for others_inside in (1_500.0, 1_799.0, 1_800.0, 1_999.0, 2_000.0):
            others = [0.23210, others_inside, 0.23200, 47_081.0]
            clean, _ = br.side_depth_price(others, x, True)
            live, _ = br.side_depth_price(br.insert_order(others, 0.23215, q, True), x, True)
            in_band = x - q <= clean.inner < x
            self.assertEqual(live.price != clean.price, in_band, others_inside)
            if in_band:
                self.assertEqual(live.price, clean.inner_px)

    def test_the_level_cap_turns_the_side_thin(self):
        others = []
        for i in range(15):
            others += [1.0 - 0.0001 * i, 1_000.0 if i == 14 else 100.0]
        sp, _ = br.side_depth_price(others, 2_000.0, True)
        self.assertEqual(sp.level, 14)
        self.assertEqual(br.side_depth_price(br.insert_order(others, 1.0005, 200.0, True), 2_000.0, True), (None, "thin"))


class PivotCounting(unittest.TestCase):
    def test_pivot_share_counts_rows_whose_clean_inner_size_is_in_the_band(self):
        rows = make_rows(400, inner=0.0)
        for i in range(100, 110):
            rows[i].dbi = 9_900.0  # in [X - q, X) for q = 200
        for i in range(200, 205):
            rows[i].dai = 9_799.0  # just below the band
        rows[300].dai = 9_999.0
        rep = br.replay(rows, settings(), TICK, 200.0, "shadow", "book")
        self.assertEqual(sum(rep.pivot), 11)
        self.assertEqual(sum(br.replay(rows, settings(), TICK, 50.0, "shadow", "book").pivot), 1)


class GateStarvation(unittest.TestCase):
    """A 12 bps Delta spread against our 10 bps quote width: live, our quotes are the touch, so the book-source
    basis starves; the depth source does not."""

    def test_book_source_starves_live_and_depth_source_does_not(self):
        rows = make_rows(1500, spread_bps=12.0)
        st = settings()
        shadow = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        live_book = br.replay(rows, st, TICK, 200.0, "live", "book")
        live_depth = br.replay(rows, st, TICK, 200.0, "live", "depth")
        self.assertEqual(sum(shadow.updated), 1500)
        self.assertLess(sum(live_book.updated), 5)  # the first loops, before a quote rests
        self.assertGreater(sum(live_book.own_touch), 1490)
        self.assertEqual(sum(live_depth.updated), 1500)
        # 1500 loops = 600 s: the starved basis is older than MM_BASIS_MAX_AGE_SEC, so the anchor is off.
        self.assertFalse(any(live_book.anchored[-100:]))
        self.assertTrue(all(live_depth.anchored[-100:]))
        self.assertTrue(all(shadow.anchored[-100:]))
        self.assertGreater(live_book.ladder_fallback, 0)  # no book file: logged fields priced the depth

    def test_depth_source_max_age_is_30_s_and_a_depth_gap_turns_the_anchor_off(self):
        # PR C runner.rs: basis_max_age_default = 300 s (book) / 30 s (depth), MM_BASIS_MAX_AGE_SEC overrides.
        self.assertEqual(br.Settings.from_config({}, "ADAUSDT", source="book").max_age_sec, 300.0)
        self.assertEqual(br.Settings.from_config({}, "ADAUSDT", source="depth").max_age_sec, 30.0)
        self.assertEqual(br.Settings.from_config({"MM_BASIS_MAX_AGE_SEC": "45"}, "ADAUSDT", source="depth").max_age_sec, 45.0)
        # A 60 s depth outage (rows 600..749 stale) on a 4 bps book (our quotes rest outside the touch, so the
        # book source keeps sampling): the depth anchor drops 30 s in and is back after the 60 s warm-up.
        rows = make_rows(1500, spread_bps=4.0)
        for r in rows[600:750]:
            r.depth_age = 90_000.0
        cfg = {"MM_FAIR_ANCHOR_WEIGHT": "1"}
        depth = br.replay(rows, br.Settings.from_config(cfg, "ADAUSDT", source="depth"), TICK, 200.0, "live", "depth")
        book = br.replay(rows, br.Settings.from_config(cfg, "ADAUSDT", source="book"), TICK, 200.0, "live", "book")
        self.assertTrue(all(depth.anchored[500:600]))
        self.assertTrue(all(depth.anchored[600:674]))  # 29.6 s into the gap: still within 30 s
        self.assertFalse(any(depth.anchored[676:750]))  # past 30 s: off until the feed returns
        self.assertFalse(any(depth.anchored[750:899]))  # ...and then the 60 s warm-up
        self.assertTrue(all(depth.anchored[901:]))
        self.assertTrue(all(book.anchored[500:]))  # the book source's 300 s max age is untouched
        # Under 300 s the same gap on a depth-source replay with the book default keeps the anchor on.
        loose = br.replay(rows, br.Settings.from_config(cfg, "ADAUSDT", source="book"), TICK, 200.0, "live", "depth")
        self.assertTrue(all(loose.anchored[600:750]))

    def test_latency_delays_the_touch_by_that_many_loops(self):
        rows = make_rows(100, spread_bps=12.0)
        for lat in (0, 1, 2):
            rep = br.replay(rows, settings(), TICK, 200.0, "live", "book", latency=lat)
            self.assertEqual(rep.own_touch.index(True), 1 + lat)

    def test_the_live_fair_without_ofi_is_self_referential_free_when_anchored(self):
        rows = make_rows(1500, spread_bps=12.0, vol_bps=1.0)
        st = settings()
        clean = br.replay(rows, st, TICK, 200.0, "shadow", "depth")
        live = br.replay(rows, st, TICK, 200.0, "live", "depth")
        d = [abs(live.fair[i] / clean.fair[i] - 1) * 1e4 for i in range(300, 1500)]
        self.assertLess(max(d), 1e-9)
        # As coded today the OFI term on our own L1 sizes leaks into the anchored fair.
        da = [abs(live.fair_asis[i] / clean.fair_asis[i] - 1) * 1e4 for i in range(300, 1500)]
        self.assertGreater(max(da), 0.5)


class OracleAndBlockCi(unittest.TestCase):
    def _rows(self):
        return make_rows(3000, spread_bps=12.0, vol_bps=3.0, seed=3)

    def test_oracle_passes_g4_and_g5_at_the_convergence_horizons(self):
        rows = self._rows()
        st = settings()
        ts = [r.ts for r in rows]
        mid = [r.mid for r in rows]
        blocks = [int((t - ts[0]) // br.BLOCK_MS) for t in ts]
        fresh = [True] * len(rows)
        old = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        old_v = br.Variant("old", old.fair_old, *br.quote_series(rows, old.fair_old, st, TICK))
        fut = br.future_index(ts, 60)
        of = [mid[j] if j >= 0 else float("nan") for j in fut]
        ov = br.Variant("oracle", of, *br.quote_series(rows, of, st, TICK))
        boot = br.BlockBoot(blocks, 200, 1)
        sc = br.score_variant(ov, old_v, ts, mid, fresh, boot, blocks)
        self.assertAlmostEqual(sc["slope"][60]["new"], 1.0, places=6)
        self.assertGreater(sc["slope"][60]["ci"][0], 0.0)
        e60 = sc["expo"][60]
        self.assertLess(e60["ci"][1], 1.0)
        self.assertLess(e60["diff_bid"], 3.0)
        self.assertLess(e60["diff_ask"], 3.0)
        self.assertEqual(e60["avg"], 0.0)  # it quotes 5 bps clear of the mid it knows

    def test_block_bootstrap_is_deterministic_and_brackets_the_mean(self):
        rng = random.Random(5)
        blocks = [i // 50 for i in range(2000)]
        vals = [(2.0 + rng.gauss(0, 1), 1.0) for _ in range(2000)]
        a = br.BlockBoot(blocks, 300, 1).ci(vals, lambda s: s[0] / s[1])
        b = br.BlockBoot(blocks, 300, 1).ci(vals, lambda s: s[0] / s[1])
        self.assertEqual(a, b)
        self.assertLess(a[0], 2.0)
        self.assertGreater(a[1], 2.0)
        self.assertGreater(a[0], 1.5)
        self.assertNotEqual(a, br.BlockBoot(blocks, 300, 2).ci(vals, lambda s: s[0] / s[1]))
        lo, hi = br.BlockBoot([0] * 10, 50, 1).ci([(1.0, 1.0)] * 10, lambda s: s[0])
        self.assertTrue(math.isnan(lo) and math.isnan(hi))  # one block: no CI


class AgreementUsesTheAsCodedFair(unittest.TestCase):
    def test_quotes_and_side_flags_are_checked_against_the_fair_the_bot_quoted(self):
        # Jittered L1 sizes give an OFI term, so the as-coded fair (OFI in while anchored) and the PR C fair
        # under test differ; a Binance step at row 700 makes the fair-jump flags differ too.
        rows = make_rows(1200, vol_bps=1.0, seed=21, size_jitter=20_000.0)
        for r in rows[700:]:
            r.bn *= 1 + 13e-4
        st = settings()
        rep = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        under_test = [br.fixed_quotes(f, TICK, st.half_bps, 1.0, r.bb, r.ba) for f, r in zip(rep.fair, rows)]
        self.assertGreater(sum(1 for i in range(1200) if rep.pbid_asis[i] != under_test[i][0]), 100)
        self.assertNotEqual(rep.place_bid_asis[700:], rep.place_bid[700:])
        # A log written from the as-coded fair (what the bot logs as bid / ask / place_*) is reproduced exactly.
        for i, r in enumerate(rows):
            r.bid, r.ask = rep.pbid_asis[i], rep.pask_asis[i]
            r.place_bid, r.place_ask = rep.place_bid_asis[i], rep.place_ask_asis[i]
        agr = br.agreement(rows, rep)
        self.assertEqual((agr["bid_exact_pct"], agr["ask_exact_pct"], agr["place_flags_pct"]), (100.0, 100.0, 100.0))
        self.assertEqual(agr["quote_rows"], 1200)
        # The same log judged against the fair under test would not be: the check must read the as-coded one.
        for i, r in enumerate(rows):
            r.bid, r.ask = under_test[i]
            r.place_bid, r.place_ask = rep.place_bid[i], rep.place_ask[i]
        agr = br.agreement(rows, rep)
        self.assertLess(agr["bid_exact_pct"], 95.0)
        self.assertLess(agr["place_flags_pct"], 100.0)


    def test_a_pr_c_log_is_checked_against_the_fair_without_the_ofi_term(self):
        # A PR C build (its log carries basis_src) quotes the anchored fair without the OFI term. Its own bid /
        # ask / side flags must be reproduced, while the OFI-in fair stays available for G3's comparison.
        rows = make_rows(1200, vol_bps=1.0, seed=21, size_jitter=20_000.0)
        for r in rows:
            r.basis_src = "book"
        st = settings()
        rep = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        self.assertEqual(rep.fair_asis, rep.fair)
        self.assertGreater(sum(1 for a, b in zip(rep.fair_ofi, rep.fair) if a != b), 100)
        for i, r in enumerate(rows):
            r.bid, r.ask = rep.pbid_asis[i], rep.pask_asis[i]
            r.place_bid, r.place_ask = rep.place_bid_asis[i], rep.place_ask_asis[i]
        agr = br.agreement(rows, rep)
        self.assertEqual((agr["bid_exact_pct"], agr["ask_exact_pct"], agr["place_flags_pct"]), (100.0, 100.0, 100.0))
        # Without basis_src (a pre-PR C log) the as-coded fair keeps the OFI term while anchored.
        for r in rows:
            r.basis_src = None
        old = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        self.assertEqual(old.fair_asis, old.fair_ofi)

class ParitySynthetic(unittest.TestCase):
    """Tight spread for the first 120 s (our quotes sit outside the touch: the basis samples), then a 12 bps
    spread (our quotes are the touch: starved). Known answer: updated = the tight rows, anchored = every row
    from 60 s on (the basis is never older than 300 s)."""

    def _rows(self):
        return make_rows(1000, spread_fn=lambda i: 4.0 if i < 300 else 12.0)

    def test_parity_numbers_match_the_construction(self):
        rows = self._rows()
        par = br.parity_replay(rows, TICK)
        self.assertEqual(par["n"], 1000)
        # The first wide row still samples (the resting quotes were set on the last tight row, outside the
        # new touch), after that none.
        self.assertAlmostEqual(par["updated_pct"], 30.1, delta=0.2)
        self.assertAlmostEqual(par["anchored_pct"], 85.0, delta=0.2)

    def test_the_full_live_replay_agrees_with_parity_on_this_case(self):
        rows = self._rows()
        rep = br.replay(rows, settings(), TICK, 200.0, "live", "book")
        self.assertAlmostEqual(100.0 * sum(rep.updated) / 1000, 30.1, delta=0.3)
        self.assertAlmostEqual(100.0 * sum(rep.anchored) / 1000, 85.0, delta=0.3)


class Cli(unittest.TestCase):
    def test_thin_data_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(make_rows(200), path)
            code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT"])
            self.assertEqual(code, 2)
            self.assertIn("thin data", out)
            code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT", "--min-rows", "10", "--min-hours", "0.01", "--boot", "20"])
            self.assertEqual(code, 1, out)  # 80 s of rows: the 60 s warm-up alone fails G1 (and no CI is defined)
            self.assertIn("Verdict: PROVISIONAL FAIL (G1)", out)
            code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT", "--config", os.path.join(d, "typo.txt")])
            self.assertEqual(code, 2)  # an explicit --config must exist (silently empty would judge the old fair)
            self.assertIn("input not found", out)
        code, _ = run_main(["--metrics", "/nonexistent/dry-run.log"])
        self.assertEqual(code, 2)

    def test_help_lists_the_exit_codes_and_the_defaults(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            br.main(["--help"])
        out = buf.getvalue()
        self.assertIn("Exit code: 0 every deciding gate (G1-G4) evaluated and passed; 1 a deciding gate fails; 2 thin data", out)
        for text in ("(default: shadow)", "(default: 0,1,2)", "(default: 400.0)", "(default: 1.0)", "(default: 500)",
                     "(default: 1000)", "(default: 1)"):
            self.assertIn(text, out)
        self.assertNotIn("(default: None)", out)

    def test_exclude_removes_the_window_from_every_statistic(self):
        rows = make_rows(3000, vol_bps=1.0)
        # A dislocation in the middle: Binance 100 bps away for 200 rows.
        for r in rows[1000:1200]:
            r.bn *= 1.01
        t0, t1 = rows[1000].ts, rows[1200].ts
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(rows, path)
            out_json = os.path.join(d, "out.json")
            common = ["--metrics", path, "--symbol", "ADAUSDT", "--min-hours", "0.01", "--min-rows", "10", "--boot", "20", "--json", out_json]
            run_main(common)
            full = read_json(out_json)["results"][0]
            run_main(common + ["--exclude", str(int(t0)), str(int(t1))])
            cut = read_json(out_json)["results"][0]
            self.assertEqual(full["rows"], 3000)
            self.assertEqual(cut["rows"], 2800)
            # The spike cannot reach the EMA comparison once its rows are gone (the clamp still lets it in
            # slowly without the exclusion).
            self.assertLess(cut["G2"]["p90_bps"], 1e-9)
            # ISO form of the same window gives the same cut.
            run_main(common + ["--exclude", br.iso(t0), br.iso(t1)])
            self.assertEqual(read_json(out_json)["results"][0]["rows"], 2800)

    def test_from_to_and_time_parsing(self):
        self.assertEqual(br.parse_time("1700000000000"), 1.7e12)
        self.assertEqual(br.parse_time("2023-11-14T22:13:20Z"), 1.7e12)
        self.assertEqual(br.parse_time("2023-11-14T22:13:20+00:00"), 1.7e12)
        self.assertEqual(br.parse_time("2023-11-14 22:13:20"), 1.7e12)
        rows = make_rows(50)
        cut = br.apply_window(rows, rows[10].ts, rows[20].ts, [(rows[12].ts, rows[14].ts)])
        self.assertEqual(len(cut), 8)

    def test_seed_is_inferred_from_the_logged_basis(self):
        # A bot that started 30 samples before the log: the logged basis follows its EMA, the replay seeds from it.
        rows = make_rows(800, vol_bps=2.0, seed=11)
        ema = br.BasisEma(120.0, 0.8, 5.0)
        for i in range(30):
            ema.update(rows[0].ts / 1000 - (30 - i) * 0.4, rows[0].mid * (1 + 1e-4), rows[0].bn)
        for i, r in enumerate(rows):
            ema.update(r.ts / 1000, r.mid, r.bn)
            r.basis = ema.value
            r.anchored = ema.warm_sec(r.ts / 1000) >= 60.0
        st = settings()
        seed = br.infer_seed(rows, st)
        self.assertEqual(seed.samples, 31)
        rep = br.replay(rows, st, TICK, 200.0, "shadow", "book", seed=seed)
        agr = br.agreement(rows, rep)
        self.assertEqual(agr["basis_agree_pct"], 100.0)
        self.assertEqual(agr["anchored_agree_pct"], 100.0)
        cold = br.agreement(rows, br.replay(rows, st, TICK, 200.0, "shadow", "book"))
        self.assertLess(cold["basis_agree_pct"], 100.0)

    def test_a_pr_c_log_seeds_and_clocks_the_ema_from_basis_n_and_basis_t(self):
        # A PR C log carries basis_n and basis_t (the average's own clock, an Instant). This one starts with the
        # bot, while the average is still a running mean (alpha = 1/n for about 3 min at a 120 s half-life), the
        # clock wanders from ts_ms by a few ms, and 14 loops inside that phase were not logged (an L3 pause).
        full = make_rows(1500, vol_bps=2.0, seed=19)
        rng = random.Random(5)
        ema = br.BasisEma(120.0, 0.8, 5.0)
        for r in full:
            r.basis_t = 4321.0 + (r.ts - full[0].ts) / 1000 + rng.uniform(-0.004, 0.004)
            r.dbp, r.dap = r.bb - rng.randint(0, 3) * TICK, r.ba + rng.randint(0, 3) * TICK  # depth sits behind the touch
            r.depth_mid = (r.dbp + r.dap) / 2
            ema.update(r.basis_t, r.depth_mid, r.bn)
            r.basis, r.basis_n, r.basis_src, r.basis_updated = ema.value, ema.samples, "depth", True
            r.anchored = ema.warm_sec(r.basis_t) >= 60.0
        logged = full[:200] + full[214:]
        st = settings()
        seed = br.infer_seed(logged, st)
        self.assertEqual(seed.samples, 1)
        self.assertIn("basis_n", seed.note)
        rep = br.replay(logged, st, TICK, 200.0, "shadow", "depth", seed=seed, resync=True)
        agr = br.agreement(logged, rep)
        self.assertEqual(agr["basis_agree_pct"], 100.0, agr)
        self.assertEqual(agr["anchored_agree_pct"], 100.0)
        # Without the two fields (a PR B log) the same rows are not reproduced: ts_ms and an inferred seed.
        for r in logged:
            r.basis_t, r.basis_n = None, None
        bare = br.agreement(logged, br.replay(logged, st, TICK, 200.0, "shadow", "depth",
                                              seed=br.infer_seed(logged, st), resync=True))
        self.assertLess(bare["basis_agree_pct"], 90.0)

    def test_tick_inference(self):
        self.assertEqual(br.infer_tick(make_rows(100)), 1e-5)

    def test_calibration_compares_the_same_statistics_on_both_books(self):
        rows = make_rows(600, spread_bps=12.0, vol_bps=1.0, seed=17)
        st = settings(anchor_weight=0.0)
        rep = br.replay(rows, st, TICK, 200.0, "live", "book")
        # A "live log" written from the synthetic book itself (our resting quotes as its bid / ask): the
        # calibration must find no difference.
        live = []
        for i, r in enumerate(rows):
            sp = rep.live_spread_bps[i] / 1e4
            bb = 2 * rep.live_mid[i] / (2 + sp)  # mid = bb (2 + s) / 2
            live.append(br.Row(ts=r.ts, bb=bb, ba=bb * (1 + sp), bq=rep.live_bq[i], aq=rep.live_aq[i],
                               bn=r.bn, bn_age=0.0, fair=rep.live_mid[i], fair_delta=None, basis=None, anchored=None,
                               bid=rep.qbid[i] if not math.isnan(rep.qbid[i]) else 0.0, ask=rep.qask[i] if not math.isnan(rep.qask[i]) else 0.0,
                               place_bid=True, place_ask=True, regime=0, ofi=rep.ofi_drift[i] / st.ofi_beta * (rep.live_bq[i] + rep.live_aq[i]),
                               depth_mid=None, depth_age=None, depth_qty=None, dbp=None, dap=None, dbi=None, dai=None,
                               dbip=None, daip=None, dts=None, basis_src=None))
        cal = br.calibrate(live, rep, 200.0, st)
        self.assertTrue(cal["touch_ok"] and cal["spread_ok"] and cal["ofi_ok"])
        # Our 200 is the touch of a 12 bps book (the OMS at the touch on every row but the first); the plan-quote
        # measure misses the rows that requote, the same way on both books.
        self.assertGreater(cal["synthetic"]["oms_touch_pct"], 95.0)  # the rest: a stale quote the market moved through
        self.assertGreater(cal["synthetic"]["touch_pct"], 80.0)
        self.assertGreater(cal["real"]["touch_pct"], 80.0)
        self.assertLess(abs(cal["real"]["touch_pct"] - cal["synthetic"]["touch_pct"]), 1.0)
        self.assertGreater(cal["synthetic"]["dust_pct"], 95.0)
        self.assertAlmostEqual(cal["real"]["spread_p50_bps"], cal["synthetic"]["spread_p50_bps"], places=6)
        # Touch occupancy is "our order is the touch", not dust: a clean book with small L1 sizes scores the dust
        # share but no touch occupancy, and a live log whose quotes rest away from the touch scores none.
        clean = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        stats = br.book_stats(clean.live_spread_bps, [100.0] * 600, clean.live_aq, clean.ofi_drift, 200.0, clean.own_touch)
        self.assertEqual(stats["touch_pct"], 0.0)
        self.assertEqual(stats["dust_pct"], 100.0)
        for r in live:
            r.bid, r.ask = r.bb * (1 - 5e-4), r.ba * (1 + 5e-4)
        self.assertEqual(br.calibrate(live, rep, 200.0, st)["real"]["touch_pct"], 0.0)
        self.assertFalse(br.calibrate(live, rep, 200.0, st)["touch_ok"])
        # On the live log a placed side's plan quote within MM_REQUOTE_TOL_BPS of the L1 counts (live_own_touch).
        r = live[10]
        r.bid, r.ask, r.place_bid, r.place_ask = r.bb * (1 - 2.9e-4), 0.0, True, True
        self.assertTrue(br.live_own_touch(r, 3.0))
        r.place_bid = False
        self.assertFalse(br.live_own_touch(r, 3.0))
        r.place_bid, r.bid = True, r.bb * (1 - 3.1e-4)
        self.assertFalse(br.live_own_touch(r, 3.0))

    def test_a_log_gap_resyncs_the_ema_from_the_logged_basis(self):
        # The bot ran 14 loops it did not log (an L3 pause) and kept updating its EMA on them.
        full = make_rows(900, vol_bps=2.0, seed=13)
        ema = br.BasisEma(120.0, 0.8, 5.0)
        for r in full:
            ema.update(r.ts / 1000, r.mid, r.bn)
            r.basis = ema.value
            r.anchored = ema.warm_sec(r.ts / 1000) >= 60.0
        for r in full[400:414]:
            r.bn *= 1.0 + 20e-4  # the hidden loops saw a different basis
        ema = br.BasisEma(120.0, 0.8, 5.0)
        for r in full:
            ema.update(r.ts / 1000, r.mid, r.bn)
            r.basis = ema.value
        logged = full[:400] + full[414:]
        st = settings()
        plain = br.replay(logged, st, TICK, 200.0, "shadow", "book")
        synced = br.replay(logged, st, TICK, 200.0, "shadow", "book", resync=True)
        self.assertEqual((synced.gaps, synced.gap_loops, synced.resyncs), (1, 14, 1))
        self.assertEqual(plain.resyncs, 0)
        self.assertLess(br.agreement(logged, plain)["basis_agree_pct"], 100.0)
        self.assertEqual(br.agreement(logged, synced)["basis_agree_pct"], 100.0)


class FairJumpRule(unittest.TestCase):
    """strategy.rs:750 tests |fair / last_fair - 1| where last_fair is this loop's L1 mid (runner.rs:1082 before
    :1156): the defence fires on the fair's distance from the current mid, not on the mid's own move."""

    def test_jump_flags_follow_the_rust_wiring(self):
        st = settings()
        self.assertEqual(br.jump_flags(1.0, 1.0, st), (True, True))
        self.assertEqual(br.jump_flags(1.0 + 13e-4, 1.0, st), (False, True))  # fair above the mid: no bid
        self.assertEqual(br.jump_flags(1.0 - 13e-4, 1.0, st), (True, False))
        self.assertEqual(br.jump_flags(1.0 + 11.9e-4, 1.0, st), (True, True))
        self.assertEqual(br.jump_flags(1.0 + 13e-4, 1.0, settings(jump_defensive=False)), (True, True))
        self.assertEqual(br.jump_flags(1.0 + 13e-4, 0.0, st), (True, True))

    def test_a_mid_jump_the_fair_follows_drops_nothing_but_a_fair_dislocation_drops_a_side(self):
        rows = make_rows(600)
        for r in rows[300:]:  # Delta and Binance both step 20 bps: the fair stays on the mid
            for k in ("bb", "ba", "bn", "fair", "fair_delta", "bid", "ask", "depth_mid", "dbp", "dap"):
                setattr(r, k, getattr(r, k) * (1 + 20e-4))
        st = settings(anchor_weight=0.0, lead_beta=0.0)  # no lead term: the old fair is the mid blend
        rep = br.replay(rows, st, TICK, 200.0, "shadow", "book")
        self.assertTrue(all(rep.place_bid) and all(rep.place_ask))
        qb, qa = br.quote_series(rows, rep.fair_old, st, TICK)
        self.assertFalse(any(math.isnan(x) for x in qb + qa))
        # Binance alone jumps 20 bps: the anchored fair sits 20 bps above the mid, so the bid is dropped.
        rows = make_rows(600)
        for r in rows[300:]:
            r.bn *= 1 + 20e-4
        rep = br.replay(rows, settings(), TICK, 200.0, "shadow", "book")
        self.assertTrue(all(rep.place_bid[:300]))
        self.assertFalse(any(rep.place_bid[310:]))
        self.assertTrue(all(rep.place_ask))


class ConfigKeys(unittest.TestCase):
    def test_strategy_keys_are_global_only_and_the_others_per_symbol(self):
        cfg = {"MM_FIXED_HALF_SPREAD_BPS": "7", "MM_FIXED_HALF_SPREAD_BPS_ADAUSDT": "5",
               "MM_FAIR_JUMP_BPS": "20", "MM_FAIR_JUMP_BPS_ADAUSDT": "9", "MM_FAIR_JUMP_DEFENSIVE_ADAUSDT": "0",
               "MM_BASIS_HALFLIFE_SEC": "120", "MM_BASIS_HALFLIFE_SEC_ADAUSDT": "30"}
        st = br.Settings.from_config(cfg, "ADAUSDT")
        self.assertEqual(st.half_bps, 7.0)  # strategy.rs env_f64: the _ADAUSDT variant is ignored
        self.assertEqual(st.jump_bps, 20.0)
        self.assertTrue(st.jump_defensive)
        self.assertEqual(st.half_life_sec, 30.0)  # runner.rs env_f64_for_symbol
        self.assertEqual(br.Settings.from_config(cfg, "BERAUSDT").half_life_sec, 120.0)

    def test_loop_ms_sets_the_max_step_and_the_rust_floor(self):
        self.assertEqual(br.Settings.from_config({}, "ADAUSDT", 1000).max_step_sec, 2.0)
        self.assertEqual(br.Settings.from_config({}, "ADAUSDT", 50).loop_sec, 0.1)  # args.loop_ms.max(100)
        self.assertEqual(br.Settings.from_config({}, "ADAUSDT").max_step_sec, 0.8)


class BookFileTests(unittest.TestCase):
    """Recorded ob_l2 frames: the as-of join on the frame ts, and the live replay's ladder path."""

    @staticmethod
    def ladder(r: br.Row, inside: float = 0.0, inside_ask: float | None = None):
        """A 15-level ladder: `inside` contracts one tick inside the touch (`inside_ask` on the ask side, default
        the same), 6 000 at the touch, 50 000 behind: X = 10 000 lands one level behind the touch with
        6 000 + inside contracts inside it (the pivot band when that is in [X - q, X))."""
        bids, asks = [], []
        inside_ask = inside if inside_ask is None else inside_ask
        if inside:
            bids.append([round(r.bb + TICK, 5), inside])
        if inside_ask:
            asks.append([round(r.ba - TICK, 5), inside_ask])
        bids.append([r.bb, 6000.0])
        asks.append([r.ba, 6000.0])
        for k in range(1, 15):
            bids.append([round(r.bb - k * TICK, 5), 50_000.0])
            asks.append([round(r.ba + k * TICK, 5), 50_000.0])
        return bids[:15], asks[:15]

    def test_asof_returns_the_last_frame_at_or_before_ts_with_thinned_frames(self):
        rows = make_rows(20, dts=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "book.jsonl")
            write_book(rows, path, self.ladder, every=4)  # only rows 0, 4, 8, ... recorded
            with open(path, "a") as f:
                f.write("not json\n" + json.dumps({"recv_us": 1, "msg": {"type": "mark_price", "sy": "ADAUSD"}}) + "\n")
            book = br.BookFile()
            book.load(path, {"ADAUSD"})
        self.assertEqual(book.frames("ADAUSD"), 5)
        self.assertIsNone(book.asof("ADAUSD", rows[0].dts - 1))
        for i in range(20):
            b, a = book.asof("ADAUSD", rows[i].dts)
            j = (i // 4) * 4
            self.assertEqual(b[0], rows[j].bb, i)
            self.assertEqual(a[0], rows[j].ba, i)
        self.assertIsNone(book.asof("XRPUSD", rows[0].dts))

    def _live_depth(self, inside: float, inside_ask: float | None = None):
        x, q = 10_000.0, 200.0
        rows = make_rows(300, spread_bps=12.0, depth_qty=x, dts=True)
        # The logged depth fields come from the ladder itself (the join trusts a frame only when it reproduces
        # the logged depth prices).
        for r in rows:
            b, a = self.ladder(r, inside, inside_ask)
            flat_b = [v for lv in b for v in lv]
            flat_a = [v for lv in a for v in lv]
            cb, _ = br.side_depth_price(flat_b, x, True)
            ca, _ = br.side_depth_price(flat_a, x, False)
            r.dbp, r.dap, r.depth_mid = cb.price, ca.price, (cb.price + ca.price) / 2
            r.dbi, r.dai, r.dbip, r.daip = cb.inner, ca.inner, cb.inner_px, ca.inner_px
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "book.jsonl")
            write_book(rows, path, lambda r: self.ladder(r, inside, inside_ask))
            book = br.BookFile()
            book.load(path, {"ADAUSD"})
        rep = br.replay(rows, settings(), TICK, q, "live", "depth", 0, book, "ADAUSDT")
        return rows, rep

    def test_our_order_on_the_recorded_ladder_moves_the_depth_mid_only_inside_the_pivot_band(self):
        # Clean ladder: 6 000 at the touch, 50 000 behind: X = 10 000 lands one level behind the touch and
        # our 200 inside the spread does not reach it.
        rows, rep = self._live_depth(0.0)
        self.assertGreater(rep.ladder_rows, 250)
        self.assertEqual(sum(rep.depth_moved), 0)
        self.assertFalse(any(rep.pivot))
        for i in range(10, 300):
            self.assertAlmostEqual(rep.depth_mid[i], rows[i].depth_mid, places=12)
        # Others' 3 000 one tick inside the touch: the clean price stays one level behind the touch with
        # 9 000 inside it, below X - q = 9 800: not a pivot, our 200 moves nothing.
        rows, rep = self._live_depth(3_000.0)
        self.assertGreater(rep.ladder_rows, 250)
        self.assertEqual(sum(rep.depth_moved), 0)
        self.assertFalse(any(rep.pivot))
        # 3 900 inside: 9 900 inside the clean price, in [X - q, X): our 200 pushes the cumulative past X one
        # level earlier (the touch): a pivot, the depth price moves one tick.
        rows, rep = self._live_depth(3_900.0)
        self.assertGreater(rep.ladder_rows, 250)
        self.assertTrue(all(rep.pivot))
        moved = [i for i in range(300) if rep.depth_moved[i]]
        self.assertGreater(len(moved), 250)
        for i in moved:  # both sides pivot by one tick: the depth mid itself is unchanged
            self.assertAlmostEqual(rep.depth_mid[i], rows[i].depth_mid, places=12)
            self.assertEqual(rep.depth_move_bps[i], 0.0)
        # Pivot on the bid side only: the depth mid moves up by half a tick (~0.2 bps at 0.24), no more.
        rows, rep = self._live_depth(3_900.0, 3_000.0)
        moved = [i for i in range(300) if rep.depth_moved[i]]
        self.assertGreater(len(moved), 250)
        for i in moved:
            self.assertAlmostEqual(rep.depth_mid[i] - rows[i].depth_mid, TICK / 2, places=9)
            self.assertAlmostEqual(rep.depth_move_bps[i], TICK / 2 / rows[i].depth_mid * 1e4, places=6)
        self.assertEqual(rep.ladder_fallback, 0)
        self.assertEqual(rep.ladder_rows, 299)  # every row but the first (no quote rests yet)

    def test_run_dir_with_a_book_file_prices_rows_on_the_ladder(self):
        rows = make_rows(900, spread_bps=12.0, dts=True)
        for r in rows:
            b, a = self.ladder(r)
            cb, _ = br.side_depth_price([v for lv in b for v in lv], 10_000.0, True)
            ca, _ = br.side_depth_price([v for lv in a for v in lv], 10_000.0, False)
            r.dbp, r.dap, r.depth_mid = cb.price, ca.price, (cb.price + ca.price) / 2
            r.dbi, r.dai = cb.inner, ca.inner
        with tempfile.TemporaryDirectory() as d:
            write_log(rows, os.path.join(d, "dry-run.log"))
            write_book(rows, os.path.join(d, "delta_mainnet_book_20260101.jsonl"), self.ladder)
            with open(os.path.join(d, "config.txt"), "w") as f:
                f.write("MM_FAIR_ANCHOR_WEIGHT=1\nMM_ORDER_QTY_ADAUSDT=200\n")
            out_json = os.path.join(d, "o.json")
            code, out = run_main(["--run-dir", d, "--symbol", "ADAUSDT", "--mode", "live", "--source", "depth",
                                  "--min-hours", "0.05", "--boot", "20", "--json", out_json])
            self.assertRegex(out, r"live depth: [1-9]\d* rows priced on the recorded ladder")
            rec = read_json(out_json)["results"][0]
            # 6 min of rows: the 60 s warm-up alone fails G1; the ladder path holds G2 and G3.
            self.assertEqual(code, 1, out)
            self.assertEqual((rec["gates"]["G1"], rec["gates"]["G2"], rec["gates"]["G3"]), (False, True, True))


class StrictJsonAndArgs(unittest.TestCase):
    def test_json_is_strict_when_statistics_are_undefined(self):
        rows = make_rows(900, depth=False)  # no depth fields: G1/G2 undefined; no logged basis: agreement undefined
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(rows, path)
            out_json = os.path.join(d, "o.json")
            code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT", "--min-hours", "0.05", "--boot", "20", "--json", out_json])
            with open(out_json) as f:
                raw = f.read()
            self.assertNotRegex(raw, r"\bNaN\b|\bInfinity\b")
            rec = read_json(out_json)["results"][0]  # parse_constant raises on a bare constant
        self.assertIsNone(rec["G2"]["p90_bps"])
        self.assertIsNone(rec["agreement"]["basis_agree_pct"])
        self.assertEqual(rec["gates"]["G1"], None)
        self.assertEqual(code, 1 if any(v is False for v in rec["gates"].values()) else 3)
        self.assertIn("INCOMPLETE" if code == 3 else "FAIL", out)
        self.assertIn("not evaluated: G1 (no depth fields logged), G2 (no depth fields logged), G3 (shadow mode)", out)

    def test_calibration_rows_stay_out_of_the_json_args_and_are_clipped_to_the_live_span(self):
        rows = make_rows(1500, spread_bps=12.0, vol_bps=1.0, seed=17)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(rows, path)
            live = os.path.join(d, "live.log")
            write_log(rows[500:800], live)  # the live log covers only the middle 300 rows
            out_json = os.path.join(d, "o.json")
            code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT", "--mode", "live", "--min-hours", "0.05",
                                  "--boot", "20", "--json", out_json, "--calibrate", live])
            size = os.path.getsize(out_json)
            doc = read_json(out_json)
        self.assertNotIn("calibrate_rows", doc["args"])
        self.assertLess(size, 60_000)
        cal = doc["results"][0]["calibration"]
        self.assertEqual(cal["real"]["n"], 300)
        self.assertEqual(cal["synthetic"]["n"], 300)  # clipped to the live log's span
        self.assertEqual(cal["span"], [rows[500].ts, rows[799].ts])
        self.assertIn("synthetic rows clipped to the live log's span", out)
        self.assertEqual(cal["live_two_sided_pct"], 100.0)
        self.assertIn("CAL", doc["results"][0]["gates"])
        # An uncalibrated synthetic book demotes a G3 pass to n/a (a fail stands) and the verdict says so.
        if not cal["ok"]:
            self.assertIn(doc["results"][0]["gates"]["G3"], (None, False))
            self.assertIn("UNCALIBRATED", out)
            self.assertIn("synthetic live book UNCALIBRATED: G3 and the live-mode rows are provisional", out)

    def test_unusable_options_exit_2_with_a_message(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(make_rows(50), path)
            for extra in (["--latency", "abc"], ["--latency", "-1"], ["--from", "garbage"], ["--to", "2026-13-99"],
                          ["--exclude", "x", "y"], ["--exclude", "1700000000000", "1600000000000"], ["--loop-ms", "0"],
                          ["--calibrate", path], ["--book", path], ["--mode", "shadow", "--calibrate", path]):
                code, out = run_main(["--metrics", path, "--symbol", "ADAUSDT"] + extra)
                self.assertEqual(code, 2, extra)
                self.assertIn("unusable option", out)
            # A run dir's book file is only picked up in live mode, never an error in shadow mode.
            os.rename(path, os.path.join(d, "dry-run.log"))
            with open(os.path.join(d, "delta_mainnet_book_20260101.jsonl"), "w"):
                pass
            code, out = run_main(["--run-dir", d, "--symbol", "ADAUSDT"])
            self.assertEqual(code, 2)
            self.assertIn("thin data", out)

    def test_covered_hours_drop_the_excluded_span(self):
        rows = make_rows(6000)  # 40 min
        t0, t1 = rows[750].ts, rows[5250].ts  # 30 min excluded: 10 min of data remain
        self.assertAlmostEqual(br.covered_hours(rows, [])[0], 5999 * LOOP_MS / 3.6e6)
        cov, exc = br.covered_hours(rows, [(t0, t1)])
        self.assertAlmostEqual(cov, (5999 * LOOP_MS - 4500 * LOOP_MS) / 3.6e6)
        self.assertAlmostEqual(exc, 0.5)
        # Overlapping and out-of-range windows are merged / clipped.
        cov2, exc2 = br.covered_hours(rows, [(t0, t1), (t0 + 1000, t1 + 1000), (rows[-1].ts + 1e6, rows[-1].ts + 2e6)])
        self.assertAlmostEqual(exc2, (t1 + 1000 - t0) / 3.6e6)
        self.assertAlmostEqual(cov2 + exc2, 5999 * LOOP_MS / 3.6e6)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(rows, path)
            out_json = os.path.join(d, "o.json")
            common = ["--metrics", path, "--symbol", "ADAUSDT", "--min-hours", "0.5", "--boot", "20", "--json", out_json,
                      "--exclude", str(int(t0)), str(int(t1))]
            code, out = run_main(common)
            self.assertEqual(code, 2)  # 10 min of covered data < 0.5 h although the span is 40 min
            self.assertIn("0.17 h covered (0.50 h excluded)", out)
            code, out = run_main(common[:-3] + ["--min-hours", "0.1", "--exclude", str(int(t0)), str(int(t1))])
            self.assertIn("rows 1500 (0.17 h covered, 0.50 h excluded)", out)
            rec = read_json(out_json)["results"][0]
            self.assertAlmostEqual(rec["hours"], cov, places=6)
            self.assertAlmostEqual(rec["excluded_hours"], 0.5)
            # An exclusion overlapping the --from edge is clipped to the window, not to the kept rows' span:
            # --from row 1000 --to row 5000 with rows 500..1500 excluded = 500 excluded rows inside the window.
            code, out = run_main(common[:-3] + ["--min-hours", "0.1", "--from", str(int(rows[1000].ts)), "--to", str(int(rows[5000].ts)),
                                                "--exclude", str(int(rows[500].ts)), str(int(rows[1500].ts))])
            rec = read_json(out_json)["results"][0]
            self.assertEqual(rec["rows"], 3500)
            self.assertAlmostEqual(rec["excluded_hours"], 500 * LOOP_MS / 3.6e6, places=6)
            self.assertAlmostEqual(rec["hours"], 3499 * LOOP_MS / 3.6e6, places=6)  # the window spans 3 999 loops
            self.assertIn("rows 3500 (0.39 h covered, 0.06 h excluded)", out)

    def test_exactly_24_h_of_loops_is_not_provisional(self):
        self.assertTrue(br.enough_hours(215_999 * 0.4 / 3600.0, 24.0, 0.4))  # 216 000 rows at 400 ms
        self.assertFalse(br.enough_hours(215_998 * 0.4 / 3600.0, 24.0, 0.4))
        self.assertTrue(br.enough_hours(24.5, 24.0, 0.4))
        # 1 000 rows one 86.4 s loop apart span 23.976 h = exactly 24 h of loops.
        rows = make_rows(1000)
        for i, r in enumerate(rows):
            r.ts = rows[0].ts + i * 86_400.0
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(rows, path)
            common = ["--metrics", path, "--symbol", "ADAUSDT", "--min-rows", "10", "--boot", "20", "--loop-ms", "86400"]
            code, out = run_main(common)
            self.assertIn("rows 1000 (23.98 h covered)", out)
            self.assertNotIn("PROVISIONAL", out)
            self.assertIn("Verdict: ", out)
            # One loop short of 24 h (999 rows) is provisional.
            write_log(rows[:999], path)
            code, out = run_main(common)
            self.assertIn("PROVISIONAL", out)
            self.assertIn("23.95 h covered < 24 h", out)

    def test_g1_is_na_without_binance_fresh_rows_and_its_threshold_is_the_plans_2_s(self):
        rows = make_rows(1500)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            cfg = os.path.join(d, "config.txt")
            with open(cfg, "w") as f:
                f.write("MM_FAIR_ANCHOR_WEIGHT=1\nMM_DEPTH_STALE_MS=5000\n")
            common = ["--metrics", path, "--config", cfg, "--symbol", "ADAUSDT", "--min-hours", "0.1", "--boot", "20",
                      "--mode", "live", "--source", "depth", "--json", os.path.join(d, "o.json")]
            for r in rows[::2]:
                r.depth_age = 3000.0  # stale for the plan's 2 s, fresh for the profile's 5 s
            write_log(rows, path)
            code, out = run_main(common)
            rec = read_json(os.path.join(d, "o.json"))["results"][0]
            self.assertIn("G1 health: depth snapshot <= 2000 ms on 50.0% of 1500 Binance-fresh rows", out)
            self.assertIn("WARNING: the profile's MM_DEPTH_STALE_MS=5000 differs from G1's fixed 2000 ms", out)
            self.assertIs(rec["gates"]["G1"], False)
            self.assertEqual(code, 1)
            for r in rows:
                r.bn = 0.0  # no Binance mid at all
            write_log(rows, path)
            code, out = run_main(common)
            rec = read_json(os.path.join(d, "o.json"))["results"][0]
            self.assertIsNone(rec["gates"]["G1"])
            self.assertIsNone(rec["G1"]["anchor_pct"])
            self.assertEqual(rec["gate_notes"]["G1"], "no Binance-fresh rows")
            g1_line = next(l for l in out.splitlines() if l.startswith("G1 health"))
            self.assertIn("of 0 Binance-fresh rows (none: not evaluated)", g1_line)
            self.assertIn("[>= 95% each]  n/a", g1_line)  # never a FAIL resting on a NaN comparison
            self.assertNotIn("FAIL", g1_line)
            self.assertEqual(code, 3)

    def test_parity_uses_the_run_settings_and_reports_them(self):
        rows = make_rows(1000, spread_fn=lambda i: 4.0 if i < 300 else 12.0)
        default = br.parity_replay(rows, TICK)
        self.assertEqual(default["settings"]["half_life_sec"], 120.0)
        same = br.parity_replay(rows, TICK, st=settings())
        self.assertEqual((same["updated_pct"], same["anchored_pct"]), (default["updated_pct"], default["anchored_pct"]))
        other = br.parity_replay(rows, TICK, st=settings(warmup_sec=200.0, max_age_sec=100.0))
        self.assertEqual(other["settings"]["warmup_sec"], 200.0)
        self.assertLess(other["anchored_pct"], default["anchored_pct"])

    def test_load_metrics_counts_the_lines_it_skips(self):
        rows = make_rows(20)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            with open(path, "w") as f:
                for r in rows:
                    f.write(row_json(r))
                f.write('x INFO MM_METRICS: {"symbol": "ADAUSDT", "fair": 1.0}\n')  # no ts_ms
                f.write('x INFO MM_METRICS: {"symbol": "BERAUSDT", "ts_ms": 1, "fair": 1.0, "book_bid": 2.0, "book_ask": 1.0}\n')  # crossed
                f.write('x INFO MM_METRICS: {broken\n')
                f.write('x INFO MM_ORDER: {"symbol": "ADAUSDT"}\n')
            skipped = {}
            got = br.load_metrics([path], skipped)
        self.assertEqual(len(got["ADAUSDT"]), 20)
        self.assertEqual(skipped, {"ADAUSDT": 1, "BERAUSDT": 1, "?": 1})
        # A symbol filter drops the other symbols' lines before the JSON parse (and does not count them).
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            with open(path, "w") as f:
                for i, r in enumerate(rows):
                    f.write(row_json(r, "ADAUSDT" if i % 2 else "BERAUSDT"))
                f.write('x INFO MM_METRICS: {"symbol": "BERAUSDT", "fair": 1.0}\n')  # no ts_ms, not wanted
                f.write('x INFO MM_METRICS: {"symbol":"ADAUSDT","fair":1.0}\n')  # serde's spacing, wanted
            skipped = {}
            got = br.load_metrics([path], skipped, {"ADAUSDT"})
        self.assertEqual(sorted(got), ["ADAUSDT"])
        self.assertEqual(len(got["ADAUSDT"]), 10)
        self.assertEqual(skipped, {"ADAUSDT": 1})
        self.assertEqual(br.line_symbol('{"ts_ms": 1, "symbol":"KITEUSDT"}'), "KITEUSDT")
        self.assertIsNone(br.line_symbol('{"ts_ms": 1}'))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(make_rows(600), path)
            code, out = run_main(["--metrics", path, "--symbol", "FOO", "--min-hours", "0.01"])
            self.assertEqual(code, 2)
            self.assertIn("no MM_METRICS rows", out)

    def test_anchor_weight_warning_names_its_source(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dry-run.log")
            write_log(make_rows(600), path)
            cfg = os.path.join(d, "config.txt")
            with open(cfg, "w") as f:
                f.write("MM_FAIR_ANCHOR_WEIGHT=1\n")
            common = ["--metrics", path, "--symbol", "ADAUSDT", "--min-hours", "0.01", "--boot", "10"]
            _, out = run_main(common + ["--config", cfg, "--anchor-weight", "0"])
            self.assertIn("anchor weight 0 (--anchor-weight 0)", out)
            _, out = run_main(common)
            self.assertIn("anchor weight 0 (no MM_FAIR_ANCHOR_WEIGHT in the config)", out)
            with open(cfg, "w") as f:
                f.write("MM_FAIR_ANCHOR_WEIGHT=0\n")
            _, out = run_main(common + ["--config", cfg])
            self.assertIn("anchor weight 0 (MM_FAIR_ANCHOR_WEIGHT=0 in the config)", out)


class GateVerdicts(unittest.TestCase):
    def test_gate_verdict_fail_beats_na_beats_pass(self):
        self.assertTrue(br.gate_verdict({"a": True, "b": True}))
        self.assertIsNone(br.gate_verdict({"a": True, "b": None}))
        self.assertFalse(br.gate_verdict({"a": False, "b": None}))
        self.assertFalse(br.gate_verdict({"a": False, "b": True}))

    def test_expo_ok_is_the_plan_bound(self):
        self.assertTrue(br.expo_ok({"n": 10, "ci": (-1.0, 1.0), "diff_bid": 3.0, "diff_ask": -1.0}))
        self.assertFalse(br.expo_ok({"n": 10, "ci": (-1.0, 1.01), "diff_bid": 0.0, "diff_ask": 0.0}))
        self.assertFalse(br.expo_ok({"n": 10, "ci": (-1.0, 0.0), "diff_bid": 3.1, "diff_ask": 0.0}))
        self.assertFalse(br.expo_ok({"n": 0}))

    @staticmethod
    def _lead_fixture(d: str, n: int = 3000, lead: int = 13) -> list[str]:
        """Binance leads Delta's mid by `lead` loops (~5 s), so the anchored fair carries real information and
        every gate can pass; MM_LEAD_BETA=0 keeps the old fair plain."""
        rows = make_rows(n + lead, spread_bps=12.0, vol_bps=3.0, seed=5)
        mids = [r.mid for r in rows]
        out = rows[:n]
        for i, r in enumerate(out):
            r.bn = mids[i + lead] / (1.0 - 8.0 / 1e4)
        path = os.path.join(d, "dry-run.log")
        write_log(out, path)
        cfg = os.path.join(d, "config.txt")
        with open(cfg, "w") as f:
            f.write("MM_FAIR_ANCHOR_WEIGHT=1\nMM_LEAD_BETA=0\nMM_ORDER_QTY_ADAUSDT=200\n")
        return ["--metrics", path, "--config", cfg, "--symbol", "ADAUSDT", "--min-hours", "0.3", "--boot", "50"]

    def test_exit_0_only_when_every_gate_is_evaluated_and_passes(self):
        with tempfile.TemporaryDirectory() as d:
            common = self._lead_fixture(d)
            out_json = os.path.join(d, "o.json")
            code, out = run_main(common + ["--mode", "live", "--source", "depth", "--json", out_json])
            self.assertEqual(code, 0, out)
            self.assertIn("Verdict: PROVISIONAL PASS (0.33 h covered < 24 h)", out)
            rec = read_json(out_json)["results"][0]
            # G1-G4 decide; G4 on the 60 s lead only. The 5 s slope and G5 exposure are diagnostics.
            self.assertEqual(rec["gates"], {"G1": True, "G2": True, "G3": True, "G4": True})
            self.assertEqual(rec["ruled_out"], {})
            self.assertEqual(rec["G4"]["components"], {"G4@60": True})
            self.assertEqual(rec["G4"]["diagnostic"], {"G4@5": True})
            self.assertEqual(rec["G5"]["components"], {"G5@30": True, "G5@60": True})
            self.assertTrue(rec["G5"]["diagnostic"])
            self.assertIn("G5 exposure (diagnostic, not in the verdict;", out)
            self.assertIn("pick-off is judged only in the pre-registered first live run", out)
            # Both oracles are scored on all four components here and fail none.
            self.assertEqual(sorted(rec["oracle"]), ["5", "60"])
            for h in ("5", "60"):
                self.assertEqual(rec["oracle"][h]["components"], {"G4@5": True, "G4@60": True, "G5@30": True, "G5@60": True})
            self.assertEqual(out.count("fails: none"), 2)
            self.assertNotIn("RULE (plan)", out)
            # Shadow mode cannot evaluate G3: INCOMPLETE, exit 3, not a pass.
            code, out = run_main(common + ["--mode", "shadow", "--source", "depth", "--json", out_json])
            self.assertEqual(code, 3, out)
            self.assertIn("Verdict: PROVISIONAL INCOMPLETE (0.33 h covered < 24 h); not evaluated: G3 (shadow mode)", out)
            self.assertEqual(read_json(out_json)["results"][0]["gates"]["G3"], None)
            # The book source starves live (our quotes are the 12 bps touch): G3 fails, exit 1.
            code, out = run_main(common + ["--mode", "live", "--source", "book"])
            self.assertEqual(code, 1, out)
            self.assertIn("Verdict: PROVISIONAL FAIL (G3)", out)
            self.assertIn("oracle (fair = mid +5 s): slope +5 s 1.000", out)
            self.assertIn("oracle (fair = mid +60 s): slope +5 s", out)
            self.assertNotIn("+30 s): slope", out)

    def test_gate_components_follow_the_plan_bounds(self):
        sc = {"slope": {5: {"new": 0.4, "old": 0.1}, 60: {"new": 0.5, "old": 0.2, "ci": (0.1, 0.9)}},
              "expo": {30: {"n": 10, "ci": (-1.0, 0.5), "diff_bid": 0.0, "diff_ask": 0.0},
                       60: {"n": 10, "ci": (-1.0, 1.5), "diff_bid": 0.0, "diff_ask": 0.0}}}
        self.assertEqual(br.gate_components(sc), {"G4@5": True, "G4@60": True, "G5@30": True, "G5@60": False})
        sc["slope"][60]["ci"] = (-0.1, 0.9)
        sc["slope"][5]["old"] = 0.5
        self.assertEqual(br.gate_components(sc), {"G4@5": False, "G4@60": False, "G5@30": True, "G5@60": False})
        sc["slope"][60]["ci"] = (float("nan"), float("nan"))
        self.assertFalse(br.gate_components(sc)["G4@60"])  # one block, no CI: not evaluable

    def test_an_oracle_failing_a_component_rules_it_out_across_horizons(self):
        # 8 min of the lead fixture with no EMA warm-up: the +60 s oracle, scored at +30 s, is more exposed
        # than the old fair on the bid side (+5.4 pp > 3, upper CI > 1), so G5@30 cannot judge a fair here. G5
        # is a diagnostic, so the deciding gates G1-G4 all pass: exit 0. (An oracle never fails its own horizon.)
        with tempfile.TemporaryDirectory() as d:
            common = self._lead_fixture(d, n=1200)
            with open(os.path.join(d, "config.txt"), "a") as f:
                f.write("MM_BASIS_WARMUP_SEC=0\n")
            out_json = os.path.join(d, "o.json")
            code, out = run_main(common[:-4] + ["--min-hours", "0.1", "--boot", "50", "--mode", "live", "--source", "depth", "--json", out_json])
            rec = read_json(out_json)["results"][0]
            self.assertEqual(rec["ruled_out"], {})  # only deciding components are ruled out
            self.assertEqual(rec["oracle"]["60"]["fails"], ["G5@30"])
            self.assertEqual(rec["oracle"]["60"]["components"]["G5@60"], True)  # its own horizon
            self.assertEqual(rec["oracle"]["5"]["fails"], [])
            self.assertGreater(rec["oracle"]["60"]["expo"]["30"]["diff_bid"], 3.0)
            self.assertEqual(rec["G5"]["components"], {"G5@30": None, "G5@60": True})
            self.assertEqual(rec["G4"]["components"], {"G4@60": True})
            self.assertEqual(rec["gates"], {"G1": True, "G2": True, "G3": True, "G4": True})
            self.assertIn("pp n/a (oracle+60 fails it)", out)
            self.assertIn("oracle (fair = mid +60 s): slope +5 s", out)
            self.assertIn("fails: G5@30", out)
            self.assertNotIn("RULE (plan)", out)
            self.assertIn("Verdict: PROVISIONAL PASS (0.13 h covered < 24 h)", out)
            self.assertEqual(code, 0, out)
            # Under two 5-min blocks every CI is undefined: both oracles fail G4@60, G5@30 and G5@60.
            code, out = run_main(common[:-4] + ["--min-hours", "0.05", "--boot", "50", "--mode", "live", "--source", "depth",
                                                "--json", out_json, "--to", str(int(br.parse_time("2023-11-14T22:19:20Z")))])
            rec = read_json(out_json)["results"][0]
            self.assertEqual(rec["rows"], 900)
            self.assertEqual(rec["ruled_out"], {"G4@60": "oracle+5, oracle+60"})
            for h in ("5", "60"):
                self.assertEqual(rec["oracle"][h]["fails"], ["G4@60", "G5@30", "G5@60"])
            self.assertEqual(rec["G4"]["components"], {"G4@60": None})
            self.assertEqual(code, 3, out)
            self.assertIn("RULE (plan): no gate may rely on a metric the oracle fails: G4@60 (oracle+5, oracle+60)", out)
            self.assertIn("not evaluated: G4 (oracle fails G4@60)", out)
            self.assertNotIn("not evaluated: G4 (oracle fails G4@60), G5", out)

    def test_a_thin_symbol_next_to_a_failing_one_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            common = self._lead_fixture(d)
            code, out = run_main(common[:4] + ["--symbol", "ADAUSDT,FOO", "--min-hours", "0.3", "--boot", "20", "--mode", "live", "--source", "book"])
            self.assertEqual(code, 2)
            self.assertIn("=== FOO: thin data: 0 rows", out)
            self.assertIn("Verdict: PROVISIONAL FAIL (G3)", out)


@unittest.skipUnless(DATA and all(os.path.exists(os.path.join(DATA, f)) for f in DATA_FILES),
                     f"PR D data pack not present: set BASIS_REPLAY_DATA to a directory holding {', '.join(DATA_FILES)}")
class RealData(unittest.TestCase):
    def test_shadow_now_ada_agrees_with_the_log(self):
        with tempfile.TemporaryDirectory() as d:
            out_json = os.path.join(d, "o.json")
            code, out = run_main([
                "--metrics", os.path.join(DATA, "shadow_now_metrics.log"), "--config", os.path.join(DATA, "shadow_now_config.txt"),
                "--symbol", "ADAUSDT", "--mode", "shadow", "--min-hours", "0.3", "--boot", "50", "--json", out_json,
            ])
            rec = read_json(out_json)["results"][0]
        self.assertGreaterEqual(rec["agreement"]["basis_agree_pct"], 99.9)
        self.assertGreaterEqual(rec["agreement"]["anchored_agree_pct"], 99.9)
        self.assertLess(rec["agreement"]["fair_max_dev_bps_anchored"], 1e-3)
        # The bot's logged bid / ask and side flags are those of the as-coded fair (the rows that differ are
        # the ones where the OFI window sum is inexact after a log gap).
        self.assertGreaterEqual(rec["agreement"]["bid_exact_pct"], 99.5)
        self.assertGreaterEqual(rec["agreement"]["ask_exact_pct"], 99.5)
        self.assertGreaterEqual(rec["agreement"]["place_flags_pct"], 99.9)
        self.assertEqual(rec["agreement"]["ofi_exact_pct"], 100.0)
        # A 24-min window: G4@60's CI fails, G3 is not evaluated in shadow mode.
        self.assertEqual(code, 1, rec["gates"])
        self.assertIs(rec["gates"]["G4"], False)
        self.assertIsNone(rec["gates"]["G3"])

    def test_parity_on_the_13_oct_ada_window(self):
        rows = br.load_metrics([os.path.join(DATA, "shadow_13oct_ada_metrics.log")])["ADAUSDT"]
        rows = br.apply_window(rows, br.parse_time("2026-10-13T07:41:00Z"), br.parse_time("2026-10-13T10:19:51Z"), [])
        par = br.parity_replay(rows, 1e-5)
        self.assertEqual(par["n"], 23818)
        self.assertAlmostEqual(par["updated_pct"], 7.6, delta=0.2)
        self.assertAlmostEqual(par["anchored_pct"], 74.1, delta=0.2)


if __name__ == "__main__":
    unittest.main()
