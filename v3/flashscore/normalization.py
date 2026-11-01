"""Explicit units and aliases; no locale guessing, imputation or count derivation."""
from .contract import DECIMALS, PERCENTAGES

ALIASES = {'passes_completed': 'completed_passes', 'saves': 'goalkeeper_saves',
           'touches_in_opposition_box': 'box_touches'}


def canonical_stat(name):
    return ALIASES.get(name, name)


def unit_for(name):
    if name in PERCENTAGES:
        return 'percent'
    if name in DECIMALS:
        return 'expected_goals'
    if name == 'cards':
        return 'typed_cards'
    return 'count'
