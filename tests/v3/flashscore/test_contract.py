from dataclasses import replace
import json
import pytest

from v3.flashscore.contract import Capability, Evidence, Fixture, Request, State, dumps


def fixture(**changes):
    return replace(Fixture('flashscore', 'm1', 'c1', '2026', 'league', 'finished', 'h', 'a', '2026-01-01'), **changes)


def capability(**changes):
    f = fixture()
    r = Request(f, 'stats_overall', 'FT', 'corners', side='home', entity_id='h')
    e = Evidence('2026-01-02T12:00:00Z', 'synthetic://m1', 'synthetic', f,
                 'stats_overall', 'FT', 'Overall active', 'active_control', 'h', 'home',
                 inspection='success', expected_covered=True, value=0, unit='count', score_scope='regulation')
    return Capability(r, replace(e, **changes))


def test_zero_missing_unknown_and_stable_roundtrip():
    c = capability()
    assert c.state == State.AVAILABLE and c.evidence.value == 0
    assert capability(value=None, null_reason='absent_value').state == State.MISSING
    for reason in ('dash', 'unknown_null', None):
        assert capability(value=None, null_reason=reason).state == State.UNKNOWN
    data = json.loads(dumps(c.to_dict()))
    assert dumps(Capability.from_dict(data).to_dict()) == dumps(data)
    data['state'] = 'MISSING'
    with pytest.raises(ValueError):
        Capability.from_dict(data)


@pytest.mark.parametrize('changes', [dict(inspection='shell'), dict(inspection='timeout'),
    dict(inspection='error'), dict(inspected_fixture=fixture(match_id='other')),
    dict(inspected_fixture=fixture(competition_id='other')), dict(inspected_surface='summary'),
    dict(selected_period='1H'), dict(period_evidence_method='url'), dict(selected_period_evidence=None),
    dict(inspected_side='away'), dict(inspected_entity_id='a'), dict(value='-'), dict(value=True),
    dict(value=-1), dict(value=1.5), dict(unit='percent'), dict(raw_or_derived='derived')])
def test_fail_closed(changes):
    assert capability(**changes).state == State.UNKNOWN


def test_noncoverage_needs_explicit_credible_evidence():
    assert capability(value=None, noncoverage_reference='absent tab').state == State.UNKNOWN
    assert capability(value=None, noncoverage_reference='provider scope notice',
                      noncoverage_method='provider_statement').state == State.NOT_COVERED


def test_authorization_independent_from_visibility():
    assert capability(acquisition_authorization='blocked').state == State.AVAILABLE
    c = capability(acquisition_mode='live')
    assert c.state == State.BLOCKED
    assert c.to_dict()['technical_visibility'] == 'visible'
    assert capability(access_blocked_reason='captcha').state == State.BLOCKED


@pytest.mark.parametrize('lifecycle', ['scheduled', 'postponed', 'cancelled', 'abandoned'])
def test_unplayed_never_zero(lifecycle):
    c = capability()
    f = fixture(lifecycle=lifecycle)
    assert Capability(replace(c.request, fixture=f), replace(c.evidence, inspected_fixture=f)).state == State.UNKNOWN


@pytest.mark.parametrize('scope', ['extra_time', 'shootout', 'including_extra_time', 'unknown'])
def test_scope_separate(scope):
    c = capability(score_scope=scope)
    assert c.state == State.AVAILABLE
    assert not c.settlement_compatible


def test_prematch_excludes_target_same_day_future_and_late_revision():
    c = capability(publication_at='2026-01-02T00:00:00Z', publication_verified=True,
                   revision_history_verified=True)
    assert c.prematch_usable('target', '2026-01-03', '2026-01-03T00:00:00Z')
    assert not c.prematch_usable('m1', '2026-01-03', '2026-01-03T00:00:00Z')
    assert not c.prematch_usable('target', '2026-01-01', '2026-01-03T00:00:00Z')
    assert not c.prematch_usable('target', '2025-12-31', '2026-01-03T00:00:00Z')
    assert not capability().prematch_usable('target', '2026-01-03', '2026-01-03T00:00:00Z')
    c = Capability(c.request, replace(c.evidence, revision_at='2026-01-04T00:00:00Z'))
    assert not c.prematch_usable('target', '2026-01-03', '2026-01-03T00:00:00Z')


def test_invalid_contract_inputs():
    with pytest.raises(ValueError):
        fixture(home_id='a')
    with pytest.raises(ValueError):
        capability(observed_at='2026-01-02')
    with pytest.raises(ValueError):
        capability(value=float('nan'))
    with pytest.raises(ValueError):
        Request(fixture(), 'stats_first_half', 'FT', 'corners', side='home', entity_id='h')


def test_derived_references_alone_cannot_certify_operands():
    assert capability(raw_or_derived='derived', operand_references=('claim',)).state == State.UNKNOWN


def test_card_actor_scope_not_assumed():
    c = capability(value=dict(yellow=0, direct_red=0, second_yellow_dismissals=0), unit='typed_cards')
    assert c.state == State.UNKNOWN
    c = Capability(c.request.__class__(c.request.fixture, c.request.surface, 'FT', 'cards',
                   side='home', entity_id='h'), c.evidence)
    assert c.state == State.UNKNOWN
    assert Capability(c.request, replace(c.evidence, card_actor_scope='on_field_players')).state == State.AVAILABLE


def test_boolean_flags_cannot_use_truthy_strings():
    with pytest.raises(ValueError):
        capability(publication_verified='false')


@pytest.mark.parametrize('changes', [dict(source_url=42), dict(sample_reference={}), dict(settlement_rules=123),
                                     dict(evidence_quality=None), dict(operand_references=(1,))])
def test_runtime_schema_rejects_untyped_provenance(changes):
    with pytest.raises(ValueError):
        capability(**changes)


def test_player_identity_must_be_an_opaque_string():
    with pytest.raises(ValueError):
        Request(fixture(), 'player_stats', 'FT', 'shots_on_target', 'player', 'home', 123)
