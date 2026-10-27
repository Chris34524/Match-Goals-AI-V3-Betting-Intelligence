import pytest
from v3.selection.pickscore import score,WEIGHTS


def quality(synthetic=True):
    return {k:dict(value=v,status='ELIGIBLE',accredited=True,lineage='synthetic-quality',synthetic_test_only=synthetic)
            for k,v in zip(WEIGHTS,(.7,100,.01,.2,0))}


def test_score_breakdown_range_deterministic():
    r=score(quality(),synthetic_test_only=True)
    assert r==score(quality(),synthetic_test_only=True) and 0<=r['score']<=100
    assert r['score']==sum(c['contribution'] for c in r['components'])
    assert sum(WEIGHTS.values())==1 and r['policy']['optimized'] is False


@pytest.mark.parametrize('component',list(WEIGHTS))
@pytest.mark.parametrize('field,value',[('status','BLOCKED'),('accredited',False),('lineage',None),('value',float('nan')),('synthetic_test_only',False)])
def test_score_required_components_blocked(component,field,value):
    q=quality();q[component][field]=value
    r=score(q,synthetic_test_only=True)
    assert r['status']=='BLOCKED' and r['score'] is None


def test_score_real_cannot_accept_synthetic_and_missing():
    assert score(quality())['score'] is None
    assert score({})['score'] is None
