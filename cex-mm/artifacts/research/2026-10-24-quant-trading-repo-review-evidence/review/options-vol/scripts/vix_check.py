"""Own re-implementation (stdlib only) of the ext repo's VIX Calculator on its own
Henry Hub data, (a) as written and (b) with strike units fixed / K0 included /
truncation fixed, to measure how much the visible bugs move the number."""
import csv, sys, math, datetime as dt, collections
D = sys.argv[1]
TRADEDATE = dt.date(2020, 11, 12)
rows = [r for r in csv.DictReader(open(D + "/henry hub european options.csv")) if r["options-id"] == "1352" and r["tradeDate"] == "2020-11-12"]
hol = {r["DATE"] for r in csv.DictReader(open(D + "/cme holidays.csv"))}
rates = {}
for r in csv.DictReader(open(D + "/treasury yield curve rates.csv")):
    m, d_, y = (int(x) for x in r["Date"].split("/"))
    rates[(dt.date(y, m, d_), r["maturity"])] = float(r["value"])
def rate(mat):
    d = TRADEDATE
    while (d, mat) not in rates: d -= dt.timedelta(days=1)   # ffill
    return rates[(d, mat)] / 100
def month_end(d, add):
    y, m = d.year, d.month + add
    while m > 12: y, m = y + 1, m - 12
    nm = dt.date(y + (m == 12), m % 12 + 1, 1)
    return dt.datetime(y, m, (nm - dt.timedelta(days=1)).day, 16)
def settle(cur, horizon, nth=4):
    s = month_end(cur, horizon - 1)
    counter = 1 if s.weekday() < 5 else 0
    while not (s.weekday() < 5 and str(s)[:10] not in hol and counter > nth - 1):
        s -= dt.timedelta(days=1)
        if s.weekday() < 5: counter += 1
    return s
def tte(cur, horizon):
    return (settle(cur, horizon) - cur).total_seconds() / 60 / 525600
def chain(exp_month):
    ch = [r for r in rows if r["futures-expirationDate"] == exp_month]
    cur = dt.datetime.fromisoformat(ch[0]["futures-updated"])
    return ch, cur
def sigma2(ch, r, T, kscale, fix):
    # kscale divides strikes (1 = as written, 1000 = $ units)
    P = collections.defaultdict(dict)
    for x in ch: P[float(x["options-strikePrice"]) / kscale][x["options-optiontype"]] = float(x["options-priorSettle"])
    ks = sorted(k for k in P if "call" in P[k] and "put" in P[k])
    kstar = min(ks, key=lambda k: abs(P[k]["call"] - P[k]["put"]))
    F = kstar + math.exp(r * T) * (P[kstar]["call"] - P[kstar]["put"])
    K0 = [k for k in ks if k <= F][-1]
    def side(typ, sel, rev):
        lst = sorted((k for k in P if typ in P[k] and sel(k)), reverse=rev)
        zeros = [i for i, k in enumerate(lst) if P[k][typ] == 0]
        cut = next((zeros[j] for j in range(1, len(zeros)) if zeros[j] - zeros[j - 1] == 1), len(lst))
        if fix:   # CBOE: stop at the first of two consecutive zeros, drop single zeros before it
            return [(k, P[k][typ]) for k in lst[:cut] if P[k][typ] != 0]
        nz = [k for k in lst if P[k][typ] != 0]       # as written: positional slice of the filtered list
        return [(k, P[k][typ]) for k in nz[:cut]]
    calls = side("call", lambda k: k > K0, False)
    puts = side("put", lambda k: k < K0, True)
    if fix:  # include K0 at the call/put average, with dK from neighbours, as one merged strip
        strip = sorted(puts + [(K0, (P[K0]["call"] + P[K0]["put"]) / 2)] + calls)
        lists = [strip]
    else:
        lists = [calls, puts]
    tot = 0.0
    for lst in lists:
        n = len(lst)
        for j, (k, q) in enumerate(lst):
            if j == 0: dk = abs(k - lst[1][0])
            elif j == n - 1: dk = abs(k - lst[j - 1][0])
            else: dk = abs(lst[j - 1][0] - lst[j + 1][0]) / 2
            tot += q * math.exp(r * T) * dk / k ** 2
    return 2 / T * tot - (F / K0 - 1) ** 2 / T, F, K0, len(calls), len(puts)
def vix(kscale, fix):
    (cf, curf), (cr, curr) = chain("2021-01-01"), chain("2021-02-01")
    Tf, Tr = tte(curf, 2), tte(curr, 3)
    rf, rr = rate("2 Mo"), rate("3 Mo")
    sf, Ff, K0f, ncf, npf = sigma2(cf, rf, Tf, kscale, fix)
    sr, Fr, K0r, ncr, npr = sigma2(cr, rr, Tr, kscale, fix)
    Nt, Ny = 3 * 30 * 24 * 60, 365 * 24 * 60
    s1 = Tf * sf * (Tr * Ny - Nt) / (Tr * Ny - Tf * Ny)
    s2 = Tr * sr * (Nt - Tf * Ny) / (Tr * Ny - Tf * Ny)
    v = (s1 + s2) * Ny / Nt
    print(f"kscale={kscale:5d} fix={fix!s:5s} Tf={Tf*365:.1f}d Tr={Tr*365:.1f}d F=({Ff:.4f},{Fr:.4f}) K0=({K0f},{K0r}) n(c,p)=({ncf},{npf}),({ncr},{npr}) "
          f"sig2=({sf:.5f},{sr:.5f}) -> VIX={math.sqrt(v)*100 if v > 0 else float('nan'):.2f}")
print("rows on 2020-11-12:", len(rows), collections.Counter(r["futures-expirationDate"] for r in rows))
vix(1, False); vix(1000, False); vix(1000, True)
