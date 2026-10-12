"""Tests for live_vs_shadow.py (no network, no keys). CI does not run Python; run:

    cd cex-mm/scripts && python3 -m unittest -v test_live_vs_shadow
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_vs_shadow as lvs  # noqa: E402
import shadow_fill_sim as sim  # noqa: E402

T0 = 1_791_800_000_000.0  # ms, local clock


def metrics_line(ts: float, bid: float = 99.9, ask: float = 100.1, book_bid: float = 99.8, book_ask: float = 100.2,
                 symbol: str = "ADAUSDT", inventory: float = 0.0, fair: float = 100.0) -> str:
    m = {"symbol": symbol, "fair": fair, "bid": bid, "ask": ask, "inventory": inventory, "regime_level": 0,
         "place_bid": True, "place_ask": True, "ts_ms": int(ts), "book_bid": book_bid, "book_ask": book_ask,
         "binance_mid": 100.0}
    return f"2026-10-12T08:00:00.000000Z  INFO MM_METRICS: {json.dumps(m, separators=(',', ':'))}\n"


def trade_line(recv_ms: float, exch_ms: float, price: float, size: float, buyer_taker: bool) -> str:
    msg = {"type": "trades", "sy": "ADAUSD", "p": str(price), "s": size, "r": "t" if buyer_taker else "m",
           "t": int(exch_ms * 1000)}
    return json.dumps({"recv_us": int(recv_ms * 1000), "msg": msg}) + "\n"


def fill_row(ts_iso: str, side: str, price: str, size="200", role: str = "maker", commission: str = "0.0424",
             symbol: str = "ADAUSD", fid: str = "1") -> dict:
    return {"id": fid, "side": side, "price": price, "size": size, "role": role, "commission": commission,
            "created_at": ts_iso, "product_symbol": symbol, "order_id": "9"}


class EnvValue(unittest.TestCase):
    def write(self, text: str) -> Path:
        d = tempfile.mkdtemp()
        p = Path(d) / ".env"
        p.write_text(text)
        return p

    def test_strips_double_quotes_spaces_and_takes_the_last_value(self):
        p = self.write('# c\nDELTA_MAINNET_API_KEY = "abc"\nOTHER=1\nDELTA_MAINNET_API_KEY="def"\n')
        self.assertEqual(lvs.env_value(p, "DELTA_MAINNET_API_KEY"), "def")

    def test_missing_key_comment_and_empty_are_none(self):
        p = self.write("#DELTA_MAINNET_API_SECRET=x\nDELTA_MAINNET_API_SECRET=\nNOEQUALS\n")
        self.assertIsNone(lvs.env_value(p, "DELTA_MAINNET_API_SECRET"))
        self.assertIsNone(lvs.env_value(p, "NOPE"))
        self.assertIsNone(lvs.env_value(Path("/nonexistent/.env"), "X"))

    def test_value_keeps_equals_signs(self):
        p = self.write("K=a=b=\n")
        self.assertEqual(lvs.env_value(p, "K"), "a=b=")


class ParseFill(unittest.TestCase):
    def test_parses_strings_side_role_fee_and_time(self):
        f = lvs.parse_fill(fill_row("2026-10-12T08:00:01.250000Z", "buy", "0.25", size="200"), cv=1.0)
        self.assertEqual(f.side, 1)
        self.assertEqual(f.contracts, 200.0)
        self.assertAlmostEqual(f.price, 0.25)
        self.assertAlmostEqual(f.fee, 0.0424)
        self.assertTrue(f.maker)
        self.assertEqual(f.ts, lvs.parse_iso_ms("2026-10-12T08:00:01.25Z"))
        g = lvs.parse_fill(fill_row("2026-10-12T08:00:01Z", "sell", "0.26", size=3, role="taker"), cv=1.0)
        self.assertEqual(g.side, -1)
        self.assertFalse(g.maker)

    def test_bad_rows_are_none(self):
        self.assertIsNone(lvs.parse_fill({"side": "buy"}, cv=1.0))
        self.assertIsNone(lvs.parse_fill(fill_row("2026-10-12T08:00:01Z", "hold", "0.25"), cv=1.0))
        self.assertIsNone(lvs.parse_fill(fill_row("not a time", "buy", "0.25"), cv=1.0))

    def test_iso_without_fraction_and_with_offset(self):
        self.assertEqual(lvs.parse_iso_ms("1970-01-01T00:00:01Z"), 1000.0)
        self.assertEqual(lvs.parse_iso_ms("1970-01-01T01:00:01+01:00"), 1000.0)


class FetchFills(unittest.TestCase):
    def test_pages_until_older_than_since_with_product_filter_and_encoded_cursor(self):
        pages = [
            {"success": True, "result": [fill_row("2026-10-12T08:00:03Z", "buy", "1", fid="3")], "meta": {"after": "a+b/="}},
            {"success": True, "result": [fill_row("2026-10-12T08:00:02Z", "buy", "1", fid="2"),
                                         fill_row("2026-10-12T07:00:00Z", "buy", "1", fid="1")], "meta": {"after": "c"}},
            {"success": True, "result": [fill_row("2026-10-12T06:00:00Z", "buy", "1", fid="0")], "meta": {"after": None}},
        ]
        calls = []

        def get(path, query):
            calls.append((path, query))
            return pages[len(calls) - 1]

        rows = lvs.fetch_fills(get, product_id=16614, since_ms=lvs.parse_iso_ms("2026-10-12T07:30:00Z"))
        self.assertEqual([r["id"] for r in rows], ["3", "2", "1"])  # the page that crossed `since` ends paging
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ("/v2/fills", "product_ids=16614&page_size=100"))
        self.assertEqual(calls[1][1], "product_ids=16614&page_size=100&after=a%2Bb%2F%3D")

    def test_failed_call_raises_with_the_error_code_only(self):
        with self.assertRaises(RuntimeError) as cm:
            lvs.fetch_fills(lambda p, q: {"success": False, "error": {"code": "ip_not_whitelisted"}}, 1, 0)
        self.assertIn("ip_not_whitelisted", str(cm.exception))


class Samples(unittest.TestCase):
    def test_filters_symbol_and_window_and_compacts_unchanged_samples(self):
        d = Path(tempfile.mkdtemp())
        lines = [metrics_line(T0 + i * 400) for i in range(10)]  # unchanged quotes, 400 ms apart
        lines.insert(3, metrics_line(T0 + 1000, symbol="KITEUSDT"))
        lines.append(metrics_line(T0 + 4100, bid=99.95))  # a change is always kept
        lines.append(metrics_line(T0 + 99_000))  # outside the window
        (d / "dry-run.log").write_text("".join(lines))
        out = lvs.load_samples([str(d / "dry-run.log")], "ADAUSDT", T0, T0 + 5000, heartbeat_ms=1000)
        ts = [s.ts - T0 for s in out]
        # kept: the first, one per second of unchanged quotes, the change
        self.assertEqual(ts, [0, 1200, 2400, 3600, 4100])
        self.assertEqual(out[-1].bid, 99.95)
        # default: full resolution, as the simulator reads it
        full = lvs.load_samples([str(d / "dry-run.log")], "ADAUSDT", T0, T0 + 5000)
        self.assertEqual(len(full), 11)

    def test_clock_offset_is_the_median_recv_minus_exchange(self):
        d = Path(tempfile.mkdtemp())
        p = d / "delta_mainnet_public_20261012.jsonl"
        p.write_text("".join(trade_line(T0 + i, T0 + i - off, 100, 1, True) for i, off in enumerate([900, 1000, 5000])))
        self.assertEqual(lvs.clock_offset_ms([str(p)], "ADAUSD", T0 - 10, T0 + 10), 1000)
        self.assertEqual(lvs.clock_offset_ms([str(p)], "KITEUSD", T0 - 10, T0 + 10), 0.0)


class RealMetrics(unittest.TestCase):
    def mids(self) -> sim.MidSeries:
        # Book mid 100 until +10 s, then 100.05 (buyer gains, seller loses).
        samples = [sim.Sample(ts=T0 + i * 1000, fair=100, bid=99.9, ask=100.1, place_bid=True, place_ask=True, regime=0,
                              book_bid=99.95 if i < 10 else 100.0, book_ask=100.05 if i < 10 else 100.1, binance_mid=100)
                   for i in range(400)]
        return sim.MidSeries(samples)

    def test_capture_markout_and_fee_for_a_buy_and_a_sell(self):
        fills = [lvs.RealFill("1", T0 + 2000, 1, 2.0, 99.9, 99.9 * 2 * 2.12e-4, True),
                 lvs.RealFill("2", T0 + 3000, -1, 2.0, 100.1, 100.1 * 2 * 2.12e-4, True)]
        sf = lvs.to_sim_fills(fills, offset_ms=0.0, mids=self.mids(), cv=1.0)
        res = sim.SimResult(fills=sf, span_ms=400_000, final_inv=0.0)
        s = sim.summarize(res, self.mids(), 1.0)
        self.assertEqual(s["scored"], 2)
        self.assertAlmostEqual(s["fee"], 2.12, places=6)
        cap_buy, cap_sell = (100 - 99.9) / 99.9 * 1e4, (100.1 - 100) / 100.1 * 1e4
        self.assertAlmostEqual(s["capture"], (cap_buy * 199.8 + cap_sell * 200.2) / 400, places=6)
        mo = 0.05 / 100 * 1e4  # +5 bps for the buyer, -5 bps for the seller
        self.assertAlmostEqual(s["mo"][60], (mo * 199.8 - mo * 200.2) / 400, places=6)
        self.assertAlmostEqual(s["pnl_fees"], -(99.9 + 100.1) * 2 * 2.12e-4, places=9)

    def test_exchange_time_is_shifted_onto_the_local_clock(self):
        fills = [lvs.RealFill("1", T0 + 9000, 1, 1.0, 99.9, 0.0, True)]
        sf = lvs.to_sim_fills(fills, offset_ms=2000.0, mids=self.mids(), cv=1.0)
        self.assertEqual(sf[0].ts, T0 + 11_000)
        self.assertAlmostEqual(sf[0].mid, 100.05)  # mid at the shifted time

    def test_fill_without_a_mid_is_dropped(self):
        fills = [lvs.RealFill("1", T0 - 60_000, 1, 1.0, 99.9, 0.0, True)]
        self.assertEqual(lvs.to_sim_fills(fills, 0.0, self.mids(), 1.0), [])


class QuoteStats(unittest.TestCase):
    def test_uptime_inside_and_agreement(self):
        live = [sim.Sample(T0 + i * 400, 100, 99.9, 100.1, True, i != 2, 0, 99.8, 100.2, 100) for i in range(5)]
        shadow = [sim.Sample(T0 + i * 400 + 50, 100, 99.9, 100.1 if i != 4 else 100.2, True, True, 0, 99.8, 100.2, 100)
                  for i in range(5)]
        quoted, inside = lvs.quote_time(live)
        self.assertEqual(quoted, 1200)  # 4 gaps of 400 ms, one with the ask off
        self.assertEqual(inside, 1200)
        same, total = lvs.quote_agreement(live, shadow, tick=0.05)
        self.assertEqual((same, total), (3, 5))  # one place flag differs, one ask differs


def write_runs(base: Path) -> tuple[Path, Path]:
    live, shadow = base / "live" / "20261012T080000Z", base / "shadow" / "20261012T070000Z"
    live.mkdir(parents=True)
    shadow.mkdir(parents=True)
    profile = ["MM_SYMBOLS=ADAUSDT", "MM_ORDER_QTY_ADAUSDT=2", "MM_MAX_INVENTORY_ADAUSDT=6",
               "MM_FIXED_HALF_SPREAD_BPS=5", "MM_MAKER_FEE_BPS=2.12", "MM_REQUOTE_TOL_BPS=3"]
    (live / "config.txt").write_text("symbols=ADAUSDT\nstarted_utc=2026-10-12T08:00:00Z\n" + "\n".join(profile) + "\n")
    (shadow / "config.txt").write_text("symbols=ADAUSDT\nstarted_utc=2026-10-12T07:00:00Z\n")
    n = 900  # 15 min of samples, flat 99.8/100.2 book, quotes 99.9/100.1
    (live / "bot.log").write_text("".join(metrics_line(T0 + i * 1000) for i in range(n)))
    (shadow / "dry-run.log").write_text("".join(metrics_line(T0 + i * 1000 + 100) for i in range(-5, n + 400)))
    # Aggressive sells through 99.9 and buys through 100.1, local recv 1 s after exchange time.
    trades = [trade_line(T0 + 10_000 + k * 20_000, T0 + 9000 + k * 20_000, 99.85 if k % 2 == 0 else 100.15, 5, k % 2 == 1)
              for k in range(30)]
    (shadow / "delta_mainnet_public_20261012.jsonl").write_text("".join(trades))
    return live, shadow


class Compare(unittest.TestCase):
    def test_real_and_simulated_rows_over_the_same_window(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        iso = lambda ms: __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc) \
            .isoformat().replace("+00:00", "Z")
        # Two real maker fills at exchange time (local = exchange + 1 s), one outside the window.
        rows = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", commission=str(99.9 * 2 * 2.12e-4), fid="a"),
                fill_row(iso(T0 + 29_000), "sell", "100.1", size="2", commission=str(100.1 * 2 * 2.12e-4), fid="b"),
                fill_row(iso(T0 - 3_600_000), "sell", "100.1", size="2", fid="old"),
                fill_row(iso(T0 + 39_000), "buy", "99.9", size="2", symbol="KITEUSD", fid="kite")]
        out = lvs.compare(live, [shadow], rows, latencies=[20, 300], tick=0.05, cv=1.0)
        self.assertEqual(out["window"]["clock_offset_ms"], 1000)
        real = out["rows"]["real"]
        self.assertEqual(real["fills"], 2)
        self.assertEqual(real["maker_pct"], 100.0)
        self.assertAlmostEqual(real["fee"], 2.12, places=6)
        sim_rows = {k: v for k, v in out["rows"].items() if k.startswith("sim")}
        self.assertEqual(set(sim_rows), {"sim shadow 20ms", "sim shadow 300ms", "sim live 20ms", "sim live 300ms"})
        self.assertGreater(sim_rows["sim shadow 300ms"]["fills"], 0)
        self.assertEqual(out["quotes"]["same"], out["quotes"]["compared"])
        self.assertEqual(out["sizing"], {"order_contracts": 2, "max_inv_orders": 3})

    def test_since_limits_the_window_and_drops_earlier_real_fills(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        iso = lambda ms: __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc) \
            .isoformat().replace("+00:00", "Z")
        rows = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", fid="early"),
                fill_row(iso(T0 + 609_000), "sell", "100.1", size="2", fid="late")]
        out = lvs.compare(live, [shadow], rows, latencies=[300], tick=0.05, cv=1.0, since_ms=T0 + 600_000)
        self.assertAlmostEqual(out["window"]["t0"], T0 + 600_000, delta=1000)
        self.assertEqual(out["rows"]["real"]["fills"], 1)

    def test_main_offline_prints_the_table_and_json(self):
        base = Path(tempfile.mkdtemp())
        live, shadow = write_runs(base)
        (live / "fills.json").write_text("[]")
        buf = io.StringIO()
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), contextlib.redirect_stdout(buf):
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--offline"])
        text = buf.getvalue()
        self.assertIn("real (Delta fills)", text)
        self.assertIn("sim shadow 300ms", text)
        buf = io.StringIO()
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), contextlib.redirect_stdout(buf):
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--offline", "--json"])
        self.assertEqual(json.loads(buf.getvalue())["rows"]["real"]["fills"], 0)

    def test_shadow_runs_are_picked_by_overlap_with_the_live_window(self):
        base = Path(tempfile.mkdtemp())
        sh = base / "shadow"
        for name in ["20261006T161427Z", "20261012T075609Z", "20261013T000000Z"]:
            (sh / name).mkdir(parents=True)
        (sh / "current").symlink_to(sh / "20261013T000000Z")
        t0 = lvs.parse_iso_ms("2026-10-12T08:00:00Z")
        t1 = lvs.parse_iso_ms("2026-10-12T20:00:00Z")
        self.assertEqual([p.name for p in lvs.shadow_runs_for(sh, t0, t1)], ["20261012T075609Z"])
        t1 = lvs.parse_iso_ms("2026-10-13T02:00:00Z")
        self.assertEqual([p.name for p in lvs.shadow_runs_for(sh, t0, t1)], ["20261012T075609Z", "20261013T000000Z"])


class Venue(unittest.TestCase):
    def test_venue_summary_reads_equity_position_and_orders(self):
        def get(path, query=""):
            if path == "/v2/wallet/balances":
                return {"success": True, "meta": {"net_equity": "294.1"}, "result": []}
            if path == "/v2/positions/margined":
                return {"success": True, "result": [{"size": -200, "entry_price": "0.2501"}]}
            if path == "/v2/orders":
                return {"success": True, "result": [{"side": "buy", "size": 200, "limit_price": "0.2498", "state": "open"}]}
            raise AssertionError(path)
        text = lvs.venue_text(get, product_id=16614, symbol="ADAUSD")
        self.assertIn("equity 294.1", text)
        self.assertIn("position ADAUSD -200 contracts", text)
        self.assertIn("buy 200 @ 0.2498", text)


if __name__ == "__main__":
    unittest.main()
