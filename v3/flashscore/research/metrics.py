"""Binary descriptive metrics; clipping is confined to logarithms."""
import math


def probability_bucket(p):
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('invalid_probability')
    return min(9, int(p * 10))


def logloss_component(y, p):
    q = max(1e-15, min(1 - 1e-15, p))
    return -(y * math.log(q) + (1-y) * math.log(1-q))


def binary_metrics(ys, ps):
    if not ys or len(ys) != len(ps) or any(type(y) is not int or y not in (0, 1) for y in ys):
        raise ValueError('invalid_labels')
    bins = [[] for _ in range(10)]
    for y,p in zip(ys,ps):
        bins[probability_bucket(p)].append((y,p))
    table = []
    for i, pairs in enumerate(bins):
        n = len(pairs)
        mean = sum(p for y,p in pairs)/n if n else None
        observed = sum(y for y,p in pairs)/n if n else None
        table.append(dict(bucket=i, lower=i/10, upper=(i+1)/10,
            upper_inclusive=i == 9, n=n, mean_probability=mean,
            observed_frequency=observed, absolute_gap=abs(mean-observed) if n else None))
    n = len(ys)
    return dict(n=n, brier=sum((p-y)**2 for y,p in zip(ys,ps))/n,
        logloss=sum(logloss_component(y,p) for y,p in zip(ys,ps))/n,
        accuracy=sum((p >= .5) == y for y,p in zip(ys,ps))/n,
        mean_probability=sum(ps)/n, observed_frequency=sum(ys)/n,
        calibration_error=abs(sum(ps)/n-sum(ys)/n),
        ece=sum(b['n']/n*(b['absolute_gap'] or 0) for b in table), bins=table)
