import pytest
from v3.selection.policy import decide
from v3.calibration.engine import fit,transform
from v3.value.fixtures import fixture
from test_calibration_final import rows
from test_selection_pickscore_final import quality


def candidate(p=.9,odds=2):
    a=rows();b=rows('CALIBRATION_VALIDATION',6)
    # Accurate fixture: identity wins ties and produces low ECE.
    for r in a+b:r.update(p=float(r['y']))
    cal=fit(a,b,synthetic_test_only=True)
    vm,obs=fixture(p=p,odds=odds)
    cp=transform(cal,p,cutoff=vm['cutoff'],source_model_hash=cal['source_model_hash'],allow_synthetic=True)
    q=quality();q['probability']['value']=cp;q['calibration']['value']=cal['reliability']['ece'];q['value']['value']=cp*odds-1
    target={k:vm[k] for k in ('internal_match_id','market','selection','line','cutoff')};target.update(kickoff_at=obs[0]['record']['kickoff_at'],target_id='synthetic-target',date='2026-10-26')
    return dict(target=target,model=dict(status='ELIGIBLE',hash=cal['source_model_hash'],probability=p,
                partition='OOS',temporal_accredited=True,temporal_lineage='synthetic',predicted_at='2026-10-26T09:00:00Z',
                synthetic_test_only=True,**{k:vm[k] for k in ('internal_match_id','market','selection','line')}),
                calibration=cal,value_model=vm,odds_observations=obs,quality=q,integrity_status='PASS',synthetic_test_only=True)


def test_policy_pass_no_bet_blocked():
    assert decide(candidate(),allow_synthetic=True)['decision']=='PASS'
    assert decide(candidate(p=.5),allow_synthetic=True)['decision']=='NO_BET'
    assert decide({})['decision']=='BLOCKED'
    assert decide(candidate())['decision']=='BLOCKED'


@pytest.mark.parametrize('change',['model','calibration','odds','quality','integrity','closing','future'])
def test_policy_fail_closed(change):
    c=candidate()
    if change=='model':c['model']['status']='BLOCKED'
    if change=='calibration':c['calibration']['status']='BLOCKED'
    if change=='odds':c['odds_observations']=[]
    if change=='quality':c['quality'].pop('stability')
    if change=='integrity':c['integrity_status']='FAIL'
    if change=='closing':c['odds_observations'][0]['record']['snapshot_type']='closing'
    if change=='future':c['model']['predicted_at']='2026-10-26T13:00:00Z'
    assert decide(c,allow_synthetic=True)['decision']=='BLOCKED'
