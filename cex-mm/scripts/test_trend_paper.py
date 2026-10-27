#!/usr/bin/env python3
"""Tests for trend_paper.py: python3 -m unittest test_trend_paper (from cex-mm/scripts)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

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


H, X = 3600, 8 * 3600  # an hour; Delta's funding interval (exchanges at 00:00, 08:00 and 16:00 UTC)
T = lambda *a: int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())  # noqa: E731


class FakeFunding:
    """Delta's /v2/history/candles for FUNDING:<sym>USD at resolution 1h, as measured on 26 Oct 2026: hourly candles,
    the value constant for the eight hours after each exchange stamp, newest first. The series starts at the first
    8-hour stamp at or after `start` (not at the first hour), ends at the last candle at or before `end`, and the
    endpoint sometimes answers an empty list. `rate(coin, stamp)` gives each exchange's rate in % per 8 h."""

    def __init__(self, rate, empty=(), down=()):
        self.rate, self.empty, self.down, self.calls = rate, list(empty), set(down), []

    def __call__(self, url: str):
        q = parse_qs(urlparse(url).query)
        coin = q["symbol"][0].removeprefix("FUNDING:").removesuffix("USD")
        start, end = int(q["start"][0]), int(q["end"][0])
        self.calls.append((coin, start, end))
        if coin in self.down:  # an outage: this series answers [] every time (as on 27 Oct 2026, all coins)
            return []
        if coin in self.empty:
            self.empty.remove(coin)  # one empty answer per listed occurrence
            return []
        first = -(-start // X) * X  # the first exchange stamp at or after start
        hours = range(first, end // H * H + 1, H)
        return [{"time": t, "open": self.rate(coin, t // X * X), "close": self.rate(coin, t // X * X)} for t in reversed(hours)]


def block_rate(coin: str, stamp: int) -> float:
    """A distinct rate for every coin and exchange, so a dropped or double-counted hour cannot cancel out."""
    return 0.001 * (1 + tb.COINS.index(coin)) + 0.0001 * ((stamp // X) % 97)


class Funding(unittest.TestCase):
    def test_exchanges_held_through(self):
        # The daily run: 25 Oct 00:05 -> 26 Oct 00:05 holds through 08:00, 16:00 and the 00:00 just before the run.
        self.assertEqual(tp.funding_exchanges(T(2026, 10, 25, 0, 5, 14), T(2026, 10, 26, 0, 5, 13)),
                         [T(2026, 10, 25, 8), T(2026, 10, 25, 16), T(2026, 10, 26)])
        # A stamp at the window start was settled before the position existed; one at the end was held through.
        self.assertEqual(tp.funding_exchanges(T(2026, 10, 25), T(2026, 10, 26)),
                         [T(2026, 10, 25, 8), T(2026, 10, 25, 16), T(2026, 10, 26)])
        # The first daily window (16:37 -> 00:05) and a weekly window (Monday 00:05 -> Monday 00:05).
        self.assertEqual(tp.funding_exchanges(T(2026, 10, 8, 16, 37), T(2026, 10, 9, 0, 5)), [T(2026, 10, 9)])
        self.assertEqual(len(tp.funding_exchanges(T(2026, 10, 19, 0, 5), T(2026, 10, 26, 0, 5))), 21)

    def fetched(self, fake, since, until, pending=()):
        with mock.patch.object(tp, "fetch", fake), mock.patch.object(tp.time, "sleep"):
            return tp.fetch_funding(since, until, pending)

    def test_each_exchange_charged_once_at_its_own_rate(self):
        # The bug of 8-26 Oct 2026: asking from 00:05 returns nothing before 08:00, so the old sum of hourly candles
        # / 8 charged the 08:00 and 16:00 exchanges and 1/8 of the 00:00 one.
        since, until = T(2026, 10, 25, 0, 5, 14), T(2026, 10, 26, 0, 5, 13)
        got = self.fetched(FakeFunding(block_rate), since, until)
        stamps = [T(2026, 10, 25, 8), T(2026, 10, 25, 16), T(2026, 10, 26)]
        self.assertEqual(got["exchanges"], stamps)
        self.assertEqual((got["since"], got["until"]), (since, until))
        for c in tb.COINS:
            self.assertEqual(got["rates"][c], [block_rate(c, s) for s in stamps], c)
        owed = tp.funding_owed(got)
        for c in tb.COINS:
            self.assertAlmostEqual(owed[c], sum(block_rate(c, s) for s in stamps) / 100, places=15, msg=c)
        self.assertEqual(tp.funding_owed(None), {})

    def test_long_window_spans_pages_without_gaps_or_doubles(self):
        # A catch-up after an outage longer than one 1999-hour page: each page start falls inside an 8-hour block.
        since, until = T(2026, 6, 1, 0, 5), T(2026, 10, 1, 0, 5)
        got = self.fetched(FakeFunding(block_rate), since, until)
        stamps = list(range(T(2026, 6, 1, 8), until + 1, X))
        self.assertEqual(got["exchanges"], stamps)
        self.assertEqual(got["rates"]["BTC"], [block_rate("BTC", s) for s in stamps])

    def test_empty_answer_is_asked_again_not_booked_as_zero(self):
        since, until = T(2026, 10, 25, 0, 5), T(2026, 10, 26, 0, 5)
        fake = FakeFunding(block_rate, empty=["LTC", "LTC", "DOGE"])
        got = self.fetched(fake, since, until)
        self.assertEqual(got["rates"]["LTC"], [block_rate("LTC", s) for s in got["exchanges"]])
        self.assertEqual(got["rates"]["DOGE"], [block_rate("DOGE", s) for s in got["exchanges"]])
        self.assertEqual(sum(1 for c, *_ in fake.calls if c == "LTC"), 3)

    def test_a_rate_still_missing_is_reported_missing_not_zero(self):
        # An outage (all FUNDING series empty on 27 Oct 2026 from some time after 00:20 UTC) must neither book zero
        # nor stop the rebalance: the stamp comes back as None, for step() to carry forward.
        fake = FakeFunding(block_rate, down=["BNB"])
        got = self.fetched(fake, T(2026, 10, 25, 0, 5), T(2026, 10, 26, 0, 5))
        self.assertEqual(got["rates"]["BNB"], [None, None, None])
        self.assertEqual(got["rates"]["BTC"], [block_rate("BTC", s) for s in got["exchanges"]])
        self.assertEqual(sum(1 for c, *_ in fake.calls if c == "BNB"), tp.FUNDING_TRIES)
        self.assertEqual(tp.funding_owed(got)["BNB"], 0.0)  # nothing booked now; step() carries it forward

    def test_pending_stamps_are_fetched_with_the_window(self):
        pending = [{"window": [1, 2], "coin": "ETH", "stamp": T(2026, 10, 24, 16), "notional": 10.0, "weight": 0.1}]
        got = self.fetched(FakeFunding(block_rate), T(2026, 10, 25, 0, 5), T(2026, 10, 26, 0, 5), pending)
        self.assertEqual(got["late_rates"], {"ETH": {T(2026, 10, 24, 16): block_rate("ETH", T(2026, 10, 24, 16))}})

    def test_journal_row_carries_what_it_charged_and_recomputes(self):
        closes, books, cvals = synthetic(NOW)
        s = tp.init_state(5000.0, NOW)
        rec0 = tp.step(s, closes, books, {}, cvals, NOW)
        self.assertEqual((rec0["funding_window"], rec0["funding_exchanges"], rec0["funding_rates"]), (None, [], {}))
        self.assertEqual((rec0["funding_late"], rec0["funding_pending"]), ([], []))
        nxt = NOW + dt.timedelta(1)
        for c in tb.COINS:
            closes[c][nxt.date() - dt.timedelta(1)] = closes[c][NOW.date() - dt.timedelta(1)]
        detail = self.fetched(FakeFunding(block_rate), s["last_rebalance_ts"], int(nxt.timestamp()))
        held = dict(s["positions"])
        rec = tp.step(s, closes, books, tp.funding_owed(detail), cvals, nxt, funding_detail=detail)
        self.assertEqual(rec["funding_window"], [detail["since"], detail["until"]])
        self.assertEqual(rec["funding_exchanges"], detail["exchanges"])
        self.assertEqual(rec["funding_rates"], detail["rates"])
        # An auditor needs only the row (and the previous row's positions) to redo the line.
        redo = sum(q * cvals[c] * rec["mids"][c] * sum(rec["funding_rates"][c]) / 100 for c, q in held.items())
        self.assertGreater(rec["funding"], 0)
        self.assertAlmostEqual(rec["funding"], redo, places=12)
        self.assertEqual((rec["funding_late"], rec["funding_pending"], s["funding_pending"]), ([], [], []))


class CarryForward(unittest.TestCase):
    """Funding Delta has not published yet is carried forward and booked at a later rebalance; the rebalance itself
    never waits for it (owner's choice, 27 Oct 2026)."""

    def fetched(self, fake, since, until, pending=()):
        with mock.patch.object(tp, "fetch", fake), mock.patch.object(tp.time, "sleep"):
            return tp.fetch_funding(since, until, pending)

    def book(self):
        closes, books, cvals = synthetic(NOW)
        s = tp.init_state(5000.0, NOW)
        tp.step(s, closes, books, {}, cvals, NOW)
        return s, closes, books, cvals

    def next_day(self, closes, when):
        for c in tb.COINS:
            closes[c][when.date() - dt.timedelta(1)] = closes[c][NOW.date() - dt.timedelta(1)]

    @staticmethod
    def owed(rec, held, cvals, rates):
        """What Delta's rule charges for one window: held notional at the rebalance mids x the exchanges' rates."""
        return sum(q * cvals[c] * rec["mids"][c] * sum(rates[c]) / 100 for c, q in held.items())

    def test_outage_rebalances_on_time_and_settles_later(self):
        s, closes, books, cvals = self.book()
        held1, w1 = dict(s["positions"]), dict(s["model_weights"])
        d1 = NOW + dt.timedelta(1)
        self.next_day(closes, d1)
        det1 = self.fetched(FakeFunding(block_rate, down=["BTC", "ETH"]), s["last_rebalance_ts"], int(d1.timestamp()))
        rec1 = tp.step(s, closes, books, tp.funding_owed(det1), cvals, d1, funding_detail=det1)
        self.assertEqual(s["last_rebalance"], d1.date().isoformat())  # the rebalance happened on time
        # Booked now: the coins whose rates were published. Carried: BTC and ETH, one entry per coin-exchange.
        booked = sum(q * cvals[c] * rec1["mids"][c] * sum(det1["rates"][c]) / 100 for c, q in held1.items() if c not in ("BTC", "ETH"))
        self.assertAlmostEqual(rec1["funding"], booked, places=12)
        pend = rec1["funding_pending"]
        self.assertEqual(sorted((p["coin"], p["stamp"]) for p in pend), sorted((c, e) for c in ("BTC", "ETH") for e in det1["exchanges"]))
        for p in pend:
            self.assertEqual(p["window"], [det1["since"], det1["until"]])
            self.assertAlmostEqual(p["notional"], held1[p["coin"]] * cvals[p["coin"]] * rec1["mids"][p["coin"]], places=12)
            self.assertEqual(p["weight"], w1[p["coin"]])
        self.assertEqual(s["funding_pending"], pend)
        self.assertIsNone(rec1["funding_rates"]["BTC"][0])

        # The series is back: the next rebalance books its own window and everything carried.
        held2 = dict(s["positions"])
        d2 = d1 + dt.timedelta(1)
        self.next_day(closes, d2)
        det2 = self.fetched(FakeFunding(block_rate), s["last_rebalance_ts"], int(d2.timestamp()), s["funding_pending"])
        rec2 = tp.step(s, closes, books, tp.funding_owed(det2), cvals, d2, funding_detail=det2)
        self.assertEqual(s["funding_pending"], [])
        self.assertEqual(rec2["funding_pending"], [])
        self.assertEqual(len(rec2["funding_late"]), len(pend))
        for x in rec2["funding_late"]:
            self.assertEqual(x["rate"], block_rate(x["coin"], x["stamp"]))
            self.assertAlmostEqual(x["amount"], x["notional"] * x["rate"] / 100, places=15)
        own = self.owed(rec2, held2, cvals, det2["rates"])
        self.assertAlmostEqual(rec2["funding"], own + sum(x["amount"] for x in rec2["funding_late"]), places=12)
        # Across the two rows, each window is charged exactly what Delta's rule says, just later for the first.
        full1 = {c: [block_rate(c, e) for e in det1["exchanges"]] for c in tb.COINS}
        self.assertAlmostEqual(rec1["funding"] + rec2["funding"], self.owed(rec1, held1, cvals, full1) + own, places=12)

    def test_settling_charges_the_model_its_carried_funding(self):
        s, closes, books, cvals = self.book()
        d1 = NOW + dt.timedelta(1)
        self.next_day(closes, d1)
        det1 = self.fetched(FakeFunding(block_rate, down=tb.COINS), s["last_rebalance_ts"], int(d1.timestamp()))
        tp.step(s, closes, books, tp.funding_owed(det1), cvals, d1, funding_detail=det1)
        self.assertTrue(s["funding_pending"])
        d2 = d1 + dt.timedelta(1)
        self.next_day(closes, d2)
        det2 = self.fetched(FakeFunding(block_rate), s["last_rebalance_ts"], int(d2.timestamp()), s["funding_pending"])
        still_down = {**det2, "late_rates": {}}
        a, b = copy.deepcopy(s), copy.deepcopy(s)
        ra = tp.step(a, closes, books, tp.funding_owed(det2), cvals, d2, funding_detail=det2)
        rb = tp.step(b, closes, books, tp.funding_owed(det2), cvals, d2, funding_detail=still_down)
        late_paid = sum(p["notional"] * block_rate(p["coin"], p["stamp"]) / 100 for p in s["funding_pending"])
        late_model = sum(p["weight"] * block_rate(p["coin"], p["stamp"]) / 100 for p in s["funding_pending"])
        self.assertGreater(late_model, 0)
        self.assertAlmostEqual(ra["funding"] - rb["funding"], late_paid, places=12)
        self.assertAlmostEqual(a["model_equity"] / b["model_equity"], 1 - late_model, places=12)
        self.assertEqual(b["funding_pending"], s["funding_pending"])  # still unpublished: still carried

    def test_order_list_counts_settlement_but_changes_nothing(self):
        s, closes, books, cvals = self.book()
        s["funding_pending"] = [{"window": [1, 2], "coin": "BTC", "stamp": T(2026, 10, 11, 16), "notional": 50.0, "weight": 0.05}]
        before = copy.deepcopy(s)
        det = {"since": s["last_rebalance_ts"], "until": s["last_rebalance_ts"], "exchanges": [], "rates": {},
               "late_rates": {"BTC": {T(2026, 10, 11, 16): 0.01}}}
        listed = tp.order_list(s, closes, books, {}, cvals, NOW, funding_detail=det)
        self.assertEqual(s, before)
        self.assertAlmostEqual(listed["funding"], 50.0 * 0.01 / 100, places=15)
        self.assertEqual(listed["unpublished"], 0)
        down = self.fetched(FakeFunding(block_rate, down=["BTC"]), s["last_rebalance_ts"], int((NOW + dt.timedelta(1)).timestamp()))
        self.next_day(closes, NOW + dt.timedelta(1))
        listed = tp.order_list(s, closes, books, tp.funding_owed(down), cvals, NOW + dt.timedelta(1), funding_detail=down)
        self.assertEqual(listed["unpublished"], len(down["exchanges"]))  # BTC's three exchanges
        self.assertEqual(s, before)

    def test_main_rebalances_through_an_outage_and_fetches_funding_before_books(self):
        now = dt.datetime.now(dt.timezone.utc)
        closes, books, cvals = synthetic(now)
        with tempfile.TemporaryDirectory() as tmp:
            s = tp.init_state(5000.0, now - dt.timedelta(1))
            tp.step(s, closes, books, {}, cvals, now - dt.timedelta(1))  # held since yesterday
            state_path = os.path.join(tmp, "state.json")
            with open(state_path, "w") as f:
                f.write(json.dumps(s))
            calls = []
            real_fetch_funding = tp.fetch_funding

            def spy_funding(*a):
                calls.append("funding")
                return real_fetch_funding(*a)

            def spy_book(c):
                calls.append("book")
                return books[c]

            argv = ["trend_paper.py", "--state-dir", tmp]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(tp, "fetch", FakeFunding(block_rate, down=tb.COINS)), \
                    mock.patch.object(tp.time, "sleep"), mock.patch.object(tp, "fetch_funding", spy_funding), \
                    mock.patch.object(tp, "fetch_book", spy_book), mock.patch.object(tp, "fetch_closes", lambda d: closes), \
                    mock.patch.object(tb, "contract_values", lambda: cvals), mock.patch("builtins.print"):
                tp.main()
            self.assertEqual(calls[0], "funding")
            self.assertTrue(all(x == "book" for x in calls[1:]) and len(calls) == 1 + len(tb.COINS))
            with open(os.path.join(tmp, "journal.jsonl")) as f:
                rows = [json.loads(x) for x in f]
            with open(state_path) as f:
                state = json.load(f)
            self.assertEqual(state["last_rebalance"], now.date().isoformat())
            self.assertEqual(rows[-1]["funding"], 0.0)
            self.assertEqual(len(rows[-1]["funding_pending"]), len(s["positions"]) * len(rows[-1]["funding_exchanges"])
                             + sum(1 for c, x in s["model_weights"].items() if x and c not in s["positions"]) * len(rows[-1]["funding_exchanges"]))
            self.assertEqual(state["funding_pending"], rows[-1]["funding_pending"])


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
