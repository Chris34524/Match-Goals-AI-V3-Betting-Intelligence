from v3.operation.pipeline import demo,current_report,run
from v3.operation.release_gate import evaluate,REQUIRED
from v3.calibration.contract import sealed
from v3.paper.ledger import Ledger


def test_synthetic_e2e_all_layers_never_ready(tmp_path):
    a=demo(tmp_path/'a');b=demo(tmp_path/'b')
    assert a==b
    assert len(a['daily']['pass_candidates'])==1
    assert a['performance']['overall']['economic_status']=='COMPUTABLE'
    assert a['oos_gate']['real_oos_count']==0 and a['release']['release_status']=='BLOCKED'
    assert a['human_confirmation_required'] and not a['automated_real_betting']


def test_release_all_missing_and_synthetic_fail_closed():
    assert current_report()['release']['release_status']=='BLOCKED'
    assert evaluate({}, {})['release_status']=='BLOCKED'
    # A contract-only fixture exercises the necessary conditions, not a real release.
    cs={k:sealed(dict(status=s,real_accredited=True,synthetic_test_only=False,evidence_hash='contract-fixture')) for k,s in REQUIRED.items()}
    oos=sealed(dict(gate_status='MET',real_oos_count=200,required_oos_count=200))
    assert evaluate(cs,oos)['release_status']=='READY'
    assert evaluate(cs,oos,synthetic_test_only=True)['release_status']=='BLOCKED'
    for k in cs:
        subset={n:c for n,c in cs.items() if n!=k}
        assert evaluate(subset,oos)['release_status']=='BLOCKED'


def test_real_operation_dry_run_no_fabricated_picks(tmp_path):
    l=Ledger(tmp_path/'v3_data/paper/real.jsonl')
    r=run([],l)
    assert not r['daily']['pass_candidates'] and r['release']['release_status']=='BLOCKED'
    assert not l.path.exists() and r['performance']['overall']['metrics'] is None


import pytest
from v3.operation.pipeline import synthetic_candidate
from v3.selection.policy import decide
from v3.performance.analyzer import analyze


@pytest.mark.parametrize('market',['BTTS','OVER_1_5','OVER_2_5','OVER_3_5','1X2'])
def test_operation_all_markets_software_only(tmp_path,market):
    c=synthetic_candidate(market)
    assert decide(c,allow_synthetic=True)['decision']=='PASS'
    clock=['2026-10-26T11:00:01Z']
    l=Ledger(tmp_path/'v3_data/paper/market.jsonl',synthetic_test_only=True,clock=lambda:clock[0])
    created=l.record(c);clock[0]='2026-10-26T16:00:00Z'
    l.settle(created['paper_bet_id'],result='WIN',label=0 if market=='1X2' else 1,completed_at='2026-10-26T15:00:00Z',settlement_lineage='synthetic-only')
    report=analyze(l,allow_synthetic=True)
    assert report['overall']['metrics']['by_market'][market]['accuracy']==1
