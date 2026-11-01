"""Experimental FS-4 catalog. Does not extend the production catalog."""
from dataclasses import dataclass

VERSION = 'fs-features-1'


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    metric: str
    period: str = 'FT'
    orientation: str = 'for'
    windows: tuple = (5, 10)
    denominator: str | None = None


def _catalog():
    rows = []
    for name, metric in (('goals', 'goals_ft'), ('goals_1H', 'goals_first_half'),
                         ('goals_2H', 'goals_second_half'), ('corners', 'corners'),
                         ('corners_1H', 'corners'), ('corners_2H', 'corners'),
                         ('cards', 'cards'), ('fouls', 'fouls'), ('shots', 'shots'),
                         ('sot', 'shots_on_target'), ('xg', 'xg'), ('xgot', 'xgot'),
                         ('big_chances', 'big_chances')):
        period = '1H' if '1H' in name else '2H' if '2H' in name else 'FT'
        windows = (5, 10, 20) if name in ('goals', 'goals_1H', 'goals_2H', 'corners') else (5, 10)
        for orientation in ('for', 'against'):
            rows.append(FeatureSpec(name + '_' + orientation, metric, period, orientation, windows))
    for metric in ('xa', 'box_touches', 'goalkeeper_saves', 'xgot_faced', 'goals_prevented',
                   'tackles', 'interceptions', 'clearances'):
        rows.append(FeatureSpec(metric, metric))
    for name, numerator, denominator in (('cards_per_foul', 'cards', 'fouls'),
                                         ('shot_accuracy', 'shots_on_target', 'shots'),
                                         ('xg_per_shot', 'xg', 'shots')):
        rows.append(FeatureSpec(name, numerator, denominator=denominator))
    return tuple(sorted(rows, key=lambda s: s.name))


CATALOG = _catalog()
BY_NAME = {spec.name: spec for spec in CATALOG}
