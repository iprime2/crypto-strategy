# Phase 2 verdicts (mechanical application of phase1_plan.md section 5)

Judge run 2026-10-21. Plan `research2/phase1_plan.md` sha256 9ad0a829f7bc269f5ce99e7c4e57a09ef89ffe1699776b479abe9b291418c095 (matches `phase2/plan_sha256.txt`). Inputs: `phase2/<id>.json` and `phase2/<id>__*.json` (COST-2 and COMBO-A are the post-buffer-fix reruns; struck-through and `_selftest` summary lines ignored), `phase2/reference.json` (seven-weekday lines), `phase2/diagnostics.md`, the family modules' docstrings for numbers the harness does not write. No result file was changed; this file is the only output.

## How each condition was read (fixed before reading the verdict column; every choice is the reading closest to the plan text)

- **Class I cond 1 hurdle** = max(0.05, 2.37 x sd_Delta) (A3 text and the task contract). Also shown: 1.98 x sd_Delta (section 4, N = 24) and 2.49 x sd_Delta, which is what the plan's own formula gives at N_eff = 90 (2.493; the harness summary's "hurdle" uses it). The A3 text's 2.37 corresponds to N of about 66, not 90; no verdict differs between 2.37 and 2.49 (nothing clears 2.37).
- **sd_Delta** is the json field, i.e. (CI hi - CI lo)/3.92 of `sim.block_bootstrap_diff` (1000 draws, 20-day blocks, seed 7), not `statistics.stdev(diffs)` as section 4 writes; P(Delta <= 0) and the 95 % CI are the bootstrap's.
- **Matched vol (cond 5 and every "maxDD/worst 7-day no worse")**: the json `matched_vol` re-run on B FULL when present (vol differs > 5 %); when absent the raw FULL line is used, because section 3 asks for the re-run only above 5 %. Tolerances 2 pp / 1 pp (cond 5); 0 for the cells whose extra says "no worse".
- **"both"**: a condition must hold on the daily AND the weekly book. Counting for near misses is by distinct condition (a condition failing on both cadences counts once); each extra is its own condition.
- **Class II metrics**: whole-contract `capital` blocks only where the plan says rounded / contracts (COST-2, COMBO-B "vs D round-nearest", SZ-13, SZ-17, the TIME-1 / TIME-4 / COMBO-A order caps at $1,000); everywhere else (SIG-2, SIG-1B, SIG-3a, SIG-3b, SIG-4, SZ-1, SZ-3, TIME-3) orders/yr and trades/yr use FULL unrounded **turnover** as the proxy and funding/yr the FULL `funding_yr`, as the task instructs. "The operational gain holds in every neighbor" = the neighbor meets the same stated threshold on all panels.
- **A6 Delta-funding stress**: triggered when average gross (FULL var/base) rises > 10 % on any of A, B, C; then cond 2 must also hold on the stress line, whose only condition-2 window is A POST (stress Sharpe var - base >= -0.03). B POST stress Delta is shown for information.
- **Reference lines** (plan section 1) for TIME-1: seven-weekday FULL means A 1.230 / B 0.895 / C 0.980 (reference.json); "within 0.03" read two-sided on FULL (POST printed). TIME-3: six-hour mean A 1.21 (plan section 1 text; no file on disk), applied to A-weekly only (there is no daily six-hour reference).
- **No-B cells**: SZ-13 (plan: "B not applicable"; primary judgement C and A at $1,000) and SZ-17 (A7: "B falls back to A's nine, reported as A/C only") are judged on the conditions their own text lists, translated to A/C. UNI-1 is the research-number class and is judged only on its 6.3 pass line (Bw vs static-24).
- **Missing evidence is a FAIL**: SIG-9 (no json), UNI-2 neighbor (b) "realistic cost line 1.18 + 2 bps on gold" (no json; `UNI-2__goldcost_low` is registered in variants_p1.py but never run, and its cost adjustment is a no-op), SIG-2's required $5,000 line, COST-2's 2022-23 / 2025-26 windows and the paired comparison vs band-0.10 rounded at each capital.

## Verdict table

| id | class | target | B POST Δ | 95 % CI | P(Δ≤0) | sd_Δ | hurdle 2.37 (1.98) | A POST / FULL Δ | C FULL Δ | B H1 / H2 Δ | neighbors ok? | matched-vol DD / worst7 ok? (var/base) | operational metric before → after | extras ok? | Delta-funding stress (A6) ok? | after-tax seg CAGR var/base (B FULL) | A3 param seen | VERDICT (first failing condition) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG-2 | I/II | both | d +0.016<br>w -0.128 | d [-0.171, +0.226]<br>w [-0.326, +0.040] | d 0.437<br>w 0.931 | d 0.1013<br>w 0.0933 | d 0.240 (0.201)<br>w 0.221 (0.185) | d -0.069 / -0.096<br>w -0.218 / -0.147 | d -0.144<br>w -0.233 | d -0.104 / +0.043<br>w -0.133 / -0.110 | d NO w NO / II: d NO w NO | d ok w ok<br>d -26.2%/-24.7%, -11.5%/-11.8% mv<br>w -18.4%/-17.0%, -7.6%/-7.6% mv | d trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->10.39x (-34%), fund 3.43%->3.17% (-8%); B turn 13.68->9.40x (-31%), fund 3.13%->2.83% (-10%); C turn 14.80->11.02x (-26%), fund 1.86%->1.79% (-4%)<br>w trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->2.56x (-25%), fund 2.11%->1.93% (-9%); B turn 2.94->2.32x (-21%), fund 1.93%->1.70% (-12%); C turn 3.24->2.74x (-15%), fund 1.05%->1.06% (+1%) | d NO (6)<br>w NO (6) | d ok: not triggered (gross A -5% B -5% C -2%); stress A POST d -0.070, B POST d +0.016<br>w ok: not triggered (gross A -5% B -4% C +1%); stress A POST d -0.218, B POST d -0.128 | d 4.0%/4.1%<br>w 2.7%/3.9% | yes (d) | **FAIL**: class I cond 1 (d/w): B POST d +0.016 vs hurdle 0.240 (2.37 sd; 2.49 sd = 0.253; 1.98 sd = 0.201), P 0.437 ‖ class II cond 1 (d/w): B POST d +0.016 (>= -0.03), CI lo -0.171 (>= -0.10) |
| SIG-1B | I/II | both | d -0.115<br>w -0.157 | d [-0.386, +0.219]<br>w [-0.456, +0.161] | d 0.757<br>w 0.826 | d 0.1542<br>w 0.1574 | d 0.365 (0.305)<br>w 0.373 (0.312) | d -0.129 / -0.223<br>w -0.219 / -0.214 | d -0.330<br>w -0.396 | d -0.388 / -0.082<br>w -0.328 / -0.130 | d NO w NO / II: d NO w NO | d NO w NO<br>d -28.7%/-24.7%, -11.0%/-11.8% mv<br>w -19.2%/-17.0%, -10.0%/-7.6% mv | d trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->8.85x (-43%), fund 3.43%->2.19% (-36%); B turn 13.68->8.04x (-41%), fund 3.13%->1.90% (-39%); C turn 14.80->8.98x (-39%), fund 1.86%->1.13% (-39%)<br>w trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->2.07x (-40%), fund 2.11%->1.31% (-38%); B turn 2.94->1.83x (-38%), fund 1.93%->1.12% (-42%); C turn 3.24->2.26x (-30%), fund 1.05%->0.64% (-39%) | none | d ok: not triggered (gross A -49% B -53% C -50%); stress A POST d -0.119, B POST d -0.111<br>w ok: not triggered (gross A -49% B -51% C -48%); stress A POST d -0.209, B POST d -0.153 | d 0.1%/4.1%<br>w 0.9%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.115 vs hurdle 0.365 (2.37 sd; 2.49 sd = 0.384; 1.98 sd = 0.305), P 0.757 ‖ class II cond 1 (d/w): B POST d -0.115 (>= -0.03), CI lo -0.386 (>= -0.10) |
| SIG-3a | I/II | both | d -0.105<br>w -0.074 | d [-0.482, +0.300]<br>w [-0.417, +0.328] | d 0.651<br>w 0.596 | d 0.1995<br>w 0.1901 | d 0.473 (0.395)<br>w 0.451 (0.376) | d -0.282 / -0.221<br>w -0.153 / -0.095 | d -0.455<br>w -0.115 | d +0.056 / -0.247<br>w -0.009 / -0.111 | d NO w NO / II: d NO w NO | d ok w ok<br>d -24.6%/-24.7%, -10.9%/-11.8% mv<br>w -18.7%/-17.0%, -7.2%/-7.6% mv | d orders/yr (turnover proxy) down >=15%: A turn 15.65->5.07x (-68%); B turn 13.68->4.61x (-66%); C turn 14.80->4.64x (-69%)<br>w orders/yr (turnover proxy) down >=15%: A turn 3.43->1.82x (-47%); B turn 2.94->1.64x (-44%); C turn 3.24->1.63x (-49%) | none | d NO: TRIGGERED (gross A +42% B +37% C +38%); stress A POST d -0.295, B POST d -0.112 < -0.03<br>w NO: TRIGGERED (gross A +41% B +36% C +41%); stress A POST d -0.164, B POST d -0.081 < -0.03 | d 6.5%/4.1%<br>w 4.9%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.105 vs hurdle 0.473 (2.37 sd; 2.49 sd = 0.497; 1.98 sd = 0.395), P 0.651 ‖ class II cond 1 (d/w): B POST d -0.105 (>= -0.03), CI lo -0.482 (>= -0.10) |
| SIG-3b | I/II | both | d -0.127<br>w -0.091 | d [-0.530, +0.348]<br>w [-0.496, +0.427] | d 0.651<br>w 0.573 | d 0.2241<br>w 0.2355 | d 0.531 (0.444)<br>w 0.558 (0.466) | d -0.371 / -0.350<br>w -0.203 / -0.190 | d -0.619<br>w -0.321 | d -0.040 / -0.252<br>w -0.037 / -0.181 | d NO w NO / II: d NO w NO | d NO w NO<br>d -25.8%/-24.7%, -15.0%/-11.8% mv<br>w -18.5%/-17.0%, -9.5%/-7.6% mv | d trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->2.07x (-87%), fund 3.43%->1.66% (-51%); B turn 13.68->1.61x (-88%), fund 3.13%->1.31% (-58%); C turn 14.80->1.82x (-88%), fund 1.86%->0.64% (-66%)<br>w trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->0.73x (-79%), fund 2.11%->1.07% (-49%); B turn 2.94->0.60x (-80%), fund 1.93%->0.83% (-57%); C turn 3.24->0.63x (-81%), fund 1.05%->0.39% (-62%) | d NO (6)<br>w NO (6) | d ok: not triggered (gross A -56% B -61% C -59%); stress A POST d -0.368, B POST d -0.130<br>w ok: not triggered (gross A -55% B -61% C -57%); stress A POST d -0.196, B POST d -0.093 | d 1.8%/4.1%<br>w 1.5%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.127 vs hurdle 0.531 (2.37 sd; 2.49 sd = 0.559; 1.98 sd = 0.444), P 0.651 ‖ class II cond 1 (d/w): B POST d -0.127 (>= -0.03), CI lo -0.530 (>= -0.10) |
| SIG-4 | I/II | both | d +0.008<br>w -0.049 | d [-0.281, +0.322]<br>w [-0.343, +0.219] | d 0.487<br>w 0.631 | d 0.1537<br>w 0.1433 | d 0.364 (0.304)<br>w 0.340 (0.284) | d -0.200 / -0.138<br>w -0.272 / -0.179 | d -0.365<br>w -0.397 | d -0.052 / +0.030<br>w -0.056 / -0.137 | d NO w NO / II: d NO w NO | d ok w ok<br>d -23.2%/-24.7%, -10.5%/-11.8% mv<br>w -14.3%/-17.0%, -7.2%/-7.6% mv | d mvDD >=3pp better AND turnover (trades proxy) lower: A mvDD -21.9%->-21.3% (+0.6pp), turn 15.65->9.44x; B mvDD -24.7%->-23.2% (+1.5pp), turn 13.68->8.83x; C mvDD -14.1%->-20.0% (-5.9pp), turn 14.80->10.97x<br>w mvDD >=3pp better AND turnover (trades proxy) lower: A mvDD -16.9%->-16.6% (+0.3pp), turn 3.43->3.15x; B mvDD -17.0%->-14.3% (+2.7pp), turn 2.94->2.95x; C mvDD -9.1%->-14.0% (-4.9pp), turn 3.24->3.69x | none | d ok: not triggered (gross A -6% B -8% C +1%); stress A POST d -0.206, B POST d +0.005<br>w ok: not triggered (gross A -5% B -6% C +4%); stress A POST d -0.277, B POST d -0.051 | d 3.7%/4.1%<br>w 2.3%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d +0.008 vs hurdle 0.364 (2.37 sd; 2.49 sd = 0.383; 1.98 sd = 0.304), P 0.487 ‖ class II cond 1 (d/w): B POST d +0.008 (>= -0.03), CI lo -0.281 (>= -0.10) |
| SIG-7A | I | both | d -0.229<br>w -0.061 | d [-0.462, +0.022]<br>w [-0.274, +0.197] | d 0.959<br>w 0.647 | d 0.1236<br>w 0.1201 | d 0.293 (0.245)<br>w 0.285 (0.238) | d -0.190 / -0.099<br>w -0.005 / +0.035 | d -0.064<br>w +0.042 | d -0.031 / -0.238<br>w +0.071 / -0.062 | d NO w NO | d NO w ok<br>d -26.8%/-24.7%, -12.8%/-11.8% mv<br>w -16.2%/-17.0%, -8.3%/-7.6% mv | class I (no II metric); info d B turn 13.68->11.81x, fund 3.13%->3.11%<br>w B turn 2.94->2.51x, fund 1.93%->1.95% | d NO (6a,6b)<br>w NO (6a) | d ok: not triggered (gross A -8% B -12% C -14%); stress A POST d -0.193, B POST d -0.231<br>w ok: not triggered (gross A -8% B -11% C -13%); stress A POST d -0.004, B POST d -0.062 | d 2.2%/4.1%<br>w 3.8%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.229 vs hurdle 0.293 (2.37 sd; 2.49 sd = 0.308; 1.98 sd = 0.245), P 0.959 |
| SIG-10 | I | both | d -0.063<br>w -0.149 | d [-0.366, +0.238]<br>w [-0.386, +0.106] | d 0.654<br>w 0.864 | d 0.1542<br>w 0.1254 | d 0.366 (0.305)<br>w 0.297 (0.248) | d -0.094 / -0.074<br>w -0.080 / -0.054 | d -0.112<br>w -0.072 | d -0.041 / -0.026<br>w -0.051 / -0.169 | d NO w NO | d ok w ok<br>d -25.6%/-24.7%, -9.9%/-11.8% mv<br>w -17.9%/-17.0%, -6.5%/-7.6% mv | class I (no II metric); info d B turn 13.68->14.99x, fund 3.13%->3.69%<br>w B turn 2.94->3.28x, fund 1.93%->2.28% | none | d NO: TRIGGERED (gross A +48% B +53% C +57%); stress A POST d -0.105, B POST d -0.068 < -0.03<br>w NO: TRIGGERED (gross A +47% B +52% C +56%); stress A POST d -0.090, B POST d -0.153 < -0.03 | d 4.5%/4.1%<br>w 3.7%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.063 vs hurdle 0.366 (2.37 sd; 2.49 sd = 0.385; 1.98 sd = 0.305), P 0.654 |
| SIG-9 | I | both | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | no json | **FAIL**: no phase2/SIG-9.json: conditional cell not run (diagnostics.md D-1 gate "SIG-9 runs = False") |
| SIG-11 | I | both | d +0.011<br>w -0.020 | d [-0.074, +0.100]<br>w [-0.104, +0.065] | d 0.365<br>w 0.669 | d 0.0443<br>w 0.0433 | d 0.105 (0.088)<br>w 0.103 (0.086) | d -0.077 / -0.047<br>w -0.083 / -0.047 | d -0.124<br>w -0.056 | d +0.006 / +0.023<br>w -0.058 / +0.019 | d NO w NO | d ok w ok<br>d -23.5%/-24.7%, -11.9%/-11.8% mv<br>w -17.3%/-17.0%, -7.9%/-7.6% mv | class I (no II metric); info d B turn 13.68->8.00x, fund 3.13%->2.50%<br>w B turn 2.94->2.06x, fund 1.93%->1.53% | d NO (6a)<br>w NO (6a,6b) | d ok: not triggered (gross A -23% B -24% C -22%); stress A POST d -0.076, B POST d +0.011<br>w ok: not triggered (gross A -23% B -24% C -21%); stress A POST d -0.082, B POST d -0.020 | d 4.2%/4.1%<br>w 3.0%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d +0.011 vs hurdle 0.105 (2.37 sd; 2.49 sd = 0.111; 1.98 sd = 0.088), P 0.365 |
| SZ-1 | II | both | d -0.058<br>w -0.045 | d [-0.148, +0.017]<br>w [-0.117, +0.023] | d 0.927<br>w 0.900 | d 0.0421<br>w 0.0357 | n/a (class) | d -0.054 / -0.069<br>w -0.027 / -0.062 | d -0.118<br>w -0.091 | d -0.040 / -0.078<br>w -0.037 / -0.065 | d NO w NO | d ok w ok<br>d -25.5%/-24.7%, -11.7%/-11.8% mv<br>w -17.5%/-17.0%, -7.7%/-7.6% mv | d orders/yr (turnover proxy) down >=15%: A turn 15.65->14.11x (-10%); B turn 13.68->12.48x (-9%); C turn 14.80->13.70x (-7%)<br>w orders/yr (turnover proxy) down >=15%: A turn 3.43->2.99x (-13%); B turn 2.94->2.60x (-12%); C turn 3.24->2.93x (-9%) | d ok<br>w NO (6) | d ok: not triggered (gross A -8% B -8% C -5%); stress A POST d -0.055, B POST d -0.058<br>w ok: not triggered (gross A -9% B -8% C -6%); stress A POST d -0.027, B POST d -0.045 | d 3.2%/4.1%<br>w 3.3%/3.9% | no | **FAIL**: class II cond 1 (d/w): B POST d -0.058 (>= -0.03), CI lo -0.148 (>= -0.10) |
| SZ-3 | II | both | d -0.060<br>w -0.066 | d [-0.154, +0.041]<br>w [-0.146, +0.027] | d 0.886<br>w 0.930 | d 0.0497<br>w 0.0441 | n/a (class) | d -0.055 / -0.053<br>w -0.027 / -0.034 | d -0.142<br>w -0.124 | d -0.012 / -0.073<br>w -0.006 / -0.084 | d NO w NO | d ok w ok<br>d -25.7%/-24.7%, -11.2%/-11.8% mv<br>w -17.7%/-17.0%, -7.4%/-7.6% mv | d trades/yr <= base AND orders/yr down >=10% (turnover proxy for both): A turn 15.65->15.01x (-4%); B turn 13.68->13.11x (-4%); C turn 14.80->14.57x (-2%)<br>w trades/yr <= base AND orders/yr down >=10% (turnover proxy for both): A turn 3.43->3.24x (-5%); B turn 2.94->2.80x (-5%); C turn 3.24->3.08x (-5%) | d ok<br>w ok | d ok: not triggered (gross A -6% B -6% C -4%); stress A POST d -0.058, B POST d -0.061<br>w ok: not triggered (gross A -6% B -6% C -5%); stress A POST d -0.030, B POST d -0.067 | d 3.1%/4.1%<br>w 3.3%/3.9% | no | **FAIL**: class II cond 1 (d/w): B POST d -0.060 (>= -0.03), CI lo -0.154 (>= -0.10) |
| SZ-6b | I | both | d +0.011<br>w +0.001 | d [-0.030, +0.051]<br>w [-0.040, +0.039] | d 0.321<br>w 0.505 | d 0.0208<br>w 0.0202 | d 0.050 (0.050)<br>w 0.050 (0.050) | d -0.012 / -0.019<br>w -0.009 / -0.019 | d -0.006<br>w -0.009 | d -0.010 / +0.000<br>w -0.016 / -0.017 | d ok w NO | d ok w ok<br>d -24.9%/-24.7%, -12.1%/-11.8% mv<br>w -17.1%/-17.0%, -7.7%/-7.6% mv | class I (no II metric); info d B turn 13.68->14.81x, fund 3.13%->3.41%<br>w B turn 2.94->3.19x, fund 1.93%->2.09% | d NO (6)<br>w NO (6) | d ok: not triggered (gross A +4% B +9% C +2%); stress A POST d -0.011, B POST d +0.011<br>w ok: not triggered (gross A +4% B +9% C +1%); stress A POST d -0.008, B POST d +0.000 | d 4.4%/4.1%<br>w 4.2%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d +0.011 vs hurdle 0.050 (2.37 sd; 2.49 sd = 0.052; 1.98 sd = 0.050), P 0.321 |
| SZ-13 | II ($1,000) | both, whole contracts | n/a (no B by plan) | n/a (no B by plan) | n/a (no B by plan) | n/a (no B by plan) | n/a | d $1,000 vs rounded: A +0.000<br>w $1,000 vs rounded: A -0.001 | d $1,000 -0.001<br>w $1,000 +0.052 | n/a (no B) | d NO w NO | d ok w ok ($1,000 vs rounded base; detail) | d orders/yr down vs rounded base AND vol within 10% of unrounded: A orders 871.5->871.5 (+0.0%), vol vs unrounded +0.0% FAIL; C orders 565.9->568.6 (+0.5%), vol vs unrounded +1.0% FAIL<br>w orders/yr down vs rounded base AND vol within 10% of unrounded: A orders 171.4->171.9 (+0.3%), vol vs unrounded +0.9% FAIL; C orders 131.0->126.0 (-3.9%), vol vs unrounded +2.3% | see detail | d ok: not triggered (gross A +0% C +0%); stress A POST d +0.000<br>w ok: not triggered (gross A +0% C +0%); stress A POST d +0.000 | d 12.7%/12.7% (A)<br>w 8.2%/8.2% (A) | no | **FAIL**: class II cond 1* (d/w): Sharpe within 0.05 of the unrounded line (B n/a): A $1,000 1.239 vs unrounded 1.250 (-0.010); C $1,000 0.926 vs unround… |
| UNI-1 | R | both | d +0.276<br>w +0.286 | d [-0.224, +0.741]<br>w [-0.233, +0.786] | d 0.119<br>w 0.123 | d 0.2464<br>w 0.2599 | n/a (class) | n/a (Bw only) | n/a | d +0.182 / +0.231<br>w +0.097 / +0.296 | not in the research-number rule (info in detail) | d ok w ok (R3, mv) | d Bw turn 13.68->15.05x (info)<br>w Bw turn 2.94->3.34x (info) | see detail | d n/a (Bw: no stress line run)<br>w n/a (Bw: no stress line run) | d 8.6%/4.1%<br>w 6.3%/3.9% | no | **PASS (research-number class)** |
| UNI-2 | I | both | d +0.093<br>w +0.088 | d [+0.011, +0.197]<br>w [+0.016, +0.182] | d 0.012<br>w 0.009 | d 0.0474<br>w 0.0424 | d 0.112 (0.094)<br>w 0.100 (0.084) | d +0.206 / +0.112<br>w +0.203 / +0.100 | d +0.000<br>w +0.000 | d -0.017 / +0.155<br>w -0.017 / +0.145 | d NO w NO | d ok w ok<br>d -23.9%/-24.0%, -11.3%/-11.7%<br>w -16.9%/-17.1%, -7.3%/-7.5% | class I (no II metric); info d B turn 13.53->15.59x, fund 3.12%->3.28%<br>w B turn 2.92->3.50x, fund 1.92%->2.02% | d NO (6a)<br>w NO (6a) | d ok: TRIGGERED (gross A +50% B +24% C +0%); stress A POST d +0.208, B POST d +0.093 >= -0.03<br>w ok: TRIGGERED (gross A +51% B +24% C +0%); stress A POST d +0.205, B POST d +0.090 >= -0.03 | d 5.3%/5.0%<br>w 4.6%/4.4% | no | **FAIL**: class I cond 1 (d/w): B POST d +0.093 vs hurdle 0.112 (2.37 sd; 2.49 sd = 0.118; 1.98 sd = 0.094), P 0.012 |
| COST-2 | II | D, whole contracts | d +0.030 | d [-0.009, +0.067] | d 0.063 | d 0.0194 | n/a (class) | d +0.029 / +0.015 | d +0.034 | d +0.005 / +0.038 | d NO | d ok<br>d -24.6%/-24.7%, -11.7%/-11.8% | d fees down >=0.20pp AND orders down >=30% vs round-nearest band 0 (A, C whole contracts): A $1000 orders 872->548 (-37%), fees 1.146%->0.958% (-0.189pp) FAIL; A $2500 orders 1083->616 (-43%), fees 1.145%->0.958% (-0.188pp) FAIL; A $5000 orders 1262->660 (-48%)… | d NO (6a,6b) | d ok: not triggered (gross A -2% B -2% C -2%); stress A POST d +0.030, B POST d +0.030 | d 5.4%/4.1% | yes (m) | **FAIL**: class II cond 3 (d): fees down >=0.20pp AND orders down >=30% vs round-nearest band 0 (A, C whole contracts): A $1000 orders 872->548 (-37%)… |
| OVL-2 | I | both | d +0.138<br>w +0.105 | d [-0.041, +0.463]<br>w [-0.053, +0.319] | d 0.116<br>w 0.127 | d 0.1286<br>w 0.0949 | d 0.305 (0.255)<br>w 0.225 (0.188) | d +0.122 / +0.124<br>w +0.081 / +0.070 | d +0.097<br>w +0.138 | d -0.125 / +0.259<br>w -0.067 / +0.198 | d ok w ok | d ok w ok<br>d -20.0%/-24.7%, -8.4%/-11.8% mv<br>w -14.8%/-17.0%, -7.1%/-7.6% mv | class I (no II metric); info d B turn 13.68->12.41x, fund 3.13%->1.25%<br>w B turn 2.94->2.78x, fund 1.93%->0.83% | d NO (6b)<br>w NO (6b) | d ok: not triggered (gross A -15% B -18% C -7%); stress A POST d +0.119, B POST d +0.136<br>w ok: not triggered (gross A -15% B -18% C -7%); stress A POST d +0.078, B POST d +0.103 | d 3.6%/4.1%<br>w 3.2%/3.9% | yes (window/threshold) | **FAIL**: class I cond 1 (d/w): B POST d +0.138 vs hurdle 0.305 (2.37 sd; 2.49 sd = 0.321; 1.98 sd = 0.255), P 0.116 |
| OVL-3 | I | both | d -0.075<br>w -0.029 | d [-0.191, +0.016]<br>w [-0.129, +0.048] | d 0.951<br>w 0.781 | d 0.0529<br>w 0.0450 | d 0.125 (0.105)<br>w 0.107 (0.089) | d -0.095 / -0.053<br>w -0.031 / -0.031 | d -0.080<br>w -0.031 | d -0.029 / -0.055<br>w -0.063 / +0.010 | d ok w ok | d ok w ok<br>d -23.5%/-24.7%, -12.0%/-11.8% mv<br>w -16.5%/-17.0%, -7.3%/-7.6% | class I (no II metric); info d B turn 13.68->14.56x, fund 3.13%->2.97%<br>w B turn 2.94->3.17x, fund 1.93%->1.80% | d NO (6b)<br>w ok | d ok: not triggered (gross A -10% B -10% C -9%); stress A POST d -0.092, B POST d -0.073<br>w ok: not triggered (gross A -10% B -9% C -9%); stress A POST d -0.029, B POST d -0.028 | d 2.6%/4.1%<br>w 3.1%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.075 vs hurdle 0.125 (2.37 sd; 2.49 sd = 0.132; 1.98 sd = 0.105), P 0.951 |
| TIME-1 | I vs W | T | t +0.176 | t [+0.031, +0.334] | t 0.009 | t 0.0773 | t 0.183 (0.153) | t +0.158 / +0.119 | t +0.272 | t +0.049 / +0.199 | t ok | t ok<br>t -14.3%/-17.0%, -7.6%/-7.6% | A $1,000 orders 171->594, C 131->409; B turn 2.94->2.87x | t NO (6b) | t ok: not triggered (gross A -1% B -2% C +2%); stress A POST d +0.159, B POST d +0.175 | t 5.0%/3.9% | yes (K) | **FAIL**: class I cond 1 (t): B POST d +0.176 vs hurdle 0.183 (2.37 sd; 2.49 sd = 0.193; 1.98 sd = 0.153), P 0.009 |
| TIME-3 | I | both | d +0.059<br>w +0.007 | d [-0.046, +0.170]<br>w [-0.129, +0.121] | d 0.131<br>w 0.472 | d 0.0551<br>w 0.0639 | d 0.131 (0.109)<br>w 0.151 (0.127) | d +0.015 / +0.007<br>w -0.052 / -0.010 | d -0.015<br>w +0.037 | d +0.031 / +0.048<br>w -0.068 / +0.112 | d ok w ok | d ok w ok<br>d -23.4%/-24.7%, -11.6%/-11.8%<br>w -18.9%/-17.0%, -7.5%/-7.6% | class I (no II metric); info d B turn 13.68->11.06x, fund 3.13%->3.07%<br>w B turn 2.94->2.87x, fund 1.93%->1.90% | d NO (6c)<br>w NO (6a) | d ok: not triggered (gross A -3% B -3% C -4%); stress A POST d +0.016, B POST d +0.059<br>w ok: not triggered (gross A -2% B -2% C -0%); stress A POST d -0.049, B POST d +0.008 | d 5.3%/4.1%<br>w 4.1%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d +0.059 vs hurdle 0.131 (2.37 sd; 2.49 sd = 0.137; 1.98 sd = 0.109), P 0.131 |
| TIME-4 | I vs W | W, whole contracts | w +0.159 | w [+0.034, +0.313] | w 0.005 | w 0.0712 | w 0.169 (0.141) | w +0.127 / +0.125 | w +0.249 | w +0.016 / +0.180 | w ok | w ok<br>w -15.1%/-17.0%, -7.5%/-7.6% | A $1,000 orders 171->332, C 131->238; B turn 2.94->2.69x | w NO (6c) | w ok: not triggered (gross A -6% B -7% C -3%); stress A POST d +0.130, B POST d +0.160 | w 4.9%/3.9% | no | **FAIL**: class I cond 1 (w): B POST d +0.159 vs hurdle 0.169 (2.37 sd; 2.49 sd = 0.178; 1.98 sd = 0.141), P 0.005 |
| COMBO-A | I vs W | T, whole contracts | t +0.123 | t [-0.046, +0.294] | t 0.073 | t 0.0866 | t 0.205 (0.172) | t +0.129 / +0.075 | t +0.189 | t +0.016 / +0.128 | t ok | t ok<br>t -15.5%/-17.0%, -8.0%/-7.6% mv | A $1,000 orders 171->523, C 131->347; B turn 2.94->2.16x | t NO (6a,6b) | t ok: not triggered (gross A -10% B -10% C -5%); stress A POST d +0.128, B POST d +0.122 | t 4.6%/3.9% | no | **FAIL**: class I cond 1 (t): B POST d +0.123 vs hurdle 0.205 (2.37 sd; 2.49 sd = 0.216; 1.98 sd = 0.172), P 0.073 |
| COMBO-B | I/II | D, whole contracts | d -0.045 | d [-0.248, +0.142] | d 0.693 | d 0.0996 | d 0.236 (0.197) | d -0.124 / -0.149 | d -0.252 | d -0.108 / -0.035 | d NO / II: d NO | d NO<br>d -27.0%/-24.7%, -11.8%/-11.8% mv | d funding down >=25% AND orders down >=30% vs D round-nearest (A, C rounded): A $1000 orders 872->881 (+1%), fund 3.43%->2.92% (-15%) FAIL; A $2500 orders 1083->1184 (+9%), fund 3.43%->2.88% (-16%) FAIL; A $5000 orders 1262->1363 (+8%), fund 3.43%->2.88% (-16%)… | none | d ok: not triggered (gross A -14% B -14% C -9%); stress A POST d -0.127, B POST d -0.046 | d 4.8%/4.1% | no | **FAIL**: class I cond 1 (d): B POST d -0.045 vs hurdle 0.236 (2.37 sd; 2.49 sd = 0.248; 1.98 sd = 0.197), P 0.693 ‖ class II cond 1 (d): B POST d -0.045 (>= -0.03), CI lo -0.248 (>= -0.10) |
| COMBO-C | I vs W | T | t +0.165 | t [+0.018, +0.322] | t 0.013 | t 0.0776 | t 0.184 (0.154) | t +0.137 / +0.109 | t +0.270 | t +0.043 / +0.190 | t ok | t ok<br>t -15.0%/-17.0%, -8.0%/-7.6% mv | class I (no II metric); info t B turn 2.94->2.74x, fund 1.93%->1.81% | t NO (6a,6b) | t ok: not triggered (gross A -4% B -5% C -2%); stress A POST d +0.139, B POST d +0.165 | t 4.9%/3.9% | no | **FAIL**: class I cond 1 (t): B POST d +0.165 vs hurdle 0.184 (2.37 sd; 2.49 sd = 0.193; 1.98 sd = 0.154), P 0.013 |
| SZ-17 | II (A7) | both (A/C only) | n/a (no B by plan) | n/a (no B by plan) | n/a (no B by plan) | n/a (no B by plan) | n/a | d -0.080 / -0.060<br>w -0.041 / -0.059 | d -0.151<br>w -0.114 | n/a (no B) | d NO w NO | d NO w NO<br>d -22.7%/-21.9%, -9.9%/-9.5% mv<br>w -17.4%/-16.9%, -7.6%/-7.4% mv (A) | d orders/yr down >=15% on rounded lines: A $1000 orders 872->812 (-7%) FAIL; C $1000 orders 566->542 (-4%) FAIL<br>w orders/yr down >=15% on rounded lines: A $1000 orders 171->159 (-7%) FAIL; C $1000 orders 131->120 (-8%) FAIL | see detail | d ok: not triggered (gross A -10% C -9%); stress A POST d -0.081<br>w ok: not triggered (gross A -10% C -9%); stress A POST d -0.042 | d 10.4%/12.7% (A)<br>w 6.7%/8.2% (A) | no | **FAIL**: class II cond 1/2* (d/w): Sharpe within -0.03 (B n/a by A7): A POST -0.080, A FULL -0.060, C FULL -0.151 |
| SIG-13 | I (A8) | both (interpreted) | d -0.036<br>w -0.016 | d [-0.093, +0.041]<br>w [-0.097, +0.056] | d 0.831<br>w 0.733 | d 0.0340<br>w 0.0389 | d 0.081 (0.067)<br>w 0.092 (0.077) | d -0.027 / -0.068<br>w -0.031 / -0.049 | d -0.108<br>w +0.002 | d -0.067 / -0.062<br>w -0.029 / +0.024 | d NO w NO | d ok w ok<br>d -25.4%/-24.7%, -11.9%/-11.8% mv<br>w -16.8%/-17.0%, -7.8%/-7.6% mv | class I (no II metric); info d B turn 13.68->13.42x, fund 3.13%->2.83%<br>w B turn 2.94->2.90x, fund 1.93%->1.74% | d ok<br>w ok | d ok: not triggered (gross A -5% B -4% C -6%); stress A POST d -0.030, B POST d -0.037<br>w ok: not triggered (gross A -6% B -4% C -5%); stress A POST d -0.034, B POST d -0.017 | d 2.6%/4.1%<br>w 3.5%/3.9% | no | **FAIL**: class I cond 1 (d/w): B POST d -0.036 vs hurdle 0.081 (2.37 sd; 2.49 sd = 0.085; 1.98 sd = 0.067), P 0.831 |

Column notes: d / w / t = daily / weekly / tranche (T) book. B = the 24 ex-ante panel (UNI-2: 25 ex-ante + gold vs 25; UNI-1: Bw rotating vs static-24 through D-0). hurdle column shows 2.37 sd (1.98 sd), floor 0.05. "after-tax seg" = A1 (a) per-coin realized-segment VDA 30 % CAGR on B FULL (A FULL for SZ-13/SZ-17, Bw for UNI-1). Table cells are abbreviated; every number used is in the detail section.

## Passes

- **UNI-1** (R, both): daily: FULL 1.050 vs static-24 0.851, POST Δ +0.276 (CI [-0.22, +0.74], P 0.12), mv maxDD -24.2% vs -24.7%, H1 +0.182 H2 +0.231; weekly: FULL 0.984 vs static-24 0.810, POST Δ +0.286 (CI [-0.23, +0.79], P 0.12), mv maxDD -16.6% vs -17.0%, H1 +0.097 H2 +0.296. **Reading-dependent:** the maxDD clause passes only at matched vol (section 3 decision line; vol is 10 % above static-24 on both books); on raw maxDD it fails on both books (-26.5 % vs -24.7 %, -18.2 % vs -17.0 %) and UNI-1 would be a one-condition near miss. Every neighbor fails the matched-vol maxDD clause on at least one book (age121 and N12 also a half). Per section 5 this is a research number for the annual review (kill criterion #6), a live rule only at >= $5,000; it is not a Sharpe-improvement claim (CI contains 0, P 0.12). Caveats in the detail section (raw maxDD worse, neighbors, missing report items, D-0 gate figures).
- No class I or class II cell passes. Nothing goes to Phase 3 as a return or execution proposal from this grid; per section 5 every failing cell is "do nothing" and goes to the considered-and-rejected table with its numbers.

## Near misses (failed exactly one condition)

- none. No cell fails exactly one condition at the 2.37 hurdle.

Closest (exactly two failing conditions; listed for the memo, not near misses):

- **TIME-1** class I: cond 1 (t): B POST d +0.176 vs hurdle 0.183 (2.37 sd; 2.49 sd = 0.193; 1.98 sd = 0.153), P 0.009 AND cond 6b orders/yr <= 350 at $1,000 (t): A 594 (W 171); C 409 (W 131)
- **TIME-4** class I: cond 1 (w): B POST d +0.159 vs hurdle 0.169 (2.37 sd; 2.49 sd = 0.178; 1.98 sd = 0.141), P 0.005 AND cond 6c orders/yr <= 220 at $1,000 (w): A 332 (W 171); C 238 (W 131)

## Detail: every condition, every cadence

### SIG-2 | class I/II | target both

**Class I: FAIL** (failing: 1, 2, 3, 4, 6)

- daily [1] **FAIL**: B POST d +0.016 vs hurdle 0.240 (2.37 sd; 2.49 sd = 0.253; 1.98 sd = 0.201), P 0.437
- daily [2] **FAIL**: A POST -0.069, A FULL -0.096, C FULL -0.144; A6 not triggered (gross A -5% B -5% C -2%); stress A POST d -0.070, B POST d +0.016
- daily [3] **FAIL**: B H1 -0.104, H2 +0.043
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.084): d0.5 +0.014, d1.5 +0.019, SIG1A_form -0.008 FAIL
- daily [5] ok: B FULL DD -26.2% vs -24.7%, worst7 -11.5% vs -11.8% (mv TV 0.434)
- daily [6 judged at $5,000 too] **FAIL**: MISSING: no $5,000 whole-contract line in SIG-2.json (plan: "Judge unrounded and at $5,000")
- weekly [1] **FAIL**: B POST d -0.128 vs hurdle 0.221 (2.37 sd; 2.49 sd = 0.233; 1.98 sd = 0.185), P 0.931
- weekly [2] **FAIL**: A POST -0.218, A FULL -0.147, C FULL -0.233; A6 not triggered (gross A -5% B -4% C +1%); stress A POST d -0.218, B POST d -0.128
- weekly [3] **FAIL**: B H1 -0.133, H2 -0.110
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.228): d0.5 -0.133 FAIL, d1.5 -0.123 FAIL, SIG1A_form -0.135 FAIL
- weekly [5] ok: B FULL DD -18.4% vs -17.0%, worst7 -7.6% vs -7.6% (mv TV 0.278)
- weekly [6 judged at $5,000 too] **FAIL**: MISSING: no $5,000 whole-contract line in SIG-2.json (plan: "Judge unrounded and at $5,000")

**Class II: FAIL** (failing: 1, 2, 3, 4, 6)

- daily [1] **FAIL**: B POST d +0.016 (>= -0.03), CI lo -0.171 (>= -0.10)
- daily [2] **FAIL**: A POST -0.069, A FULL -0.096, C FULL -0.144; B H1 -0.104, H2 +0.043 (>= -0.05); A6 not triggered (gross A -5% B -5% C -2%); stress A POST d -0.070, B POST d +0.016
- daily [3] **FAIL**: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->10.39x (-34%), fund 3.43%->3.17% (-8%); B turn 13.68->9.40x (-31%), fund 3.13%->2.83% (-10%); C turn 14.80->11.02x (-26%), fund 1.86%->1.79% (-4%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): d0.5 d +0.014, op NOT met FAIL, d1.5 d +0.019, op NOT met FAIL, SIG1A_form d -0.008, op NOT met FAIL
- daily [5] ok: B FULL DD -26.2% vs -24.7%, worst7 -11.5% vs -11.8% (mv TV 0.434)
- daily [6 judged at $5,000 too] **FAIL**: MISSING: no $5,000 whole-contract line in SIG-2.json (plan: "Judge unrounded and at $5,000")
- weekly [1] **FAIL**: B POST d -0.128 (>= -0.03), CI lo -0.326 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.218, A FULL -0.147, C FULL -0.233; B H1 -0.133, H2 -0.110 (>= -0.05); A6 not triggered (gross A -5% B -4% C +1%); stress A POST d -0.218, B POST d -0.128
- weekly [3] **FAIL**: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->2.56x (-25%), fund 2.11%->1.93% (-9%); B turn 2.94->2.32x (-21%), fund 1.93%->1.70% (-12%); C turn 3.24->2.74x (-15%), fund 1.05%->1.06% (+1%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): d0.5 d -0.133, op NOT met FAIL, d1.5 d -0.123, op NOT met FAIL, SIG1A_form d -0.135, op NOT met FAIL
- weekly [5] ok: B FULL DD -18.4% vs -17.0%, worst7 -7.6% vs -7.6% (mv TV 0.278)
- weekly [6 judged at $5,000 too] **FAIL**: MISSING: no $5,000 whole-contract line in SIG-2.json (plan: "Judge unrounded and at $5,000")

- The plan judges SIG-2 "unrounded and at $5,000"; SIG-2.json has no capital block, so the $5,000 half is missing evidence (an extra failure; the unrounded half fails on its own).

### SIG-1B | class I/II | target both

**Class I: FAIL** (failing: 1, 2, 3, 4, 5)

- daily [1] **FAIL**: B POST d -0.115 vs hurdle 0.365 (2.37 sd; 2.49 sd = 0.384; 1.98 sd = 0.305), P 0.757
- daily [2] **FAIL**: A POST -0.129, A FULL -0.223, C FULL -0.330; A6 not triggered (gross A -49% B -53% C -50%); stress A POST d -0.119, B POST d -0.111
- daily [3] **FAIL**: B H1 -0.388, H2 -0.082
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.215): t0.75 -0.032 FAIL, t1.25 -0.000 FAIL
- daily [5] **FAIL**: B FULL DD -28.7% vs -24.7%, worst7 -11.0% vs -11.8% (mv TV 0.656)
- weekly [1] **FAIL**: B POST d -0.157 vs hurdle 0.373 (2.37 sd; 2.49 sd = 0.392; 1.98 sd = 0.312), P 0.826
- weekly [2] **FAIL**: A POST -0.219, A FULL -0.214, C FULL -0.396; A6 not triggered (gross A -49% B -51% C -48%); stress A POST d -0.209, B POST d -0.153
- weekly [3] **FAIL**: B H1 -0.328, H2 -0.130
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.257): t0.75 -0.034 FAIL, t1.25 -0.322 FAIL
- weekly [5] **FAIL**: B FULL DD -19.2% vs -17.0%, worst7 -10.0% vs -7.6% (mv TV 0.427)

**Class II: FAIL** (failing: 1, 2, 4, 5)

- daily [1] **FAIL**: B POST d -0.115 (>= -0.03), CI lo -0.386 (>= -0.10)
- daily [2] **FAIL**: A POST -0.129, A FULL -0.223, C FULL -0.330; B H1 -0.388, H2 -0.082 (>= -0.05); A6 not triggered (gross A -49% B -53% C -50%); stress A POST d -0.119, B POST d -0.111
- daily [3] ok: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->8.85x (-43%), fund 3.43%->2.19% (-36%); B turn 13.68->8.04x (-41%), fund 3.13%->1.90% (-39%); C turn 14.80->8.98x (-39%), fund 1.86%->1.13% (-39%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): t0.75 d -0.032, op NOT met FAIL, t1.25 d -0.000, op ok
- daily [5] **FAIL**: B FULL DD -28.7% vs -24.7%, worst7 -11.0% vs -11.8% (mv TV 0.656)
- weekly [1] **FAIL**: B POST d -0.157 (>= -0.03), CI lo -0.456 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.219, A FULL -0.214, C FULL -0.396; B H1 -0.328, H2 -0.130 (>= -0.05); A6 not triggered (gross A -49% B -51% C -48%); stress A POST d -0.209, B POST d -0.153
- weekly [3] ok: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->2.07x (-40%), fund 2.11%->1.31% (-38%); B turn 2.94->1.83x (-38%), fund 1.93%->1.12% (-42%); C turn 3.24->2.26x (-30%), fund 1.05%->0.64% (-39%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): t0.75 d -0.034, op NOT met FAIL, t1.25 d -0.322, op ok FAIL
- weekly [5] **FAIL**: B FULL DD -19.2% vs -17.0%, worst7 -10.0% vs -7.6% (mv TV 0.427)


### SIG-3a | class I/II | target both

**Class I: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d -0.105 vs hurdle 0.473 (2.37 sd; 2.49 sd = 0.497; 1.98 sd = 0.395), P 0.651
- daily [2] **FAIL**: A POST -0.282, A FULL -0.221, C FULL -0.455; A6 TRIGGERED (gross A +42% B +37% C +38%); stress A POST d -0.295, B POST d -0.112 < -0.03
- daily [3] **FAIL**: B H1 +0.056, H2 -0.247
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.205): speed_x0.75 -0.036 FAIL, speed_x1.25 -0.148 FAIL
- daily [5] ok: B FULL DD -24.6% vs -24.7%, worst7 -10.9% vs -11.8% (mv TV 0.335)
- weekly [1] **FAIL**: B POST d -0.074 vs hurdle 0.451 (2.37 sd; 2.49 sd = 0.474; 1.98 sd = 0.376), P 0.596
- weekly [2] **FAIL**: A POST -0.153, A FULL -0.095, C FULL -0.115; A6 TRIGGERED (gross A +41% B +36% C +41%); stress A POST d -0.164, B POST d -0.081 < -0.03
- weekly [3] **FAIL**: B H1 -0.009, H2 -0.111
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.174): speed_x0.75 -0.046 FAIL, speed_x1.25 -0.141 FAIL
- weekly [5] ok: B FULL DD -18.7% vs -17.0%, worst7 -7.2% vs -7.6% (mv TV 0.218)

**Class II: FAIL** (failing: 1, 2, 4)

- daily [1] **FAIL**: B POST d -0.105 (>= -0.03), CI lo -0.482 (>= -0.10)
- daily [2] **FAIL**: A POST -0.282, A FULL -0.221, C FULL -0.455; B H1 +0.056, H2 -0.247 (>= -0.05); A6 TRIGGERED (gross A +42% B +37% C +38%); stress A POST d -0.295, B POST d -0.112 < -0.03
- daily [3] ok: orders/yr (turnover proxy) down >=15%: A turn 15.65->5.07x (-68%); B turn 13.68->4.61x (-66%); C turn 14.80->4.64x (-69%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): speed_x0.75 d -0.036, op ok, speed_x1.25 d -0.148, op ok FAIL
- daily [5] ok: B FULL DD -24.6% vs -24.7%, worst7 -10.9% vs -11.8% (mv TV 0.335)
- weekly [1] **FAIL**: B POST d -0.074 (>= -0.03), CI lo -0.417 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.153, A FULL -0.095, C FULL -0.115; B H1 -0.009, H2 -0.111 (>= -0.05); A6 TRIGGERED (gross A +41% B +36% C +41%); stress A POST d -0.164, B POST d -0.081 < -0.03
- weekly [3] ok: orders/yr (turnover proxy) down >=15%: A turn 3.43->1.82x (-47%); B turn 2.94->1.64x (-44%); C turn 3.24->1.63x (-49%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): speed_x0.75 d -0.046, op ok, speed_x1.25 d -0.141, op ok FAIL
- weekly [5] ok: B FULL DD -18.7% vs -17.0%, worst7 -7.2% vs -7.6% (mv TV 0.218)


### SIG-3b | class I/II | target both

**Class I: FAIL** (failing: 1, 2, 3, 4, 5, 6)

- daily [1] **FAIL**: B POST d -0.127 vs hurdle 0.531 (2.37 sd; 2.49 sd = 0.559; 1.98 sd = 0.444), P 0.651
- daily [2] **FAIL**: A POST -0.371, A FULL -0.350, C FULL -0.619; A6 not triggered (gross A -56% B -61% C -59%); stress A POST d -0.368, B POST d -0.130
- daily [3] **FAIL**: B H1 -0.040, H2 -0.252
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.227): denom15 -0.129 FAIL, denom30 -0.127 FAIL
- daily [5] **FAIL**: B FULL DD -25.8% vs -24.7%, worst7 -15.0% vs -11.8% (mv TV 0.998)
- daily [6 mvDD no worse] **FAIL**: B FULL mvDD -25.8% vs -24.7% (mv TV 0.998)
- weekly [1] **FAIL**: B POST d -0.091 vs hurdle 0.558 (2.37 sd; 2.49 sd = 0.587; 1.98 sd = 0.466), P 0.573
- weekly [2] **FAIL**: A POST -0.203, A FULL -0.190, C FULL -0.321; A6 not triggered (gross A -55% B -61% C -57%); stress A POST d -0.196, B POST d -0.093
- weekly [3] **FAIL**: B H1 -0.037, H2 -0.181
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.191): denom15 -0.096 FAIL, denom30 -0.093 FAIL
- weekly [5] **FAIL**: B FULL DD -18.5% vs -17.0%, worst7 -9.5% vs -7.6% (mv TV 0.635)
- weekly [6 mvDD no worse] **FAIL**: B FULL mvDD -18.5% vs -17.0% (mv TV 0.635)

**Class II: FAIL** (failing: 1, 2, 4, 5, 6)

- daily [1] **FAIL**: B POST d -0.127 (>= -0.03), CI lo -0.530 (>= -0.10)
- daily [2] **FAIL**: A POST -0.371, A FULL -0.350, C FULL -0.619; B H1 -0.040, H2 -0.252 (>= -0.05); A6 not triggered (gross A -56% B -61% C -59%); stress A POST d -0.368, B POST d -0.130
- daily [3] ok: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 15.65->2.07x (-87%), fund 3.43%->1.66% (-51%); B turn 13.68->1.61x (-88%), fund 3.13%->1.31% (-58%); C turn 14.80->1.82x (-88%), fund 1.86%->0.64% (-66%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): denom15 d -0.129, op ok FAIL, denom30 d -0.127, op ok FAIL
- daily [5] **FAIL**: B FULL DD -25.8% vs -24.7%, worst7 -15.0% vs -11.8% (mv TV 0.998)
- daily [6 mvDD no worse] **FAIL**: B FULL mvDD -25.8% vs -24.7% (mv TV 0.998)
- weekly [1] **FAIL**: B POST d -0.091 (>= -0.03), CI lo -0.496 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.203, A FULL -0.190, C FULL -0.321; B H1 -0.037, H2 -0.181 (>= -0.05); A6 not triggered (gross A -55% B -61% C -57%); stress A POST d -0.196, B POST d -0.093
- weekly [3] ok: trades/yr (turnover proxy) AND funding/yr down >=25%: A turn 3.43->0.73x (-79%), fund 2.11%->1.07% (-49%); B turn 2.94->0.60x (-80%), fund 1.93%->0.83% (-57%); C turn 3.24->0.63x (-81%), fund 1.05%->0.39% (-62%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): denom15 d -0.096, op ok FAIL, denom30 d -0.093, op ok FAIL
- weekly [5] **FAIL**: B FULL DD -18.5% vs -17.0%, worst7 -9.5% vs -7.6% (mv TV 0.635)
- weekly [6 mvDD no worse] **FAIL**: B FULL mvDD -18.5% vs -17.0% (mv TV 0.635)

- SIG-3b__denom30 is an exact 2/3 rescale of the primary (variants_signal N1), so it is a degenerate neighbor; the cell fails cond 1-2 regardless.

### SIG-4 | class I/II | target both

**Class I: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d +0.008 vs hurdle 0.364 (2.37 sd; 2.49 sd = 0.383; 1.98 sd = 0.304), P 0.487
- daily [2] **FAIL**: A POST -0.200, A FULL -0.138, C FULL -0.365; A6 not triggered (gross A -6% B -8% C +1%); stress A POST d -0.206, B POST d +0.005
- daily [3] **FAIL**: B H1 -0.052, H2 +0.030
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.092): 7_lookbacks +0.040, paper_sizing -0.013 FAIL, same_day_norm +0.008
- daily [5] ok: B FULL DD -23.2% vs -24.7%, worst7 -10.5% vs -11.8% (mv TV 0.479)
- weekly [1] **FAIL**: B POST d -0.049 vs hurdle 0.340 (2.37 sd; 2.49 sd = 0.357; 1.98 sd = 0.284), P 0.631
- weekly [2] **FAIL**: A POST -0.272, A FULL -0.179, C FULL -0.397; A6 not triggered (gross A -5% B -6% C +4%); stress A POST d -0.277, B POST d -0.051
- weekly [3] **FAIL**: B H1 -0.056, H2 -0.137
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.149): 7_lookbacks -0.023 FAIL, paper_sizing -0.056 FAIL, same_day_norm -0.049 FAIL
- weekly [5] ok: B FULL DD -14.3% vs -17.0%, worst7 -7.2% vs -7.6% (mv TV 0.299)

**Class II: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d +0.008 (>= -0.03), CI lo -0.281 (>= -0.10)
- daily [2] **FAIL**: A POST -0.200, A FULL -0.138, C FULL -0.365; B H1 -0.052, H2 +0.030 (>= -0.05); A6 not triggered (gross A -6% B -8% C +1%); stress A POST d -0.206, B POST d +0.005
- daily [3] **FAIL**: mvDD >=3pp better AND turnover (trades proxy) lower: A mvDD -21.9%->-21.3% (+0.6pp), turn 15.65->9.44x; B mvDD -24.7%->-23.2% (+1.5pp), turn 13.68->8.83x; C mvDD -14.1%->-20.0% (-5.9pp), turn 14.80->10.97x
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): 7_lookbacks d +0.040, op NOT met FAIL, paper_sizing d -0.013, op NOT met FAIL, same_day_norm d +0.008, op NOT met FAIL
- daily [5] ok: B FULL DD -23.2% vs -24.7%, worst7 -10.5% vs -11.8% (mv TV 0.479)
- weekly [1] **FAIL**: B POST d -0.049 (>= -0.03), CI lo -0.343 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.272, A FULL -0.179, C FULL -0.397; B H1 -0.056, H2 -0.137 (>= -0.05); A6 not triggered (gross A -5% B -6% C +4%); stress A POST d -0.277, B POST d -0.051
- weekly [3] **FAIL**: mvDD >=3pp better AND turnover (trades proxy) lower: A mvDD -16.9%->-16.6% (+0.3pp), turn 3.43->3.15x; B mvDD -17.0%->-14.3% (+2.7pp), turn 2.94->2.95x; C mvDD -9.1%->-14.0% (-4.9pp), turn 3.24->3.69x
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): 7_lookbacks d -0.023, op NOT met FAIL, paper_sizing d -0.056, op NOT met FAIL, same_day_norm d -0.049, op NOT met FAIL
- weekly [5] ok: B FULL DD -14.3% vs -17.0%, worst7 -7.2% vs -7.6% (mv TV 0.299)

- SIG-4__same_day_norm has zero exposure until the 360-day channel exists, so its FULL window misses 2020-21 (variants_signal N2); its B POST Δ equals the primary's.

### SIG-7A | class I | target both

**Class I: FAIL** (failing: 1, 2, 3, 4, 5, 6a, 6b)

- daily [1] **FAIL**: B POST d -0.229 vs hurdle 0.293 (2.37 sd; 2.49 sd = 0.308; 1.98 sd = 0.245), P 0.959
- daily [2] **FAIL**: A POST -0.190, A FULL -0.099, C FULL -0.064; A6 not triggered (gross A -8% B -12% C -14%); stress A POST d -0.193, B POST d -0.231
- daily [3] **FAIL**: B H1 -0.031, H2 -0.238
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.329): L200 -0.195 FAIL, L300 -0.019 FAIL
- daily [5] **FAIL**: B FULL DD -26.8% vs -24.7%, worst7 -12.8% vs -11.8% (mv TV 0.437)
- daily [6a +0.05 on B POST] **FAIL**: B POST d -0.229
- daily [6b maxDD no worse] **FAIL**: B FULL mvDD -26.8% vs -24.7%
- weekly [1] **FAIL**: B POST d -0.061 vs hurdle 0.285 (2.37 sd; 2.49 sd = 0.299; 1.98 sd = 0.238), P 0.647
- weekly [2] ok: A POST -0.005, A FULL +0.035, C FULL +0.042; A6 not triggered (gross A -8% B -11% C -13%); stress A POST d -0.004, B POST d -0.062
- weekly [3] **FAIL**: B H1 +0.071, H2 -0.062
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.161): L200 -0.031 FAIL, L300 +0.010
- weekly [5] ok: B FULL DD -16.2% vs -17.0%, worst7 -8.3% vs -7.6% (mv TV 0.275)
- weekly [6a +0.05 on B POST] **FAIL**: B POST d -0.061
- weekly [6b maxDD no worse] ok: B FULL mvDD -16.2% vs -17.0%


### SIG-10 | class I | target both

**Class I: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d -0.063 vs hurdle 0.366 (2.37 sd; 2.49 sd = 0.385; 1.98 sd = 0.305), P 0.654
- daily [2] **FAIL**: A POST -0.094, A FULL -0.074, C FULL -0.112; A6 TRIGGERED (gross A +48% B +53% C +57%); stress A POST d -0.105, B POST d -0.068 < -0.03
- daily [3] **FAIL**: B H1 -0.041, H2 -0.026
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.163): map_0_25_50_100 -0.071 FAIL, map_0_50_75_100 -0.116 FAIL
- daily [5] ok: B FULL DD -25.6% vs -24.7%, worst7 -9.9% vs -11.8% (mv TV 0.322)
- weekly [1] **FAIL**: B POST d -0.149 vs hurdle 0.297 (2.37 sd; 2.49 sd = 0.313; 1.98 sd = 0.248), P 0.864
- weekly [2] **FAIL**: A POST -0.080, A FULL -0.054, C FULL -0.072; A6 TRIGGERED (gross A +47% B +52% C +56%); stress A POST d -0.090, B POST d -0.153 < -0.03
- weekly [3] **FAIL**: B H1 -0.051, H2 -0.169
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.249): map_0_25_50_100 -0.119 FAIL, map_0_50_75_100 -0.208 FAIL
- weekly [5] ok: B FULL DD -17.9% vs -17.0%, worst7 -6.5% vs -7.6% (mv TV 0.203)


### SIG-9 | class I | target both

- FAIL: no phase2/SIG-9.json: conditional cell not run (diagnostics.md D-1 gate "SIG-9 runs = False"). Its pre-registered neighbors (memory 15 / 30 days) have no json either. N for the haircut still counts it (section 4).

### SIG-11 | class I | target both

**Class I: FAIL** (failing: 1, 2, 3, 4, 6a, 6b)

- daily [1] **FAIL**: B POST d +0.011 vs hurdle 0.105 (2.37 sd; 2.49 sd = 0.111; 1.98 sd = 0.088), P 0.365
- daily [2] **FAIL**: A POST -0.077, A FULL -0.047, C FULL -0.124; A6 not triggered (gross A -23% B -24% C -22%); stress A POST d -0.076, B POST d +0.011
- daily [3] ok: B H1 +0.006, H2 +0.023
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.089): looks_20_80_160 -0.014 FAIL, smooth_L8 +0.048
- daily [5] ok: B FULL DD -23.5% vs -24.7%, worst7 -11.9% vs -11.8% (mv TV 0.515)
- daily [6a breakout-only >= sign-only on A and B] **FAIL**: control d A full -0.172, A post -0.243, B full -0.002, B post +0.001
- daily [6b 50/50 beats both on B POST] ok: B POST Sharpe 50/50 0.597, sign 0.586, breakout 0.587
- weekly [1] **FAIL**: B POST d -0.020 vs hurdle 0.103 (2.37 sd; 2.49 sd = 0.108; 1.98 sd = 0.086), P 0.669
- weekly [2] **FAIL**: A POST -0.083, A FULL -0.047, C FULL -0.056; A6 not triggered (gross A -23% B -24% C -21%); stress A POST d -0.082, B POST d -0.020
- weekly [3] **FAIL**: B H1 -0.058, H2 +0.019
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.120): looks_20_80_160 -0.027 FAIL, smooth_L8 +0.010
- weekly [5] ok: B FULL DD -17.3% vs -17.0%, worst7 -7.9% vs -7.6% (mv TV 0.325)
- weekly [6a breakout-only >= sign-only on A and B] **FAIL**: control d A full -0.146, A post -0.254, B full -0.084, B post -0.072
- weekly [6b 50/50 beats both on B POST] **FAIL**: B POST Sharpe 50/50 0.471, sign 0.492, breakout 0.419

- Control line (breakout only, not a neighbor): B POST Δ daily +0.001, weekly -0.072; A FULL -0.172 / -0.146. 6a read on FULL and POST of A and B (the plan names no window; it fails on A in every window).

### SZ-1 | class II | target both

**Class II: FAIL** (failing: 1, 2, 3, 4, 6)

- daily [1] **FAIL**: B POST d -0.058 (>= -0.03), CI lo -0.148 (>= -0.10)
- daily [2] **FAIL**: A POST -0.054, A FULL -0.069, C FULL -0.118; B H1 -0.040, H2 -0.078 (>= -0.05); A6 not triggered (gross A -8% B -8% C -5%); stress A POST d -0.055, B POST d -0.058
- daily [3] **FAIL**: orders/yr (turnover proxy) down >=15%: A turn 15.65->14.11x (-10%); B turn 13.68->12.48x (-9%); C turn 14.80->13.70x (-7%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): COM45 d -0.050, op NOT met FAIL, COM90 d -0.072, op NOT met FAIL
- daily [5] ok: B FULL DD -25.5% vs -24.7%, worst7 -11.7% vs -11.8% (mv TV 0.424)
- daily [6 worst7 no worse] ok: B FULL mv worst7 -11.7% vs -11.8% (mv TV 0.424); info A -10.0% vs -9.5%, C -6.6% vs -7.7%
- weekly [1] **FAIL**: B POST d -0.045 (>= -0.03), CI lo -0.117 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.027, A FULL -0.062, C FULL -0.091; B H1 -0.037, H2 -0.065 (>= -0.05); A6 not triggered (gross A -9% B -8% C -6%); stress A POST d -0.027, B POST d -0.045
- weekly [3] **FAIL**: orders/yr (turnover proxy) down >=15%: A turn 3.43->2.99x (-13%); B turn 2.94->2.60x (-12%); C turn 3.24->2.93x (-9%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): COM45 d -0.047, op NOT met FAIL, COM90 d -0.060, op NOT met FAIL
- weekly [5] ok: B FULL DD -17.5% vs -17.0%, worst7 -7.7% vs -7.6% (mv TV 0.267)
- weekly [6 worst7 no worse] **FAIL**: B FULL mv worst7 -7.7% vs -7.6% (mv TV 0.267); info A -7.7% vs -7.4%, C -4.7% vs -4.4%


### SZ-3 | class II | target both

**Class II: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d -0.060 (>= -0.03), CI lo -0.154 (>= -0.10)
- daily [2] **FAIL**: A POST -0.055, A FULL -0.053, C FULL -0.142; B H1 -0.012, H2 -0.073 (>= -0.05); A6 not triggered (gross A -6% B -6% C -4%); stress A POST d -0.058, B POST d -0.061
- daily [3] **FAIL**: trades/yr <= base AND orders/yr down >=10% (turnover proxy for both): A turn 15.65->15.01x (-4%); B turn 13.68->13.11x (-4%); C turn 14.80->14.57x (-2%)
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): wfast06 d -0.072, op NOT met FAIL, wfast08 d -0.048, op NOT met FAIL
- daily [5] ok: B FULL DD -25.7% vs -24.7%, worst7 -11.2% vs -11.8% (mv TV 0.430)
- daily [6 worst7 no worse] ok: B FULL mv worst7 -11.2% vs -11.8% (mv TV 0.430); info A -9.9% vs -9.5%, C -7.1% vs -7.7%
- weekly [1] **FAIL**: B POST d -0.066 (>= -0.03), CI lo -0.146 (>= -0.10)
- weekly [2] **FAIL**: A POST -0.027, A FULL -0.034, C FULL -0.124; B H1 -0.006, H2 -0.084 (>= -0.05); A6 not triggered (gross A -6% B -6% C -5%); stress A POST d -0.030, B POST d -0.067
- weekly [3] **FAIL**: trades/yr <= base AND orders/yr down >=10% (turnover proxy for both): A turn 3.43->3.24x (-5%); B turn 2.94->2.80x (-5%); C turn 3.24->3.08x (-5%)
- weekly [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): wfast06 d -0.080, op NOT met FAIL, wfast08 d -0.057, op NOT met FAIL
- weekly [5] ok: B FULL DD -17.7% vs -17.0%, worst7 -7.4% vs -7.6% (mv TV 0.269)
- weekly [6 worst7 no worse] ok: B FULL mv worst7 -7.4% vs -7.6% (mv TV 0.269); info A -7.8% vs -7.4%, C -5.1% vs -4.4%


### SZ-6b | class I | target both

**Class I: FAIL** (failing: 1, 3, 4, 6)

- daily [1] **FAIL**: B POST d +0.011 vs hurdle 0.050 (2.37 sd; 2.49 sd = 0.052; 1.98 sd = 0.050), P 0.321
- daily [2] ok: A POST -0.012, A FULL -0.019, C FULL -0.006; A6 not triggered (gross A +4% B +9% C +2%); stress A POST d -0.011, B POST d +0.011
- daily [3] **FAIL**: B H1 -0.010, H2 +0.000
- daily [4] ok: neighbors B POST (>=0 and >= -0.089): ref060 +0.012, ref080 +0.009
- daily [5] ok: B FULL DD -24.9% vs -24.7%, worst7 -12.1% vs -11.8% (mv TV 0.368)
- daily [6 d >= +0.05 on A, B and C] **FAIL**: A POST -0.012, A FULL -0.019, B POST +0.011, C FULL -0.006
- weekly [1] **FAIL**: B POST d +0.001 vs hurdle 0.050 (2.37 sd; 2.49 sd = 0.050; 1.98 sd = 0.050), P 0.505
- weekly [2] ok: A POST -0.009, A FULL -0.019, C FULL -0.009; A6 not triggered (gross A +4% B +9% C +1%); stress A POST d -0.008, B POST d +0.000
- weekly [3] **FAIL**: B H1 -0.016, H2 -0.017
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.099): ref060 -0.001 FAIL, ref080 +0.003
- weekly [5] ok: B FULL DD -17.1% vs -17.0%, worst7 -7.7% vs -7.6% (mv TV 0.229)
- weekly [6 d >= +0.05 on A, B and C] **FAIL**: A POST -0.009, A FULL -0.019, B POST +0.001, C FULL -0.009


### SZ-13 | class II ($1,000) | target both, whole contracts

**Cell rule: FAIL** (failing: 1*, 3, 4)

- daily [1*] **FAIL**: Sharpe within 0.05 of the unrounded line (B n/a): A $1,000 1.239 vs unrounded 1.250 (-0.010); C $1,000 0.926 vs unrounded 0.994 (-0.068)
- daily [2*] ok: d >= -0.03 at $1,000 (FULL; POST not in capital blocks): A $1,000 vs rounded base d +0.000; C $1,000 vs rounded base d -0.001
- daily [3] **FAIL**: orders/yr down vs rounded base AND vol within 10% of unrounded: A orders 871.5->871.5 (+0.0%), vol vs unrounded +0.0% FAIL; C orders 565.9->568.6 (+0.5%), vol vs unrounded +1.0% FAIL
- daily [4] **FAIL**: neighbors at $1,000 (d >= -0.08, op gain holds): thr2_exit16: A d -0.009 orders 871.5->864.5, C d +0.199 orders 565.9->571.4 FAIL; exit09: A d -0.001 orders 871.5->870.8, C d -0.001 orders 565.9->568.6 FAIL
- daily [5] ok: DD/worst7 at $1,000 vs rounded base (no matched-vol re-run exists for capital lines): A DD -21.7% vs -21.7%, w7 -10.1% vs -10.1%; C DD -15.2% vs -15.2%, w7 -7.6% vs -7.6%
- weekly [1*] **FAIL**: Sharpe within 0.05 of the unrounded line (B n/a): A $1,000 1.094 vs unrounded 1.121 (-0.026); C $1,000 0.857 vs unrounded 0.704 (+0.153) [one-sided reading: pass]
- weekly [2*] ok: d >= -0.03 at $1,000 (FULL; POST not in capital blocks): A $1,000 vs rounded base d -0.001; C $1,000 vs rounded base d +0.052
- weekly [3] **FAIL**: orders/yr down vs rounded base AND vol within 10% of unrounded: A orders 171.4->171.9 (+0.3%), vol vs unrounded +0.9% FAIL; C orders 131.0->126.0 (-3.9%), vol vs unrounded +2.3%
- weekly [4] **FAIL**: neighbors at $1,000 (d >= -0.08, op gain holds): thr2_exit16: A d +0.064 orders 171.4->164.6, C d -0.297 orders 131.0->103.0 FAIL; exit09: A d +0.021 orders 171.4->172.8 FAIL, C d -0.031 orders 131.0->124.1
- weekly [5] ok: DD/worst7 at $1,000 vs rounded base (no matched-vol re-run exists for capital lines): A DD -17.7% vs -17.4%, w7 -7.3% vs -7.7%; C DD -9.2% vs -9.5%, w7 -4.4% vs -5.1%

- Unrounded lines are the baseline by construction (variants_sizing I-13.1), so every B/A/C unrounded Δ is 0.000; the content is on the capital lines. $500 / $2,500 / $5,000 lines are in the json (no-op at $2,500 / $5,000 by construction on A; $500 C daily +0.232, C weekly -0.232).
- "Sharpe within 0.05 of the unrounded line" read two-sided; one-sided (not more than 0.05 below) the weekly book passes it but the daily book still fails (C $1,000 0.926 vs 0.994), and cond 3 fails on both books regardless.

### UNI-1 | class R | target both

**Cell rule: PASS**

- daily [R1] ok: FULL Sharpe 1.050 >= 0.86
- daily [R2] ok: d vs static-24 on B POST +0.276 (CI [-0.22,+0.74], P 0.12)
- daily [R3] ok: maxDD -24.2% vs static-24 -24.7% (mv TV 0.363; raw -26.5%; plan's quoted av_runs line -24.1%)
- daily [R4] ok: halves vs static-24: H1 +0.182, H2 +0.231
- weekly [R1] ok: FULL Sharpe 0.984 >= 0.82
- weekly [R2] ok: d vs static-24 on B POST +0.286 (CI [-0.23,+0.79], P 0.12)
- weekly [R3] ok: maxDD -16.6% vs static-24 -17.0% (mv TV 0.227; raw -18.2%; plan's quoted av_runs line -16.8%)
- weekly [R4] ok: halves vs static-24: H1 +0.097, H2 +0.296

- Neighbors (information; the research-number pass line in 6.3 has no neighbor clause), same four clauses:
  - UNI-1__age121 daily: fails R3: FULL Sharpe 0.966 >= 0.86; d vs static-24 on B POST +0.147 (CI [-0.31,+0.63], P 0.23); maxDD -25.8% vs static-24 -24.7% (mv TV 0.364; raw -28.1%; plan's quoted av_runs line -24.1%); halves vs static-24: H1 +0.045, H2 +0.231
  - UNI-1__age121 weekly: fails R3, R4: FULL Sharpe 0.912 >= 0.82; d vs static-24 on B POST +0.188 (CI [-0.29,+0.68], P 0.19); maxDD -18.8% vs static-24 -17.0% (mv TV 0.226; raw -20.6%; plan's quoted av_runs line -16.8%); halves vs static-24: H1 -0.029, H2 +0.313
  - UNI-1__quarterly daily: fails R3: FULL Sharpe 1.058 >= 0.86; d vs static-24 on B POST +0.253 (CI [-0.34,+0.77], P 0.19); maxDD -25.1% vs static-24 -24.7% (mv TV 0.379; raw -26.4%; plan's quoted av_runs line -24.1%); halves vs static-24: H1 +0.256, H2 +0.138
  - UNI-1__quarterly weekly: fails R3: FULL Sharpe 0.945 >= 0.82; d vs static-24 on B POST +0.198 (CI [-0.43,+0.78], P 0.24); maxDD -19.0% vs static-24 -17.0% (mv TV 0.238; raw -19.9%; plan's quoted av_runs line -16.8%); halves vs static-24: H1 +0.119, H2 +0.157
  - UNI-1__N12 daily: fails R3: FULL Sharpe 1.004 >= 0.86; d vs static-24 on B POST +0.256 (CI [-0.23,+0.70], P 0.15); maxDD -27.0% vs static-24 -24.7% (mv TV 0.377; raw -28.5%; plan's quoted av_runs line -24.1%); halves vs static-24: H1 +0.182, H2 +0.113
  - UNI-1__N12 weekly: fails R3, R4: FULL Sharpe 0.855 >= 0.82; d vs static-24 on B POST +0.089 (CI [-0.42,+0.57], P 0.34); maxDD -19.5% vs static-24 -17.0% (raw, vol within 5%; raw -19.5%; plan's quoted av_runs line -16.8%); halves vs static-24: H1 +0.110, H2 -0.071
- Raw (not vol-matched) maxDD is worse than static-24 on both books (daily -26.5 % vs -24.7 %, weekly -18.2 % vs -17.0 %); the verdict uses the matched-vol re-run because section 3 makes it the decision line when vol differs > 5 % (daily vol 18.4 % vs 16.7 %, weekly 12.2 % vs 11.0 %). Against the plan's quoted av_runs figures (-24.1 % / -16.8 %) the matched daily line is 0.09 pp worse, the weekly 0.2 pp better.
- Not in any json (6.3 report items, not pass clauses): whole-contract lines at $1,000 / $5,000 with the UNI-5 gate, names changed per reset, delisting events hit (`variants_universe.py report` prints them to stdout; no output was saved). Bw has no A6 stress line and no summary line (harness prints "(no B panel)" for Bw).
- D-0 precondition: D-0.json reproduces the harness static-24 to 0.000 on every window (FULL 0.8512 daily / 0.8101 weekly, = baseline.json B). The 6.0 gate text quotes 0.86 / 0.82 (av_runs/av_universe_9.txt, maxDD -24.1 / -16.8 %); the harness static-24 rounds to 0.85 / 0.81 (maxDD -24.7 / -17.0 %). This 0.01 gap is between the av_runs engine and the T0-verified harness and affects panel B in every cell, not UNI-1 specifically; UNI-1 clears 0.86 / 0.82 either way (1.050 / 0.984). Recorded, not used to fail the cell.

### UNI-2 | class I | target both

**Class I: FAIL** (failing: 1, 3, 4, 6a)

- daily [1] **FAIL**: B POST d +0.093 vs hurdle 0.112 (2.37 sd; 2.49 sd = 0.118; 1.98 sd = 0.094), P 0.012
- daily [2] ok: A POST +0.206, A FULL +0.112, C FULL +0.000; A6 TRIGGERED (gross A +50% B +24% C +0%); stress A POST d +0.208, B POST d +0.093 >= -0.03
- daily [3] **FAIL**: B H1 -0.017, H2 +0.155
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.007): goldcap025 +0.093, MISSING_realistic_cost_1.18+2bps: json MISSING
- daily [5] ok: B FULL DD -23.9% vs -24.0%, worst7 -11.3% vs -11.7% (raw, vol within 5%)
- daily [6a pre-bull Sharpe not below base] **FAIL**: proxy H1 2020-05..2023-12 (window 2020-08-28..2023-12-31 not in json; gold has no weight before 2020-12-27): B+gold -0.017, A+gold -0.047
- daily [6b maxDD not worse] ok: B+gold FULL DD -23.9% vs -24.0% (raw, vol within 5%); report 2024-26 (H2) d +0.155; ex-2025 line not in json (report item)
- weekly [1] **FAIL**: B POST d +0.088 vs hurdle 0.100 (2.37 sd; 2.49 sd = 0.106; 1.98 sd = 0.084), P 0.009
- weekly [2] ok: A POST +0.203, A FULL +0.100, C FULL +0.000; A6 TRIGGERED (gross A +51% B +24% C +0%); stress A POST d +0.205, B POST d +0.090 >= -0.03
- weekly [3] **FAIL**: B H1 -0.017, H2 +0.145
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.012): goldcap025 +0.088, MISSING_realistic_cost_1.18+2bps: json MISSING
- weekly [5] ok: B FULL DD -16.9% vs -17.1%, worst7 -7.3% vs -7.5% (raw, vol within 5%)
- weekly [6a pre-bull Sharpe not below base] **FAIL**: proxy H1 2020-05..2023-12 (window 2020-08-28..2023-12-31 not in json; gold has no weight before 2020-12-27): B+gold -0.017, A+gold -0.047
- weekly [6b maxDD not worse] ok: B+gold FULL DD -16.9% vs -17.1% (raw, vol within 5%); report 2024-26 (H2) d +0.145; ex-2025 line not in json (report item)

- Missing neighbor (b) "realistic cost line 1.18 + 2 bps/side on gold": no json. `variants_p1.UNI-2__goldcost_low` is registered but was never run, and its `_gold_sim(gold_cost_bps)` returns the unmodified simulation (the cost adjustment is not implemented), so running it as-is would not produce the pre-registered line either.
- At the 1.98 hurdle cond 1 would still fail on the daily book (0.093 < 0.094) and pass on the weekly (0.088 >= 0.084); cond 3 (B H1 -0.017 on both books) and the pre-bull extra fail regardless. A+gold vs A: POST +0.21 / +0.20, FULL +0.11 / +0.10, H1 -0.047 / -0.047: the gain is the 2024-26 gold bull the plan's extra condition was written to exclude.

### COST-2 | class II | target D, whole contracts

**Class II: FAIL** (failing: 3, 4, 6a, 6b)

- daily [1] ok: B POST d +0.030 (>= -0.03), CI lo -0.009 (>= -0.10)
- daily [2] ok: A POST +0.029, A FULL +0.015, C FULL +0.034; B H1 +0.005, H2 +0.038 (>= -0.05); A6 not triggered (gross A -2% B -2% C -2%); stress A POST d +0.030, B POST d +0.030
- daily [3] **FAIL**: fees down >=0.20pp AND orders down >=30% vs round-nearest band 0 (A, C whole contracts): A $1000 orders 872->548 (-37%), fees 1.146%->0.958% (-0.189pp) FAIL; A $2500 orders 1083->616 (-43%), fees 1.145%->0.958% (-0.188pp) FAIL; A $5000 orders 1262->660 (-48%), fees 1.145%->0.947% (-0.197pp) FAIL; C $1000 orders 566->366 (-35%), fees 1.076%->0.744% (-0.332pp); C $2500 orders 726->469 (-35%), fees 1.073%->0.903% (-0.170pp) FAIL; C $5000 orders 857->495 (-42%), fees 1.077%->0.918% (-0.159pp) FAIL; B unrounded (information only per plan): turn 13.68->11.00x, fees 1.000%->0.804%
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): m1 d +0.030, op NOT met FAIL, b025 d +0.034, op ok, COST1_F010 d +0.043, op NOT met FAIL, COST1_F020 d +0.046, op NOT met FAIL
- daily [5] ok: B FULL DD -24.6% vs -24.7%, worst7 -11.7% vs -11.8% (raw, vol within 5%)
- daily [6a |d|<=0.08 & CI contains 0, every capital (FULL)] **FAIL**: A $1000 +0.019 [-0.013,+0.057]; A $2500 +0.015 [-0.015,+0.053]; A $5000 +0.018 [-0.015,+0.061]; C $1000 +0.133 [+0.003,+0.292] FAIL; C $2500 +0.051 [-0.012,+0.106]; C $5000 +0.036 [-0.022,+0.091]
- daily [6b same on 2022-23 and 2025-26 windows and vs band-0.10 rounded] **FAIL**: MISSING: capital blocks carry the FULL window only; no paired COST-2 vs D_band10 bootstrap at capital (point Sharpe gaps only, see detail)

- Versus band 0.10 rounded (D_band10.json capital lines; point gaps only, no paired bootstrap exists): A $1000 Sharpe 1.259 vs 1.239 (+0.020), orders 548 vs 549, fees 0.958% vs 1.109%; A $2500 Sharpe 1.259 vs 1.254 (+0.005), orders 616 vs 562, fees 0.958% vs 1.089%; A $5000 Sharpe 1.267 vs 1.253 (+0.014), orders 660 vs 546, fees 0.947% vs 1.075%; C $1000 Sharpe 1.060 vs 0.931 (+0.129), orders 366 vs 427, fees 0.744% vs 1.061%; C $2500 Sharpe 1.020 vs 1.000 (+0.020), orders 469 vs 464, fees 0.903% vs 1.049%; C $5000 Sharpe 1.031 vs 1.008 (+0.024), orders 495 vs 468, fees 0.918% vs 1.036%. C $1,000 is +0.129, outside the 0.08 bound on this comparison too.
- The share of coin-days with B_i > A_i/3 (6.4 "is printed") is not in any json or log.
- A fee cut of 0.189 / 0.188 / 0.197 pp on A ($1,000 / $2,500 / $5,000) misses the 0.20 pp bar; C passes it only at $1,000 (0.332 pp). Orders fall 35-48 % everywhere (the >= 30 % half holds). B unrounded (b|u| buffer, information only) cuts fees 0.196 pp.

### OVL-2 | class I | target both

**Class I: FAIL** (failing: 1, 3, 6b)

- daily [1] **FAIL**: B POST d +0.138 vs hurdle 0.305 (2.37 sd; 2.49 sd = 0.321; 1.98 sd = 0.255), P 0.116
- daily [2] ok: A POST +0.122, A FULL +0.124, C FULL +0.097; A6 not triggered (gross A -15% B -18% C -7%); stress A POST d +0.119, B POST d +0.136
- daily [3] **FAIL**: B H1 -0.125, H2 +0.259
- daily [4] ok: neighbors B POST (>=0 and >= +0.038): 30d40 +0.117, 14d40 +0.120
- daily [5] ok: B FULL DD -20.0% vs -24.7%, worst7 -8.4% vs -11.8% (mv TV 0.523)
- daily [6a maxDD not worse] ok: B FULL DD -20.0% vs -24.7% (mv TV 0.523; raw -15.5%)
- daily [6b CAGR not lower by >1pp] **FAIL**: B FULL CAGR 13.64%->11.30% (-2.33pp)
- daily [6c >=8 binding episodes outside 2021 on B] ok: 88 (variants_overlay.py self-test I7; not a json field)
- weekly [1] **FAIL**: B POST d +0.105 vs hurdle 0.225 (2.37 sd; 2.49 sd = 0.237; 1.98 sd = 0.188), P 0.127
- weekly [2] ok: A POST +0.081, A FULL +0.070, C FULL +0.138; A6 not triggered (gross A -15% B -18% C -7%); stress A POST d +0.078, B POST d +0.103
- weekly [3] **FAIL**: B H1 -0.067, H2 +0.198
- weekly [4] ok: neighbors B POST (>=0 and >= +0.005): 30d40 +0.043, 14d40 +0.075
- weekly [5] ok: B FULL DD -14.8% vs -17.0%, worst7 -7.1% vs -7.6% (mv TV 0.324)
- weekly [6a maxDD not worse] ok: B FULL DD -14.8% vs -17.0% (mv TV 0.324; raw -11.6%)
- weekly [6b CAGR not lower by >1pp] **FAIL**: B FULL CAGR 8.67%->7.13% (-1.54pp)
- weekly [6c >=8 binding episodes outside 2021 on B] ok: 72 (variants_overlay.py self-test I7; not a json field)

- 6c episode counts come from the variants_overlay.py self-test (I7: B daily 88, weekly 72; 30 / 27 from 2022 on, of which 23 coin-runs are one 2024-03/04 cluster). The secondary cell 14d40 is reported, never chosen; 30d40 is the neighbor.
- 6b uses raw FULL CAGR (the cell lowers vol 24 % on B daily; CAGR at matched vol is not in the json).

### OVL-3 | class I | target both

**Class I: FAIL** (failing: 1, 2, 3, 6b)

- daily [1] **FAIL**: B POST d -0.075 vs hurdle 0.125 (2.37 sd; 2.49 sd = 0.132; 1.98 sd = 0.105), P 0.951
- daily [2] **FAIL**: A POST -0.095, A FULL -0.053, C FULL -0.080; A6 not triggered (gross A -10% B -10% C -9%); stress A POST d -0.092, B POST d -0.073
- daily [3] **FAIL**: B H1 -0.029, H2 -0.055
- daily [4] ok: neighbors B POST (>=0 and >= -0.175): none by design
- daily [5] ok: B FULL DD -23.5% vs -24.7%, worst7 -12.0% vs -11.8% (mv TV 0.421)
- daily [6a maxDD not worse] ok: B FULL DD -23.5% vs -24.7% (mv TV 0.421; raw -22.4%)
- daily [6b CAGR not lower by >1pp] **FAIL**: B FULL CAGR 13.64%->12.27% (-1.37pp)
- weekly [1] **FAIL**: B POST d -0.029 vs hurdle 0.107 (2.37 sd; 2.49 sd = 0.112; 1.98 sd = 0.089), P 0.781
- weekly [2] **FAIL**: A POST -0.031, A FULL -0.031, C FULL -0.031; A6 not triggered (gross A -10% B -9% C -9%); stress A POST d -0.029, B POST d -0.028
- weekly [3] **FAIL**: B H1 -0.063, H2 +0.010
- weekly [4] ok: neighbors B POST (>=0 and >= -0.129): none by design
- weekly [5] ok: B FULL DD -16.5% vs -17.0%, worst7 -7.3% vs -7.6% (raw, vol within 5%)
- weekly [6a maxDD not worse] ok: B FULL DD -16.5% vs -17.0% (raw, vol within 5%; raw -16.5%)
- weekly [6b CAGR not lower by >1pp] ok: B FULL CAGR 8.67%->7.91% (-0.76pp)

- Gate flag (variants_overlay.py G1): diagnostics.md opened OVL-3 on the unconditional Correction column; under the cited source's wording (signal on) the gate is closed (+0.61 % / +0.09 %). The cell fails either way. Reported: flips/yr of the target (var vs base) B daily 702.7 vs 569.8, weekly 260.2 vs 208.2; fees/yr B daily 1.06% vs 1.00%, weekly 0.23% vs 0.22%.

### TIME-1 | class I vs W | target T

**Class I: FAIL** (failing: 1, 6b)

- tranche [1] **FAIL**: B POST d +0.176 vs hurdle 0.183 (2.37 sd; 2.49 sd = 0.193; 1.98 sd = 0.153), P 0.009
- tranche [2] ok: A POST +0.158, A FULL +0.119, C FULL +0.272; A6 not triggered (gross A -1% B -2% C +2%); stress A POST d +0.159, B POST d +0.175
- tranche [3] ok: B H1 +0.049, H2 +0.199
- tranche [4] ok: neighbors B POST (>=0 and >= +0.076): K3 +0.196, K5 +0.151, TIME5_partial +0.186, TIME2_signal_smooth +0.147
- tranche [5] ok: B FULL DD -14.3% vs -17.0%, worst7 -7.6% vs -7.6% (raw, vol within 5%)
- tranche [6a within 0.03 of seven-weekday mean (FULL)] ok: A 1.239 vs 1.230 (+0.010); B 0.920 vs 0.895 (+0.025); C 0.976 vs 0.980 (-0.003) | POST info: A 0.818 vs 0.807 (+0.012); B 0.667 vs 0.635 (+0.032); C 0.976 vs 0.980 (-0.003)
- tranche [6b orders/yr <= 350 at $1,000] **FAIL**: A 594 (W 171); C 409 (W 131)
- tranche [6c turnover <= W] ok: A 3.23 vs 3.43x; B 2.87 vs 2.94x; C 2.94 vs 3.24x

- Decomposition the plan requires (section 6.6, FULL Sharpe): total vs W = design-weekday luck (seven-weekday mean - Sunday-candle W) + residual (TIME-1 - seven-weekday mean): A +0.119 = +0.109 + +0.010; B +0.110 = +0.085 + +0.025; C +0.272 = +0.275 + -0.003.
- Control K = 1 (D at TV 0.25 band 10, not a neighbor): B POST Δ vs W +0.105, A FULL +0.132, C +0.307; turnover B 7.99x.
- Whole-contract lines: A $1000 Δ +0.140 [-0.03,+0.31] orders 594 (W 171); A $2500 Δ +0.143 [-0.00,+0.28] orders 774 (W 188); A $5000 Δ +0.118 [-0.03,+0.26] orders 875 (W 191); C $1000 Δ +0.321 [+0.03,+0.68] orders 409 (W 131); C $2500 Δ +0.293 [+0.11,+0.60] orders 547 (W 152); C $5000 Δ +0.293 [+0.14,+0.59] orders 673 (W 159). Orders/yr exceed 350 at every capital on A and at every capital on C.
- At the 1.98 hurdle cond 1 would pass (0.176 >= 0.153, P 0.009); the order cap fails regardless of the hurdle.

### TIME-3 | class I | target both

**Class I: FAIL** (failing: 1, 2, 3, 6a, 6c)

- daily [1] **FAIL**: B POST d +0.059 vs hurdle 0.131 (2.37 sd; 2.49 sd = 0.137; 1.98 sd = 0.109), P 0.131
- daily [2] ok: A POST +0.015, A FULL +0.007, C FULL -0.015; A6 not triggered (gross A -3% B -3% C -4%); stress A POST d +0.016, B POST d +0.059
- daily [3] ok: B H1 +0.031, H2 +0.048
- daily [4] ok: neighbors B POST (>=0 and >= -0.041): all24 +0.057, h0_8_16 +0.028
- daily [5] ok: B FULL DD -23.4% vs -24.7%, worst7 -11.6% vs -11.8% (raw, vol within 5%)
- daily [6a within 0.03 of six-hour mean on A] n/a: n/a on the daily book (the six-hour reference is a W-book line; none exists for D)
- daily [6b no increase in orders/yr (turnover proxy)] ok: A 15.65->12.80x; B 13.68->11.06x; C 14.80->12.10x
- daily [6c no loss on C] **FAIL**: C FULL d -0.015
- weekly [1] **FAIL**: B POST d +0.007 vs hurdle 0.151 (2.37 sd; 2.49 sd = 0.159; 1.98 sd = 0.127), P 0.472
- weekly [2] **FAIL**: A POST -0.052, A FULL -0.010, C FULL +0.037; A6 not triggered (gross A -2% B -2% C -0%); stress A POST d -0.049, B POST d +0.008
- weekly [3] **FAIL**: B H1 -0.068, H2 +0.112
- weekly [4] ok: neighbors B POST (>=0 and >= -0.093): all24 +0.007, h0_8_16 +0.002
- weekly [5] ok: B FULL DD -18.9% vs -17.0%, worst7 -7.5% vs -7.6% (raw, vol within 5%)
- weekly [6a within 0.03 of six-hour mean on A] **FAIL**: A-weekly FULL 1.110 vs six-hour mean 1.21 (plan section 1 value; no reference file) (-0.100)
- weekly [6b no increase in orders/yr (turnover proxy)] ok: A 3.43->3.31x; B 2.94->2.87x; C 3.24->3.20x
- weekly [6c no loss on C] ok: C FULL d +0.037

- Reference lines (section 1, reported next to every timing variant): seven-weekday FULL mean A 1.230 / B 0.895 / C 0.980; this cell's FULL Sharpe (weekly) A 1.110, B 0.816, C 0.741; D at TV 0.25 band 10: A 1.252 / B 0.856 / C 1.011.

### TIME-4 | class I vs W | target W, whole contracts

**Class I: FAIL** (failing: 1, 6c)

- weekly [1] **FAIL**: B POST d +0.159 vs hurdle 0.169 (2.37 sd; 2.49 sd = 0.178; 1.98 sd = 0.141), P 0.005
- weekly [2] ok: A POST +0.127, A FULL +0.125, C FULL +0.249; A6 not triggered (gross A -6% B -7% C -3%); stress A POST d +0.130, B POST d +0.160
- weekly [3] ok: B H1 +0.016, H2 +0.180
- weekly [4] ok: neighbors B POST (>=0 and >= +0.059): mon_fri +0.217, full_gap +0.150
- weekly [5] ok: B FULL DD -15.1% vs -17.0%, worst7 -7.5% vs -7.6% (raw, vol within 5%)
- weekly [6a A-weekly >= 1.17] ok: A FULL 1.246 ($1,000 1.207)
- weekly [6b C >= 0.80] ok: C FULL 0.953 ($1,000 1.139)
- weekly [6c orders/yr <= 220 at $1,000] **FAIL**: A 332 (W 171); C 238 (W 131)
- weekly [6d realized gross within 10% of one-session book] ok: A -5.5%; B -6.6%; C -2.7%

- Reference lines (section 1, reported next to every timing variant): seven-weekday FULL mean A 1.230 / B 0.895 / C 0.980; this cell's FULL Sharpe (weekly) A 1.246, B 0.893, C 0.953; D at TV 0.25 band 10: A 1.252 / B 0.856 / C 1.011.
- Whole-contract: A $1000 orders 332 (W 171) Δ +0.111; A $2500 orders 383 (W 188) Δ +0.105; A $5000 orders 407 (W 191) Δ +0.127; C $1000 orders 238 (W 131) Δ +0.333; C $2500 orders 301 (W 152) Δ +0.202; C $5000 orders 332 (W 159) Δ +0.231. At the 1.98 hurdle cond 1 would pass (0.159 >= 0.141, P 0.005); the 220 order cap fails at every capital on A and at $1,000 / $2,500 / $5,000 on C (238 / 301 / 332).

### COMBO-A | class I vs W | target T, whole contracts

**Class I: FAIL** (failing: 1, 6a, 6b)

- tranche [1] **FAIL**: B POST d +0.123 vs hurdle 0.205 (2.37 sd; 2.49 sd = 0.216; 1.98 sd = 0.172), P 0.073
- tranche [2] ok: A POST +0.129, A FULL +0.075, C FULL +0.189; A6 not triggered (gross A -10% B -10% C -5%); stress A POST d +0.128, B POST d +0.122
- tranche [3] ok: B H1 +0.016, H2 +0.128
- tranche [4] ok: neighbors B POST (>=0 and >= +0.023): no_buffer +0.115, cc60 +0.170
- tranche [5] ok: B FULL DD -15.5% vs -17.0%, worst7 -8.0% vs -7.6% (mv TV 0.278)
- tranche [6a B POST Sharpe >= TIME-1 - 0.03] **FAIL**: 0.614 vs TIME-1 0.667 (-0.053)
- tranche [6b orders/yr <= 0.85 x TIME-1 at $1,000] **FAIL**: A 523 vs 0.85 x 594 = 505; C 347 vs 0.85 x 409 = 348

- Reference lines (section 1, reported next to every timing variant): seven-weekday FULL mean A 1.230 / B 0.895 / C 0.980; this cell's FULL Sharpe (tranche) A 1.196, B 0.871, C 0.893; D at TV 0.25 band 10: A 1.252 / B 0.856 / C 1.011.
- Implementation note (not a verdict change): plan 6.7 says COMBO-A's unrounded line uses the 10 % band, but COMBO-A.json's unrounded rows use the buffer (b|u| = 0.10|u|, sim convention). The plan-literal unrounded line is COMBO-A__no_buffer's (TIME-1 + SZ-1, band 10): B POST Δ +0.115 (sd 0.0867, hurdle 0.205), B POST Sharpe 0.607 vs TIME-1 0.667. Cond 1 and extra 6a fail under either reading.

### COMBO-B | class I/II | target D, whole contracts

**Class I: FAIL** (failing: 1, 2, 3, 4, 5)

- daily [1] **FAIL**: B POST d -0.045 vs hurdle 0.236 (2.37 sd; 2.49 sd = 0.248; 1.98 sd = 0.197), P 0.693
- daily [2] **FAIL**: A POST -0.124, A FULL -0.149, C FULL -0.252; A6 not triggered (gross A -14% B -14% C -9%); stress A POST d -0.127, B POST d -0.046
- daily [3] **FAIL**: B H1 -0.108, H2 -0.035
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.145): no_buffer -0.042 FAIL, cc60 +0.011
- daily [5] **FAIL**: B FULL DD -27.0% vs -24.7%, worst7 -11.8% vs -11.8% (mv TV 0.470)

**Class II: FAIL** (failing: 1, 2, 3, 4, 5)

- daily [1] **FAIL**: B POST d -0.045 (>= -0.03), CI lo -0.248 (>= -0.10)
- daily [2] **FAIL**: A POST -0.124, A FULL -0.149, C FULL -0.252; B H1 -0.108, H2 -0.035 (>= -0.05); A6 not triggered (gross A -14% B -14% C -9%); stress A POST d -0.127, B POST d -0.046
- daily [3] **FAIL**: funding down >=25% AND orders down >=30% vs D round-nearest (A, C rounded): A $1000 orders 872->881 (+1%), fund 3.43%->2.92% (-15%) FAIL; A $2500 orders 1083->1184 (+9%), fund 3.43%->2.88% (-16%) FAIL; A $5000 orders 1262->1363 (+8%), fund 3.43%->2.88% (-16%) FAIL; C $1000 orders 566->651 (+15%), fund 1.90%->1.57% (-17%) FAIL; C $2500 orders 726->956 (+32%), fund 1.87%->1.67% (-11%) FAIL; C $5000 orders 857->1186 (+38%), fund 1.86%->1.67% (-10%) FAIL; B unrounded proxy: turn 13.68->5.34x (-61%), fund 3.13%->2.57% (-18%) FAIL
- daily [4] **FAIL**: neighbors (d >= -0.08 and op gain holds): no_buffer d -0.042, op NOT met FAIL, cc60 d +0.011, op NOT met FAIL
- daily [5] **FAIL**: B FULL DD -27.0% vs -24.7%, worst7 -11.8% vs -11.8% (mv TV 0.470)


### COMBO-C | class I vs W | target T

**Class I: FAIL** (failing: 1, 6a, 6b)

- tranche [1] **FAIL**: B POST d +0.165 vs hurdle 0.184 (2.37 sd; 2.49 sd = 0.193; 1.98 sd = 0.154), P 0.013
- tranche [2] ok: A POST +0.137, A FULL +0.109, C FULL +0.270; A6 not triggered (gross A -4% B -5% C -2%); stress A POST d +0.139, B POST d +0.165
- tranche [3] ok: B H1 +0.043, H2 +0.190
- tranche [4] ok: neighbors B POST (>=0 and >= +0.065): h0_8_16_K7 +0.165, six_K5 +0.156
- tranche [5] ok: B FULL DD -15.0% vs -17.0%, worst7 -8.0% vs -7.6% (mv TV 0.265)
- tranche [6a d vs TIME-1 > 0 on B POST] **FAIL**: B POST Sharpe 0.657 vs TIME-1 0.667 (-0.010; point gap, no paired bootstrap vs TIME-1 in json)
- tranche [6b no panel losing vs TIME-1] **FAIL**: A FULL -0.009; A POST -0.021; B FULL -0.007; B POST -0.010; C FULL -0.002

- Reference lines (section 1, reported next to every timing variant): seven-weekday FULL mean A 1.230 / B 0.895 / C 0.980; this cell's FULL Sharpe (tranche) A 1.230, B 0.913, C 0.974; D at TV 0.25 band 10: A 1.252 / B 0.856 / C 1.011.
- At the 1.98 hurdle cond 1 would pass (0.165 >= 0.154); the cell still fails its own adoption condition (Δ vs TIME-1 alone > 0 on B POST: -0.010, and every panel is below TIME-1), so per 6.7 the answer is "TIME-1 alone".

### SZ-17 | class II (A7) | target both (A/C only)

**Cell rule: FAIL** (failing: 1/2*, 3, 4, 5)

- daily [1/2*] **FAIL**: Sharpe within -0.03 (B n/a by A7): A POST -0.080, A FULL -0.060, C FULL -0.151
- daily [3] **FAIL**: orders/yr down >=15% on rounded lines: A $1000 orders 872->812 (-7%) FAIL; C $1000 orders 566->542 (-4%) FAIL
- daily [4] **FAIL**: neighbors (A POST as the B substitute): COM30 A POST d -0.070, op NOT met, COM90 A POST d -0.091, op NOT met
- daily [5] **FAIL**: matched-vol DD and worst7 no worse (A7 tightens 2pp/1pp to 0): A DD -22.7% vs -21.9%, w7 -9.9% vs -9.5% (mv TV 0.446); C DD -13.9% vs -14.1%, w7 -7.2% vs -7.7% (mv TV 0.435)
- weekly [1/2*] **FAIL**: Sharpe within -0.03 (B n/a by A7): A POST -0.041, A FULL -0.059, C FULL -0.114
- weekly [3] **FAIL**: orders/yr down >=15% on rounded lines: A $1000 orders 171->159 (-7%) FAIL; C $1000 orders 131->120 (-8%) FAIL
- weekly [4] **FAIL**: neighbors (A POST as the B substitute): COM30 A POST d -0.048, op NOT met, COM90 A POST d -0.052, op NOT met
- weekly [5] **FAIL**: matched-vol DD and worst7 no worse (A7 tightens 2pp/1pp to 0): A DD -17.4% vs -16.9%, w7 -7.6% vs -7.4% (mv TV 0.281); C DD -9.5% vs -9.1%, w7 -4.8% vs -4.4% (mv TV 0.271)

- B is not a B result by A7 (the B rows, absent here, would be the nine-coin subset). Neighbor clause read on A POST as the B substitute.

### SIG-13 | class I (A8) | target both (interpreted)

**Class I: FAIL** (failing: 1, 2, 3, 4)

- daily [1] **FAIL**: B POST d -0.036 vs hurdle 0.081 (2.37 sd; 2.49 sd = 0.085; 1.98 sd = 0.067), P 0.831
- daily [2] **FAIL**: A POST -0.027, A FULL -0.068, C FULL -0.108; A6 not triggered (gross A -5% B -4% C -6%); stress A POST d -0.030, B POST d -0.037
- daily [3] **FAIL**: B H1 -0.067, H2 -0.062
- daily [4] **FAIL**: neighbors B POST (>=0 and >= -0.136): sleeve120_only -0.024 FAIL, funding_x2 -0.018 FAIL
- daily [5] ok: B FULL DD -25.4% vs -24.7%, worst7 -11.9% vs -11.8% (mv TV 0.422)
- daily [6 funding/yr not higher] ok: A 3.43%->3.18%; B 3.13%->2.83%; C 1.86%->1.50%
- weekly [1] **FAIL**: B POST d -0.016 vs hurdle 0.092 (2.37 sd; 2.49 sd = 0.097; 1.98 sd = 0.077), P 0.733
- weekly [2] **FAIL**: A POST -0.031, A FULL -0.049, C FULL +0.002; A6 not triggered (gross A -6% B -4% C -5%); stress A POST d -0.034, B POST d -0.017
- weekly [3] **FAIL**: B H1 -0.029, H2 +0.024
- weekly [4] **FAIL**: neighbors B POST (>=0 and >= -0.116): sleeve120_only -0.014 FAIL, funding_x2 -0.019 FAIL
- weekly [5] ok: B FULL DD -16.8% vs -17.0%, worst7 -7.8% vs -7.6% (mv TV 0.265)
- weekly [6 funding/yr not higher] ok: A 2.11%->1.93%; B 1.93%->1.74%; C 1.05%->0.87%

- Target not stated in A8; read as "both" like every other signal cell. A6 stress line for SIG-13 uses archive funding in the signal (variants_signal I11; reporting only, exposure is lower so A6 is not triggered).

## Data and implementation flags found while judging (none changes a verdict)

1. Haircut multiplier: plan A3 states 2.37 for N_eff = 90, but its own Bailey-Lopez de Prado formula gives 2.49 at N = 90 (the harness summary uses 2.49). The decision here uses 2.37 as instructed; nothing clears either.
2. sd_Delta in every json is CI width / 3.92, not the bootstrap stdev section 4 specifies.
3. COMBO-A unrounded rows use the contract buffer instead of the plan's 10 % band (see COMBO-A detail); COMBO-A__no_buffer is the plan-literal unrounded line and also fails.
4. UNI-2 neighbor (b) never ran and its implementation is a no-op (see UNI-2 detail).
5. COST-2 required windows (2022-23, 2025-26) and the paired comparison vs band-0.10 rounded at each capital were not produced; the B_i > A_i/3 share was not printed.
6. D-0 gate figures 0.86 / 0.82 (av_runs) vs harness static-24 0.8512 / 0.8101 (see UNI-1 detail).
7. OVL-3 gate column (G1) and OVL-2 / OVL-3 report items (episodes, flips) live only in variants_overlay.py's self-test text, not in the json.
8. UNI-1 report items (whole-contract lines, names changed, delisting events) were not saved anywhere.



## Correction 2026-10-22: D-0 gate and UNI-1 (from the adversarial verification, uni1_verify/synthesis.md)

The D-0 note above treated the 0.01 gap between the harness static-24 (0.8512 daily / 0.8101 weekly) and the plan's quoted gate (0.86 / 0.82) as an engine difference. It was a data defect: `universe/fetch_all.py` dropped failed downloads silently (DASHUSDT-1d-2022-10 missing), and Binance's monthly files lack 2022-02-26..28 and 2022-04-01..02 for 51 symbols; each gap restarts the 121-close rule. Filling the 71 coin-rows from Binance's own files moves static-24 to 0.860 / 0.819 with maxDD -24.01 % / -16.75 %, which is the plan's gate. On the corrected data UNI-1's daily book fails clause R3 (matched-vol maxDD -24.51 % vs -24.01 %); its target is both books, so **UNI-1 is "do nothing"**, not a research-number pass. Corrected scorecard: daily FULL 1.046 vs 0.860, POST delta +0.256 [-0.24, +0.73] P 0.13; weekly 0.984 vs 0.819, POST +0.273 [-0.24, +0.77] P 0.13.
Every other verdict stands: the variant and baseline arms share the same panel, so the paired deltas are computed on identical data, and every failing cell also fails a condition that does not depend on the panel-B gap (TIME-1 6b, TIME-4 6c, COMBO-C 6b, COST-2 cond 3, the A-panel cond 2 of the signal and sizing cells).
**Final Phase 2 result: no cell passes. The running rule is unchanged; no third paper book.**
