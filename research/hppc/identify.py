"""ORNL HPPC exploratory identification. Run: py -3.13 research/hppc/identify.py"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
SHA256 = '8b4135978f150d465dbd5b83f55f7235b8fbd0c39a91fa9033a65c11622f6bf1'
TRAIN = [0, 1, 3, 4, 6, 7]
TEST = [2, 5, 8, 9]


def events(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Unexpected source bytes; obtain the pinned upstream file')
    d = pd.read_csv(path)
    current = d['Current(A)'].to_numpy()
    starts = np.flatnonzero((current < -25) & np.r_[True, current[:-1] >= -25])
    if len(starts) != 10:
        raise ValueError('Expected ten discharge events')
    t = d['Time(s)'].to_numpy()
    # Trapezoidal throughput is only a relative SoC coordinate; nominal 33.1 Ah.
    dq = np.r_[0, np.cumsum(-0.5 * (current[1:] + current[:-1]) * np.diff(t) / 3600)]
    result = []
    for start in starts:
        end = start
        while end < len(d) and d['Step'].iloc[end] in (6, 7, 8):
            end += 1
        rows = d.iloc[start-1:end]
        if set(rows['Step'].iloc[1:]) != {6, 7, 8}:
            raise ValueError('Unexpected segment sequence')
        result.append(dict(t=rows['Time(s)'].to_numpy(), i=-rows['Current(A)'].to_numpy(),
                           v=rows['Voltage(V)'].to_numpy(), step=rows['Step'].to_numpy(),
                           q=float(dq[start-1])))
    return result


def predict(e, r0, r1, tau, vrc0, slope):
    t, i = e['t'], e['i']
    dt = np.diff(t)
    decay = np.exp(-dt / tau)
    vrc = np.empty(len(t)); vrc[0] = vrc0
    q = np.zeros(len(t))
    for k in range(1, len(t)):
        # Current at the end of each interval approximates the measured input.
        vrc[k] = decay[k-1]*vrc[k-1] + r1*i[k]*(1-decay[k-1])
        q[k] = q[k-1] + i[k]*dt[k-1]/3600
    return e['v'][0] - slope*q - r0*i - vrc + vrc0


def slopes(es, train):
    # Long-rest pre-pulse voltages are quasi-OCV proxies, not equilibrium OCV.
    q = np.array([es[k]['q'] for k in train]); v = np.array([es[k]['v'][0] for k in train])
    order = np.argsort(q); q, v = q[order], v[order]
    s = -np.diff(v)/np.diff(q)
    return np.interp([e['q'] for e in es], (q[1:]+q[:-1])/2, s)


def residual(x, es, ids, slope, discharge=False):
    r0, r1, tau, v0 = x
    return np.concatenate([(predict(es[k], r0, r1, tau, v0, slope[k])-es[k]['v'])[
        (es[k]['step'] == 6) if discharge else np.isin(es[k]['step'], (6, 7, 8))] for k in ids])


def fit(es, ids, slope, discharge=False, v0_fixed=None):
    lo = [0, 0, 1, -0.03]; hi = [.02, .05, 300, .03]
    if v0_fixed is not None:
        lo[3], hi[3] = v0_fixed-1e-12, v0_fixed+1e-12
    return least_squares(residual, [0.0016, .0014, 20, v0_fixed or 0],
                         bounds=(lo, hi), args=(es, ids, slope, discharge),
                         x_scale=[.001, .001, 20, .01], max_nfev=500)


def metrics(es, ids, slope, x):
    result = {}
    for label, step in [('discharge', 6), ('rest', 7), ('regen', 8)]:
        errs = np.concatenate([(predict(es[k], *x, slope[k])-es[k]['v'])[es[k]['step'] == step] for k in ids])
        result[label] = {'n':len(errs), 'rmse_mV':float(np.sqrt(np.mean(errs**2))*1000),
                         'bias_mV':float(np.mean(errs)*1000), 'max_abs_mV':float(np.max(np.abs(errs))*1000)}
    return result


def main():
    es = events(HERE/'source.csv'); slope = slopes(es, TRAIN)
    joint = fit(es, TRAIN, slope)
    # Isolated discharge fits, each constrained to vrc0=0, aggregate median.
    individual = [fit(es, [k], slope, True, 0).x for k in TRAIN]
    isolated = np.median(individual, axis=0); isolated[3] = 0
    out = {'train_pulses':[k+1 for k in TRAIN], 'test_pulses':[k+1 for k in TEST],
           'quasi_ocv_slopes_V_per_Ah':slope.tolist(), 'individual':np.array(individual).tolist()}
    for name, x in [('joint',joint.x), ('isolated',isolated)]:
        out[name] = {'r0_mOhm':x[0]*1000, 'r1_mOhm':x[1]*1000, 'tau_s':x[2],
                     'c1_F':x[2]/x[1], 'vrc0_mV':x[3]*1000,
                     'train':metrics(es,TRAIN,slope,x), 'test':metrics(es,TEST,slope,x),
                     'last_pulse':metrics(es,[9],slope,x)}
    # Historical medians used constant Vpre as OCV and Vrc(0)=0.
    historical = np.array([.001610,.001342,25.22,0.])
    out['historical_approx'] = {'r0_mOhm':1.610,'r1_mOhm':1.342,'tau_s':25.22,
        'c1_F':25.22/.001342,'train':metrics(es,TRAIN,slope*0,historical),
        'test':metrics(es,TEST,slope*0,historical),
        'last_pulse':metrics(es,[9],slope*0,historical)}
    # Sensitivity to assumed common initial polarization and quasi-OCV slope.
    out['sensitivity'] = {}
    for label, ss, v in [('zero_vrc',slope,0),('vrc_plus_5mV',slope,.005),
                         ('slope_zero',slope*0,None),('slope_x2',slope*2,None)]:
        x = fit(es,TRAIN,ss,v0_fixed=v).x
        out['sensitivity'][label] = {'r0_mOhm':x[0]*1000,'r1_mOhm':x[1]*1000,
                                     'tau_s':x[2],'vrc0_mV':x[3]*1000,
                                     'test':metrics(es,TEST,ss,x)}
    # Leave-one-training-pulse-out spread: model/experiment sensitivity, not CI.
    out['leave_one_out'] = [fit(es,[j for j in TRAIN if j!=k],slopes(es,[j for j in TRAIN if j!=k])).x.tolist() for k in TRAIN]
    out['jacobian_singular_values_scaled'] = np.linalg.svd(joint.jac @ np.diag([.001,.001,20,.01]),compute_uv=False).tolist()
    (HERE/'results.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__ == '__main__':
    main()
