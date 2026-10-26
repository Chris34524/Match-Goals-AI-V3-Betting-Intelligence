from dataclasses import replace
import pytest
from v3.features.intelligence_contracts import contracts, TEAM_STATS, KEEPER_STATS


@pytest.mark.parametrize('name', TEAM_STATS + KEEPER_STATS)
def test_advanced_observation_requires_permission_identity_time_and_orientation(name):
    row = next(r for r in contracts('2.8') if r.name == name)
    assert row.status == 'blocked'
    assert row.provenance_requirement and row.temporal_requirement and row.blocked_reason
    assert 'null' in row.unknown_policy
    with pytest.raises(ValueError): replace(row, status='available')


def test_corners_prepared_as_future_market_only():
    row = next(r for r in contracts('2.8') if r.name == 'corners')
    assert row.markets == ('CORNERS_FUTURE',)
    assert all(r.status == 'blocked' for r in contracts('2.8'))


from v3.features.intelligence_contracts import PLAYER_DEFINITIONS


@pytest.mark.parametrize('name', PLAYER_DEFINITIONS)
def test_player_candidates_have_independent_temporal_and_identity_gate(name):
    row = next(r for r in contracts('2.9') if r.name == name)
    assert row.status == 'blocked'
    assert 'publication timestamp' in row.blocked_reason
    assert 'player' in row.provenance_requirement or 'entity' in row.provenance_requirement
    assert 'official versus predicted' in row.prerequisites


def test_predicted_and_official_xi_remain_distinct():
    rows = {r.name:r for r in contracts('2.9')}
    assert rows['official_starting_xi'].definition != rows['predicted_xi'].definition
    assert 'never substitute' in rows['predicted_xi'].definition
    assert 'shirt number/name is insufficient' in rows['stable_player_ids'].definition
    assert 'competition average is distinct' in rows['player_rating'].definition


from v3.features.intelligence_contracts import DISCIPLINE_DEFINITIONS, CARD_LEDGER_CONTRACT


@pytest.mark.parametrize('name', DISCIPLINE_DEFINITIONS)
def test_discipline_requires_complete_ledger(name):
    r = next(r for r in contracts('2.10') if r.name == name)
    assert r.status == 'blocked'
    assert r.markets == ('CARDS_FUTURE',)
    assert 'complete' in r.prerequisites and 'second-yellow' in r.prerequisites
    assert 'null' in r.unknown_policy


def test_card_market_contract_preserves_dismissal_link_and_rules():
    assert 'dismissal_id_when_red' in CARD_LEDGER_CONTRACT['required_identity']
    assert 'one dismissal_id' in CARD_LEDGER_CONTRACT['second_yellow_policy']
    assert 'separate and not implemented' in CARD_LEDGER_CONTRACT['rules']
    assert 'boolean complete=true alone is insufficient' in CARD_LEDGER_CONTRACT['completeness']


from v3.features.intelligence_contracts import CONTEXT_DEFINITIONS


@pytest.mark.parametrize('name', CONTEXT_DEFINITIONS)
def test_context_requires_objective_definition_source_time_and_unknown(name):
    r = next(r for r in contracts('2.11') if r.name == name)
    assert r.status == 'blocked'
    assert r.definition and r.prerequisites and r.provenance_requirement
    assert 'cutoff' in r.prerequisites
    assert 'null' in r.unknown_policy
    assert not any(word in r.name for word in ('fear','emotion','morale','motivation','anxiety','psychological'))


def test_manager_flag_cannot_infer_false_from_missing_appointments():
    r = next(r for r in contracts('2.11') if r.name == 'manager_changed_14d')
    assert 'false only with complete appointment coverage' in r.definition
    assert '[cutoff-14 days, cutoff)' in r.definition
