"""Independent raw-5m loader for the verify pass (own code; reads public CSVs only)."""
import csv, os, glob, datetime as dt
import numpy as np
SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
EP = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)

def load5m(sym, months=None, pattern=None):
    """dict open_ms -> (o,h,l,c) for every 5m bar in the matching files (header rows skipped, us->ms)."""
    pat = pattern or f"{SP}/universe/klines5m/binance-{sym}USDT-5m-*.csv"
    out = {}
    for fn in sorted(glob.glob(pat)):
        if months is not None and fn[-11:-4] not in months:
            continue
        with open(fn) as f:
            for line in f:
                if not line[0].isdigit():
                    continue
                p = line.split(",", 6)
                t = int(p[0])
                if t > 10**14:
                    t //= 1000
                out[t] = (float(p[1]), float(p[2]), float(p[3]), float(p[4]))
    return out

def ms(d, h=0, m=0):
    return int((dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) - EP).total_seconds() * 1000) + h * 3600000 + m * 60000

def close00(b, d):
    """close at 00:00 UTC of d = close of the 5m bar opening 23:55 d-1."""
    v = b.get(ms(d) - 300000)
    return v[3] if v else np.nan

def p01(b, d):
    """close at 01:00 UTC of d = close of the 5m bar opening 00:55 d."""
    v = b.get(ms(d, 0, 55))
    return v[3] if v else np.nan

def funding(sym):
    rows = {}
    for cache in [f"{SP}/trend-cache", f"{SP}/av_cache", f"{SP}/universe/cache", f"{SP}/universe/cache_all"]:
        for fn in sorted(glob.glob(f"{cache}/binance-{sym}USDT-fundingRate-*.csv")):
            with open(fn) as f:
                for row in csv.reader(f):
                    if row and row[0].isdigit():
                        k = round(int(row[0]) / 1000)
                        rows.setdefault(k, (int(row[0]), float(row[2])))
    return sorted(rows.values())
