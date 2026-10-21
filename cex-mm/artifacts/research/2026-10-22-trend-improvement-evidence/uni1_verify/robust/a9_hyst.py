"""Extra: hysteresis sweep H (incumbent kept while rank <= H), N = 9."""
from common import *
c = ctx()
for name, cad in CADS.items():
    b = run(c, cad, W_of(c, cad, U_static24(c)))
    print(f"\n=== {name}: static-24 FULL {sh(b):.3f} POST {sh(b, POST):.3f}")
    for H in (9, 11, 13, 15, 18, 21, 24, 30, 40, 1000):
        U, lg = membership_custom(c, cad, N=9, H=H); r = run(c, cad, W_of(c, cad, U))
        bt = boot(r, b, POST, None, r)
        print(f"  H={H:4d}: FULL {sh(r):.3f} (d {sh(r)-sh(b):+.3f}) POST {sh(r, POST):.3f} (d {bt[0]:+.3f} [{bt[1]:+.2f},{bt[2]:+.2f}] P {bt[3]:.2f}) | 2022: {','.join(lg[2][1])} | 2025: {','.join(lg[5][1])}")
