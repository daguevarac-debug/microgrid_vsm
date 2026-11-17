from pathlib import Path
import json,csv,hashlib,math
p=Path('work/cross_validation')
base=json.loads(Path('outputs/validation/bess_dcdc_50hz/bess_dcdc_50hz_summary.json').read_text())
old={r['label']:r for r in base['scenarios']}
vbase=json.loads(Path('outputs/validation/vsg_50hz_interface_audit_6p5s.json').read_text())['scenarios_6p5s']
cols=['vdc_post_min_v','vdc_ss_mean_v','f_post_min_hz','rocof_abs_max_hz_s','soc_final','soh_final','i_bank_post_min_a','i_bank_post_max_a','i_bus_post_min_a','i_bus_post_max_a','pi_saturation_fraction','anti_windup_fraction','dcdc_saturation_fraction','e_dc_bus_residual_post_j','e_dcdc_conv_residual_post_j','ecm_1rc_bank_residual_max_w']
rows=[]; hashes={}
for name,b in old.items():
 f=p/(name+'.json')
 if not f.exists():continue
 n=json.loads(f.read_text()); hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
 for k in cols:
  a,bv=b.get(k),n.get(k)
  if isinstance(a,(int,float)) and isinstance(bv,(int,float)):
   rows.append(dict(case=name,metric=k,previous=a,corrected=bv,delta=bv-a))
for f in sorted(p.glob('vsg_[56]0_[24]0_[01].json')):
 n=json.loads(f.read_text());base_case=next((r for r in vbase if int(round(r['frequency_hz']))==int(round(n['frequency_hz'])) and abs(r['step']-n['step'])<1e-8 and r['bess']==n['bess']),None)
 if base_case:
  hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
  for k in ('vdc_post_min_v','vdc_final_v','frequency_post_min_hz','rocof_post_abs_max_hz_s','soc_min','soc_max','bess_current_post_min_a','bess_current_post_max_a','modulation_limited_fraction_post'):
   a,bv=base_case.get(k),n.get(k)
   if isinstance(a,(float,int)) and isinstance(bv,(float,int)): rows.append(dict(case=f.stem,metric=k,previous=a,corrected=bv,delta=bv-a))
with (p/'comparacion.csv').open('w',newline='') as fh:
 w=csv.DictWriter(fh,fieldnames=['case','metric','previous','corrected','delta'], lineterminator='\n');w.writeheader();w.writerows(rows)
summary={}
for r in rows:
 if math.isfinite(r['delta']):
  entry=summary.get(r['metric'])
  if entry is None or abs(r['delta'])>abs(entry['delta']): summary[r['metric']]={'case':r['case'],'delta':r['delta']}
(p/'comparacion_resumen.json').write_text(json.dumps({'completed_dcdc':len([x for x in old if (p/(x+'.json')).exists()]),'completed_vsg':len(list(p.glob('vsg_[56]0_[24]0_[01].json'))),'max_abs_deltas':summary,'sha256':hashes},indent=2)+'\n')
print('completed',len(hashes),'cases')
