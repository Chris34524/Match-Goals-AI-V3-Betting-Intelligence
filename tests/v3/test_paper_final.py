import json
import pytest
from v3.paper.ledger import Ledger
from test_selection_policy_final import candidate


def ledger(tmp_path):
    clock=['2026-10-26T11:00:01Z']
    return Ledger(tmp_path/'v3_data/paper/demo.jsonl',synthetic_test_only=True,clock=lambda:clock[0]),clock


def test_paper_append_only_fixed_unit_settlement(tmp_path):
    l,clock=ledger(tmp_path);c=l.record(candidate());before=l.path.read_bytes()
    assert c['stake_units']==1 and c['status']=='OPEN'
    clock[0]='2026-10-26T15:01:00Z'
    e=l.settle(c['paper_bet_id'],result='WIN',completed_at='2026-10-26T15:00:00Z',settlement_lineage='synthetic-result',label=1)
    assert l.path.read_bytes().startswith(before) and e['profit_units']==1
    assert len(l.events())==2 and l.positions()[0]['status']=='SETTLED'
    with pytest.raises(ValueError):l.record(candidate())
    with pytest.raises(ValueError):l.settle(c['paper_bet_id'],result='WIN',completed_at='2026-10-26T15:00:00Z',settlement_lineage='x',label=1)


@pytest.mark.parametrize('now',['2026-10-26T10:59:00Z','2026-10-26T12:00:00Z','2026-10-26T13:00:00Z'])
def test_paper_no_backdating_or_postkickoff(tmp_path,now):
    l,c=ledger(tmp_path);c[0]=now
    with pytest.raises(ValueError):l.record(candidate())


def test_settlement_post_event_and_label_consistent(tmp_path):
    l,c=ledger(tmp_path);a=l.record(candidate());c[0]='2026-10-26T15:00:00Z'
    with pytest.raises(ValueError):l.settle(a['paper_bet_id'],result='WIN',completed_at=c[0],settlement_lineage='x',label=1)
    c[0]='2026-10-26T16:00:00Z'
    with pytest.raises(ValueError):l.settle(a['paper_bet_id'],result='WIN',completed_at='2026-10-26T15:00:00Z',settlement_lineage='x',label=0)


def test_paper_detects_tampering(tmp_path):
    l,c=ledger(tmp_path);l.record(candidate());a=json.loads(l.path.read_text());a['stake_units']=2;l.path.write_text(json.dumps(a)+'\n')
    with pytest.raises(ValueError):l.events()


def test_production_clock_runtime_and_synthetic_protection(tmp_path):
    with pytest.raises(ValueError):Ledger(tmp_path/'ledger.jsonl')
    with pytest.raises(ValueError):Ledger(tmp_path/'v3_data/paper/l.jsonl',clock=lambda:'2020-01-01T00:00:00Z')
    l=Ledger(tmp_path/'v3_data/paper/l.jsonl')
    with pytest.raises(ValueError):l.record(candidate())
