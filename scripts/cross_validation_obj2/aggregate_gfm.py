"""Aggregate four separately completed GFM runs without declaring partial runs complete."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / 'src'))
from validation.validate_gfm_integrated_system import _comparison_record, _overall_status, _json_ready

out = Path('work/cross_validation')
names = ('STEADY', 'STEP_20', 'STEP_40', 'STEP_20_BESS_PI')
steady, step20, step40, bess_pi = [
    json.loads((out / f'gfm_{name}_SPEC.json').read_text()) for name in names
]
scenarios = [steady, step20, step40, _comparison_record(step20, bess_pi)]
report = {'scenario_count': 4, 'simulation_count': 4,
          'status': _overall_status(scenarios), 'scenarios': scenarios}
(out / 'gfm_completo.json').write_text(json.dumps(report, indent=2, default=_json_ready) + '\n')
print('GFM:', report['status'])
