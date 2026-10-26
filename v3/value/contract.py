"""Deterministic JSON contract shared with the canonical odds layer."""
from v3.odds.contract import canonical_json, finite, timestamp, nonempty
from . import VERSION

IDENTITY = ('internal_match_id', 'market', 'selection', 'line', 'provider', 'bookmaker')
METRICS = ('fair_odds', 'implied_probability_raw', 'market_probability_no_vig',
           'overround', 'absolute_edge', 'relative_edge', 'ev_per_unit')


def safe(value):
    """Invalid inputs remain blocked, but cannot leak nonfinite JSON numbers."""
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, float) and not finite(value):
        return None
    return value


def serialize(value):
    return canonical_json(value)
