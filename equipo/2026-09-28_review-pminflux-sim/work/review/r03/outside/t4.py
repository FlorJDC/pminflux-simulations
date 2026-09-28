import numpy as np, pminflux_sim as pm, warnings
cw = pm.count_windows
# bordes
print(cw([0.0, 10.1, 12.5, 22.6, 49.999999], b=10.1))       # esperado [1,1,0,0]? 0.0 en w0, 10.1 fuera, 12.5 en w1, 22.6 fuera
print(cw([0.0, 12.5, 25, 37.5, 49.99999], b=12.5))           # b=T/K: [1,1,1,2]
# micro = -1e-17 / a - tiny
print("a-tiny", cw([np.nextafter(0.5,0)], a=0.5, b=12.5), cw([-1e-17], a=0.0, b=12.5), cw([50-1e-15], a=0.0, b=12.5))
# absolutos
rng=np.random.default_rng(0); micro=rng.uniform(0,50,100000); macro=rng.integers(0,2**40//50,100000)
absn = macro*50.0 + micro
print("abs == micro", np.array_equal(cw(absn,b=10.1), cw(micro,b=10.1)), (cw(absn,b=10.1)-cw(micro,b=10.1)))
macro2=rng.integers(0,2**52//50,100000); print("abs huge", cw(macro2*50.0+micro,b=10.1)-cw(micro,b=10.1))
# macro_index float
print(cw([1.,2.,13.], macro_index=np.array([0.,1.,1.])))
try: cw([1.,2.], macro_index=np.array([0.,np.nan]))
except Exception as e: print(type(e).__name__, e)
# vs nMINFLUX (legacy) para photons interiores
import sys; sys.path.insert(0, r"C:\Users\BANGHO\Documents\GithubPRO\pminflux-sim-v2\legacy\p-minflux-main")
from tools import tools_simulations as ts
t = rng.uniform(0,50,20000); tau = np.arange(4)*12.5
print("nMINFLUX", ts.nMINFLUX(4,tau,t,0.0,10.1), cw(t, b=10.1))
print("nMINFLUX a=-1", ts.nMINFLUX(4,tau,t,-1.0,10.1), cw(t, a=-1.0, b=10.1))
# n_loc sin macro_index ignorado
print(cw([1.,2.], n_loc=5))
# b = T/K + tiny numeric
print(cw([1.], T=50, K=3, b=50/3))
# stacklevel
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always"); cw([1.], b=20, allow_overlap=True); print(w[0].filename, w[0].lineno)
