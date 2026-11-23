"""Isolated BLAST-Lite API probe; writes results beside this script."""
import hashlib
import importlib.metadata as md
import inspect
import json
import sys
from pathlib import Path

import numpy as np
from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery
from blast.models.degradation_model import BatteryDegradationModel

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))
from bess.aging_capacity import CapacitySnapshot

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def state(b):
    q = float(b.outputs['q'][-1])
    return dict(q=q, qNew=float(b.outputs['qNew'][-1]),
                qLoss_t=float(b.states['qLoss_t'][-1]), qLoss_EFC=float(b.states['qLoss_EFC'][-1]),
                efc=float(b.stressors['efc'][-1]), time_days=float(b.stressors['t_days'][-1]),
                qNew_times_66=66*float(b.outputs['qNew'][-1]), cap2_times_q=46*q,
                k_cal=float(b.rates['k_cal'][-1]))

def run(t, soc, temp, split=None):
    b = Battery()
    if split is None:
        b.update_battery_state(t, soc, temp)
        return {'final': state(b)}
    b.update_battery_state(t[:split+1], soc[:split+1], temp[:split+1])
    mid = state(b)
    b.update_battery_state(t[split:], soc[split:], temp[split:])
    return {'middle': mid, 'final': state(b)}

t = np.linspace(0, 7200, 121)
soc = np.where(t <= 3600, 1-t/3600, (t-3600)/3600)
temp = np.full_like(t, 25.)
rest_t = np.linspace(0, 30*86400, 121)
rest_soc = np.full_like(rest_t, .5)
rest_temp = np.full_like(rest_t, 25.)
cycle = run(t, soc, temp)
split = run(t, soc, temp, 60)
rest = run(rest_t, rest_soc, rest_temp)
rest_split = run(rest_t, rest_soc, rest_temp, 60)
varying_temp = np.linspace(20., 30., len(t))
cycle_varying_temp = run(t, soc, varying_temp)
cycle_varying_temp_split = run(t, soc, varying_temp, 60)
q = cycle['final']['q']; q0 = float(Battery().outputs['q'][0])
snapshots = {}
for initial in (44.1, 43.5):
    snap = CapacitySnapshot(66, initial, q/q0)
    snapshots[str(initial)] = {'q_eff_ah': snap.q_eff_ah, 'soh': snap.soh}

# The boundary below is a separate illustration at nonzero SoC; no profile is rebased.
pre = rest_split['middle']['q'] * 44.1
post = rest_split['final']['q'] * 44.1
s = .5
boundary = {'soc_before': s, 'capacity_before_ah': pre, 'capacity_after_ah': post,
            'hold_soc_stored_ah_before': s*pre, 'hold_soc_stored_ah_after': s*post,
            'hold_charge_soc_after': s*pre/post}

result = {'python': sys.version, 'executable': sys.executable, 'blast_version': md.version('BLAST-Lite'),
          'numpy': np.__version__, 'class_path': inspect.getfile(Battery), 'class_sha256': sha(inspect.getfile(Battery)),
          'base_path': inspect.getfile(BatteryDegradationModel), 'base_sha256': sha(inspect.getfile(BatteryDegradationModel)),
          'initial': {'cap': Battery().cap, 'cap_2ndLife': Battery().cap_2ndLife,
                      'q': float(Battery().outputs['q'][0]), 'qNew': float(Battery().outputs['qNew'][0]),
                      'qNew_times_66': float(Battery().outputs['qNew'][0])*66},
          'profiles': {'rest': '30 days, SoC 0.5, 25 C, 121 equally spaced samples',
                       'cycle': '7200 s, SoC 1 to 0 to 1, 1 h each leg, 25 C, 60 s spacing; C-rate relative to initial available capacity'},
          'rest_continuous': rest, 'rest_two_windows': rest_split,
          'cycle_continuous': cycle, 'cycle_two_windows': split,
          'cycle_temperature_ramp_continuous': cycle_varying_temp,
          'cycle_temperature_ramp_two_windows': cycle_varying_temp_split,
          'hypothetical_snapshots_at_cycle_end': snapshots, 'boundary_illustration': boundary}
assert result['initial']['qNew_times_66'] == 46.199999999999996
assert abs(cycle['final']['efc']-1) < 1e-12
assert split['final']['efc'] < cycle['final']['efc']
assert 0 < q <= 1
Path(__file__).with_name('results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
print(json.dumps(result, indent=2))
