"""Brier: binary mean square; multiclass mean SUM of class squared errors.

Log clipping epsilon=1e-15 affects logarithms only. Fixed ten reliability bins.
"""
import math
from .contract import CLASSES

EPSILON = 1e-15
BINS_VERSION = 'equal-width-10-v1'


def probability(p):
    if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('invalid_probability')


def vector(ps):
    if len(ps) != 3:
        raise ValueError('invalid_probability_vector')
    for p in ps:
        probability(p)
    if not math.isclose(sum(ps), 1, abs_tol=1e-12, rel_tol=0):
        raise ValueError('invalid_probability_sum')


def reliability(ys, ps):
    bins = []
    for i in range(10):
        pairs = [(y,p) for y,p in zip(ys,ps) if min(9,int(p*10)) == i]
        bins.append(dict(lower=i/10, upper=(i+1)/10, count=len(pairs),
                         mean_probability=sum(p for y,p in pairs)/len(pairs) if pairs else None,
                         observed_rate=sum(y for y,p in pairs)/len(pairs) if pairs else None))
    return bins


def binary_metrics(ys, ps):
    if not ys or len(ys) != len(ps) or any(y not in (0,1) for y in ys):
        raise ValueError('invalid_labels_or_lengths')
    for p in ps:
        probability(p)
    return dict(brier=sum((p-y)**2 for y,p in zip(ys,ps))/len(ys),
                logloss=-sum(y*math.log(max(EPSILON,p))+(1-y)*math.log(max(EPSILON,1-p)) for y,p in zip(ys,ps))/len(ys),
                accuracy=sum((p >= 0.5) == y for y,p in zip(ys,ps))/len(ys),
                reliability=reliability(ys,ps), bins_version=BINS_VERSION)


def multiclass_metrics(ys, ps):
    if not ys or len(ys) != len(ps) or any(y not in (0,1,2) for y in ys):
        raise ValueError('invalid_labels_or_lengths')
    for p in ps:
        vector(p)
    return dict(logloss=-sum(math.log(max(EPSILON,p[y])) for y,p in zip(ys,ps))/len(ys),
                brier=sum(sum((p[k]-(y==k))**2 for k in range(3)) for y,p in zip(ys,ps))/len(ys),
                brier_convention='mean_sum_squared_errors_no_half',
                accuracy=sum(max(range(3),key=lambda k:p[k]) == y for y,p in zip(ys,ps))/len(ys),
                per_class={name: binary_metrics([int(y==k) for y in ys],[p[k] for p in ps]) for k,name in enumerate(CLASSES)})


def base_rate(ys, multiclass=False):
    if not ys:
        raise ValueError('empty_train')
    return [sum(y==k for y in ys)/len(ys) for k in range(3)] if multiclass else sum(ys)/len(ys)
