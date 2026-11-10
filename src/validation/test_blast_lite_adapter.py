"""Synthetic integration tests using the separately installed original BLAST."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bess.aging_capacity import CapacitySnapshot
from bess.blast_lite_adapter import BlastLiteAdapter, preserve_window_state
from bess.model import SecondLifeBattery1RC
from controllers.gfm_controller import GFMController
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from microgrid import MicrogridWithBESS
from microgrid_bess_pi import MicrogridWithBESSPI

PYTHON = Path(os.environ.get('BLAST_LITE_PYTHON') or
              Path(os.environ.get('LOCALAPPDATA', '')) / 'microgrid_blast_probe_312' / 'Scripts' / 'python.exe')
META = dict(profile_kind='synthetic', temperature_origin='synthetic_cell',
            current_origin='synthetic_2p_group', current_sign='positive_discharge',
            units=('s','fraction','C','A'))

def feed(adapter, t, soc, temp=None, current=None, **changes):
    return adapter.update(time_s=t, soc=soc, temperature_c=temp if temp is not None else [25.]*len(t),
                          current_2p_a=current if current is not None else [0.]*len(t),
                          **(META | changes))

def battery():
    return SecondLifeBattery1RC(r0_nominal_ohm=.01, q_nom_ref_ah=66.,
                                q_init_case_ah=44.1, k_deg=.001, r0_soh_sensitivity=0.)


class BlastAdapterTests(unittest.TestCase):
    def test_initial_references_and_retention(self):
        for q_init in (44.1, 43.5):
            with self.subTest(initial=q_init), BlastLiteAdapter(PYTHON, q_init_case_ah=q_init) as adapter:
                self.assertEqual(adapter.snapshot.retention_since_case_start, 1.)
                self.assertEqual(adapter.snapshot.q_eff_ah, q_init)
                self.assertEqual(adapter.q0, 1.)
                self.assertEqual(adapter.blast_nominal_ah, 66)
                self.assertEqual(adapter.blast_second_life_ah, 46)
                self.assertAlmostEqual(adapter.blast_initial_qnew_ah, 46.2)
                result = feed(adapter, [0, 60, 120], [.5, .5, .5])
                self.assertAlmostEqual(result.capacity_snapshot.q_eff_ah, q_init*result.q/adapter.q0)
                self.assertAlmostEqual(result.q_new*66, 46.2*result.q)
                self.assertEqual(adapter.history[0]['samples'], 3)

    def test_state_history_and_synthetic_boundary(self):
        with BlastLiteAdapter(PYTHON) as adapter:
            a = feed(adapter, [0,30,60], [.5,.5,.5])
            b = feed(adapter, [60,90,120], [.5,.5,.5])
            self.assertEqual((a.windows,b.windows), (1,2))
            self.assertEqual((a.efc,b.efc), (0,0))
            self.assertLess(b.q, a.q)
            self.assertGreater(b.calendar_loss, a.calendar_loss)
            self.assertEqual(b.cycle_loss, 0)
            self.assertEqual(adapter.history[0]['end_s'], adapter.history[1]['start_s'])
            for t, s in [([121,150,180],[.5]*3),([120,150,180],[.6]*3)]:
                with self.assertRaises(ValueError): feed(adapter, t, s)
            self.assertEqual(adapter.snapshot, b.capacity_snapshot)

    def test_case_anchor_keeps_prior_history_and_does_not_repeat_old_loss(self):
        with BlastLiteAdapter(PYTHON) as adapter:
            previous = feed(adapter, [0, 43200, 86400], [.5]*3)
            anchored = adapter.anchor_case()
            self.assertEqual(anchored.q_eff_ah, 44.1)
            self.assertEqual(anchored.retention_since_case_start, 1.)
            self.assertEqual(adapter.q0, previous.q)
            self.assertEqual(adapter.history[-1]['windows'], 1)
            result = feed(adapter, [86400, 129600, 172800], [.5]*3)
            self.assertEqual(result.windows, 2)
            self.assertAlmostEqual(result.capacity_snapshot.q_eff_ah, 44.1*result.q/previous.q)
            self.assertEqual(result.efc, previous.efc)

    def test_synthetic_cycle_accumulates_original_blast_efc(self):
        with BlastLiteAdapter(PYTHON) as adapter:
            a = feed(adapter, [0,1800,3600], [1,.5,0], current=[46,46,46])
            b = feed(adapter, [3600,5400,7200], [0,.5,1], current=[-46,-46,-46])
            self.assertAlmostEqual(a.efc, .5)
            self.assertAlmostEqual(b.efc, .5 + .5*a.q)
            self.assertGreater(b.cycle_loss, a.cycle_loss)
            self.assertLess(b.q, a.q)

    def test_operational_or_missing_physical_data_rejected(self):
        with BlastLiteAdapter(PYTHON) as adapter:
            for change in ({'profile_kind':'operational'}, {'current_origin':'dc_bus'},
                           {'temperature_origin':'ambient'}, {'units':('s','fraction','K','A')}):
                with self.assertRaises(ValueError): feed(adapter, [0,60], [.5,.5], **change)
            with self.assertRaises(ValueError): adapter.update(time_s=[0,60], soc=[.5,.5],
                temperature_c=None, current_2p_a=None, **META)
            self.assertEqual(adapter.snapshot.retention_since_case_start, 1)
            self.assertEqual(len(adapter.history), 0)

    def test_named_modes_exclusive_and_snapshot_fixed_for_both_solvers(self):
        snap = CapacitySnapshot(66,44.1,.95)
        kwargs = dict(bess_model=battery(), controller=GFMController(p_ref=0,inertia_m=80,damping_d=1500))
        linear = MicrogridWithBESS(**kwargs, aging_mode='linear')
        legacy = MicrogridWithBESS(**kwargs)
        blast = MicrogridWithBESS(**kwargs, aging_mode='blast', capacity_snapshot=snap, blast_profile_kind='synthetic')
        old = linear.initial_state_with_bess(); old[12] = .6; old[14] = 10.
        state = old.copy()
        self.assertEqual(linear.system_dynamics(0, state), legacy.system_dynamics(0, state))
        self.assertEqual(state[12], old[12])
        self.assertEqual(state[14], old[14])
        self.assertEqual(blast._bess_soh(0), blast._bess_soh(100))
        self.assertNotEqual(linear._bess_soh(0), linear._bess_soh(100))
        self.assertEqual(len(blast.system_dynamics(0,state)), 15)
        for low, high in ((.1,.9),):
            for s in (low,high):
                state[12] = s
                self.assertEqual(blast.initial_state_with_bess()[12], blast.bess.soc_initial)
                self.assertTrue(low <= state[12] <= high)
        for options in ({'capacity_snapshot':snap}, {'aging_mode':'linear','capacity_snapshot':snap}, {'aging_mode':'blast'},
                        {'aging_mode':'blast','capacity_snapshot':snap},
                        {'aging_mode':'blast','capacity_snapshot':snap,'blast_profile_kind':'operational'},
                        {'aging_mode':'linear','blast_profile_kind':'synthetic'}, {'aging_mode':'other'}):
            with self.assertRaises(ValueError): MicrogridWithBESS(**kwargs, **options)
        with self.assertRaises(ValueError):
            MicrogridWithBESSPI(**kwargs, capacity_snapshot=snap,
                dc_link_bess_pi=DCLinkBESSPIController(vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.))
        with self.assertRaises(ValueError):
            MicrogridWithBESSPI(**kwargs, capacity_snapshot=snap, aging_mode='blast', blast_profile_kind='operational',
                dc_link_bess_pi=DCLinkBESSPIController(vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.))

    def test_missing_dependency_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'cannot start BLAST'):
            BlastLiteAdapter('missing-python-executable')

    def test_below_soh_limit_does_not_advance_worker(self):
        with BlastLiteAdapter(PYTHON, soh_min=44.1/66.) as adapter:
            with self.assertRaisesRegex(ValueError, 'SoH limit'):
                feed(adapter, [0,30,60], [.5]*3)
            self.assertEqual(adapter.snapshot.q_eff_ah, 44.1)
            self.assertEqual(adapter.history, [])
            anchor = adapter.anchor_case()
            self.assertEqual(adapter.q0, 1.)
            self.assertEqual(anchor.retention_since_case_start, 1.)
            self.assertEqual(adapter.history[-1]['windows'], 0)

    def test_real_snapshots_in_consecutive_microgrid_windows(self):
        kwargs = dict(bess_model=battery(), controller=GFMController(p_ref=0,inertia_m=80,damping_d=1500))
        with BlastLiteAdapter(PYTHON) as adapter:
            first = feed(adapter, [0,30,60], [.5,.5,.5])
            before = MicrogridWithBESS(**kwargs, aging_mode='blast', capacity_snapshot=first.capacity_snapshot, blast_profile_kind='synthetic')
            state = before.initial_state_with_bess(vdc0=340.)
            state[12] = .5
            original = state.copy()
            result = feed(adapter, [60,90,120], [.5,.5,.5])
            after = MicrogridWithBESS(**kwargs, aging_mode='blast', capacity_snapshot=result.capacity_snapshot, blast_profile_kind='synthetic')
            state = preserve_window_state(state, soc_min=after.bess.soc_min, soc_max=after.bess.soc_max)
            self.assertEqual(state, original)
            self.assertEqual(after.integrated_signals(0, state)['i_bess'], 0.)
            self.assertEqual(after.integrated_signals(0, state)['p_bess_dc'], 0.)
            self.assertEqual(result.efc, first.efc)
            self.assertEqual(after.system_dynamics(0, state)[14], 0.)
            self.assertEqual(after._compute_i_bess(330., after.bess.soc_min, result.capacity_snapshot.soh), 0.)
            self.assertEqual(after._compute_i_bess(350., after.bess.soc_max, result.capacity_snapshot.soh), 0.)
            state[14] = 100.
            self.assertEqual(after._bess_soh(state[14]), result.capacity_snapshot.soh)
            pi = MicrogridWithBESSPI(**kwargs, aging_mode='blast', capacity_snapshot=result.capacity_snapshot, blast_profile_kind='synthetic',
                dc_link_bess_pi=DCLinkBESSPIController(vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.))
            pi_state = state + [0.]
            self.assertEqual(len(pi.system_dynamics(0, pi_state)), 16)
            self.assertEqual(pi.integrated_signals(0, pi_state)['soh_bess'], result.capacity_snapshot.soh)

    def test_boundary_rejects_outside_soc_without_clipping(self):
        state = [0.] * 15
        for value in (.1, .9):
            state[12] = value
            self.assertEqual(preserve_window_state(state, soc_min=.1, soc_max=.9), state)
        for value in (.099, .901):
            state[12] = value
            with self.assertRaises(ValueError): preserve_window_state(state, soc_min=.1, soc_max=.9)

if __name__ == '__main__':
    unittest.main()
