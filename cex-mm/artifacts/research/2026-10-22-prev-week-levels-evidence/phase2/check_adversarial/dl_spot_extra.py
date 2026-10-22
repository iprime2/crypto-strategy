"""Download Binance SPOT 5 m monthly klines (public data.binance.vision) for extra Phase 1 coins, sensitivity only.
Usage: python3 -I dl_spot_extra.py <out_dir> SYM [SYM ...]   (writes only under out_dir/<SYM>/)
Each zip's sha256 is checked against Binance's .CHECKSUM; only the expected CSV member is extracted, by name."""
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/spot/monthly/klines/{s}USDT/5m/"
BASE = "https://data.binance.vision/data/spot/monthly/klines/{s}USDT/5m/{f}"


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-check/0.1"}),
                                  timeout=60).read()


def main():
    out, syms = sys.argv[1], sys.argv[2:]
    log = {}
    for s in syms:
        d = os.path.join(out, s)
        os.makedirs(d, exist_ok=True)
        xml = get(S3.format(s=s)).decode()
        files = sorted(set(re.findall(rf"({s}USDT-5m-(\d{{4}})-(\d{{2}})\.zip)<", xml)))
        files = [f for f, y, m in files if (int(y), int(m)) <= (2020, 4)]
        ok = bad = 0
        for f in files:
            csvname = f.replace(".zip", ".csv")
            dst = os.path.join(d, csvname)
            if os.path.exists(dst):
                ok += 1
                continue
            z = get(BASE.format(s=s, f=f))
            ck = get(BASE.format(s=s, f=f) + ".CHECKSUM").decode().split()[0]
            if hashlib.sha256(z).hexdigest() != ck:
                bad += 1
                continue
            with zipfile.ZipFile(io.BytesIO(z)) as zf:
                names = zf.namelist()
                assert names == [csvname], names
                data = zf.read(csvname)
            with open(dst, "wb") as fh:
                fh.write(data)
            ok += 1
        log[s] = {"months": len(files), "ok": ok, "checksum_bad": bad, "first": files[0] if files else None,
                  "last": files[-1] if files else None}
        print(s, log[s], flush=True)
    with open(os.path.join(out, "download_log.json"), "w") as fh:
        json.dump(log, fh, indent=1)


if __name__ == "__main__":
    main()
