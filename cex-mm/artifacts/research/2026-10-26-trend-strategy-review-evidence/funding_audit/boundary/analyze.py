#!/usr/bin/env python3
"""Offline: did any FUNDING candle change value after it first appeared, and when does the candle of a new 8-hour
block appear? Reads snapshot_loop.py output (one or more JSONL files) and, optionally, a later re-fetch to diff.

    python3 analyze.py local_snaps_2026-10-27.json vm_snaps_2026-10-27.json [--refetch LATER.jsonl]

For each file: candles seen, candles whose value ever changed between snapshots (the provisional-value test), when
the 00:00 UTC 27 Oct candle first appeared per coin, and the tickers' funding_rate just before 00:00 against that
candle. With --refetch, every candle of the last snapshot is compared with the same hour in the re-fetch."""
import argparse, datetime as dt, json

UTC = dt.timezone.utc
B = int(dt.datetime(2026, 10, 27, tzinfo=UTC).timestamp())
hm = lambda t: dt.datetime.fromtimestamp(t, UTC).strftime("%d %H:%M:%S")  # noqa: E731


def load(path):
    """A JSON array of snapshots (as committed) or the loop's raw JSONL output."""
    text = open(path).read().strip()
    rows = json.loads(text) if text.startswith("[") else [json.loads(x) for x in text.splitlines() if x.strip()]
    return [s for s in rows if "candles" in s]


def analyse(path):
    snaps = load(path)
    print(f"\n=== {path}: {len(snaps)} snapshots, {hm(snaps[0]['t'])} to {hm(snaps[-1]['t'])} UTC")
    seen, changed = {}, []
    first_b = {}
    for s in snaps:
        for c, rows in s["candles"].items():
            for t, v in rows:
                k = (c, t)
                if k in seen and seen[k][1] != v:
                    changed.append((c, hm(t), seen[k][1], v, hm(s["t"])))
                seen.setdefault(k, (s["t"], v))
                seen[k] = (seen[k][0], v)
                if t == B and c not in first_b:
                    first_b[c] = (s["t"], v)
    print(f"distinct candles seen {len(seen)}; candles whose value changed after first seen: {len(changed)}")
    for x in changed[:20]:
        print("  CHANGED", x)
    empt = sum(sum(s["empties"].values()) for s in snaps)
    print(f"empty answers retried: {empt} over {len(snaps) * 9} requests")
    pre = [s for s in snaps if s["t"] < B]
    last_pre = pre[-1] if pre else None
    print("00:00 UTC 27 Oct candle: first seen, value; ticker funding_rate in the last snapshot before 00:00")
    for c in sorted(first_b):
        t, v = first_b[c]
        tk = last_pre["tickers"].get(c, {}).get("funding_rate") if last_pre else None
        print(f"  {c:<5} first seen {hm(t)} ({t - B:+.0f} s)  value {v:.8f}  ticker before 00:00 {tk}")
    missing = sorted(set(snaps[-1]["candles"]) - set(first_b))
    if missing:
        print("  never appeared:", missing)
    return snaps


ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--refetch")
a = ap.parse_args()
lasts = {f: analyse(f)[-1] for f in a.files}
if a.refetch:
    later = load(a.refetch)[-1]
    print(f"\n=== re-fetch at {hm(later['t'])} UTC vs the last snapshot of each file")
    L = {(c, t): v for c, rows in later["candles"].items() for t, v in rows}
    for f, s in lasts.items():
        common = diff = 0
        for c, rows in s["candles"].items():
            for t, v in rows:
                if (c, t) in L:
                    common += 1
                    if L[(c, t)] != v:
                        diff += 1
                        print("  DIFF", f, c, hm(t), v, L[(c, t)])
        print(f"  {f}: {common} common candles, {diff} differ")
