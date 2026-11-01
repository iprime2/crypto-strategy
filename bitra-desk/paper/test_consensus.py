"""Tests for the consensus account and the flat scores: run with
python3 -m unittest discover -s bitra-desk/paper -p 'test_*.py' -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import consensus
import paper

H0 = "2026-10-29T00-00-00Z-BTCUSDT"
T0 = paper.cycle_ms(H0)
B = paper.BAR_MS
HOUR = 3_600_000
HOLD = 12 * HOUR
FLAT = (100.0, 100.2, 99.8, 100.0)


def tmpdir(test: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bitra-cons-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def hour_id(h: int) -> str:
    return f"2026-10-29T{h:02d}-00-00Z-BTCUSDT"


def make_desk(root: Path, name: str, calls: list) -> Path:
    """calls: (hour, target, confidence, intent or None). Writes index rows, cycle.json and finished_at."""
    cycles = root / name / "runs" / "cycles"
    (cycles / "index").mkdir(parents=True)
    rows = []
    for h, target, conf, intent in calls:
        cid = hour_id(h)
        rows.append({"cycle_id": cid, "held": False, "intent": intent, "seen": {"mid": "100"}})
        (cycles / cid).mkdir()
        (cycles / cid / "cycle.json").write_text(json.dumps({
            "cycle_id": cid, "finished_at": f"2026-10-29T{h:02d}:00:30+00:00",
            "analyst": {"target": target, "setup": "range_reversion" if target != "flat" else "no_setup",
                        "confidence": conf}}))
    (cycles / "index" / "2026-10-29.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (root / name / "strategy.toml").write_text("[run]\nsize_step = 0.001\n[controls]\nmax_risk_per_trade_bps = 50\n")
    return root / name


def intent(side: str, conviction: str = "0.6", stop: float = 101.0, take: float = 98.0) -> dict:
    if side == "long":
        stop, take = 99.0, 102.0
    return {"target": side, "size": "2", "stop_price": str(stop), "take_price": str(take),
            "priced_round_trip_bps": "10", "setup": "range_reversion", "conviction": conviction, "reason": "r"}


def bars_from(hour_to_bars: dict) -> dict:
    """{hour: [(o,h,l,c), ...]} -> 5-minute bars; hours not named are flat."""
    out = {}
    for h in range(0, 24):
        seq = hour_to_bars.get(h, [FLAT] * 12)
        for i, bar in enumerate(seq):
            out[T0 + h * HOUR + i * B] = bar
    return out


class ConsensusIntentsTest(unittest.TestCase):
    def setUp(self):
        root = tmpdir(self)
        self.desks = [
            ("a", make_desk(root, "a", [(1, "short", 0.7, intent("short", "0.7")), (2, "short", 0.7, intent("short")),
                                        (3, "short", 0.5, None), (4, "long", 0.7, intent("long", "0.7"))])),
            ("b", make_desk(root, "b", [(1, "short", 0.5, None), (2, "flat", 0.2, None), (3, "short", 0.5, None),
                                        (4, "long", 0.9, intent("long", "0.9"))])),
            ("c", make_desk(root, "c", [(1, "flat", 0.6, None), (2, "flat", 0.6, None), (4, "flat", 0.6, None)])),
        ]

    def test_two_must_agree_and_one_must_have_passed_its_gates(self):
        taken = consensus.consensus_intents([(n, consensus.load_desk(p)) for n, p in self.desks])
        self.assertEqual([(t["hour"], t["side"], t["desk"]) for t in taken],
                         [("2026-10-29T01", "short", "a"),   # a + b agree, a passed its gates
                          ("2026-10-29T04", "long", "b")])   # a + b both passed; b's conviction 0.9 wins
        self.assertEqual(taken[0]["agreed"], ["a", "b"])
        self.assertEqual(taken[0]["at_ms"], T0 + HOUR + 30_000)  # the chosen desk's own decision time
        # hour 2: only a says short (b flat, c flat); hour 3: a and b agree but neither passed its gates

    def test_summary_counts_hours(self):
        loaded = [(n, consensus.load_desk(p)) for n, p in self.desks]
        s = consensus.hours_summary(loaded)
        self.assertEqual((s["hours_any"], s["hours_all"], s["agreed_hours"]), (4, 3, 3))  # hours 1, 3 and 4 agree


class FlatScoreTest(unittest.TestCase):
    def test_scores_the_others_trades_in_the_hours_a_desk_said_flat(self):
        root = tmpdir(self)
        a = make_desk(root, "a", [(1, "short", 0.7, intent("short")), (4, "long", 0.7, intent("long"))])
        b = make_desk(root, "b", [(4, "long", 0.9, intent("long")), (6, "short", 0.7, intent("short"))])
        c = make_desk(root, "c", [(1, "flat", 0.6, None), (4, "flat", 0.6, None), (6, "short", 0.6, None)])
        # hour 1 short wins (take at 98); hour 4 longs lose (stop at 99); hour 6 is not a flat hour for c
        bars = bars_from({1: [FLAT, (100.0, 100.1, 97.9, 98.0)] + [FLAT] * 10,
                          4: [FLAT, (100.0, 100.1, 98.9, 99.0)] + [FLAT] * 10})
        loaded = [(n, consensus.load_desk(p)) for n, p in (("a", a), ("b", b), ("c", c))]
        scores = consensus.flat_scores(loaded, bars, HOLD)
        c_score = scores["c"]
        self.assertEqual((c_score["flat_hours"], c_score["others_intents"], c_score["closed"]), (2, 3, 3))
        self.assertAlmostEqual(c_score["mean_net_bps"], (190 + -110 + -110) / 3, places=0)  # +200/-100 gross, 10 bps cost
        self.assertAlmostEqual(c_score["won"], 1 / 3, places=2)
        self.assertEqual(c_score["by_desk"], {"a": 2, "b": 1})
        self.assertEqual(scores["a"]["flat_hours"], 0)
        self.assertEqual(scores["a"]["others_intents"], 0)

    def test_an_intent_still_open_is_counted_but_not_scored(self):
        root = tmpdir(self)
        a = make_desk(root, "a", [(1, "short", 0.7, intent("short"))])
        c = make_desk(root, "c", [(1, "flat", 0.6, None)])
        bars = {T0 + HOUR + B: FLAT, T0 + HOUR + 2 * B: FLAT}  # two flat bars, the hold not over
        scores = consensus.flat_scores([(n, consensus.load_desk(p)) for n, p in (("a", a), ("c", c))], bars, HOLD)
        self.assertEqual((scores["c"]["others_intents"], scores["c"]["closed"], scores["c"]["mean_net_bps"]), (1, 0, None))


class BuildTest(unittest.TestCase):
    def test_build_runs_the_account_and_writes_everything_the_dashboard_reads(self):
        root = tmpdir(self)
        a = make_desk(root, "a", [(1, "short", 0.7, intent("short")), (3, "flat", 0.6, None)])
        b = make_desk(root, "b", [(1, "short", 0.6, None), (3, "long", 0.7, intent("long"))])
        bars = bars_from({1: [FLAT, (100.0, 100.1, 97.9, 98.0)] + [FLAT] * 10})
        state = consensus.build([(n, consensus.load_desk(p)) for n, p in (("a", a), ("b", b))], bars, HOLD, 1_000, 50, 0.001)
        self.assertEqual(state["closed"], 1)
        self.assertEqual(state["trades"][0]["exit_reason"], "take")
        self.assertEqual(state["trades"][0]["desk"], "a")
        self.assertEqual(state["desks"], ["a", "b"])
        self.assertEqual(state["rule"], consensus.RULE)
        self.assertEqual(len(state["taken"]), 1)
        self.assertIn("flat_scores", state)
        self.assertEqual(state["flat_scores"]["a"]["others_intents"], 1)  # b's long in hour 3, a said flat
        json.dumps(state)


if __name__ == "__main__":
    unittest.main()
