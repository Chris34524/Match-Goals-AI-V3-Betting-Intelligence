"""Research-only evidence states and predeclared baseline comparison."""
from collections import defaultdict
from .metrics import binary_metrics, probability_bucket


def evidence_state(n):
    return 'OBSERVE' if n < 50 else 'DIAGNOSE' if n < 100 else 'COMPARE_CHALLENGERS' if n < 200 else 'FORMAL_EVALUATION'


def summarize(rows):
    metrics = binary_metrics([r['binary_label'] for r in rows], [r['probability'] for r in rows])
    n = len({(r['provider'],r['match_id']) for r in rows})
    real_n = len({(r['provider'],r['match_id']) for r in rows if not r['synthetic'] and r['real_accredited']})
    return dict(metrics=metrics, unique_match_n=n, diagnostic_state=evidence_state(n),
        real_n=real_n, real_state=evidence_state(real_n), stable_conclusion=False,
        interpretation='descriptive research; synthetic observations do not satisfy real evidence')


def effectiveness(predictions):
    groups = defaultdict(list)
    dimensions = ('market','market_family','model','competition_id','period','feature_quality',
                  'coverage_bucket','probability_bucket')
    for r in predictions:
        for dimension in dimensions:
            value = (probability_bucket(r['probability']) if dimension == 'probability_bucket' else
                'COMPLETE' if r['coverage'] == 1 else 'PARTIAL' if r['coverage'] > 0 else 'NONE') if dimension in ('coverage_bucket','probability_bucket') else r[dimension]
            groups[(dimension,str(value))].append(r)
    by_model = {value:summarize(rows) for (dim,value),rows in groups.items() if dim == 'model'}
    decisions = {model:'BASELINE' if model == 'BASE_RATE' else 'CHALLENGER' for model in by_model}
    baseline = [r for r in predictions if r['model'] == 'BASE_RATE']
    comparable = lambda rs: {(r['target_key'],r['fold_id']) for r in rs}
    if baseline:
        bm = summarize(baseline)['metrics']
        for model in sorted(by_model):
            if model == 'BASE_RATE':
                continue
            candidate = [r for r in predictions if r['model'] == model]
            cm = by_model[model]['metrics']
            good = (comparable(candidate) == comparable(baseline)
                and by_model[model]['unique_match_n'] >= 100
                and len({r['fold_id'] for r in candidate}) >= 2
                and cm['brier'] < bm['brier'] and cm['logloss'] < bm['logloss']
                and cm['ece'] <= bm['ece'] + .01)
            for fold_id in {r['fold_id'] for r in candidate}:
                c = summarize([r for r in candidate if r['fold_id'] == fold_id])['metrics']
                b = summarize([r for r in baseline if r['fold_id'] == fold_id])['metrics'] if comparable(candidate) == comparable(baseline) else None
                good = good and b is not None and c['brier'] <= b['brier']+.01 and c['logloss'] <= b['logloss']+.01
            if good:
                decisions[model] = 'DEMO_ONLY' if any(r['synthetic'] for r in candidate) else (
                    'RESEARCH_WINNER' if by_model[model]['real_n'] >= 100 else 'CHALLENGER')
    # Single winner under frozen ordering, no accuracy-based ranking.
    eligible = sorted((m for m in decisions if decisions[m] in ('DEMO_ONLY','RESEARCH_WINNER')),
        key=lambda m:(by_model[m]['metrics']['brier'],by_model[m]['metrics']['logloss'],m))
    for m in eligible[1:]:
        decisions[m] = 'CHALLENGER'
    return dict(by_model=by_model, selection=decisions,
        selection_rule='same folds; >=100 unique fixtures; >=2 folds; both losses strictly improve; ECE regression <=.01; each fold losses regression <=.01; rank Brier,LogLoss,name',
        segments=[dict(dimension=dim, value=value, **summarize(rows)) for (dim,value),rows in sorted(groups.items())])
