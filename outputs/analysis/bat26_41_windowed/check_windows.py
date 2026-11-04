"""Three-window synthetic microgrid experiment with the original BLAST worker."""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import scipy
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from bess.blast_lite_adapter import BlastLiteAdapter, preserve_window_state
from controllers.dc_link_bess_pi import DCLinkBESSPIController
from controllers.gfm_controller import GFMController
from config import SIM_SOLVER_ATOL_DEFAULT, SIM_SOLVER_RTOL_DEFAULT, SIM_SOLVER_MAX_STEP_S_DEFAULT
from microgrid import MicrogridWithBESS
from microgrid_bess_pi import MicrogridWithBESSPI

PYTHON = os.environ.get('BLAST_LITE_PYTHON') or str(Path(os.environ['LOCALAPPDATA']) / 'microgrid_blast_probe_312' / 'Scripts' / 'python.exe')
META = dict(profile_kind='synthetic', temperature_origin='synthetic_cell',
            current_origin='synthetic_2p_group', current_sign='positive_discharge',
            units=('s', 'fraction', 'C', 'A'))

def make_model(pi, snapshot=None, mode='blast'):
    kw = dict(controller=GFMController(p_ref=3000., inertia_m=80., damping_d=1500.), aging_mode=mode)
    if mode == 'blast':
        kw.update(capacity_snapshot=snapshot, blast_profile_kind='synthetic')
    if pi:
        return MicrogridWithBESSPI(dc_link_bess_pi=DCLinkBESSPIController(
            vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.), **kw)
    return MicrogridWithBESS(**kw)

def run_case(pi):
    records = []
    with BlastLiteAdapter(PYTHON) as adapter:
        snap = adapter.snapshot
        assert snap.q_eff_ah == 44.1 and adapter.q0 == 1.0
        model = make_model(pi, snap)
        x = model.initial_state_with_bess(vdc0=340.)
        assert len(x) == (16 if pi else 15)
        previous_efc = 0.
        for index in range(3):
            start, end = index*.02, (index+1)*.02
            times = np.linspace(start, end, 21)
            start_state = np.asarray(x, dtype=float).copy()
            sol = solve_ivp(model.system_dynamics, (start,end), x, t_eval=times,
                rtol=SIM_SOLVER_RTOL_DEFAULT, atol=SIM_SOLVER_ATOL_DEFAULT,
                max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT)
            assert sol.success and np.isfinite(sol.y).all()
            assert np.all((sol.y[12] >= model.bess.soc_min) & (sol.y[12] <= model.bess.soc_max))
            currents = []
            max_soc_rhs_error = 0.
            for t, state in zip(sol.t, sol.y.T):
                signals = model.integrated_signals(float(t), state)
                current = float(signals['i_bess'])
                currents.append(current)
                derivative = model.system_dynamics(float(t), state)
                max_soc_rhs_error = max(max_soc_rhs_error, abs(derivative[12] + current/(3600*snap.q_eff_ah)))
                assert np.isclose(signals['soh_bess'], snap.soh, rtol=0, atol=1e-15)
            assert max_soc_rhs_error < 1e-16
            final_state = sol.y[:,-1].copy()
            before = model.integrated_signals(end, final_state)
            old_q = adapter.q0 if index == 0 else previous_q
            # Synthetic test-only 1:1 current proxy; BLAST does not consume current.
            result = adapter.update(time_s=sol.t.tolist(), soc=sol.y[12].tolist(),
                temperature_c=[25.]*len(sol.t), current_2p_a=currents, **META)
            expected_efc_delta = old_q * float(np.abs(np.diff(sol.y[12])).sum()) / 2
            assert np.isclose(result.efc-previous_efc, expected_efc_delta, rtol=1e-10, atol=1e-16)
            assert np.isclose(result.capacity_snapshot.q_eff_ah, 44.1*result.q/adapter.q0, rtol=0, atol=1e-12)
            next_state = preserve_window_state(final_state, soc_min=model.bess.soc_min, soc_max=model.bess.soc_max)
            assert np.array_equal(final_state, next_state)
            updated = make_model(pi, result.capacity_snapshot)
            after = updated.integrated_signals(end, next_state)
            assert result.efc == adapter.history[-1]['result'].efc
            assert next_state[14] == final_state[14]
            assert all(next_state[i] == final_state[i] for i in range(len(next_state)))
            assert np.isclose(updated._bess_soh(next_state[14]+100), result.capacity_snapshot.soh, rtol=0, atol=0)
            altered = next_state.copy(); altered[14] += 100.
            assert np.isclose(updated.system_dynamics(end, altered)[12], updated.system_dynamics(end, next_state)[12], rtol=0, atol=0)
            records.append({'window': index+1, 'start_s': start, 'end_s': end,
                'q_used_ah': snap.q_eff_ah, 'soh_used': snap.soh, 'q_blast_end': result.q,
                'q_next_ah': result.capacity_snapshot.q_eff_ah, 'retention_next': result.capacity_snapshot.retention_since_case_start,
                'soc_start': float(start_state[12]), 'soc_end': float(final_state[12]),
                'z_start_ah': float(start_state[14]), 'z_end_ah': float(final_state[14]),
                'blast_efc_total': result.efc, 'blast_efc_delta': result.efc-previous_efc,
                'q_loss_t': result.calendar_loss, 'q_loss_efc': result.cycle_loss,
                'max_state_jump': float(np.max(np.abs(final_state-np.asarray(next_state)))),
                'delta_i_boundary_a': float(after['i_bess']-before['i_bess']),
                'delta_p_boundary_w': float(after['p_bess_dc']-before['p_bess_dc']),
                'delta_vt_boundary_v': float(after['vt_bess']-before['vt_bess']),
                'delta_algebraic_soc_times_q_ah': float(final_state[12]*(result.capacity_snapshot.q_eff_ah-snap.q_eff_ah)),
                'max_soc_rhs_error': max_soc_rhs_error, 'nfev': sol.nfev,
                'initial_state': start_state.tolist(), 'terminal_state': final_state.tolist(),
                'time_samples_s': sol.t.tolist(), 'soc_samples': sol.y[12].tolist(),
                'synthetic_2p_current_assumption_a': currents,
                'input_profile_sha256': adapter.history[-1]['sha256']})
            previous_q, previous_efc = result.q, result.efc
            x, model, snap = next_state, updated, result.capacity_snapshot
        assert len(adapter.history) == 3
        for invalid in (.099, .901):
            bad = x.copy(); bad[12] = invalid
            try: preserve_window_state(bad, soc_min=.1, soc_max=.9)
            except ValueError: pass
            else: raise AssertionError('invalid boundary SoC was not rejected')
        if pi:
            low = model._operating_power_limits(vdc_v=340.,soc_bess=.1,soh_bess=snap.soh)
            high = model._operating_power_limits(vdc_v=340.,soc_bess=.9,soh_bess=snap.soh)
            assert low[1] == 0. and low[0] < 0. and high[0] == 0. and high[1] > 0.
        else:
            assert model._compute_i_bess(330.,.1,snap.soh) == 0.
            assert model._compute_i_bess(350.,.9,snap.soh) == 0.
            assert model._compute_i_bess(350.,.1,snap.soh) < 0.
            assert model._compute_i_bess(330.,.9,snap.soh) > 0.
        lin = make_model(pi, mode='linear')
        default_kw = dict(controller=GFMController(p_ref=3000., inertia_m=80., damping_d=1500.))
        if pi:
            default = MicrogridWithBESSPI(dc_link_bess_pi=DCLinkBESSPIController(vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.), **default_kw)
        else: default = MicrogridWithBESS(**default_kw)
        assert np.array_equal(lin.system_dynamics(.06,x), default.system_dynamics(.06,x))
        assert lin._bess_soh(x[14]) == max(lin.bess.soh_min, lin.bess.soh_init_case-lin.bess.k_deg*x[14])
    return records

def main():
    data = {'python': sys.version, 'executable': sys.executable,
            'numpy': np.__version__, 'scipy': scipy.__version__, 'BLAST_worker': 'Python 3.12.10, BLAST-Lite 1.1.0 (worker-enforced hashes)',
            'profile': 'synthetic, T_cell 25 C, test-only numerical 1:1 current proxy; not an identified 2p-to-bus conversion',
            'excel_sha256': hashlib.sha256((ROOT/'OCV_SOC.xlsx').read_bytes()).hexdigest(),
            'rtol': SIM_SOLVER_RTOL_DEFAULT, 'atol': SIM_SOLVER_ATOL_DEFAULT,
            'max_step_s': SIM_SOLVER_MAX_STEP_S_DEFAULT, 'sample_points_per_window': 21,
            'gfm_M':80., 'gfm_D':1500., 'results': {'15_states':run_case(False), '16_states':run_case(True)}}
    out = Path(__file__).with_name('results.json')
    out.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    for kind, rows in data['results'].items():
        for r in rows:
            print(f"{kind} w{r['window']}: Q={r['q_used_ah']:.12f}->{r['q_next_ah']:.12f} Ah; SoC={r['soc_start']:.12f}->{r['soc_end']:.12f}; q={r['q_blast_end']:.12f}; EFC={r['blast_efc_total']:.12g}; jump={r['max_state_jump']:.1f}; delta_Vt={r['delta_vt_boundary_v']:.12g}")
    print('PASS: three windows per architecture; see results.json')

if __name__ == '__main__':
    main()
