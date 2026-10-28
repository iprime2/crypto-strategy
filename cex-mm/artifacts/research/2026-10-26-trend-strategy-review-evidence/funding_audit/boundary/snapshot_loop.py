#!/usr/bin/env python3
"""Snapshot Delta's FUNDING:<sym>USD hourly candles and the tickers' funding_rate for the nine trend coins, once
every --every seconds until --until (unix s), one JSON line per snapshot on stdout. Public data, no keys, writes no
file. Run here and, piped over ssh, on the VM:  python3 - --until U < snapshot_loop.py > snaps.jsonl
A single snapshot from a given time (the 24 h re-fetch):  python3 snapshot_loop.py --until 0 --start T

Each request starts on an 8-hour stamp at least 30 h back, so the endpoint's start truncation cannot cut a block,
and an empty answer is asked again (up to 6 times; the count is recorded)."""
import argparse, json, time, urllib.request

DELTA = "https://api.india.delta.exchange"
COINS = "BTC ETH XRP BNB ADA LTC LINK DOGE BCH".split()
X = 8 * 3600


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cex-mm-funding-audit/0.1"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["result"]


def snapshot(start_at=None):
    t0 = time.time()
    start = (start_at if start_at is not None else int(t0) - 30 * 3600) // X * X
    out = {"t": t0, "start": start, "candles": {}, "empties": {}, "tickers": {}}
    for c in COINS:
        for k in range(6):
            rows = get(f"{DELTA}/v2/history/candles?resolution=1h&symbol=FUNDING:{c}USD&start={start}&end={int(t0)}")
            if rows:
                break
            time.sleep(0.5)
        out["empties"][c] = k if rows else 6
        out["candles"][c] = sorted([r["time"], r["close"]] for r in rows)
    try:
        for tk in get(f"{DELTA}/v2/tickers?contract_types=perpetual_futures"):
            c = tk["symbol"][:-3]
            if tk["symbol"].endswith("USD") and c in COINS:
                out["tickers"][c] = {"funding_rate": tk.get("funding_rate"), "timestamp": tk.get("timestamp")}
    except Exception as e:  # a tickers failure must not lose the candle snapshot
        out["tickers_error"] = repr(e)
    out["t_done"] = time.time()
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--until", type=int, required=True)
ap.add_argument("--every", type=int, default=60)
ap.add_argument("--start", type=int, help="fetch from this unix time (put on an 8-hour stamp) instead of 30 h back")
a = ap.parse_args()
while True:
    t = time.time()
    try:
        print(json.dumps(snapshot(a.start)), flush=True)
    except Exception as e:
        print(json.dumps({"t": t, "error": repr(e)}), flush=True)
    if time.time() + a.every > a.until:
        break
    time.sleep(max(1.0, a.every - (time.time() - t)))
