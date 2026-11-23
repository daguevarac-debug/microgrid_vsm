"""Tests use synthetic values only; they do not characterize a real battery."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bess.dc_dc_adapter import DCDCParameters, convert_power


class TestDCDCAdapter(unittest.TestCase):
    def setUp(self):
        self.params = DCDCParameters(
            n_series=10, n_parallel=3, eta_discharge=0.9, eta_charge=0.8,
            unit_voltage_min_v=2.0, unit_voltage_max_v=5.0,
            unit_discharge_max_a=10.0, unit_charge_max_a=8.0,
            bus_current_max_a=100.0, bus_power_max_w=10000.0,
        )

    def convert(self, request, **overrides):
        args = dict(parameters=self.params, bus_power_request_w=request,
                    bus_voltage_v=100.0, ocv_v=4.0, vrc_v=0.2,
                    r0_ohm=0.1, soc=0.5, soc_min=0.1, soc_max=0.9)
        args.update(overrides)
        return convert_power(**args)

    def check_balance(self, result, eta, discharge):
        self.assertAlmostEqual(result.unit_voltage_v, 3.8 - 0.1 * result.unit_current_a)
        self.assertAlmostEqual(result.bank_power_w, 30 * result.unit_voltage_v * result.unit_current_a)
        self.assertAlmostEqual(result.bus_power_w, 100 * result.bus_current_a)
        self.assertAlmostEqual(result.loss_power_w, result.bank_power_w - result.bus_power_w)
        self.assertGreaterEqual(result.loss_power_w, 0)
        if discharge:
            self.assertAlmostEqual(result.bus_power_w, eta * result.bank_power_w)
        else:
            self.assertAlmostEqual(result.bank_power_w, eta * result.bus_power_w)

    def test_discharge_low_current_root_and_power_balance(self):
        r = self.convert(200)
        self.assertGreater(r.unit_current_a, 0)
        self.assertLess(r.unit_current_a, 3.8 / 0.2)
        self.assertFalse(r.saturated)
        self.check_balance(r, 0.9, True)

    def test_charge_sign_and_power_balance(self):
        r = self.convert(-200)
        self.assertLess(r.unit_current_a, 0)
        self.assertLess(r.bus_current_a, 0)
        self.check_balance(r, 0.8, False)

    def test_rest_and_lossless_efficiency(self):
        r = self.convert(0)
        self.assertEqual((r.unit_current_a, r.bus_current_a, r.loss_power_w), (0, 0, 0))
        r = self.convert(100, parameters=replace(self.params, eta_discharge=1))
        self.assertAlmostEqual(r.loss_power_w, 0)

    def test_unit_current_and_voltage_saturation(self):
        r = self.convert(10000)
        self.assertTrue(r.saturated)
        self.assertAlmostEqual(r.unit_current_a, 10)
        self.check_balance(r, 0.9, True)
        r = self.convert(-10000, parameters=replace(self.params, unit_voltage_max_v=4.0))
        self.assertTrue(r.saturated)
        self.assertAlmostEqual(r.unit_voltage_v, 4.0)
        self.check_balance(r, 0.8, False)

    def test_bus_limits_and_soc_boundaries(self):
        params = replace(self.params, bus_current_max_a=0.5, bus_power_max_w=40)
        for request in (-100, 100):
            r = self.convert(request, parameters=params)
            self.assertTrue(r.saturated)
            self.assertEqual(abs(r.bus_power_w), 40)
        self.assertEqual(self.convert(100, soc=0.1).bus_power_w, 0)
        self.assertEqual(self.convert(-100, soc=0.9).bus_power_w, 0)
        self.assertGreater(self.convert(100, soc=0.9).bus_power_w, 0)
        self.assertLess(self.convert(-100, soc=0.1).bus_power_w, 0)
        self.assertEqual(self.convert(0, soc=0.1).bus_discharge_limit_w, 0)
        self.assertEqual(self.convert(0, soc=0.9).bus_charge_limit_w, 0)

    def test_maximum_power_saturates_infeasible_discriminant(self):
        params = replace(self.params, unit_voltage_min_v=0.1, unit_discharge_max_a=100)
        r = self.convert(10000, parameters=params)
        self.assertTrue(r.saturated)
        self.assertAlmostEqual(r.unit_current_a, 19.0, places=6)
        self.check_balance(r, 0.9, True)

    def test_zero_resistance_and_small_request(self):
        r = self.convert(1e-12)
        self.assertAlmostEqual(r.unit_current_a, 1e-12 / (0.9 * 30 * 3.8), places=25)
        r = self.convert(100, r0_ohm=0)
        self.assertAlmostEqual(r.unit_current_a, 100 / (0.9 * 30 * 3.8))
        self.assertAlmostEqual(r.unit_voltage_v, 3.8)

    def test_reject_invalid_or_infeasible_inputs(self):
        for overrides in (dict(r0_ohm=-1), dict(soc=float('nan')),
                          dict(soc_min=0.9, soc_max=0.1)):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.convert(100, **overrides)
        for overrides in (dict(n_series=0), dict(n_parallel=True),
                          dict(eta_charge=0), dict(eta_discharge=1.1),
                          dict(unit_voltage_min_v=5)):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                replace(self.params, **overrides)

    def test_bus_current_limit_independent_of_power_limit(self):
        params = replace(self.params, bus_current_max_a=0.5, bus_power_max_w=10000)
        for request in (100, -100):
            with self.subTest(request=request):
                r = self.convert(request, parameters=params)
                self.assertEqual((r.bus_charge_limit_w, r.bus_discharge_limit_w), (-50, 50))
                self.assertEqual(r.bus_power_w, 50 if request > 0 else -50)
                self.assertTrue(r.saturated)
                self.assertEqual(r.protection_status, 'ok')
                self.check_balance(r, 0.9 if request > 0 else 0.8, request > 0)

    def test_discharge_voltage_limit_independently(self):
        params = replace(self.params, unit_voltage_min_v=3.5, unit_discharge_max_a=100)
        r = self.convert(10000, parameters=params)
        self.assertAlmostEqual(r.unit_voltage_v, 3.5)
        self.assertAlmostEqual(r.unit_current_a, 3.0)
        self.assertAlmostEqual(r.bus_discharge_limit_w, 30 * 3.5 * 3 * .9)
        self.assertAlmostEqual(r.bus_power_w, r.bus_discharge_limit_w)
        self.check_balance(r, 0.9, True)

    def test_charge_current_limit_independently(self):
        r = self.convert(-10000)
        self.assertAlmostEqual(r.unit_current_a, -8)
        self.assertAlmostEqual(r.bus_charge_limit_w, -30 * 4.6 * 8 / .8)
        self.assertAlmostEqual(r.bus_power_w, r.bus_charge_limit_w)
        self.check_balance(r, 0.8, False)

    def test_unity_efficiency_charge(self):
        r = self.convert(-200, parameters=replace(self.params, eta_charge=1))
        self.assertEqual(r.loss_power_w, 0)
        self.check_balance(r, 1, False)

    def test_series_and_parallel_scale_independently(self):
        base = self.convert(0)
        for name in ('n_series', 'n_parallel'):
            with self.subTest(name=name):
                p = replace(self.params, **{name: 2 * getattr(self.params, name)})
                r = self.convert(0, parameters=p)
                self.assertAlmostEqual(r.bus_charge_limit_w, 2 * base.bus_charge_limit_w)
                self.assertAlmostEqual(r.bus_discharge_limit_w, 2 * base.bus_discharge_limit_w)
                sent = self.convert(200, parameters=p)
                self.assertAlmostEqual(sent.bank_power_w,
                    p.n_series * p.n_parallel * sent.unit_voltage_v * sent.unit_current_a)
                self.assertAlmostEqual(sent.bus_power_w, .9 * sent.bank_power_w)

    def test_voltage_protection_blocks_exchange_without_claiming_valid_voltage(self):
        for overrides, status, expected_voltage in (
            (dict(ocv_v=2, vrc_v=0.1), 'unit_undervoltage', 1.9),
            (dict(ocv_v=5, vrc_v=-0.1), 'unit_overvoltage', 5.1),
            (dict(bus_voltage_v=0), 'bus_voltage_nonpositive', 3.8),
            (dict(bus_voltage_v=-1), 'bus_voltage_nonpositive', 3.8),
            (dict(ocv_v=0, vrc_v=0), 'ocv_nonpositive', 0),
        ):
            for request in (-100, 0, 100):
                with self.subTest(status=status, request=request):
                    r = self.convert(request, **overrides)
                    self.assertEqual(r.protection_status, status)
                    self.assertAlmostEqual(r.unit_voltage_v, expected_voltage)
                    self.assertEqual((r.unit_current_a, r.bus_current_a, r.bank_power_w,
                                      r.bus_power_w, r.loss_power_w), (0, 0, 0, 0, 0))
                    self.assertEqual((r.bus_charge_limit_w, r.bus_discharge_limit_w), (0, 0))
                    self.assertEqual(r.saturated, request != 0)

    def test_external_soh_limits_reduce_not_expand_and_can_block(self):
        p = self.params
        base = self.convert(0)
        r = self.convert(10000, unit_discharge_available_a=2,
                         unit_charge_available_a=3)
        self.assertAlmostEqual(r.unit_current_a, 2)
        self.assertAlmostEqual(r.bus_discharge_limit_w, 30 * 3.6 * 2 * .9)
        self.assertAlmostEqual(r.bus_charge_limit_w, -30 * 4.1 * 3 / .8)
        self.assertEqual(r.bus_power_w, r.bus_discharge_limit_w)
        self.check_balance(r, .9, True)
        expanded = self.convert(0, unit_discharge_available_a=100,
                                unit_charge_available_a=100)
        self.assertEqual((expanded.bus_charge_limit_w, expanded.bus_discharge_limit_w),
                         (base.bus_charge_limit_w, base.bus_discharge_limit_w))
        stopped = self.convert(-1, unit_charge_available_a=0)
        self.assertEqual(stopped.bus_charge_limit_w, 0)
        self.assertEqual(stopped.bus_power_w, 0)
        self.assertTrue(stopped.saturated)
        with self.assertRaises(ValueError):
            self.convert(0, unit_discharge_available_a=-1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
