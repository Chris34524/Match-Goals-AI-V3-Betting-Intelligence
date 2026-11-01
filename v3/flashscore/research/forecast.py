"""Offline model probabilities. No odds transport, Value Engine or production imports."""
from .dataset import validate_features
from .models import predict
from .calibration import transform
from .training import verify
from ..contract import timestamp
from ..feature_catalog import VERSION as FEATURE_VERSION
from ..market_contract import VERSION as TARGET_VERSION


def forecast(fixture, features, artifact=None, *, allow_synthetic=False):
    result = dict(status='NO_MODEL', marker='RESEARCH / NOT_PRODUCTION', match_id=fixture.match_id,
        market=None, market_family=None, period=None, side=None, line=None, model_id=None,
        feature_set=None, probability=None, fair_odds=None, fair_odds_label='MODEL_FAIR_ODDS',
        sample_size=0, evaluation_metadata=None, brier=None, logloss=None, calibration=None,
        feature_quality=None, feature_coverage=None, blocked_reasons=[], network_calls=0,
        odds_status='UNAVAILABLE', value_status='NOT_EVALUATED', EV=None, edge=None, PickScore=None)
    if artifact is None:
        result['blocked_reasons'] = ['NO_MODEL']
        return result
    try:
        verify(artifact)
        contract = artifact['contract']
        if (contract['feature_schema_version'] != FEATURE_VERSION or
                contract['target_schema_version'] != TARGET_VERSION or contract['schema_version'] != TARGET_VERSION):
            raise ValueError('unsupported_schema')
        result.update({k:contract[k] for k in ('market','market_family','period','side','line','feature_set')})
        result.update(model_id=artifact['artifact_sha256'], sample_size=artifact['model']['sample_size'],
            evaluation_metadata=dict(status=artifact['evaluation_status'], fold_id=artifact['fold_id'],
                window=artifact['evaluation_window'],
                synthetic=artifact['synthetic'], real_performance=artifact['real_performance'],
                production_evidence=False), calibration=artifact['calibrator']['status'])
        if artifact['model']['model_status'] != 'FITTED':
            result.update(status='MODEL_NOT_VALIDATED', blocked_reasons=['MODEL_NOT_FITTED'])
            return result
        # This release deliberately has no real accreditation/validation adapter.
        if artifact['evaluation_status'] != 'DEMO_ONLY' or artifact['synthetic'] is not True:
            result.update(status='MODEL_NOT_VALIDATED', blocked_reasons=['REAL_MODEL_VALIDATION_UNAVAILABLE'])
            return result
        if not allow_synthetic:
            result.update(status='INSUFFICIENT_EVIDENCE', blocked_reasons=['SYNTHETIC_MODEL_REQUIRES_EXPLICIT_DEMO'])
            return result
        if (artifact['model']['sample_size'] < 50 or artifact['evaluation_window']['test_n'] < 25
                or artifact['evaluation_window']['temporal'] is not True):
            result.update(status='INSUFFICIENT_EVIDENCE', blocked_reasons=['MINIMUM_TRAIN_50_TEST_25_TEMPORAL_REQUIRED'])
            return result
        if fixture.provider != 'synthetic' or fixture.provider != contract['provider']:
            result.update(status='BLOCKED', blocked_reasons=['SYNTHETIC_MODEL_ON_REAL_FIXTURE_FORBIDDEN'])
            return result
        selected, reasons = validate_features(fixture, features, contract['feature_set'], contract['settlement_policy_version'])
        if reasons:
            result.update(status='INSUFFICIENT_FEATURES', blocked_reasons=reasons)
            return result
        cutoff = selected[0]['cutoff']
        if artifact['train_end'] >= fixture.match_date or timestamp(artifact['label_available_at']) >= timestamp(cutoff):
            result.update(status='BLOCKED', blocked_reasons=['MODEL_TEMPORAL_INELIGIBLE'])
            return result
        p = transform(artifact['calibrator'], predict(artifact['model'], [[f['value'] for f in selected]]))[0]
        result.update(status='AVAILABLE', probability=p, fair_odds=1/p if 0 < p <= 1 else None,
            feature_quality='COMPLETE', feature_coverage=min(f['coverage_rate'] for f in selected))
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        result.update(status='BLOCKED', blocked_reasons=['INVALID_MODEL_OR_INPUT:' + str(exc)])
    return result


def rank_forecasts(rows):
    """Highest research probabilities; high probability is not evidence of value."""
    return sorted(rows, key=lambda r:(r['probability'] is None, -(r['probability'] or 0),
                                     r['match_id'],r['model_id'] or ''))
