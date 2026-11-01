"""Tests for the bitra-desk Telegram notifier: run with
python3 -m unittest discover -s bitra-desk/telegram -p 'test_*.py' -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import notify

NOW = datetime(2026, 11, 1, 6, 12, tzinfo=timezone.utc)  # 11:42 IST
TOKEN = "123456:secret-token-value"


def tmpdir(test: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="bitra-tg-"))
    test.addCleanup(shutil.rmtree, d, True)
    return d


def trade(entry_ms: int, net: float, side: str = "short") -> dict:
    return {"side": side, "setup": "range_breakout", "size": 0.004, "entry": 77932.1, "entry_ms": entry_ms,
            "exit": 77411.6, "exit_ms": entry_ms + 3_600_000, "exit_reason": "time limit", "net_usd": net,
            "net_bps": 54.0}


def state(equity: float, trades: list | None = None, open_: dict | None = None, service: str = "active",
          recent: list | None = None, model: str = "google:gemini-3.1-flash-lite", cost: float | None = None) -> dict:
    trades = trades or []
    return {
        "now": NOW, "model": model, "service": service, "total_cycles": 10,
        "counts": {"asked": 5, "held": 4, "would trade": 1},
        "paper": {"start_equity": 1000, "equity": equity, "return_pct": (equity / 1000 - 1) * 100,
                  "closed": len(trades), "wins": sum(t["net_usd"] > 0 for t in trades),
                  "losses": sum(t["net_usd"] <= 0 for t in trades), "trades": trades, "open": open_,
                  "equity_curve": [[t["exit_ms"], equity] for t in trades]},
        "hindsight": None, "usage": [],
        "cost": {"total_usd": cost, "today_usd": cost},
        "recent": recent or [],
    }


class DigestTest(unittest.TestCase):
    def test_ranked_by_equity_with_calls_and_cost(self):
        recent = [{"at": NOW - timedelta(minutes=40), "outcome": "refused", "target": "flat", "setup": "no_setup",
                   "confidence": 0.6}]
        states = {"gemini": state(1011.81, [trade(1793300000000, 11.81)]),
                  "groq": state(1000.0),
                  "claude": state(1000.5, model="claude:claude-opus-5-5", cost=0.31, recent=recent)}
        text = notify.digest_text(states, [(1793400000000, 77000.0), (1793486400000, 77478.6)], NOW,
                                  since=NOW - timedelta(hours=2))
        self.assertLess(text.index("gemini"), text.index("claude"))
        self.assertLess(text.index("claude"), text.index("groq"))
        self.assertIn("$1,011.81", text)
        self.assertIn("+1.18%", text)
        self.assertIn("77,478.6", text)
        self.assertIn("flat no_setup 0.60", text)
        self.assertIn("40 min ago", text)
        self.assertIn("Claude API ≈ $0.31", text)
        self.assertIn("bitra-desk.taildea8d9.ts.net", text)
        self.assertNotIn("⚠️", text)

    def test_escapes_text_and_warns_on_a_stopped_desk(self):
        recent = [{"at": NOW - timedelta(hours=1), "outcome": "refused", "target": "short", "setup": "<b>x</b>",
                   "confidence": 0.5}]
        text = notify.digest_text({"groq": state(1000.0, service="failed", recent=recent)}, [], NOW,
                                  since=NOW - timedelta(hours=2))
        self.assertNotIn("<b>x</b>", text)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", text)
        self.assertIn("⚠️ groq: service failed", text)

    def test_counts_only_cycles_since_the_last_digest(self):
        recent = [{"at": NOW - timedelta(minutes=30), "outcome": "refused", "target": "flat"},
                  {"at": NOW - timedelta(minutes=90), "outcome": "would trade", "target": "short"},
                  {"at": NOW - timedelta(hours=3), "outcome": "refused", "target": "flat"},
                  {"at": NOW - timedelta(minutes=50), "outcome": "held"}]
        text = notify.digest_text({"gemini": state(1000.0, recent=recent)}, [], NOW, since=NOW - timedelta(hours=2))
        self.assertIn("gemini asked 2 (1 would-be trade), held 1", text)


class EventsTest(unittest.TestCase):
    def test_first_run_records_without_alerting(self):
        alerts, seen = notify.events({"gemini": state(1005.0, [trade(1, 5.0)])}, {})
        self.assertEqual(alerts, [])
        self.assertEqual(seen["desks"]["gemini"]["trades"], ["1:short"])

    def test_new_close_new_open_and_service_change(self):
        _, seen = notify.events({"gemini": state(1005.0, [trade(1, 5.0)])}, {})
        opened = {"side": "long", "setup": "pullback_in_trend", "size": 0.003, "entry": 78000.0, "entry_ms": 9,
                  "stop": 77500.0, "take": 79000.0, "mark": 78100.0, "unrealized_usd": 0.3}
        now = {"gemini": state(1003.0, [trade(1, 5.0), trade(5, -2.0)], open_=opened, service="failed")}
        alerts, seen = notify.events(now, seen)
        text = "\n".join(alerts)
        self.assertEqual(len(alerts), 3)
        self.assertIn("gemini</b> closed SHORT", text)
        self.assertIn("−$2.00", text)
        self.assertIn("gemini</b> opened LONG 0.003 BTC at 78,000.0", text)
        self.assertIn("stop 77,500.0", text)
        self.assertIn("gemini desk is <b>failed</b>", text)
        again, _ = notify.events(now, seen)
        self.assertEqual(again, [])
        back, _ = notify.events({"gemini": state(1003.0, [trade(1, 5.0), trade(5, -2.0)], open_=opened)}, seen)
        self.assertEqual(len(back), 1)
        self.assertIn("running again", back[0])


class SendTest(unittest.TestCase):
    def test_errors_never_carry_the_token(self):
        orig = notify.urllib.request.urlopen

        def boom(req, timeout=None):
            raise urllib.error.URLError(f"cannot reach {req.full_url}")

        notify.urllib.request.urlopen = boom
        self.addCleanup(setattr, notify.urllib.request, "urlopen", orig)
        with self.assertRaises(notify.SendError) as ctx:
            notify.send(TOKEN, "42", "hi")
        self.assertNotIn(TOKEN, str(ctx.exception))
        self.assertIn("***", str(ctx.exception))

    def test_quiet_hours_are_ist_nights(self):
        self.assertTrue(notify.quiet(datetime(2026, 11, 1, 20, 30, tzinfo=timezone.utc)))  # 02:00 IST
        self.assertFalse(notify.quiet(NOW))  # 11:42 IST


class DiscoverTest(unittest.TestCase):
    def fake_updates(self, chats):
        orig = notify.api_get
        notify.api_get = lambda token, method: {"ok": True, "result": [
            {"update_id": i, "message": {"chat": {"id": cid, "type": kind}}} for i, (cid, kind) in enumerate(chats)]}
        self.addCleanup(setattr, notify, "api_get", orig)

    def test_one_private_chat_is_locked_in(self):
        env = tmpdir(self) / "telegram.env"
        env.write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\n")
        self.fake_updates([(42, "private"), (42, "private")])
        self.assertEqual(notify.discover_chat(TOKEN, env), "42")
        self.assertIn("TELEGRAM_CHAT_ID=42", env.read_text())
        self.assertIn(f"TELEGRAM_BOT_TOKEN={TOKEN}", env.read_text())

    def test_none_or_several_chats_lock_nothing(self):
        env = tmpdir(self) / "telegram.env"
        env.write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\n")
        self.fake_updates([])
        self.assertIsNone(notify.discover_chat(TOKEN, env))
        self.fake_updates([(1, "private"), (2, "private")])
        self.assertIsNone(notify.discover_chat(TOKEN, env))
        self.assertNotIn("TELEGRAM_CHAT_ID", env.read_text())


if __name__ == "__main__":
    unittest.main()
