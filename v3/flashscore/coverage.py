"""Denominator-aware research rates and descriptive Wilson intervals."""
from collections import Counter
from math import sqrt

from .contract import State


def rate(numerator, denominator):
    if not denominator:
        return dict(n=0, numerator=numerator, denominator=0, raw_rate=None, ci95_wilson=None)
    p, z = numerator / denominator, 1.959963984540054
    d = 1 + z*z/denominator
    center = (p + z*z/(2*denominator)) / d
    half = z * sqrt(p*(1-p)/denominator + z*z/(4*denominator**2)) / d
    return dict(n=denominator, numerator=numerator, denominator=denominator, raw_rate=p,
                ci95_wilson=[max(0.0, center-half), min(1.0, center+half)])


def tier(numerator, denominator, successful, minimum=30, assessed_fraction=1.0):
    if not denominator or successful < minimum or successful / denominator < assessed_fraction:
        return 'UNASSESSED'
    coverage = numerator / denominator
    return 'CORE' if coverage >= .8 else 'CONDITIONAL' if coverage >= .5 else 'EXPERIMENTAL'


def summarize(units, minimum, assessed_fraction):
    counts = Counter(u['state'] for u in units)
    total = len(units)
    available = counts[State.AVAILABLE.value]
    inspected = sum(u['successful_inspection'] for u in units)
    assessed = sum(counts[s.value] for s in (State.AVAILABLE, State.MISSING, State.NOT_COVERED))
    return dict(total_target_units=total, attempted_units=sum(u['attempted'] for u in units),
        successful_inspections=inspected, conclusive_assessments=assessed, states={s.value: counts[s.value] for s in State},
        successful_inspection_conditional_availability=rate(available, inspected),
        all_target_operational_completeness=rate(available, total),
        settlement_compatible_availability=rate(sum(u['settlement_compatible'] for u in units), total),
        temporal_prematch_usability=rate(sum(u['prematch_usable'] is True for u in units), total)
            if all(u['prematch_usable'] is not None for u in units) else None,
        research_tier=tier(available, total, assessed, minimum, assessed_fraction))
