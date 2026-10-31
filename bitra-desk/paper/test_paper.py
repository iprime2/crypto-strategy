"""Tests for the bitra-desk paper account: run with
python3 -m unittest discover -s bitra-desk/paper -p 'test_*.py' -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import paper

T0 = paper.cycle_ms("2026-10-29T00-00-00Z-BTCUSDT")
B = paper.BAR_MS
HOLD = 12 * 3_600_000


def tmpdir(test: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bitra-paper-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def bars_from(ohlc: list[tuple[float, float, float, float]], start: int = T0) -> dict:
    return {start + i * B: bar for i, bar in enumerate(ohlc)}


def intent(at_ms: int, side: str = "short", stop: float = 101.0, take: float = 98.0, rt: float = 10.0) -> dict:
    return {"cycle": f"c{at_ms}", "at_ms": at_ms, "side": side, "size": 2.0, "stop": stop, "take": take,
            "round_trip_bps": rt, "setup": "range_reversion", "conviction": "0.6", "reason": "test"}


FLAT = (100.0, 100.2, 99.8, 100.0)


class SimulateTest(unittest.TestCase):
    def test_short_reaches_take(self):
        bars = bars_from([FLAT, (100.0, 100.1, 99.0, 99.2), (99.2, 99.3, 97.9, 98.1)])
        s = paper.simulate([intent(T0)], bars, HOLD, 10_000)
        t = s["trades"][0]
        self.assertEqual((t["exit_reason"], t["exit"], t["entry"]), ("take", 98.0, 100.0))
        self.assertAlmostEqual(t["gross_usd"], 4.0)  # (100 - 98) x 2
        self.assertAlmostEqual(t["cost_usd"], 0.2)  # 10 bps of 200
        self.assertAlmostEqual(s["equity"], 10_003.8)
        self.assertIsNone(s["open"])

    def test_bar_reaching_both_levels_counts_as_the_stop(self):
        bars = bars_from([FLAT, (100.0, 101.5, 97.5, 100.0)])
        t = paper.simulate([intent(T0)], bars, HOLD, 10_000)["trades"][0]
        self.assertEqual((t["exit_reason"], t["exit"]), ("stop", 101.0))
        self.assertAlmostEqual(t["net_usd"], -2.2)

    def test_long_closes_at_the_time_limit(self):
        n = HOLD // B + 5
        bars = bars_from([FLAT] * (n - 1) + [(100.0, 100.5, 99.9, 100.4)])
        bars[T0 + (HOLD // B - 1) * B] = (100.0, 100.5, 99.9, 100.3)  # the bar that ends at the limit
        t = paper.simulate([intent(T0, side="long", stop=95.0, take=110.0)], bars, HOLD, 10_000)["trades"][0]
        self.assertEqual(t["exit_reason"], "time limit")
        self.assertEqual(t["exit"], 100.3)
        self.assertEqual(t["exit_ms"], T0 + HOLD)

    def test_one_position_at_a_time(self):
        bars = bars_from([FLAT] * 3 + [(100.0, 100.1, 97.9, 98.0)] + [FLAT] * 10)
        s = paper.simulate([intent(T0), intent(T0 + B), intent(T0 + 8 * B)], bars, HOLD, 10_000)
        self.assertEqual(len(s["trades"]), 1)  # the first, closed at its take on bar 3
        self.assertEqual(s["skipped"], [{"cycle": f"c{T0 + B}", "side": "short", "why": "a short is already open"}])
        self.assertEqual(s["open"]["cycle"], f"c{T0 + 8 * B}")  # the third opened after the first closed

    def test_open_position_is_marked_to_the_last_close(self):
        bars = bars_from([FLAT, (100.0, 100.3, 99.4, 99.5)])
        s = paper.simulate([intent(T0)], bars, HOLD, 10_000)
        self.assertEqual(s["open"]["mark"], 99.5)
        self.assertAlmostEqual(s["unrealized_usd"], 0.8)  # (100 - 99.5) x 2 - 0.2
        self.assertAlmostEqual(s["equity"], 10_000.8)
        self.assertEqual(s["closed"], 0)

    def test_intent_without_a_bar_yet_waits(self):
        s = paper.simulate([intent(T0 + 10 * B)], bars_from([FLAT]), HOLD, 10_000)
        self.assertEqual(s["skipped"][0]["why"], "waiting for its first bar")
        self.assertEqual(s["equity"], 10_000)


class SizingTest(unittest.TestCase):
    def test_size_is_cut_to_the_risk_rule_on_this_equity(self):
        bars = bars_from([FLAT, (100.0, 100.1, 97.9, 98.0)])
        s = paper.simulate([intent(T0)], bars, HOLD, 100, risk_bps=50, size_step=0.001)
        t = s["trades"][0]
        # 50 bps of $100 is $0.50; the stop is 1.00 away plus 0.10 of round trip: 0.4545 -> 0.454
        self.assertEqual((t["size"], t["desk_size"]), (0.454, 2.0))
        self.assertAlmostEqual(t["net_usd"], 0.86)  # (100 - 98) x 0.454 - 10 bps of 45.4
        self.assertAlmostEqual(s["equity"], 100.86)

    def test_size_that_fits_is_kept(self):
        s = paper.simulate([intent(T0)], bars_from([FLAT]), HOLD, 1_000, risk_bps=50, size_step=0.001)
        self.assertEqual(s["open"]["size"], 2.0)  # 2 x 1.10 = 2.20 at the stop, under $5

    def test_trade_that_rounds_to_nothing_is_skipped(self):
        s = paper.simulate([intent(T0)], bars_from([FLAT]), HOLD, 1, risk_bps=50, size_step=0.01)
        self.assertIsNone(s["open"])
        self.assertTrue(s["skipped"][0]["why"].startswith("too small"))

    def test_desk_sizing_reads_the_desks_rule(self):
        d = tmpdir(self)
        self.assertEqual(paper.desk_sizing(d), (50.0, 0.001))
        (d / "strategy.toml").write_text("[run]\nsize_step = 0.01   # step\n[controls]\nmax_risk_per_trade_bps = 25\n")
        self.assertEqual(paper.desk_sizing(d), (25.0, 0.01))


class DataTest(unittest.TestCase):
    def test_parse_klines_sorts_and_refuses_errors(self):
        rows = paper.parse_klines({"retCode": 0, "result": {"list": [
            ["1000", "2", "3", "1", "2.5", "9", "9"], ["700", "1", "2", "0.5", "1.5", "9", "9"]]}})
        self.assertEqual(rows, [(700, 1.0, 2.0, 0.5, 1.5), (1000, 2.0, 3.0, 1.0, 2.5)])
        with self.assertRaises(ValueError):
            paper.parse_klines({"retCode": 10006, "retMsg": "Too many visits"})

    def test_entry_waits_for_the_finished_decision(self):
        d = tmpdir(self)
        (d / "index").mkdir()
        it = {"target": "short", "size": "0.01", "stop_price": "1", "take_price": "1", "priced_round_trip_bps": "13"}
        cid = "2026-10-29T03-00-00Z-BTCUSDT"
        (d / "index" / "x.jsonl").write_text(json.dumps({"cycle_id": cid, "intent": it}) + "\n")
        (d / cid).mkdir()
        (d / cid / "cycle.json").write_text(json.dumps({"finished_at": "2026-10-29T03:00:41.500000+00:00"}))
        got = paper.load_intents(d)[0]
        self.assertEqual(got["at_ms"], paper.cycle_ms(cid) + 41_500)
        bars = {paper.cycle_ms(cid) + i * B: FLAT for i in range(3)}
        s = paper.simulate([{**intent(0), "at_ms": got["at_ms"]}], bars, HOLD, 10_000)
        self.assertEqual(s["open"]["entry_ms"], paper.cycle_ms(cid) + B)  # not the bar that began before it

    def test_load_intents_dedupes_and_orders(self):
        d = tmpdir(self)
        (d / "index").mkdir()
        it = {"target": "short", "size": "0.005", "stop_price": "81795.30", "take_price": "79416.00",
              "priced_round_trip_bps": "13.0123", "setup": "range_reversion", "at": "ignored"}
        rows = [{"cycle_id": "2026-10-29T02-00-00Z-BTCUSDT", "intent": it},
                {"cycle_id": "2026-10-29T01-00-00Z-BTCUSDT", "intent": None},
                {"cycle_id": "2026-10-29T00-00-00Z-BTCUSDT", "intent": it},
                {"cycle_id": "2026-10-29T02-00-00Z-BTCUSDT", "intent": it}]
        (d / "index" / "2026-10-29.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        got = paper.load_intents(d)
        self.assertEqual([g["cycle"][:13] for g in got], ["2026-10-29T00", "2026-10-29T02"])
        self.assertEqual((got[0]["size"], got[0]["round_trip_bps"]), (0.005, 13.0123))

    def test_cache_fetches_only_the_missing_tail(self):
        d = tmpdir(self)
        calls = []

        def fake_fetch(symbol, start_ms, end_ms):
            calls.append((start_ms, end_ms))
            return [(t, 1.0, 1.0, 1.0, 1.0) for t in range(start_ms, end_ms + 1, B)]

        orig = paper.fetch_klines
        paper.fetch_klines = fake_fetch
        self.addCleanup(setattr, paper, "fetch_klines", orig)
        bars, err = paper.update_cache(d / "c.jsonl", "BTCUSDT", T0, T0 + 4 * B + 10)
        self.assertIsNone(err)
        self.assertEqual(sorted(bars), [T0, T0 + B, T0 + 2 * B, T0 + 3 * B])  # the bar from T0+4B is still forming
        paper.update_cache(d / "c.jsonl", "BTCUSDT", T0, T0 + 6 * B + 10)
        self.assertEqual(calls[-1], (T0 + 4 * B, T0 + 5 * B))  # only the bars closed since


if __name__ == "__main__":
    unittest.main()
