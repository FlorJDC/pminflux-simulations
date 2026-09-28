# -*- coding: utf-8 -*-
import numpy as np
exec(open("v_c03b.py", encoding="utf-8").read().split("res_full, res_frozen")[0])
for ang in (90., 210.):
    t = np.radians(ang)
    for rr in [30, 40, 44, 46, 47, 48, 49, 50, 51, 51.6]:
        x, y = rr*np.cos(t), rr*np.sin(t); Sr = I_all(x, y).sum()/S0; Nr = Ns+Ns/(SBR*Sr)
        cf = crb(pf_fixed(SBR), x, y, N)
        for h in (1e-3, 1e-5):
            pass
        print("ang %3.0f r=%5.1f  CRBfix %.4f  full %.4f (h=1e-5: %.4f) frozen %.4f" % (ang, rr, cf, crb(pconst, x, y, Nr)/cf, crb(pconst, x, y, Nr, h=1e-5)/crb(pf_fixed(SBR), x, y, N, h=1e-5), crb(pf_fixed(SBR*Sr), x, y, Nr)/cf))
