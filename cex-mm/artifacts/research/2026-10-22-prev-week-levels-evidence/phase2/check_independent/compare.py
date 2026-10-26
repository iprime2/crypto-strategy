#!/usr/bin/env python3
"""Compare indep_results.json / indep events with the run's results.json and events files (read-only)."""
import json

import numpy as np
import pandas as pd

ROOT = '/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2'
OUT = ROOT + '/check_indep'
me = json.load(open(OUT + '/indep_results.json'))
run = json.load(open(ROOT + '/run/results.json'))

rows = []
TOL_M, TOL_N = 0.1, 1
for p in ['OT', 'OX']:
    R = run[p]
    c = R['cells']['4h']
    g = R['gating_4h']
    M = me[p]
    pairs = [
        ('n real events', M['n_real'], c['real']['n'], 'n'),
        ('n P1 events', M['n_P1'], c['P1']['n'], 'n'),
        ('real gross mean', M['real_gross'], c['real']['gross'], 'm'),
        ('real net base mean', M['real_net_base'], c['real']['net_base'], 'm'),
        ('P1 gross mean', M['P1_gross'], c['P1']['gross'], 'm'),
        ('real - P1 gross', M['diff_real_P1'], g['2_diff_P1']['diff_gross'], 'm'),
        ('H1 real net base', M['H1_net_base'], g['3_halves']['H1_net_base'], 'm'),
        ('H2 real net base', M['H2_net_base'], g['3_halves']['H2_net_base'], 'm'),
        ('coins with net > 0', M['coins_pos_net'], g['4_coins']['coins_pos_net_base'], 'n'),
        # extra, non-required
        ('H1 real - P1 (extra)', M['H1_diff_P1'], g['3_halves']['H1_diff_P1'], 'm'),
        ('H2 real - P1 (extra)', M['H2_diff_P1'], g['3_halves']['H2_diff_P1'], 'm'),
        ('real net stress (extra)', M['real_net_stress'], c['real']['net_stress'], 'm'),
        ('P1_in gross (extra)', M['P1_in_gross'], c['P1_in']['gross'], 'm'),
        ('P1_out gross (extra)', M['P1_out_gross'], c['P1_out']['gross'], 'm'),
        ('coin-weeks used (extra)', M['coin_weeks_used'], R['coin_weeks_used'], 'n'),
        ('coin-weeks skipped (extra)', M['coin_weeks_skipped'], R['coin_weeks_skipped'], 'n'),
        ('boot P(net<=0) (extra)', M['boot']['p_net_le0'], g['1_net']['p_net_le0'], 'p'),
        ('boot P(diff<=0) (extra)', M['boot']['p_diff_le0'], g['2_diff_P1']['p_diff_le0'], 'p'),
        ('boot diff CI lo (extra)', M['boot']['diff_ci'][0], g['2_diff_P1']['ci'][0], 'm'),
        ('boot diff CI hi (extra)', M['boot']['diff_ci'][1], g['2_diff_P1']['ci'][1], 'm'),
    ]
    for name, a, b, kind in pairs:
        d = abs(a - b)
        ok = d <= (TOL_N if kind == 'n' else TOL_M if kind == 'm' else 1e-12)
        rows.append(dict(panel=p, quantity=name, indep=a, run=b, abs_diff=d, within_tol=bool(ok),
                         gating=('extra' not in name)))
    # per coin
    rc = R['per_coin']['4h']['coins']
    worst = 0.0
    for coin, v in M['per_coin_net_base'].items():
        key = coin
        worst = max(worst, abs(v - rc[key]['net_base']))
        if M['per_coin_n'][coin] != rc[key]['n']:
            print('per-coin n mismatch', p, coin, M['per_coin_n'][coin], rc[key]['n'])
    rows.append(dict(panel=p, quantity='max |per-coin net diff| (extra)', indep=worst, run=0.0, abs_diff=worst,
                     within_tol=bool(worst <= TOL_M), gating=False))

df = pd.DataFrame(rows)
pd.set_option('display.width', 200)
print(df.to_string(index=False))
df.to_csv(OUT + '/compare_table.csv', index=False)
all_gating_ok = bool(df[df.gating].within_tol.all())
print('ALL GATING WITHIN TOL:', all_gating_ok)

# ---- row-level event comparison at 4 h (real + P1) ----
evcmp = {}
for p in ['OT', 'OX']:
    mine = pd.read_csv(f'{OUT}/indep_events_{p}_4h.csv.gz')
    mine = mine[mine.status == 'ok']
    rr = pd.read_csv(f'{ROOT}/run/events_{p}.csv.gz')
    rr = rr[(rr.horizon == '4h') & (~rr.level_kind.str.startswith('P3'))]
    k = ['coin', 'week_start', 'level_kind']
    m = mine.merge(rr, on=k, how='outer', suffixes=('_me', '_run'), indicator=True)
    b = m[m._merge == 'both']
    # my exit_time is the exit bar's open; the run's is the bar's close (= open + 5 min)
    et_me = pd.to_datetime(b.exit_time_me) + pd.Timedelta(minutes=5)
    et_run = pd.to_datetime(b.exit_time_run)
    evcmp[p] = dict(matched=int(len(b)), only_indep=int((m._merge == 'left_only').sum()),
                    only_run=int((m._merge == 'right_only').sum()),
                    entry_time_mismatch=int((b.entry_time_me != b.entry_time_run).sum()),
                    exit_time_mismatch_after_5min_shift=int((et_me != et_run).sum()),
                    max_abs_gross_diff_bps=float(np.abs(b.gross - b.gross_bps).max()),
                    max_rel_level_diff=float(np.abs(b.level_px_me / b.level_px_run - 1).max()),
                    max_abs_exit_px_diff=float(np.abs(b.exit_px_me - b.exit_px_run).max()))
print(json.dumps(evcmp, indent=1))

# ---- coin-week used flags ----
cw = {}
for p in ['OT', 'OX']:
    rr = pd.read_csv(f'{ROOT}/run/coin_weeks_{p}.csv.gz')
    rr['week'] = pd.to_datetime(rr.W, unit='ms', utc=True).dt.strftime('%Y-%m-%d')
    used_run = set(map(tuple, rr[rr.used][['coin', 'week']].values))
    mine = pd.read_csv(f'{OUT}/indep_events_{p}_4h.csv.gz')
    cw[p] = dict(run_used=len(used_run), indep_used=me[p]['coin_weeks_used'])
print(json.dumps(cw))

json.dump(dict(all_gating_within_tol=all_gating_ok, events=evcmp, coin_weeks=cw,
               table=df.to_dict('records')), open(OUT + '/compare.json', 'w'), indent=1, default=float)
