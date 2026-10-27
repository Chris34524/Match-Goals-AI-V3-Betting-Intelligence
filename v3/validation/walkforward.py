"""Expanding distinct UTC date windows, frozen configuration, no OOS tuning.

Features must be accredited pre-cutoff. Model TRAIN labels precede calibration;
calibration-fit labels precede selection; selection labels precede OOS prediction.
"""
from copy import deepcopy
from v3.calibration.contract import time, digest, sealed, prediction_rows
from v3.calibration.engine import fit, transform
from v3.calibration.reliability import metrics
from v3.models.binary import Logistic
from v3.models.multiclass import Softmax
from v3.models.contract import CONFIGS
from .economics import economics

VERSION='expanding-distinct-utc-dates-v1'


def folds(rows, train_dates=3, calibration_dates=2, validation_dates=2, oos_dates=2):
    sizes=(train_dates,calibration_dates,validation_dates,oos_dates)
    if any(type(n) is not int or n<1 for n in sizes):raise ValueError('invalid_window')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('duplicate_id')
    dates=sorted({time(r['kickoff_at']).date() for r in rows})
    result=[]
    for end in range(sum(sizes[:3]),len(dates)-oos_dates+1,oos_dates):
        bounds=(0,end-validation_dates-calibration_dates,end-validation_dates,end,end+oos_dates)
        parts={}
        for name,lo,hi in zip(('TRAIN','CALIBRATION','CALIBRATION_VALIDATION','OOS'),bounds,bounds[1:]):
            parts[name]=sorted([deepcopy(r) for r in rows if time(r['kickoff_at']).date() in dates[lo:hi]],key=lambda r:(time(r['kickoff_at']),r['id']))
        result.append(parts)
    return result


def run(rows, *, market='BTTS', synthetic_test_only=False, **windows):
    if not rows:return dict(real_status='BLOCKED',reason_codes=['phase5_no_accredited_temporal_predictions'],folds=[])
    dimensions={len(r['features']) for r in rows}
    if len(dimensions)!=1 or 0 in dimensions:raise ValueError('feature_dimension')
    import math
    for r in rows:
        if r.get('feature_lineage') is None or not time(r['features_available_at']) <= time(r['cutoff']) < time(r['kickoff_at']):raise ValueError('feature_temporal_invalid')
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in r['features']):raise ValueError('invalid_feature')
        prediction_rows([dict(r,partition='OOS',p=[1/3]*3 if market=='1X2' else .5)],'OOS',market,synthetic_test_only)
    outputs=[]
    # One fixed predeclared model configuration; no fold-to-fold retuning.
    for index,parts in enumerate(folds(rows,**windows)):
        names=('TRAIN','CALIBRATION','CALIBRATION_VALIDATION','OOS')
        for left,right in zip(names,names[1:]):
            if max(time(r['label_available_at']) for r in parts[left]) >= min(time(r['predicted_at']) for r in parts[right]):raise ValueError('fold_label_leakage')
        model=(Softmax() if market=='1X2' else Logistic()).fit([r['features'] for r in parts['TRAIN']],[r['y'] for r in parts['TRAIN']],dict(CONFIGS[1]))
        predicted={}
        for name in names[1:]:
            predicted[name]=[dict(r,partition=name,p=p,source_model_hash=model.model_hash) for r,p in zip(parts[name],model.predict_proba([r['features'] for r in parts[name]]))]
        calibrator=fit(predicted['CALIBRATION'],predicted['CALIBRATION_VALIDATION'],market=market,synthetic_test_only=synthetic_test_only)
        oos=predicted['OOS']
        ps=[transform(calibrator,r['p'],cutoff=r['cutoff'],source_model_hash=model.model_hash,allow_synthetic=synthetic_test_only) for r in oos]
        outputs.append(sealed(dict(fold_id=f'fold-{index:04d}',status='PASS',
            ranges={k:[v[0]['kickoff_at'],v[-1]['kickoff_at']] for k,v in parts.items()},
            ids={k:[r['id'] for r in v] for k,v in parts.items()},model_hash=model.model_hash,
            calibrator_hash=calibrator['hash'],metrics=metrics([r['y'] for r in oos],ps,market),
            economics=economics(oos,allow_synthetic=synthetic_test_only),
            predictions=[dict(id=r['id'],original_probability=r['p'],calibrated_probability=p) for r,p in zip(oos,ps)],
            synthetic_test_only=synthetic_test_only)))
    return sealed(dict(version=VERSION,config=CONFIGS[1],config_hash=digest(CONFIGS[1]),
                       status='PASS' if outputs else 'BLOCKED',folds=outputs,synthetic_test_only=synthetic_test_only))
