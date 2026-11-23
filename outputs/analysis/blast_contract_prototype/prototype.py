"""Read-only, research-only interpretation of the original BLAST instance."""
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import sys

import numpy as np
from blast.models.lmo_gr_NissanLeaf66Ah_2ndLife_2020 import Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))
from bess.aging_capacity import CapacitySnapshot


@dataclass(frozen=True)
class View:
    q: float
    q_new: float
    calendar_loss: float
    cycle_loss: float
    efc: float
    blast_nominal_ah: float
    blast_second_life_ah: float
    blast_initial_qnew_ah: float
    retention_since_case_start: float
    capacity: CapacitySnapshot


class ResearchContract:
    """Capture case anchor and read the same externally updated BLAST instance."""
    def __init__(self, battery, initial_ah, *, assume_relative_transfer):
        if type(battery) is not Lmo_Gr_NissanLeaf66Ah_2ndLife_Battery:
            raise TypeError('expected the original Nissan Leaf BLAST instance')
        if assume_relative_transfer is not True:
            raise ValueError('relative retention transfer must be acknowledged as a hypothesis')
        self._battery = battery
        self._initial_ah = initial_ah
        self._q0 = float(battery.outputs['q'][-1])
        self._last = None
        self._history = None
        self.read()

    def read(self):
        b = self._battery
        histories = {group: {k: np.array(v, copy=True) for k, v in getattr(b, group).items()}
                     for group in ('states', 'outputs', 'stressors', 'rates')}
        if self._history is not None:
            for group, values in self._history.items():
                for key, old in values.items():
                    new = histories[group][key]
                    if len(new) < len(old) or not np.array_equal(new[:len(old)], old, equal_nan=True):
                        raise ValueError('BLAST history changed or was reset')
        q = float(b.outputs['q'][-1]); qnew = float(b.outputs['qNew'][-1])
        lt = float(b.states['qLoss_t'][-1]); lc = float(b.states['qLoss_EFC'][-1])
        efc = float(b.stressors['efc'][-1]); elapsed = float(b.stressors['t_days'][-1])
        if not all(isfinite(v) for v in (q, qnew, lt, lc, efc, elapsed, self._q0)) or self._q0 <= 0:
            raise ValueError('missing or nonfinite BLAST state')
        if min(lt, lc, efc, elapsed) < 0 or abs(q-(1-lt-lc)) > 1e-12 or abs(qnew-.7*q) > 1e-12:
            raise ValueError('inconsistent original BLAST state')
        if self._last is not None and (q > self._last[0] or efc < self._last[1] or elapsed < self._last[2]):
            raise ValueError('nonmonotone capacity, EFC or time')
        # A separate case capacity and q/q0 prevent applying 0.7 or past loss twice.
        snapshot = CapacitySnapshot(66., self._initial_ah, q/self._q0)
        view = View(q, qnew, lt, lc, efc, float(b.cap), float(b.cap_2ndLife),
                    66*.7, snapshot.retention_since_case_start, snapshot)
        self._history = histories
        self._last = (q, efc, elapsed)
        return view


@dataclass(frozen=True)
class Boundary:
    soc_before: float
    soc_after: float
    stored_before_ah: float
    stored_after_ah: float
    within_operational_limits: bool


def boundary(soc, q_before_ah, q_after_ah, *, policy):
    if not all(isfinite(x) for x in (soc, q_before_ah, q_after_ah)) or not 0 <= soc <= 1 or not 0 < q_after_ah <= q_before_ah:
        raise ValueError('invalid boundary values')
    if policy == 'fractional_soc':
        after = soc
    elif policy == 'algebraic_charge':
        after = soc*q_before_ah/q_after_ah
    else:
        raise ValueError('unknown candidate policy')
    return Boundary(soc, after, soc*q_before_ah, after*q_after_ah, .1 <= after <= .9)


def validate_physical_profile(*, time_s, soc, temperature_c, current_2p_a, current_origin,
                              temperature_origin, units, current_sign):
    """Demand independently supplied group-level signals; never infer current from bus."""
    if (any(x is None for x in (time_s, soc, temperature_c, current_2p_a))
            or current_origin != '2p_group' or temperature_origin != 'cell'
            or units != ('s', 'fraction', 'C', 'A') or current_sign != 'positive_discharge'):
        raise ValueError('time, SoC, cell temperature and 2p group current with explicit origin are required')
    arrays = [np.asarray(x, dtype=float) for x in (time_s, soc, temperature_c, current_2p_a)]
    if any(a.ndim != 1 for a in arrays) or len(arrays[0]) < 2 or len({len(a) for a in arrays}) != 1:
        raise ValueError('signals must be aligned one-dimensional arrays')
    if not all(np.isfinite(a).all() for a in arrays) or np.any(np.diff(arrays[0]) <= 0):
        raise ValueError('invalid signal values or timestamps')
    if np.any((arrays[1] < 0) | (arrays[1] > 1)) or np.any(arrays[2] <= -273.15):
        raise ValueError('invalid SoC or temperature in Celsius')
    return None
