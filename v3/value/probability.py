"""Pure finite probability and decimal-price arithmetic."""
from v3.odds.contract import finite


def probability(p):
    if not finite(p) or not 0 <= p <= 1:
        raise ValueError('invalid_probability')
    return p


def fair_odds(p):
    probability(p)
    if p == 0:
        return None
    result = 1 / p
    if not finite(result):
        raise ValueError('nonfinite_computation')
    return result


def implied_probability(odds):
    if not finite(odds) or odds <= 1:
        raise ValueError('invalid_odds')
    return 1 / odds
