import pytest
from v3.operation.handoff import Handoff
from test_selection_policy_final import candidate


def test_human_acknowledgement_immutable_no_execution(tmp_path):
    clock=['2026-10-26T11:00:01Z']
    h=Handoff(tmp_path/'v3_data/operation/handoffs',synthetic_test_only=True,clock=lambda:clock[0])
    r=h.create(candidate())
    from v3.calibration.contract import verify
    verify(r)
    before=(h.root/(r['recommendation_id']+'.json')).read_bytes()
    clock[0]='2026-10-26T11:01:00Z';e=h.review(r['recommendation_id'],review_status='ACKNOWLEDGED',reviewer='synthetic-human')
    assert e['meaning']=='acknowledgement_intention_or_review_only' and e['automated_real_betting'] is False
    assert e['human_confirmation_required'] is True
    assert before==(h.root/(r['recommendation_id']+'.json')).read_bytes()
    with pytest.raises(FileExistsError):h.review(r['recommendation_id'],review_status='REJECTED',reviewer='x')
    assert not {'sportsbook_execution_id','real_bet_receipt','funding','bankroll_transaction'} & e.keys()


def test_handoff_blocked_invalid_states_and_real_release(tmp_path):
    h=Handoff(tmp_path/'v3_data/operation/handoffs')
    with pytest.raises(ValueError):h.create(candidate())
    with pytest.raises(ValueError):h.review('../bad',review_status='ACKNOWLEDGED',reviewer='x')
    h=Handoff(tmp_path/'v3_data/operation/demo',synthetic_test_only=True,clock=lambda:'2026-10-26T11:00:01Z')
    r=h.create(candidate())
    with pytest.raises(ValueError):h.review(r['recommendation_id'],review_status='PLACED',reviewer='x')
