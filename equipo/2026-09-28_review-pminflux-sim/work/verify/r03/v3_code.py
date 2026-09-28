# -*- coding: utf-8 -*-
"""(2) New R3 code behaviour: overlap guard, count_windows (vs tags, vs own window rule, vs own C),
t_mask port of F107, converged flag."""
import os, sys, json, math, warnings, time
import numpy as np
from scipy import stats
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.join(HERE, "..", "r02"))
import pminflux_sim as pm
from pminflux_sim import simulate as sim, estimate as es, windows as wn, mixing as mx, psf
from mysim import stream, my_C, my_probs, window_index_periodic, chi2p

out = {}
pos = psf.beam_positions(4, 100.0, center=True)
C = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 10.1, 0.3)
lam = psf.lambda_beams(np.array([5.0, -5.0]), pos, 360.0)


def raises(f):
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            f()
        return "no-raise", [str(x.category.__name__) for x in w]
    except ValueError as e:
        return "ValueError", str(e)[:60]


# ---- guard
g = {}
g["simulate_b20"] = raises(lambda: sim.simulate_counts(lam, 2, 50, 21.0, params=sim.SimParams(b=20.0),
                                                       rng=np.random.default_rng(0)))
g["simulate_b20_allow"] = raises(lambda: sim.simulate_counts(lam, 2, 50, 21.0,
                                 params=sim.SimParams(b=20.0, allow_overlap=True), rng=np.random.default_rng(0)))
g["simulate_b12.5"] = raises(lambda: sim.simulate_counts(lam, 2, 50, 21.0, params=sim.SimParams(b=12.5),
                                                         rng=np.random.default_rng(0)))
g["simulate_b12.5000001"] = raises(lambda: sim.simulate_counts(lam, 2, 50, 21.0, params=sim.SimParams(b=12.5000001),
                                                               rng=np.random.default_rng(0)))
C20 = mx.mixing_matrix(4.21, 50.0, 4, 0.0, 20.0, 0.3)
g["crb_b20"] = raises(lambda: es.crb(np.array([[5.0, -5.0]]), pos, 360.0, C20, 20.0, 50.0, 21.0, 2095))
g["crb_b20_allow"] = raises(lambda: es.crb(np.array([[5.0, -5.0]]), pos, 360.0, C20, 20.0, 50.0, 21.0, 2095,
                                           allow_overlap=True))
cnt = np.array([[500, 500, 500, 500]])
g["mle_b20"] = raises(lambda: es.mle_mixing(cnt, pos, 360.0, C20, 20.0, 50.0, 21.0, 75.0))
g["mle_b20_allow"] = raises(lambda: es.mle_mixing(cnt, pos, 360.0, C20, 20.0, 50.0, 21.0, 75.0, allow_overlap=True))
g["count_b20"] = raises(lambda: wn.count_windows(np.array([1.0, 2.0]), b=20.0))
g["count_b20_allow"] = raises(lambda: wn.count_windows(np.array([1.0, 2.0]), b=20.0, allow_overlap=True))
# entry points NOT guarded (informative)
g["forward_probs_b20"] = raises(lambda: es.forward_probs(np.array([5.0, -5.0]), pos, 360.0, C20, 20.0, 50.0, 21.0))
g["window_probs_b20"] = raises(lambda: mx.window_probs(np.ones(4) / 4, C20, 20.0, 50.0, 2000, 95)
                               if hasattr(mx, "window_probs") else None)
out["guard"] = g
print(json.dumps(g, indent=0, ensure_ascii=True))

# ---- count_windows vs simulate tags, vs own membership rule, in 3 setups
cw = {}
for (a, b, irf, tc) in [(0.0, 10.1, 0.3, "earliest"), (5.0, 10.0, 0.3, "none"), (-0.5, 12.5, 0.0, "highest"),
                        (-3.0, 12.5, 0.3, "earliest")]:
    p = sim.SimParams(a=a, b=b, irf_fwhm=irf, tcspc=tc, rate_per_cycle=0.05)
    counts, tags = sim.simulate_counts(lam, 30, 2000, 21.0, params=p, rng=np.random.default_rng(7), return_tags=True)
    c2 = wn.count_windows(tags["microtime_ns"], a=a, b=b, macro_index=tags["loc"], n_loc=30)
    # own rule on absolute time = cycle*T + micro (tests the t mod T fold)
    tabs = tags["cycle"] * 50.0 + tags["microtime_ns"]
    c3 = wn.count_windows(tabs, a=a, b=b, macro_index=tags["loc"], n_loc=30)
    own = window_index_periodic(tags["microtime_ns"], a, b)
    c4 = np.stack([np.bincount(tags["loc"][own[i]], minlength=30) for i in range(4)], 1)
    cw["a=%g,b=%g,%s" % (a, b, tc)] = dict(tags_eq=bool(np.array_equal(counts, c2)),
                                           abs_time_eq=bool(np.array_equal(c2, c3)),
                                           own_rule_eq=bool(np.array_equal(c2, c4)),
                                           n_photons=int(tags["loc"].size))
# wrap-around and a<0 against explicit intervals on uniform times
rng = np.random.default_rng(3)
t = rng.uniform(-100, 300, 200000)
for (a, b) in [(5.0, 10.0), (-0.5, 12.5), (40.0, 12.5), (0.0, 10.1)]:
    c = wn.count_windows(t, a=a, b=b)
    ref = []
    for i in range(4):
        lo = i * 12.5 + a
        ph = np.mod(t - lo, 50.0)
        ref.append(int(np.sum(ph < b)))
    cw["uniform a=%g b=%g" % (a, b)] = bool(list(c) == ref)
# low-rate chi2 of count_windows on OWN simulator stream vs OWN C
q = np.array(lam) / np.sum(lam)
st = stream(q, 21.0, 1e-4, 4000000000 // 1, np.random.default_rng(11), irf=0.3, d=22.0, tcspc="earliest")
c = wn.count_windows(st["t"])
Cown = my_C(4.21, 0.0, 10.1, 0.3)
pr = my_probs(q, Cown, 10.1, 21.0 / 22.0, 1.0 / 22.0)
chi, pv, z = chi2p(c, pr)
cw["own_stream_1e-4_vs_ownC"] = dict(n=int(c.sum()), chi2=chi, p=pv, z=z.tolist())
# window_probs of package vs own C probs
if hasattr(mx, "window_probs"):
    try:
        wp = np.asarray(mx.window_probs(q, C, 10.1, 50.0, 21.0 / 22.0, 1.0 / 22.0))
        cw["window_probs_vs_own"] = float(np.max(np.abs(wp / wp.sum() - pr)))
    except Exception as e:
        cw["window_probs_vs_own"] = "call failed: %s" % e
out["count_windows"] = cw
print(json.dumps(cw, indent=0))

# ---- t_mask (F107 port)
tmr = {}
M = 1000
masks = {"block_half": np.r_[np.ones(M // 2), np.zeros(M // 2)].astype(int),
         "alternating": np.tile([1, 0], M // 2)}
for mname, tm in masks.items():
    for tc in ("earliest", "highest", "none"):
        for sbr in (np.inf, 5.0):
            p = sim.SimParams(tcspc=tc, rate_per_cycle=2.5e-3)
            counts, tags = sim.simulate_counts(lam, 40, 1000, sbr, params=p, rng=np.random.default_rng(5),
                                               return_tags=True, t_mask=tm)
            off = tm[tags["cycle"] % M] == 0
            sig_off = int(np.sum(off & (tags["source"] >= 0)))
            frac_off = float(off.mean())
            se = math.sqrt(frac_off * (1 - frac_off) / off.size)
            tmr["%s/%s/sbr%s" % (mname, tc, sbr)] = dict(signal_in_off=sig_off, frac_off=frac_off,
                                                          z_vs_1_7=(frac_off - 1 / 7.) / se if sbr == 5.0 else None)
# signal window distribution with mask == without mask (chi2 two-sample)
p = sim.SimParams(rate_per_cycle=2.5e-3)
cA = sim.simulate_counts(lam, 400, 2000, 21.0, params=p, rng=np.random.default_rng(21), t_mask=masks["block_half"]).sum(0)
cB = sim.simulate_counts(lam, 400, 2000, 21.0, params=p, rng=np.random.default_rng(22)).sum(0)
# with mask: on-cycles have SBR 21 but off cycles add bg only -> expected differs; compare with own expectation
Nb_frac_on = 1 / 22.
s_share = (21 / 22.) / (21 / 22. + 2 / 22.)          # signal share of detected photons with half-off mask
pr_mask = my_probs(q, Cown, 10.1, s_share, 1 - s_share)
chiA, pA, zA = chi2p(cA, pr_mask)
chiB, pB, zB = chi2p(cB, my_probs(q, Cown, 10.1, 21 / 22., 1 / 22.))
tmr["masked_counts_vs_own_expectation"] = dict(p=pA, z=zA.tolist())
tmr["unmasked_counts_vs_own_expectation"] = dict(p=pB, z=zB.tolist())
ones = sim.simulate_counts(lam, 20, 500, 21.0, params=p, rng=np.random.default_rng(9), t_mask=np.ones(7, int))
none_ = sim.simulate_counts(lam, 20, 500, 21.0, params=p, rng=np.random.default_rng(9))
tmr["all_ones_equals_no_mask"] = bool(np.array_equal(ones, none_))
out["t_mask"] = tmr
print(json.dumps(tmr, indent=0))

# ---- converged flag
cv = {}
rng = np.random.default_rng(5)
allc, R0 = [], []
for N in (10, 20, 30, 50):
    for _ in range(1500):
        r0 = rng.uniform(-30, 30, 2)
        pr0 = es.forward_probs(r0, pos, 360.0, C, 10.1, 50.0, 21.0)
        capt = es.capture_fraction(r0, pos, 360.0, C, 10.1, 50.0, 21.0)
        allc.append(rng.multinomial(N, np.r_[np.asarray(pr0) * capt, 1 - capt])[:4])
allc = np.array(allc)
t0 = time.time()
res = es.mle_mixing(allc, pos, 360.0, C, 10.1, 50.0, 21.0, 75.0)
cv["n"] = int(allc.shape[0]); cv["n_not_converged"] = int(np.sum(~res.converged))
cv["n_boundary"] = int(np.sum(res.on_boundary))
# own refinement: Nelder-Mead from the returned r on own objective (interior only)
def nll_own(r, c):
    if np.hypot(*r) > 75.0:
        return 1e300
    pp = np.asarray(es.forward_probs(r, pos, 360.0, C, 10.1, 50.0, 21.0))
    return -float(np.sum(c * np.log(pp)))
sel = np.nonzero(res.converged & ~res.on_boundary)[0]
sel = rng.choice(sel, size=min(600, sel.size), replace=False)
moves, dnll = [], []
for i in list(sel) + list(np.nonzero(~res.converged)[0]):
    f0 = nll_own(res.r[i], allc[i])
    rr = minimize(nll_own, res.r[i], args=(allc[i],), method="Nelder-Mead",
                  options=dict(xatol=1e-7, fatol=1e-12, maxiter=4000))
    moves.append(float(np.hypot(*(rr.x - res.r[i])))); dnll.append(f0 - rr.fun)
m = len(sel)
cv["converged_true_sample"] = m
cv["conv_true_max_move_nm"] = max(moves[:m]); cv["conv_true_max_dnll"] = max(dnll[:m])
cv["conv_true_n_move_gt_0.01nm"] = int(np.sum(np.array(moves[:m]) > 0.01))
cv["not_conv_moves_nm"] = moves[m:]; cv["not_conv_dnll"] = dnll[m:]
out["converged"] = cv
print(json.dumps(cv, indent=0))
json.dump(out, open(os.path.join(HERE, "v3_code.json"), "w"), indent=1, default=str)
