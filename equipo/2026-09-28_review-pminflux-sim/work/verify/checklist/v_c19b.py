# -*- coding: utf-8 -*-
import numpy as np
src = open("v_c19.py", encoding="utf-8").read().split("r0 = (5.0, -5.0)")[0]
exec(src)
r0 = (-5.0, -8.0); T = 2e5*50.0
for ton in (1e5, 1e3):
    sig, crb, n = sigma_fl(r0, lambda: w_interleaved(T, ton, ton), 3000)
    print("(-5,-8) interleaved t=%g ns: sigma_fl %.3e nm CRB %.4f ratio %.2e" % (ton, sig, crb, sig/crb))
sig, crb, n = sigma_fl(r0, lambda: w_sequential(1e5, 1e5, 1e5, 25), 4000)
print("(-5,-8) sequential 25x(4x100us): %.3f nm ratio %.2f" % (sig, sig/crb))
