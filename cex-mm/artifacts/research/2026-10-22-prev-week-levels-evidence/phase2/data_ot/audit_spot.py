#!/usr/bin/env python3
"""Audit the OT panel: Binance SPOT 5m klines, 13 USDT pairs, first month .. 2020-04 (read-only on the data).

Outputs in research3/p2/data_ot/<tag>/ (tag = pre | post, i.e. before / after patch_spot_gaps.py):
  audit_files.csv       one row per (pair, month) file: header, rows vs expected, units, dups, off-grid, integrity
  gaps_all.csv          every gap (consecutive open times more than 5 min apart) per pair, after the first bar
  zero_volume_runs.csv  runs of consecutive zero-volume bars per pair
  week_coverage.csv     bars per Monday-00:00-UTC week per pair, from the listing week to the week of 2020-04-27
  outlier_bars.csv      bars whose high/low range exceeds 20 % or whose |ln(close/open)| exceeds 10 % (information)
  audit_summary.json    aggregates used by the report

Usage: python3 -I audit_spot.py <scratchpad_root> <tag>
"""
import calendar
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT, TAG = sys.argv[1], sys.argv[2]
KD = os.path.join(ROOT, "universe", "spot5m")
OUT = os.path.join(ROOT, "research3", "p2", "data_ot", TAG)
SYMS = ["BTC", "ETH", "BNB", "LTC", "NEO", "XRP", "ADA", "EOS", "XLM", "TRX", "ETC", "LINK", "DOGE"]
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
BAR = 300_000
WEEK = 7 * 86_400_000
MON0 = 4 * 86_400_000  # 1970-01-05, a Monday, 00:00 UTC in ms
WIN_END = int(pd.Timestamp("2020-05-01", tz="UTC").value // 1_000_000)  # exclusive
LAST_EVENT_WEEK = int(pd.Timestamp("2020-04-20", tz="UTC").value // 1_000_000)
NEXP = WEEK // BAR  # 2016
COVERAGE = 0.99


def ms_of(month):
    y, m = map(int, month.split("-"))
    a = int(pd.Timestamp(year=y, month=m, day=1, tz="UTC").value // 1_000_000)
    nd = calendar.monthrange(y, m)[1]
    return a, a + nd * 86_400_000, nd * 288


def iso(ms):
    return pd.Timestamp(int(ms), unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M")


def day(ms):
    return pd.Timestamp(int(ms), unit="ms", tz="UTC").strftime("%Y-%m-%d")


def files_of(pair):
    pre = f"binance-spot-{pair}-5m-"
    return sorted(f for f in os.listdir(KD) if f.startswith(pre) and f.endswith(".csv"))


def load(path):
    with open(path, "rb") as f:
        first = f.readline()
    header = not first[:1].isdigit()
    df = pd.read_csv(path, header=0 if header else None, names=None if header else COLS,
                     dtype={"open_time": "int64", "close_time": "int64"})
    if header and list(df.columns) != COLS:
        raise RuntimeError(f"unexpected header in {path}: {list(df.columns)}")
    if df.shape[1] != 12:
        raise RuntimeError(f"unexpected column count in {path}: {df.shape[1]}")
    return df, header


def runs(mask, t):
    """Runs of consecutive True in mask over contiguous 5m bars (a time gap ends a run)."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1] and t[j + 1] - t[j] == BAR:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    file_rows, gaps, zruns, weeks, outl = [], [], [], [], []
    summary = {"tag": TAG, "coins": {}}
    for sym in SYMS:
        pair = f"{sym}USDT"
        frames = []
        for fn in files_of(pair):
            month = fn[-11:-4]
            a, b, exp = ms_of(month)
            df, header = load(os.path.join(KD, fn))
            ot_raw, ct_raw = df["open_time"].to_numpy(), df["close_time"].to_numpy()
            ot_us = (ot_raw > 1e14)
            ct_us = (ct_raw > 1e14)
            ot = np.where(ot_us, ot_raw // 1000, ot_raw)
            ct = np.where(ct_us, ct_raw // 1000, ct_raw)
            num = df[["open", "high", "low", "close", "volume", "quote_volume", "count"]].astype(float)
            ohlc_bad = ((num["high"] < num[["open", "close"]].max(axis=1)) |
                        (num["low"] > num[["open", "close"]].min(axis=1)) | (num["low"] > num["high"]))
            vol0 = (num["volume"] == 0).to_numpy()
            flat = (num["high"] == num["low"]).to_numpy()
            file_rows.append(dict(
                coin=pair, month=month, file=fn, header=header, rows=len(df), expected_rows=exp,
                missing_rows=exp - len(df), pct_of_expected=round(100.0 * len(df) / exp, 3),
                open_time_unit=("mixed" if ot_us.any() and (~ot_us).any() else ("us" if ot_us.any() else "ms")),
                close_time_unit=("mixed" if ct_us.any() and (~ct_us).any() else ("us" if ct_us.any() else "ms")),
                first_bar=iso(ot.min()), last_bar=iso(ot.max()),
                dup_open_times=int(pd.Series(ot).duplicated().sum()), dup_full_rows=int(df.duplicated().sum()),
                not_increasing=int((np.diff(ot) <= 0).sum()), off_grid=int((ot % BAR != 0).sum()),
                outside_month=int(((ot < a) | (ot >= b)).sum()),
                close_minus_open_not_299999=int((ct - ot != BAR - 1).sum()),
                nan_cells=int(df.isna().sum().sum()),
                nonpos_price=int((num[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
                ohlc_inconsistent=int(ohlc_bad.sum()), zero_volume_bars=int(vol0.sum()),
                zero_volume_nonflat=int((vol0 & ~flat).sum()), zero_trades_bars=int((num["count"] == 0).sum()),
            ))
            frames.append(pd.DataFrame({"t": ot, "ct": ct, "o": num["open"].to_numpy(), "h": num["high"].to_numpy(),
                                        "l": num["low"].to_numpy(), "c": num["close"].to_numpy(),
                                        "v": num["volume"].to_numpy(), "flat": flat}))
        allb = pd.concat(frames, ignore_index=True).sort_values("t", kind="stable")
        cross_dups = int(allb["t"].duplicated().sum())
        u = allb.drop_duplicates("t").reset_index(drop=True)
        u = u[u["t"] < WIN_END].reset_index(drop=True)
        t = u["t"].to_numpy()
        first, last = int(t[0]), int(t[-1])
        # off-grid rows would break the gap logic; they are counted per file above (0 expected)
        d = np.diff(t)
        ctv = u["ct"].to_numpy()
        ong = (t % BAR == 0)
        for i in np.nonzero(d > BAR)[0]:
            prev, nxt = int(t[i]), int(t[i + 1])
            mm = (nxt - prev - BAR) / 60_000  # minutes with no bar opening on the bar clock (fractional if off-grid)
            halt = (nxt - int(ctv[i]) - 1) / 60_000  # from the last bar's close time to the next bar's open
            gaps.append(dict(coin=pair, last_bar_before=iso(prev),
                             last_close_before=pd.Timestamp(int(ctv[i]) + 1, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
                             first_missing_bar=iso(prev + BAR),
                             next_bar=pd.Timestamp(nxt, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M:%S"),
                             first_missing_ms=prev + BAR, next_bar_ms=nxt,
                             missing_bars=round(mm / 5, 2), missing_minutes=round(mm, 2), halt_minutes=round(halt, 2),
                             ends_off_grid=bool((not ong[i]) or (not ong[i + 1])),
                             longer_than_15min=bool(mm > 15),
                             close_before=float(u["c"].iloc[i]), open_after=float(u["o"].iloc[i + 1]),
                             jump_bps=round(1e4 * np.log(u["o"].iloc[i + 1] / u["c"].iloc[i]), 2)))
        # tail: data must reach 2020-04-30 23:55
        tail_missing = int((WIN_END - BAR - last) // BAR)
        z = (u["v"].to_numpy() == 0)
        fl = u["flat"].to_numpy()
        for i, j in runs(z, t):
            zruns.append(dict(coin=pair, first_bar=iso(t[i]), last_bar=iso(t[j]), bars=j - i + 1,
                              minutes=(j - i + 1) * 5, all_flat_hl=bool(fl[i:j + 1].all()),
                              first_ms=int(t[i]), last_ms=int(t[j])))
        rng = np.log(u["h"].to_numpy() / u["l"].to_numpy())
        oc = np.abs(np.log(u["c"].to_numpy() / u["o"].to_numpy()))
        for i in np.nonzero((rng > np.log(1.2)) | (oc > 0.10))[0]:
            outl.append(dict(coin=pair, bar=iso(t[i]), open=u["o"].iloc[i], high=u["h"].iloc[i], low=u["l"].iloc[i],
                             close=u["c"].iloc[i], volume=u["v"].iloc[i], range_pct=round(100 * (np.exp(rng[i]) - 1), 2),
                             oc_pct=round(100 * (np.exp(oc[i]) - 1), 2)))
        # weeks
        wk = (t - MON0) // WEEK
        cnt = pd.Series(wk).value_counts()
        cnt_g = pd.Series(wk[ong]).value_counts()
        cnt_v = pd.Series(wk[~z]).value_counts()
        w_first = (first - MON0) // WEEK
        w_last = (LAST_EVENT_WEEK - MON0) // WEEK + 1  # include 2020-04-27 (truncated) for completeness
        wrows = []
        for w in range(int(w_first), int(w_last) + 1):
            ws = MON0 + w * WEEK
            n = int(cnt.get(w, 0))
            if ws + WEEK > WIN_END:
                status = "window_truncated"
            elif ws < first:
                status = "listing_week"
            else:
                status = "full" if n >= COVERAGE * NEXP else "below_99pct"
            wrows.append(dict(coin=pair, week_start=pd.Timestamp(ws, unit="ms", tz="UTC").strftime("%Y-%m-%d"),
                              week_ms=int(ws), bars=n, bars_on_grid=int(cnt_g.get(w, 0)), expected=NEXP,
                              pct=round(100.0 * n / NEXP, 3),
                              bars_with_volume=int(cnt_v.get(w, 0)), zero_volume_bars=n - int(cnt_v.get(w, 0)),
                              status=status, ge99=bool(n >= COVERAGE * NEXP),
                              ge99_on_grid=bool(int(cnt_g.get(w, 0)) >= COVERAGE * NEXP)))
        wdf = pd.DataFrame(wrows)
        # event-week eligibility per Phase 1 rule: week w and week w-1 both >= 99 % of 2016 bars
        wdf["prev_ge99"] = wdf["ge99"].shift(1, fill_value=False)
        wdf["event_eligible"] = wdf["ge99"] & wdf["prev_ge99"] & (wdf["week_ms"] <= LAST_EVENT_WEEK)
        weeks.append(wdf)
        inwin = wdf[wdf["week_ms"] <= LAST_EVENT_WEEK]
        afterlist = inwin[inwin["week_ms"] >= first]
        full = afterlist[afterlist["ge99"]]
        elig = inwin[inwin["event_eligible"]]
        g = pd.DataFrame([x for x in gaps if x["coin"] == pair])
        summary["coins"][pair] = dict(
            first_bar=iso(first), last_bar=iso(last), tail_missing_bars_to_2020_04_30_2355=tail_missing,
            unique_bars=int(len(t)), cross_file_dup_open_times=cross_dups,
            span_bars=int((last - first) // BAR + 1), missing_bars_after_first_bar=int((last - first) // BAR + 1 - len(t)),
            off_grid_bars=int((~ong).sum()),
            off_grid_first=(iso(t[~ong].min()) if (~ong).any() else None),
            off_grid_last=(iso(t[~ong].max()) if (~ong).any() else None),
            weeks_ge99_differ_on_grid=wdf.loc[wdf["ge99"] != wdf["ge99_on_grid"], "week_start"].tolist(),
            gaps_any=int(len(g)), gaps_gt15min=int((g["missing_minutes"] > 15).sum()) if len(g) else 0,
            gaps_ge60min=int((g["missing_minutes"] >= 60).sum()) if len(g) else 0,
            gaps_ge120min=int((g["missing_minutes"] >= 120).sum()) if len(g) else 0,
            missing_minutes_total=round(float(g["missing_minutes"].sum()), 2) if len(g) else 0,
            zero_volume_bars=int(z.sum()),
            first_monday_week_after_listing=(pd.Timestamp(int(afterlist["week_ms"].iloc[0]), unit="ms", tz="UTC")
                                             .strftime("%Y-%m-%d") if len(afterlist) else None),
            first_ge99_week=(full["week_start"].iloc[0] if len(full) else None),
            weeks_after_listing_through_2020_04_20=int(len(afterlist)),
            weeks_ge99_through_2020_04_20=int(len(full)),
            weeks_below99_after_listing=afterlist.loc[~afterlist["ge99"], "week_start"].tolist(),
            first_event_week=(elig["week_start"].iloc[0] if len(elig) else None),
            event_eligible_weeks_through_2020_04_20=int(len(elig)),
        )
    pd.DataFrame(file_rows).to_csv(os.path.join(OUT, "audit_files.csv"), index=False)
    pd.DataFrame(gaps).to_csv(os.path.join(OUT, "gaps_all.csv"), index=False)
    pd.DataFrame(zruns).to_csv(os.path.join(OUT, "zero_volume_runs.csv"), index=False)
    pd.concat(weeks, ignore_index=True).to_csv(os.path.join(OUT, "week_coverage.csv"), index=False)
    pd.DataFrame(outl).to_csv(os.path.join(OUT, "outlier_bars.csv"), index=False)
    fr = pd.DataFrame(file_rows)
    summary["files"] = dict(
        n=int(len(fr)), with_header=int(fr["header"].sum()),
        open_time_units=fr["open_time_unit"].value_counts().to_dict(),
        close_time_units=fr["close_time_unit"].value_counts().to_dict(),
        **{k: int(fr[k].sum()) for k in ["dup_open_times", "dup_full_rows", "not_increasing", "off_grid", "outside_month",
                                         "close_minus_open_not_299999", "nan_cells", "nonpos_price",
                                         "ohlc_inconsistent", "zero_volume_bars", "zero_volume_nonflat",
                                         "zero_trades_bars"]})
    with open(os.path.join(OUT, "audit_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
