"""Strict provider labels, zero preservation and opt-in diagnostic derivations."""
from v3.flashscore.contract import valid_value
from v3.flashscore.normalization import unit_for

LABELS = dict(zip((
    'Total Shots', 'Shots on Goal', 'Shots off Goal', 'Blocked Shots',
    'Shots insidebox', 'Shots outsidebox', 'Fouls', 'Corner Kicks', 'Offsides',
    'Ball Possession', 'Yellow Cards', 'Red Cards', 'Goalkeeper Saves',
    'Total passes', 'Passes accurate', 'Passes %'), (
    'shots', 'shots_on_target', 'shots_off_target', 'blocked_shots',
    'shots_inside_box', 'shots_outside_box', 'fouls', 'corners', 'offsides',
    'possession', 'yellow_cards', 'red_cards', 'goalkeeper_saves',
    'passes', 'completed_passes', 'pass_accuracy')))
ADDITIVE = frozenset(('corners', 'shots', 'shots_on_target', 'shots_off_target',
    'blocked_shots', 'shots_inside_box', 'shots_outside_box', 'fouls', 'offsides',
    'yellow_cards', 'red_cards', 'goalkeeper_saves', 'passes', 'completed_passes'))
DERIVATION = 'api-football-additive-ft-minus-1h-1'


def number(value, field):
    unit = unit_for(field)
    if unit == 'percent' and isinstance(value, str) and value.endswith('%'):
        try:
            value = float(value[:-1])
        except ValueError:
            return None
    return value if valid_value(field, value, unit) else None


def derive_second_half(field, ft, first_half):
    result = dict(field=field, raw_ft=ft, raw_first_half=first_half,
        formula='FT - 1H', derivation_version=DERIVATION, value=None,
        status='UNKNOWN', validation_result='non_additive_or_invalid')
    if field in ADDITIVE and all(type(x) is int and x >= 0 for x in (ft, first_half)):
        result['validation_result'] = 'FT_less_than_1H' if ft < first_half else 'valid_additive_counts'
        if ft >= first_half:
            result.update(value=ft-first_half, status='AVAILABLE')
    return result
