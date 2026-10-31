"""Tests for the bitra-desk dashboard: run with
python3 -m unittest discover -s bitra-desk/dashboard -p 'test_*.py' -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import server

NOW = datetime(2026, 10, 29, 10, 30, tzinfo=timezone.utc)
INTENT = {"at": "2026-10-29T09-00-00Z-BTCUSDT", "target": "short", "setup": "range_reversion", "mid": "80972.05", "stop_price": "81795.30",
          "take_price": "79416.00", "conviction": "0.600", "priced_round_trip_bps": "13.0123",
          "break_even_win_rate": "0.390", "reason": "close above the window mean"}


def tmpdir(test: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bitra-dash-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def make_desk(test: unittest.TestCase, reason: str = "technical: confidence 0.55 below the declared 0.6") -> Path:
    desk = tmpdir(test)
    cycles = desk / "runs" / "cycles"
    (cycles / "index").mkdir(parents=True)
    rows = [
        {"cycle_id": "2026-10-29T07-00-00Z-BTCUSDT", "held": True, "intent": None, "seen": {"mid": "80100"}},
        {"cycle_id": "2026-10-29T08-00-00Z-BTCUSDT", "held": False, "intent": None, "seen": {"mid": "80200"}},
        {"cycle_id": "2026-10-29T09-00-00Z-BTCUSDT", "held": False, "intent": INTENT, "seen": {"mid": "80972.05"}},
        {"cycle_id": "2026-10-29T10-00-00Z-BTCUSDT", "held": False, "intent": None, "seen": {"mid": "80300"}},
        # a later record of the same cycle wins
        {"cycle_id": "2026-10-29T07-00-00Z-BTCUSDT", "held": True, "intent": None, "seen": {"mid": "80101"}},
    ]
    (cycles / "index" / "2026-10-29.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    cycle = {
        "cycle_id": "2026-10-29T08-00-00Z-BTCUSDT", "held": False, "tokens": 12465, "stopped_by": None,
        "refusals": [reason],
        "analyst": {"target": "short", "setup": "range_breakout", "confidence": 0.55, "reason": reason},
        "context": {"macro_analyst": {"regime": "risk-off", "reason": "both bearish", "data_as_of": "2026-10-24"},
                    "sentiment_analyst": {"state": "neutral", "reason": "fear_greed 51", "data_as_of": "2026-10-29"}},
        "series": [{"series": "us10y", "value": "4.99", "state": "bearish", "observed_at": "2026-10-27T00:00:00+00:00",
                    "age_h": 58.0, "source": "fred DGS10"}],
    }
    for cid, extra in (("2026-10-29T07-00-00Z-BTCUSDT", {"held": True, "refusals": ["trigger: quiet"]}),
                       ("2026-10-29T08-00-00Z-BTCUSDT", {}),
                       ("2026-10-29T09-00-00Z-BTCUSDT", {"refusals": []})):
        (cycles / cid).mkdir()
        (cycles / cid / "cycle.json").write_text(json.dumps({**cycle, "cycle_id": cid, **extra}))
    (cycles / "2026-10-29T10-00-00Z-BTCUSDT").mkdir()  # cut short: no cycle.json
    at = NOW.timestamp()
    usage = [{"at": at, "model": "gemini-3.1-flash-lite", "outcome": "ok", "input_tokens": 1000,
              "output_tokens": 200, "latency_ms": 20000},
             {"at": at, "model": "", "outcome": "error: ChainError", "input_tokens": 0, "output_tokens": 0}]
    (cycles / "usage.jsonl").write_text("".join(json.dumps(u) + "\n" for u in usage))
    (cycles / "hindsight.json").write_text(json.dumps({
        "days": 1, "independent": 1, "hold_s": 43200, "skipped": {"hold not over": 11},
        "admitted": {"decisions": 3, "mean_net_bps": "137.7", "won": "1.00"},
        "all_refused": {"decisions": 4, "mean_net_bps": "76.1", "won": "1.00", "verdict": "too few to tell"},
        "gates": [{"gate": "exit", "decisions": 3, "mean_net_bps": "36.9", "won": "1.0", "verdict": "too few to tell"}],
        "side": {"model_side": {"decisions": 7, "mean_net_bps": "102.5"},
                 "opposite_side": {"decisions": 7, "mean_net_bps": "-71.2"}, "verdict": "too few to tell"}}))
    return desk


class StateTest(unittest.TestCase):
    def test_counts_and_outcomes(self):
        s = server.build_state(make_desk(self), now=NOW, service="active")
        self.assertEqual(s["total_cycles"], 4)  # the duplicate record is one cycle
        self.assertEqual(s["counts"], {"held": 1, "asked": 2, "would trade": 1, "error (recent)": 1})
        self.assertEqual([x["outcome"] for x in s["recent"]], ["incomplete", "would trade", "refused", "held"])
        self.assertEqual(s["recent"][-1]["mid"], "80101")
        self.assertEqual(s["trades"][0]["target"], "short")
        self.assertEqual([a["role"] for a in s["analysts"]], ["macro", "sentiment", "technical"])
        self.assertEqual(s["series"][0]["series"], "us10y")
        self.assertEqual(s["next_pass"], datetime(2026, 10, 29, 11, 0, tzinfo=timezone.utc))

    def test_usage_counts_failures_and_models(self):
        day = server.build_state(make_desk(self), now=NOW, service="active")["usage"][0]
        self.assertEqual((day["calls"], day["ok"], day["errors"]), (2, 1, 1))
        self.assertEqual(day["models"], {"gemini-3.1-flash-lite": 1})
        self.assertEqual(day["median_latency_s"], 20.0)

    def test_empty_desk(self):
        s = server.build_state(tmpdir(self), now=NOW, service="inactive")
        self.assertEqual(s["total_cycles"], 0)
        self.assertIn("No analyst has answered yet", server.render(s))


class RenderTest(unittest.TestCase):
    def test_model_text_is_escaped(self):
        desk = make_desk(self, reason="<script>alert(1)</script> & more")
        page = server.render(server.build_state(desk, now=NOW, service="active"))
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more", page)

    def test_sections_present(self):
        page = server.render(server.build_state(make_desk(self), now=NOW, service="active"))
        for heading in ("What the analysts say now", "Would-be trades", "Hindsight", "Recent cycles", "Model use"):
            self.assertIn(heading, page)
        self.assertIn("-71.2", page)  # the reverse side from hindsight.json
        self.assertIn("39%", page)  # break-even win rate of the would-be trade


class PaperTest(unittest.TestCase):
    def test_paper_section(self):
        desk = make_desk(self)
        pdir = tmpdir(self)
        trade = {"cycle": "c", "side": "short", "setup": "range_reversion", "size": 0.005, "entry": 81300.0,
                 "entry_ms": 1793232000000, "stop": 81795.3, "take": 79416.0, "round_trip_bps": 13.0, "desk_size": 0.01,
                 "conviction": "0.6", "reason": "<b>x</b>", "exit": 80000.0, "exit_ms": 1793275200000,
                 "exit_reason": "time limit", "gross_usd": 6.5, "cost_usd": 0.53, "net_usd": 5.97, "net_bps": 146.9}
        (pdir / "state.json").write_text(json.dumps({
            "start_equity": 10000, "equity": 10005.97, "realized_usd": 5.97, "unrealized_usd": 0.0,
            "return_pct": 0.06, "closed": 1, "wins": 1, "losses": 0, "open": None, "trades": [trade],
            "skipped": [{"cycle": "d", "side": "short", "why": "a short is already open"}],
            "equity_curve": [[1793275200000, 10005.97]], "hold_hours": 12, "risk_bps": 50, "generated_ms": NOW.timestamp() * 1000,
            "fetch_error": None}))
        page = server.render(server.build_state(desk, now=NOW, service="active", paper_dir=pdir))
        for text in ("Paper account", "$10,005.97", "+0.06%", "time limit", "+$5.97", "12 h, net of", "Flat: no position open",
                     "0.005 BTC (desk 0.01)", "within 50 bps of equity"):
            self.assertIn(text, page)

    def test_paper_missing(self):
        page = server.render(server.build_state(make_desk(self), now=NOW, service="active", paper_dir=tmpdir(self)))
        self.assertIn("Paper account", page)
        self.assertIn("Not computed yet", page)


class DesksTest(unittest.TestCase):
    def test_parse_desk(self):
        g = server.parse_desk("groq=/home/u/bitra/desk-groq")
        self.assertEqual((g["name"], str(g["paper"]), g["unit"]), ("groq", "/home/u/bitra/paper-groq", "bitra-desk-groq"))
        c = server.parse_desk("claude=/home/u/bitra/desk-claude")  # the unit name bitra-dashboard.service relies on
        self.assertEqual((str(c["paper"]), c["unit"]), ("/home/u/bitra/paper-claude", "bitra-desk-claude"))
        d = server.parse_desk("/home/u/bitra/desk")
        self.assertEqual((d["name"], str(d["paper"]), d["unit"]), ("desk", "/home/u/bitra/paper", "bitra-desk"))

    def test_desk_model_reads_the_agents_table_only(self):
        desk = tmpdir(self)
        (desk / "strategy.toml").write_text(
            '[[channel]]\nname = "taker-taker"\n[agents]\nprovider = "groq"   # the vendor\n'
            'model = "openai/gpt-oss-120b"\n[agents.roles.x]\nmodel = "other"\n')
        self.assertEqual(server.desk_model(desk), "groq:openai/gpt-oss-120b")
        self.assertEqual(server.desk_model(tmpdir(self)), "")

    def test_comparison_and_desk_switch(self):
        root = tmpdir(self)
        a, b = make_desk(self), make_desk(self)
        desks = [{"name": "gemini", "path": a, "paper": root / "pa", "unit": "x"},
                 {"name": "groq", "path": b, "paper": root / "pb", "unit": "y"}]
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(desks))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        page = urllib.request.urlopen(base + "/").read().decode()
        self.assertIn("Model comparison", page)
        self.assertIn("<title>bitra-desk · gemini</title>", page)
        self.assertIn("href='?desk=groq#detail'", page)  # its card and its tab
        page = urllib.request.urlopen(base + "/?desk=groq").read().decode()
        self.assertIn("<title>bitra-desk · groq</title>", page)
        self.assertIn("<a class='tab' href='?desk=groq#detail' style='--c:var(--s2)' aria-current=page>", page)
        state = json.loads(urllib.request.urlopen(base + "/api/state.json?desk=groq").read())
        self.assertEqual(state["desk"], str(b))
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(base + "/?desk=nope")
        self.assertEqual(ctx.exception.code, 404)

    def test_single_desk_has_no_comparison(self):
        page = server.render(server.build_state(make_desk(self), now=NOW, service="active"))
        self.assertNotIn("Model comparison", page)


class OverviewDataTest(unittest.TestCase):
    def test_summary_carries_the_technical_answer_as_fields(self):
        s = server.build_state(make_desk(self), now=NOW, service="active")
        refused = next(x for x in s["recent"] if x["outcome"] == "refused")
        self.assertEqual((refused["target"], refused["setup"], refused["confidence"]), ("short", "range_breakout", 0.55))
        held = next(x for x in s["recent"] if x["outcome"] == "held")
        self.assertEqual(held["target"], "short")  # the fixture's held cycle still records an answer

    def test_candles_merge_dedupe_and_skip_bad_lines(self):
        a, b = tmpdir(self), tmpdir(self)
        (a / "candles.jsonl").write_text("[1000, 1, 2, 0.5, 1.5]\nnot json\n[2000, 1, 2, 0.5, 1.7]\n")
        (b / "candles.jsonl").write_text("[2000, 1, 2, 0.5, 1.7]\n[3000, 1, 2, 0.5, 1.9]\n")
        self.assertEqual(server.load_candles([a, b, tmpdir(self)]), [(1000, 1.5), (2000, 1.7), (3000, 1.9)])
        self.assertEqual(server.load_candles([a, b], since_ms=2000), [(2000, 1.7), (3000, 1.9)])

    def test_hourly_decisions_keep_the_most_telling_cycle_per_hour(self):
        h0 = datetime(2026, 10, 29, 8, 0, tzinfo=timezone.utc)
        recent = [  # newest first, as build_state returns them
            {"at": h0.replace(hour=9, minute=40), "outcome": "held"},
            {"at": h0.replace(hour=9, minute=5), "outcome": "would trade", "target": "short"},
            {"at": h0.replace(minute=30), "outcome": "held"},
            {"at": h0.replace(minute=0), "outcome": "refused", "target": "flat"},
        ]
        slots = server.hourly_decisions(recent, NOW, hours=4)
        self.assertEqual([x["hour"].hour for x in slots], [7, 8, 9, 10])
        self.assertIsNone(slots[0]["cycle"])
        self.assertEqual(slots[1]["cycle"]["target"], "flat")  # asked beats held
        self.assertEqual(slots[2]["cycle"]["outcome"], "would trade")
        self.assertIsNone(slots[3]["cycle"])

    def test_api_cost_prices_known_models_only(self):
        rows = [{"at": NOW.timestamp(), "model": "claude-opus-5-5", "outcome": "ok",
                 "input_tokens": 1_000_000, "output_tokens": 100_000},
                {"at": NOW.timestamp() - 2 * 86400, "model": "claude-sonnet-5-5", "outcome": "ok",
                 "input_tokens": 500_000, "output_tokens": 0}]
        cost = server.api_cost(rows, NOW)
        self.assertAlmostEqual(cost["total_usd"], 4.0 + 2.0 + 1.0)
        self.assertAlmostEqual(cost["today_usd"], 6.0)
        free = server.api_cost([{"at": NOW.timestamp(), "model": "gemini-3.1-flash-lite", "input_tokens": 9}], NOW)
        self.assertIsNone(free["total_usd"])

    def test_script_json_cannot_close_its_script_tag(self):
        out = server.script_json({"reason": "</script><script>alert(1)</script> & <b>"})
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertEqual(json.loads(out)["reason"], "</script><script>alert(1)</script> & <b>")


class OverviewRenderTest(unittest.TestCase):
    def states(self, reason="technical: confidence 0.55 below the declared 0.6"):
        pdir = tmpdir(self)
        (pdir / "state.json").write_text(json.dumps({
            "start_equity": 1000, "equity": 1004.5, "realized_usd": 4.5, "unrealized_usd": 0.0, "return_pct": 0.45,
            "closed": 1, "wins": 1, "losses": 0, "open": None, "skipped": [], "hold_hours": 12, "risk_bps": 50,
            "equity_curve": [[1793232000000, 1004.5]], "generated_ms": NOW.timestamp() * 1000, "fetch_error": None,
            "trades": [{"side": "short", "setup": "x", "entry": 80000.0, "entry_ms": 1793200000000, "exit": 79000.0,
                        "exit_ms": 1793232000000, "exit_reason": "take", "size": 0.004, "desk_size": 0.004,
                        "net_usd": 4.5, "net_bps": 120.0, "reason": reason}]}))
        a = server.build_state(make_desk(self, reason), now=NOW, service="active", paper_dir=pdir)
        b = server.build_state(make_desk(self), now=NOW, service="failed")
        return {"gemini": a, "groq": b}

    def test_leaderboard_grid_and_charts(self):
        page = server.render_overview(self.states(), "groq", [(1793200000000, 80000.0), (1793203600000, 79500.0)], NOW)
        self.assertIn("Model comparison", page)
        self.assertIn("$1,004.50", page)
        self.assertIn("href='?desk=gemini#detail'", page)
        self.assertEqual(page.count("class='cell"), 2 * server.GRID_HOURS)
        data = json.loads(page.split("<script type='application/json' id='chart-data'>")[1].split("</script>")[0])
        self.assertEqual([d["name"] for d in data["desks"]], ["gemini", "groq"])
        self.assertEqual(data["desks"][0]["trades"][0]["side"], "short")
        self.assertEqual(data["price"][-1], [1793203600000, 79500.0])

    def test_overview_escapes_model_text(self):
        page = server.render_overview(self.states("<img src=x onerror=alert(1)>"), "gemini", [], NOW)
        self.assertNotIn("<img src=x", page)


class HttpTest(unittest.TestCase):
    def test_routes(self):
        desk = make_desk(self)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(desk))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        with urllib.request.urlopen(base + "/") as r:
            self.assertEqual(r.status, 200)
            self.assertIn("text/html", r.headers["Content-Type"])
        with urllib.request.urlopen(base + "/api/state.json") as r:
            self.assertEqual(json.loads(r.read())["total_cycles"], 4)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(base + "/../.env")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
