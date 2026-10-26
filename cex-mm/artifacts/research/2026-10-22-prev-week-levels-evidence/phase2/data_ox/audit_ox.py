#!/usr/bin/env python3
"""Audit the panel OX 5 m klines (15 coins, 2021-12..2026-09) in universe/ox5m/ (read-only on the data).

Outputs (next to this script, or under the folder given as argv[1]):
  audit_files.csv       one row per (coin, month): header, rows, expected, units, dups, off-grid, integrity
  gaps_all.csv          every gap (consecutive open times more than 5 min apart) per coin, with a >15 min flag
  week_coverage.csv     bars and traded bars per Monday-00:00-UTC week per coin (2021-11-29 .. 2026-09-28)
  zero_volume_runs.csv  runs of consecutive zero-volume bars per coin
  audit_summary.json    per-coin aggregates, last full week, flat tails

Usage: python3 -I audit_ox.py [out_dir]
"""
import calendar, json, os, sys
import numpy as np, pandas as pd

SP = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad"
KD = f"{SP}/universe/ox5m"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{SP}/research3/p2/data_ox"
SYMS = json.load(open(f"{SP}/research3/p2/data_ox/selection_meta.json"))["selected"]
MONTHS = [f"{y}-{m:02d}" for y in range(2021, 2027) for m in range(1, 13) if (2021, 12) <= (y, m) <= (2026, 9)]
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
BAR, DAY = 300_000, 86_400_000
WEEK = 7 * DAY
MON0 = 4 * DAY  # 1970-01-05 Monday
WIN_START = int(pd.Timestamp("2021-12-01", tz="UTC").value // 1_000_000)
WIN_END = int(pd.Timestamp("2026-10-01", tz="UTC").value // 1_000_000)  # exclusive
W_FIRST, W_LAST = "2021-11-29", "2026-09-28"


def ms_of(month):
    y, m = map(int, month.split("-"))
    a = int(pd.Timestamp(year=y, month=m, day=1, tz="UTC").value // 1_000_000)
    nd = calendar.monthrange(y, m)[1]
    return a, a + nd * DAY, nd * 288


def iso(ms):
    return pd.Timestamp(int(ms), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M")


def load(path):
    with open(path, "rb") as f:
        first = f.readline()
    header = not first[:1].isdigit()
    df = pd.read_csv(path, header=0 if header else None, names=None if header else COLS,
                     dtype={"open_time": "int64", "close_time": "int64"})
    if header and list(df.columns) != COLS:
        raise RuntimeError(f"unexpected header in {path}: {list(df.columns)}")
    return df, header


def main():
    file_rows, all_gaps, week_rows, zero_runs = [], [], [], []
    summary = {"coins": {}}
    for sym in SYMS:
        frames = []
        for month in MONTHS:
            a, b, exp = ms_of(month)
            path = os.path.join(KD, f"binance-{sym}-5m-{month}.csv")
            rec = {"coin": sym, "month": month, "expected_rows": exp}
            if not os.path.exists(path):
                rec.update(present=False)
                file_rows.append(rec)
                continue
            df, header = load(path)
            ot_raw, ct_raw = df["open_time"].to_numpy(), df["close_time"].to_numpy()
            ot_us, ct_us = bool((ot_raw > 1e14).any()), bool((ct_raw > 1e14).any())
            ot_mixed = bool((ot_raw > 1e14).any() and (ot_raw <= 1e14).any())
            ot = np.where(ot_raw > 1e14, ot_raw // 1000, ot_raw)
            ct = np.where(ct_raw > 1e14, ct_raw // 1000, ct_raw)
            num = df[["open", "high", "low", "close", "volume", "quote_volume"]].astype(float)
            ohlc_bad = int(((num["high"] < num[["open", "close"]].max(axis=1)) |
                            (num["low"] > num[["open", "close"]].min(axis=1)) | (num["low"] > num["high"])).sum())
            rec.update(
                present=True, header=header, rows=len(df), missing_rows=exp - len(df),
                pct_of_expected=round(100.0 * len(df) / exp, 3),
                open_time_unit=("mixed" if ot_mixed else ("us" if ot_us else "ms")), close_time_unit=("us" if ct_us else "ms"),
                first_bar=iso(ot.min()), last_bar=iso(ot.max()),
                dup_open_times=int(pd.Series(ot).duplicated().sum()), dup_full_rows=int(df.duplicated().sum()),
                not_sorted=int((np.diff(ot) <= 0).sum()), off_grid=int((ot % BAR != 0).sum()),
                outside_month=int(((ot < a) | (ot >= b)).sum()),
                close_minus_open_not_299999=int((ct - ot != BAR - 1).sum()),
                nan_cells=int(df.isna().sum().sum()),
                nonpos_price=int((num[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
                ohlc_inconsistent=ohlc_bad, zero_volume_bars=int((num["volume"] == 0).sum()),
            )
            file_rows.append(rec)
            frames.append(pd.DataFrame({"t": ot, "v": num["volume"].to_numpy(), "qv": num["quote_volume"].to_numpy(),
                                        "c": num["close"].to_numpy(), "flat": (num["high"] == num["low"]).to_numpy()}))
        allt = pd.concat(frames, ignore_index=True).sort_values("t", kind="stable")
        cross_dups = int(allt["t"].duplicated().sum())
        u = allt.drop_duplicates("t").reset_index(drop=True)
        t = u["t"].to_numpy()
        first, last = int(t[0]), int(t[-1])
        d = np.diff(t)
        gi = np.nonzero(d > BAR)[0]
        for i in gi:
            prev, nxt = int(t[i]), int(t[i + 1])
            mm = (nxt - prev - BAR) // 60_000
            all_gaps.append({"coin": sym, "last_bar_before": iso(prev), "first_missing_bar": iso(prev + BAR),
                             "next_bar": iso(nxt), "missing_bars": (nxt - prev) // BAR - 1, "missing_minutes": mm,
                             "gt_15min": bool(mm > 15)})
        z = u["v"].to_numpy() == 0
        i = 0
        while i < len(z):
            if z[i]:
                j = i
                while j + 1 < len(z) and z[j + 1] and t[j + 1] - t[j] == BAR:
                    j += 1
                zero_runs.append({"coin": sym, "first_bar": iso(t[i]), "last_bar": iso(t[j]), "bars": j - i + 1,
                                  "minutes": (j - i + 1) * 5, "all_flat_hl": bool(u["flat"].to_numpy()[i:j + 1].all()),
                                  "close_constant": bool(np.all(u["c"].to_numpy()[i:j + 1] == u["c"].to_numpy()[i]))})
                i = j + 1
            else:
                i += 1
        wk = (t - MON0) // WEEK
        cnt = pd.Series(wk).value_counts()
        cnt_traded = pd.Series(wk[u["v"].to_numpy() > 0]).value_counts()
        w0 = (pd.Timestamp(W_FIRST, tz="UTC").value // 1_000_000 - MON0) // WEEK
        w1 = (pd.Timestamp(W_LAST, tz="UTC").value // 1_000_000 - MON0) // WEEK
        last_traded = int(t[np.nonzero(u["v"].to_numpy() > 0)[0][-1]])
        for w in range(int(w0), int(w1) + 1):
            ws, we = MON0 + w * WEEK, MON0 + (w + 1) * WEEK
            n, nt = int(cnt.get(w, 0)), int(cnt_traded.get(w, 0))
            if ws < WIN_START or we > WIN_END:
                status = "window_truncated"
            elif we <= first:
                status = "pre_listing"
            elif ws < first:
                status = "listing_week"
            elif ws > last:
                status = "post_last_bar"
            elif n < 0.99 * 2016:
                status = "below_99pct"
            else:
                status = "full"
            week_rows.append({"coin": sym, "week_start": pd.Timestamp(ws, unit="ms", tz="UTC").strftime("%Y-%m-%d"),
                              "bars": n, "expected": 2016, "pct": round(100.0 * n / 2016, 3), "bars_with_volume": nt,
                              "pct_bars_with_volume": round(100.0 * nt / 2016, 3), "status": status})
        wdf = pd.DataFrame([r for r in week_rows if r["coin"] == sym])
        full = wdf[wdf.status == "full"]
        full_traded = full[full.pct_bars_with_volume >= 99.0]
        summary["coins"][sym] = {
            "first_bar": iso(first), "last_bar": iso(last), "last_bar_with_volume": iso(last_traded),
            "unique_bars": int(len(t)), "cross_file_dup_open_times": cross_dups, "gaps_any": int(len(gi)),
            "gaps_gt_15min": int(sum(1 for g in all_gaps if g["coin"] == sym and g["gt_15min"])),
            "missing_bars_after_first_bar": int(((last - first) // BAR + 1) - len(t)),
            "zero_volume_bars": int(z.sum()),
            "full_weeks_99pct_bars": int(len(full)),
            "first_full_week": full.week_start.min() if len(full) else None,
            "last_full_week_99pct_bars": full.week_start.max() if len(full) else None,
            "last_week_99pct_bars_and_99pct_traded": full_traded.week_start.max() if len(full_traded) else None,
            "weeks_below_99pct_in_listing": wdf[wdf.status == "below_99pct"].week_start.tolist(),
            "weeks_full_but_traded_lt_99pct": full[full.pct_bars_with_volume < 99.0].week_start.tolist(),
        }
    pd.DataFrame(file_rows).to_csv(os.path.join(OUT, "audit_files.csv"), index=False)
    pd.DataFrame(all_gaps, columns=["coin", "last_bar_before", "first_missing_bar", "next_bar", "missing_bars",
                                    "missing_minutes", "gt_15min"]).to_csv(os.path.join(OUT, "gaps_all.csv"), index=False)
    pd.DataFrame(week_rows).to_csv(os.path.join(OUT, "week_coverage.csv"), index=False)
    pd.DataFrame(zero_runs, columns=["coin", "first_bar", "last_bar", "bars", "minutes", "all_flat_hl", "close_constant"]
                 ).to_csv(os.path.join(OUT, "zero_volume_runs.csv"), index=False)
    json.dump(summary, open(os.path.join(OUT, "audit_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
