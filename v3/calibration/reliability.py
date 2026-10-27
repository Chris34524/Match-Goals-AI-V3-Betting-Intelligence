"""Ten fixed bins [i/10,(i+1)/10), last includes 1. ECE=sum(n/N*abs(mean-y))."""
from v3.models.metrics import binary_metrics, multiclass_metrics


def reliability(ys, ps):
    metrics = binary_metrics(ys, ps)
    buckets = metrics['reliability']
    for b in buckets:
        b['absolute_calibration_error'] = abs(b['mean_probability']-b['observed_rate']) if b['count'] else None
    return dict(version='equal-width-10-ece-v1', buckets=buckets,
                ece=sum(b['count']/len(ys)*(b['absolute_calibration_error'] or 0) for b in buckets))


def metrics(ys, ps, market):
    out = multiclass_metrics(ys, ps) if market == '1X2' else binary_metrics(ys, ps)
    out['calibration'] = {name:reliability([int(y==k) for y in ys],[p[k] for p in ps])
                          for k,name in enumerate(('home','draw','away'))} if market == '1X2' else reliability(ys,ps)
    return out
