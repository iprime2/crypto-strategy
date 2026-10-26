#!/usr/bin/env python3
"""Audit Binance USDT-M 5m klines 2020-01..2026-09 for the nine coins (read-only on the data).

Outputs (in research3/data/):
  audit_files.csv     one row per expected (coin, month): header, rows, expected, units, dups, off-grid, ...
  gaps_all.csv        every gap (consecutive open times more than 5 min apart) per coin
  week_coverage.csv   bars per Monday-00:00-UTC week per coin (2019-12-30 .. 2026-09-28)
  zero_volume_runs.csv runs of consecutive zero-volume bars per coin
  audit_summary.json  aggregates used by the report

Usage: python3 -I audit_klines.py <scratchpad_root>
"""
import json
import os
import sys
import calendar

import numpy as np
import pandas as pd

ROOT = sys.argv[1]
KD = os.path.join(ROOT, "universe", "klines5m")
OUT = os.path.join(ROOT, "research3", "data")
SYMS = ["BTC", "ETH", "XRP", "BNB", "ADA", "LTC", "LINK", "DOGE", "BCH"]
MONTHS = [f"{y}-{m:02d}" for y in range(2020, 2027) for m in range(1, 13)
          if (y, m) <= (2026, 9)]
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
BAR = 300_000
WEEK = 7 * 86_400_000
MON0 = 4 * 86_400_000  # 1970-01-05 Monday 00:00 UTC in ms
WIN_START = int(pd.Timestamp("2020-01-01", tz="UTC").value // 1_000_000)
WIN_END = int(pd.Timestamp("2026-10-01", tz="UTC").value // 1_000_000)  # exclusive


def ms_of(month):
    y, m = map(int, month.split("-"))
    a = int(pd.Timestamp(year=y, month=m, day=1, tz="UTC").value // 1_000_000)
    nd = calendar.monthrange(y, m)[1]
    return a, a + nd * 86_400_000, nd * 288


def iso(ms):
    return pd.Timestamp(int(ms), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M")


def load(path):
    with open(path, "rb") as f:
        first = f.readline()
    header = not first[:1].isdigit()
    hdr_text = first.decode().strip() if header else ""
    df = pd.read_csv(path, header=0 if header else None, names=None if header else COLS,
                     dtype={"open_time": "int64", "close_time": "int64"})
    if header and list(df.columns) != COLS:
        raise RuntimeError(f"unexpected header in {path}: {list(df.columns)}")
    return df, header, hdr_text


def main():
    file_rows, all_gaps, week_rows, zero_runs = [], [], [], []
    summary = {"coins": {}}
    for sym in SYMS:
        pair = f"{sym}USDT"
        frames = []
        for month in MONTHS:
            a, b, exp = ms_of(month)
            path = os.path.join(KD, f"binance-{pair}-5m-{month}.csv")
            rec = {"coin": pair, "month": month, "expected_rows": exp}
            if not os.path.exists(path):
                rec.update(present=False)
                file_rows.append(rec)
                continue
            df, header, _ = load(path)
            ot_raw = df["open_time"].to_numpy()
            ct_raw = df["close_time"].to_numpy()
            ot_us = bool((ot_raw > 1e14).any())
            ot_mixed = bool((ot_raw > 1e14).any() and (ot_raw <= 1e14).any())
            ct_us = bool((ct_raw > 1e14).any())
            ot = np.where(ot_raw > 1e14, ot_raw // 1000, ot_raw)
            ct = np.where(ct_raw > 1e14, ct_raw // 1000, ct_raw)
            num = df[["open", "high", "low", "close", "volume"]].astype(float)
            ohlc_bad = int(((num["high"] < num[["open", "close"]].max(axis=1)) |
                            (num["low"] > num[["open", "close"]].min(axis=1)) |
                            (num["low"] > num["high"])).sum())
            rec.update(
                present=True, header=header, rows=len(df), missing_rows=exp - len(df),
                pct_of_expected=round(100.0 * len(df) / exp, 3),
                open_time_unit=("mixed" if ot_mixed else ("us" if ot_us else "ms")),
                close_time_unit=("us" if ct_us else "ms"),
                first_bar=iso(ot.min()), last_bar=iso(ot.max()),
                dup_open_times=int(pd.Series(ot).duplicated().sum()),
                dup_full_rows=int(df.duplicated().sum()),
                not_sorted=int((np.diff(ot) <= 0).sum()),
                off_grid=int((ot % BAR != 0).sum()),
                outside_month=int(((ot < a) | (ot >= b)).sum()),
                close_minus_open_not_299999=int((ct - ot != BAR - 1).sum()),
                nan_cells=int(df.isna().sum().sum()),
                nonpos_price=int((num[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
                ohlc_inconsistent=ohlc_bad,
                zero_volume_bars=int((num["volume"] == 0).sum()),
            )
            file_rows.append(rec)
            frames.append(pd.DataFrame({"t": ot, "src": month, "v": num["volume"].to_numpy(),
                                        "flat": (num["high"] == num["low"]).to_numpy()}))
        allt = pd.concat(frames, ignore_index=True).sort_values("t", kind="stable")
        cross_dups = int(allt["t"].duplicated().sum())
        t = np.unique(allt["t"].to_numpy())
        first, last = int(t[0]), int(t[-1])
        d = np.diff(t)
        gi = np.nonzero(d > BAR)[0]
        for i in gi:
            prev, nxt = int(t[i]), int(t[i + 1])
            all_gaps.append({
                "coin": pair, "last_bar_before": iso(prev), "first_missing_bar": iso(prev + BAR),
                "next_bar": iso(nxt), "missing_bars": (nxt - prev) // BAR - 1,
                "missing_minutes": (nxt - prev - BAR) // 60_000,
                "open_time_diff_min": (nxt - prev) // 60_000,
            })
        # runs of consecutive zero-volume bars (exchange halts / maintenance: Binance prints flat bars)
        u = allt.drop_duplicates("t")
        z = (u["v"].to_numpy() == 0)
        tt = u["t"].to_numpy()
        i = 0
        while i < len(z):
            if z[i]:
                j = i
                while j + 1 < len(z) and z[j + 1] and tt[j + 1] - tt[j] == BAR:
                    j += 1
                zero_runs.append({"coin": pair, "first_bar": iso(tt[i]), "last_bar": iso(tt[j]), "bars": j - i + 1,
                                  "all_flat_hl": bool(u["flat"].to_numpy()[i:j + 1].all())})
                i = j + 1
            else:
                i += 1
        # week coverage
        wk = (t - MON0) // WEEK
        cnt = pd.Series(wk).value_counts()
        tv = u.loc[u["v"] > 0, "t"].to_numpy()
        cnt_traded = pd.Series((tv - MON0) // WEEK).value_counts()
        w0 = (pd.Timestamp("2019-12-30", tz="UTC").value // 1_000_000 - MON0) // WEEK
        w1 = (pd.Timestamp("2026-09-28", tz="UTC").value // 1_000_000 - MON0) // WEEK
        for w in range(int(w0), int(w1) + 1):
            ws = MON0 + w * WEEK
            we = ws + WEEK
            # bars possible inside the data window
            lo, hi = max(ws, WIN_START), min(we, WIN_END)
            possible = max(0, (hi - lo) // BAR)
            n = int(cnt.get(w, 0))
            if ws < WIN_START or we > WIN_END:
                status = "window_truncated"
            elif we <= first:
                status = "pre_listing"
            elif ws < first:
                status = "listing_week"
            else:
                status = "full" if n >= 0.99 * 2016 else "below_99pct"
            week_rows.append({"coin": pair, "week_start": pd.Timestamp(ws, unit="ms", tz="UTC").strftime("%Y-%m-%d"),
                              "bars": n, "expected": 2016, "pct": round(100.0 * n / 2016, 3),
                              "bars_with_volume": int(cnt_traded.get(w, 0)),
                              "bars_possible_in_window": possible, "status": status})
        summary["coins"][pair] = {
            "first_bar": iso(first), "last_bar": iso(last), "unique_bars": int(len(t)),
            "cross_file_dup_open_times": cross_dups, "gaps_any": int(len(gi)),
            "missing_bars_after_first_bar": int(((last - first) // BAR + 1) - len(t)),
        }
    fdf = pd.DataFrame(file_rows)
    fdf.to_csv(os.path.join(OUT, "audit_files.csv"), index=False)
    gdf = pd.DataFrame(all_gaps, columns=["coin", "last_bar_before", "first_missing_bar", "next_bar",
                                          "missing_bars", "missing_minutes", "open_time_diff_min"])
    gdf.to_csv(os.path.join(OUT, "gaps_all.csv"), index=False)
    wdf = pd.DataFrame(week_rows)
    wdf.to_csv(os.path.join(OUT, "week_coverage.csv"), index=False)
    pd.DataFrame(zero_runs).to_csv(os.path.join(OUT, "zero_volume_runs.csv"), index=False)
    with open(os.path.join(OUT, "audit_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
