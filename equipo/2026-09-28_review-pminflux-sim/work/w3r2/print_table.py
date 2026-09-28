import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8'))
print(r['source'], r['runtime_s'], r['legacy_crosscheck_pos_MINFLUX'])
print("irf SBR pos | N_win | est: bx±se by±se |b|±se sx sy RMSE2D±se CRB RMSE/CRB±se bnd | legacy asym")
for c in r['cases']:
  for n in ('legacy','mixing','mixing_freebg'):
    m=c['estimators'][n]
    print("%.1f %s %-14s %6.1f %-13s bx %+.3f±%.3f by %+.3f±%.3f |b| %.3f±%.3f sx %.3f sy %.3f rmse %.3f±%.3f crb %.3f r/c %.3f±%.3f bnd %.3f fail %d | asym %.3f crbleg %.3f"%(c['irf_fwhm_ns'],c['sbr_label'],tuple(c['position_nm']),c['n_in_windows_mean'],n,m['bias_x'],m['bias_x_se'],m['bias_y'],m['bias_y_se'],m['bias_abs'],m['bias_abs_se'],m['sigma_x'],m['sigma_y'],m['rmse_2d'],m['rmse_2d_se'],m['crb_axis_nm'],m['rmse_over_crb'],m['rmse_over_crb_se'],m['boundary_fraction'],m['n_failed'],c['legacy_asymptotic_bias_nm'],c['crb_minflux_legacy_axis_nm']))
