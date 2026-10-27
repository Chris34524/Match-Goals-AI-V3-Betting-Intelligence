import pytest
from v3.performance.oos_gate import evaluate,count_positions
from test_performance_final import settled


def real_position():
    # Counter contract fixture only, never real evidence or report output.
    return dict(paper_bet_id='p',internal_match_id='m',synthetic_test_only=False,real=True,status='SETTLED',partition='OOS',decision='PASS',eligible=True,
                backfilled=False,temporal_lineage='counter-contract-fixture',settlement_accredited=True,settlement_lineage='counter-contract-fixture',stake_units=1,
                observed_at='2026-01-01T09:00:00Z',cutoff='2026-01-01T10:00:00Z',created_at='2026-01-01T10:01:00Z',
                kickoff_at='2026-01-01T12:00:00Z',completed_at='2026-01-01T14:00:00Z',settled_at='2026-01-01T15:00:00Z')


def test_oos_counter_threshold_contract_only():
    rs=[dict(real_position(),paper_bet_id=str(i),internal_match_id=str(i)) for i in range(200)]
    assert count_positions(rs)['gate_status']=='MET'
    assert count_positions(rs[:-1])['gate_status']=='NOT_MET'
    assert count_positions([])['real_oos_count']==0
    with pytest.raises(ValueError):count_positions(rs,threshold=199)


@pytest.mark.parametrize('field,value',[('synthetic_test_only',True),('partition','TRAIN'),('partition','VALIDATION'),('decision','NO_BET'),('decision','BLOCKED'),('status','OPEN'),('backfilled',True),('temporal_lineage',None),('created_at','2026-01-01T12:00:00Z')])
def test_oos_exclusions(field,value):
    assert count_positions([dict(real_position(),**{field:value})])['real_oos_count']==0


def test_oos_duplicates_and_multiple_markets_cannot_inflate():
    p=real_position()
    assert count_positions([p,p])['real_oos_count']==0
    assert count_positions([p,dict(p,paper_bet_id='other')])['real_oos_count']==1


def test_synthetic_journal_never_counts_real(tmp_path):
    r=evaluate(settled(tmp_path));assert r['real_oos_count']==0 and r['gate_status']=='NOT_MET'
    assert count_positions([],integrity_status='FAIL')['gate_status']=='BLOCKED'
