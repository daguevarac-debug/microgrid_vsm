"""BAT26-55 N2: static protections, followed by four global profile-E solves."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import scipy
from scipy.integrate import RK45, solve_ivp
from validate_bat26_55_n1_profile import *
from bess.dc_dc_adapter import convert_power

OUT = ROOT / 'outputs/validation/bat26_55_n2_protections.json'

def diagnose_strict_rhs():
    """Reproduce the former strict check and retain RK45's last accepted state."""
    model, pack = make_model()
    x = model.initial_state_with_bess(); x[12] = pack.soc_max; x[0] = 339.999
    def strict_rhs(t, y):
        if y[14] < 0:
            raise ValueError(f'z_deg={y[14]!r} at t={t!r}')
        return model.system_dynamics(t, y)
    solver = RK45(strict_rhs, 0, x, .002, rtol=RTOL, atol=ATOL, max_step=MAX_STEP_S)
    try:
        while solver.status == 'running':
            solver.step()
    except ValueError as exc:
        return {'strict_exception': str(exc), 'last_accepted_t_s': float(solver.t),
                'last_accepted_z_ah': float(solver.y[14]), 'nfev': solver.nfev}
    return {'strict_exception': None, 'last_accepted_t_s': float(solver.t),
            'last_accepted_z_ah': float(solver.y[14]), 'nfev': solver.nfev}

def make_model():
    pack = Leaf48ModulePack(q_init_case_ah=QEFF_AH)
    model = MicrogridWithBESS(controller=GFMController(p_ref=P_REF_W, inertia_m=M, damping_d=D),
        bess_model=build_battery(QEFF_AH), irradiance_profile=irradiance_profile,
        load_profile=load_profile, leaf_pack=pack, dcdc_parameters=fixture_parameters(pack),
        capacity_snapshot=pack.capacity(), aging_mode='blast', blast_profile_kind='synthetic')
    return model, pack

def static_checks():
    model, pack = make_model()
    checks = {}
    for soc, vdc, blocked in ((.1,330,True),(.1,350,False),(.9,350,True),(.9,330,False)):
        x = model.initial_state_with_bess(); x[12] = soc; x[0] = vdc
        s = model.integrated_signals(0, x)
        key = f'soc_{soc}_vdc_{vdc}'
        checks[key+'_block_flag'] = bool(s['dcdc_soc_blocked']) == blocked
        checks[key+'_direction'] = (s['i_pack'] == 0 and s['p_bus'] == 0) if blocked else (s['i_pack'] * (340-vdc) > 0)
    x = model.initial_state_with_bess(); x[0] = 330
    zero = model.system_dynamics(0, x)
    x[14] = -1e-9
    checks['rhs_tiny_negative_matches_zero'] = np.allclose(model.system_dynamics(0,x),zero,rtol=0,atol=0)
    checks['throughput_derivative_unchanged'] = zero[14] == abs(model.integrated_signals(0, [*x[:14],0])['i_pack'])/3600
    x[14] = -1.01e-9
    try: model.system_dynamics(0,x)
    except ValueError: checks['rhs_significant_negative_rejected'] = True
    else: checks['rhs_significant_negative_rejected'] = False
    p = fixture_parameters(pack)
    common = dict(parameters=p, bus_voltage_v=340, ocv_v=3.75, vrc_v=0, r0_ohm=.000970, soc=.6, soc_min=.1, soc_max=.9)
    for name, changes, status in (
        ('under', {'vrc_v': 2}, 'unit_undervoltage'),
        ('over', {'vrc_v': -2}, 'unit_overvoltage'),
        ('bus_zero', {'bus_voltage_v': 0}, 'bus_voltage_nonpositive'),
        ('bus_negative', {'bus_voltage_v': -1}, 'bus_voltage_nonpositive')):
        for request in (-1000,0,1000):
            r = convert_power(bus_power_request_w=request, **(common | changes))
            checks[f'{name}_{request}_status'] = r.protection_status == status
            checks[f'{name}_{request}_zero'] = (r.unit_current_a,r.bus_current_a,r.bank_power_w,r.bus_power_w,r.loss_power_w) == (0,0,0,0,0)
        r = convert_power(bus_power_request_w=1000, **common)
        checks[name+'_recovery'] = r.protection_status == 'ok' and r.bus_power_w > 0
    return checks

def run_case(soc, vdc):
    model, pack = make_model(); x = model.initial_state_with_bess(); x[12]=soc; x[0]=vdc
    minimum_stage = 0.; negatives = 0
    def rhs(t, y):
        nonlocal minimum_stage, negatives
        minimum_stage = min(minimum_stage,float(y[14])); negatives += int(y[14] < 0)
        return model.system_dynamics(t,y)
    start = time.perf_counter()
    sol = solve_ivp(rhs,(0,T_END_S),x,method='RK45',rtol=RTOL,atol=ATOL,max_step=MAX_STEP_S,dense_output=True)
    elapsed = time.perf_counter()-start
    checks = {'solver_success': bool(sol.success), 'finite': bool(np.all(np.isfinite(sol.y))),
              'state_count_15': sol.y.shape[0] == 15,
              'accepted_throughput_nonnegative': bool(np.all(sol.y[14] >= 0)),
              'accepted_throughput_monotonic_within_atol': bool(np.all(np.diff(sol.y[14]) >= -ATOL)),
              'soc_in_bounds': bool(np.all(sol.y[12] >= pack.soc_min-1e-9) and np.all(sol.y[12] <= pack.soc_max+1e-9))}
    if not sol.success or not checks['accepted_throughput_nonnegative']:
        return {'soc_initial':soc,'vdc_initial':vdc,'checks':checks,'solver':{'success':bool(sol.success),'message':sol.message,'nfev':sol.nfev,'elapsed_s':elapsed},'minimum_rhs_z_ah':minimum_stage,'negative_rhs_calls':negatives}
    t=np.linspace(0,T_END_S,round(T_END_S/SAMPLE_DT_S)+1); y=sol.sol(t)
    rows=[model.integrated_signals(float(tt),y[:,i]) for i,tt in enumerate(t)]
    arr=lambda k: np.array([r[k] for r in rows],dtype=float)
    ip,ib,pb,pp,loss,v=map(arr,('i_pack','i_bus','p_bus','p_pack','p_dcdc_loss','Vdc'))
    blocked=arr('dcdc_soc_blocked') > .5
    checks.update({'vdc_positive':bool(np.all(v>0)), 'zero_when_blocked':bool(np.all((ip[blocked]==0)&(ib[blocked]==0)&(pb[blocked]==0))),
        'power_balance':bool(np.all(np.abs(pp-pb-loss)<=1e-8+1e-10*np.maximum.reduce((abs(pp),abs(pb),abs(loss),np.ones_like(v))))),
        'bus_power_identity':bool(np.all(np.abs(pb-v*ib)<=1e-8+1e-10*np.maximum(abs(pb),abs(v*ib)))),
        'pack_voltage_envelope':bool(np.all((arr('v_pack')>=pack.minimum_voltage_v)&(arr('v_pack')<=pack.maximum_voltage_v))),
        'converter_status_ok':all(r['dcdc_protection_status']=='ok' for r in rows),
        'pack_current_limit':bool(np.max(abs(ip))<=UNIT_CURRENT_LIMIT_A+1e-8),
        'bus_current_limit':bool(np.max(abs(ib))<=BUS_CURRENT_LIMIT_A+1e-8),
        'bus_power_limit':bool(np.max(abs(pb))<=BUS_POWER_LIMIT_W+1e-8)} )
    # A boundary must block its forbidden direction and permit the reverse.
    forbidden=(v>340) if soc==.9 else (v<340)
    starts_blocked = (soc == .1 and vdc < 340) or (soc == .9 and vdc > 340)
    checks['initial_directional_response'] = bool(blocked[0]) == starts_blocked
    if starts_blocked:
        checks['observed_directional_block'] = bool(np.any(blocked & forbidden))
    checks['observed_recovery']=bool(np.any(ip>0) if soc==.9 else np.any(ip<0))
    return {'soc_initial':soc,'vdc_initial':vdc,'checks':checks,'solver':{'success':bool(sol.success),'message':sol.message,'nfev':sol.nfev,'elapsed_s':elapsed,'accepted_points':len(sol.t)},'minimum_rhs_z_ah':minimum_stage,'negative_rhs_calls':negatives,'minimum_accepted_z_ah':float(np.min(sol.y[14])),'metrics':{'vdc_min_v':float(min(v)),'vdc_max_v':float(max(v)),'soc_min':float(min(y[12])),'soc_max':float(max(y[12])),'blocked_samples':int(sum(blocked)),'i_pack_min_a':float(min(ip)),'i_pack_max_a':float(max(ip))}}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--static',action='store_true'); parser.add_argument('--output',type=Path,default=OUT); args=parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new run path')
    started=datetime.now(timezone.utc); clock=time.perf_counter(); checks=static_checks()
    report={'task':'BAT26-55 N2','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'command':sys.argv,'utc_start':started.isoformat(),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
        'profile':'N1 E, 1.2 s; RK45 rtol=1e-6 atol=1e-9 max_step=5e-5 s; sample 0.5 ms',
        'scope':'hypothetical converter; internal numerical validation; no upper bus voltage protection is modelled',
        'strict_rhs_diagnostic':diagnose_strict_rhs(),
        'static':{'checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL'},'dynamic':[]}
    def save_progress():
        report['utc_end'] = datetime.now(timezone.utc).isoformat()
        report['elapsed_s'] = time.perf_counter() - clock
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    report['status'] = 'BLOCKED'
    save_progress()
    if not args.static and all(checks.values()):
        for soc,vdc in ((.1,330),(.1,350),(.9,330),(.9,350)):
            report['current_scenario'] = {'soc_initial': soc, 'vdc_initial': vdc}
            save_progress()
            print(f'Running SoC={soc}, Vdc={vdc}',flush=True)
            try: case=run_case(soc,vdc)
            except Exception as e: case={'soc_initial':soc,'vdc_initial':vdc,'checks':{'exception':False},'error':repr(e)}
            report['dynamic'].append(case)
            save_progress()
            print(json.dumps(case),flush=True)
    report['status']='PASS' if all(checks.values()) and (args.static or (len(report['dynamic'])==4 and all(all(c['checks'].values()) for c in report['dynamic']))) else 'FAIL'
    report['design_review'] = {'status': 'REVIEW', 'reason': 'No upper DC bus voltage protection is modelled; observed voltage is not a safety assessment.'}
    report['exit_code'] = 0 if report['status'] == 'PASS' else 1
    report.pop('current_scenario', None)
    save_progress()
    print(f"{report['status']}: {args.output}",flush=True)
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
