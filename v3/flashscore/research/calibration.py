"""Chronological held-out Platt calibration. Outer labels are not an input."""
import math
from .models import sigmoid
from ..contract import timestamp


def logit(p):
    p = max(1e-15, min(1 - 1e-15, p))
    return math.log(p / (1 - p))


def partition(train, *, minimum=50):
    if minimum < 50:
        raise ValueError('calibration_minimum_must_be_50')
    dates = sorted({r['target_date'] for r in train})
    if len(dates) < 2:
        return train, []
    boundary = dates[max(1, int(len(dates) * .75))]
    fit_rows = [r for r in train if r['target_date'] < boundary]
    cal_rows = [r for r in train if r['target_date'] >= boundary]
    if len(fit_rows) < minimum or len(cal_rows) < minimum or len({r['binary_label'] for r in cal_rows}) < 2:
        return train, []
    if max(timestamp(r['label_available_at']) for r in fit_rows) >= min(timestamp(r['cutoff']) for r in cal_rows):
        raise ValueError('calibration_label_leakage')
    return fit_rows, cal_rows


def fit_calibrator(ps, ys):
    if len(ps) != len(ys) or len(ps) < 50 or len(set(ys)) < 2:
        return dict(status='UNASSESSED', reason='minimum_50_and_two_classes_required')
    if any(type(y) is not int or y not in (0, 1) for y in ys) or any(not 0 <= p <= 1 for p in ps):
        raise ValueError('invalid_calibration_data')
    xs = [logit(p) for p in ps]
    a, b = 1.0, 0.0
    for _ in range(600):
        errors = [sigmoid(a*x+b)-y for x,y in zip(xs,ys)]
        a -= .01 * sum(e*x for e,x in zip(errors,xs)) / len(xs)
        b -= .01 * sum(errors) / len(xs)
    return dict(status='FITTED', method='platt-v1', n=len(ps), a=a, b=b)


def transform(calibrator, ps):
    return [sigmoid(calibrator['a'] * logit(p) + calibrator['b']) for p in ps] if calibrator['status'] == 'FITTED' else list(ps)
