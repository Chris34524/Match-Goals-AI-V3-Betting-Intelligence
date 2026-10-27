import pytest
from v3.performance.analyzer import analyze
from v3.performance.drawdown import drawdown
from v3.validation.economics import economics
from test_paper_final import ledger
from test_selection_policy_final import candidate


def settled(tmp_path,result='WIN',label=1):
    l,clock=ledger(tmp_path);r=l.record(candidate());clock[0]='2026-10-26T16:00:00Z'
    l.settle(r['paper_bet_id'],result=result,label=label,completed_at='2026-10-26T15:00:00Z',settlement_lineage='synthetic-result')
    return l


def test_predictive_economic_known_formulas_and_clv_blocked(tmp_path):
    r=analyze(settled(tmp_path),allow_synthetic=True)
    s=r['overall'];m=s['metrics']['overall'];e=s['economics']
    import math
    assert m['brier']==pytest.approx(.01) and m['logloss']==pytest.approx(-math.log(.9))
    assert m['accuracy']==1 and e['total_staked']==1 and e['total_return']==2
    assert e['profit']==1 and e['roi']==e['yield_units']==1
    assert s['clv_status']=='BLOCKED' and e['clv'] is None
    assert r['by_model'] and r['by_period'] and r['real_status']=='BLOCKED'


def test_loss_void_and_unsettled(tmp_path):
    l=settled(tmp_path/'loss','LOSS',0)
    r=analyze(l,allow_synthetic=True);assert r['overall']['economics']['roi']==-1
    l=settled(tmp_path/'void','VOID',None)
    r=analyze(l,allow_synthetic=True);assert r['overall']['predictive_status']=='NOT_APPLICABLE'
    assert r['overall']['economics']['profit']==0
    l,clock=ledger(tmp_path/'open');l.record(candidate())
    assert analyze(l,allow_synthetic=True)['overall']['status']=='BLOCKED'


def test_drawdown_chronology_initial_loss_and_ties():
    rs=[dict(settled_at=f'2026-10-{i+1:02d}T16:00:00Z',paper_bet_id=str(9-i),profit_units=p) for i,p in enumerate([-1,3,-1,-1,1])]
    assert drawdown(list(reversed(rs)))==drawdown(rs)
    r=drawdown(rs);assert r['max_drawdown_units']==2 and r['equity_curve'][-1]['equity_units']==1
    assert drawdown([])['max_drawdown_units']==0


def test_economics_rejects_invalid_odds_or_settlement(tmp_path):
    p=settled(tmp_path).positions()[0];c=p['decision_provenance']['candidate']
    r=dict(p,decision_model=dict(c['value_model'],model_probability=.9),odds_observations=c['odds_observations'])
    assert economics([r],allow_synthetic=True)['economic_status']=='COMPUTABLE'
    for key,value in [('settlement_accredited',False),('stake_units',2),('settled_at',p['kickoff_at'])]:
        assert economics([dict(r,**{key:value})],allow_synthetic=True)['economic_status']=='BLOCKED'
    r['odds_observations'][0]['record']['snapshot_type']='closing'
    assert economics([r],allow_synthetic=True)['economic_status']=='BLOCKED'


def test_performance_synthetic_not_real(tmp_path):
    with pytest.raises(ValueError):analyze(settled(tmp_path))
