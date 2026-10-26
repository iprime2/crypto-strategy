#!/usr/bin/env python3
"""Audit a trend paper journal's funding line against Delta's published FUNDING:<sym> candles. Own code: it does not
import trend_paper.py. Public data only, no keys.

For every rebalance after the first it recomputes the funding the book owed over the holding window with three rules:
  old trader rule  what trend_paper.py did until 2026-10-26: hourly candles from the first 8-hour stamp at or after
                   `since` (all Delta returns for a window that starts inside a block) up to `until`, summed / 8
  all hours        hourly candles with since <= t < until, summed / 8 (the 26 Oct review's recompute)
  venue rule       one rate per funding exchange in (since, until]: the candle stamped at 00:00, 08:00 or 16:00
                   UTC, which is what Delta's ledger charges (matched 13 of 13 live ADA funding entries, 22-26 Oct)
A row that logs funding_rates (written since the 2026-10-26 fix) must also log exactly the published rates, and its
funding must equal the venue rule within --tol dollars.

    python3 funding_audit.py JOURNAL [JOURNAL ...] [--candles DUMP.json] [--save DUMP.json] [--tol 0.01]

JOURNAL is a journal.jsonl or a JSON array of rows. Exit status 1 if a row with logged rates fails.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.request

DELTA = "https://api.india.delta.exchange"
X, H = 8 * 3600, 3600
UTC = dt.timezone.utc


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "cex-mm-funding-audit/0.1"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["result"]


def fetch_candles(coins: list[str], t0: int, t1: int) -> dict[str, dict[int, float]]:
    """Hourly FUNDING closes per coin over [t0, t1]. t0 is put on an 8-hour stamp so no block is cut off, and an
    empty answer is asked again."""
    t0 = t0 // X * X
    out = {}
    for c in coins:
        got: dict[int, float] = {}
        for s in range(t0, t1 + 1, 1999 * H):
            for attempt in range(8):
                rows = get(f"{DELTA}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={s}&end={min(s + 1999 * H, t1)}")
                if rows:
                    break
                time.sleep(1 + attempt)
            got.update({r["time"]: float(r["close"]) for r in rows})
        out[c] = got
    return out


def load(path: str) -> list[dict]:
    text = open(path).read().strip()
    return json.loads(text) if text.startswith("[") else [json.loads(x) for x in text.splitlines() if x.strip()]


def ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp())


def rules(by: dict[int, float], since: int, until: int) -> dict[str, float]:
    first = -(-since // X) * X
    stamps = range((since // X + 1) * X, until + 1, X)
    return {"old": sum(v for t, v in by.items() if first <= t < until) / 800,
            "all": sum(v for t, v in by.items() if since <= t < until) / 800,
            "venue": sum(by[e] for e in stamps) / 100 if all(e in by for e in stamps) else float("nan")}


def audit(rows: list[dict], candles: dict, cvals: dict, tol: float, label: str) -> bool:
    ok = True
    tot = {"journal": 0.0, "old": 0.0, "all": 0.0, "venue": 0.0}
    print(f"\n{label}: {len(rows)} rows")
    print(f"{'rebalance':<17}{'journal':>10}{'old rule':>10}{'all hours':>10}{'venue':>10}  logged rates")
    for p, r in zip(rows, rows[1:]):
        win = r.get("funding_window")
        since, until = (win[0], win[1]) if win else (ts(p["time"]), int(dt.datetime.fromisoformat(r["time"]).timestamp()))
        per = {k: 0.0 for k in ("old", "all", "venue")}
        for c, q in p["positions"].items():
            amt = q * cvals[c] * r["mids"][c]
            for k, v in rules(candles[c], since, until).items():
                per[k] += amt * v
        note = "-"
        if "funding_rates" in r:
            stamps = r["funding_exchanges"]
            want = list(range((since // X + 1) * X, until + 1, X))
            bad = [c for c, rs in r["funding_rates"].items() if rs != [candles[c].get(e) for e in stamps]]
            gap = r["funding"] - per["venue"]
            good = stamps == want and not bad and abs(gap) <= tol
            ok &= good
            note = f"{'PASS' if good else 'FAIL'}: {len(stamps)} exchanges, rates {'match' if not bad else 'differ for ' + ','.join(bad)}, journal - venue {gap:+.2e} $"
        for k in tot:
            tot[k] += r["funding"] if k == "journal" else per[k]
        print(f"{r['time'][:16]:<17}{r['funding']:>10.4f}{per['old']:>10.4f}{per['all']:>10.4f}{per['venue']:>10.4f}  {note}")
    print(f"{'TOTAL':<17}{tot['journal']:>10.4f}{tot['old']:>10.4f}{tot['all']:>10.4f}{tot['venue']:>10.4f}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("journals", nargs="+")
    ap.add_argument("--candles", help="use a saved candle dump instead of fetching")
    ap.add_argument("--save", help="write the fetched candles here")
    ap.add_argument("--tol", type=float, default=0.01, help="dollars per interval")
    a = ap.parse_args()
    books = {j: load(j) for j in a.journals}
    coins = sorted({c for rows in books.values() for r in rows for c in r["mids"]})
    if a.candles:
        dump = json.load(open(a.candles))
        candles = {c: {int(t): v for t, v in d.items()} for c, d in dump["candles"].items()}
        cvals = dump["cvals"]
    else:
        t0 = min(ts(rows[0]["time"]) for rows in books.values()) - X
        t1 = max(ts(rows[-1]["time"]) for rows in books.values())
        candles = fetch_candles(coins, t0, t1)
        cvals = {c: float(get(f"{DELTA}/v2/products/{c}USD")["contract_value"]) for c in coins}
        if a.save:
            json.dump({"fetched_at": dt.datetime.now(UTC).isoformat(timespec="seconds"), "cvals": cvals,
                       "candles": candles}, open(a.save, "w"))
    ok = all([audit(rows, candles, cvals, a.tol, j) for j, rows in books.items()])
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
