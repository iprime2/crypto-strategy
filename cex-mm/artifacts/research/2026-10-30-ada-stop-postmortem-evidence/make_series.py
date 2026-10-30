#!/usr/bin/env python3
"""1 s series of the shadow's ADA fair and Delta L1 mid (local receive clock) + the tape's receive-minus-exchange offset.

  python3 make_series.py DATA_DIR REPO_SCRIPTS_DIR   ->  DATA_DIR/series.json
"""
import glob, json, os, statistics, sys

D, SCRIPTS = sys.argv[1], sys.argv[2]
sys.path.insert(0, SCRIPTS)
import shadow_fill_sim as sim  # noqa: E402

ts, fair, mid = [], [], []
last_sec = None
for line in sim.iter_lines(os.path.join(D, "ada_metrics.log.gz")):
    p = sim.parse_metrics_line(line)
    if not p or p[0] != "ADAUSDT":
        continue
    s = p[1]
    sec = int(s.ts // 1000)
    if sec == last_sec:
        ts[-1], fair[-1], mid[-1] = s.ts, s.fair, (s.book_bid + s.book_ask) / 2
    else:
        ts.append(s.ts); fair.append(s.fair); mid.append((s.book_bid + s.book_ask) / 2)
        last_sec = sec
order = sorted(range(len(ts)), key=ts.__getitem__)
ts, fair, mid = [ts[i] for i in order], [fair[i] for i in order], [mid[i] for i in order]
offs = []
for path in sorted(glob.glob(os.path.join(D, "delta_mainnet_public_*.jsonl"))):
    for line in sim.iter_lines(path):
        p = sim.parse_trade_record(line)
        if p and p[0] == "ADAUSD" and p[2] > 0:
            offs.append(p[1].ts - p[2])
off = statistics.median(offs)
json.dump(dict(ts=ts, fair=fair, mid=mid, recv_minus_exch_ms=off), open(os.path.join(D, "series.json"), "w"))
print(f"{len(ts)} seconds from {ts[0]:.0f} to {ts[-1]:.0f}; tape offset recv-exch median {off:.0f} ms over {len(offs)} trades")
