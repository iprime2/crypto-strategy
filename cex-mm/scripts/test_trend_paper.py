#!/usr/bin/env python3
"""Tests for trend_paper.py: python3 -m unittest test_trend_paper (from cex-mm/scripts)."""
from __future__ import annotations

import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trend_backtest as tb  # noqa: E402
import trend_paper as tp  # noqa: E402

NOW = dt.datetime(2026, 10, 12, 0, 5, tzinfo=dt.timezone.utc)  # a Monday, 00:05 UTC


def synthetic(now: dt.datetime, up: float = 1.01):
    """Trending closes for every coin, a tight book around the last close, 0.01 contract values."""
    days = [now.date() - dt.timedelta(k) for k in range(200, 0, -1)]
    closes = {c: {d: 100 * up ** i * (1 + 0.02 * (-1) ** i) for i, d in enumerate(days)} for c in tb.COINS}
    last = closes["BTC"][days[-1]]
    books = {c: ([(last * 0.9999, 1e9)], [(last * 1.0001, 1e9)]) for c in tb.COINS}
    return closes, books, {c: 0.01 for c in tb.COINS}


class Due(unittest.TestCase):
    def test_fresh_state_is_due(self):
        self.assertTrue(tp.due(tp.init_state(1000, NOW), NOW.date(), weekly=False))
        self.assertTrue(tp.due(tp.init_state(1000, NOW), NOW.date(), weekly=True))

    def test_daily_once_per_day(self):
        s = {"last_rebalance": "2026-10-12"}
        self.assertFalse(tp.due(s, dt.date(2026, 10, 12), weekly=False))
        self.assertTrue(tp.due(s, dt.date(2026, 10, 13), weekly=False))

    def test_weekly_once_per_iso_week(self):
        s = {"last_rebalance": "2026-10-12"}  # Monday
        for day in range(12, 19):  # Monday .. Sunday of the same ISO week
            self.assertFalse(tp.due(s, dt.date(2026, 10, day), weekly=True), day)
        self.assertTrue(tp.due(s, dt.date(2026, 10, 19), weekly=True))  # next Monday
        # A Monday that was missed is caught up on Tuesday of the same week, once.
        s = {"last_rebalance": "2026-10-11"}  # the previous week's Sunday
        self.assertTrue(tp.due(s, dt.date(2026, 10, 13), weekly=True))


class Config(unittest.TestCase):
    def test_legacy_state_is_the_daily_default(self):
        s = {"capital": 1000}  # written before the config field existed
        tp.check_config(s, tp.DEFAULT_CONFIG)  # no error
        with self.assertRaises(SystemExit):
            tp.check_config(s, {"weekly": True, "target_vol": 0.25, "band": 0.10})

    def test_mismatch_refuses(self):
        cfg = {"weekly": True, "target_vol": 0.25, "band": 0.10}
        s = tp.init_state(1000, NOW, cfg)
        tp.check_config(s, dict(cfg))
        for bad in ({**cfg, "weekly": False}, {**cfg, "target_vol": 0.40}, {**cfg, "band": 0.0}):
            with self.assertRaises(SystemExit):
                tp.check_config(s, bad)


class Sizing(unittest.TestCase):
    def test_target_vol_scales_positions(self):
        closes, books, cvals = synthetic(NOW)
        s40, s25 = tp.init_state(100000.0, NOW), tp.init_state(100000.0, NOW)
        tp.step(s40, closes, books, {}, cvals, NOW, target_vol=0.40)
        tp.step(s25, closes, books, {}, cvals, NOW, target_vol=0.25)
        for c in tb.COINS:
            ratio = s25["positions"][c] / s40["positions"][c]
            self.assertAlmostEqual(ratio, 0.625, delta=0.02, msg=c)  # 0.25 / 0.40, within whole-contract rounding

    def test_band_skips_small_trades_but_never_a_close(self):
        pos = {"BTC": 100, "ETH": 10}
        w = {"BTC": 0.5, "ETH": 0.0}
        mids = {c: 100.0 for c in tb.COINS}
        cvals = {c: 0.01 for c in tb.COINS}
        eq = 100 * 0.01 * 100 * 2 / 1.0  # BTC target = 0.5 * eq / (100 * 0.01) = 0.5 * 200 / 1 = 100 contracts
        # Target 105 vs held 100: a 5-contract trade is 4.8% of the target -> skipped at a 10% band, traded at 0.
        w = {"BTC": 0.525, "ETH": 0.0}
        plan, skipped = tp.plan_orders(pos, w, eq, mids, cvals, band=0.10)
        self.assertEqual([p["coin"] for p in plan], ["ETH"])  # the ETH close is never skipped
        self.assertEqual(plan[0]["contracts"], -10)
        self.assertEqual([(k["coin"], k["contracts"]) for k in skipped], [("BTC", 5)])
        plan0, skipped0 = tp.plan_orders(pos, w, eq, mids, cvals, band=0.0)
        self.assertEqual(sorted(p["coin"] for p in plan0), ["BTC", "ETH"])
        self.assertEqual(skipped0, [])

    def test_step_records_skipped_and_keeps_position(self):
        closes, books, cvals = synthetic(NOW)
        s = tp.init_state(100000.0, NOW, {"weekly": True, "target_vol": 0.25, "band": 0.10})
        rec = tp.step(s, closes, books, {}, cvals, NOW, target_vol=0.25, band=0.10)
        self.assertEqual(rec["skipped"], [])  # from flat, every trade is 100% of its target
        held = dict(s["positions"])
        # A flat week: seven unchanged closes lower the 60-day realized vol by about 6%, so every target grows
        # about 6%, inside the 10% band. Nothing trades and the positions stay where they were.
        nxt = NOW + dt.timedelta(7)
        last = closes["BTC"][NOW.date() - dt.timedelta(1)]
        for c in tb.COINS:
            for k in range(7):
                closes[c][NOW.date() + dt.timedelta(k)] = last
        rec2 = tp.step(s, closes, books, {}, cvals, nxt, target_vol=0.25, band=0.10)
        self.assertEqual(rec2["orders"], [])
        self.assertEqual(s["positions"], held)
        self.assertTrue(rec2["skipped"] and all(k["contracts"] > 0 for k in rec2["skipped"]), rec2["skipped"])


class OrdersOnly(unittest.TestCase):
    def test_order_list_matches_step_and_does_not_mutate(self):
        closes, books, cvals = synthetic(NOW)
        s = tp.init_state(5000.0, NOW, {"weekly": True, "target_vol": 0.25, "band": 0.10})
        before = dict(s)
        listed = tp.order_list(s, closes, books, {}, cvals, NOW, target_vol=0.25, band=0.10)
        self.assertEqual(s, before)
        self.assertEqual(listed["signal_day"], NOW.date() - dt.timedelta(1))
        rec = tp.step(s, closes, books, {}, cvals, NOW, target_vol=0.25, band=0.10)
        self.assertEqual([(p["coin"], p["contracts"]) for p in listed["plan"]],
                         [(o["coin"], o["contracts"]) for o in rec["orders"]])

    def test_order_list_includes_funding_like_step(self):
        closes, books, cvals = synthetic(NOW)
        s = tp.init_state(5000.0, NOW)
        tp.step(s, closes, books, {}, cvals, NOW)
        funding = {c: 0.001 for c in tb.COINS}
        nxt = NOW + dt.timedelta(1)
        for c in tb.COINS:
            closes[c][nxt.date() - dt.timedelta(1)] = closes[c][NOW.date() - dt.timedelta(1)]
        listed = tp.order_list(s, closes, books, funding, cvals, nxt)
        eq_no_funding = tp.equity(s, listed["mids"], cvals)
        self.assertLess(listed["equity"], eq_no_funding)
        self.assertAlmostEqual(eq_no_funding - listed["equity"], listed["funding"])


if __name__ == "__main__":
    unittest.main()
