"""Independent re-implementation (own code, stdlib only) of the ext repo's
Options Straddle logic on its own stoxx50.xlsx, to check units and P&L."""
import zipfile, re, sys, datetime as dt
from xml.etree import ElementTree as ET
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
z = zipfile.ZipFile(sys.argv[1])
ss = [ "".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
wb = ET.fromstring(z.read("xl/workbook.xml"))
rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
def col2n(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n
def sheet(name):
    for s in wb.find("m:sheets", NS):
        if s.get("name") == name:
            tgt = rels[s.get(RNS)]
            x = ET.fromstring(z.read("xl/" + tgt.lstrip("/").replace("xl/", "")))
            rows = []
            for r in x.find("m:sheetData", NS):
                row = {}
                for c in r:
                    ref = re.match(r"([A-Z]+)", c.get("r")).group(1)
                    v = c.find("m:v", NS)
                    if v is None: continue
                    val = ss[int(v.text)] if c.get("t") == "s" else float(v.text)
                    row[col2n(ref)] = val
                rows.append(row)
            return rows
def table(rows):
    hdr = rows[0]
    out = {}
    for r in rows[1:]:
        if 1 not in r: continue
        d = dt.date(1899, 12, 30) + dt.timedelta(days=int(r[1]))
        out[d] = {hdr[k]: v for k, v in r.items() if k != 1 and k in hdr}
    return hdr, out
which = sys.argv[2] if len(sys.argv) > 2 else "aug"
_, spot = table(sheet("spot"))
hdr, opt = table(sheet(which))
cols = [v for k, v in hdr.items() if k != 1]
strikes = [re.search(r"\d{4}", c).group() for c in cols]
common = sorted({s for s in strikes if strikes.count(s) > 1})
print(which, "rows", len(opt), "dates", min(opt), "->", max(opt), "strikes with C and P:", common)
dates = sorted(d for d in opt if d in spot)
print("merged dates", dates[0], "->", dates[-1], "n", len(dates))
CS = 10
for k in common:
    c = next(x for x in cols if "C" + k in x); p = next(x for x in cols if "P" + k in x)
    sig = [d for d in dates if c in opt[d] and p in opt[d] and abs(opt[d][c] - opt[d][p]) < 2]
    if not sig:
        print(k, "no trade"); continue
    d0 = sig[0]; prem = opt[d0][c] + opt[d0][p]
    sT = list(spot[dates[-1]].values())[0]
    repo_pnl = abs(sT * CS - int(k) * CS) - prem          # what the script prints
    pts_pnl = abs(sT - int(k)) - prem                      # consistent units (index points)
    print(f"K={k} entry {d0} C={opt[d0][c]:.2f} P={opt[d0][p]:.2f} prem={prem:.2f} pts | exit {dates[-1]} spot={sT:.2f} | "
          f"script P&L={repo_pnl:.1f} | consistent P&L={pts_pnl:.2f} pts = {pts_pnl*CS:.1f} EUR/contract | first-signal day count={len(sig)}")
