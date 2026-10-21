import sys
sys.path.insert(0, ".")
from robust import *
for cad in (DAILY, WEEKLY):
    rows = [p.idx[dt.date(y - 1, 12, 31)] for y in range(2021, 2027)]
    mask, log, _ = build(cad, rank_pop="eligible", start_elig="any", reset_rows=rows)
    print(fmt("reset on Dec-31 row (00:00 Jan 1 decision)", cad, judge(cad, mask)))
    saved = set(EXCL); EXCL.clear()
    mask2, log2, _ = build(cad, rank_pop="eligible", start_elig="any")
    J = judge(cad, mask2); print(fmt("no tag exclusions at all", cad, J), "membership same as with exclusions:", end=" ")
    EXCL.update(saved)
    mask3, _, _ = build(cad, rank_pop="eligible", start_elig="any")
    print(bool((mask2 == mask3).all()))
