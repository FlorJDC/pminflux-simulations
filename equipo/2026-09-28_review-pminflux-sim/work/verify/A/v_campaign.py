# -*- coding: utf-8 -*-
"""Own sim_exp campaign (legacy code called read-only). Counts windows with my own counter AND
with nMINFLUX; tests mixing / naive / 'highest-k' / 'earliest' predictors (my own derivations)."""
import os, sys, json, time, argparse
import numpy as np
from scipy import stats
from multiprocessing import Pool
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."]*5))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
T, K, TAU, A, B = 50.0, 4, 4.21, 0.0, 10.1
TAUS = np.arange(K)*T/K

def Cmat(tau=TAU, a=A, b=B):
    # own closed form: C[i,j] = sum_m P(E in [off+a+mT, off+a+b+mT]), off=(i-j)T/K mod T
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i-j)*T/K) % T
            lo = off + a; hi = off + a + b
            # geometric sum over m>=0 (valid for 0<=lo<hi)
            C[i, j] = (np.exp(-lo/tau) - np.exp(-hi/tau))/(1-np.exp(-T/tau))
    return C

def my_counts(t, a=A, b=B):
    return np.array([np.sum((t > TAUS[i]+a) & (t < TAUS[i]+a+b)) for i in range(K)], float)

def worker(args):
    from tools import tools_simulations as ts
    seed, ncalls, lam, Ns, Nb, Mp, factor = args
    np.random.seed(seed)
    psf = np.asarray(lam, float).reshape(K, 1, 1)
    tot = np.zeros(K); tot2 = np.zeros(K); fails = 0; nzero = 0
    for _ in range(ncalls):
        t, _, f = ts.sim_exp('p_minflux', None, psf, (0, 0), Ns/max(Nb, 1), Ns, Nb, Mp, TAU, factor, T)
        if f: fails += 1; continue
        c1 = ts.nMINFLUX(K, TAUS, t, A, B); c2 = my_counts(t)
        tot += c1; tot2 += c2
    return tot, tot2, fails

def run(lam, Ns, Nb, Mp, factor, ncalls, seed, nproc=7, chunk=None):
    chunk = chunk or max(1, ncalls//(nproc*4))
    jobs = []; left = ncalls; s = seed
    while left > 0:
        n = min(chunk, left); jobs.append((s, n, lam, Ns, Nb, Mp, factor)); left -= n; s += 1
    with Pool(nproc) as p: res = p.map(worker, jobs)
    tot = sum(r[0] for r in res); tot2 = sum(r[1] for r in res); fails = sum(r[2] for r in res)
    return tot, tot2, fails

def label_fracs(lam, Ns, Mp, factor, rule, ndraw=4000, rng=None):
    """Label fraction of surviving signal photons in sim_exp at finite rate (my derivation):
    per beam n_k ~ Multinomial(Nh, q); slot (m,k) occupied w.p. 1-(1-1/M)^{n_k}, independently
    across k given n; cycle keeps highest occupied k ('highest') or earliest-arriving ('earliest').
    Random deletion to Ns keeps label proportions."""
    rng = rng or np.random.default_rng(0)
    q = np.asarray(lam, float)/np.sum(lam); Nh = int(Ns*factor)
    acc = np.zeros(K)
    for _ in range(ndraw):
        n = rng.multinomial(Nh, q); occ = 1-(1-1.0/Mp)**n
        if rule == 'highest':
            w = np.array([occ[k]*np.prod(1-occ[k+1:]) for k in range(K)])
        elif rule == 'ideal':
            w = occ
        acc += w/w.sum()
    return acc/ndraw

def model(frac_sig, Ns, Nb, C):
    E = Ns*C.dot(frac_sig) + Nb*B/T
    return E/E.sum()

def naive(lam, Ns, Nb):
    s = Ns/Nb if Nb > 0 else np.inf; q = np.asarray(lam)/np.sum(lam)
    if np.isinf(s): return q
    return s/(s+1)*q + 1/(s+1)/K

def chi2(n, p):
    N = n.sum(); c = np.sum((n-N*p)**2/(N*p)); return c, stats.chi2.sf(c, K-1), (n-N*p)/np.sqrt(N*p*(1-p))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", default="0.40,0.10,0.20,0.30"); ap.add_argument("--Ns", type=int, default=2000)
    ap.add_argument("--Nb", type=int, default=400); ap.add_argument("--Mp", type=float, default=2e6)
    ap.add_argument("--factor", type=float, default=1.05); ap.add_argument("--ncalls", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=777000); ap.add_argument("--tag", default="main")
    g = ap.parse_args(); lam = [float(x) for x in g.lam.split(",")]; Mp = int(g.Mp)
    t0 = time.time()
    tot, tot2, fails = run(lam, g.Ns, g.Nb, Mp, g.factor, g.ncalls, g.seed)
    C = Cmat(); q = np.array(lam)/np.sum(lam)
    out = {"tag": g.tag, "lam": lam, "Ns": g.Ns, "Nb": g.Nb, "Mp": Mp, "factor": g.factor, "ncalls": g.ncalls,
           "fails": fails, "rate_(Ns+Nb)/Mp": (g.Ns+g.Nb)/Mp, "counts_nMINFLUX": tot.tolist(),
           "counts_own": tot2.tolist(), "N": float(tot.sum()), "seconds": time.time()-t0}
    preds = {"mixing_ideal": model(q, g.Ns, g.Nb, C), "naive": naive(lam, g.Ns, g.Nb),
             "highest": model(label_fracs(lam, g.Ns, Mp, g.factor, 'highest'), g.Ns, g.Nb, C)}
    for k, p in preds.items():
        c, pv, dev = chi2(tot, p)
        out[k] = {"p": p.tolist(), "chi2": c, "pvalue": pv, "dev_se": dev.tolist()}
    out["highest_minus_ideal"] = (preds["highest"]-preds["mixing_ideal"]).tolist()
    print(json.dumps(out, indent=1))
    json.dump(out, open("camp_%s.json" % g.tag, "w"), indent=1)
