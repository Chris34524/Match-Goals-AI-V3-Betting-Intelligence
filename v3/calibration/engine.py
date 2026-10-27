"""Calibrator selection only on explicit CALIBRATION_VALIDATION; never final TEST."""
from copy import deepcopy
from .contract import VERSION, BLOCK_REASON, digest, sealed, verify, prediction_rows, time
from v3.models.contract import MARKETS
from .reliability import metrics
from . import platt, isotonic

METHODS = ('identity','platt','isotonic')


def apply(method, parameters, p, market='BTTS'):
    from v3.models.metrics import probability, vector
    (vector if market == '1X2' else probability)(p)
    if method not in METHODS or (market == '1X2' and method != 'identity'):
        raise ValueError('multiclass_method_incompatible' if market == '1X2' else 'unknown_method')
    return deepcopy(p) if method == 'identity' else (platt if method == 'platt' else isotonic).predict(parameters,p)


def fit(fit_rows, validation_rows, *, market='BTTS', synthetic_test_only=False):
    if market not in MARKETS:raise ValueError('unsupported_market')
    prediction_rows(fit_rows,'CALIBRATION',market,synthetic_test_only)
    prediction_rows(validation_rows,'CALIBRATION_VALIDATION',market,synthetic_test_only)
    if {r['id'] for r in fit_rows} & {r['id'] for r in validation_rows}:
        raise ValueError('partition_overlap')
    # Whole UTC dates kept together; all fit labels must be known before validation predictions.
    if max(time(r['kickoff_at']).date() for r in fit_rows) >= min(time(r['kickoff_at']).date() for r in validation_rows):
        raise ValueError('calibration_future_leakage')
    if max(time(r['label_available_at']) for r in fit_rows) >= min(time(r['predicted_at']) for r in validation_rows):
        raise ValueError('future_calibration_observation')
    for key in ('source_model_hash','label_version'):
        if len({r[key] for r in fit_rows+validation_rows}) != 1:
            raise ValueError('incomparable_predictions')
    ys=[r['y'] for r in fit_rows]; ps=[r['p'] for r in fit_rows]
    vy=[r['y'] for r in validation_rows]; vp=[r['p'] for r in validation_rows]
    candidates=[]
    for index,method in enumerate(METHODS if market != '1X2' else ('identity',)):
        params={} if method=='identity' else (platt if method=='platt' else isotonic).fit(ps,ys)
        result=metrics(vy,[apply(method,params,p,market) for p in vp],market)
        candidates.append((result['logloss'],result['brier'],index,method,params,result))
    _,_,_,method,params,post=min(candidates,key=lambda c:c[:3])
    out=dict(calibration_id=None,market=market,method=method,version=VERSION,
             fit_ids=sorted(r['id'] for r in fit_rows),validation_ids=sorted(r['id'] for r in validation_rows),
             source_model_hash=fit_rows[0]['source_model_hash'],label_version=fit_rows[0]['label_version'],
             fit_cutoff=max((r['label_available_at'] for r in fit_rows),key=time),
             available_at=max((r['label_available_at'] for r in validation_rows),key=time),parameters=params,
             pre_metrics=metrics(vy,vp,market),post_metrics=post,reliability=post['calibration'],
             selection='calibration-validation:logloss,brier,identity/platt/isotonic-v1',
             incompatible_methods=['platt','isotonic'] if market=='1X2' else [],
             status='ELIGIBLE',reason=None,synthetic_test_only=synthetic_test_only)
    out['calibration_id']=digest(out)
    return sealed(out)


def transform(manifest,p,*,cutoff,source_model_hash,allow_synthetic=False):
    verify(manifest)
    if manifest['status']!='ELIGIBLE' or manifest['source_model_hash']!=source_model_hash:
        raise ValueError('calibration_ineligible')
    if manifest['synthetic_test_only'] and not allow_synthetic:
        raise ValueError('synthetic_not_production')
    if time(manifest['available_at']) >= time(cutoff):
        raise ValueError('future_calibrator')
    return apply(manifest['method'],manifest['parameters'],p,manifest['market'])


def real_state():
    """Audit merged Phase 5 checkpoint evidence; never manufacture a real fit."""
    import json
    from pathlib import Path
    checkpoints=[json.loads(Path(f'docs/v3/models/checkpoint-5.{i}.json').read_text()) for i in range(2,7)]
    blocked=all(c['experiment_status']=='BLOCKED' and c['predictions_hash'] is None for c in checkpoints)
    return dict(real_status='BLOCKED',reason_codes=[BLOCK_REASON if blocked else 'real_prediction_adapter_requires_accreditation'],
                calibration=None,real_metrics=None,source_hash=digest(checkpoints))
