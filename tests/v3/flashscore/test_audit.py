from dataclasses import asdict, replace
import json
import random
import pytest

from v3.flashscore.audit import audit
from v3.flashscore.contract import Capability, Request, State, dumps
from v3.flashscore.coverage import rate, tier
from v3.flashscore.manifest import load_manifest
from v3.flashscore.cli import main
from v3.flashscore.replay import jsonl, replay_document
from test_contract import fixture, capability
from test_replay import sample


def manifest(fields=None, fixtures=None, **kwargs):
    return dict(schema_version='fs-audit-manifest-1', manifest_id='synthetic-audit',
                declared_at='2026-01-01T00:00:00Z', fixtures=fixtures or [asdict(fixture())],
                fields=fields or [dict(canonical_stat='corners', period='FT', surface='stats_overall')],
                min_successful_inspections=1, **kwargs)


def operands(m, value=0):
    c = capability()
    return [Capability(r, replace(c.evidence, inspected_fixture=r.fixture, inspected_surface=r.surface,
             inspected_side=r.side, inspected_entity_id=r.entity_id, selected_period=r.period,
             value=value)) for r in load_manifest(m).requests]


def market(result, name, player=None):
    return next(r for r in result['markets']['units'] if r['market'] == name and r['player_id'] == player)


def test_all_target_denominator_partial_and_missing():
    m = manifest()
    c = capability()
    r = audit(m, [c])
    assert r['metrics']['total_target_units'] == 2
    assert r['metrics']['attempted_units'] == 1
    assert r['metrics']['successful_inspections'] == 1
    assert r['metrics']['states'] == dict(AVAILABLE=1, MISSING=0, NOT_COVERED=0, BLOCKED=0, UNKNOWN=1)
    assert r['metrics']['all_target_operational_completeness']['raw_rate'] == .5
    assert r['metrics']['successful_inspection_conditional_availability']['raw_rate'] == 1
    assert r['metrics']['research_tier'] == 'UNASSESSED'
    assert not market(r, 'TOTAL_CORNERS')['ready']
    away = next(c for c in operands(m) if c.request.side == 'away')
    away = Capability(away.request, replace(away.evidence, value=None, expected_covered=True, null_reason='absent_value'))
    r = audit(m, [c, away])
    assert r['metrics']['states']['MISSING'] == 1
    assert r['metrics']['research_tier'] == 'CONDITIONAL'
    assert not market(r, 'MOST_CORNERS')['ready']
    assert market(audit(m, operands(m)), 'TOTAL_CORNERS')['ready']


def test_duplicate_fixture_observation_and_revisit():
    m = manifest(fixtures=[asdict(fixture())]*2)
    c = capability()
    r = audit(m, [c, c, Capability(c.request, replace(c.evidence, observed_at='2026-01-03T00:00:00Z'))])
    assert r['unique_fixtures'] == 1 and r['duplicate_fixtures'] == 1
    assert r['duplicate_observations'] == 1
    assert r['metrics']['total_target_units'] == 2 and r['metrics']['attempted_units'] == 1
    m['fixtures'][1] = asdict(fixture(competition_id='wrong'))
    with pytest.raises(ValueError):
        audit(m, [])


def test_latest_failure_is_not_replaced_with_optimistic_history():
    c = capability()
    error = Capability(c.request, replace(c.evidence, observed_at='2026-01-03T00:00:00Z', inspection='timeout'))
    r = audit(manifest(), [error, c])
    assert r['metrics']['states']['AVAILABLE'] == 0
    assert r['metrics']['successful_inspections'] == 0
    assert r['metrics']['attempted_units'] == 1


def test_equal_time_conflict_is_unknown_independent_of_input_order():
    c = capability()
    other = Capability(c.request, replace(c.evidence, value=3))
    assert audit(manifest(), [c, other]) == audit(manifest(), [other, c])
    assert next(u for u in audit(manifest(), [c, other])['units'] if u['request']['side'] == 'home')['null_reason'] == 'conflicting_latest_observations'


def test_observations_outside_frame_and_predeclaration_rejected():
    with pytest.raises(ValueError):
        audit(manifest(fixtures=[asdict(fixture(match_id='other'))]), [capability()])
    with pytest.raises(ValueError):
        audit(manifest(), [capability(observed_at='2025-12-01T00:00:00Z')])


@pytest.mark.parametrize('n,d,expected', [(499,1000,'EXPERIMENTAL'), (1,2,'CONDITIONAL'),
    (799,1000,'CONDITIONAL'), (4,5,'CORE')])
def test_tier_boundaries(n, d, expected):
    assert tier(n, d, d, minimum=1) == expected


def test_unassessed_and_intervals():
    assert tier(0, 10, 0, minimum=1) == 'UNASSESSED'
    assert tier(5, 10, 5, minimum=1) == 'UNASSESSED'
    assert tier(10, 10, 10, minimum=30) == 'UNASSESSED'
    assert rate(0, 0)['raw_rate'] is None
    assert rate(1, 2)['ci95_wilson'][0] < .5 < rate(1, 2)['ci95_wilson'][1]
    for evidence in [dict(access_blocked_reason='policy'), dict(inspection='shell')]:
        m = manifest()
        observations = [Capability(c.request, replace(c.evidence, **evidence)) for c in operands(m)]
        r = audit(m, observations)
        assert r['metrics']['research_tier'] == 'UNASSESSED'
        assert r['metrics']['all_target_operational_completeness']['denominator'] == 2


def test_period_and_joint_ht_ft_scores():
    fields = [dict(canonical_stat=field, surface='summary', period=period)
              for field, period in [('goals_ft','FT'), ('goals_first_half','1H')]]
    m = manifest(fields)
    obs = operands(m)
    assert market(audit(m, obs), 'HT_FT')['ready']
    c = next(c for c in obs if c.request.capability_name == 'goals_first_half')
    obs = [Capability(x.request, replace(x.evidence, value=2)) if x == c else x for x in obs]
    assert not market(audit(m, obs), 'HT_FT')['ready']
    assert not market(audit(m, operands(m)[:2]), 'HT_FT')['ready']


def test_1h_joint_corners_not_implied_by_ft():
    m = manifest([dict(canonical_stat='corners', period=p, surface=s) for p,s in
                  [('FT','stats_overall'), ('1H','stats_first_half')]])
    obs = operands(m)
    assert market(audit(m, obs), 'CORNERS_1H')['ready']
    obs = [c for c in obs if c.request.period == 'FT']
    r = audit(m, obs)
    assert market(r, 'TOTAL_CORNERS')['ready'] and not market(r, 'CORNERS_1H')['ready']


@pytest.mark.parametrize('scope', ['extra_time','shootout','including_extra_time','unknown'])
def test_scope_cannot_settle_markets(scope):
    m = manifest()
    obs = [Capability(c.request, replace(c.evidence, score_scope=scope)) for c in operands(m)]
    r = audit(m, obs)
    assert not market(r, 'TOTAL_CORNERS')['ready']
    assert r['metrics']['settlement_compatible_availability']['numerator'] == 0


@pytest.mark.parametrize('status', ['cancelled','postponed','abandoned','scheduled','live'])
def test_unsettled_market(status):
    m = manifest(fixtures=[asdict(fixture(lifecycle=status))])
    assert not market(audit(m, operands(m)), 'TOTAL_CORNERS')['ready']


def test_cards_require_types_and_same_settlement_rules():
    m = manifest([dict(canonical_stat='cards', period='FT', surface='stats_overall')])
    cards = dict(yellow=1, direct_red=0, second_yellow_dismissals=0)
    obs = [Capability(c.request, replace(c.evidence, value=cards, unit='typed_cards', card_actor_scope='on_field_players')) for c in operands(m)]
    assert not market(audit(m, obs), 'CARDS')['ready']
    obs = [Capability(c.request, replace(c.evidence, settlement_rules='rules-v1')) for c in obs]
    assert market(audit(m, obs), 'CARDS')['ready']
    obs[0] = Capability(obs[0].request, replace(obs[0].evidence, settlement_rules='rules-v2'))
    assert not market(audit(m, obs), 'CARDS')['ready']


def test_player_eligibility_denominator_and_joint_readiness():
    fields = [dict(canonical_stat='shots_on_target', surface='player_stats', period='FT', level='player',
                   eligibility=dict(min_minutes=1, positions=['FW','MF']))]
    players = [dict(provider='flashscore', match_id='m1', player_id='p'+str(i), side='home',
                    participated=p, minutes=mins, position=pos, participation_reference='roster')
               for i,(p,mins,pos) in enumerate([(True,90,'FW'),(False,0,'FW'),(True,90,'GK'),(None,None,'MF')])]
    m = manifest(fields, players=players)
    r = audit(m, [])
    assert r['metrics']['total_target_units'] == 1
    assert [x['status'] for x in r['player_eligibility']] == ['eligible','excluded','excluded','unassessed']
    assert not market(r, 'PLAYER_SOT','p0')['ready']
    r = audit(m, operands(m))
    assert market(r, 'PLAYER_SOT','p0')['ready']
    assert r['metrics']['total_target_units'] == 1
    assert r['eligibility_incomplete']
    assert r['metrics']['research_tier'] == 'UNASSESSED'
    m['players'] = []
    r = audit(m, [])
    assert r['player_eligibility'][0]['status'] == 'unassessed_roster'
    assert r['markets']['totals'][-1]['readiness']['numerator'] == 0


def test_temporal_metrics_with_explicit_cutoff():
    m = manifest(target_context=dict(match_id='m1', match_date='2026-01-01', cutoff='2026-01-01T12:00:00Z'))
    r = audit(m, operands(m))
    assert r['metrics']['temporal_prematch_usability']['numerator'] == 0
    assert r['metrics']['settlement_compatible_availability']['numerator'] == 2
    assert audit(manifest(), [])['metrics']['temporal_prematch_usability'] is None


def test_strata_rates_are_pooled_by_units_not_mean_percentages():
    fixtures = [asdict(fixture(match_id=str(i), competition_id='big' if i else 'small')) for i in range(10)]
    m = manifest(fixtures=fixtures)
    obs = [c for c in operands(m) if c.request.fixture.competition_id == 'big']
    r = audit(m, obs)
    assert r['metrics']['all_target_operational_completeness']['raw_rate'] == .9
    assert len(r['strata']) == 4


def test_thousands_of_units_deterministic_order():
    m = manifest(fixtures=[asdict(fixture(match_id=f'{i:04}')) for i in range(1500)])
    obs = operands(m)
    r = audit(m, obs)
    random.Random(42).shuffle(obs)
    assert dumps(r) == dumps(audit(m, obs))
    assert len(r['units']) == 3000


def test_cli_replay_audit_stable_and_roundtrip(tmp_path):
    c = capability()
    replay = dict(schema_version='fs-replay-batch-1', items=[dict(request=asdict(c.request), sample=sample())])
    path = tmp_path / 'replay.json'
    path.write_text(dumps(replay))
    mp = tmp_path / 'manifest.json'
    mp.write_text(dumps(manifest()))
    out = tmp_path / 'replayed'
    assert main(['replay','--input',str(path),'--output',str(out)]) == 0
    obs = out / 'observations.jsonl'
    target = tmp_path / 'audit'
    assert main(['coverage','--manifest',str(mp),'--observations',str(obs),'--output',str(target)]) == 0
    before = (target / 'coverage.json').read_bytes()
    main(['coverage','--manifest',str(mp),'--observations',str(obs),'--output',str(target)])
    assert (target / 'coverage.json').read_bytes() == before
    assert json.loads(before)['metrics']['states']['AVAILABLE'] == 1
    assert jsonl(replay_document(replay)) == obs.read_text()


def test_inspection_success_is_independent_of_value_interpretability():
    m = manifest()
    obs = [Capability(c.request, replace(c.evidence, value='-')) for c in operands(m)]
    r = audit(m, obs)
    assert r['metrics']['successful_inspections'] == 2
    assert r['metrics']['conclusive_assessments'] == 0
    assert r['metrics']['states']['UNKNOWN'] == 2
    assert r['metrics']['successful_inspection_conditional_availability']['denominator'] == 2
    assert r['metrics']['research_tier'] == 'UNASSESSED'


def test_checked_in_synthetic_example_reproduces():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3] / 'docs/v3/flashscore/examples'
    m = json.loads((root / 'synthetic-manifest.json').read_text())
    replay = json.loads((root / 'synthetic-replay.json').read_text())
    expected = json.loads((root / 'synthetic-coverage.json').read_text())
    assert audit(m, replay_document(replay)) == expected
