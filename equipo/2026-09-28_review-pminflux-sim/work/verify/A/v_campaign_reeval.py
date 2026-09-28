# -*- coding: utf-8 -*-
"""Re-evaluate campaign counts against the deterministic pattern predictor (n_k = Nh q_k) of v_sweep_pred
(the campaign's own 'highest' predictor averaged 4000 multinomial draws -> ~1.7e-4 MC noise in labels)."""
import json, glob
import numpy as np
from scipy import stats
from v_sweep_pred import predict
out = {}
for f in sorted(glob.glob("camp_*.json")):
    d = json.load(open(f)); n = np.array(d["counts_nMINFLUX"]); N = n.sum()
    r = predict(d["lam"], d["Ns"], d["Nb"], d["Mp"], int(d["Ns"]*d["factor"]))
    row = {"rate": d["rate_(Ns+Nb)/Mp"], "N": N}
    for k in ("ideal", "highest", "earliest"):
        p = r[k]; c = float(np.sum((n-N*p)**2/(N*p)))
        row[k] = {"chi2": c, "p": float(stats.chi2.sf(c, 3)), "dev": ((n-N*p)/np.sqrt(N*p*(1-p))).round(2).tolist()}
    row["hi_minus_ideal"] = (r["highest"]-r["ideal"]).tolist()
    se2000 = np.sqrt(r["ideal"]*(1-r["ideal"])/2000); row["max_bias_SE_per_2000"] = float(np.max(np.abs(r["highest"]-r["ideal"])/se2000))
    out[d["tag"]] = row
    print(d["tag"], "rate %.4g N %.3g" % (row["rate"], N), {k: ("%.2f" % row[k]["chi2"], "%.3g" % row[k]["p"]) for k in ("ideal", "highest", "earliest")},
          "hi-id", np.round(row["hi_minus_ideal"], 6), "maxSE2000 %.3f" % row["max_bias_SE_per_2000"])
json.dump(out, open("v_campaign_reeval.json", "w"), indent=1)
