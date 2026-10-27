#!/usr/bin/env python3
"""Offline QA of the carry-forward fix (27 Oct 2026, owner's option 2). Runs trend_paper.step() on synthetic data
through four rebalances (normal; BTC and ETH funding unpublished; every coin unpublished; all published again) with
the tests' fake of Delta's endpoint, then audits the journal with funding_audit.py against a candle dump of the same
rates: once complete, once cut before the recovery (its windows must show PENDING), and twice tampered (a wrong
late rate; a missing rate never carried), which must FAIL. Run from this folder: python3 carry_forward_qa.py"""
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / "scripts"))
import test_trend_paper as t  # noqa: E402
import trend_backtest as tb  # noqa: E402
import trend_paper as tp  # noqa: E402

now = t.NOW
closes, books, cvals = t.synthetic(now)
s = tp.init_state(5000.0, now)
rows = [tp.step(s, closes, books, {}, cvals, now)]
when = now
for k, down in enumerate([(), ("BTC", "ETH"), tuple(tb.COINS), ()], 1):
    when = now + dt.timedelta(k)
    for c in tb.COINS:
        closes[c][when.date() - dt.timedelta(1)] = closes[c][now.date() - dt.timedelta(1)] * (1 + 0.01 * k)
    with mock.patch.object(tp, "fetch", t.FakeFunding(t.block_rate, down=down)), mock.patch.object(tp.time, "sleep"):
        det = tp.fetch_funding(s["last_rebalance_ts"], int(when.timestamp()), s.get("funding_pending", []))
    rows.append(tp.step(s, closes, books, tp.funding_owed(det), cvals, when, funding_detail=det))
    print(f"day {k}, unpublished {','.join(down) or 'none'}: funding ${rows[-1]['funding']:.6f}, "
          f"{len(rows[-1]['funding_pending'])} carried, {len(rows[-1]['funding_late'])} settled late")
X = 8 * 3600
t0, t1 = int(now.timestamp()) // X * X - X, int(when.timestamp()) + 3600
candles = {c: {str(h): t.block_rate(c, h // X * X) for h in range(t0, t1, 3600)} for c in tb.COINS}
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    json.dump({"cvals": cvals, "candles": candles}, open(tmp / "candles.json", "w"))
    bad_rate = json.loads(json.dumps(rows))
    bad_rate[-1]["funding_late"][0]["rate"] += 0.001
    uncarried = json.loads(json.dumps(rows))
    uncarried[2]["funding_pending"] = [x for x in uncarried[2]["funding_pending"] if x["coin"] != "BTC"]
    cases = {"complete": (rows, 0), "cut before the recovery": (rows[:-1], 0),
             "tampered: wrong late rate": (bad_rate, 1), "tampered: a missing rate never carried": (uncarried, 1)}
    for name, (journal, want) in cases.items():
        path = tmp / (name.split(":")[0].replace(" ", "_") + str(want) + ".json")
        json.dump(journal, open(path, "w"))
        r = subprocess.run([sys.executable, "-I", str(HERE.parent / "funding_audit.py"), str(path), "--candles",
                            str(tmp / "candles.json")], capture_output=True, text=True)
        print(f"\n=== {name}: exit {r.returncode} ({'as expected' if r.returncode == want else 'UNEXPECTED'})")
        print("\n".join(x for x in r.stdout.splitlines()[1:] if x.strip()))
