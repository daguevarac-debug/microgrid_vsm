import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from validation.validate_bess_dcdc_50hz import _build_dcdc_model,simulate_and_audit_dcdc,T_STEP_S
from validation.validate_vsg_50hz_interface import run
from config import MICROGRID_LOAD_P_NOM_W_DEFAULT as P, MICROGRID_IRRADIANCE_W_PER_M2_DEFAULT as G
out=Path('work/cross_validation'); name=sys.argv[1]; start=time.monotonic()
step=lambda t:P if t<T_STEP_S else P*1.4
const=lambda t:P
irr=lambda t:G if t<T_STEP_S else 400.0
cfg={
'step40_dcdc_soc0p60_eta0p95':dict(soc_initial=.6,eta_discharge=.95,eta_charge=.95,load_profile=step),
'step40_dcdc_soc0p12_below340v':dict(soc_initial=.12,eta_discharge=.95,eta_charge=.95,load_profile=step),
'step40_dcdc_soc0p88_above340v':dict(soc_initial=.88,eta_discharge=.95,eta_charge=.95,load_profile=step),
'step40_dcdc_soh1p00':dict(soh_case=1.,load_profile=step),
'step40_dcdc_soh0p70':dict(soh_case=.7,load_profile=step),
'step40_dcdc_soh0p55':dict(soh_case=.55,load_profile=step),
'step40_dcdc_eta1p00':dict(eta_discharge=1.,eta_charge=1.,load_profile=step),
'step40_dcdc_eta0p90':dict(eta_discharge=.9,eta_charge=.9,load_profile=step),
'step40_dcdc_bess_disabled':dict(bess_enabled=False,load_profile=step),
'irrad_drop_dcdc_eta0p95':dict(eta_discharge=.95,eta_charge=.95,load_profile=const,irradiance_profile=irr),
'irrad_drop_dcdc_eta0p90':dict(eta_discharge=.9,eta_charge=.9,load_profile=const,irradiance_profile=irr),
'irrad_drop_dcdc_pmax1200w':dict(bus_power_max_w=1200.,load_profile=const,irradiance_profile=irr),
'irrad_drop_dcdc_bess_disabled':dict(bess_enabled=False,load_profile=const,irradiance_profile=irr)}
if name in cfg:
 rec,_=simulate_and_audit_dcdc(name,_build_dcdc_model(freq_hz=50.,**cfg[name]))
else:
 _,freq,step_pct,bess=name.split('_')
 rec=run(float(freq),float(step_pct)/100,bess=='1')
rec['_wall_s']=time.monotonic()-start
path=out/(name+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(rec,indent=2,allow_nan=True)+'\n');tmp.replace(path)
print(name,rec.get('status'),rec['_wall_s'],flush=True)
