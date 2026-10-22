"""Mechanical application of phase1_plan.md section 5 (+ section 6 extras, amendment A-2026-10-21) to phase2/<id>.json.
Reads only; writes phase2/verdicts.md (path given on argv[1]) and prints a compact log."""
import json, os, math, sys
from statistics import NormalDist

P = '/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research2/phase2'
OUT = sys.argv[1] if len(sys.argv) > 1 else None
G = 0.5772156649
def emax(n):
    N = NormalDist(); return (1 - G) * N.inv_cdf(1 - 1 / n) + G * N.inv_cdf(1 - 1 / (n * math.e))
M_DEC = 2.37             # decision multiplier: plan A3 text ("N_eff = 90 (multiplier 2.37)") and the task contract
M_FORM = emax(90)        # what the plan's own formula gives at N = 90 (= harness MULT_EFF, the summary.md 'hurdle')
M_24 = 1.98              # plan section 4 (N = 24)
REF = json.load(open(f'{P}/reference.json'))
SIXH_A_W = 1.21          # plan section 1: mean of the six single-decision-hour W books on A (no file on disk; plan text)

_cache = {}
def load(i):
    if i not in _cache:
        f = f'{P}/{i}.json'
        _cache[i] = json.load(open(f)) if os.path.exists(f) else None
    return _cache[i]

def f3(x): return f'{x:+.3f}'
def f2(x): return f'{x:+.2f}'
def pct(x, d=1): return f'{100*x:.{d}f}%'

# ------------------------------------------------------------------ generic pieces
def dd_check(r, tol_dd=0.02, tol_w7=0.01):
    fv, fb = r['full']['var'], r['full']['base']
    if 'matched_vol' in r:
        m = r['matched_vol']; mdd, w7, src = m['mdd'], m['worst7'], f"mv TV {m['tv']:.3f}"
    else:
        mdd, w7, src = fv['mdd'], fv['worst7'], 'raw, vol within 5%'
    ok = (mdd >= fb['mdd'] - tol_dd - 1e-12) and (w7 >= fb['worst7'] - tol_w7 - 1e-12)
    return ok, mdd, w7, fb['mdd'], fb['worst7'], src

def a6_check(J, keys):
    """A6: exposure = avg gross FULL var/base; if > +10 % on any panel, condition 2 must hold on the stress line (A POST is the only
    condition-2 window the stress line has)."""
    ratios = {}
    for p, k in keys.items():
        if k in J: ratios[p] = J[k]['full']['var']['gross'] / J[k]['full']['base']['gross'] - 1
    trig = any(v > 0.10 for v in ratios.values())
    rtxt = ' '.join(f'{p} {v:+.0%}' for p, v in ratios.items())
    a = J.get(keys['A'], {}).get('delta_funding_stress'); b = J.get(keys.get('B', ''), {}).get('delta_funding_stress') if keys.get('B') else None
    sa = (a['sharpe_post'] - a['base_sharpe_post']) if a else None
    sb = (b['sharpe_post'] - b['base_sharpe_post']) if b else None
    stxt = (f"stress A POST d {f3(sa)}" if sa is not None else 'stress A n/a') + (f", B POST d {f3(sb)}" if sb is not None else '')
    if not trig:
        return True, f"not triggered (gross {rtxt}); {stxt}"
    if sa is None:
        return False, f"TRIGGERED (gross {rtxt}) but no stress line on A"
    return sa >= -0.03, f"TRIGGERED (gross {rtxt}); {stxt} {'>=' if sa >= -0.03 else '<'} -0.03"

# ------------------------------------------------------------------ operational metrics (class II condition 3 and its neighbor clause)
def _full(J, k): return J[k]['full']
def op_turn_fund(J, cad, keys, t_cut, f_cut, label):
    ok = True; parts = []
    for p in ('A', 'B', 'C'):
        r = _full(J, f'{keys[p]}-{cad}')
        tb, tv = r['base']['turnover'], r['var']['turnover']; fb, fv = r['base']['funding_yr'], r['var']['funding_yr']
        dt, df = tv / tb - 1, fv / fb - 1
        o = True
        if t_cut is not None: o &= dt <= -t_cut
        if f_cut is not None: o &= df <= -f_cut
        ok &= o
        s = f"{p} turn {tb:.2f}->{tv:.2f}x ({dt:+.0%})"
        if f_cut is not None: s += f", fund {pct(fb,2)}->{pct(fv,2)} ({df:+.0%})"
        parts.append(s)
    return ok, f"{label}: " + '; '.join(parts)

def op_sig4(J, cad, keys):
    ok = True; parts = []
    for p in ('A', 'B', 'C'):
        r = J[f'{keys[p]}-{cad}']
        _, mdd, _, bmdd, _, _ = dd_check(r)
        tb, tv = r['full']['base']['turnover'], r['full']['var']['turnover']
        o = (mdd - bmdd >= 0.03) and (tv < tb); ok &= o
        parts.append(f"{p} mvDD {pct(bmdd)}->{pct(mdd)} ({100*(mdd-bmdd):+.1f}pp), turn {tb:.2f}->{tv:.2f}x")
    return ok, "mvDD >=3pp better AND turnover (trades proxy) lower: " + '; '.join(parts)

def op_capital(J, cad, keys, caps, f_orders, f_fund=None, fee_pp=None, label=''):
    ok = True; parts = []
    for p in ('A', 'C'):
        cb = J[f'{keys[p]}-{cad}'].get('capital', {})
        for c in caps:
            x = cb.get(c)
            if x is None:
                ok = False; parts.append(f"{p} ${c[:-2]} MISSING"); continue
            do = x['orders_yr'] / x['base_orders_yr'] - 1
            o = do <= -f_orders; s = f"{p} ${c[:-2]} orders {x['base_orders_yr']:.0f}->{x['orders_yr']:.0f} ({do:+.0%})"
            if fee_pp is not None:
                dfee = x['base_fees_yr'] - x['fees_yr']; o &= dfee >= fee_pp - 1e-12
                s += f", fees {pct(x['base_fees_yr'],3)}->{pct(x['fees_yr'],3)} (-{100*dfee:.3f}pp)"
            if f_fund is not None:
                dfu = x['funding_yr'] / x['base_funding_yr'] - 1; o &= dfu <= -f_fund
                s += f", fund {pct(x['base_funding_yr'],2)}->{pct(x['funding_yr'],2)} ({dfu:+.0%})"
            ok &= o; parts.append(s + ('' if o else ' FAIL'))
    return ok, label + ': ' + '; '.join(parts)

def op_cost2(J, cad, keys):
    ok, txt = op_capital(J, cad, keys, ['1000.0', '2500.0', '5000.0'], 0.30, fee_pp=0.0020, label='fees down >=0.20pp AND orders down >=30% vs round-nearest band 0 (A, C whole contracts)')
    r = _full(J, f'B-{cad}'); tb, tv = r['base']['turnover'], r['var']['turnover']
    txt += f"; B unrounded (information only per plan): turn {tb:.2f}->{tv:.2f}x, fees {pct(r['base']['fees_yr'],3)}->{pct(r['var']['fees_yr'],3)}"
    return ok, txt

def op_combob(J, cad, keys):
    ok, txt = op_capital(J, cad, keys, ['1000.0', '2500.0', '5000.0'], 0.30, f_fund=0.25, label='funding down >=25% AND orders down >=30% vs D round-nearest (A, C rounded)')
    r = _full(J, f'B-{cad}'); tb, tv = r['base']['turnover'], r['var']['turnover']; fb, fv = r['base']['funding_yr'], r['var']['funding_yr']
    oB = (tv / tb - 1 <= -0.30) and (fv / fb - 1 <= -0.25); ok &= oB
    txt += f"; B unrounded proxy: turn {tb:.2f}->{tv:.2f}x ({tv/tb-1:+.0%}), fund {pct(fb,2)}->{pct(fv,2)} ({fv/fb-1:+.0%}){'' if oB else ' FAIL'}"
    return ok, txt

OPS = {
    'trades_funding25': lambda J, cad, k: op_turn_fund(J, cad, k, 0.25, 0.25, 'trades/yr (turnover proxy) AND funding/yr down >=25%'),
    'orders15': lambda J, cad, k: op_turn_fund(J, cad, k, 0.15, None, 'orders/yr (turnover proxy) down >=15%'),
    'sz3': lambda J, cad, k: op_turn_fund(J, cad, k, 0.10, None, 'trades/yr <= base AND orders/yr down >=10% (turnover proxy for both)'),
    'dd3_trades': op_sig4,
    'cost2': op_cost2,
    'combob': op_combob,
}

# ------------------------------------------------------------------ extras (section 6 per cell); each returns list of (id, ok, text)
def ex_mvdd_noworse(J, cad, k, cell):
    ok, mdd, w7, bm, bw, src = dd_check(J[f"{k['B']}-{cad}"])
    return [('6 mvDD no worse', mdd >= bm - 1e-12, f"B FULL mvDD {pct(mdd)} vs {pct(bm)} ({src})")]

def ex_w7_noworse(J, cad, k, cell):
    out = []
    ok, mdd, w7, bm, bw, src = dd_check(J[f"{k['B']}-{cad}"])
    info = []
    for p in ('A', 'C'):
        _, _, w7p, _, bwp, _ = dd_check(J[f"{k[p]}-{cad}"]); info.append(f"{p} {pct(w7p)} vs {pct(bwp)}")
    out.append(('6 worst7 no worse', w7 >= bw - 1e-12, f"B FULL mv worst7 {pct(w7)} vs {pct(bw)} ({src}); info {', '.join(info)}"))
    return out

def ex_sig7a(J, cad, k, cell):
    r = J[f"{k['B']}-{cad}"]; d = r['post']['delta']
    ok, mdd, w7, bm, bw, src = dd_check(r)
    return [('6a +0.05 on B POST', d >= 0.05, f"B POST d {f3(d)}"), ('6b maxDD no worse', mdd >= bm - 1e-12, f"B FULL mvDD {pct(mdd)} vs {pct(bm)}")]

def ex_sig11(J, cad, k, cell):
    ctl = load('SIG-11__control_breakout_only')
    if ctl is None: return [('6a breakout>=sign on A,B', False, 'control json MISSING'), ('6b 50/50 beats both on B POST', False, 'control json MISSING')]
    vals = {f'{p} {w}': ctl[f'{p}-{cad}'][w]['delta'] for p in ('A', 'B') for w in ('full', 'post')}
    a_ok = all(v >= 0 for v in vals.values())
    me = J[f"B-{cad}"]['post']; s50, sb = me['var']['sharpe'], me['base']['sharpe']; sc = ctl[f'B-{cad}']['post']['var']['sharpe']
    b_ok = s50 > sb and s50 > sc
    return [('6a breakout-only >= sign-only on A and B', a_ok, 'control d ' + ', '.join(f'{kk} {f3(v)}' for kk, v in vals.items())),
            ('6b 50/50 beats both on B POST', b_ok, f"B POST Sharpe 50/50 {s50:.3f}, sign {sb:.3f}, breakout {sc:.3f}")]

def ex_funding_not_higher(J, cad, k, cell):
    parts = []; ok = True
    for p in ('A', 'B', 'C'):
        r = _full(J, f'{k[p]}-{cad}'); fv, fb = r['var']['funding_yr'], r['base']['funding_yr']; ok &= fv <= fb + 1e-12
        parts.append(f"{p} {pct(fb,2)}->{pct(fv,2)}")
    return [('6 funding/yr not higher', ok, '; '.join(parts))]

def ex_sz6b(J, cad, k, cell):
    v = {'A POST': J[f'A-{cad}']['post']['delta'], 'A FULL': J[f'A-{cad}']['full']['delta'], 'B POST': J[f'B-{cad}']['post']['delta'], 'C FULL': J[f'C-{cad}']['full']['delta']}
    return [('6 d >= +0.05 on A, B and C', all(x >= 0.05 for x in v.values()), ', '.join(f'{a} {f3(b)}' for a, b in v.items()))]

def ex_uni2(J, cad, k, cell):
    hB = J[f'B25G-{cad}']['h1']['delta']; hA = J[f'A10-{cad}']['h1']['delta']
    ok, mdd, w7, bm, bw, src = dd_check(J[f'B25G-{cad}'])
    h2 = J[f'B25G-{cad}']['h2']['delta']
    return [('6a pre-bull Sharpe not below base', hB >= 0 and hA >= 0, f"proxy H1 2020-05..2023-12 (window 2020-08-28..2023-12-31 not in json; gold has no weight before 2020-12-27): B+gold {f3(hB)}, A+gold {f3(hA)}"),
            ('6b maxDD not worse', mdd >= bm - 1e-12, f"B+gold FULL DD {pct(mdd)} vs {pct(bm)} ({src}); report 2024-26 (H2) d {f3(h2)}; ex-2025 line not in json (report item)")]

def ex_cost2(J, cad, k, cell):
    out = []; bad = []; allp = []
    for p in ('A', 'C'):
        for c, x in J[f'{p}-{cad}']['capital'].items():
            lo, hi = x['ci']; d = x['delta']; o = abs(d) <= 0.08 and lo <= 0 <= hi
            allp.append(f"{p} ${c[:-2]} {f3(d)} [{lo:+.3f},{hi:+.3f}]" + ('' if o else ' FAIL')); 
            if not o: bad.append(f'{p} ${c[:-2]}')
    out.append(('6a |d|<=0.08 & CI contains 0, every capital (FULL)', not bad, '; '.join(allp)))
    out.append(('6b same on 2022-23 and 2025-26 windows and vs band-0.10 rounded', False,
                'MISSING: capital blocks carry the FULL window only; no paired COST-2 vs D_band10 bootstrap at capital (point Sharpe gaps only, see detail)'))
    return out

def ex_ovl(J, cad, k, cell, episodes=False):
    r = J[f'B-{cad}']; ok, mdd, w7, bm, bw, src = dd_check(r)
    cv, cb = r['full']['var']['cagr'], r['full']['base']['cagr']
    out = [('6a maxDD not worse', mdd >= bm - 1e-12, f"B FULL DD {pct(mdd)} vs {pct(bm)} ({src}; raw {pct(r['full']['var']['mdd'])})"),
           ('6b CAGR not lower by >1pp', cv >= cb - 0.01 - 1e-12, f"B FULL CAGR {pct(cb,2)}->{pct(cv,2)} ({100*(cv-cb):+.2f}pp)")]
    if episodes:
        n = {'daily': 88, 'weekly': 72}[cad]
        out.append(('6c >=8 binding episodes outside 2021 on B', n >= 8, f"{n} (variants_overlay.py self-test I7; not a json field)"))
    return out

def ex_time1(J, cad, k, cell):
    out = []; parts = []; ok = True; pparts = []
    for p in ('A', 'B', 'C'):
        s = J[f'{p}-{cad}']['full']['var']['sharpe']; m = REF[p]['mean_full']; o = abs(s - m) <= 0.03; ok &= o
        parts.append(f"{p} {s:.3f} vs {m:.3f} ({s-m:+.3f})")
        sp = J[f'{p}-{cad}']['post']['var']['sharpe']; mp = REF[p]['mean_post']; pparts.append(f"{p} {sp:.3f} vs {mp:.3f} ({sp-mp:+.3f})")
    out.append(('6a within 0.03 of seven-weekday mean (FULL)', ok, '; '.join(parts) + ' | POST info: ' + '; '.join(pparts)))
    oparts = []; ook = True
    for p in ('A', 'C'):
        x = J[f'{p}-{cad}']['capital']['1000.0']; o = x['orders_yr'] <= 350; ook &= o; oparts.append(f"{p} {x['orders_yr']:.0f} (W {x['base_orders_yr']:.0f})")
    out.append(('6b orders/yr <= 350 at $1,000', ook, '; '.join(oparts)))
    tparts = []; tok = True
    for p in ('A', 'B', 'C'):
        r = J[f'{p}-{cad}']['full']; o = r['var']['turnover'] <= r['base']['turnover'] + 1e-12; tok &= o; tparts.append(f"{p} {r['var']['turnover']:.2f} vs {r['base']['turnover']:.2f}x")
    out.append(('6c turnover <= W', tok, '; '.join(tparts)))
    return out

def ex_time3(J, cad, k, cell):
    out = []
    if cad == 'weekly':
        s = J['A-weekly']['full']['var']['sharpe']
        out.append(('6a within 0.03 of six-hour mean on A', abs(s - SIXH_A_W) <= 0.03, f"A-weekly FULL {s:.3f} vs six-hour mean {SIXH_A_W:.2f} (plan section 1 value; no reference file) ({s-SIXH_A_W:+.3f})"))
    else:
        out.append(('6a within 0.03 of six-hour mean on A', None, 'n/a on the daily book (the six-hour reference is a W-book line; none exists for D)'))
    tparts = []; tok = True
    for p in ('A', 'B', 'C'):
        r = J[f'{p}-{cad}']['full']; o = r['var']['turnover'] <= r['base']['turnover'] + 1e-12; tok &= o; tparts.append(f"{p} {r['base']['turnover']:.2f}->{r['var']['turnover']:.2f}x")
    out.append(('6b no increase in orders/yr (turnover proxy)', tok, '; '.join(tparts)))
    c = J[f'C-{cad}']['full']['delta']
    out.append(('6c no loss on C', c >= 0, f"C FULL d {f3(c)}"))
    return out

def ex_time4(J, cad, k, cell):
    a = J['A-weekly']['full']['var']['sharpe']; c = J['C-weekly']['full']['var']['sharpe']
    out = [('6a A-weekly >= 1.17', a >= 1.17, f"A FULL {a:.3f} ($1,000 {J['A-weekly']['capital']['1000.0']['var']['sharpe']:.3f})"),
           ('6b C >= 0.80', c >= 0.80, f"C FULL {c:.3f} ($1,000 {J['C-weekly']['capital']['1000.0']['var']['sharpe']:.3f})")]
    oparts = []; ook = True
    for p in ('A', 'C'):
        x = J[f'{p}-weekly']['capital']['1000.0']; o = x['orders_yr'] <= 220; ook &= o; oparts.append(f"{p} {x['orders_yr']:.0f} (W {x['base_orders_yr']:.0f})")
    out.append(('6c orders/yr <= 220 at $1,000', ook, '; '.join(oparts)))
    gparts = []; gok = True
    for p in ('A', 'B', 'C'):
        r = J[f'{p}-weekly']['full']; g = r['var']['gross'] / r['base']['gross'] - 1; o = abs(g) <= 0.10; gok &= o; gparts.append(f"{p} {g:+.1%}")
    out.append(('6d realized gross within 10% of one-session book', gok, '; '.join(gparts)))
    return out

def ex_combo_a(J, cad, k, cell):
    T = load('TIME-1'); s = J['B-tranche']['post']['var']['sharpe']; st = T['B-tranche']['post']['var']['sharpe']
    out = [('6a B POST Sharpe >= TIME-1 - 0.03', s >= st - 0.03, f"{s:.3f} vs TIME-1 {st:.3f} ({s-st:+.3f})")]
    oparts = []; ook = True
    for p in ('A', 'C'):
        x = J[f'{p}-tranche']['capital']['1000.0']['orders_yr']; t = T[f'{p}-tranche']['capital']['1000.0']['orders_yr']; o = x <= 0.85 * t; ook &= o
        oparts.append(f"{p} {x:.0f} vs 0.85 x {t:.0f} = {0.85*t:.0f}")
    out.append(('6b orders/yr <= 0.85 x TIME-1 at $1,000', ook, '; '.join(oparts)))
    return out

def ex_combo_c(J, cad, k, cell):
    T = load('TIME-1'); s = J['B-tranche']['post']['var']['sharpe']; st = T['B-tranche']['post']['var']['sharpe']
    out = [('6a d vs TIME-1 > 0 on B POST', s - st > 0, f"B POST Sharpe {s:.3f} vs TIME-1 {st:.3f} ({s-st:+.3f}; point gap, no paired bootstrap vs TIME-1 in json)")]
    parts = []; ok = True
    for p in ('A', 'B', 'C'):
        for w in ('full', 'post'):
            if p == 'C' and w == 'post': continue
            d = J[f'{p}-tranche'][w]['var']['sharpe'] - T[f'{p}-tranche'][w]['var']['sharpe']; ok &= d >= 0; parts.append(f"{p} {w.upper()} {d:+.3f}")
    out.append(('6b no panel losing vs TIME-1', ok, '; '.join(parts)))
    return out

def ex_cap5000(J, cad, k, cell):
    has = any('5000.0' in J[f'{p}-{cad}'].get('capital', {}) for p in ('A', 'C'))
    return [('6 judged at $5,000 too', has if has else False, 'present' if has else 'MISSING: no $5,000 whole-contract line in SIG-2.json (plan: "Judge unrounded and at $5,000")')]

EXTRAS = {'mvdd_noworse': ex_mvdd_noworse, 'w7_noworse': ex_w7_noworse, 'sig7a': ex_sig7a, 'sig11': ex_sig11,
          'funding_not_higher': ex_funding_not_higher, 'sz6b': ex_sz6b, 'uni2': ex_uni2, 'cost2': ex_cost2,
          'ovl2': lambda J, c, k, cell: ex_ovl(J, c, k, cell, episodes=True), 'ovl3': lambda J, c, k, cell: ex_ovl(J, c, k, cell),
          'time1': ex_time1, 'time3': ex_time3, 'time4': ex_time4, 'combo_a': ex_combo_a, 'combo_c': ex_combo_c, 'cap5000': ex_cap5000}

# ------------------------------------------------------------------ class evaluations
def class1(cell, J, cad):
    k = cell['keys']; B = J[f"{k['B']}-{cad}"]; A = J[f"{k['A']}-{cad}"]; C = J[f"{k['C']}-{cad}"]
    res = []
    d, sd, p = B['post']['delta'], B['post']['sd_delta'], B['post']['p_le0']
    h = max(0.05, M_DEC * sd)
    res.append(('1', d >= h and p <= 0.10, f"B POST d {f3(d)} vs hurdle {h:.3f} (2.37 sd; 2.49 sd = {max(0.05, M_FORM*sd):.3f}; 1.98 sd = {max(0.05, M_24*sd):.3f}), P {p:.3f}"))
    v = [A['post']['delta'], A['full']['delta'], C['full']['delta']]
    a6ok, a6t = a6_check(J, {pp: f"{k[pp]}-{cad}" for pp in ('A', 'B', 'C')})
    res.append(('2', all(x >= -0.03 for x in v) and a6ok, f"A POST {f3(v[0])}, A FULL {f3(v[1])}, C FULL {f3(v[2])}; A6 {a6t}"))
    h1, h2 = B['h1']['delta'], B['h2']['delta']
    res.append(('3', h1 > 0 and h2 > 0, f"B H1 {f3(h1)}, H2 {f3(h2)}"))
    nparts = []; nok = True
    for lab in cell['nb']:
        nj = load(f"{cell['id']}__{lab}") if not lab.startswith('MISSING') else None
        if nj is None:
            nok = False; nparts.append(f"{lab}: json MISSING"); continue
        nd = nj[f"{k['B']}-{cad}"]['post']['delta']; o = nd >= 0 and nd >= d - 0.10; nok &= o
        nparts.append(f"{lab} {f3(nd)}" + ('' if o else ' FAIL'))
    if not cell['nb']: nparts.append('none by design')
    res.append(('4', nok, f"neighbors B POST (>=0 and >= {d-0.10:+.3f}): " + ', '.join(nparts)))
    ok5, mdd, w7, bm, bw, src = dd_check(B)
    res.append(('5', ok5, f"B FULL DD {pct(mdd)} vs {pct(bm)}, worst7 {pct(w7)} vs {pct(bw)} ({src})"))
    for e in cell.get('extras', []):
        res.extend(EXTRAS[e](J, cad, k, cell))
    return res

def class2(cell, J, cad):
    k = cell['keys']; B = J[f"{k['B']}-{cad}"]; A = J[f"{k['A']}-{cad}"]; C = J[f"{k['C']}-{cad}"]
    res = []
    d, lo = B['post']['delta'], B['post']['ci'][0]
    res.append(('1', d >= -0.03 and lo >= -0.10, f"B POST d {f3(d)} (>= -0.03), CI lo {lo:+.3f} (>= -0.10)"))
    v = [A['post']['delta'], A['full']['delta'], C['full']['delta']]; h1, h2 = B['h1']['delta'], B['h2']['delta']
    a6ok, a6t = a6_check(J, {pp: f"{k[pp]}-{cad}" for pp in ('A', 'B', 'C')})
    res.append(('2', all(x >= -0.03 for x in v) and h1 >= -0.05 and h2 >= -0.05 and a6ok,
                f"A POST {f3(v[0])}, A FULL {f3(v[1])}, C FULL {f3(v[2])}; B H1 {f3(h1)}, H2 {f3(h2)} (>= -0.05); A6 {a6t}"))
    ok3, t3 = OPS[cell['op']](J, cad, k)
    res.append(('3', ok3, t3))
    nparts = []; nok = True
    for lab in cell['nb']:
        nj = load(f"{cell['id']}__{lab}")
        if nj is None:
            nok = False; nparts.append(f"{lab}: json MISSING"); continue
        nd = nj[f"{k['B']}-{cad}"]['post']['delta']; o3, _ = OPS[cell['op']](nj, cad, k); o = nd >= -0.08 and o3; nok &= o
        nparts.append(f"{lab} d {f3(nd)}, op {'ok' if o3 else 'NOT met'}" + ('' if o else ' FAIL'))
    res.append(('4', nok, 'neighbors (d >= -0.08 and op gain holds): ' + ', '.join(nparts)))
    ok5, mdd, w7, bm, bw, src = dd_check(B)
    res.append(('5', ok5, f"B FULL DD {pct(mdd)} vs {pct(bm)}, worst7 {pct(w7)} vs {pct(bw)} ({src})"))
    for e in cell.get('extras', []):
        res.extend(EXTRAS[e](J, cad, k, cell))
    return res

# ------------------------------------------------------------------ special cells
def sz13(cell, J, cad):
    """SZ-13: B not applicable (plan); primary judgement C and A at $1,000: Sharpe within 0.05 of the unrounded line, orders/yr down
    vs the rounded baseline, realized vol within 10 % of the unrounded line; class II items translated to A/C at $1,000."""
    res = []
    parts = []; ok = True; one = True
    for p in ('A', 'C'):
        r = J[f'{p}-{cad}']; x = r['capital']['1000.0']; s, su = x['var']['sharpe'], r['full']['var']['sharpe']
        o = abs(s - su) <= 0.05; ok &= o; one &= (s - su) >= -0.05; parts.append(f"{p} $1,000 {s:.3f} vs unrounded {su:.3f} ({s-su:+.3f})")
    res.append(('1*', ok, 'Sharpe within 0.05 of the unrounded line (B n/a): ' + '; '.join(parts) + ('' if ok == one else f" [one-sided reading: {'pass' if one else 'fail'}]")))
    parts = []; ok = True
    for p in ('A', 'C'):
        x = J[f'{p}-{cad}']['capital']['1000.0']; o = x['delta'] >= -0.03; ok &= o; parts.append(f"{p} $1,000 vs rounded base d {f3(x['delta'])}")
    res.append(('2*', ok, 'd >= -0.03 at $1,000 (FULL; POST not in capital blocks): ' + '; '.join(parts)))
    parts = []; ok = True
    for p in ('A', 'C'):
        r = J[f'{p}-{cad}']; x = r['capital']['1000.0']; do = x['orders_yr'] / x['base_orders_yr'] - 1; dv = x['var']['vol'] / r['full']['var']['vol'] - 1
        o = do < 0 and abs(dv) <= 0.10; ok &= o; parts.append(f"{p} orders {x['base_orders_yr']:.1f}->{x['orders_yr']:.1f} ({do:+.1%}), vol vs unrounded {dv:+.1%}" + ('' if o else ' FAIL'))
    res.append(('3', ok, 'orders/yr down vs rounded base AND vol within 10% of unrounded: ' + '; '.join(parts)))
    nparts = []; nok = True
    for lab in cell['nb']:
        nj = load(f"SZ-13__{lab}")
        if nj is None: nok = False; nparts.append(f'{lab}: MISSING'); continue
        sub = []
        for p in ('A', 'C'):
            r = nj[f'{p}-{cad}']; x = r['capital']['1000.0']; o = x['delta'] >= -0.08 and x['orders_yr'] < x['base_orders_yr'] and abs(x['var']['vol'] / r['full']['var']['vol'] - 1) <= 0.10
            nok &= o; sub.append(f"{p} d {f3(x['delta'])} orders {x['base_orders_yr']:.1f}->{x['orders_yr']:.1f}" + ('' if o else ' FAIL'))
        nparts.append(f"{lab}: " + ', '.join(sub))
    res.append(('4', nok, 'neighbors at $1,000 (d >= -0.08, op gain holds): ' + '; '.join(nparts)))
    parts = []; ok = True
    for p in ('A', 'C'):
        x = J[f'{p}-{cad}']['capital']['1000.0']; o = x['var']['mdd'] >= x['base']['mdd'] - 0.02 and x['var']['worst7'] >= x['base']['worst7'] - 0.01; ok &= o
        parts.append(f"{p} DD {pct(x['var']['mdd'])} vs {pct(x['base']['mdd'])}, w7 {pct(x['var']['worst7'])} vs {pct(x['base']['worst7'])}")
    res.append(('5', ok, 'DD/worst7 at $1,000 vs rounded base (no matched-vol re-run exists for capital lines): ' + '; '.join(parts)))
    return res

def sz17(cell, J, cad):
    """SZ-17 (A7): class II with its own list; B falls back to A's nine, cell reported A/C only."""
    res = []
    v = {'A POST': J[f'A-{cad}']['post']['delta'], 'A FULL': J[f'A-{cad}']['full']['delta'], 'C FULL': J[f'C-{cad}']['full']['delta']}
    res.append(('1/2*', all(x >= -0.03 for x in v.values()), 'Sharpe within -0.03 (B n/a by A7): ' + ', '.join(f'{a} {f3(b)}' for a, b in v.items())))
    ok3, t3 = op_capital(J, cad, cell['keys'], ['1000.0'], 0.15, label='orders/yr down >=15% on rounded lines')
    res.append(('3', ok3, t3))
    nparts = []; nok = True
    for lab in cell['nb']:
        nj = load(f"SZ-17__{lab}")
        if nj is None: nok = False; nparts.append(f'{lab}: MISSING'); continue
        nd = nj[f'A-{cad}']['post']['delta']; o3, _ = op_capital(nj, cad, cell['keys'], ['1000.0'], 0.15); o = nd >= -0.08 and o3; nok &= o
        nparts.append(f"{lab} A POST d {f3(nd)}, op {'ok' if o3 else 'NOT met'}")
    res.append(('4', nok, 'neighbors (A POST as the B substitute): ' + ', '.join(nparts)))
    parts = []; ok = True
    for p in ('A', 'C'):
        o5, mdd, w7, bm, bw, src = dd_check(J[f'{p}-{cad}'], 0.0, 0.0); ok &= o5; parts.append(f"{p} DD {pct(mdd)} vs {pct(bm)}, w7 {pct(w7)} vs {pct(bw)} ({src})")
    res.append(('5', ok, 'matched-vol DD and worst7 no worse (A7 tightens 2pp/1pp to 0): ' + '; '.join(parts)))
    return res

def uni1(cell, J, cad):
    r = J[f'Bw-{cad}']; res = []
    s = r['full']['var']['sharpe']; thr = 0.86 if cad == 'daily' else 0.82
    res.append(('R1', s >= thr, f"FULL Sharpe {s:.3f} >= {thr}"))
    d = r['post']['delta']; res.append(('R2', d >= 0, f"d vs static-24 on B POST {f3(d)} (CI [{r['post']['ci'][0]:+.2f},{r['post']['ci'][1]:+.2f}], P {r['post']['p_le0']:.2f})"))
    ok, mdd, w7, bm, bw, src = dd_check(r)
    res.append(('R3', mdd >= bm - 1e-12, f"maxDD {pct(mdd)} vs static-24 {pct(bm)} ({src}; raw {pct(r['full']['var']['mdd'])}; plan's quoted av_runs line {'-24.1%' if cad=='daily' else '-16.8%'})"))
    h1, h2 = r['h1']['delta'], r['h2']['delta']
    res.append(('R4', h1 >= 0 and h2 >= 0, f"halves vs static-24: H1 {f3(h1)}, H2 {f3(h2)}"))
    return res

# ------------------------------------------------------------------ cell table (plan section 6 order, then A7/A8)
K0 = {'A': 'A', 'B': 'B', 'C': 'C'}
BOTH = ['daily', 'weekly']
CELLS = [
    dict(id='SIG-2', cls='I/II', target='both', cads=BOTH, nb=['d0.5', 'd1.5', 'SIG1A_form'], op='trades_funding25', extras1=['cap5000'], extras2=['cap5000'], a3='yes (d)'),
    dict(id='SIG-1B', cls='I/II', target='both', cads=BOTH, nb=['t0.75', 't1.25'], op='trades_funding25'),
    dict(id='SIG-3a', cls='I/II', target='both', cads=BOTH, nb=['speed_x0.75', 'speed_x1.25'], op='orders15'),
    dict(id='SIG-3b', cls='I/II', target='both', cads=BOTH, nb=['denom15', 'denom30'], op='trades_funding25', extras1=['mvdd_noworse'], extras2=['mvdd_noworse']),
    dict(id='SIG-4', cls='I/II', target='both', cads=BOTH, nb=['7_lookbacks', 'paper_sizing', 'same_day_norm'], op='dd3_trades'),
    dict(id='SIG-7A', cls='I', target='both', cads=BOTH, nb=['L200', 'L300'], extras1=['sig7a']),
    dict(id='SIG-10', cls='I', target='both', cads=BOTH, nb=['map_0_25_50_100', 'map_0_50_75_100']),
    dict(id='SIG-9', cls='I', target='both', cads=BOTH, nb=['mem15', 'mem30'], missing='no phase2/SIG-9.json: conditional cell not run (diagnostics.md D-1 gate "SIG-9 runs = False")'),
    dict(id='SIG-11', cls='I', target='both', cads=BOTH, nb=['looks_20_80_160', 'smooth_L8'], extras1=['sig11']),
    dict(id='SZ-1', cls='II', target='both', cads=BOTH, nb=['COM45', 'COM90'], op='orders15', extras2=['w7_noworse']),
    dict(id='SZ-3', cls='II', target='both', cads=BOTH, nb=['wfast06', 'wfast08'], op='sz3', extras2=['w7_noworse']),
    dict(id='SZ-6b', cls='I', target='both', cads=BOTH, nb=['ref060', 'ref080'], extras1=['sz6b']),
    dict(id='SZ-13', cls='II ($1,000)', target='both, whole contracts', cads=BOTH, nb=['thr2_exit16', 'exit09'], special=sz13),
    dict(id='UNI-1', cls='R', target='both', cads=BOTH, nb=['age121', 'quarterly', 'N12'], special=uni1),
    dict(id='UNI-2', cls='I', target='both', cads=BOTH, keys={'A': 'A10', 'B': 'B25G', 'C': 'C'}, nb=['goldcap025', 'MISSING_realistic_cost_1.18+2bps'], extras1=['uni2']),
    dict(id='COST-2', cls='II', target='D, whole contracts', cads=['daily'], nb=['m1', 'b025', 'COST1_F010', 'COST1_F020'], op='cost2', extras2=['cost2'], a3='yes (m)'),
    dict(id='OVL-2', cls='I', target='both', cads=BOTH, nb=['30d40', '14d40'], extras1=['ovl2'], a3='yes (window/threshold)'),
    dict(id='OVL-3', cls='I', target='both', cads=BOTH, nb=[], extras1=['ovl3']),
    dict(id='TIME-1', cls='I vs W', target='T', cads=['tranche'], nb=['K3', 'K5', 'TIME5_partial', 'TIME2_signal_smooth'], extras1=['time1'], a3='yes (K)'),
    dict(id='TIME-3', cls='I', target='both', cads=BOTH, nb=['all24', 'h0_8_16'], extras1=['time3']),
    dict(id='TIME-4', cls='I vs W', target='W, whole contracts', cads=['weekly'], nb=['mon_fri', 'full_gap'], extras1=['time4']),
    dict(id='COMBO-A', cls='I vs W', target='T, whole contracts', cads=['tranche'], nb=['no_buffer', 'cc60'], extras1=['combo_a']),
    dict(id='COMBO-B', cls='I/II', target='D, whole contracts', cads=['daily'], nb=['no_buffer', 'cc60'], op='combob'),
    dict(id='COMBO-C', cls='I vs W', target='T', cads=['tranche'], nb=['h0_8_16_K7', 'six_K5'], extras1=['combo_c']),
    dict(id='SZ-17', cls='II (A7)', target='both (A/C only)', cads=BOTH, nb=['COM30', 'COM90'], special=sz17),
    dict(id='SIG-13', cls='I (A8)', target='both (interpreted)', cads=BOTH, nb=['sleeve120_only', 'funding_x2'], extras1=['funding_not_higher']),
]

def evaluate(cell):
    J = load(cell['id']); cell.setdefault('keys', K0)
    if J is None:
        return dict(missing=True)
    out = {}
    classes = []
    if 'special' in cell:
        classes = [('S', cell['special'])]
    else:
        if cell['cls'].startswith('I') and cell['cls'] != 'II':
            classes.append(('I', lambda c, J, cad: class1({**c, 'extras': c.get('extras1', [])}, J, cad)))
        if 'II' in cell['cls']:
            classes.append(('II', lambda c, J, cad: class2({**c, 'extras': c.get('extras2', [])}, J, cad)))
    for name, fn in classes:
        per = {cad: fn(cell, J, cad) for cad in cell['cads']}
        fails = []
        for cad, rs in per.items():
            for cid, ok, txt in rs:
                if ok is False: fails.append((cid, cad, txt))
        ids = []
        for cid, cad, _ in fails:
            if cid not in ids: ids.append(cid)
        out[name] = dict(per=per, fails=fails, fail_ids=ids, passed=not fails)
    return out

def cond_order(cid):
    import re
    m = re.match(r'(\d+)', cid.replace('R', '').replace('*', '').split('/')[0]) if cid[0] != 'R' else re.match(r'R(\d)', cid)
    return int(m.group(1)) if m else 99

RESULTS = []
for cell in CELLS:
    r = evaluate(cell); RESULTS.append((cell, r))

# ------------------------------------------------------------------ console log
for cell, r in RESULTS:
    if r.get('missing'):
        print(cell['id'], 'MISSING'); continue
    for name, x in r.items():
        print(f"{cell['id']:8s} class {name:3s} {'PASS' if x['passed'] else 'FAIL'} fails={x['fail_ids']}")
        for cad, rs in x['per'].items():
            for cid, ok, txt in rs:
                print(f"     {cad:7s} [{cid}] {'ok ' if ok else ('n/a' if ok is None else 'FAIL')} {txt}")
import pickle
pickle.dump([(c['id'], r) for c, r in RESULTS], open('/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/judge/results.pkl', 'wb'))

# ================================================================== markdown
import re
def okey(cid):
    m = re.match(r'R?(\d+)([a-z]?)', cid)
    return (int(m.group(1)), m.group(2) or '') if m else (99, '')

def cads_of(cell): return cell['cads']
def ab(cad): return {'daily': 'd', 'weekly': 'w', 'tranche': 't'}[cad]
def per_cad(cell, fn):
    J = load(cell['id']); out = []
    for cad in cell['cads']:
        try: out.append(f"{ab(cad)} {fn(J, cad)}")
        except KeyError: out.append(f"{ab(cad)} n/a")
    return '<br>'.join(out)

def cond_status(r, cls, cid_prefix):
    x = r.get(cls)
    if not x: return 'n/a'
    st = []
    for cad, rs in x['per'].items():
        oks = [ok for cid, ok, _ in rs if cid.split(' ')[0].startswith(cid_prefix)]
        if not oks: continue
        st.append(f"{ab(cad)} " + ('ok' if all(o is not False for o in oks) else 'NO'))
    return ' '.join(st) if st else 'n/a'

def extras_status(r, cls):
    x = r.get(cls)
    if not x: return 'n/a'
    st = []
    for cad, rs in x['per'].items():
        ex = [(cid, ok) for cid, ok, _ in rs if cid.startswith('6')]
        if not ex: continue
        bad = [cid.split(' ')[0] for cid, ok in ex if ok is False]
        st.append(f"{ab(cad)} " + ('ok' if not bad else 'NO (' + ','.join(bad) + ')'))
    return '<br>'.join(st) if st else 'none'

def first_fail(x):
    if not x['fails']: return None
    fs = sorted(x['fails'], key=lambda f: (okey(f[0]), ['daily', 'weekly', 'tranche'].index(f[1])))
    cid = fs[0][0]; cads = [ab(f[1]) for f in x['fails'] if f[0] == cid]
    return cid, cads, fs[0][2]

def short(txt, n=150):
    return txt if len(txt) <= n else txt[:n - 1] + '…'

def verdict(cell, r):
    if r.get('missing'): return 'FAIL', f"FAIL: {cell['missing']}"
    if any(x['passed'] for x in r.values()):
        p = [k for k, x in r.items() if x['passed']]
        return 'PASS', 'PASS' + (' (research-number class)' if cell['cls'] == 'R' else f" (class {'/'.join(p)})")
    parts = []
    for k, x in r.items():
        cid, cads, txt = first_fail(x)
        lab = {'I': 'I', 'II': 'II', 'S': cell['cls'].split(' ')[0]}[k]
        parts.append(f"class {lab} cond {cid.split(' ')[0]} ({'/'.join(cads)}): {short(txt, 120)}")
    return 'FAIL', 'FAIL: ' + ' ‖ '.join(parts)

def opmetric(cell, r):
    J = load(cell['id'])
    for k in ('II', 'S'):
        if k in r:
            for cad, rs in r[k]['per'].items():
                pass
    if 'II' in r:
        return '<br>'.join(f"{ab(cad)} " + short([t for c, o, t in rs if c == '3'][0], 260) for cad, rs in r['II']['per'].items())
    if 'S' in r and cell['id'] in ('SZ-13', 'SZ-17'):
        return '<br>'.join(f"{ab(cad)} " + short([t for c, o, t in rs if c == '3'][0], 260) for cad, rs in r['S']['per'].items())
    if cell['id'] in ('TIME-1', 'TIME-4', 'COMBO-A'):
        cad = cell['cads'][0]
        return ' ; '.join(f"A ${'1,000'} orders {J[f'A-{cad}']['capital']['1000.0']['base_orders_yr']:.0f}->{J[f'A-{cad}']['capital']['1000.0']['orders_yr']:.0f}, C {J[f'C-{cad}']['capital']['1000.0']['base_orders_yr']:.0f}->{J[f'C-{cad}']['capital']['1000.0']['orders_yr']:.0f}" for _ in [0]) + f"; B turn {J['B-'+cad]['full']['base']['turnover']:.2f}->{J['B-'+cad]['full']['var']['turnover']:.2f}x"
    if cell['id'] == 'UNI-1':
        return '<br>'.join(f"{ab(cad)} Bw turn {J[f'Bw-{cad}']['full']['base']['turnover']:.2f}->{J[f'Bw-{cad}']['full']['var']['turnover']:.2f}x (info)" for cad in cell['cads'])
    k = cell['keys']['B']
    return 'class I (no II metric); info ' + '<br>'.join(f"{ab(cad)} B turn {J[f'{k}-{cad}']['full']['base']['turnover']:.2f}->{J[f'{k}-{cad}']['full']['var']['turnover']:.2f}x, fund {pct(J[f'{k}-{cad}']['full']['base']['funding_yr'],2)}->{pct(J[f'{k}-{cad}']['full']['var']['funding_yr'],2)}" for cad in cell['cads'])

def a6col(cell, r):
    J = load(cell['id']); k = cell['keys']
    out = []
    for cad in cell['cads']:
        if cell['id'] == 'UNI-1': out.append(f"{ab(cad)} n/a (Bw: no stress line run)"); continue
        keys = {p: f"{k[p]}-{cad}" for p in ('A', 'B', 'C') if f"{k[p]}-{cad}" in J}
        if 'B' not in keys: keys['B'] = None
        ok, t = a6_check(J, {p: v for p, v in keys.items() if v} | {'A': keys['A']})
        out.append(f"{ab(cad)} {'ok' if ok else 'NO'}: {short(t, 110)}")
    return '<br>'.join(out)

def taxcol(cell):
    J = load(cell['id']); k = cell['keys']['B'] if cell['id'] not in ('SZ-13', 'SZ-17', 'UNI-1') else ('Bw' if cell['id'] == 'UNI-1' else 'A')
    out = []
    for cad in cell['cads']:
        r = J[f'{k}-{cad}']['full']; out.append(f"{ab(cad)} {pct(r['tax']['segment']['cagr'])}/{pct(r['base_tax']['segment']['cagr'])}" + (' (A)' if k == 'A' else ''))
    return '<br>'.join(out)

def bcol(cell, w, fn):
    J = load(cell['id'])
    if cell['id'] in ('SZ-13', 'SZ-17'): return 'n/a (no B by plan)'
    k = 'Bw' if cell['id'] == 'UNI-1' else cell['keys']['B']
    return '<br>'.join(f"{ab(cad)} {fn(J[f'{k}-{cad}'][w])}" for cad in cell['cads'])

def hurdle_col(cell):
    if cell['id'] in ('SZ-13', 'SZ-17', 'UNI-1') or 'I' not in load_res(cell): return 'n/a (class)' if cell['id'] not in ('SZ-13', 'SZ-17') else 'n/a'
    J = load(cell['id']); k = cell['keys']['B']
    return '<br>'.join(f"{ab(cad)} {max(0.05, M_DEC*J[f'{k}-{cad}']['post']['sd_delta']):.3f} ({max(0.05, M_24*J[f'{k}-{cad}']['post']['sd_delta']):.3f})" for cad in cell['cads'])

RES = {c['id']: r for c, r in RESULTS}
def load_res(cell): return RES[cell['id']]

def nbcol(cell, r):
    for k in ('I', 'II', 'S'):
        if k in r:
            if cell['id'] == 'UNI-1': return 'not in the research-number rule (info in detail)'
            return cond_status(r, k, '4') + ('' if k != 'I' or 'II' not in r else ' / II: ' + cond_status(r, 'II', '4'))
    return 'n/a'

def halves(cell):
    if cell['id'] in ('SZ-13', 'SZ-17'): return 'n/a (no B)'
    J = load(cell['id']); k = 'Bw' if cell['id'] == 'UNI-1' else cell['keys']['B']
    return '<br>'.join(f"{ab(cad)} {f3(J[f'{k}-{cad}']['h1']['delta'])} / {f3(J[f'{k}-{cad}']['h2']['delta'])}" for cad in cell['cads'])

def ddcol(cell, r):
    if cell['id'] == 'SZ-13': return cond_status(r, 'S', '5') + ' ($1,000 vs rounded base; detail)'
    k = 'I' if 'I' in r else ('II' if 'II' in r else 'S')
    if cell['id'] == 'UNI-1': return cond_status(r, 'S', 'R3') + ' (R3, mv)'
    J = load(cell['id']); kk = cell['keys']['B'] if cell['id'] not in ('SZ-13', 'SZ-17') else 'A'
    out = []
    for cad in cell['cads']:
        ok, mdd, w7, bm, bw, src = dd_check(J[f'{kk}-{cad}'])
        out.append(f"{ab(cad)} {pct(mdd)}/{pct(bm)}, {pct(w7)}/{pct(bw)}" + (' mv' if 'mv' in src else ''))
    return cond_status(r, k, '5') + '<br>' + '<br>'.join(out) + (' (A)' if kk == 'A' else '')

L = []
L.append('# Phase 2 verdicts (mechanical application of phase1_plan.md section 5)')
L.append('')
L.append('Judge run 2026-10-21. Plan `research2/phase1_plan.md` sha256 9ad0a829f7bc269f5ce99e7c4e57a09ef89ffe1699776b479abe9b291418c095 (matches `phase2/plan_sha256.txt`). '
         'Inputs: `phase2/<id>.json` and `phase2/<id>__*.json` (COST-2 and COMBO-A are the post-buffer-fix reruns; struck-through and `_selftest` summary lines ignored), '
         '`phase2/reference.json` (seven-weekday lines), `phase2/diagnostics.md`, the family modules\' docstrings for numbers the harness does not write. No result file was changed; this file is the only output.')
L.append('')
L.append('## How each condition was read (fixed before reading the verdict column; every choice is the reading closest to the plan text)')
L.append('')
L.append(f'- **Class I cond 1 hurdle** = max(0.05, 2.37 x sd_Delta) (A3 text and the task contract). Also shown: 1.98 x sd_Delta (section 4, N = 24) and 2.49 x sd_Delta, which is what the plan\'s own formula gives at N_eff = 90 ({M_FORM:.3f}; the harness summary\'s "hurdle" uses it). The A3 text\'s 2.37 corresponds to N of about 66, not 90; no verdict differs between 2.37 and 2.49 (nothing clears 2.37).')
L.append('- **sd_Delta** is the json field, i.e. (CI hi - CI lo)/3.92 of `sim.block_bootstrap_diff` (1000 draws, 20-day blocks, seed 7), not `statistics.stdev(diffs)` as section 4 writes; P(Delta <= 0) and the 95 % CI are the bootstrap\'s.')
L.append('- **Matched vol (cond 5 and every "maxDD/worst 7-day no worse")**: the json `matched_vol` re-run on B FULL when present (vol differs > 5 %); when absent the raw FULL line is used, because section 3 asks for the re-run only above 5 %. Tolerances 2 pp / 1 pp (cond 5); 0 for the cells whose extra says "no worse".')
L.append('- **"both"**: a condition must hold on the daily AND the weekly book. Counting for near misses is by distinct condition (a condition failing on both cadences counts once); each extra is its own condition.')
L.append('- **Class II metrics**: whole-contract `capital` blocks only where the plan says rounded / contracts (COST-2, COMBO-B "vs D round-nearest", SZ-13, SZ-17, the TIME-1 / TIME-4 / COMBO-A order caps at $1,000); everywhere else (SIG-2, SIG-1B, SIG-3a, SIG-3b, SIG-4, SZ-1, SZ-3, TIME-3) orders/yr and trades/yr use FULL unrounded **turnover** as the proxy and funding/yr the FULL `funding_yr`, as the task instructs. "The operational gain holds in every neighbor" = the neighbor meets the same stated threshold on all panels.')
L.append('- **A6 Delta-funding stress**: triggered when average gross (FULL var/base) rises > 10 % on any of A, B, C; then cond 2 must also hold on the stress line, whose only condition-2 window is A POST (stress Sharpe var - base >= -0.03). B POST stress Delta is shown for information.')
L.append('- **Reference lines** (plan section 1) for TIME-1: seven-weekday FULL means A 1.230 / B 0.895 / C 0.980 (reference.json); "within 0.03" read two-sided on FULL (POST printed). TIME-3: six-hour mean A 1.21 (plan section 1 text; no file on disk), applied to A-weekly only (there is no daily six-hour reference).')
L.append('- **No-B cells**: SZ-13 (plan: "B not applicable"; primary judgement C and A at $1,000) and SZ-17 (A7: "B falls back to A\'s nine, reported as A/C only") are judged on the conditions their own text lists, translated to A/C. UNI-1 is the research-number class and is judged only on its 6.3 pass line (Bw vs static-24).')
L.append('- **Missing evidence is a FAIL**: SIG-9 (no json), UNI-2 neighbor (b) "realistic cost line 1.18 + 2 bps on gold" (no json; `UNI-2__goldcost_low` is registered in variants_p1.py but never run, and its cost adjustment is a no-op), SIG-2\'s required $5,000 line, COST-2\'s 2022-23 / 2025-26 windows and the paired comparison vs band-0.10 rounded at each capital.')
L.append('')

hdr = ['id', 'class', 'target', 'B POST Δ', '95 % CI', 'P(Δ≤0)', 'sd_Δ', 'hurdle 2.37 (1.98)', 'A POST / FULL Δ', 'C FULL Δ', 'B H1 / H2 Δ', 'neighbors ok?', 'matched-vol DD / worst7 ok? (var/base)', 'operational metric before → after', 'extras ok?', 'Delta-funding stress (A6) ok?', 'after-tax seg CAGR var/base (B FULL)', 'A3 param seen', 'VERDICT (first failing condition)']
L.append('## Verdict table')
L.append('')
L.append('| ' + ' | '.join(hdr) + ' |')
L.append('|' + '---|' * len(hdr))
PASSES, NEAR, TWO = [], [], []
for cell, r in RESULTS:
    if r.get('missing'):
        row = [cell['id'], cell['cls'], cell['target']] + ['no json'] * 15 + [f"**FAIL**: {cell['missing']}"]
        L.append('| ' + ' | '.join(row) + ' |'); continue
    J = load(cell['id'])
    v, vt = verdict(cell, r)
    if v == 'PASS': PASSES.append((cell, r))
    else:
        for k, x in r.items():
            ids = sorted(set(f[0] for f in x['fails']), key=okey)
            if len(ids) == 1: NEAR.append((cell, k, x))
            elif len(ids) == 2: TWO.append((cell, k, ids, x))
    if cell['id'] == 'UNI-1':
        apf = 'n/a (Bw only)'; cc = 'n/a'
    elif cell['id'] in ('SZ-13',):
        apf = '<br>'.join(f"{ab(cad)} $1,000 vs rounded: A {f3(J[f'A-{cad}']['capital']['1000.0']['delta'])}" for cad in cell['cads']); cc = '<br>'.join(f"{ab(cad)} $1,000 {f3(J[f'C-{cad}']['capital']['1000.0']['delta'])}" for cad in cell['cads'])
    else:
        ka = cell['keys']['A']
        apf = '<br>'.join(f"{ab(cad)} {f3(J[f'{ka}-{cad}']['post']['delta'])} / {f3(J[f'{ka}-{cad}']['full']['delta'])}" for cad in cell['cads'])
        cc = '<br>'.join(f"{ab(cad)} {f3(J[f'C-{cad}']['full']['delta'])}" for cad in cell['cads'])
    row = [cell['id'], cell['cls'], cell['target'],
           bcol(cell, 'post', lambda x: f3(x['delta'])), bcol(cell, 'post', lambda x: f"[{x['ci'][0]:+.3f}, {x['ci'][1]:+.3f}]"),
           bcol(cell, 'post', lambda x: f"{x['p_le0']:.3f}"), bcol(cell, 'post', lambda x: f"{x['sd_delta']:.4f}"),
           hurdle_col(cell), apf, cc,
           halves(cell),
           nbcol(cell, r), ddcol(cell, r), opmetric(cell, r),
           (extras_status(r, 'I') if 'I' in r else extras_status(r, 'II')) if 'S' not in r else 'see detail',
           a6col(cell, r), taxcol(cell), cell.get('a3', 'no'), f"**{vt.split(':')[0]}**" + (':' + ':'.join(vt.split(':')[1:]) if ':' in vt else '')]
    L.append('| ' + ' | '.join(str(x).replace('|', '\\|') for x in row) + ' |')
L.append('')
L.append('Column notes: d / w / t = daily / weekly / tranche (T) book. B = the 24 ex-ante panel (UNI-2: 25 ex-ante + gold vs 25; UNI-1: Bw rotating vs static-24 through D-0). hurdle column shows 2.37 sd (1.98 sd), floor 0.05. "after-tax seg" = A1 (a) per-coin realized-segment VDA 30 % CAGR on B FULL (A FULL for SZ-13/SZ-17, Bw for UNI-1). Table cells are abbreviated; every number used is in the detail section.')
L.append('')

# ------------------------------------------------------------------ passes / near misses
L.append('## Passes')
L.append('')
if PASSES:
    for cell, r in PASSES:
        J = load(cell['id'])
        L.append(f"- **{cell['id']}** ({cell['cls']}, {cell['target']}): " + '; '.join(f"{cad}: FULL {J[f'Bw-{cad}']['full']['var']['sharpe']:.3f} vs static-24 {J[f'Bw-{cad}']['full']['base']['sharpe']:.3f}, POST Δ {f3(J[f'Bw-{cad}']['post']['delta'])} (CI [{J[f'Bw-{cad}']['post']['ci'][0]:+.2f}, {J[f'Bw-{cad}']['post']['ci'][1]:+.2f}], P {J[f'Bw-{cad}']['post']['p_le0']:.2f}), mv maxDD {pct(J[f'Bw-{cad}']['matched_vol']['mdd'])} vs {pct(J[f'Bw-{cad}']['full']['base']['mdd'])}, H1 {f3(J[f'Bw-{cad}']['h1']['delta'])} H2 {f3(J[f'Bw-{cad}']['h2']['delta'])}" for cad in cell['cads'])
                 + '. **Reading-dependent:** the maxDD clause passes only at matched vol (section 3 decision line; vol is 10 % above static-24 on both books); on raw maxDD it fails on both books (-26.5 % vs -24.7 %, -18.2 % vs -17.0 %) and UNI-1 would be a one-condition near miss. Every neighbor fails the matched-vol maxDD clause on at least one book (age121 and N12 also a half). Per section 5 this is a research number for the annual review (kill criterion #6), a live rule only at >= $5,000; it is not a Sharpe-improvement claim (CI contains 0, P 0.12). Caveats in the detail section (raw maxDD worse, neighbors, missing report items, D-0 gate figures).')
else:
    L.append('- none')
L.append('- No class I or class II cell passes. Nothing goes to Phase 3 as a return or execution proposal from this grid; per section 5 every failing cell is "do nothing" and goes to the considered-and-rejected table with its numbers.')
L.append('')
L.append('## Near misses (failed exactly one condition)')
L.append('')
if NEAR:
    for cell, k, x in NEAR:
        cid, cads, txt = first_fail(x)
        L.append(f"- **{cell['id']}** class {k}: cond {cid} ({'/'.join(cads)}): {txt}")
else:
    L.append('- none. No cell fails exactly one condition at the 2.37 hurdle.')
L.append('')
L.append('Closest (exactly two failing conditions; listed for the memo, not near misses):')
L.append('')
for cell, k, ids, x in TWO:
    seen = {}
    for cid, cad, txt in sorted(x['fails'], key=lambda f: okey(f[0])):
        seen.setdefault(cid, (cad, txt))
    L.append(f"- **{cell['id']}** class {k}: " + ' AND '.join(f"cond {cid} ({ab(c)}): {t}" for cid, (c, t) in seen.items()))
L.append('')

# ------------------------------------------------------------------ detail
L.append('## Detail: every condition, every cadence')
L.append('')
for cell, r in RESULTS:
    L.append(f"### {cell['id']} | class {cell['cls']} | target {cell['target']}")
    L.append('')
    if r.get('missing'):
        L.append(f"- FAIL: {cell['missing']}. Its pre-registered neighbors (memory 15 / 30 days) have no json either. N for the haircut still counts it (section 4).")
        L.append(''); continue
    for k, x in r.items():
        lab = {'I': 'Class I', 'II': 'Class II', 'S': 'Cell rule'}[k]
        L.append(f"**{lab}: {'PASS' if x['passed'] else 'FAIL'}**" + ('' if x['passed'] else f" (failing: {', '.join(sorted(set(f[0].split(' ')[0] for f in x['fails']), key=okey))})"))
        L.append('')
        for cad, rs in x['per'].items():
            for cid, ok, txt in rs:
                L.append(f"- {cad} [{cid}] {'ok' if ok else ('n/a' if ok is None else '**FAIL**')}: {txt}")
        L.append('')
    # cell-specific notes
    J = load(cell['id'])
    if cell['id'] == 'TIME-1':
        L.append('- Decomposition the plan requires (section 6.6, FULL Sharpe): total vs W = design-weekday luck (seven-weekday mean - Sunday-candle W) + residual (TIME-1 - seven-weekday mean): ' +
                 '; '.join(f"{p} {J[f'{p}-tranche']['full']['var']['sharpe'] - J[f'{p}-tranche']['full']['base']['sharpe']:+.3f} = {REF[p]['mean_full'] - J[f'{p}-tranche']['full']['base']['sharpe']:+.3f} + {J[f'{p}-tranche']['full']['var']['sharpe'] - REF[p]['mean_full']:+.3f}" for p in ('A', 'B', 'C')) + '.')
        k1 = load('TIME-1__K1_control')
        L.append(f"- Control K = 1 (D at TV 0.25 band 10, not a neighbor): B POST Δ vs W {f3(k1['B-tranche']['post']['delta'])}, A FULL {f3(k1['A-tranche']['full']['delta'])}, C {f3(k1['C-tranche']['full']['delta'])}; turnover B {k1['B-tranche']['full']['var']['turnover']:.2f}x.")
        L.append(f"- Whole-contract lines: " + '; '.join(f"{p} ${c[:-2]} Δ {f3(x['delta'])} [{x['ci'][0]:+.2f},{x['ci'][1]:+.2f}] orders {x['orders_yr']:.0f} (W {x['base_orders_yr']:.0f})" for p in ('A', 'C') for c, x in J[f'{p}-tranche']['capital'].items()) + '. Orders/yr exceed 350 at every capital on A and at every capital on C.')
        L.append('- At the 1.98 hurdle cond 1 would pass (0.176 >= 0.153, P 0.009); the order cap fails regardless of the hurdle.')
    if cell['id'] in ('TIME-4', 'COMBO-C', 'COMBO-A', 'TIME-3'):
        cad = cell['cads'][-1]
        L.append(f"- Reference lines (section 1, reported next to every timing variant): seven-weekday FULL mean A 1.230 / B 0.895 / C 0.980; this cell's FULL Sharpe ({cad}) A {J[f'A-{cad}']['full']['var']['sharpe']:.3f}, B {J[f'B-{cad}']['full']['var']['sharpe']:.3f}, C {J[f'C-{cad}']['full']['var']['sharpe']:.3f}; D at TV 0.25 band 10: A 1.252 / B 0.856 / C 1.011.")
    if cell['id'] == 'TIME-4':
        L.append(f"- Whole-contract: " + '; '.join(f"{p} ${c[:-2]} orders {x['orders_yr']:.0f} (W {x['base_orders_yr']:.0f}) Δ {f3(x['delta'])}" for p in ('A', 'C') for c, x in J[f'{p}-weekly']['capital'].items()) + '. At the 1.98 hurdle cond 1 would pass (0.159 >= 0.141, P 0.005); the 220 order cap fails at every capital on A and at $1,000 / $2,500 / $5,000 on C (238 / 301 / 332).')
    if cell['id'] == 'COMBO-A':
        nb = load('COMBO-A__no_buffer')
        L.append(f"- Implementation note (not a verdict change): plan 6.7 says COMBO-A's unrounded line uses the 10 % band, but COMBO-A.json's unrounded rows use the buffer (b|u| = 0.10|u|, sim convention). The plan-literal unrounded line is COMBO-A__no_buffer's (TIME-1 + SZ-1, band 10): B POST Δ {f3(nb['B-tranche']['post']['delta'])} (sd {nb['B-tranche']['post']['sd_delta']:.4f}, hurdle {max(0.05, M_DEC*nb['B-tranche']['post']['sd_delta']):.3f}), B POST Sharpe {nb['B-tranche']['post']['var']['sharpe']:.3f} vs TIME-1 0.667. Cond 1 and extra 6a fail under either reading.")
    if cell['id'] == 'COMBO-C':
        L.append('- At the 1.98 hurdle cond 1 would pass (0.165 >= 0.154); the cell still fails its own adoption condition (Δ vs TIME-1 alone > 0 on B POST: -0.010, and every panel is below TIME-1), so per 6.7 the answer is "TIME-1 alone".')
    if cell['id'] == 'UNI-1':
        L.append('- Neighbors (information; the research-number pass line in 6.3 has no neighbor clause), same four clauses:')
        for lab in cell['nb']:
            nj = load(f'UNI-1__{lab}')
            for cad in cell['cads']:
                rs = uni1(cell, nj, cad); bad = [c for c, o, t in rs if o is False]
                L.append(f"  - UNI-1__{lab} {cad}: {'all four hold' if not bad else 'fails ' + ', '.join(bad)}: " + '; '.join(t for c, o, t in rs))
        L.append('- Raw (not vol-matched) maxDD is worse than static-24 on both books (daily -26.5 % vs -24.7 %, weekly -18.2 % vs -17.0 %); the verdict uses the matched-vol re-run because section 3 makes it the decision line when vol differs > 5 % (daily vol 18.4 % vs 16.7 %, weekly 12.2 % vs 11.0 %). Against the plan\'s quoted av_runs figures (-24.1 % / -16.8 %) the matched daily line is 0.09 pp worse, the weekly 0.2 pp better.')
        L.append('- Not in any json (6.3 report items, not pass clauses): whole-contract lines at $1,000 / $5,000 with the UNI-5 gate, names changed per reset, delisting events hit (`variants_universe.py report` prints them to stdout; no output was saved). Bw has no A6 stress line and no summary line (harness prints "(no B panel)" for Bw).')
        L.append('- D-0 precondition: D-0.json reproduces the harness static-24 to 0.000 on every window (FULL 0.8512 daily / 0.8101 weekly, = baseline.json B). The 6.0 gate text quotes 0.86 / 0.82 (av_runs/av_universe_9.txt, maxDD -24.1 / -16.8 %); the harness static-24 rounds to 0.85 / 0.81 (maxDD -24.7 / -17.0 %). This 0.01 gap is between the av_runs engine and the T0-verified harness and affects panel B in every cell, not UNI-1 specifically; UNI-1 clears 0.86 / 0.82 either way (1.050 / 0.984). Recorded, not used to fail the cell.')
    if cell['id'] == 'COST-2':
        b = load('D_band10'); parts = []
        for p in ('A', 'C'):
            for c in ('1000.0', '2500.0', '5000.0'):
                x = J[f'{p}-daily']['capital'][c]; y = b[f'{p}-daily']['capital'][c]
                parts.append(f"{p} ${c[:-2]} Sharpe {x['var']['sharpe']:.3f} vs {y['var']['sharpe']:.3f} ({x['var']['sharpe']-y['var']['sharpe']:+.3f}), orders {x['orders_yr']:.0f} vs {y['orders_yr']:.0f}, fees {pct(x['fees_yr'],3)} vs {pct(y['fees_yr'],3)}")
        L.append('- Versus band 0.10 rounded (D_band10.json capital lines; point gaps only, no paired bootstrap exists): ' + '; '.join(parts) + '. C $1,000 is +0.129, outside the 0.08 bound on this comparison too.')
        L.append('- The share of coin-days with B_i > A_i/3 (6.4 "is printed") is not in any json or log.')
        L.append('- A fee cut of 0.189 / 0.188 / 0.197 pp on A ($1,000 / $2,500 / $5,000) misses the 0.20 pp bar; C passes it only at $1,000 (0.332 pp). Orders fall 35-48 % everywhere (the >= 30 % half holds). B unrounded (b|u| buffer, information only) cuts fees 0.196 pp.')
    if cell['id'] == 'UNI-2':
        L.append('- Missing neighbor (b) "realistic cost line 1.18 + 2 bps/side on gold": no json. `variants_p1.UNI-2__goldcost_low` is registered but was never run, and its `_gold_sim(gold_cost_bps)` returns the unmodified simulation (the cost adjustment is not implemented), so running it as-is would not produce the pre-registered line either.')
        L.append('- At the 1.98 hurdle cond 1 would still fail on the daily book (0.093 < 0.094) and pass on the weekly (0.088 >= 0.084); cond 3 (B H1 -0.017 on both books) and the pre-bull extra fail regardless. A+gold vs A: POST +0.21 / +0.20, FULL +0.11 / +0.10, H1 -0.047 / -0.047: the gain is the 2024-26 gold bull the plan\'s extra condition was written to exclude.')
    if cell['id'] == 'OVL-2':
        L.append('- 6c episode counts come from the variants_overlay.py self-test (I7: B daily 88, weekly 72; 30 / 27 from 2022 on, of which 23 coin-runs are one 2024-03/04 cluster). The secondary cell 14d40 is reported, never chosen; 30d40 is the neighbor.')
        L.append('- 6b uses raw FULL CAGR (the cell lowers vol 24 % on B daily; CAGR at matched vol is not in the json).')
    if cell['id'] == 'OVL-3':
        L.append('- Gate flag (variants_overlay.py G1): diagnostics.md opened OVL-3 on the unconditional Correction column; under the cited source\'s wording (signal on) the gate is closed (+0.61 % / +0.09 %). The cell fails either way. Reported: flips/yr of the target (var vs base) B daily 702.7 vs 569.8, weekly 260.2 vs 208.2; fees/yr B daily ' +
                 f"{pct(J['B-daily']['full']['var']['fees_yr'],2)} vs {pct(J['B-daily']['full']['base']['fees_yr'],2)}, weekly {pct(J['B-weekly']['full']['var']['fees_yr'],2)} vs {pct(J['B-weekly']['full']['base']['fees_yr'],2)}.")
    if cell['id'] == 'SZ-13':
        L.append('- Unrounded lines are the baseline by construction (variants_sizing I-13.1), so every B/A/C unrounded Δ is 0.000; the content is on the capital lines. $500 / $2,500 / $5,000 lines are in the json (no-op at $2,500 / $5,000 by construction on A; $500 C daily +0.232, C weekly -0.232).')
        L.append('- "Sharpe within 0.05 of the unrounded line" read two-sided; one-sided (not more than 0.05 below) the weekly book passes it but the daily book still fails (C $1,000 0.926 vs 0.994), and cond 3 fails on both books regardless.')
    if cell['id'] == 'SZ-17':
        L.append('- B is not a B result by A7 (the B rows, absent here, would be the nine-coin subset). Neighbor clause read on A POST as the B substitute.')
    if cell['id'] == 'SIG-2':
        L.append('- The plan judges SIG-2 "unrounded and at $5,000"; SIG-2.json has no capital block, so the $5,000 half is missing evidence (an extra failure; the unrounded half fails on its own).')
    if cell['id'] == 'SIG-11':
        c = load('SIG-11__control_breakout_only')
        L.append(f"- Control line (breakout only, not a neighbor): B POST Δ daily {f3(c['B-daily']['post']['delta'])}, weekly {f3(c['B-weekly']['post']['delta'])}; A FULL {f3(c['A-daily']['full']['delta'])} / {f3(c['A-weekly']['full']['delta'])}. 6a read on FULL and POST of A and B (the plan names no window; it fails on A in every window).")
    if cell['id'] == 'SIG-13':
        L.append('- Target not stated in A8; read as "both" like every other signal cell. A6 stress line for SIG-13 uses archive funding in the signal (variants_signal I11; reporting only, exposure is lower so A6 is not triggered).')
    if cell['id'] == 'SIG-4':
        L.append('- SIG-4__same_day_norm has zero exposure until the 360-day channel exists, so its FULL window misses 2020-21 (variants_signal N2); its B POST Δ equals the primary\'s.')
    if cell['id'] == 'SIG-3b':
        L.append('- SIG-3b__denom30 is an exact 2/3 rescale of the primary (variants_signal N1), so it is a degenerate neighbor; the cell fails cond 1-2 regardless.')
    L.append('')

L.append('## Data and implementation flags found while judging (none changes a verdict)')
L.append('')
L.append('1. Haircut multiplier: plan A3 states 2.37 for N_eff = 90, but its own Bailey-Lopez de Prado formula gives 2.49 at N = 90 (the harness summary uses 2.49). The decision here uses 2.37 as instructed; nothing clears either.')
L.append('2. sd_Delta in every json is CI width / 3.92, not the bootstrap stdev section 4 specifies.')
L.append('3. COMBO-A unrounded rows use the contract buffer instead of the plan\'s 10 % band (see COMBO-A detail); COMBO-A__no_buffer is the plan-literal unrounded line and also fails.')
L.append('4. UNI-2 neighbor (b) never ran and its implementation is a no-op (see UNI-2 detail).')
L.append('5. COST-2 required windows (2022-23, 2025-26) and the paired comparison vs band-0.10 rounded at each capital were not produced; the B_i > A_i/3 share was not printed.')
L.append('6. D-0 gate figures 0.86 / 0.82 (av_runs) vs harness static-24 0.8512 / 0.8101 (see UNI-1 detail).')
L.append('7. OVL-3 gate column (G1) and OVL-2 / OVL-3 report items (episodes, flips) live only in variants_overlay.py\'s self-test text, not in the json.')
L.append('8. UNI-1 report items (whole-contract lines, names changed, delisting events) were not saved anywhere.')
L.append('')

if OUT:
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('WROTE', OUT, len(L), 'lines')
