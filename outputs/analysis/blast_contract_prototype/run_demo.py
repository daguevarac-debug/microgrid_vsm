"""Exercise the real BLAST API with prior history, preserving one instance."""
from dataclasses import asdict
import hashlib
import importlib.metadata as md
import inspect
import json
from pathlib import Path
import sys
import numpy as np
from blast.models.degradation_model import BatteryDegradationModel
from prototype import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery, ResearchContract, boundary

assert sys.version_info[:3] == (3, 12, 10) and md.version('BLAST-Lite') == '1.1.0'
for cls, expected in ((Battery, '258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844'),
                      (BatteryDegradationModel, '1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f')):
    assert hashlib.sha256(Path(inspect.getfile(cls)).read_bytes()).hexdigest() == expected

result = {'python': sys.version, 'blast': md.version('BLAST-Lite'), 'numpy': np.__version__,
          'class_path': inspect.getfile(Battery), 'base_path': inspect.getfile(BatteryDegradationModel),
          'experiment': '15 days at SoC 1 and 25 C; then 1 to 0 to 1 in two 1-hour windows at 25 C',
          'cases': {}}
for initial in (44.1, 43.5):
    b = Battery(); t0 = 15*86400
    b.update_battery_state(np.linspace(0,t0,61), np.ones(61), np.full(61,25.))
    c = ResearchContract(b, initial, assume_relative_transfer=True)
    start = c.read()
    b.update_battery_state(np.linspace(t0,t0+3600,61), np.linspace(1,0,61), np.full(61,25.))
    middle = c.read()
    b.update_battery_state(np.linspace(t0+3600,t0+7200,61), np.linspace(0,1,61), np.full(61,25.))
    end = c.read()
    result['cases'][str(initial)] = {'start': asdict(start), 'middle': asdict(middle), 'end': asdict(end),
        'boundary_soc_05': {p: asdict(boundary(.5, start.capacity.q_eff_ah, end.capacity.q_eff_ah, policy=p))
                            for p in ('fractional_soc','algebraic_charge')},
        'boundary_soc_09': {p: asdict(boundary(.9, start.capacity.q_eff_ah, end.capacity.q_eff_ah, policy=p))
                            for p in ('fractional_soc','algebraic_charge')}}

Path(__file__).with_name('results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
print(json.dumps(result, indent=2))
