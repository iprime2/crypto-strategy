#!/usr/bin/env python3
"""Rebuild incomplete monthly files from Binance daily zips (same month), with full provenance.

For each (pair, month) given: the downloaded monthly CSV is moved to research3/data/replaced_monthly/,
every daily zip of that month in the S3 listing is downloaded into its own temp folder, sha256-checked
against its .CHECKSUM, and concatenated in date order. Every row of the replaced monthly file must
appear byte-identical in the daily concat (else abort and restore). The header line is kept only if
the monthly file had one. Only months inside the downloaded range 2020-01..2023-12 are allowed.

Usage: python3 -I patch_from_daily.py <scratchpad_root> PAIR:YYYY-MM [PAIR:YYYY-MM ...]
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import zipfile

ROOT = sys.argv[1]
TARGETS = [a.split(":") for a in sys.argv[2:]]
KD = os.path.join(ROOT, "universe", "klines5m")
WORK = os.path.join(ROOT, "research3", "data")
TMP = os.path.join(WORK, "tmp_patch")
KEEP = os.path.join(WORK, "replaced_monthly")
BASE = "https://data.binance.vision/"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def curl(url, dest=None):
    args = ["curl", "-sS", "--fail", "--retry", "4", "--retry-delay", "2", "--max-time", "120", url]
    if dest:
        args[1:1] = ["-o", dest]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl rc={r.returncode} {url}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def daily_keys(pair, month):
    q = urllib.parse.urlencode({"delimiter": "/", "prefix": f"data/futures/um/daily/klines/{pair}/5m/{pair}-5m-{month}-"})
    t = curl(S3 + "?" + q).decode()
    assert "<IsTruncated>true" not in t
    return sorted(k for k in re.findall(r"<Key>([^<]*)</Key>", t) if k.endswith(".zip"))


def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    log = []
    for pair, month in TARGETS:
        assert "2020-01" <= month <= "2023-12", month
        out = os.path.join(KD, f"binance-{pair}-5m-{month}.csv")
        orig = open(out, "rb").read()
        olines = orig.splitlines()
        ohdr = olines[0] if not olines[0][:1].isdigit() else None
        orows = olines[1:] if ohdr else olines
        rec = {"pair": pair, "month": month, "monthly_rows": len(orows), "monthly_header": ohdr is not None,
               "monthly_sha256_of_csv": hashlib.sha256(orig).hexdigest(), "daily": []}
        rows = []
        for key in daily_keys(pair, month):
            name = key.split("/")[-1]
            d = os.path.join(TMP, name[:-4])
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(d)
            zp = os.path.join(d, name)
            curl(BASE + key, zp)
            h = hashlib.sha256(open(zp, "rb").read()).hexdigest()
            ck = curl(BASE + key + ".CHECKSUM").decode().split()[0].lower()
            if ck != h:
                raise RuntimeError(f"checksum mismatch {key}")
            with zipfile.ZipFile(zp) as z:
                ms = [m for m in z.infolist() if not m.is_dir()]
                cand = [m for m in ms if os.path.basename(m.filename) == name[:-4] + ".csv"]
                assert len(cand) == 1, [m.filename for m in ms]
                data = z.read(cand[0])
            shutil.rmtree(d)
            ls = data.splitlines()
            hdr = not ls[0][:1].isdigit()
            body = ls[1:] if hdr else ls
            rec["daily"].append({"zip": key, "sha256": h, "checksum_ok": True, "rows": len(body), "header": hdr})
            rows += body
        oset, dset = set(orows), set(rows)
        missing_in_daily = len(oset - dset)
        rec["daily_rows"] = len(rows)
        rec["monthly_rows_not_in_daily"] = missing_in_daily
        rec["rows_added"] = len(dset - oset)
        if missing_in_daily:
            raise RuntimeError(f"{pair} {month}: {missing_in_daily} monthly rows differ from daily; not patched")
        ts = [int(r.split(b",")[0]) for r in rows]
        assert ts == sorted(ts) and len(set(ts)) == len(ts), "daily concat not strictly increasing"
        shutil.copy2(out, os.path.join(KEEP, os.path.basename(out)))
        new = ((ohdr + b"\n") if ohdr else b"") + b"\n".join(rows) + b"\n"
        tmp = out + ".part"
        with open(tmp, "wb") as f:
            f.write(new)
        os.replace(tmp, out)
        rec["new_rows"] = len(rows)
        rec["new_sha256_of_csv"] = hashlib.sha256(new).hexdigest()
        log.append(rec)
        print(pair, month, "monthly", len(orows), "-> daily", len(rows), "added", rec["rows_added"], flush=True)
    shutil.rmtree(TMP, ignore_errors=True)
    with open(os.path.join(WORK, "patch_log.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
