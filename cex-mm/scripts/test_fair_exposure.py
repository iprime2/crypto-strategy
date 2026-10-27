#!/usr/bin/env python3
"""Tests for fair_exposure.py: python3 -m unittest test_fair_exposure (from cex-mm/scripts)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fair_exposure as fe  # noqa: E402


def tmpdir(test: unittest.TestCase) -> Path:
    """A fresh temp directory, removed when `test` ends (pass or fail)."""
    d = Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    return d


T0 = 1_791_800_000_000


def run_lines(n: int = 600, step_at: int = 300, lag: int = 25) -> list[str]:
    """Binance steps +10 bps at `step_at`; the Delta book (5 bps below Binance) follows `lag` samples later.
    The logged fair is anchored (Binance x (1 - 5 bps), at once); fair_delta follows the lagging book."""
    lines = []
    for i in range(n):
        b = 100.0 if i < step_at else 100.1
        book_b = 100.0 if i < step_at + lag else 100.1
        book_mid = book_b * (1 - 5e-4)
        fair = b * (1 - 5e-4)
        m = {"symbol": "ADAUSDT", "ts_ms": T0 + i * 400, "fair": fair, "fair_delta": book_mid,
             "bid": fair * (1 - 5e-4), "ask": fair * (1 + 5e-4), "place_bid": True, "place_ask": i % 100 != 0,
             "binance_mid": b, "book_bid": book_mid - 0.01, "book_ask": book_mid + 0.01, "anchored": True}
        lines.append(f"2026-10-13T08:00:00Z  INFO MM_METRICS: {json.dumps(m)}\n")
    return lines


class Report(unittest.TestCase):
    def rows(self):
        d = tmpdir(self)
        (d / "dry-run.log").write_text("".join(run_lines()))
        return fe.load([str(d / "dry-run.log")], "ADAUSDT"), d

    def test_anchored_fair_is_never_exposed_and_the_lagging_one_is(self):
        rows, _ = self.rows()
        out = fe.report(rows, half_spread_bps=5.0, tol_bps=3.0, exposed_bps=1.0, window_min=20.0)
        self.assertAlmostEqual(out["basis_median_bps"], -5.0, places=6)
        logged, old = out["logged_fair"], out["fair_delta"]
        self.assertLess(logged["gap_p90_bps"], 0.01)
        self.assertEqual((logged["exposed_bid_pct"], logged["exposed_ask_pct"]), (0.0, 0.0))
        # After the up-step the lagging fair's ask sits below the new price for `lag` samples: 25 of 600.
        self.assertAlmostEqual(old["exposed_ask_pct"], 100 * 25 / 600, places=6)
        self.assertEqual(old["exposed_bid_pct"], 0.0)
        self.assertEqual(old["gap_p90_bps"], 0.0)  # lagging in only 4% of samples
        self.assertAlmostEqual(logged["one_sided_pct"], 100 * 6 / 600)  # place_ask false every 100th sample
        self.assertEqual(logged["anchored_pct"], 100.0)

    def test_a_long_lag_shows_in_the_gap_tail(self):
        d = tmpdir(self)
        (d / "dry-run.log").write_text("".join(run_lines(lag=120)))  # lagging in 20% of samples
        old = fe.report(fe.load([str(d / "dry-run.log")], "ADAUSDT"), 5.0, 3.0, 1.0, 20.0)["fair_delta"]
        self.assertAlmostEqual(old["gap_p90_bps"], 10.0, delta=0.01)

    def test_a_requote_tolerance_keeps_orders_resting(self):
        # With a 20 bps tolerance the old fair's ask never moves after the step: exposed for the whole tail.
        rows, _ = self.rows()
        old = fe.report(rows, 5.0, tol_bps=20.0, exposed_bps=1.0, window_min=20.0)["fair_delta"]
        self.assertAlmostEqual(old["exposed_ask_pct"], 100 * 300 / 600, places=6)

    def test_cli_prints_both_rows_and_refuses_a_thin_run(self):
        _, d = self.rows()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fe.main(["--run-dir", str(d)]), 0)
        text = buf.getvalue()
        self.assertIn("logged fair", text)
        self.assertIn("fair_delta (no anchor)", text)
        empty = tmpdir(self)
        (empty / "dry-run.log").write_text("".join(run_lines(n=50)))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fe.main(["--run-dir", str(empty)]), 2)

    def test_samples_with_a_silent_binance_feed_are_skipped(self):
        d = tmpdir(self)
        lines = [l.replace('"anchored": true', '"anchored": true, "binance_age_ms": 9000') if i % 10 == 0 else l
                 for i, l in enumerate(run_lines())]
        (d / "dry-run.log").write_text("".join(lines))
        self.assertEqual(len(fe.load([str(d / "dry-run.log")], "ADAUSDT")), 540)
        self.assertEqual(len(fe.load([str(d / "dry-run.log")], "ADAUSDT", max_binance_age_ms=1e9)), 600)

    def test_runs_before_fair_delta_was_logged_score_the_logged_fair_only(self):
        d = tmpdir(self)
        lines = [l.replace('"fair_delta"', '"x_fair_delta"') for l in run_lines()]
        (d / "dry-run.log").write_text("".join(lines))
        out = fe.report(fe.load([str(d / "dry-run.log")], "ADAUSDT"), 5.0, 3.0, 1.0, 20.0)
        self.assertEqual(out["fair_delta"], {"samples": 0})
        self.assertGreater(out["logged_fair"]["samples"], 0)


if __name__ == "__main__":
    unittest.main()
