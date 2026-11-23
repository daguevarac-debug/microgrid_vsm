"""BLAST-Lite subprocess: original model only, one instance for its lifetime."""
import copy
import hashlib
import importlib.metadata
import inspect
import json
import sys

import numpy as np
from blast.models.degradation_model import BatteryDegradationModel
from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery


def main():
    if sys.version_info[:3] != (3, 12, 10) or importlib.metadata.version('BLAST-Lite') != '1.1.0':
        raise RuntimeError('BLAST worker requires Python 3.12.10 and BLAST-Lite 1.1.0')
    for cls, digest in ((Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery, '258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844'),
                        (BatteryDegradationModel, '1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f')):
        if hashlib.sha256(open(inspect.getfile(cls), 'rb').read()).hexdigest() != digest:
            raise RuntimeError('BLAST source differs from the audited implementation')
    b = Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery()
    q0 = float(b.outputs['q'][-1])
    print(json.dumps({'ready': True, 'q0': q0, 'cap': b.cap, 'cap_2ndLife': b.cap_2ndLife,
                      'qNew0': float(b.outputs['qNew'][-1])}), flush=True)
    for line in sys.stdin:
        backup = None
        try:
            request = json.loads(line)
            if request.get('action') == 'anchor_case':
                q0 = float(b.outputs['q'][-1])
                print(json.dumps({'q0': q0, 'efc': float(b.stressors['efc'][-1]),
                                  'windows': len(b.outputs['q'])-1}), flush=True)
                continue
            backup = copy.deepcopy(b)
            b.update_battery_state(np.asarray(request['time_s'], dtype=float),
                np.asarray(request['soc'], dtype=float), np.asarray(request['temperature_c'], dtype=float))
            q = float(b.outputs['q'][-1]); efc = float(b.stressors['efc'][-1])
            if not (np.isfinite(q) and 0 < q <= float(backup.outputs['q'][-1]) and
                    np.isfinite(efc) and efc >= float(backup.stressors['efc'][-1])):
                raise ValueError('invalid BLAST capacity or EFC')
            if request['initial_ah'] * q / q0 / 66 < request['soh_min']:
                raise ValueError('snapshot below configured SoH limit')
            response = {'q': q, 'qNew': float(b.outputs['qNew'][-1]),
                'qLoss_t': float(b.states['qLoss_t'][-1]), 'qLoss_EFC': float(b.states['qLoss_EFC'][-1]),
                'efc': efc, 't_days': float(b.stressors['t_days'][-1]), 'q0': q0,
                'windows': len(b.outputs['q'])-1}
            print(json.dumps(response, allow_nan=False), flush=True)
        except Exception as exc:
            if backup is not None:
                b = backup
            print(json.dumps({'error': str(exc)}), flush=True)


if __name__ == '__main__':
    main()
