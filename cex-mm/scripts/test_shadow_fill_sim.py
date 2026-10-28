#!/usr/bin/env python3
"""Tests for the Scalper Offer fee model in shadow_fill_sim.py (stdlib only).

    cd cex-mm/scripts && python3 -m unittest -v test_shadow_fill_sim

Hand-computed cases on a flat market: Delta book 98 / 102 (mid 100), our bid 99 and ask 101,
contract value 1, so a buy costs 99 * 2.12 / 1e4 per contract in fees and a sell 101 * 2.12 / 1e4.
"""
from __future__ import annotations

import contextlib
import datetime
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

    def test_flat_episode_restarts_when_position_reopens(self):
        # Flat at 10 s. The long opened at 100 s is a new episode, so closing it at 120 s is free,
        # although 119 s have passed since the first open.
        for match in ("fifo", "flat"):
            fills = self.fills([(1, BUY, 1), (10, SELL, 1), (100, BUY, 1), (120, SELL, 1)], match=match)
            self.assertEqual([f.free_qty for f in fills], [0, 1, 0, 1], match)

    def test_flat_flip_restarts_episode(self):
        # The flip at 50 s closes the long opened at 1 s (49 s old, free) and opens a short, a new
        # episode, so covering it at 100 s (50 s later, 99 s after the first open) is free too.
        for match in ("fifo", "flat"):
            fills = self.fills([(1, BUY, 1), (50, SELL, 2), (100, BUY, 1)], match=match)
            self.assertEqual([f.free_qty for f in fills], [0, 1, 1], match)

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


def ev_config(cancel_first: tuple[float, float] | None = None, latency: float = 700.0) -> sim.SimConfig:
    return sim.SimConfig(
        latency_ms=latency,
        half_spread_bps=None,
        rule="strict",
        quote_usd=200.0,  # 2 contracts per quote at price 100
        max_inv_orders=3,
        fee_bps=FEE_BPS,
        requote_tol_bps=3.0,
        max_gap_ms=1e12,
        loop_ms=400.0,
        cancel_first=cancel_first,
    )


def quotes(*rows: tuple[float, float, float]) -> list[sim.Sample]:
    """(ms, our bid, our ask) -> samples; the Delta book sits a point outside our quotes."""
    return [
        sim.Sample(ts=t, fair=(b + a) / 2, bid=b, ask=a, place_bid=True, place_ask=True,
                   regime=0, book_bid=b - 1, book_ask=a + 1, binance_mid=0.0)
        for t, b, a in rows
    ]


def tape(*rows: tuple[float, int, float, float]) -> list[sim.Trade]:
    """(ms, our side hit, price, contracts) -> trades."""
    return [sim.Trade(ts=t, price=p, size=q, aggressor=-side) for t, side, p, q in rows]


class CancelFirst(unittest.TestCase):
    """The event engine: edits land after --latency-ms; cancel-first takes an adverse quote off sooner."""

    def fills(self, samples, trades, cancel_first=None):
        res = sim.simulate_events(samples, trades, tick=0.5, cv=1.0, cfg=ev_config(cancel_first))
        return [(f.ts, f.side, f.price, f.qty) for f in res.fills]

    # The fair falls at 1 s: the bid should go 99 -> 97 (adverse), the ask 101 -> 99 (toward the market).
    FALL = quotes((0, 99, 101), (1000, 97, 99))

    def test_edit_leaves_the_stale_bid_until_the_edit_lands(self):
        trades = tape((1300, BUY, 98.0, 1), (1800, BUY, 96.5, 1))
        self.assertEqual(self.fills(self.FALL, trades), [(1300, BUY, 99, 1), (1800, BUY, 97, 1)])

    def test_cancel_first_pulls_the_stale_bid_after_the_cancel(self):
        # Cancel lands at 1070, the new bid at 1670: the 1300 sell finds no bid, the 1800 one fills at 97.
        trades = tape((1050, BUY, 98.0, 1), (1300, BUY, 98.0, 1), (1650, BUY, 96.5, 1), (1800, BUY, 96.5, 1))
        self.assertEqual(
            self.fills(self.FALL, trades, cancel_first=(70.0, 600.0)),
            [(1050, BUY, 99, 1), (1800, BUY, 97, 1)],
        )

    def test_move_toward_the_market_keeps_the_edit(self):
        # The ask improves 101 -> 99 by edit in both modes: still 101 at 1650, 99 from 1700.
        trades = tape((1650, SELL, 100.0, 1), (1750, SELL, 100.0, 1))
        for cf in (None, (70.0, 600.0)):
            self.assertEqual(self.fills(self.FALL, trades, cf), [(1750, SELL, 99, 1)], cf)

    def test_quote_filled_out_before_the_cancel_lands_is_not_replaced(self):
        # The bid fills out (2 contracts) at 1050, before the 1070 cancel: no replace at 1670. The bot
        # places again on the first sample a loop after the fill (2000), landing at 2700.
        samples = quotes((0, 99, 101), (1000, 97, 99), (2000, 97, 99))
        trades = tape((1050, BUY, 98.0, 2), (1700, BUY, 96.5, 1), (2500, BUY, 96.0, 1), (2800, BUY, 96.0, 1))
        self.assertEqual(
            self.fills(samples, trades, cancel_first=(70.0, 600.0)),
            [(1050, BUY, 99, 2), (2800, BUY, 97, 1)],
        )

    def test_no_new_decision_while_a_call_is_in_flight(self):
        # Placed at 0 (lands 700): the 400 sample waits, the 800 one edits 99 -> 97 (lands 1500).
        samples = quotes((0, 99, 101), (400, 98, 101), (800, 97, 101))
        trades = tape((1200, BUY, 97.5, 1), (1600, BUY, 96.5, 1))
        self.assertEqual(self.fills(samples, trades), [(1200, BUY, 99, 1), (1600, BUY, 97, 1)])

    def test_side_switched_off_is_pulled_after_the_latency(self):
        samples = quotes((0, 99, 101), (1000, 99, 101))
        samples[1].place_bid = False
        trades = tape((1500, BUY, 98.0, 1), (1800, BUY, 98.0, 1))
        self.assertEqual(self.fills(samples, trades), [(1500, BUY, 99, 1)])

    def test_no_samples_no_fills(self):
        self.assertEqual(self.fills([], tape((10, BUY, 98.0, 1))), [])


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

    def test_cli_cancel_first_adds_two_rows_per_config(self):
        off = self.report()
        on = self.report("--cancel-first", "10:15")
        self.assertEqual(len([r for r in off if r.startswith(("bot quotes", "fair +/-"))]), 2)
        self.assertNotIn("cancel-first", "\n".join(off).lower())
        rows = [r for r in on if r.startswith(("bot quotes", "fair +/-", "  edit", "  cancel"))]
        self.assertEqual(
            [r[:22].rstrip() for r in rows],
            ["bot quotes 20ms", "  edit 20ms", "  cancel-first 10+15",
             "fair +/- 5bps", "  edit 20ms", "  cancel-first 10+15"],
        )
        self.assertEqual(sum("cancel-first vs edit:" in r for r in on), 2)
        self.assertTrue(any(r.startswith("Cancel-first:") for r in on))
        # A flat market never moves a quote, so the bot-quote rows of both engines fill alike.
        self.assertEqual({r[22:].split()[0] for r in rows[:3]}, {"6"})

    def iso(self, sec: float) -> str:
        return datetime.datetime.fromtimestamp((self.T0 + sec * 1000) / 1000, datetime.timezone.utc).isoformat()

    def test_since_utc_drops_earlier_quotes_and_trades(self):
        full = [r for r in self.report() if r.startswith("bot quotes")][0]
        late = self.report("--since-utc", self.iso(50).replace("+00:00", "Z"))
        bot = [r for r in late if r.startswith("bot quotes")][0]
        self.assertEqual(full.split()[3], "6")
        self.assertEqual(bot.split()[3], "3")  # the trades at 100, 300 and 310 s
        self.assertIn("650 samples", "\n".join(late))
        self.assertTrue(any(r.startswith("Window: from 2026-") and "UTC" in r for r in late))
        self.assertFalse(any(r.startswith("Window:") for r in self.report()))

    def test_since_utc_naive_time_is_utc(self):
        bot = [r for r in self.report("--since-utc", self.iso(50)[:19]) if r.startswith("bot quotes")][0]
        self.assertEqual(bot.split()[3], "3")

    def test_since_utc_after_all_data_exits(self):
        with self.assertRaises(SystemExit) as cm:
            self.report("--since-utc", self.iso(10_000))
        self.assertIn("no MM_METRICS samples", str(cm.exception))

    def test_since_utc_rejects_bad_time(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.report("--since-utc", "yesterday")

    def test_cli_cancel_first_rejects_bad_spec(self):
        for bad in ("70", "70:", "a:600", "-5:600"):
            with self.assertRaises(SystemExit, msg=bad), contextlib.redirect_stderr(io.StringIO()):
                self.report("--cancel-first", bad)


if __name__ == "__main__":
    unittest.main()
