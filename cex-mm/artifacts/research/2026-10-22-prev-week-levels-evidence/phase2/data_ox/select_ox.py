#!/usr/bin/env python3
"""Phase 2 OX coin selection (phase2_plan.md section 2), from local Binance USDT-M 1d monthly files only.

Rule: among USDT-M perps whose first daily bar is on or before 2021-09-30, excluding the 25 Phase 1 coins and index or
synthetic contracts (DEFIUSDT, BTCDOMUSDT, any name ending in INDEX), rank by median daily quote volume over
2021-10-01..2021-12-31 and take the top 15.

Data: universe/cache_all/ (the archive pull) plus universe/cache/ (181 symbols that cache_all's fetch skipped because they
were already cached there; same Binance futures/um/monthly/klines/<SYM>/1d source and file format). The 25 Phase 1 coins
(in trend-cache/ and av_cache/) are excluded by the rule, so they are listed but not read for volume.

No 2022+ price is read: for volume only files 2021-10..2021-12 are opened, and for the first daily bar only the
open_time column of the symbol's earliest monthly file is read.
"""
import csv, json, os, re, sys
import numpy as np, pandas as pd

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
OUTD = f"{SP}/research3/p2/data_ox"
DIRS = {"cache_all": f"{SP}/universe/cache_all", "cache": f"{SP}/universe/cache"}
P1 = ("BTC ETH XRP BNB ADA LTC LINK DOGE BCH EOS TRX ETC XLM XMR DASH ZEC XTZ ATOM ONT IOTA BAT VET NEO QTUM IOST").split()
P1 = {c + "USDT" for c in P1}
SYNTH = {"DEFIUSDT", "BTCDOMUSDT"}
CUTOFF_FIRST = pd.Timestamp("2021-09-30 23:59:59.999", tz="UTC")
W0, W1 = pd.Timestamp("2021-10-01", tz="UTC"), pd.Timestamp("2021-12-31", tz="UTC")
NTOP = 15

def read_kl(path):
    """Read a Binance kline csv with or without a header row; return DataFrame with open_time (UTC) and quote_volume."""
    with open(path) as f:
        first = f.readline()
    hdr = 0 if first.split(",")[0].strip().lower() in ("open_time", "opentime", "open time") else None
    df = pd.read_csv(path, header=hdr)
    df = df.iloc[:, :12]
    df.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
                  "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"][: df.shape[1]]
    ot = pd.to_numeric(df["open_time"], errors="coerce").astype("float64")
    ot = np.where(ot > 1e14, ot / 1000.0, ot)  # us -> ms
    df["open_time"] = pd.to_datetime(ot, unit="ms", utc=True)
    df["quote_volume"] = pd.to_numeric(df["quote_volume"], errors="coerce")
    return df, hdr is not None

files = {}  # sym -> {ym: (dirname, path)}
dup_src = []
for dn, d in DIRS.items():
    for fn in os.listdir(d):
        m = re.match(r"^binance-(.+)-1d-(\d{4}-\d{2})\.csv$", fn)
        if not m:
            continue
        sym, ym = m.group(1), m.group(2)
        if ym in files.setdefault(sym, {}):
            dup_src.append((sym, ym, files[sym][ym][0], dn))
            continue
        files[sym][ym] = (dn, f"{d}/{fn}")

# completeness against the S3 listing
s3 = json.load(open(f"{OUTD}/s3_um_symbols.json"))
s3_usdt = sorted(s for s in s3 if s.endswith("USDT"))
local = set(files) | P1
missing_local = [s for s in s3_usdt if s not in local]

rows = []
for sym in sorted(set(files) | P1):
    srcs = sorted({v[0] for v in files.get(sym, {}).values()})
    yms = sorted(files.get(sym, {}))
    r = {"symbol": sym, "source_dirs": "+".join(srcs) if srcs else "trend-cache/av_cache (not read)",
         "first_month_file": yms[0] if yms else "", "n_month_files": len(yms)}
    excl = []
    if not sym.endswith("USDT"):
        excl.append("not USDT-margined")
    if sym in P1:
        excl.append("Phase 1 coin")
    if sym in SYNTH or sym.endswith("INDEX"):
        excl.append("index/synthetic")
    first_bar = pd.NaT
    if yms and sym not in P1:
        df, _ = read_kl(files[sym][yms[0]][1])
        first_bar = df["open_time"].min()
    r["first_daily_bar"] = first_bar.strftime("%Y-%m-%d") if pd.notna(first_bar) else ""
    if pd.notna(first_bar) and first_bar > CUTOFF_FIRST:
        excl.append("first bar after 2021-09-30")
    med, nd = np.nan, 0
    if sym not in P1 and pd.notna(first_bar) and first_bar <= CUTOFF_FIRST:
        parts = []
        for ym in ("2021-10", "2021-11", "2021-12"):
            if ym in files[sym]:
                df, _ = read_kl(files[sym][ym][1])
                parts.append(df[["open_time", "quote_volume"]])
        if parts:
            q = pd.concat(parts).drop_duplicates("open_time")
            q = q[(q.open_time >= W0) & (q.open_time <= W1)]
            nd = len(q)
            med = float(q["quote_volume"].median()) if nd else np.nan
        if nd == 0:
            excl.append("no daily bars in 2021-10..12")
    r["n_days_q4_2021"] = nd
    r["median_daily_quote_volume_usdt"] = med
    r["exclusion"] = "; ".join(excl)
    r["eligible"] = int(not excl)
    rows.append(r)

tab = pd.DataFrame(rows)
el = tab[tab.eligible == 1].sort_values("median_daily_quote_volume_usdt", ascending=False).reset_index(drop=True)
el["rank"] = np.arange(1, len(el) + 1)
# literal cache_all-only ranking (sensitivity only): the same rule restricted to symbols present in cache_all
el_ca = el[el.source_dirs.str.contains("cache_all")].copy()
el_ca["rank_cache_all_only"] = np.arange(1, len(el_ca) + 1)
tab = tab.merge(el[["symbol", "rank"]], on="symbol", how="left").merge(el_ca[["symbol", "rank_cache_all_only"]], on="symbol", how="left")
tab["selected"] = ((tab["rank"] <= NTOP)).astype(int)
tab = tab.sort_values(["eligible", "rank", "symbol"], ascending=[False, True, True])
cols = ["rank", "symbol", "first_daily_bar", "median_daily_quote_volume_usdt", "n_days_q4_2021", "selected", "eligible",
        "exclusion", "source_dirs", "first_month_file", "n_month_files", "rank_cache_all_only"]
tab["rank"] = tab["rank"].astype("Int64"); tab["rank_cache_all_only"] = tab["rank_cache_all_only"].astype("Int64")
tab[cols].to_csv(f"{OUTD}/selection.csv", index=False, float_format="%.2f")

sel = el.head(NTOP)
meta = {"rule": "phase2_plan.md section 2", "n_symbols_local": int(len(tab)), "n_eligible": int(len(el)),
        "s3_usdt_symbols": len(s3_usdt), "s3_usdt_missing_locally": missing_local, "duplicate_month_sources": dup_src,
        "selected": sel["symbol"].tolist(),
        "selected_cache_all_only_literal": el_ca.head(NTOP)["symbol"].tolist()}
json.dump(meta, open(f"{OUTD}/selection_meta.json", "w"), indent=1)
pd.set_option("display.width", 200)
print(el.head(30)[["rank", "symbol", "first_daily_bar", "median_daily_quote_volume_usdt", "n_days_q4_2021", "source_dirs"]].to_string(index=False))
print(json.dumps({k: v for k, v in meta.items() if k != "duplicate_month_sources"}, indent=1))
print("duplicate month sources:", len(dup_src), dup_src[:5])
