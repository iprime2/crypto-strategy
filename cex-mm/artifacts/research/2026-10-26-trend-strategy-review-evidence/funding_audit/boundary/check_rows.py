#!/usr/bin/env python3
"""Offline: the 27 Oct 00:05 rows against the FUNDING candles in the snapshot loop's 00:05 snapshot.
The VM's row (old code) must equal the old rule exactly; the fixed code's rows must log the published rate of each
exchange in (since, until] and charge their sum. Run from this folder: python3 check_rows.py"""
import datetime as dt
import json

X = 8 * 3600
UTC = dt.timezone.utc
CV = json.load(open("../candles_2026-10-26T1835Z.json"))["cvals"]
snaps = [json.loads(x) for x in open("local_snaps_2026-10-27.jsonl") if x.strip()]
ts = lambda s: int(dt.datetime.fromisoformat(s).timestamp())  # noqa: E731


def candles_at(t):
    """The last snapshot taken at or before t: what a fetch at t could have seen."""
    s = [x for x in snaps if "candles" in x and x["t"] <= t][-1]
    return {c: {int(a): b for a, b in rows} for c, rows in s["candles"].items()}, s["t"]


def check(path, label):
    p, r = json.load(open(path))
    since, until = ts(p["time"]), ts(r["time"])
    C, t_snap = candles_at(until)
    hm = lambda t: dt.datetime.fromtimestamp(t, UTC).strftime("%d %H:%M:%S")  # noqa: E731
    first = -(-since // X) * X
    stamps = list(range((since // X + 1) * X, until + 1, X))
    amt = {c: q * CV[c] * r["mids"][c] for c, q in p["positions"].items()}
    old = sum(a * sum(v for t, v in C[c].items() if first <= t < until) / 800 for c, a in amt.items())
    venue = sum(a * sum(C[c][e] for e in stamps) / 100 for c, a in amt.items())
    print(f"\n{label}: window {hm(since)} -> {hm(until)} UTC, exchanges {[hm(e) for e in stamps]}, candles from the {hm(t_snap)} snapshot")
    print(f"  journal {r['funding']:+.12f}   old rule {old:+.12f}   Delta's rule {venue:+.12f}")
    if "funding_rates" in r:
        ok_rates = r["funding_exchanges"] == stamps and all(r["funding_rates"][c] == [C[c][e] for e in stamps] for c in r["funding_rates"])
        print(f"  logged exchanges and rates equal the published candles: {ok_rates}; journal - Delta's rule {r['funding'] - venue:+.2e} $")
    else:
        print(f"  journal - old rule {r['funding'] - old:+.2e} $ (relative {abs(r['funding'] - old) / abs(old):.1e}); journal - Delta's rule {r['funding'] - venue:+.4f} $")


check("vm_daily_rows_2026-10-27T0005Z.json", "VM daily book, old code (deployed 2711fca)")
check("fixed_daily_rows_2026-10-27T0005Z.json", "Scratch daily book, fixed code, same starting state")
check("fixed_weekly_rows_2026-10-27T0005Z.json", "Scratch weekly book, fixed code (scratch state set due; the VM's weekly book was not due)")
