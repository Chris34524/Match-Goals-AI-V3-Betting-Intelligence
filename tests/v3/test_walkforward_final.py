import pytest
from v3.validation.walkforward import run,folds
from v3.validation.economics import economics
from test_calibration_final import rows


def temporal_rows():
    rs=rows('OOS',1,15)
    for r in rs:r.update(features=[float(r['y'])],features_available_at=r['predicted_at'],feature_lineage='synthetic')
    return rs


def test_walkforward_multiple_folds_temporal_deterministic():
    rs=temporal_rows();a=run(rs,synthetic_test_only=True)
    assert a==run(rs,synthetic_test_only=True) and len(a['folds'])==4
    for f in a['folds']:
        sets=[set(v) for v in f['ids'].values()]
        assert not any(x&y for i,x in enumerate(sets) for y in sets[i+1:])
        assert f['economics']['economic_status']=='BLOCKED'
        assert f['model_hash'] and f['calibrator_hash']


def test_same_date_never_crosses_fold_and_oos_disjoint():
    rs=temporal_rows(); rs.append(dict(rs[0],id='same-date'))
    fs=folds(rs)
    for f in fs:
        date_sets=[{r['kickoff_at'][:10] for r in group} for group in f.values()]
        assert not any(x&y for i,x in enumerate(date_sets) for y in date_sets[i+1:])
    assert len({r['id'] for f in fs for r in f['OOS']})==sum(len(f['OOS']) for f in fs)


@pytest.mark.parametrize('field,value',[('label_available_at','2026-02-01T12:00:00Z'),('features_available_at','2026-02-01T12:00:00Z'),('temporal_accredited',False)])
def test_walkforward_leakage_rejected(field,value):
    rs=temporal_rows();rs[0][field]=value
    with pytest.raises(ValueError):run(rs,synthetic_test_only=True)


def test_walkforward_real_and_economics_missing_blocked():
    assert run([])['real_status']=='BLOCKED'
    assert economics([{}])['economic_status']=='BLOCKED'


def test_walkforward_oos_labels_do_not_change_fit():
    rs=temporal_rows();a=run(rs,synthetic_test_only=True)['folds'][0]
    rs[7]['y']=1-rs[7]['y']
    b=run(rs,synthetic_test_only=True)['folds'][0]
    assert a['model_hash']==b['model_hash'] and a['calibrator_hash']==b['calibrator_hash']
    assert a['predictions']==b['predictions']
