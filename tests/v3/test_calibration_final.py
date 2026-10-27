import copy
import pytest
from v3.calibration import engine, platt, isotonic
from v3.calibration.reliability import reliability


def rows(partition='CALIBRATION',start=1,n=4):
    return [dict(id=f'{partition}-{i}',partition=partition,p=[0,.2,.8,1][i%4],y=i%2,
                 predicted_at=f'2026-01-{start+i:02d}T09:00:00Z',cutoff=f'2026-01-{start+i:02d}T10:00:00Z',
                 kickoff_at=f'2026-01-{start+i:02d}T12:00:00Z',label_available_at=f'2026-01-{start+i:02d}T15:00:00Z',
                 source_model_hash='synthetic-model-hash',label_version='regulation-v1',
                 temporal_lineage='synthetic fixture',temporal_accredited=True,synthetic_test_only=True) for i in range(n)]


def calibration():
    return engine.fit(rows(),rows('CALIBRATION_VALIDATION',6),synthetic_test_only=True)


def test_calibration_deterministic_original_preserved():
    rs=rows(); original=copy.deepcopy(rs)
    assert engine.fit(rs,rows('CALIBRATION_VALIDATION',6),synthetic_test_only=True)==calibration()
    assert rs==original
    assert calibration()['fit_ids'] and calibration()['validation_ids']


@pytest.mark.parametrize('partition',['TEST','OOS','TRAIN','VALIDATION'])
def test_calibration_forbidden_fit(partition):
    with pytest.raises(ValueError):
        engine.fit(rows(partition),rows('CALIBRATION_VALIDATION',6),synthetic_test_only=True)


def test_calibration_future_overlap_and_missing_lineage():
    for field,value in [('temporal_accredited',False),('label_available_at','2026-02-01T10:00:00Z'),('synthetic_test_only',False)]:
        rs=rows();rs[0][field]=value
        with pytest.raises(ValueError): engine.fit(rs,rows('CALIBRATION_VALIDATION',6),synthetic_test_only=True)
    with pytest.raises(ValueError): engine.fit(rows(),rows('CALIBRATION_VALIDATION',3),synthetic_test_only=True)


def test_platt_endpoints_deterministic():
    a=platt.fit([0,.2,.8,1],[0,0,1,1])
    assert a==platt.fit([0,.2,.8,1],[0,0,1,1])
    assert all(0<=platt.predict(a,p)<=1 for p in [0,.5,1])


def test_isotonic_ties_monotonic_and_serializable():
    import json
    a=isotonic.fit([.1,.1,.2,.4,.8],[1,0,0,1,1])
    a=json.loads(json.dumps(a))
    ps=[isotonic.predict(a,i/100) for i in range(101)]
    assert ps==sorted(ps)
    assert a==isotonic.fit([.8,.4,.2,.1,.1],[1,1,0,0,1])
    with pytest.raises(ValueError): isotonic.predict(a,1.1)


def test_reliability_ece_known():
    r=reliability([0,1],[.2,.8])
    assert r==reliability([0,1],[.2,.8])
    assert r['ece']==pytest.approx(.2)
    assert sum(b['count'] for b in r['buckets'])==2


def test_multiclass_identity_simplex():
    a=rows();b=rows('CALIBRATION_VALIDATION',6)
    for r in a+b:r.update(p=[.2,.3,.5],y=1)
    m=engine.fit(a,b,market='1X2',synthetic_test_only=True)
    assert m['method']=='identity' and m['incompatible_methods']==['platt','isotonic']
    assert engine.apply('identity',{},[.2,.3,.5],'1X2')==[.2,.3,.5]
    with pytest.raises(ValueError):engine.apply('platt',{},[.2,.3,.5],'1X2')


def test_transform_blocks_future_synthetic_and_model_mismatch():
    m=calibration()
    for kw in [dict(cutoff='2026-01-09T10:00:00Z',source_model_hash=m['source_model_hash'],allow_synthetic=True),
               dict(cutoff='2026-02-01T10:00:00Z',source_model_hash=m['source_model_hash']),
               dict(cutoff='2026-02-01T10:00:00Z',source_model_hash='other',allow_synthetic=True)]:
        with pytest.raises(ValueError):engine.transform(m,.5,**kw)


def test_real_calibration_blocked():
    r=engine.real_state()
    assert r['real_status']=='BLOCKED' and r['calibration'] is None and r['real_metrics'] is None
