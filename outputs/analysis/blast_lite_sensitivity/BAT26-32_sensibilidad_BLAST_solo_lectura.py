"""BAT26-32: reproduccion matematica controlada, SIN correr ni alterar microgrid_vsm.

Copia SOLAMENTE la forma de la ley y coeficientes publicos de BLAST-Lite:
NatLabRockies/BLAST-Lite, lmo_gr_NissanLeaf66Ah_2ndLife_2020.py,
BatteryDegradationModel._update_power_state.

Los EFC son ENTRADA controlada; NO se infieren de ciclos de Braco.
Q0=44.1Ah es sensibilidad hipotetica con la misma ley relativa,
NO reparametrizacion ni validacion de BLAST.
"""
from pathlib import Path
import csv, math, json

OUT=Path('/mnt/data')
KCAL_A=3.25e8; KCAL_B=-7580.0; KCAL_C=162.0; PCAL=0.464
KCYC=7.58e-5; PCYC=1.08

def update_power_state(y0, dx, k, p):
    if y0==0:
        dydx=0.0 if dx==0 else k*dx**p/dx
    else:
        dydx=0.0 if dx==0 else k*p*((y0/k)**((p-1)/p))
    return max(0.0,y0+dydx*dx)

def run(days=365.,efc=183.,temp_c=25.,soc=0.5, n=365):
    T=temp_c+273.15
    k_cal=KCAL_A*math.exp(KCAL_B/T)*math.exp(KCAL_C*soc/T)
    qt=qc=0.0
    dt=days/n; de=efc/n
    for _ in range(n):
        qt=update_power_state(qt,dt,k_cal,PCAL)
        qc=update_power_state(qc,de,KCYC,PCYC)
    return {'days':days,'EFC_controlados':efc,'temp_C':temp_c,'SoC_medio':soc,
            'n_pasos':n,'k_cal':k_cal,'qLoss_cal':qt,'qLoss_cyc':qc,
            'q_relativo':1-qt-qc}

cases=[('inicio',0,0,25,.5),('solo_calendario',365,0,25,.5),
       ('solo_ciclado',0,183,25,.5),('combinado_25C',365,183,25,.5),
       ('combinado_20C',365,183,20,.5),('combinado_30C',365,183,30,.5),
       ('combinado_SoC20',365,183,25,.2),('combinado_SoC80',365,183,25,.8)]
rows=[]
for name,days,efc,T,soc in cases:
    res=run(days,efc,T,soc)
    for q0 in (46.2,44.1):
        row={'caso':name,'Q0_Ah':q0,'Q0_tipo':'BLAST_original' if q0==46.2 else 'hipotesis_trasladada',**res,
             'Q_final_Ah':res['q_relativo']*q0,'perdida_Ah':q0*(1-res['q_relativo']),
             'SoH_sobre_66':res['q_relativo']*q0/66.0}
        rows.append(row)

path=OUT/'BAT26-32_BLAST_caso_controlado_Q0_y_calendario.csv'
with path.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
# Control de convergencia numerica del integrador incremental transcrito
checks={str(n):run(n=n) for n in (365,3650,36500)}
assert rows[0]['q_relativo']==1.0
assert all(0 <=r['qLoss_cal']<1 and 0<=r['qLoss_cyc']<1 for r in rows)
assert abs(checks['3650']['q_relativo']-checks['36500']['q_relativo'])<1e-3
assert rows[6]['Q_final_Ah']>0
meta={'source': 'BLAST-Lite GitHub codigo publico; reproduce forma incremental y coeficientes pero NO invoca paquete BLAST instalado',
      'not_validation':True,'sensitivity': 'Q0 44.1Ah es transformacion hipotesis no un ajuste calibrado de NissanLeaf66Ah',
      'EFC': 'EFC fijados como input; no convertir ciclos de Braco ni incorporar RPT',
      'T_SoC': 'constantes durante el horizonte. Modelos mas completos promedian kcal instantaneo en trayectorias T/SoC',
      'steps':checks,'files':[path.name]}
(OUT/'BAT26-32_BLAST_caso_controlado_metodologia.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
for r in rows:
 if r['Q0_tipo']=='BLAST_original': print(f"{r['caso']:<19} qcal={r['qLoss_cal']:.6f} qcyc={r['qLoss_cyc']:.6f} Q46.2={r['Q_final_Ah']:.4f} Q44.1={next(s['Q_final_Ah'] for s in rows if s['caso']==r['caso'] and s['Q0_Ah']==44.1):.4f}")
print('convergencia:', {k: round(v['q_relativo'],8) for k,v in checks.items()})
print('OUTPUT',path)
