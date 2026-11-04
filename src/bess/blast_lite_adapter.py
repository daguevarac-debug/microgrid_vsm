"""Experimental BLAST snapshots, updated outside the fast microgrid solver.

The worker uses a separate Python 3.12.10 environment and the original model.
Only explicitly synthetic profiles are enabled until physical provenance exists.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import subprocess

from bess.aging_capacity import CapacitySnapshot


def preserve_window_state(state, *, soc_min, soc_max):
    """Carry the protected 15/16-state vector unchanged, rejecting invalid SoC."""
    try:
        values = [float(x) for x in state]
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid microgrid boundary state') from exc
    if (len(values) not in (15, 16) or not all(math.isfinite(x) for x in values)
            or not 0 <= soc_min < soc_max <= 1 or not soc_min <= values[12] <= soc_max):
        raise ValueError('boundary state or SoC violates the configured limits')
    return values


@dataclass(frozen=True)
class BlastResult:
    capacity_snapshot: CapacitySnapshot
    q: float
    q_new: float
    calendar_loss: float
    cycle_loss: float
    efc: float
    elapsed_days: float
    windows: int


class BlastLiteAdapter:
    """A persistent worker owns BLAST; no import of BLAST in the main process."""
    def __init__(self, python_executable, *, q_init_case_ah=44.1, soh_min=0.5):
        initial = CapacitySnapshot(66.0, q_init_case_ah, 1.0)
        if not math.isfinite(soh_min) or not 0 <= soh_min <= initial.soh:
            raise ValueError('invalid initial SoH limit')
        self._initial = initial
        self._soh_min = soh_min
        self._end = None
        self.history = []
        worker = Path(__file__).with_name('blast_worker.py')
        try:
            self._process = subprocess.Popen([str(python_executable), '-B', '-u', str(worker)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8')
        except OSError as exc:
            raise RuntimeError(f'cannot start BLAST Python environment: {exc}') from exc
        ready = self._read()
        if not ready.get('ready') or ready.get('cap') != 66 or ready.get('cap_2ndLife') != 46 or ready.get('qNew0') != .7:
            self.close()
            raise RuntimeError('unexpected BLAST reference capacities')
        self._q0 = ready['q0']
        self.blast_nominal_ah = ready['cap']
        self.blast_second_life_ah = ready['cap_2ndLife']
        self.blast_initial_qnew_ah = ready['qNew0'] * ready['cap']
        self.snapshot = initial

    @property
    def q0(self):
        return self._q0

    def _read(self):
        line = self._process.stdout.readline()
        if not line:
            message = self._process.stderr.read()
            self.close()
            raise RuntimeError(f'BLAST worker unavailable: {message.strip()}')
        result = json.loads(line)
        if 'error' in result:
            raise ValueError(f"BLAST rejected window: {result['error']}")
        return result

    def update(self, *, time_s, soc, temperature_c, current_2p_a, profile_kind,
               temperature_origin, current_origin, current_sign, units):
        """Update using an explicitly synthetic profile; no DC bus conversion."""
        if profile_kind != 'synthetic':
            raise ValueError('operational BLAST profiles are disabled pending physical accreditation')
        if (temperature_origin != 'synthetic_cell' or current_origin != 'synthetic_2p_group'
                or current_sign != 'positive_discharge' or units != ('s', 'fraction', 'C', 'A')):
            raise ValueError('explicit synthetic 2p/cell provenance, sign and units are required')
        try:
            arrays = [[float(v) for v in a] for a in (time_s, soc, temperature_c, current_2p_a)]
        except (TypeError, ValueError) as exc:
            raise ValueError('all four aligned physical signals are required') from exc
        t, s, temp, current = arrays
        if len(t) < 2 or any(len(a) != len(t) for a in arrays):
            raise ValueError('window requires aligned signals with at least two points')
        if (not all(math.isfinite(x) for a in arrays for x in a)
                or any(b <= a for a, b in zip(t, t[1:]))
                or any(x < 0 or x > 1 for x in s) or any(x <= -273.15 for x in temp)):
            raise ValueError('invalid timestamps, SoC or temperature')
        if self._end is not None and (t[0], s[0], temp[0]) != self._end:
            raise ValueError('time, fractional SoC and temperature must be continuous between windows')
        request = {'time_s': t, 'soc': s, 'temperature_c': temp,
                   'initial_ah': self._initial.q_init_case_ah, 'soh_min': self._soh_min}
        self._process.stdin.write(json.dumps(request, allow_nan=False) + '\n')
        self._process.stdin.flush()
        data = self._read()
        snapshot = CapacitySnapshot(66.0, self._initial.q_init_case_ah, data['q'] / self.q0)
        result = BlastResult(snapshot, data['q'], data['qNew'], data['qLoss_t'],
                             data['qLoss_EFC'], data['efc'], data['t_days'], data['windows'])
        self.snapshot = snapshot
        self._end = (t[-1], s[-1], temp[-1])
        profile = {'time_s': t, 'soc': s, 'temperature_c': temp, 'current_2p_a': current,
                   'provenance': profile_kind, 'units': units, 'current_sign': current_sign}
        profile_hash = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':'),
                                                allow_nan=False).encode('utf-8')).hexdigest()
        self.history.append({'start_s': t[0], 'end_s': t[-1], 'samples': len(t),
                             'profile_kind': profile_kind, 'sha256': profile_hash, 'result': result})
        return result

    def anchor_case(self):
        """Start a separately defined case without discarding prior BLAST history."""
        self._process.stdin.write('{"action":"anchor_case"}\n')
        self._process.stdin.flush()
        data = self._read()
        self._q0 = data['q0']
        self.snapshot = self._initial
        self.history.append({'event': 'case_start', 'q0': self.q0,
                             'efc': data['efc'], 'windows': data['windows']})
        return self.snapshot

    def close(self):
        process = getattr(self, '_process', None)
        if process is not None and process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
