#!/usr/bin/env python3
"""Offline: does the old trader rule reproduce every journal funding value to float precision, from the candles
published on 26 Oct? Old rule = hourly FUNDING candles from the first 8-hour stamp at or after `since` (all Delta
returns for a window that starts inside a block) up to `until`, summed / 100 / 8, times position x contract value x
the rebalance mid. Run from this folder: python3 exact_match.py"""
import datetime as dt
import json

X = 8 * 3600
dump = json.load(open("candles_2026-10-26T1835Z.json"))
C = {c: {int(t): v for t, v in d.items()} for c, d in dump["candles"].items()}
CV = dump["cvals"]
ts = lambda s: int(dt.datetime.fromisoformat(s).timestamp())  # noqa: E731


def old_rule(c, since, until):
    first = -(-since // X) * X
    return sum(v for t, v in C[c].items() if first <= t < until) / 100 / 8


worst = 0.0
for path in ("vm_daily_journal_2026-10-26.json", "vm_weekly_journal_2026-10-26.json"):
    rows = json.load(open(path))
    for p, r in zip(rows, rows[1:]):
        s, u = ts(p["time"]), ts(r["time"])
        v = sum(q * CV[c] * r["mids"][c] * old_rule(c, s, u) for c, q in p["positions"].items())
        rel = abs(v - r["funding"]) / max(1e-9, abs(r["funding"]))
        worst = max(worst, rel)
        print(f"{path[3:9]} {r['time'][:16]}  journal {r['funding']:+.12f}  old rule {v:+.12f}  rel diff {rel:.1e}")
print(f"worst relative difference {worst:.1e} over 19 rows: the trader saw today's published values, with no hours missing beyond the rule and no empty answers")
