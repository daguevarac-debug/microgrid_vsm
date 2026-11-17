import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from validation import validate_gfm_integrated_system as v
name=sys.argv[1]; spec=getattr(v,name); start=time.monotonic()
rec,_,_=v.run_scenario(spec,p_ref_w=v._reference_active_power_w(),t_end_s=v.T_END_S_DEFAULT)
rec['_wall_s']=time.monotonic()-start
p=Path('work/cross_validation')/('gfm_'+name+'.json');q=p.with_suffix('.tmp');q.write_text(json.dumps(rec,indent=2,default=v._json_ready)+'\n');q.replace(p)
print(name,rec['status'],rec['_wall_s'],flush=True)
