"""BAT26-54 algebraic study; fixtures are not equipment ratings.

Run with --test for independent analytical checks, or without it for JSON.
No dynamic model, hardware limits, or BLAST workers are used.
"""
from __future__ import annotations

import json
import math
import sys
import unittest


def study(p_ac_w, pf, pv_dc_w, vbus_v, vpack_v, eta_inv, eta_dis, eta_ch, filter_loss_w=0.0):
    """Steady operating point; signed BESS power positive towards the DC bus.

    eta_inv applies from inverter DC input to bridge AC output; filter_loss_w
    covers positive bridge-to-load active losses. Surplus goes to charging only
    by the explicit ideal dispatcher assumption: no curtailment or other load.
    """
    vals = (p_ac_w, pf, pv_dc_w, vbus_v, vpack_v, eta_inv, eta_dis, eta_ch, filter_loss_w)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vals):
        raise ValueError('inputs must be finite numbers')
    if p_ac_w < 0 or pv_dc_w < 0 or filter_loss_w < 0 or vbus_v <= 0 or vpack_v <= 0:
        raise ValueError('power must be nonnegative and voltages positive')
    if not all(0 < x <= 1 for x in (pf, eta_inv, eta_dis, eta_ch)):
        raise ValueError('power factor and efficiencies must be in (0, 1]')
    apparent = p_ac_w / pf
    reactive = p_ac_w * math.tan(math.acos(pf))
    bridge = p_ac_w + filter_loss_w
    inv_dc = bridge / eta_inv
    bus = inv_dc - pv_dc_w
    pack = bus / eta_dis if bus >= 0 else bus * eta_ch
    return dict(p_ac_w=p_ac_w, s_ac_va=apparent, q_ac_var=reactive,
                p_bridge_w=bridge, p_inv_dc_w=inv_dc, p_pv_dc_w=pv_dc_w,
                p_bess_bus_w=bus, i_bess_bus_a=bus/vbus_v, p_pack_w=pack,
                i_pack_a=pack/vpack_v, p_loss_filter_w=filter_loss_w,
                p_loss_inv_w=inv_dc-bridge, p_loss_dcdc_w=pack-bus,
                vbus_over_vpack=vbus_v/vpack_v)


class TestSizing(unittest.TestCase):
    def test_known_full_backup(self):
        r = study(4200, .95, 0, 340, 240, .97, .95, .95)
        self.assertAlmostEqual(r['s_ac_va'], 4421.052631578947)
        self.assertAlmostEqual(r['p_inv_dc_w'], 4329.896907216495)
        self.assertAlmostEqual(r['p_pack_w'], 4557.786218122626)
        self.assertAlmostEqual(r['i_pack_a'], 18.9907759088443)
        self.assertAlmostEqual(r['p_pack_w'], r['p_ac_w'] + r['p_loss_inv_w'] + r['p_loss_dcdc_w'])

    def test_pv_deficit_and_surplus(self):
        a = study(1200, .95, 1000, 340, 360, .97, .95, .90, 50)
        self.assertAlmostEqual(a['p_bess_bus_w'], 1250/.97 - 1000)
        self.assertAlmostEqual(a['p_pack_w'] + 1000, 1200 + sum(a[k] for k in ('p_loss_inv_w', 'p_loss_dcdc_w', 'p_loss_filter_w')))
        b = study(1200, .95, 2000, 340, 360, .97, .95, .90)
        self.assertLess(b['p_pack_w'], 0)
        self.assertAlmostEqual(b['p_pack_w'], .9*b['p_bess_bus_w'])
        self.assertGreater(b['p_loss_dcdc_w'], 0)
        self.assertAlmostEqual(b['p_pv_dc_w'] + b['p_pack_w'], b['p_ac_w'] + b['p_loss_inv_w'] + b['p_loss_dcdc_w'])

    def test_unity_and_voltage_scaling(self):
        a = study(1200, 1, 0, 340, 360, 1, 1, 1)
        b = study(1200, 1, 0, 306, 240, 1, 1, 1)
        self.assertEqual(a['p_pack_w'], 1200)
        self.assertEqual(a['p_loss_dcdc_w'], 0)
        self.assertEqual(a['q_ac_var'], 0)
        self.assertAlmostEqual(a['i_bess_bus_a']*340, b['i_bess_bus_a']*306)
        self.assertAlmostEqual(a['i_pack_a']*360, b['i_pack_a']*240)

    def test_invalid_inputs(self):
        args = [1200, .95, 0, 340, 240, .97, .95, .95]
        for index, value in ((0, -1), (1, 0), (2, -1), (3, 0), (4, float('nan')), (5, 1.1), (6, 0), (7, True)):
            values = args.copy(); values[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                study(*values)


def main():
    scenarios = {}
    for power in (1200, 4200):
        for pv in (0, 1000):
            for vbus in (306, 340, 374):
                for vpack in (240, 360, 398.4):
                    key = f'ac{power}_pv{pv}_bus{vbus}_pack{vpack}'
                    scenarios[key] = study(power, .95, pv, vbus, vpack, .97, .95, .95)
    sensitivities = {f'inv{ei}_dcdc{ed}': study(4200, .95, 0, 340, 240, ei, ed, ed)
                     for ei in (.95, .97, 1.0) for ed in (.90, .95, .98, 1.0)}
    print(json.dumps({'label': 'HYPOTHETICAL sensitivity, NOT equipment ratings',
                      'assumptions': {'pf': .95, 'eta_inverter': .97, 'eta_dcdc_charge_discharge': .95,
                                      'filter_loss_w': 0, 'pv_at_bus_w': [0, 1000],
                                      'vbus_sensitivity_v': [306, 340, 374]},
                      'scenarios': scenarios, 'efficiency_sensitivity_4200w': sensitivities}, indent=2))


if __name__ == '__main__':
    if '--test' in sys.argv:
        sys.argv.remove('--test')
        unittest.main(verbosity=2)
    else:
        main()
