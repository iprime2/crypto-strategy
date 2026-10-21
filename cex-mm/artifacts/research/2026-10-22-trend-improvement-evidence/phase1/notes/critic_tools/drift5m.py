import sys, zipfile, io, csv, statistics as st, datetime as dt, glob, os, collections
d = sys.argv[1]
out = collections.defaultdict(list)
for z in sorted(glob.glob(os.path.join(d, "*-5m-*.zip"))):
    sym = os.path.basename(z).split("-")[0]
    with zipfile.ZipFile(z) as zf:
        rows = list(csv.reader(io.TextIOWrapper(zf.open(zf.namelist()[0]))))
    rows = [r for r in rows if r[0].isdigit()]
    bars = {int(r[0]): (float(r[1]), float(r[4])) for r in rows}  # open, close
    for t, (o, c) in bars.items():
        ts = dt.datetime.fromtimestamp(t/1000, dt.UTC)
        if ts.hour == 0 and ts.minute == 0:
            prev = bars.get(t - 300000)  # close of 23:55 bar = daily close
            nxt = bars.get(t + 300000)
            if prev and nxt:
                close0 = prev[1]
                out[sym, "00:00->00:05 close"].append((c/close0 - 1)*1e4)      # 00:05 close vs daily close
                out[sym, "00:00->00:05 open(nxt bar)"].append((nxt[0]/close0 - 1)*1e4)
        if ts.hour == 12 and ts.minute == 0:
            prev = bars.get(t - 300000)
            if prev:
                out[sym, "12:00->12:05 close (control)"].append((c/prev[1] - 1)*1e4)
for k, v in sorted(out.items()):
    n = len(v); m = st.mean(v); s = st.stdev(v); a = st.mean(abs(x) for x in v); med = st.median(abs(x) for x in v)
    print(f"{k[0]:8s} {k[1]:32s} n={n:4d} mean={m:+6.2f} bps  sd={s:6.2f}  mean|r|={a:5.2f}  median|r|={med:5.2f}  t={m/(s/n**0.5):+5.2f}")
