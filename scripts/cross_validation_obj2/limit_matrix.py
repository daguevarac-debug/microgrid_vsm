import sys
sys.path.insert(0, 'src')
from validation.test_microgrid_bess_dcdc import TestMicrogridWithBESSDCDC
from validation.compare_bess_soh_scenarios import _nominal_soh
m = TestMicrogridWithBESSDCDC()._make_model()
count=0
for soc in (m.bess.soc_min, 0.6, m.bess.soc_max):
 for soh in (0.5, _nominal_soh(), 1.0):
  for v in (10.0, 330.0, 350.0):
   for xi in (-100.0, 100.0):
    c=m._evaluate_dcdc_coupling(vdc_v=v,soc_bess=soc,vrc_bess=0,soh_bess=soh,xi_bess_vdc_v_s=xi)
    p=c.p_bus_w; d=c.dcdc_result; pi=c.pi_output
    assert abs(c.i_bus_a) <= m.dcdc_parameters.bus_current_max_a + 1e-8
    assert abs(p) <= min(m.dcdc_parameters.bus_power_max_w, m._available_p_bess_max_w(soh)) + 1e-8
    assert abs(d.unit_current_a) <= m._available_i_bess_max(soh)+1e-8
    assert d.bus_charge_limit_w - 1e-8 <= p <= d.bus_discharge_limit_w + 1e-8
    assert abs(pi.p_bess_ref_w-p) < 1e-8
    assert not (soc <= m.bess.soc_min and p > 1e-8)
    assert not (soc >= m.bess.soc_max and p < -1e-8)
    if pi.anti_windup_active: assert pi.d_xi_vdc_dt == 0
    count += 1
print(f'{count} combinaciones de SoC, SoH, tensión y comando PI: PASS')
