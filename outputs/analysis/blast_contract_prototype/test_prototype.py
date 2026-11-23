import copy
from dataclasses import FrozenInstanceError
import unittest

import numpy as np
from prototype import (Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery as Battery,
                       ResearchContract, boundary, validate_physical_profile)


def window(b, start, end, start_soc=.5, end_soc=.5):
    t = np.linspace(start, end, 61)
    b.update_battery_state(t, np.linspace(start_soc, end_soc, 61), np.full(61, 25.))


def state(b):
    return {group: {k: v.copy() for k, v in getattr(b, group).items()}
            for group in ('states', 'outputs', 'stressors', 'rates')}


def equal_states(a, b):
    return all(np.array_equal(x, b[g][k], equal_nan=True)
               for g in a for k, x in a[g].items())


class PrototypeTests(unittest.TestCase):
    def test_initial_units_and_immutability(self):
        for initial in (44.1, 43.5):
            b = Battery(); v = ResearchContract(b, initial, assume_relative_transfer=True).read()
            self.assertEqual(v.retention_since_case_start, 1)
            self.assertEqual(v.capacity.q_eff_ah, initial)
            self.assertAlmostEqual(v.capacity.soh, initial/66)
            self.assertEqual((v.blast_nominal_ah, v.blast_second_life_ah), (66,46))
            self.assertAlmostEqual(v.blast_initial_qnew_ah, 46.2)
            with self.assertRaises(FrozenInstanceError): v.q = 0
            with self.assertRaises(FrozenInstanceError): v.capacity.q_eff_ah = 0
        with self.assertRaises(ValueError): ResearchContract(Battery(), 44.1, assume_relative_transfer=False)

    def test_history_anchor_no_double_degradation_and_preservation(self):
        b = Battery(); window(b, 0, 15*86400)
        past = state(b); q0 = float(b.outputs['q'][-1]); past_loss = b.states['qLoss_t'][-1]
        c = ResearchContract(b, 44.1, assume_relative_transfer=True)
        v0 = c.read()
        self.assertAlmostEqual(v0.capacity.q_eff_ah, 44.1)
        self.assertTrue(equal_states(past, state(b)))
        window(b, 15*86400, 30*86400)
        before_read = state(b); v = c.read(); self.assertTrue(equal_states(before_read, state(b)))
        self.assertLess(v.capacity.q_eff_ah, v0.capacity.q_eff_ah)
        self.assertAlmostEqual(v.capacity.q_eff_ah, 44.1*v.q/q0)
        self.assertNotAlmostEqual(v.capacity.q_eff_ah, 44.1*v.q)
        self.assertNotAlmostEqual(v.capacity.q_eff_ah, 44.1*.7*v.q/q0)
        self.assertGreater(v.calendar_loss, past_loss)
        self.assertEqual(v.efc, 0.)
        self.assertEqual(v.cycle_loss, 0.)
        self.assertTrue(equal_states(before_read, state(b)))
        b.states['qLoss_t'][0] = .01
        with self.assertRaises(ValueError): c.read()

    def test_two_real_windows_cycle_continuity(self):
        b = Battery(); c = ResearchContract(b, 43.5, assume_relative_transfer=True)
        window(b, 0, 3600, 1, 0); first = c.read()
        prefix = state(b)
        window(b, 3600, 7200, 0, 1); second = c.read()
        self.assertGreater(second.efc, first.efc)
        self.assertLess(second.capacity.q_eff_ah, first.capacity.q_eff_ah)
        for group, vals in prefix.items():
            for k, old in vals.items():
                self.assertTrue(np.array_equal(getattr(b,group)[k][:len(old)], old, equal_nan=True))

    def test_boundary_candidates_and_limits(self):
        before, after = 44.1, 43.5
        a = boundary(.5, before, after, policy='fractional_soc')
        b = boundary(.5, before, after, policy='algebraic_charge')
        self.assertEqual(a.soc_after, .5)
        self.assertLess(a.stored_after_ah, a.stored_before_ah)
        self.assertAlmostEqual(b.stored_after_ah, b.stored_before_ah)
        self.assertGreater(b.soc_after, .5)
        self.assertFalse(boundary(.9, before, after, policy='algebraic_charge').within_operational_limits)
        self.assertGreater(boundary(1, before, after, policy='algebraic_charge').soc_after, 1)
        with self.assertRaises(ValueError): boundary(.5, before, after, policy='automatic')

    def test_rebase_is_not_a_physical_interval(self):
        b = Battery(); c = ResearchContract(b, 44.1, assume_relative_transfer=True)
        before = state(b); first = c.read(); second = c.read()
        self.assertEqual(first.efc, second.efc)
        self.assertTrue(equal_states(before, state(b)))
        outcome = boundary(.5, 44.1, 43.5, policy='algebraic_charge')
        t = np.array([0.,60.]); temp = np.array([25.,25.])
        false_efc = b._extract_stressors(t, np.array([.5,outcome.soc_after]), temp)['delta_efc']
        correct_efc = b._extract_stressors(t, np.array([outcome.soc_after,outcome.soc_after]), temp)['delta_efc']
        self.assertGreater(false_efc,0); self.assertEqual(correct_efc,0)
        # A read-only capacity view has no current or energy output.
        self.assertFalse(hasattr(second, 'current')); self.assertFalse(hasattr(second, 'energy'))

    def test_missing_group_physical_signals_rejected(self):
        good = dict(time_s=[0,60], soc=[.5,.5], temperature_c=[25,25],
                    current_2p_a=[0,0], current_origin='2p_group', temperature_origin='cell',
                    units=('s','fraction','C','A'), current_sign='positive_discharge')
        validate_physical_profile(**good)
        for name in ('time_s','soc','temperature_c','current_2p_a','current_origin','temperature_origin','units','current_sign'):
            bad = copy.copy(good); bad[name] = None
            with self.assertRaises(ValueError): validate_physical_profile(**bad)
        for name, value in [('current_origin','dc_bus'), ('temperature_origin','ambient'),
                            ('units',('s','fraction','K','A')), ('current_sign','positive_charge'), ('temperature_c',[298.15,None]),
                            ('soc',[50,50]), ('time_s',[0,0]), ('current_2p_a',[0])]:
            bad = copy.copy(good); bad[name] = value
            with self.assertRaises((ValueError,TypeError)): validate_physical_profile(**bad)

if __name__ == '__main__':
    unittest.main()
