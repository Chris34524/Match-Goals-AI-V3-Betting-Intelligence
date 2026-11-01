"""Idempotent descriptive error ledger, never causal attribution."""
from ..observation_index import digest
from .metrics import probability_bucket, logloss_component


def error_ledger(predictions):
    entries = {}
    for r in predictions:
        p, y = r['probability'], r['binary_label']
        bucket = probability_bucket(p)
        hit = int(p >= .5) == y
        confidence = max(p, 1-p)
        classes = []
        if not hit and confidence >= .8:
            classes.extend(['HIGH_CONFIDENCE_MISS', 'OVERCONFIDENCE'])
        if hit and confidence < .6:
            classes.extend(['LOW_CONFIDENCE_HIT', 'UNDERCONFIDENCE'])
        key = {k:r[k] for k in ('target_key','model_id','fold_id')}
        entry = dict(entry_id=digest(key), match_id=r['match_id'], competition=r['competition_id'],
            market=r['market'], market_family=r['market_family'], period=r['period'], side=r['side'],
            model=r['model'], feature_set=r['feature_set'], fold_id=r['fold_id'],
            predicted_probability=p, predicted_class=int(p >= .5), actual=y,
            brier_component=(p-y)**2, logloss_component=logloss_component(y,p),
            probability_bucket=bucket, feature_quality=r['feature_quality'], coverage=r['coverage'],
            cutoff=r['cutoff'], prediction_provenance=r['prediction_provenance'],
            error_classes=classes, synthetic=r['synthetic'])
        if entry['entry_id'] in entries and entries[entry['entry_id']] != entry:
            raise ValueError('duplicate_prediction_conflict')
        entries[entry['entry_id']] = entry
    return [entries[key] for key in sorted(entries)]
