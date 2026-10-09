#!/usr/bin/env python3
"""Tests for the Scalper Offer fee model in shadow_fill_sim.py (stdlib only).

    cd cex-mm/scripts && python3 -m unittest -v test_shadow_fill_sim

Hand-computed cases on a flat market: Delta book 98 / 102 (mid 100), our bid 99 and ask 101,
contract value 1, so a buy costs 99 * 2.12 / 1e4 per contract in fees and a sell 101 * 2.12 / 1e4.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shadow_fill_sim as sim  # noqa: E402

FEE_BPS = 2.12
BID, ASK = 99.0, 101.0
BUY, SELL = 1, -1  # our side: BUY = our bid was hit, SELL = our ask was lifted


def fee(qty: float, price: float) -> float:
    return qty * price * FEE_BPS / 1e4


def config(window_min: float = 0.0, match: str = "fifo") -> sim.SimConfig:
    kw = {} if window_min == 0 else {"scalper_window_min": window_min, "scalper_match": match}
    return sim.SimConfig(
        latency_ms=0.0,
        half_spread_bps=None,
        rule="strict",
        quote_usd=200.0,  # 2 contracts per quote at price 100, inventory cap 6
        max_inv_orders=3,
        fee_bps=FEE_BPS,
        requote_tol_bps=3.0,
        max_gap_ms=1e12,
        loop_ms=0.0,
        **kw,
    )


def sample(ts: float) -> sim.Sample:
    return sim.Sample(
        ts=ts, fair=100.0, bid=BID, ask=ASK, place_bid=True, place_ask=True,
        regime=0, book_bid=98.0, book_ask=102.0, binance_mid=0.0,
    )


def run(events, window_min: float = 0.0, match: str = "fifo"):
    """events: (second, our side, contracts). One sample a second, so every fill gets a 300 s markout."""
    trades = [
        # An aggressive sell below our bid fills it; an aggressive buy above our ask fills it.
        sim.Trade(ts=sec * 1000.0, price=98.5 if side == BUY else 101.5, size=size, aggressor=-side)
        for sec, side, size in events
    ]
    samples = [sample(k * 1000.0) for k in range(int(events[-1][0]) + 302)]
    res = sim.simulate(samples, trades, tick=0.5, cv=1.0, cfg=config(window_min, match))
    return res, sim.MidSeries(samples)


class ScalperOfferFees(unittest.TestCase):
    def fills(self, events, window_min=1.0, match="fifo"):
        fills = run(events, window_min, match)[0].fills
        self.assertEqual([(round(f.ts / 1000), f.side, f.qty) for f in fills], [(e[0], e[1], e[2]) for e in events])
        return fills

    def test_close_within_window_is_free_open_pays(self):
        opened, closed = self.fills([(1, BUY, 1), (31, SELL, 1)])
        self.assertAlmostEqual(opened.fee_offer, fee(1, BID))
        self.assertEqual(opened.free_qty, 0)
        self.assertEqual(closed.fee_offer, 0)
        self.assertEqual(closed.free_qty, 1)
        self.assertAlmostEqual(closed.fee, fee(1, ASK))  # the normal fee is unchanged

    def test_close_at_window_edge_is_free(self):
        _, closed = self.fills([(1, BUY, 1), (61, SELL, 1)])  # aged exactly 60 s
        self.assertEqual(closed.fee_offer, 0)

    def test_close_after_window_pays_full_fee(self):
        _, closed = self.fills([(1, BUY, 1), (62, SELL, 1)])  # aged 61 s
        self.assertAlmostEqual(closed.fee_offer, fee(1, ASK))
        self.assertEqual(closed.free_qty, 0)

    def test_partial_close(self):
        # Open 2 in one fill; close 1 inside the window (free), the other 1 after it (pays).
        _, first, second = self.fills([(1, BUY, 2), (30, SELL, 1), (90, SELL, 1)])
        self.assertEqual(first.fee_offer, 0)
        self.assertAlmostEqual(second.fee_offer, fee(1, ASK))

    def test_fifo_matches_two_lots_of_different_age(self):
        # Lot A opened at 1 s (69 s old at the close, pays), lot B at 50 s (20 s old, free).
        *_, closed = self.fills([(1, BUY, 1), (50, BUY, 1), (70, SELL, 2)])
        self.assertEqual(closed.free_qty, 1)
        self.assertAlmostEqual(closed.fee_offer, fee(1, ASK))

    def test_flip_through_zero(self):
        # Long 1, then sell 2: the closing contract is free, the overshoot opens a short and pays.
        # Buying 1 back 10 s later closes that short inside the window, so it is free too.
        _, flip, cover = self.fills([(1, BUY, 1), (10, SELL, 2), (20, BUY, 1)])
        self.assertEqual(flip.free_qty, 1)
        self.assertAlmostEqual(flip.fee_offer, fee(1, ASK))
        self.assertEqual(cover.fee_offer, 0)

    def test_flat_is_stricter_than_fifo_while_old_position_stays_open(self):
        # Inventory is long from 1 s to 70 s without touching zero. The last close matches lot B
        # (opened 40 s, 30 s old): free under fifo, but the position episode is 69 s old under flat.
        events = [(1, BUY, 1), (40, BUY, 1), (50, SELL, 1), (70, SELL, 1)]
        fifo = self.fills(events, match="fifo")
        flat = self.fills(events, match="flat")
        self.assertEqual([f.free_qty for f in fifo], [0, 0, 1, 1])
        self.assertEqual([f.free_qty for f in flat], [0, 0, 1, 0])
        self.assertAlmostEqual(flat[3].fee_offer, fee(1, ASK))

    def test_flat_whole_fill_pays_when_episode_too_old(self):
        *_, closed = self.fills([(1, BUY, 1), (50, BUY, 1), (70, SELL, 2)], match="flat")
        self.assertEqual(closed.free_qty, 0)
        self.assertAlmostEqual(closed.fee_offer, fee(2, ASK))

    def test_knob_off_matches_todays_fees_and_fills(self):
        events = [(1, BUY, 1), (10, SELL, 2), (20, BUY, 1), (400, SELL, 1)]
        off = run(events)[0].fills
        on = run(events, window_min=15)[0].fills
        for f in off:
            self.assertEqual(f.fee, f.notional * FEE_BPS / 1e4)
            self.assertIsNone(f.fee_offer)
            self.assertEqual(f.free_qty, 0)
        # The offer only adds a second fee; it never changes which fills happen.
        self.assertEqual(
            [(f.ts, f.side, f.price, f.qty, f.notional, f.fee) for f in off],
            [(f.ts, f.side, f.price, f.qty, f.notional, f.fee) for f in on],
        )

    def test_unknown_match_rule_rejected(self):
        with self.assertRaises(ValueError):
            run([(1, BUY, 1)], window_min=1, match="lifo")


class ScalperOfferSummary(unittest.TestCase):
    EVENTS = [(1, BUY, 1), (10, SELL, 2), (20, BUY, 1)]  # notional 99 + 202 + 99 = 400, 200 of it free

    def test_summary_reports_with_and_without(self):
        res, mids = run(self.EVENTS, window_min=15)
        s = sim.summarize(res, mids, 1.0)
        self.assertEqual(s["scored"], 3)
        self.assertAlmostEqual(s["fee"], FEE_BPS)
        self.assertAlmostEqual(s["free_share"], 0.5)
        self.assertAlmostEqual(s["fee_offer"], FEE_BPS / 2)  # 1.06 bps: half the notional was a free close
        self.assertAlmostEqual(s["net60_offer"] - s["net60"], FEE_BPS / 2)
        self.assertAlmostEqual(s["net300_offer"] - s["net300"], FEE_BPS / 2)
        saved = fee(1, ASK) + fee(1, BID)
        self.assertAlmostEqual(s["pnl_fees_offer"], s["pnl_fees"] + saved)
        self.assertAlmostEqual(s["pnl_total_offer"], s["pnl_total"] + saved)

    def test_summary_keys_unchanged_when_off(self):
        res, mids = run(self.EVENTS)
        s = sim.summarize(res, mids, 1.0)
        self.assertEqual(
            set(s),
            {"fills", "scored", "days", "fills_per_day", "usd_per_day", "uptime", "inside", "capture", "mo",
             "fee", "net60", "net300", "pnl_total", "pnl_spread", "pnl_fees", "pnl_inventory", "final_inv"},
        )

    def test_offer_on_with_no_fills_still_reports(self):
        res = sim.simulate([sample(0.0), sample(1000.0)], [], tick=0.5, cv=1.0, cfg=config(15))
        s = sim.summarize(res, sim.MidSeries([sample(0.0)]), 1.0)
        self.assertEqual((s["fee_offer"], s["free_share"], s["pnl_total_offer"]), (0.0, 0.0, 0.0))


class EndToEnd(unittest.TestCase):
    """A run dir in the recorder's formats: dry-run.log.gz (MM_METRICS lines) + delta_mainnet_public_<day>.jsonl."""

    T0 = 1_791_500_000_000  # ms

    def write_run(self, d: str) -> None:
        with gzip.open(os.path.join(d, "dry-run.log.gz"), "wt") as f:
            f.write("2026-10-09T00:00:00.000Z  WARN mm_bot: not a metrics line\n")
            for k in range(700):
                m = {
                    "symbol": "ADAUSDT", "fair": 100.0, "bid": BID, "ask": ASK, "place_bid": True,
                    "place_ask": True, "regime_level": 0, "ts_ms": self.T0 + k * 1000,
                    "book_bid": 98.0, "book_ask": 102.0, "binance_mid": 100.0,
                }
                f.write(f"2026-10-09T00:00:00.000Z  INFO MM_METRICS: {json.dumps(m)}\n")
        tape = [(5, SELL, 1), (20, BUY, 1), (40, BUY, 1), (100, SELL, 1), (300, SELL, 1), (310, BUY, 1)]
        with open(os.path.join(d, "delta_mainnet_public_20261009.jsonl"), "w") as f:
            f.write('{"recv_us": 1, "msg": {"type": "subscriptions"}}\n')
            for sec, aggressor, size in tape:
                ts = self.T0 + sec * 1000
                msg = {"type": "trades", "sy": "ADAUSD", "p": "101.5" if aggressor > 0 else "98.5", "s": size,
                       "r": "t" if aggressor > 0 else "m", "t": (ts - 1000) * 1000}
                f.write(json.dumps({"recv_us": ts * 1000, "msg": msg}) + "\n")

    def report(self, *extra: str) -> list[str]:
        out = io.StringIO()
        argv = ["--run-dir", self.dir, "--latency-ms", "20", "--sweep", "5", "--quote-usd", "100", *extra]
        with mock.patch.object(sim, "product_meta", return_value=(0.5, 1.0)), contextlib.redirect_stdout(out):
            sim.main(argv)
        return out.getvalue().splitlines()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.write_run(self.dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cli_with_and_without_offer(self):
        off = self.report()
        on = self.report("--scalper-window-min", "15")
        flat = self.report("--scalper-window-min", "15", "--scalper-match", "flat")
        self.assertNotIn("onet60", "\n".join(off))
        self.assertNotIn("Scalper", "\n".join(off))
        rows_off = [r for r in off if r.startswith(("bot quotes", "fair +/-"))]
        rows_on = [r for r in on if r.startswith(("bot quotes", "fair +/-"))]
        self.assertEqual(len(rows_off), 2)
        self.assertEqual(len(rows_on), 2)
        self.assertTrue(any("onet60" in r for r in on))
        self.assertTrue(any("Scalper Offer: 15 min window, fifo" in r for r in on))
        self.assertTrue(any("Scalper Offer: 15 min window, flat" in r for r in flat))
        # Same base columns and verdict; the offer columns sit between fee$ and the verdict.
        for a, b in zip(rows_off, rows_on):
            base, _, verdict = a.rpartition("  ")
            self.assertTrue(b.startswith(base), (a, b))
            self.assertTrue(b.endswith("  " + verdict), (a, b))
            self.assertGreater(len(b), len(a))
        # 6 fills; each of the 3 closes comes within 15 min of its open: $301 of $600 free -> free% 50%.
        bot_on = rows_on[0].split()
        self.assertEqual(bot_on[0:3], ["bot", "quotes", "20ms"])
        self.assertEqual(bot_on[3], "6")
        self.assertIn("50%", rows_on[0])


if __name__ == "__main__":
    unittest.main()
