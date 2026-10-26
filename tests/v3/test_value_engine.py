"""Phase 4.1 synthetic, offline contract and arithmetic coverage."""
from copy import deepcopy
import json
import math
import pytest
from v3.value.engine import evaluate
from v3.value.probability import fair_odds, implied_probability
from v3.value.contract import serialize
from v3.odds.contract import MARKETS


from v3.value.fixtures import fixture


def run(model=None, records=None):
    m,r=fixture()
    return evaluate(m if model is None else model, r if records is None else records, allow_synthetic=True)


@pytest.mark.parametrize('p,expected', [(0,None),(1,1.0),(.25,4.0),(.5,2.0)])
def test_fair(p,expected):
    assert fair_odds(p)==expected
    m,r=fixture(p=p)
    out=run(m,r)
    assert out['eligibility']=='ELIGIBLE'
    assert out['fair_odds']==expected
    assert json.loads(serialize(out))==out


@pytest.mark.parametrize('p', [float('nan'),float('inf'),-float('inf'),True,False,'0.5',-.1,1.1,None])
def test_probability_rejection(p):
    with pytest.raises(ValueError): fair_odds(p)
    m,r=fixture(p=p)
    out=run(m,r)
    assert out['exclusion_reason']=='invalid_probability'
    assert all(out[k] is None for k in ('fair_odds','ev_per_unit','absolute_edge'))
    serialize(out)


@pytest.mark.parametrize('odds',[0,1,-2,True,'2',None,float('nan'),float('inf'),-float('inf')])
def test_odds_rejection(odds):
    with pytest.raises(ValueError): implied_probability(odds)
    m,r=fixture(odds=odds)
    assert run(m,r)['exclusion_reason']=='invalid_odds'


@pytest.mark.parametrize('market',MARKETS)
def test_complete_math(market):
    m,r=fixture(market)
    out=run(m,r)
    n=len(MARKETS[market])
    assert out['eligibility']=='ELIGIBLE'
    assert out['implied_probability_raw']==.5
    assert out['overround']==n*.5-1
    assert out['market_probability_no_vig']==pytest.approx(1/n)
    assert out['absolute_edge']==pytest.approx(.6-1/n)
    assert out['relative_edge']==pytest.approx(.6/(1/n)-1)
    from v3.value.market import normalize
    assert math.fsum(normalize([e['record'] for e in r])[1].values())==pytest.approx(1,abs=1e-12)


@pytest.mark.parametrize('p,ev',[(.6,.2),(.5,0),(.4,-.2)])
def test_ev(p,ev):
    m,r=fixture(p=p)
    assert run(m,r)['ev_per_unit']==pytest.approx(ev)


@pytest.mark.parametrize('field,value,reason',[
    ('bookmaker','other','bookmaker_mismatch'),('line',2.5,'invalid_odds_contract:invalid_line'),
    ('observed_at','2026-10-26T09:00:00Z','snapshot_mismatch'),
    ('provider','other','source_not_authorized'),('market','1X2','invalid_odds_contract:invalid_selection'),
    ('snapshot_type','opening','invalid_odds_contract:snapshot_requires_explicit_temporal_evidence')])
def test_mixing(field,value,reason):
    m,r=fixture();r[1]['record'][field]=value
    assert run(m,r)['exclusion_reason']==reason


def test_incomplete_duplicate_and_line_mixing():
    m,r=fixture()
    assert run(m,r[:1])['exclusion_reason']=='market_incomplete'
    assert run(m,[r[0],r[0]])['exclusion_reason']=='market_incomplete'
    from v3.value.market import normalize
    rr=[deepcopy(e['record']) for e in r];rr[1]['line']=2.5
    with pytest.raises(ValueError,match='line_mismatch'):normalize(rr)


@pytest.mark.parametrize('field,value,reason',[
    ('observed_at','2026-10-26T11:00:01Z','temporally_ineligible'),
    ('observed_at','2026-10-26T12:00:00Z','temporally_ineligible'),
    ('observed_at','2026-10-26T12:00:01Z','temporally_ineligible'),
    ('snapshot_type','closing','closing_not_pre_match_input'),
    ('price_state','suspended','price_not_active'),('provenance',{},'missing_provenance'),
    ('validity',{'pre_match':False},'temporally_ineligible')])
def test_eligibility(field,value,reason):
    m,r=fixture();r[0]['record'][field]=value
    out=run(m,r)
    assert out['eligibility']=='BLOCKED'
    assert out['exclusion_reason']==reason
    assert out['ev_per_unit'] is None


def test_source_and_explicit_synthetic_isolation():
    m,r=fixture()
    assert evaluate(m,r)['exclusion_reason']=='source_not_authorized'
    m['provenance']['origin']='production'
    assert run(m,r)['exclusion_reason']=='source_not_authorized'
    m,r=fixture();r[1]['record']['provenance']['origin']='production'
    assert run(m,r)['exclusion_reason']=='source_not_authorized'


def test_target_clock_rules_provenance_and_determinism():
    m,r=fixture(); before=deepcopy((m,r))
    assert serialize(run(m,r))==serialize(run(m,list(reversed(r))))
    assert (m,r)==before
    for field,value in [('cutoff','2026-10-26T12:00:00Z'),('period','first_half'),('rules','extra_time')]:
        changed=deepcopy(m);changed[field]=value
        assert run(changed,r)['eligibility']=='BLOCKED'
    m['provenance']={}
    assert run(m,r)['exclusion_reason']=='missing_provenance'


def test_nonuniform_1x2_prices_and_target_alignment():
    m,r=fixture('1X2')
    for envelope,odds in zip(r,[2.,3.,4.]):envelope['record']['decimal_odds']=odds
    out=run(m,r)
    assert out['eligibility']=='ELIGIBLE'
    assert out['overround']==pytest.approx(1/12)
    assert out['market_probability_no_vig']==pytest.approx(6/13)
    assert out['relative_edge']==pytest.approx(.6/(6/13)-1)
    for field,value,reason in [('internal_match_id','different','match_mismatch'),
                               ('market','BTTS','market_mismatch'),('line',1.5,'line_mismatch'),
                               ('selection','missing','selection_mismatch')]:
        changed=deepcopy(m);changed[field]=value
        assert run(changed,r)['exclusion_reason']==reason


def test_opening_and_inclusive_observation_cutoff():
    m,r=fixture()
    for envelope in r:
        envelope['record'].update(snapshot_type='opening',observed_at=m['cutoff'],
            temporal_semantics=dict(definition='Explicit provider opening definition',evidence='synthetic fixture'))
    assert run(m,r)['eligibility']=='ELIGIBLE'
    for envelope in r:envelope['cutoff']='2026-10-26T12:00:00Z'
    m['cutoff']='2026-10-26T12:00:00Z'
    assert run(m,r)['exclusion_reason']=='temporally_ineligible'


@pytest.mark.parametrize('field,value', [('cutoff','2026-10-26T10:59:00Z'),('period','first_half'),('rules','extra_time')])
def test_envelope_scope_mismatch(field,value):
    m,r=fixture();r[1][field]=value
    assert run(m,r)['eligibility']=='BLOCKED'


def test_finite_arithmetic_overflow_fails_closed():
    m,r=fixture(p=5e-324)
    out=run(m,r)
    assert out['exclusion_reason']=='nonfinite_computation'
    assert out['fair_odds'] is None
    serialize(out)
