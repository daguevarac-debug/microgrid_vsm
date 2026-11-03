"""Preregistered comparison; outputs comparison_results.json, not the baseline model."""
import json
import sys
import numpy as np
import scipy
from scipy.optimize import least_squares
from identify import HERE, TRAIN, events, slopes

PHASES = {'discharge': 6, 'rest': 7, 'regen': 8}
GROUPS = {'train': TRAIN, 'test_3_6_9': [2, 5, 8], 'test_10': [9]}
BOUNDS = {
    '1rc': ([.05,.05,1.,-30.], [20.,20.,300.,30.]),
    'variable': ([.05,.05,1.,-30.,-.7,-.7,-.7], [20.,20.,300.,30.,.7,.7,.7]),
    '2rc': ([.05,.05,.05,1.,1.,-30.], [20.,20.,20.,30.,270.,30.]),
}
STARTS = {
    '1rc': [[1.6,1.1,23.,-5.]],
    'variable': [[1.6,1.1,23.,-5.,0.,0.,0.]],
    '2rc': [[1.5,.5,1.,3.,25.,-5.], [1.7,1.,.5,10.,70.,0.],
            [1.2,.3,1.5,1.5,150.,5.], [1.8,1.5,.3,25.,10.,-10.]],
}


def coordinate(es, ids):
    values = np.array([es[k]['q'] for k in ids])
    return (values.min()+values.max())/2, (values.max()-values.min())/2


def response(current, dt, resistance, tau, initial):
    """Exact ZOH recurrence, using cumulative products within an 80 s window."""
    decay = np.exp(-dt/tau)
    product = np.cumprod(decay)
    increments = resistance * current * (1-decay)
    return np.r_[initial, product*(initial + np.cumsum(increments/product))]


def prediction(e, model, x, slope, center, span):
    dt = np.diff(e['t']); i = e['i'][1:]
    charge = np.r_[0.,np.cumsum(i*dt/3600)]
    if model == 'variable':
        z = np.clip((e['q']+charge-center)/span,-1,1)
        r0 = x[0]*np.exp(x[4]*z)
        r1 = x[1]*np.exp(x[5]*z[1:])
        tau = x[2]*np.exp(x[6]*z[1:])
        states = response(i,dt,r1/1000,tau,x[3]/1000)
        initial = x[3]/1000
    elif model == '1rc':
        r0 = x[0]
        initial = x[3]/1000
        states = response(i,dt,x[1]/1000,x[2],initial)
    elif model == '2rc':
        r0 = x[0]
        initial = x[5]/1000
        first = initial*x[1]/(x[1]+x[2])
        states = (response(i,dt,x[1]/1000,x[3],first) +
                  response(i,dt,x[2]/1000,x[3]+x[4],initial-first))
    else:
        raise ValueError(model)
    return e['v'][0] - slope*charge - r0*np.asarray(e['i'])/1000 - states + initial


def objective(x, model, es, ids, slope, center, span):
    parts = []
    for k in ids:
        error = prediction(es[k],model,x,slope[k],center,span)-es[k]['v']
        for phase in PHASES.values():
            selected = error[es[k]['step'] == phase]
            if not len(selected):
                raise ValueError('Missing phase')
            parts.append(selected/np.sqrt(len(selected)*len(ids)*3))
    if model == 'variable':
        parts.append(.002*np.asarray(x[4:7]))
    return np.concatenate(parts)


def fit(model, es, ids, slope, fixed_v0=None):
    center, span = coordinate(es,ids)
    lo, hi = [np.array(v,dtype=float) for v in BOUNDS[model]]
    v_index = 5 if model == '2rc' else 3
    if fixed_v0 is not None:
        lo[v_index],hi[v_index] = fixed_v0-1e-9,fixed_v0+1e-9
    attempts = []
    for start in STARTS[model]:
        x0=np.array(start,dtype=float)
        if fixed_v0 is not None: x0[v_index]=fixed_v0
        fit_result=least_squares(objective,x0,bounds=(lo,hi),
            args=(model,es,ids,slope,center,span),x_scale='jac',max_nfev=500,
            ftol=1e-9,xtol=1e-9,gtol=1e-9)
        attempts.append({'x':fit_result.x.tolist(),'cost':float(2*fit_result.cost),
                         'success':bool(fit_result.success),'nfev':int(fit_result.nfev),
                         'active_mask':fit_result.active_mask.tolist()})
    valid = [a for a in attempts if a['success']]
    if not valid: raise RuntimeError(f'No converged fit for {model}')
    best=min(valid,key=lambda a:a['cost'])
    return {'parameters':best['x'], 'cost':best['cost'], 'active_mask':best['active_mask'],
            'center_Ah':center,'span_Ah':span,'starts':attempts}


def error_metrics(error):
    e=np.asarray(error)*1000
    return {'n':len(e),'rmse_mV':float(np.sqrt(np.mean(e*e))),
            'mae_mV':float(np.mean(np.abs(e))), 'bias_mV':float(np.mean(e)),
            'max_abs_mV':float(np.max(np.abs(e)))}


def physical_parameters(model, x, z=0.):
    if model == 'variable':
        r0=x[0]*np.exp(x[4]*z); r1=x[1]*np.exp(x[5]*z); tau=x[2]*np.exp(x[6]*z)
    else:
        r0,r1=x[0],x[1]; tau=x[3] if model=='2rc' else x[2]
    result={'r0_mOhm':float(r0),'r1_mOhm':float(r1),'tau1_s':float(tau),
            'c1_F':float(tau/(r1/1000))}
    if model=='2rc':
        tau2=x[3]+x[4]
        result.update(r2_mOhm=x[2],tau2_s=tau2,c2_F=tau2/(x[2]/1000))
    return result


def evaluate(model, fitted, es, ids, slope):
    by_phase={name:[] for name in PHASES}; by_pulse={}
    for k in ids:
        error=prediction(es[k],model,fitted['parameters'],slope[k],
                         fitted['center_Ah'],fitted['span_Ah'])-es[k]['v']
        by_pulse[str(k+1)]={}
        for name,step in PHASES.items():
            part=error[es[k]['step']==step]; by_phase[name].extend(part)
            by_pulse[str(k+1)][name]=error_metrics(part)
    indicator=np.sqrt(np.mean([p['rmse_mV']**2 for pulse in by_pulse.values() for p in pulse.values()]))
    return {'indicator_mV':float(indicator),
            'phases':{name:error_metrics(v) for name,v in by_phase.items()},'pulses':by_pulse}


def main():
    es=events(HERE/'source.csv'); baseline_slopes=slopes(es,TRAIN)
    output={'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
            'groups':{name:[i+1 for i in ids] for name,ids in GROUPS.items()},'models':{}}
    for model in BOUNDS:
        fitted=fit(model,es,TRAIN,baseline_slopes)
        result={'fit':fitted,'metrics':{name:evaluate(model,fitted,es,ids,baseline_slopes)
                                      for name,ids in GROUPS.items()},'sensitivity':{},'leave_one_out':{},
                'physical_at_center':physical_parameters(model,fitted['parameters']),
                'physical_by_pulse':{str(k+1):physical_parameters(model,fitted['parameters'],
                   np.clip((es[k]['q']-fitted['center_Ah'])/fitted['span_Ah'],-1,1)) for k in range(len(es))}}
        for name,scale,fixed in [('ocv_zero',0,None),('ocv_double',2,None),
                                 ('v0_zero',1,0),('v0_plus_5mV',1,5)]:
            s=baseline_slopes*scale
            f=fit(model,es,TRAIN,s,fixed)
            result['sensitivity'][name]={'fit':f,'metrics':{group:evaluate(model,f,es,ids,s)
                                                           for group,ids in GROUPS.items()}}
        for omitted in TRAIN:
            ids=[j for j in TRAIN if j!=omitted]; s=slopes(es,ids)
            f=fit(model,es,ids,s)
            result['leave_one_out'][str(omitted+1)]={'fit':f,
                'omitted':evaluate(model,f,es,[omitted],s)}
        output['models'][model]=result
        print(model, 'complete',flush=True)
    (HERE/'comparison_results.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__': main()
