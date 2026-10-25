"""Small runtime checks shared by the isolated dataset adapters."""
from datetime import datetime
import math


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.utcoffset() is not None else None
    except ValueError:
        return None


def day(value):
    if not isinstance(value, str):
        return None
    for fmt in ('%Y-%m-%d', '%d.%m.%y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def number(value, maximum=None):
    return (type(value) in (int, float) and math.isfinite(value)
            and value >= 0 and (maximum is None or value <= maximum))


def prediction_errors(prediction):
    errors = []
    for key, value in prediction.items():
        if value is not None and (key.startswith('lambda_') or key.startswith('p_')):
            if not number(value, 1 if key.startswith('p_') else None):
                errors.append('invalid_prediction:' + key)
    # Absolute tolerance covers source decimal rounding, never rescales values.
    for keys, expected, reason in (
        (('lambda_home', 'lambda_away'), prediction.get('lambda_total'), 'lambda_sum'),
        (('p_home', 'p_draw', 'p_away'), 1, 'probability_sum'),
    ):
        values = [prediction.get(k) for k in keys]
        if expected is not None and all(number(v) for v in values) and number(expected):
            if not math.isclose(sum(values), expected, rel_tol=0, abs_tol=0.0002):
                errors.append(reason)
    return errors


def label_values(home, away):
    total = home + away
    return dict(total_goals=total, label_btts=home > 0 and away > 0,
                label_1x2='1' if home > away else '2' if away > home else 'X',
                **{'label_over_' + str(n) + '_5': total > n + .5 for n in range(1, 5)})
