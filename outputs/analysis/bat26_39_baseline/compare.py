"""Compare committed linear baseline with current default in isolated processes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
COMMIT = '95272bee594a6f16817945fd6b2959681a7bc552'


def child(source, mode):
    import builtins
    import numpy as np
    import scipy
    from scipy.integrate import solve_ivp
    real_import = builtins.__import__
    def reject_blast(name, *args, **kwargs):
        if name == 'blast' or name.startswith('blast.') or name.startswith('bess.blast_'):
            raise AssertionError('linear mode attempted to import BLAST')
        return real_import(name, *args, **kwargs)
    builtins.__import__ = reject_blast
    def reject_worker(*args, **kwargs):
        raise AssertionError('linear mode attempted to launch a subprocess')
    subprocess.Popen = reject_worker
    sys.path.insert(0, str(Path(source) / 'src'))
    from controllers.gfm_controller import GFMController
    from controllers.dc_link_bess_pi import DCLinkBESSPIController
    from microgrid import MicrogridWithBESS
    from microgrid_bess_pi import MicrogridWithBESSPI
    from config import SIM_SOLVER_RTOL_DEFAULT, SIM_SOLVER_ATOL_DEFAULT, SIM_SOLVER_MAX_STEP_S_DEFAULT
    cases = {}
    for kind in ('grid_following_bess_15', 'gfm_bess_15', 'gfm_bess_pi_16'):
        kw = dict(bess_excel_path=ROOT/'OCV_SOC.xlsx')
        if kind.startswith('gfm'):
            kw['controller'] = GFMController(p_ref=3000., inertia_m=80., damping_d=1500.)
        if mode == 'explicit_linear': kw['aging_mode'] = 'linear'
        if kind.endswith('16'):
            model = MicrogridWithBESSPI(dc_link_bess_pi=DCLinkBESSPIController(
                vdc_ref_v=340., kp_w_per_v=100., ki_w_per_v_s=20.), **kw)
        else:
            model = MicrogridWithBESS(**kw)
        state = model.initial_state_with_bess(vdc0=340.)
        state[14] = 12.5
        probe = state.copy(); probe[0] = 330.; probe[12] = .4
        probe2 = state.copy(); probe2[0] = 350.; probe2[12] = .9
        derivatives = [model.system_dynamics(0., x) for x in (state, probe, probe2)]
        solution = solve_ivp(model.system_dynamics, (0., .02), state,
            t_eval=np.array([0., .005, .01, .015, .02]), method='RK45',
            max_step=SIM_SOLVER_MAX_STEP_S_DEFAULT, rtol=SIM_SOLVER_RTOL_DEFAULT,
            atol=SIM_SOLVER_ATOL_DEFAULT)
        if not solution.success: raise RuntimeError(solution.message)
        cases[kind] = {'initial_state': state, 'probe_states': [probe, probe2],
            'derivatives': derivatives, 'trajectory': solution.y.tolist(),
            'solver_nfev': solution.nfev,
            'config': {'rtol': SIM_SOLVER_RTOL_DEFAULT, 'atol': SIM_SOLVER_ATOL_DEFAULT,
                       'max_step_s': SIM_SOLVER_MAX_STEP_S_DEFAULT, 't_end_s': .02,
                       'controller': type(model.controller).__name__,
                       'M': model.controller.frequency_dynamics.inertia_m if kind.startswith('gfm') else None,
                       'D': model.controller.frequency_dynamics.damping_d if kind.startswith('gfm') else None,
                       'pi_kp_w_per_v': model.dc_link_bess_pi.kp_w_per_v if kind.endswith('16') else None,
                       'pi_ki_w_per_v_s': model.dc_link_bess_pi.ki_w_per_v_s if kind.endswith('16') else None,
                       'numpy': np.__version__, 'scipy': scipy.__version__,
                       'vdc_ref': model.vdc_ref, 'kp_bess': model.kp_bess,
                       'i_bess_max': model.i_bess_max, 'p_bess_max_w': model.p_bess_max_w,
                       'q_nom': model.bess.q_nom_ref_ah, 'q_initial': model.bess.q_init_case_ah,
                       'k_deg': model.bess.k_deg, 'soh_min': model.bess.soh_min,
                       'soc_min': model.bess.soc_min, 'soc_max': model.bess.soc_max,
                       'r0_nominal_ohm': model.bess.r0_nominal_ohm,
                       'r0_soh_sensitivity': model.bess.r0_soh_sensitivity,
                       'Cdc': model.plant.dcp.Cdc}}
    assert not any(name == 'blast' or name.startswith('blast.') for name in sys.modules)
    print(json.dumps(cases, allow_nan=False))


def main():
    import numpy as np
    baseline = Path(tempfile.mkdtemp(prefix='bat26_39_baseline_'))
    archive = baseline/'source.zip'
    subprocess.run(['git','archive','--format=zip',f'--output={archive}',COMMIT,'src'], cwd=ROOT, check=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(baseline)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    results = {}
    for label, source, mode in (('baseline', baseline, 'default'), ('default', ROOT, 'default'),
                                ('explicit_linear', ROOT, 'explicit_linear')):
        p = subprocess.run([sys.executable, '-B', str(__file__), '--child', str(source), mode],
                           cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        results[label] = json.loads(p.stdout)
    summary = {}
    for kind in results['baseline']:
        reference = results['baseline'][kind]
        if kind.startswith('gfm'):
            assert reference['config']['M'] == 80. and reference['config']['D'] == 1500.
        for label in ('default','explicit_linear'):
            candidate = results[label][kind]
            assert reference['config'] == candidate['config']
            assert reference['solver_nfev'] == candidate['solver_nfev']
            summary[f'{kind}_{label}'] = {}
            for key in ('initial_state','probe_states','derivatives','trajectory'):
                a=np.asarray(reference[key]); b=np.asarray(candidate[key])
                delta=float(np.max(np.abs(a-b)))
                assert np.array_equal(a,b), (kind,label,key,delta)
                summary[f'{kind}_{label}'][key+'_max_abs'] = delta
    metadata = {'baseline_commit': COMMIT, 'baseline_temporary_dir': str(baseline),
        'python': sys.version, 'executable': sys.executable,
        'excel_sha256': hashlib.sha256((ROOT/'OCV_SOC.xlsx').read_bytes()).hexdigest(),
        'current_source_sha256': {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ('src/microgrid.py','src/microgrid_bess_pi.py','src/bess/model.py','src/config.py')},
        'baseline_source_sha256': {p:hashlib.sha256((baseline/p).read_bytes()).hexdigest() for p in
            ('src/microgrid.py','src/microgrid_bess_pi.py','src/bess/model.py','src/config.py')},
        'results': results, 'comparison': summary}
    assert metadata['baseline_source_sha256']['src/config.py'] == metadata['current_source_sha256']['src/config.py']
    (HERE/'results.json').write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'baseline_commit':COMMIT, 'excel_sha256':metadata['excel_sha256'],
                      'comparison':summary},indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child': child(sys.argv[2],sys.argv[3])
    else: main()
