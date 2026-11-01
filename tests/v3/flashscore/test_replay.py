from dataclasses import asdict, replace
import pytest

from v3.flashscore.contract import Request, State
from v3.flashscore.collector import collect_live, live_authorized
from v3.flashscore.parser import StructuredParser
from v3.flashscore.events import normalize_events
from test_contract import fixture


def sample(surface='stats_overall', period='FT'):
    return dict(schema_version='fs-replay-1', sample_kind='synthetic', permission_reference='synthetic-test',
        inspected_fixture=asdict(fixture()), surface=surface, completeness_reference='test-container',
        metadata=dict(observed_at='2026-01-02T12:00:00Z', source_url='synthetic://m1',
            inspection='success', selected_period=period, selected_period_evidence='active '+period,
            period_evidence_method='structured_period', score_scope='regulation'),
        covered_fields=['corners', 'xg'], stats=[dict(canonical_stat='corners', side='home', entity_id='h', value=0)])


def request(name='corners', surface='stats_overall', period='FT', **kwargs):
    return Request(fixture(), surface, period, name, **(kwargs or dict(side='home', entity_id='h')))


def parse(r=None, s=None):
    return StructuredParser().parse(r or request(), s or sample())


def test_parent_available_child_missing_and_bilateral_partial():
    assert parse(request('stats_overall', level='match')).state == State.AVAILABLE
    assert parse(request('xg')).state == State.MISSING
    assert parse(request(side='away', entity_id='a')).state == State.MISSING
    assert parse().evidence.value == 0


@pytest.mark.parametrize('period,surface', [('1H','stats_first_half'), ('2H','stats_second_half')])
def test_half_is_not_inherited(period, surface):
    assert parse(request(surface=surface, period=period)).state == State.UNKNOWN
    assert parse(request(surface=surface, period=period), sample(surface, period)).state == State.AVAILABLE
    s = sample(surface, period)
    s['metadata']['inspection'] = 'shell'
    assert parse(request(surface=surface, period=period), s).state == State.UNKNOWN


@pytest.mark.parametrize('key,value', [('match_id','wrong'), ('competition_id','wrong'), ('lifecycle','scheduled')])
def test_identity_mismatch(key, value):
    s = sample()
    s['inspected_fixture'][key] = value
    assert parse(s=s).state == State.UNKNOWN


def test_duplicate_cell_not_silently_chosen():
    s = sample()
    s['stats'] *= 2
    assert parse(s=s).state == State.UNKNOWN


def test_manual_permission_and_schema_gate():
    for key, value in [('sample_kind','web'), ('permission_reference',None), ('schema_version','v0')]:
        s = sample()
        s[key] = value
        with pytest.raises(ValueError):
            parse(s=s)
    s = sample()
    s['sample_kind'] = 'permitted_manual'
    assert parse(s=s).state == State.AVAILABLE


def test_live_never_uses_replay_permission_or_visibility():
    for family in ('advanced_team_stats','corners','players','unknown'):
        assert not live_authorized('flashscore', 'permitted_ingestion', family)
        assert collect_live(request(), method='permitted_ingestion', family=family,
            observed_at='2026-01-02T00:00:00Z', source_url='https://example.invalid').state == State.BLOCKED


def event(kind='goal', **kwargs):
    return dict(event_id='e1', kind=kind, period='2H', score_scope='regulation', side='home',
                actor_id='p1', actor_scope='player', minute=70, added_time=0, sequence=1, **kwargs)


def test_second_yellow_and_synthetic_red_are_one_dismissal():
    yellow = event('second_yellow', dismissal_id='d1', dismissal_kind='second_yellow')
    red = dict(yellow, kind='red', event_id='e2')
    result = normalize_events([red, yellow], fixture(), 'complete-ledger')
    assert result['unique_dismissals'] == 1 and result['market_card_count'] is None
    assert result == normalize_events([yellow, red], fixture(), 'complete-ledger')
    with pytest.raises(ValueError):
        normalize_events([red], fixture(), 'complete-ledger')
    with pytest.raises(ValueError):
        normalize_events([event('red')], fixture(), 'complete-ledger')


@pytest.mark.parametrize('kind', ['goal','penalty_goal','own_goal','cancelled_goal','yellow','substitution'])
def test_event_kinds_and_scope_preserved(kind):
    row = event(kind)
    if kind == 'substitution':
        row['replacement_id'] = 'p2'
    result = normalize_events([row], fixture(), 'complete-ledger')
    assert result['rows'][0]['kind'] == kind
    row.update(actor_scope='staff', score_scope='shootout')
    result = normalize_events([row], fixture(), 'complete-ledger')
    assert result['rows'][0]['actor_scope'] == 'staff'
    assert result['rows'][0]['score_scope'] == 'shootout'


def test_events_surface_and_ambiguous_red():
    s = sample('events')
    s['events'] = [event()]
    r = request('events', surface='events', level='match')
    assert parse(r, s).state == State.AVAILABLE
    s['events'] = [event('red')]
    assert parse(r, s).state == State.UNKNOWN


def test_summary_scores_require_own_period_and_scope():
    s = sample('summary', '1H')
    s['stats'][0]['canonical_stat'] = 'goals_first_half'
    r = request('goals_first_half', surface='summary', period='1H')
    assert parse(r, s).settlement_compatible
    s['metadata']['score_scope'] = 'including_extra_time'
    assert not parse(r, s).settlement_compatible


@pytest.mark.parametrize('surface,rows', [
    ('lineups', [dict(player_id='p1', team_id='h', side='home', kind='official', role='starter', position='FW')]),
    ('standings', [dict(team_id='h', rank=1, played=3, points=7, snapshot_reference='snapshot')]),
    ('h2h', [dict(match_id='earlier', match_date='2025-01-01', home_id='h', away_id='a',
                  home_goals=0, away_goals=0, score_scope='regulation')]),
    ('player_stats', [dict(player_id='p1', team_id='h', side='home', participated=True, minutes=90, position='FW')])])
def test_context_surface_validated_independently(surface, rows):
    s = sample(surface)
    s['rows'] = rows
    r = request(surface, surface=surface, level='match')
    assert parse(r, s).state == State.AVAILABLE
    s['rows'] = rows * 2
    assert parse(r, s).state == State.UNKNOWN
    del s['rows']
    assert parse(r, s).state == State.UNKNOWN


def test_player_absence_and_participation():
    r = request('shots_on_target', surface='player_stats', level='player', side='home', entity_id='p1')
    s = sample('player_stats')
    assert parse(r, s).state == State.UNKNOWN
    s['stats'] = [dict(canonical_stat='shots_on_target', side='home', entity_id='p1', value=0)]
    assert parse(r, s).state == State.UNKNOWN
    s['rows'] = [dict(player_id='p1', team_id='h', side='home', participated=True, minutes=90, position='FW')]
    assert parse(r, s).state == State.AVAILABLE
    s['rows'][0]['participated'] = False
    assert parse(r, s).state == State.UNKNOWN


def test_unresolved_fixture_and_wrong_operand_orientation_are_unknown():
    s = sample()
    s['inspected_fixture']['match_id'] = None
    assert parse(s=s).state == State.UNKNOWN
    s = sample()
    s['stats'][0]['entity_id'] = 'wrong'
    assert parse(s=s).state == State.UNKNOWN


def test_unknown_html_surface_fails_closed():
    s = sample('lineups')
    s['html'] = '<html>Loading...</html>'
    assert parse(request('lineups', surface='lineups', level='match'), s).state == State.UNKNOWN
