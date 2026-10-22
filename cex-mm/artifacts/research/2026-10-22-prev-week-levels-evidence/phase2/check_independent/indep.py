#!/usr/bin/env python3
"""Independent recompute of the Phase 2 gating numbers (panels OT and OX, h = 4 h).

Written only from research3/phase2_plan.md and research3/plan.md. It does not read or import the run
agent's code (p2/run/*.py) or the Phase 1 engine. It reads the raw 5 m CSVs directly.

Definitions used (plan text -> code):
- Week: Monday 00:00 UTC to next Monday 00:00 UTC (2,016 bars of 5 m). Bar = keyed by open time.
- Coverage: a coin-week w is used iff week w and week w-1 each have >= 99 % of 2,016 bars present
  (>= 1,996). A bar is "present" if a row with that open time exists (zero-volume rows count).
- PWH / PWL = max high / min low over week w-1; O = open of the first present bar of week w.
- D_H = ln(PWH/O), D_L = ln(O/PWL). P1 levels: O*exp(m*D_H) (above), O*exp(-m*D_L) (below),
  m in {0.5, 0.75, 1.25, 1.5}.
- First touch inside week w: first bar with high > L*(1+0.5e-4) (above) or low < L*(1-0.5e-4) (below).
- T entry: at L on the touch bar, breakout direction (long above, short below).
- Exit: close of the bar that ends 4 h after the touch bar opens = bar with open time touch+4h-5m.
  If that bar lies after the data end the event is dropped (plan). If it is missing inside the data
  (outage) the event is dropped too (primary); a sensitivity uses the last close at or before it.
- Gross = s * (X/L - 1) * 1e4, s = +1 above, -1 below. Net base = gross - 14.62.
- OT: candidate event weeks from (first Monday week at or after the first bar) + 1 week through
  2020-04-20; data capped at 2020-05-01 00:00. Halves by week start: < 2019-01-01 is half 1.
- OX: candidate event weeks 2022-01-03 .. 2026-09-21; data capped at 2026-10-01 00:00.
  "Delisted coins stay in until their last full week": series cut after its last bar with volume > 0
  (post-delisting flat placeholder rows are not trading). Sensitivity: no cut. Halves by week start:
  < 2024-05-01 is half 1.
"""
import glob
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd

ROOT = '/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad'
OT_DIR = ROOT + '/universe/spot5m'
OX_DIR = ROOT + '/universe/ox5m'
OUT = ROOT + '/research3/p2/check_indep'

BAR = 300
WEEK = 7 * 86400
MON0 = 4 * 86400                     # 1970-01-05 00:00 UTC is a Monday
NB = WEEK // BAR                     # 2016
MINB = int(np.ceil(0.99 * NB))       # 1996
TH = 0.5e-4                          # 0.5 bp
COST_BASE = 14.62
COST_STRESS = 30.62
MS = [0.5, 0.75, 1.25, 1.5]
P1_REQUIRE_POS = True
DSTAT = []

OT_COINS = ['BTC', 'ETH', 'BNB', 'LTC', 'NEO', 'XRP', 'ADA', 'EOS', 'XLM', 'TRX', 'ETC', 'LINK', 'DOGE']
OX_COINS = ['1000SHIB', 'SOL', 'SAND', 'LUNA', 'MANA', 'DOT', 'AVAX', 'FTM', 'MATIC', 'GALA', 'AXS',
            'DYDX', 'FIL', 'LRC', 'CRV']


def ts(s):
    return int(pd.Timestamp(s, tz='UTC').timestamp())


def iso(t):
    return pd.Timestamp(int(t), unit='s', tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ')


def day(t):
    return pd.Timestamp(int(t), unit='s', tz='UTC').strftime('%Y-%m-%d')


def week_floor(t):
    return (t - MON0) // WEEK * WEEK + MON0


def load_coin(files):
    parts = []
    for f in files:
        df = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5], dtype=str)
        df = df[df[0].str.match(r'^\d')]   # drop a header row if present
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    t = df[0].astype(np.int64).values
    t = np.where(t > 10**14, t // 1000, t)          # us -> ms
    t = t // 1000                                     # ms -> s
    o, h, l, c, v = (df[i].astype(float).values for i in range(1, 6))
    order = np.argsort(t, kind='stable')
    t, o, h, l, c, v = t[order], o[order], h[order], l[order], c[order], v[order]
    info = {'rows': int(len(t)), 'dup_open_times': int((np.diff(t) == 0).sum()),
            'off_grid': int((t % BAR != 0).sum())}
    keep = np.r_[True, np.diff(t) != 0]
    t, o, h, l, c, v = t[keep], o[keep], h[keep], l[keep], c[keep], v[keep]
    return t, o, h, l, c, v, info


def build_grid(t, o, h, l, c, v, cap):
    """Dense 5 m grid starting at the Monday of the first bar; NaN = missing bar."""
    m = t < cap
    t, o, h, l, c, v = t[m], o[m], h[m], l[m], c[m], v[m]
    g0 = week_floor(t[0])
    nweeks = (week_floor(t[-1]) - g0) // WEEK + 2      # one spare week for exits
    n = nweeks * NB
    idx = (t - g0) // BAR
    G = {k: np.full(n, np.nan) for k in 'ohlcv'}
    for k, arr in zip('ohlcv', (o, h, l, c, v)):
        G[k][idx] = arr
    G['g0'] = g0
    G['nweeks'] = nweeks
    G['last_t'] = int(t[-1])
    G['first_t'] = int(t[0])
    G['present'] = ~np.isnan(G['c'])
    return G


def coin_events(coin, G, wk_from, wk_to, data_end_t):
    """Return (list of event dicts, coin-week stats). data_end_t = open time of last usable bar."""
    g0 = G['g0']
    cnt = G['present'].reshape(-1, NB).sum(axis=1)
    events = []
    used, skipped = [], []
    k0 = max(1, (wk_from - g0) // WEEK)
    k1 = (wk_to - g0) // WEEK
    for k in range(k0, k1 + 1):
        W = g0 + k * WEEK
        if W < wk_from or W > wk_to:
            continue
        if k >= G['nweeks'] or cnt[k] < MINB or cnt[k - 1] < MINB:
            skipped.append(W)
            continue
        used.append(W)
        ps, pe = (k - 1) * NB, k * NB
        ws, we = k * NB, (k + 1) * NB
        PWH = np.nanmax(G['h'][ps:pe])
        PWL = np.nanmin(G['l'][ps:pe])
        pres = G['present'][ws:we]
        j0 = int(np.argmax(pres))
        O = G['o'][ws + j0]
        DH = np.log(PWH / O)
        DL = np.log(O / PWL)
        levels = [('PWH', 'H', 'real', None, PWH), ('PWL', 'L', 'real', None, PWL)]
        # Plan: D_H, D_L > 0. Where D <= 0 the four P1 levels of that side would equal the real level
        # (or lie on the wrong side of O); P1_REQUIRE_POS=True creates none (Phase 1 convention),
        # False keeps them (literal formula, sensitivity).
        if DH > 0 or not P1_REQUIRE_POS:
            for mm in MS:
                levels.append(('P1H_%g' % mm, 'H', 'P1', mm, O * np.exp(mm * DH)))
        if DL > 0 or not P1_REQUIRE_POS:
            for mm in MS:
                levels.append(('P1L_%g' % mm, 'L', 'P1', mm, O * np.exp(-mm * DL)))
        DSTAT.append((coin, W, DH, DL))
        hh = G['h'][ws:we]
        ll = G['l'][ws:we]
        for kind, side, ctrl, mm, L in levels:
            if side == 'H':
                hit = hh > L * (1 + TH)
            else:
                hit = ll < L * (1 - TH)
            if not hit.any():
                continue
            j = int(np.argmax(hit))
            tt = W + j * BAR
            gi_exit = ws + j + (4 * 3600) // BAR - 1
            t_exit = W + (j + (4 * 3600) // BAR - 1) * BAR
            status = 'ok'
            X = np.nan
            X_alt = np.nan
            if t_exit > data_end_t:
                status = 'after_end'
            elif not G['present'][gi_exit]:
                status = 'missing_bar'
                # sensitivity: last close at or before the exit bar
                back = np.where(G['present'][ws + j:gi_exit + 1])[0]
                X_alt = G['c'][ws + j + back[-1]]
            else:
                X = G['c'][gi_exit]
                X_alt = X
            s = 1.0 if side == 'H' else -1.0
            gross = s * (X / L - 1.0) * 1e4 if status == 'ok' else np.nan
            gross_alt = s * (X_alt / L - 1.0) * 1e4 if status != 'after_end' else np.nan
            events.append(dict(coin=coin, week_start=day(W), W=W, level_kind=kind, side=side, ctrl=ctrl,
                               m=mm, level_px=L, entry_t=tt, entry_time=iso(tt), exit_time=iso(t_exit),
                               exit_px=X, gross=gross, gross_alt=gross_alt, status=status,
                               O=O, PWH=PWH, PWL=PWL, touch_open=G['o'][ws + j], open_outside=bool(O > PWH or O < PWL),
                               gap_through=bool((side == 'H' and G['o'][ws + j] > L * (1 + TH)) or
                                                (side == 'L' and G['o'][ws + j] < L * (1 - TH)))))
    return events, used, skipped


def mean(x):
    x = np.asarray(x, float)
    return float(np.mean(x)) if len(x) else float('nan')


def summarize(ev, coins, half_split, weeks_used):
    ok = ev[ev.status == 'ok'].copy()
    ok['net'] = ok.gross - COST_BASE
    r = ok[ok.ctrl == 'real']
    p = ok[ok.ctrl == 'P1']
    res = {}
    res['n_real'] = int(len(r))
    res['n_P1'] = int(len(p))
    res['real_gross'] = mean(r.gross)
    res['real_net_base'] = mean(r.net)
    res['real_net_stress'] = mean(r.gross - COST_STRESS)
    res['P1_gross'] = mean(p.gross)
    res['diff_real_P1'] = res['real_gross'] - res['P1_gross']
    res['P1_in_gross'] = mean(p[p.m < 1].gross)
    res['P1_out_gross'] = mean(p[p.m > 1].gross)
    res['n_P1_in'] = int((p.m < 1).sum())
    res['n_P1_out'] = int((p.m > 1).sum())
    h1 = r.W < half_split
    res['H1_n'] = int(h1.sum())
    res['H2_n'] = int((~h1).sum())
    res['H1_net_base'] = mean(r[h1].net)
    res['H2_net_base'] = mean(r[~h1].net)
    ph1 = p.W < half_split
    res['H1_diff_P1'] = mean(r[h1].gross) - mean(p[ph1].gross)
    res['H2_diff_P1'] = mean(r[~h1].gross) - mean(p[~ph1].gross)
    # halves by touch time (sensitivity)
    th1 = r.entry_t < half_split
    res['H1_net_base_by_touch'] = mean(r[th1].net)
    res['H2_net_base_by_touch'] = mean(r[~th1].net)
    res['H1_n_by_touch'] = int(th1.sum())
    pc = r.groupby('coin').net.mean()
    res['per_coin_net_base'] = {c: float(pc.get(c, np.nan)) for c in coins}
    res['per_coin_n'] = {c: int((r.coin == c).sum()) for c in coins}
    res['coins_pos_net'] = int((pc > 0).sum())
    res['n_coins'] = len(coins)
    res['coins_needed'] = int(np.ceil(2 * len(coins) / 3))
    # dropped
    res['dropped'] = {c: ev[(ev.ctrl == c) & (ev.status != 'ok')].status.value_counts().to_dict()
                      for c in ['real', 'P1']}
    # sensitivity: keep missing-bar exits at the last available close
    alt = ev[ev.status != 'after_end']
    ra = alt[alt.ctrl == 'real']
    pa = alt[alt.ctrl == 'P1']
    res['sens_keep_missing'] = {'n_real': int(len(ra)), 'n_P1': int(len(pa)),
                                'real_net_base': mean(ra.gross_alt - COST_BASE),
                                'diff_real_P1': mean(ra.gross_alt) - mean(pa.gross_alt)}
    # bootstrap (own implementation): resample Monday weeks with >= 1 used coin-week
    weeks = np.array(sorted(weeks_used))
    widx = {w: i for i, w in enumerate(weeks)}
    rng = np.random.default_rng(11)
    draws = rng.integers(0, len(weeks), size=(2000, len(weeks)))
    cntw = np.zeros((2000, len(weeks)))
    for b in range(2000):
        cntw[b] = np.bincount(draws[b], minlength=len(weeks))
    rw = r.W.map(widx).values
    pw = p.W.map(widx).values
    Wr = cntw[:, rw]
    Wp = cntw[:, pw]
    mr = (Wr * r.net.values).sum(1) / Wr.sum(1)
    mrg = (Wr * r.gross.values).sum(1) / Wr.sum(1)
    mpg = (Wp * p.gross.values).sum(1) / Wp.sum(1)
    d = mrg - mpg
    res['boot'] = {'n_weeks': int(len(weeks)), 'p_net_le0': float(np.mean(mr <= 0)),
                   'p_diff_le0': float(np.mean(d <= 0)),
                   'diff_ci': [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                   'net_ci': [float(np.percentile(mr, 2.5)), float(np.percentile(mr, 97.5))]}
    return res


def run_panel(name, coins, files_of, cap, wk_from_of, wk_to, half_split, cut_delist):
    allev = []
    meta = {}
    used_all = {}
    weeks_used = set()
    for coin in coins:
        files = files_of(coin)
        t, o, h, l, c, v, info = load_coin(files)
        m = t < cap
        t, o, h, l, c, v = t[m], o[m], h[m], l[m], c[m], v[m]
        cut = 0
        if cut_delist:
            lastv = np.where(v > 0)[0][-1]
            cut = int(len(t) - lastv - 1)
            t, o, h, l, c, v = t[:lastv + 1], o[:lastv + 1], h[:lastv + 1], l[:lastv + 1], c[:lastv + 1], v[:lastv + 1]
        G = build_grid(t, o, h, l, c, v, cap)
        wf = wk_from_of(G)
        ev, used, skipped = coin_events(coin, G, wf, wk_to, G['last_t'])
        allev += ev
        used_all[coin] = used
        weeks_used.update(used)
        meta[coin] = dict(info, first_bar=iso(G['first_t']), last_bar=iso(G['last_t']), bars_cut=cut,
                          first_cand_week=day(wf), used=len(used), skipped=len(skipped),
                          missing_after_first=int((~G['present'][(G['first_t'] - G['g0']) // BAR:
                                                                 (G['last_t'] - G['g0']) // BAR + 1]).sum()))
    ev = pd.DataFrame(allev)
    res = summarize(ev, coins, half_split, weeks_used)
    res['coin_weeks_used'] = int(sum(len(u) for u in used_all.values()))
    res['coin_weeks_skipped'] = int(sum(mm['skipped'] for mm in meta.values()))
    res['coin_weeks_used_halves'] = [int(sum(1 for u in used_all.values() for w in u if w < half_split)),
                                     int(sum(1 for u in used_all.values() for w in u if w >= half_split))]
    res['open_outside_prev_range_coin_weeks'] = int(ev.drop_duplicates(['coin', 'W']).open_outside.sum())
    res['gap_through_real_events'] = int(ev[(ev.ctrl == 'real') & (ev.status == 'ok')].gap_through.sum())
    res['meta'] = meta
    res['used_coin_weeks'] = sorted([c, day(w)] for c, u in used_all.items() for w in u)
    return res, ev


def main():
    t0 = time.time()
    out = {}
    # ---- OT ----
    def ot_files(c):
        return sorted(glob.glob(f'{OT_DIR}/binance-spot-{c}USDT-5m-*.csv'))

    def ot_from(G):
        # first Monday week at or after the first bar, + 1 week
        fm = week_floor(G['first_t'])
        if fm < G['first_t']:
            fm += WEEK
        return fm + WEEK

    res_ot, ev_ot = run_panel('OT', OT_COINS, ot_files, ts('2020-05-01'), ot_from, ts('2020-04-20'),
                              ts('2019-01-01'), cut_delist=False)
    out['OT'] = res_ot

    # ---- OX ----
    def ox_files(c):
        return sorted(glob.glob(f'{OX_DIR}/binance-{c}USDT-5m-*.csv'))

    res_ox, ev_ox = run_panel('OX', OX_COINS, ox_files, ts('2026-10-01'), lambda G: ts('2022-01-03'),
                              ts('2026-09-21'), ts('2024-05-01'), cut_delist=True)
    out['OX'] = res_ox
    # sensitivity: no delisting cut (flat placeholder rows treated as bars)
    res_ox_nc, ev_ox_nc = run_panel('OX', OX_COINS, ox_files, ts('2026-10-01'), lambda G: ts('2022-01-03'),
                                    ts('2026-09-21'), ts('2024-05-01'), cut_delist=False)
    out['OX_sens_no_delist_cut'] = {k: v for k, v in res_ox_nc.items() if k != 'meta'}
    dz = pd.DataFrame(DSTAT, columns=['coin', 'W', 'DH', 'DL'])
    out['D_le0_coin_weeks_all_runs'] = dz[(dz.DH <= 0) | (dz.DL <= 0)].drop_duplicates(['coin', 'W']).assign(
        week=lambda x: x.W.map(day)).drop(columns='W').to_dict('records')
    # sensitivity: literal formula, P1 levels kept where D <= 0
    global P1_REQUIRE_POS
    P1_REQUIRE_POS = False
    res_ot_lit, _ = run_panel('OT', OT_COINS, ot_files, ts('2020-05-01'), ot_from, ts('2020-04-20'),
                              ts('2019-01-01'), cut_delist=False)
    res_ox_lit, _ = run_panel('OX', OX_COINS, ox_files, ts('2026-10-01'), lambda G: ts('2022-01-03'),
                              ts('2026-09-21'), ts('2024-05-01'), cut_delist=True)
    out['OT_sens_P1_at_D0'] = {k: v for k, v in res_ot_lit.items() if k != 'meta'}
    out['OX_sens_P1_at_D0'] = {k: v for k, v in res_ox_lit.items() if k != 'meta'}
    P1_REQUIRE_POS = True
    out['runtime_s'] = time.time() - t0
    with open(f'{OUT}/indep_results.json', 'w') as f:
        json.dump(out, f, indent=1, default=float)
    cols = ['coin', 'week_start', 'level_kind', 'ctrl', 'level_px', 'entry_time', 'exit_time', 'exit_px',
            'gross', 'status', 'touch_open', 'gap_through']
    ev_ot[cols].to_csv(f'{OUT}/indep_events_OT_4h.csv.gz', index=False)
    ev_ox[cols].to_csv(f'{OUT}/indep_events_OX_4h.csv.gz', index=False)
    ev_ox_nc[cols].to_csv(f'{OUT}/indep_events_OX_4h_nocut.csv.gz', index=False)
    for p in ['OT', 'OX', 'OX_sens_no_delist_cut', 'OT_sens_P1_at_D0', 'OX_sens_P1_at_D0']:
        r = out[p]
        print(p, {k: r[k] for k in ['n_real', 'n_P1', 'real_gross', 'real_net_base', 'P1_gross', 'diff_real_P1',
                                    'H1_net_base', 'H2_net_base', 'coins_pos_net', 'coin_weeks_used',
                                    'coin_weeks_skipped']})
        print('   boot', r['boot'], 'dropped', r['dropped'])
    print('D<=0 coin-weeks', out['D_le0_coin_weeks_all_runs'])
    print('runtime', out['runtime_s'])


if __name__ == '__main__':
    main()
