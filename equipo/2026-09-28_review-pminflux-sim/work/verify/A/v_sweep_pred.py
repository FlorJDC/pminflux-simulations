# -*- coding: utf-8 -*-
"""Own finite-rate predictors via occupancy-pattern decomposition (n_k = Nh q_k):
'highest' (sim_exp overwrite) and 'earliest' (first-photon TCSPC, raw time 12.5k+E, then fold).
Compare with W1's numbers in results/mixing_rate_sweep.json."""
import itertools, json, os
import numpy as np
from scipy import stats, optimize
T, K, TAU, B = 50.0, 4, 4.21, 10.1
TAUS = np.arange(K) * T / K
rng = np.random.default_rng(5)


def Cmat(tau=TAU, a=0.0, b=B):
    C = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            off = ((i - j) * T / K) % T
            C[i, j] = (np.exp(-(off + a) / tau) - np.exp(-(off + a + b) / tau)) / (1 - np.exp(-T / tau))
    return C


def win_of(t, b=B):
    ph = np.mod(t, T)
    w = np.full(len(t), -1)
    for i in range(K):
        w[(ph > TAUS[i]) & (ph < TAUS[i] + b)] = i
    return w


def predict(lam, Ns, Nb, Mp, Nh, tau=TAU, b=B, nmc=400000):
    q = np.asarray(lam, float) / np.sum(lam)
    occ = 1 - (1 - 1.0 / Mp) ** (Nh * q)
    C = Cmat(tau, 0, b)
    acc = {"highest": np.zeros(K), "earliest": np.zeros(K), "ideal": np.zeros(K)}
    Pany = 0.0
    for r in range(1, K + 1):
        for S in itertools.combinations(range(K), r):
            P = np.prod([occ[k] if k in S else 1 - occ[k] for k in range(K)])
            Pany += P
            acc["highest"] += P * C[:, max(S)]
            if r == 1:
                acc["earliest"] += P * C[:, S[0]]
            else:
                E = rng.exponential(tau, (nmc, r)) + TAUS[list(S)]
                w = win_of(E.min(1), b)
                acc["earliest"] += P * np.array([np.mean(w == i) for i in range(K)])
    ideal_sig = C.dot(q)
    res = {}
    for k in ("highest", "earliest"):
        Es = Ns * acc[k] / Pany + Nb * b / T
        res[k] = Es / Es.sum()
    Ei = Ns * ideal_sig + Nb * b / T
    res["ideal"] = Ei / Ei.sum()
    ge2 = 1 - sum(occ[k] * np.prod(np.delete(1 - occ, k)) for k in range(K)) / Pany
    res["frac_occ_ge2"] = ge2
    return res


if __name__ == "__main__":
    lam = [0.12, 0.28, 0.35, 0.25]
    w1 = json.load(open(os.path.join(os.path.dirname(__file__), *[".."] * 5, "results", "mixing_rate_sweep.json")))
    out = {}
    rows = [(p["Ns"], p["Nb"], p["M_p"], p["Nh"], p["rate_per_cycle"], p) for p in w1["points"]]
    sc = w1["studies_config"]["with_leak_tau4.21_b10.1"]
    rows.append((2000, 95, 200000, 2100, 0.0105, sc))
    for Ns, Nb, Mp, Nh, rate, p in rows:
        r = predict(lam, Ns, Nb, Mp, Nh)
        hm = r["highest"] - r["ideal"]; em = r["earliest"] - r["ideal"]
        out[str(rate)] = {"hi_minus_mix": hm.tolist(), "ea_minus_mix": em.tolist(), "ge2": r["frac_occ_ge2"],
                          "W1_hi_minus_mix": p["pred_highest_minus_mixing_abs"], "W1_ea_minus_mix": p["pred_earliest_minus_mixing_abs"]}
        print("rate %.4g ge2 %.3g (W1 %.3g)" % (rate, r["frac_occ_ge2"], p["frac_occupied_cycles_with_ge2_beams"]))
        print("   hi-mix mine", np.round(hm, 6), " W1", np.round(p["pred_highest_minus_mixing_abs"], 6))
        print("   ea-mix mine", np.round(em, 6), " W1", np.round(p["pred_earliest_minus_mixing_abs"], 6))
        # per-localisation size (2000 photons) in SE
        pm = r["ideal"]; se2000 = np.sqrt(pm * (1 - pm) / 2000)
        print("   |hi-mix|/SE(2000) max %.3f" % np.max(np.abs(hm) / se2000))
    # noncentrality for 50% power at alpha=1e-3, 3 dof
    c = stats.chi2.ppf(1 - 1e-3, 3)
    lamnc = optimize.brentq(lambda L: stats.ncx2.sf(c, 3, L) - 0.5, 1, 100)
    print("noncentrality", lamnc)
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "v_sweep_pred.json"), "w"), indent=1)
