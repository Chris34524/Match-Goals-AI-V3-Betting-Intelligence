"""Independent count models; descriptive temporal holdout, never calibration fit."""
import math
from statistics import mean, variance


def fit(values, family='auto', expectation=None):
    if not values or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('valid_count_sample_required')
    mu = mean(values) if expectation is None else expectation
    var = variance(values) if len(values) > 1 else None
    # Method of moments. Overdispersion is descriptive, not evidence of calibration.
    alpha = max(0.0, (var - mean(values)) / mean(values)**2) if var and mean(values) else 0.0
    selected = 'negative_binomial' if family == 'negative_binomial' or (
        family == 'auto' and len(values) >= 10 and alpha > 0) else 'poisson'
    if selected == 'negative_binomial' and alpha <= 1e-12:
        selected = 'poisson'
    return dict(family=selected, mean=mu, variance_observed=var, n=len(values),
                dispersion_alpha=alpha if selected == 'negative_binomial' else 0.0,
                estimation='method_of_moments' if selected == 'negative_binomial' else 'sample_mean',
                calibrated=False)


def logpmf(k, model):
    mu, alpha = model['mean'], model['dispersion_alpha']
    if mu == 0:
        return 0.0 if k == 0 else -math.inf
    if alpha == 0:
        return -mu + k * math.log(mu) - math.lgamma(k + 1)
    r = 1 / alpha
    return (math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
            - r * math.log1p(mu / r) + k * (math.log(mu) - math.log(r + mu)))


def over(line, models):
    """Convolve only the finite lower tail; retain all upper-tail probability."""
    k = math.floor(line)
    distribution = [1.0] + [0.0] * k
    for model in models:
        pmf = [math.exp(logpmf(i, model)) for i in range(k + 1)]
        distribution = [sum(distribution[j] * pmf[i-j] for j in range(i + 1)) for i in range(k + 1)]
    return max(0.0, min(1.0, 1 - sum(distribution)))


def evaluate(values, lines):
    """Values in oldest-first order. Fixed 70/30 holdout; no selection or refit."""
    split = int(len(values) * .7)
    if split < 10 or len(values) - split < 5:
        return dict(status='INSUFFICIENT_DATA', n=len(values), metrics=None,
                    reason='requires_at_least_10_train_and_5_validation', calibrated=False)
    train, validation = values[:split], values[split:]
    metrics = {}
    for family in ('poisson', 'negative_binomial'):
        model = fit(train, family)
        probabilities = [over(line, [model]) for line in lines]
        brier = sum((p - (y > line))**2 for y in validation for line, p in zip(lines, probabilities))
        metrics[family] = dict(fitted_family=model['family'], model=model,
            count_log_loss=-sum(logpmf(int(y), model) for y in validation)/len(validation)
                if all(logpmf(int(y), model) > -math.inf for y in validation) else None,
            brier=brier/(len(validation)*len(lines)),
            reliability=[dict(line=line, predicted=p, observed=sum(y > line for y in validation)/len(validation),
                              n=len(validation)) for line, p in zip(lines, probabilities)])
    return dict(status='EXPERIMENTAL', split='chronological_70_30', n_train=len(train),
                n_validation=len(validation), metrics=metrics, calibrated=False,
                limitation='Descriptive holdout only; no OOS accreditation or calibrated model claim.')
