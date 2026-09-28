# -*- coding: utf-8 -*-
"""Independent checks of F101-F111 and discarded F105/F151/F153/F154 (legacy called read-only)."""
import os, sys, json, warnings, io, contextlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
sys.path.insert(0, os.path.join(ROOT, "legacy", "p-minflux-main"))
sys.path.insert(0, HERE)
import matplotlib; matplotlib.use("Agg")
from tools import tools_simulations as ts
from v_F104 import donut, q, POS, pn, fisher_crb
warnings.filterwarnings("ignore")
out = {}
K, T = 4, 50.0
TAUS = np.arange(K) * T / K
lam0 = donut(np.hypot(5 - POS[:, 0], -5 - POS[:, 1]))
psf1 = lam0.reshape(K, 1, 1)


def hi_label(occ):
    w = np.array([occ[k] * np.prod(1 - occ[k + 1:]) for k in range(K)])
    return w / w.sum()


# ---- F101 ----
Nh, Mp = 2100, 200000
qq = np.array([0.12, 0.28, 0.35, 0.25])
occ = 1 - (1 - 1 / Mp) ** (Nh * qq)
anyocc = 1 - np.prod(1 - occ)
one = sum(occ[k] * np.prod(np.delete(1 - occ, k)) for k in range(K))
hi = hi_label(occ)
out["F101"] = {"frac_occupied_cycles_ge2beams": (anyocc - one) / anyocc, "hi_label": hi.tolist(),
               "max_rel_diff": float(np.max(np.abs(hi - qq) / qq))}
np.random.seed(101)
tot = np.zeros(K)
for _ in range(60):
    t, _, f = ts.sim_exp('p_minflux', None, qq.reshape(K, 1, 1), (0, 0), 1e9, 1000, 0, 2000, 0.001, 1.0, T)
    if not f:
        tot += ts.nMINFLUX(K, TAUS, t, 0, 12.5)
hih = hi_label(1 - (1 - 1 / 2000.) ** (1000 * qq))
fo = tot / tot.sum(); se = np.sqrt(fo * (1 - fo) / tot.sum())
out["F101"]["high_rate_0.5"] = {"f_obs": fo.tolist(), "pred_highest": hih.tolist(),
                                "z_vs_highest": ((fo - hih) / se).tolist(), "z_vs_p": ((fo - qq) / se).tolist(),
                                "N": float(tot.sum())}

# ---- F102 ----
PSF = np.array([ts.psf(POS[i], 200, 1, [0, 0], d='donut') for i in range(K)])
r0i = ts.spaceToIndex(np.array([5.0, -5.0]), 200, 1)
np.random.seed(102)
res = {}
for a in (0.0, -0.25):
    cnts, errs = [], []
    for _ in range(10):
        t, _, f = ts.sim_exp('p_minflux', None, PSF, r0i, 2000 / 95, 2000, 95, 200000, 0.001, 1.05, T)
        n = ts.nMINFLUX(K, TAUS, t, a, 12.5); cnts.append(n)
        idx = ts.pos_MINFLUX(n, PSF, 2000 / 95, px_nm=1, r_max_nm=75)
        errs.append(np.hypot(*(ts.indexToSpace(idx, 200, 1) - [5, -5])))
    res[str(a)] = {"n_zeros": int(np.sum(t == 0)), "len": int(len(t)), "mean_counts": np.mean(cnts, 0).tolist(),
                   "mean_err_nm": float(np.mean(errs))}
out["F102"] = res

# ---- F103 ----
NG = 500000
tg = (np.arange(NG) + 0.5) * T / NG
qv = lam0 / lam0.sum()


def phase_density(tau):
    return [np.exp(-np.mod(tg - TAUS[j], T) / tau) / tau / (1 - np.exp(-T / tau)) for j in range(K)]


def E_in(mask, dens, Ns=2000, Nb=95):
    return sum(Ns * qv[j] * np.sum(dens[j][mask]) * T / NG for j in range(K)) + Nb * np.sum(mask) / NG


r103 = {}
for tl in (4.21, 0.001):
    dens = phase_density(tl)
    leg0 = E_in((tg > -0.5) & (tg < 12.0), dens)
    per0 = E_in((tg < 12.0) | (tg > 49.5), dens)
    r103[str(tl)] = {"E0_legacy": leg0, "E0_periodic": per0, "lost_pct": 100 * (1 - leg0 / per0)}
np.random.seed(103)
for tl in (4.21, 0.001):
    tt = []
    for _ in range(30):
        t, _, f = ts.sim_exp('p_minflux', None, psf1, (0, 0), 2000 / 95, 2000, 95, 200000, tl, 1.05, T)
        tt.append(t[t > 0])
    t = np.concatenate(tt); n = ts.nMINFLUX(K, TAUS, t, 0, 13.0)
    r103[str(tl)]["double_count_pct_b13"] = 100 * (n.sum() - np.sum(t < 50.5)) / len(t)
    r103[str(tl)]["sum_counts_over_detected_b13"] = float(n.sum() / len(t))
out["F103"] = r103


# ---- F105: sandwich (fixed Ns, Nb) / multinomial CRB, study config ----
def sandwich_ratio(r0, Ns, Nb, h=1e-4):
    s = Ns / Nb; N = Ns + Nb
    p = pn(r0, s); ps = q(r0); pb = np.ones(K) / K
    G = np.array([(pn(r0 + d, s) - pn(r0 - d, s)) / (2 * h) for d in (np.array([h, 0.]), np.array([0., h]))]).T
    W = G / p[:, None]
    J = N * (G.T @ W)
    Cm = N * (np.diag(p) - np.outer(p, p))
    Cf = Ns * (np.diag(ps) - np.outer(ps, ps)) + Nb * (np.diag(pb) - np.outer(pb, pb))
    Ji = np.linalg.inv(J)
    Vm = Ji @ (W.T @ Cm @ W) @ Ji; Vf = Ji @ (W.T @ Cf @ W) @ Ji
    return float(np.sqrt(np.trace(Vf) / np.trace(Vm)))


out["F105"] = {str(r): sandwich_ratio(np.array(r, float), 2000, 95)
               for r in [(5, -5), (-5.07, -7.56), (20, 0), (-15, 15), (0, -30), (0, 0.5), (40, 0)]}

# ---- F106 ----
idx = ts.spaceToIndex(np.array([-5.07, -7.56]), 200, 1)
out["F106"] = {"snap_node_nm": ts.indexToSpace(idx, 200, 1).tolist()}
rng = np.random.default_rng(106)
for r in [(5, -5), (5.4, -5.3)]:
    for N in [2095, 104750]:
        pt = pn(np.array(r, float), 2000 / 95); est = []
        for _ in range(200):
            n = rng.multinomial(N, pt)
            est.append(ts.indexToSpace(ts.pos_MINFLUX(n, PSF, 2000 / 95, px_nm=1, r_max_nm=75), 200, 1))
        est = np.array(est); err = est - np.array(r)
        crb = fisher_crb(lambda x: pn(x, 2000 / 95), np.array(r, float), N)
        out["F106"]["%s_N%d" % (r, N)] = {"rmse_over_crb": float(np.sqrt(np.mean(np.sum(err ** 2, 1)) / 2) / crb),
                                           "crb": crb, "mean_err": err.mean(0).tolist(),
                                           "frac_exact_node": float(np.mean(np.all(est == np.round(np.array(r)), 1)))}

# ---- F107 ----
np.random.seed(107)
mask = np.ones(200000); mask[:100000] = 0
t, absT, f = ts.sim_exp('p_minflux', mask, psf1, (0, 0), 1e9, 2000, 0, 200000, 0.001, 1.05, T)
occ_idx = np.nonzero(t[:200000] > 0)[0]
out["F107"] = {"frac_in_off_half": float(np.mean(occ_idx < 100000)), "failed": int(f)}

# ---- F108 ----
r108 = {}
for phi in [0, 30, 60, 120, 150]:
    ph = np.radians(phi); R = np.array([[np.cos(ph), -np.sin(ph)], [np.sin(ph), np.cos(ph)]])
    cov = R @ np.diag([9.0, 1.0]) @ R.T
    with contextlib.redirect_stdout(io.StringIO()):
        w, h, th = ts.cov_ellipse(cov, nsig=1)
    w, h = float(np.ravel(w)[0]), float(np.ravel(h)[0]); th = float(th)
    major_dir = th if w > h else th + 90          # matplotlib Ellipse: width axis along angle
    r108[phi] = {"w": w, "h": h, "theta": th, "major_axis_error_deg": float(((major_dir - phi + 90) % 180) - 90)}
out["F108"] = r108

# ---- F109 ----
g = ts.psf([0, 0], 800, 1, [0, 0], d='gaussian', donut_fwhm=250)
row = g[400]; above = np.where(row >= 0.5 * row.max())[0]
out["F109"] = {"gauss_fwhm_measured_px": int(above[-1] - above[0] + 1)}
try:
    ts.psf([0, 0], 100, 1, [0, 0], d='sw'); out["F109"]["sw"] = "ok"
except Exception as e:
    out["F109"]["sw"] = repr(e)
for fc in ([0, 0], [20, 20]):
    d = ts.psf([0, 0], 200, 1, fc, d='donut'); iz = np.unravel_index(np.argmin(d), d.shape)
    out["F109"]["zero_index_fov%s" % fc] = [int(iz[0]), int(iz[1])]
    out["F109"]["zero_via_indexToSpace_fov%s" % fc] = ts.indexToSpace(iz, 200, 1).tolist()

# ---- F110 ----
pt = pn(np.array([5.0, -5.0]), 1e12)
out["F110"] = {}
for s in (np.inf, 1e12):
    idx = ts.pos_MINFLUX(1000 * pt, PSF, s, px_nm=1, r_max_nm=75)
    crb = ts.crb_minflux(K, PSF, s, 1, 200, 1000, method='1')
    out["F110"][str(s)] = {"est": ts.indexToSpace(idx, 200, 1).tolist(), "crb_all_nan": bool(np.all(np.isnan(crb)))}

# ---- F111 ----
out["F111"] = {}
for Kx in (4, 5, 7):
    for c in (True, False):
        try:
            ts.ebp_centres(Kx, 100, c); out["F111"]["K%d_center%s" % (Kx, c)] = "ok"
        except Exception as e:
            out["F111"]["K%d_center%s" % (Kx, c)] = repr(e)
b4 = ts.beams(4, 100, True, 'donut')
out["F111"]["max_diff_vs_beams"] = float(np.max(np.abs(np.array([b4[i] for i in range(4)]) - ts.ebp_centres(4, 100, True))))

# ---- F151 ----
crbmap = ts.crb_minflux(K, PSF, 2000 / 95, 1, 200, 2095, method='1')
r151 = {}
for r in [(5, -5), (20, 0), (-15, 15), (0, -30)]:
    ii = ts.spaceToIndex(np.array(r, float), 200, 1)
    r151[str(r)] = [float(crbmap[ii[0], ii[1]]), fisher_crb(lambda x: pn(x, 2000 / 95), np.array(r, float), 2095)]
out["F151"] = r151

# ---- F153 ----
rng = np.random.default_rng(153); bad = 0
for _ in range(20):
    r = np.round(rng.uniform(-60, 60, 2), 2)
    d = ts.psf(r, 200, 1, [0, 0], d='donut'); iz = np.array(np.unravel_index(np.argmin(d), d.shape))
    bad += int(np.any(iz != ts.spaceToIndex(r, 200, 1)))
out["F153"] = {"mismatches_of_20": bad}

# ---- F154 ----
try:
    ts.sim_exp('cw_minflux', None, psf1, (0, 0), 1e9, 200, 0, 200001, 1.0, 1.05, T); out["F154"] = "no error"
except Exception as e:
    out["F154"] = repr(e)

print(json.dumps(out, indent=1, default=str))
json.dump(out, open(os.path.join(HERE, "v_findings.json"), "w"), indent=1, default=str)
