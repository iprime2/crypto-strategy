"""Tests for live_vs_shadow.py (no network, no keys). CI runs it on ubuntu (pr.yml, Python script tests);
locally:

    cd cex-mm/scripts && python3 -m unittest -v test_live_vs_shadow
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
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
                 symbol: str = "ADAUSDT", inventory: float = 0.0, fair: float = 100.0, binance_mid: float = 100.0) -> str:
    m = {"symbol": symbol, "fair": fair, "bid": bid, "ask": ask, "inventory": inventory, "regime_level": 0,
         "place_bid": True, "place_ask": True, "ts_ms": int(ts), "book_bid": book_bid, "book_ask": book_ask,
         "binance_mid": binance_mid}
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

    def test_stops_at_a_cached_fill_and_returns_only_new_rows(self):
        pages = [{"success": True, "result": [fill_row("2026-10-12T08:00:03Z", "buy", "1", fid="9"),
                                              fill_row("2026-10-12T08:00:02Z", "buy", "1", fid="8")], "meta": {"after": "x"}},
                 {"success": True, "result": [fill_row("2026-10-12T08:00:01Z", "buy", "1", fid="7")], "meta": {"after": "y"}}]
        calls = []
        get = lambda p, q: (calls.append(q), pages[len(calls) - 1])[1]  # noqa: E731
        rows = lvs.fetch_fills(get, 1, since_ms=0, known_ids={"8"})
        self.assertEqual([r["id"] for r in rows], ["9"])
        self.assertEqual(len(calls), 1)
        merged = lvs.merge_fills([fill_row("2026-10-12T08:00:02Z", "buy", "1", fid="8")], rows)
        self.assertEqual([r["id"] for r in merged], ["9", "8"])

    def test_page_cap_raises_instead_of_truncating_and_keeps_the_rows(self):
        page = {"success": True, "result": [fill_row("2026-10-12T08:00:03Z", "buy", "1")], "meta": {"after": "z"}}
        with mock.patch.object(lvs.time, "sleep"), self.assertRaises(lvs.FillsIncomplete) as cm:
            lvs.fetch_fills(lambda p, q: page, 1, since_ms=0, max_pages=3)
        self.assertIn("3 pages", str(cm.exception))
        self.assertEqual(len(cm.exception.rows), 3)

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
    def test_uptime_and_inside(self):
        live = [sim.Sample(T0 + i * 400, 100, 99.9, 100.1, True, i != 2, 0, 99.8, 100.2, 100) for i in range(5)]
        quoted, inside = lvs.quote_time(live)
        self.assertEqual(quoted, 1200)  # 4 gaps of 400 ms, one with the ask off
        self.assertEqual(inside, 1200)

    def test_live_span_falls_back_to_a_full_scan(self):
        d = Path(tempfile.mkdtemp())
        p = d / "bot.log"
        p.write_text(metrics_line(T0, inventory=200) + metrics_line(T0 + 1000) + "WARN stale book\n" * 50)
        with mock.patch.object(lvs, "TAIL_BYTES", 100):
            self.assertEqual(lvs.live_span([str(p)], "ADAUSDT"), (T0, T0 + 1000, 200.0))
        self.assertEqual(lvs.inventory_at([str(p)], "ADAUSDT", T0 + 500), 0.0)


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
    # Binance flat at 100.0 but ticking for one second every 10 min, like a live feed (a mid unchanged for over
    # BINANCE_STALE_MS is a frozen feed). No markout of the real fills lands on a tick.
    (shadow / "dry-run.log").write_text("".join(
        metrics_line(T0 + i * 1000 + 100, binance_mid=100.0001 if i % 600 == 450 else 100.0)
        for i in range(-3600, n + 400)))
    # Aggressive sells through 99.9 and buys through 100.1 every 20 s, from an hour before the live start to 10 min
    # into it; local recv 1 s after exchange time.
    trades = [trade_line(T0 - 3_600_000 + k * 20_000, T0 - 3_601_000 + k * 20_000, 99.85 if k % 2 == 0 else 100.15, 5,
                         k % 2 == 1) for k in range(210)]
    (shadow / "delta_mainnet_public_20261012.jsonl").write_text("".join(trades))
    return live, shadow


def iso(ms: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class Compare(unittest.TestCase):
    def test_real_fills_vs_the_pre_live_baseline_on_both_references(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        # Two real maker fills (local = exchange + 1 s), plus ones that must not count.
        rows = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", commission=str(99.9 * 2 * 2.12e-4), fid="a"),
                fill_row(iso(T0 + 29_000), "sell", "100.1", size="2", commission=str(100.1 * 2 * 2.12e-4), fid="b"),
                fill_row(iso(T0 - 3_600_000), "sell", "100.1", size="2", fid="old"),
                fill_row(iso(T0 + 39_000), "buy", "99.9", size="2", symbol="KITEUSD", fid="kite"),
                dict(fill_row(iso(T0 + 49_000), "sell", "100.1", size="2", fid="adl"), fill_type="adl"),
                fill_row(iso(T0 + 2_000_000), "sell", "100.1", size="2", fid="late"),
                fill_row(iso(T0 + 59_000), "hold", "100.1", size="2", fid="junk")]
        out = lvs.compare(live, [shadow], rows, latencies=[20, 300], tick=0.05, cv=1.0)
        self.assertEqual(out["window"]["clock_offset_ms"], 1000)
        self.assertTrue(out["window"]["whole_run"])
        self.assertEqual(set(out["rows"]), {"real", "sim baseline 20ms", "sim baseline 300ms"})
        real = out["rows"]["real"]
        self.assertEqual(real["fills"], 2)
        self.assertEqual(real["maker_pct"], 100.0)
        self.assertAlmostEqual(real["fee"], 2.12, places=6)
        self.assertIsNone(real["inside"])  # our own quotes are the book: not measurable
        # Binance reference: flat 100.0 and zero basis, so capture is the distance to 100 and markouts are 0.
        self.assertEqual(out["basis_bps"], 0.0)
        cap = ((100 - 99.9) / 99.9 * 199.8 + (100.1 - 100) / 100.1 * 200.2) / 400 * 1e4
        self.assertAlmostEqual(real["bcapture"], cap, places=6)
        self.assertAlmostEqual(real["bmo60"], 0.0, places=9)
        self.assertAlmostEqual(real["bnet60"], cap - 2.12, places=6)
        self.assertEqual(out["fills"], {"total": 5, "used": 2, "before_window": 1, "after_window": 1, "no_mid": 0,
                                        "unparsed": 1, "other_types": {"adl": 1}})
        self.assertEqual(out["stop"]["fills"], 2)
        self.assertEqual(out["baseline"]["shadow_runs"], [shadow.name])
        # The baseline ends 300 s before the live start and lasts 1 h (the 15 min window is below the minimum),
        # clipped by the shadow's start an hour before the live run: 164 trades through our quotes, each a fill.
        b = out["baseline"]
        self.assertAlmostEqual(b["t1"], T0 - 300_000, delta=1000)
        self.assertAlmostEqual(b["t0"], T0 - 3_600_000, delta=1000)
        self.assertEqual(b["tape_trades"], 164)
        for lat in (20, 300):
            r = out["rows"][f"sim baseline {lat}ms"]
            self.assertEqual(r["fills"], 164)
            self.assertIsNotNone(r["bnet60"])
        self.assertEqual(out["sizing"], {"order_contracts": 2, "max_inv_orders": 3})
        text = lvs.format_table(out)
        self.assertIn("1 adl fill(s) excluded", text)
        self.assertIn("live stop rule: CONTINUE (2/300 real fills)", text)
        # PnL per $ traded: bought 2 @ 99.9, sold 2 @ 100.1, flat, minus fees.
        self.assertAlmostEqual(real["pnl_bps"], (0.4 - 400 * 2.12e-4) / 400 * 1e4, places=6)

    def test_a_partial_window_says_so_and_reports_the_inventory_there(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        logp = live / "bot.log"
        logp.write_text(logp.read_text().replace('"inventory":0.0', '"inventory":200.0'))
        rows = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", fid="early"),
                fill_row(iso(T0 + 609_000), "sell", "100.1", size="2", fid="late")]
        out = lvs.compare(live, [shadow], rows, latencies=[300], tick=0.05, cv=1.0, since_ms=T0 + 600_000)
        self.assertAlmostEqual(out["window"]["t0"], T0 + 600_000, delta=1000)
        self.assertFalse(out["window"]["whole_run"])
        self.assertEqual(out["rows"]["real"]["fills"], 1)
        self.assertEqual(out["inventory_at_window_start"], 200.0)
        # The baseline still sits before the live run's start, not before the window.
        self.assertLess(out["baseline"]["t1"], T0)
        self.assertIn("[this window only", lvs.format_table(out))

    def test_without_a_binance_mid_the_b_columns_are_marked_unavailable(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        sl = shadow / "dry-run.log"
        sl.write_text(re.sub(r'"binance_mid":[0-9.]+', '"binance_mid":null', sl.read_text()))
        out = lvs.compare(live, [shadow], [], latencies=[300], tick=0.05, cv=1.0)
        self.assertIsNone(out["basis_bps"])
        self.assertIsNone(out["rows"]["real"]["bnet60"])
        self.assertIn("the b* columns are unavailable", lvs.format_table(out))

    def test_calibrated_stop_rule(self):
        out = lambda n, bps, whole=True: {"window": {"whole_run": whole}, "stop": {"fills": n, "pnl_bps": bps}}  # noqa: E731
        self.assertTrue(lvs.stop_rule(out(299, -9.0)).startswith("CONTINUE (299/300 real fills)"))
        self.assertTrue(lvs.stop_rule(out(300, -0.4)).startswith("OK: real PnL -0.40"))  # above -2.6 early on
        self.assertTrue(lvs.stop_rule(out(300, -2.7)).startswith("STOP: real PnL -2.70 bps per $ traded over 300 fills"))
        self.assertTrue(lvs.stop_rule(out(1000, -0.1)).startswith("STOP: real PnL -0.10"))  # below 0 after 1,000
        self.assertTrue(lvs.stop_rule(out(1000, 0.3)).startswith("OK: real PnL +0.30"))
        self.assertIn("[this window only", lvs.stop_rule(out(300, 1.0, whole=False)))

    def test_a_frozen_binance_feed_is_not_a_basis(self):
        # The 8-12 Oct 2026 failure: Binance stuck (last change at 2 s) while Delta moves from 100 to 110.
        stale_s = int(lvs.BINANCE_STALE_MS / 1000)
        last_fresh = stale_s + 2
        samples = [sim.Sample(T0 + i * 1000, 100, 99.9, 100.1, True, True, 0, 99.95 + 10 * (i > last_fresh),
                              100.05 + 10 * (i > last_fresh), 95.5 if i == 1 else 95.0) for i in range(3 * stale_s)]
        # Only samples up to BINANCE_STALE_MS after the last change count, all with Delta at 100.
        self.assertAlmostEqual(lvs.basis_bps(samples), (100 / 95 - 1) * 1e4, places=9)
        ref = lvs.RefSeries(samples)
        self.assertEqual(ref.at(T0 + 1000), 95.5)
        self.assertEqual(ref.at(T0 + last_fresh * 1000), 95.0)  # unchanged for exactly BINANCE_STALE_MS: fresh
        self.assertIsNone(ref.at(T0 + 2 * stale_s * 1000))  # frozen, though a sample exists at that time

    def test_stop_rule_counts_fills_the_shadow_missed_marked_at_the_live_mid(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        sl = shadow / "dry-run.log"  # the shadow goes down 5 min into the live run
        sl.write_text("".join(l for l in sl.read_text().splitlines(keepends=True)
                              if json.loads(l[l.index("{"):])["ts_ms"] < T0 + 300_000))
        rows = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", commission="0", fid="a"),
                fill_row(iso(T0 + 600_000), "buy", "99.0", size="2", commission="0", fid="b")]  # no shadow mid
        out = lvs.compare(live, [shadow], rows, latencies=[300], tick=0.05, cv=1.0)
        self.assertEqual(out["fills"]["no_mid"], 1)
        self.assertEqual(out["stop"]["fills"], 2)
        # Bought 2 @ 99.9 and 2 @ 99.0, marked at the live bot's last mid 100.0.
        self.assertAlmostEqual(out["stop"]["pnl_usd"], 2 * (100 - 99.9) + 2 * (100 - 99.0), places=9)

    def test_baseline_skips_time_another_live_run_was_quoting(self):
        base = Path(tempfile.mkdtemp())
        live, shadow = write_runs(base)
        other = live.parent / "20261012T070000Z"  # an earlier live run that stopped 30 min before this one
        other.mkdir()
        (other / "bot.log").write_text("".join(metrics_line(T0 - 2_400_000 + i * 1000) for i in range(600)))
        out = lvs.compare(live, [shadow], [], latencies=[300], tick=0.05, cv=1.0)
        # It ended at T0 - 1801 s; the baseline starts after it + the DMS TTL + the 300 s gap.
        self.assertGreaterEqual(out["baseline"]["t0"], T0 - 1_801_000 + 15_000 + 300_000)

    def test_baseline_uses_only_the_shadow_run_checked_at_start(self):
        base = Path(tempfile.mkdtemp())
        live, shadow = write_runs(base)
        newer = shadow.parent / "20261012T075500Z"  # another run over the same hour, with its own tape
        newer.mkdir()
        (newer / "dry-run.log").write_text((shadow / "dry-run.log").read_text())
        (newer / "delta_mainnet_public_20261012.jsonl").write_text("")
        cfg = live / "config.txt"
        cfg.write_text(cfg.read_text() + f"shadow_run={shadow.name}\n")
        out = lvs.compare(live, [newer, shadow], [], latencies=[300], tick=0.05, cv=1.0)
        self.assertEqual(out["baseline"]["shadow_runs"], [shadow.name])
        self.assertEqual(out["baseline"]["tape_trades"], 164)

    def test_no_baseline_when_the_shadow_started_with_the_live_run(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        sl = shadow / "dry-run.log"
        sl.write_text("".join(l for l in sl.read_text().splitlines(keepends=True)
                              if json.loads(l[l.index("{"):])["ts_ms"] >= T0 - 60_000))
        out = lvs.compare(live, [shadow], [], latencies=[300], tick=0.05, cv=1.0)
        self.assertIsNone(out["baseline"])
        self.assertEqual(set(out["rows"]), {"real"})
        self.assertIn("no baseline", lvs.format_table(out))

    def test_main_offline_prints_the_table_and_json(self):
        base = Path(tempfile.mkdtemp())
        live, shadow = write_runs(base)
        (live / "fills.json").write_text("[]")
        buf = io.StringIO()
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(io.StringIO()):
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--offline"])
        text = buf.getvalue()
        self.assertIn("real (Delta fills)", text)
        self.assertIn("sim baseline 300ms", text)
        buf = io.StringIO()
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(io.StringIO()):
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--offline", "--json"])
        self.assertEqual(json.loads(buf.getvalue())["rows"]["real"]["fills"], 0)

    def test_offline_needs_fills_json_and_ends_the_window_at_its_time(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--offline"])
        self.assertIn("no ", str(cm.exception))
        out = lvs.compare(live, [shadow], [], latencies=[300], tick=0.05, cv=1.0, fills_until_ms=T0 + 300_000)
        self.assertAlmostEqual(out["window"]["t1"], T0 + 300_000, delta=1000)
        self.assertLessEqual(out["rows"]["real"]["uptime"], 1.0)

    def test_a_capped_fetch_still_saves_what_it_got(self):
        live, shadow = write_runs(Path(tempfile.mkdtemp()))
        env = live.parent / ".env"
        env.write_text("DELTA_MAINNET_API_KEY=k\nDELTA_MAINNET_API_SECRET=s\n")
        partial = [fill_row(iso(T0 + 9000), "buy", "99.9", size="2", fid="p1")]
        with mock.patch.object(lvs.sim, "product_meta", return_value=(0.05, 1.0)), \
                mock.patch.object(lvs, "product", return_value=(16614, 0.05, 1.0)), \
                mock.patch.object(lvs, "fetch_fills", side_effect=lvs.FillsIncomplete("capped", partial)), \
                self.assertRaises(SystemExit):
            lvs.main(["--live-dir", str(live), "--shadow-dir", str(shadow), "--env-file", str(env)])
        self.assertEqual([r["id"] for r in json.loads((live / "fills.json").read_text())], ["p1"])

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
        _, n = lvs.venue_report(get, product_id=16614, symbol="ADAUSD")
        self.assertEqual(n, 1)
        _, n = lvs.venue_report(lambda p, q="": {"success": False, "error": {"code": "x"}}, 16614, "ADAUSD")
        self.assertIsNone(n)  # unreadable is not "no orders"


if __name__ == "__main__":
    unittest.main()
