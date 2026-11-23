"""Run original BLAST on the identical 121-point profiles at nested partitions."""
import csv
import hashlib
import importlib.metadata as md
import inspect
import json
import sys
from pathlib import Path

import numpy as np
from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery
from blast.models.degradation_model import BatteryDegradationModel

HERE = Path(__file__).resolve().parent
FIELDS = ('q', 'qNew', 'qLoss_t', 'qLoss_EFC', 'efc', 'cap_qNew_ah', 'cap_46q_ah')

def profiles():
    t = np.linspace(0, 7200, 121)
    soc = np.where(t <= 3600, 1-t/3600, (t-3600)/3600)
    tr = np.linspace(0, 30*86400, 121)
    return {'rest': (tr, np.full_like(tr, .5), np.full_like(tr, 25.)),
            'cycle': (t, soc, np.full_like(t, 25.)),
            'ramp': (t, soc, np.linspace(20., 30., 121))}

def edges(n):
    indices = [0, 120]
    while len(indices)-1 < n:
        indices = [v for a, b in zip(indices, indices[1:]) for v in (a, (a+b)//2)] + [120]
    assert len(indices) == n+1 and all(b > a for a, b in zip(indices, indices[1:]))
    return indices

def run(profile, n):
    t, soc, temp = profile
    b = Battery()
    bounds = edges(n)
    total_intervals = []
    raw_efc = 0.
    for a, z in zip(bounds, bounds[1:]):
        total_intervals.extend(range(a, z))
        raw_efc += float(np.abs(np.diff(soc[a:z+1])).sum()/2)
        b.update_battery_state(t[a:z+1], soc[a:z+1], temp[a:z+1])
    assert total_intervals == list(range(120))
    assert abs(raw_efc - float(np.abs(np.diff(soc)).sum()/2)) < 1e-12
    assert len(b.states['qLoss_t']) == n+1
    q = float(b.outputs['q'][-1]); qnew = float(b.outputs['qNew'][-1])
    out = {'q': q, 'qNew': qnew, 'qLoss_t': float(b.states['qLoss_t'][-1]),
           'qLoss_EFC': float(b.states['qLoss_EFC'][-1]), 'efc': float(b.stressors['efc'][-1]),
           'cap_qNew_ah': 66*qnew, 'cap_46q_ah': 46*q, 'raw_soc_efc': raw_efc,
           'min_intervals': int(min(np.diff(bounds))), 'max_intervals': int(max(np.diff(bounds))),
           'edges': bounds}
    assert np.isclose(q, 1-out['qLoss_t']-out['qLoss_EFC'], rtol=0, atol=1e-14)
    assert np.isclose(qnew, .7*q, rtol=0, atol=1e-14)
    return out

def main():
    assert md.version('BLAST-Lite') == '1.1.0' and sys.version_info[:3] == (3, 12, 10)
    assert hashlib.sha256(Path(inspect.getfile(Battery)).read_bytes()).hexdigest() == '258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844'
    assert hashlib.sha256(Path(inspect.getfile(BatteryDegradationModel)).read_bytes()).hexdigest() == '1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f'
    previous = json.loads((HERE.parent/'blast_original_probe'/'results.json').read_text(encoding='utf-8'))
    names = {'rest': 'rest', 'cycle': 'cycle', 'ramp': 'cycle_temperature_ramp'}
    rows = []
    for name, profile in profiles().items():
        results = {n: run(profile, n) for n in (1,2,4,8,16,32,64)}
        for n in (1,2):
            reference = previous[names[name] + ('_continuous' if n == 1 else '_two_windows')]['final']
            for key in ('q','qNew','qLoss_t','qLoss_EFC','efc'):
                assert np.isclose(results[n][key], reference[key], rtol=0, atol=1e-14), (name,n,key)
        for n, result in results.items():
            row = {'profile': name, 'windows': n, **result}
            for key in FIELDS:
                for label, base in (('vs_one', results[1][key]), ('vs_64', results[64][key]),
                                    ('vs_previous', results[n//2][key] if n > 1 else None)):
                    delta = None if base is None else result[key]-base
                    row[f'{key}_{label}_signed'] = delta
                    row[f'{key}_{label}_abs'] = None if delta is None else abs(delta)
                    row[f'{key}_{label}_rel'] = None if base is None or base == 0 else delta/abs(base)
            rows.append(row)
    k = 3.25e8*np.exp(-7580/298.15)*np.exp(162*.5/298.15)
    analytic = {'k_cal': float(k), 'qLoss_t': float(k*30**.464), 'q': float(1-k*30**.464)}
    assert abs(rows[0]['q'] - analytic['q']) < 1e-14
    output = {'environment': {'python': sys.version, 'executable': sys.executable,
              'blast_version': md.version('BLAST-Lite'), 'numpy': np.__version__,
              'class_path': inspect.getfile(Battery), 'base_path': inspect.getfile(BatteryDegradationModel)},
              'rest_analytic_constant_stress': analytic, 'rows': rows}
    (HERE/'results.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    with (HERE/'convergence.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    for row in rows:
        print(f"{row['profile']:6} {row['windows']:2} q={row['q']:.10f} qNew={row['qNew']:.10f} loss_t={row['qLoss_t']:.10f} loss_EFC={row['qLoss_EFC']:.10f} efc={row['efc']:.10f} delta_q_prev={row['q_vs_previous_signed']}")
    print('Analytic constant-stress rest:', analytic)

if __name__ == '__main__':
    main()
