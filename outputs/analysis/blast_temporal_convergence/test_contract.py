"""Independent checks of partition coverage and proposed boundary bookkeeping."""
import unittest
import numpy as np
from convergence import Battery, edges, profiles, run

class ContractTests(unittest.TestCase):
    def test_nested_partition_covers_original_intervals(self):
        for n in (1, 2, 4, 8, 16, 32, 64):
            bounds = edges(n)
            self.assertTrue(set(edges(n//2)).issubset(bounds) if n > 1 else True)
            self.assertEqual([i for a, z in zip(bounds, bounds[1:]) for i in range(a, z)], list(range(120)))
            for profile in profiles().values():
                result = run(profile, n)
                expected = np.abs(np.diff(profile[1])).sum()/2
                self.assertAlmostEqual(result['raw_soc_efc'], expected, places=12)

    def test_prior_blast_history_preserves_state_and_uses_case_q0(self):
        b = Battery()
        tr, sr, temp = profiles()['rest']
        b.update_battery_state(tr[:61], np.ones_like(sr[:61]), temp[:61])
        q0 = b.outputs['q'][-1]
        old_t = b.states['qLoss_t'][-1]
        tc, sc, temperature = profiles()['cycle']
        b.update_battery_state(tc + tr[60], sc, temperature)
        retention = b.outputs['q'][-1]/q0
        self.assertLess(retention, 1)
        self.assertGreater(b.states['qLoss_t'][-1], old_t)
        self.assertGreater(retention, b.outputs['q'][-1])
        self.assertAlmostEqual(44.1*retention/66, (44.1/66)*retention)

    def test_fractional_vs_charge_boundary_and_no_rebase_throughput(self):
        old_q, new_q, soc = 43.49916710474606, 43.22038064134823, .5
        rebased = soc*old_q/new_q
        self.assertGreater(rebased, soc)
        self.assertAlmostEqual(rebased*new_q, soc*old_q)
        self.assertLess(soc*new_q, soc*old_q)
        b = Battery()
        t = np.array([0., 60.]); temp = np.array([25.,25.])
        baseline = b._extract_stressors(t, np.array([rebased,rebased]), temp)['delta_efc']
        erroneous = b._extract_stressors(t, np.array([soc,rebased]), temp)['delta_efc']
        self.assertEqual(baseline, 0)
        self.assertAlmostEqual(erroneous, abs(rebased-soc)/2)
        self.assertGreater(.9*old_q/new_q, .9)

if __name__ == '__main__':
    unittest.main()
