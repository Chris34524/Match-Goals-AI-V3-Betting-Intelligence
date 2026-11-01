"""Frozen chronological experiments. Real training requires a future accreditation adapter."""
from . import VERSION
from .models import CONFIG, fit, predict, registry
from .calibration import partition, fit_calibrator, transform
from .splits import expanding_folds
from .effectiveness import effectiveness
from .error_ledger import error_ledger
from ..observation_index import digest


def sealed(value):
    return dict(value, artifact_sha256=digest(value))


def verify(value):
    body = {k:v for k,v in value.items() if k != 'artifact_sha256'}
    if digest(body) != value.get('artifact_sha256'):
        raise ValueError('artifact_integrity_mismatch')


def run_experiment(rows, *, synthetic_demo=False, min_train=100, min_test=25, fold_size=50):
    if not rows:
        return dict(status='BLOCKED', reason='empty_dataset', models=[], predictions=[])
    if not synthetic_demo or not all(r['synthetic'] for r in rows):
        return dict(status='BLOCKED', reason='REAL_MODEL_TRAINING_BLOCKED_no_accreditation_adapter', models=[], predictions=[])
    # A model represents one event definition, never pooled incompatible lines/periods/sides.
    contract_fields = ('provider','market_family','market','period','side','line','entity',
                       'feature_set','feature_schema_version','schema_version','target_schema_version','settlement_policy_version')
    # entity is a fixture-specific team ID for team markets; side defines its response.
    invariant = tuple(k for k in contract_fields if k != 'entity')
    if len({digest({k:r[k] for k in invariant}) for r in rows}) != 1:
        raise ValueError('mixed_training_contracts')
    try:
        folds = expanding_folds(rows, min_train=min_train, min_test=min_test, fold_size=fold_size)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(status='BLOCKED', reason='temporal_evaluation_blocked:' + str(exc), models=[], predictions=[])
    if not folds:
        return dict(status='BLOCKED', reason='insufficient_chronological_sample', models=[], predictions=[])
    predictions, artifacts, fold_metadata, model_statuses = [], [], [], []
    for fold in folds:
        train, test = fold['train'], fold['test']
        fit_rows, cal_rows = partition(train)
        fold_metadata.append(dict(**{k:v for k,v in fold.items() if k not in ('train','test')},
            feature_set_version=rows[0]['feature_set'], target_schema=rows[0]['schema_version'],
            target_policy=rows[0]['settlement_policy_version'], model_config=CONFIG,
            train_ids=[r['target_key'] for r in train], test_ids=[r['target_key'] for r in test],
            fit_ids=[r['target_key'] for r in fit_rows], calibration_ids=[r['target_key'] for r in cal_rows]))
        for name in registry():
            model = fit(name, [r['x'] for r in fit_rows], [r['binary_label'] for r in fit_rows])
            model_statuses.append(dict(fold_id=fold['fold_id'], family=name, status=model['model_status']))
            if model['model_status'] != 'FITTED':
                continue
            cal = fit_calibrator(predict(model, [r['x'] for r in cal_rows]), [r['binary_label'] for r in cal_rows])
            # Frozen before accessing outer test labels.
            artifact = sealed(dict(version=VERSION, model=model, calibrator=cal,
                contract={k:rows[0][k] for k in invariant}, fold_id=fold['fold_id'],
                train_end=train[-1]['target_date'],
                label_available_at=max(r['label_available_at'] for r in train),
                training_ids=[r['target_key'] for r in fit_rows],
                calibration_ids=[r['target_key'] for r in cal_rows],
                evaluation_window=dict(test_start=fold['test_start'], test_end=fold['test_end'],
                    test_n=fold['test_n'], temporal=True),
                evaluation_status='DEMO_ONLY', synthetic=True, real_performance=False,
                production_evidence=False))
            model_id = artifact['artifact_sha256']
            artifacts.append(artifact)
            raw = predict(model, [r['x'] for r in test])
            for r, p, original in zip(test, transform(cal, raw), raw):
                predictions.append(dict(r, probability=p, raw_probability=original,
                    model=name, model_id=model_id, fold_id=fold['fold_id'],
                    prediction_provenance=dict(model_sha256=model_id, dataset_row_sha256=digest(r),
                        feature_hashes=r['provenance_hashes'], calibration_status=cal['status'])))
    report = effectiveness(predictions)
    # Evidence stays separate from fitted artifacts; no test labels feed model fitting.
    return sealed(dict(version=VERSION, status='DEMO_ONLY', synthetic=True, real_performance=False,
        production_evidence=False, REAL_EVALUATION='BLOCKED', REAL_MODEL_TRAINING='BLOCKED',
        dataset_sha256=digest(rows), config=CONFIG, folds=fold_metadata, models=artifacts,
        model_statuses=model_statuses, predictions=predictions, effectiveness=report,
        error_ledger=error_ledger(predictions)))
