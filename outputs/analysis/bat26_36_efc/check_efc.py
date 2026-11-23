"""Synthetic BAT26-36 accounting checks against the actual BESS and BLAST APIs."""
import hashlib
import importlib.metadata as metadata
import inspect
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.integrate import solve_ivp
from blast.models.degradation_model import BatteryDegradationModel
from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from bess.aging_capacity import CapacitySnapshot
from bess.blast_lite_adapter import preserve_window_state
from bess.model import SecondLifeBattery1RC

CASES = {
    # Current is constant on each one-hour interval, positive for discharge.
    'reposo': (.5, [0.], [44.1]),
    'descarga_80pct': (.9, [35.28], [44.1]),
    'carga_80pct': (.1, [-35.28], [44.1]),
    'ciclo_completo': (1., [44.1, -44.1], [44.1, 44.1]),
    'ciclo_parcial': (.7, [17.64, -17.64], [44.1, 44.1]),
    'capacidad_variable': (.9, [17.64, -15.876], [44.1, 39.69]),
}

def simulate(case, parts=1):
    soc, currents, capacities = case
    model = Battery()
    initial_ah = 44.1
    throughput = efc_initial = efc_variable = 0.
    qstart = []
    q_end = []
    delta_efc = []
    time = 0.
    for current, capacity in zip(currents, capacities):
        # Every boundary holds fractional SoC; the physical intervals alone contribute Ah.
        for _ in range(parts):
            duration = 3600./parts
            t = np.linspace(time, time+duration, 61)
            end_soc = soc-current*duration/(3600*capacity)
            s = np.linspace(soc, end_soc, len(t))
            assert np.min(s) >= -1e-12 and np.max(s) <= 1+1e-12
            qstart.append(float(model.outputs['q'][-1]))
            before = float(model.stressors['efc'][-1])
            model.update_battery_state(t, s, np.full_like(t, 25.))
            q_end.append(float(model.outputs['q'][-1]))
            delta_efc.append(float(model.stressors['efc'][-1])-before)
            ah = abs(current)*duration/3600.
            throughput += ah
            efc_initial += ah/(2*initial_ah)
            efc_variable += ah/(2*capacity)
            soc = end_soc
            time += duration
    return {'throughput_ah': throughput, 'efc_initial': efc_initial, 'efc_variable': efc_variable,
            'efc_blast': float(model.stressors['efc'][-1]), 'final_soc': soc,
            'blast_q_start_windows': qstart, 'blast_q_end_windows': q_end,
            'blast_delta_efc_windows': delta_efc, 'blast_q_loss_cyclic': float(model.states['qLoss_EFC'][-1])}


class Tests(unittest.TestCase):
    def test_reference_capacities(self):
        b = Battery()
        self.assertEqual((b.cap, b.cap_2ndLife), (66, 46))
        self.assertAlmostEqual(b.outputs['qNew'][0]*b.cap, 46.2)
        for initial in (44.1, 43.5):
            self.assertEqual(CapacitySnapshot(66, initial, 1).q_eff_ah, initial)

    def test_bess_rhs_current_sign_and_units(self):
        bess = SecondLifeBattery1RC(r0_nominal_ohm=.01, q_nom_ref_ah=66., q_init_case_ah=44.1)
        for capacity in (44.1, 39.69):
            snapshot = CapacitySnapshot(66,44.1,capacity/44.1)
            for current in (-17.64, 0., 17.64):
                ds, _, dz = bess.rhs(0., [.5,0.,0.], current, snapshot.soh, capacity_snapshot=snapshot)
                self.assertAlmostEqual(ds, -current/(3600*capacity))
                self.assertAlmostEqual(dz, abs(current)/3600)
        self.assertAlmostEqual(1.*3600/3600, 1.)

    def test_controlled_profiles_and_physical_partition_invariance(self):
        expected = {'reposo': (0.,0.,0.), 'descarga_80pct': (35.28,.4,.4),
                    'carga_80pct': (35.28,.4,.4), 'ciclo_completo': (88.2,1.,1.),
                    'ciclo_parcial': (35.28,.4,.4), 'capacidad_variable': (33.516,.38,.4)}
        for name, case in CASES.items():
            with self.subTest(case=name):
                one, divided = simulate(case, 1), simulate(case, 4)
                for key, exp in zip(('throughput_ah','efc_initial','efc_variable'), expected[name]):
                    self.assertAlmostEqual(one[key], exp, places=11)
                    self.assertAlmostEqual(one[key], divided[key], places=11)
                self.assertAlmostEqual(one['final_soc'], divided['final_soc'], places=12)
                if name != 'reposo':
                    self.assertGreater(one['efc_blast'], 0.)
                else:
                    self.assertEqual(one['efc_blast'], 0.)

    def test_bess_state_accumulates_synthetic_throughput_across_snapshot_change(self):
        bess = SecondLifeBattery1RC(r0_nominal_ohm=.01, q_nom_ref_ah=66., q_init_case_ah=44.1)
        x = [.9, 0., 0.]
        for current, capacity in zip([17.64, -15.876], [44.1,39.69]):
            snapshot = CapacitySnapshot(66.,44.1,capacity/44.1)
            solution = solve_ivp(lambda t, y: bess.rhs(t,y,current,snapshot.soh,capacity_snapshot=snapshot),
                                 (0,3600), x, method='Radau', rtol=1e-9, atol=1e-11)
            self.assertTrue(solution.success)
            x = list(solution.y[:,-1])
        self.assertAlmostEqual(x[0], .9, places=8)
        self.assertAlmostEqual(x[2], 33.516, places=8)

    def test_blast_actual_q_history_and_window_partition(self):
        case = CASES['ciclo_completo']
        two = simulate(case, 1)
        self.assertAlmostEqual(two['efc_blast'], .5+.5*two['blast_q_start_windows'][1])
        self.assertLess(two['blast_q_start_windows'][1], 1.)
        b = Battery()
        t = np.linspace(0,7200,121)
        s = np.where(t <= 3600, 1-t/3600, (t-3600)/3600)
        b.update_battery_state(t, s, np.full_like(t,25.))
        self.assertAlmostEqual(b.stressors['efc'][-1], 1.)
        self.assertLess(two['efc_blast'], b.stressors['efc'][-1])
        b = Battery()
        rest = np.linspace(0, 15*86400, 61)
        b.update_battery_state(rest, np.ones_like(rest), np.full_like(rest,25.))
        q0 = b.outputs['q'][-1]
        self.assertLess(q0, 1.)
        b.update_battery_state(t+rest[-1], s, np.full_like(t,25.))
        self.assertAlmostEqual(b.stressors['efc'][-1], q0)

    def test_capacity_boundary_is_not_throughput(self):
        state = [0.]*15; state[12] = .5; state[14] = 12.3
        same = preserve_window_state(state, soc_min=.1, soc_max=.9)
        self.assertEqual(same, state)
        self.assertAlmostEqual(.5*(39.69-44.1), -2.205)
        b = Battery(); t = np.array([0., 60.]); temp = np.array([25.,25.])
        physical = b._extract_stressors(t, np.array([.5,.5]), temp)['delta_efc']
        rebased_soc = .5*44.1/39.69
        false_count = b._extract_stressors(t, np.array([.5,rebased_soc]), temp)['delta_efc']
        self.assertEqual(physical, 0.)
        self.assertAlmostEqual(false_count, abs(rebased_soc-.5)/2)

    def test_conditional_mapping_after_prior_blast_history(self):
        b = Battery()
        t = np.linspace(0,15*86400,61)
        b.update_battery_state(t,np.ones_like(t),np.full_like(t,25.))
        q0 = float(b.outputs['q'][-1]); self.assertLess(q0,1.)
        initial_efc = float(b.stressors['efc'][-1]); efc_case = efc_current = 0.
        for start, end in ((1.,.5),(.5,1.)):
            qprev = float(b.outputs['q'][-1])
            capacity = 44.1*qprev/q0
            physical_ah = capacity*abs(end-start)
            efc_case += physical_ah/(2*44.1)
            efc_current += physical_ah/(2*capacity)
            times = np.linspace(t[-1], t[-1]+3600,61)
            b.update_battery_state(times,np.linspace(start,end,61),np.full_like(times,25.))
            t = times
        self.assertAlmostEqual(b.stressors['efc'][-1]-initial_efc, q0*efc_case)
        self.assertAlmostEqual(efc_current, .5)


if __name__ == '__main__':
    assert sys.version_info[:3] == (3,12,10)
    assert metadata.version('BLAST-Lite') == '1.1.0'
    assert hashlib.sha256(Path(inspect.getfile(BatteryDegradationModel)).read_bytes()).hexdigest() == '1333d29393d2290669b8fb54170efefd68fdf0676e5994b71832adb6f8c0fd6f'
    assert hashlib.sha256(Path(inspect.getfile(Battery)).read_bytes()).hexdigest() == '258a76cf85db321cc6f525e166eb7c24f032ec7991cf7887a794f65b915b4844'
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    output = {'python': sys.version, 'executable': sys.executable, 'blast_version': metadata.version('BLAST-Lite'),
              'class_path': inspect.getfile(Battery), 'base_path': inspect.getfile(BatteryDegradationModel),
              'cases': {name: {'windows': simulate(case, 1), 'refined': simulate(case, 4)} for name, case in CASES.items()}}
    Path(__file__).with_name('results.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    for name, data in output['cases'].items():
        v = data['windows']; print(f"{name}: Ah={v['throughput_ah']:.6f}, EFC_ini={v['efc_initial']:.8f}, EFC_eff={v['efc_variable']:.8f}, BLAST={v['efc_blast']:.10f}; BLAST_refinado={data['refined']['efc_blast']:.10f}")
