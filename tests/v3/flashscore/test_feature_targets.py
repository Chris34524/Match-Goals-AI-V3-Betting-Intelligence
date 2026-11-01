"""Synthetic evidence only; no acquisition or predictive-quality assertions."""
from dataclasses import replace
from datetime import date, timedelta
import random

import pytest

from v3.flashscore.contract import Capability, Evidence, Fixture, Request, dumps
from v3.flashscore.feature_catalog import CATALOG
from v3.flashscore.feature_materializer import FeatureMaterializer
from v3.flashscore.market_contract import (CardSettlementPolicy, MarketSpec, PlayerMarketPolicy,
    RESEARCH_CARDS, evaluate_over, research_markets)
from v3.flashscore.normalization import unit_for
from v3.flashscore.observation_index import digest
from v3.flashscore.targets import TargetEngine

CUTOFF = '2026-10-30T12:00:00Z'
TARGET = Fixture('synthetic', 'target', 'league', '2026', 'stage', 'finished', 'A', 'B', '2026-10-30')


def cap(f=TARGET, metric='goals_ft', value=2, side='home', period='FT', **changes):
    level = changes.pop('level', 'team')
    entity = changes.pop('entity', getattr(f, side + '_id') if level == 'team' else None)
    surface = ('summary' if metric.startswith('goals_') else 'player_stats' if level in ('player', 'match')
               else {'FT': 'stats_overall', '1H': 'stats_first_half', '2H': 'stats_second_half'}[period])
    request = Request(f, surface, period, metric, level, side if level != 'match' else None, entity)
    publication = (date.fromisoformat(f.match_date) + timedelta(days=1)).isoformat() + 'T08:00:00Z'
    evidence = Evidence(publication, 'synthetic://evidence', 'synthetic', inspected_fixture=f,
        inspected_surface=surface, selected_period=period, selected_period_evidence='synthetic-period',
        period_evidence_method='structured_period', inspected_side=request.side,
        inspected_entity_id=entity, inspection='success', value=value,
        unit='surface' if level == 'match' else unit_for(metric), score_scope='regulation',
        publication_at=publication, publication_verified=True, revision_history_verified=True,
        sample_reference='synthetic-only', evidence_quality='synthetic', **changes)
    return Capability(request, evidence)


def edit(c, **changes):
    return replace(c, evidence=replace(c.evidence, **changes))


def history(n, metric='goals_ft', *, alternate=False, value=2):
    rows = []
    for i in range(n):
        f = replace(TARGET, match_id=f'h{i:03}', match_date=(date(2026, 10, 28)-timedelta(days=i)).isoformat(),
                    home_id='C' if alternate and i % 2 else 'A', away_id='A' if alternate and i % 2 else 'C')
        side = 'home' if f.home_id == 'A' else 'away'
        rows.append(cap(f, metric, value, side))
    return rows


def feature(rows, name='goals_for', n=5, scope='overall', **kwargs):
    return next(r for r in FeatureMaterializer(rows).materialize(TARGET, CUTOFF, names=[name],
        scopes=[scope], **kwargs) if r['side'] == 'home' and r['window'] == f'L{n}')


def settle(rows, family='goals', market='over', period='FT', side='total', line=2.5, **kwargs):
    spec = MarketSpec(family, market, period, side, line if market == 'over' else None)
    return TargetEngine(rows).settle(TARGET, specs=[spec], **kwargs)[0]


def pair(metric='goals_ft', home=2, away=1, period='FT', **kwargs):
    return [cap(metric=metric, value=home, period=period, **kwargs),
            cap(metric=metric, value=away, period=period, side='away', **kwargs)]


@pytest.mark.parametrize('n', [5, 10, 20])
def test_exact_windows(n):
    r = feature(history(n+3), n=n)
    assert (r['status'], r['value'], r['n_eligible'], r['n_available'], r['coverage_rate']) == ('AVAILABLE', 2, n, n, 1)
    assert r['source_match_ids'] == [f'h{i:03}' for i in range(n)]


@pytest.mark.parametrize('n', [10, 20])
def test_insufficient(n):
    r = feature(history(6), n=n)
    assert r['status'] == 'INSUFFICIENT_HISTORY' and r['value'] is None
    assert r['n_eligible'] == r['n_available'] == 6 and r['coverage_rate'] == 6/n


@pytest.mark.parametrize('match_id,match_date', [('target', '2026-10-20'), ('future', '2026-10-31'),
                                               ('same', '2026-10-30')])
def test_excluded_history(match_id, match_date):
    rows = history(5) + [cap(replace(TARGET, match_id=match_id, match_date=match_date), value=99)]
    r = feature(rows)
    assert r['value'] == 2 and match_id not in r['source_match_ids']
    assert match_id in [x['match_id'] for x in r['excluded_fixtures']]


@pytest.mark.parametrize('change', [dict(publication_at=CUTOFF), dict(revision_at=CUTOFF),
    dict(publication_verified=False), dict(revision_history_verified=False),
    dict(publication_at='2026-10-31T00:00:00Z'), dict(revision_at='2026-10-01T00:00:00Z')])
def test_strict_lineage(change):
    rows = history(5)
    rows[0] = edit(rows[0], **change)
    r = feature(rows)
    assert r['status'] == 'TEMPORAL_INELIGIBLE' and r['value'] is None and r['n_available'] == 4


@pytest.mark.parametrize('scope,expected', [('home', ['h000','h002','h004','h006','h008']),
                                           ('away', ['h001','h003','h005','h007','h009'])])
def test_orientation(scope, expected):
    rows = history(10, alternate=True)
    r = feature(rows, scope=scope)
    assert r['source_match_ids'] == expected and r['value'] == 2
    against = [cap(c.request.fixture, side='away' if c.request.side == 'home' else 'home', value=3) for c in rows]
    assert feature(rows+against, 'goals_against', scope=scope)['value'] == 3


def test_zero_missing_and_no_backfill():
    rows = history(6, value=0)
    assert feature(rows)['value'] == 0
    rows[0] = edit(rows[0], value=None, expected_covered=True, null_reason='absent_value')
    r = feature(rows)
    assert r['status'] == 'MISSING_OPERAND' and r['value'] is None and r['n_available'] == 4
    assert 'h005' not in r['source_match_ids']


def test_partial_xg():
    rows = history(6, 'xg', value=1.5)
    rows[2] = edit(rows[2], value=None)
    r = feature(rows, 'xg_for')
    assert r['status'] == 'UNASSESSED' and r['value'] is None and r['n_available'] == 4


@pytest.mark.parametrize('name,metric,denominator', [('shot_accuracy','shots_on_target','shots'),
    ('xg_per_shot','xg','shots'), ('cards_per_foul','cards','fouls')])
def test_ratios(name, metric, denominator):
    value = {'yellow':1,'direct_red':0,'second_yellow_dismissals':0} if metric == 'cards' else 1
    nums = history(5, metric, value=value)
    if metric == 'cards':
        nums = [edit(c, settlement_rules=RESEARCH_CARDS.operand_rules, card_actor_scope='on_field_players') for c in nums]
    denoms = history(5, denominator, value=2)
    kwargs = {'card_policy': RESEARCH_CARDS}
    assert feature(nums+denoms, name, **kwargs)['value'] == .5
    zero = [edit(c, value=0) for c in denoms]
    assert feature(nums+zero, name, **kwargs)['status'] == 'SEMANTIC_INCOMPATIBLE'
    assert feature(nums+denoms[1:], name, **kwargs)['value'] is None


@pytest.mark.parametrize('change,status', [(dict(access_blocked_reason='denied'),'BLOCKED_SOURCE'),
    (dict(inspected_entity_id='wrong'),'UNASSESSED'), (dict(inspected_side='away'),'UNASSESSED'),
    (dict(score_scope='including_extra_time'),'TEMPORAL_INELIGIBLE'),
    (dict(value=None, noncoverage_reference='synthetic', noncoverage_method='provider_statement'),'NOT_COVERED')])
def test_feature_failure_reasons(change,status):
    rows = history(5); rows[0] = edit(rows[0], **change)
    assert feature(rows)['status'] == status


def test_duplicate_conflict_revision_and_determinism():
    rows = history(5)
    before = feature(rows)
    assert dumps(feature(rows+rows)) == dumps(before)
    revised = edit(rows[0], value=7, revision_at='2026-10-29T10:00:00Z', observed_at='2026-10-31T10:00:00Z')
    assert feature(rows+[revised])['value'] == 3
    late = edit(revised, value=100, revision_at='2026-10-31T10:00:00Z')
    assert feature(rows+[late])['value'] == 2
    conflict = edit(revised, value=9)
    assert feature(rows+[revised,conflict])['status'] == 'UNASSESSED'
    random.Random(77).shuffle(rows)
    assert dumps(feature(rows)) == dumps(before)
    assert set(before['source_observation_hashes']) == {digest(c.to_dict()) for c in rows}
    bad = replace(rows[0], request=replace(rows[0].request, fixture=replace(rows[0].request.fixture, stage='different')))
    with pytest.raises(ValueError, match='conflicting fixture'):
        FeatureMaterializer(rows+[bad])


def test_targets_never_features():
    target = settle(pair())
    for bad in (target, target['binary_label'], {'labels':target}, feature(history(5))):
        with pytest.raises(ValueError, match='only FS capabilities'):
            FeatureMaterializer([bad])
    assert feature(history(5)+pair())['value'] == 2


@pytest.mark.parametrize('goals,line,label', [(0,.5,0),(1,.5,1),(1,1.5,0),(2,1.5,1),(2,2.5,0),
    (3,2.5,1),(3,3.5,0),(4,3.5,1),(4,4.5,0),(5,4.5,1)])
def test_goal_thresholds(goals,line,label):
    r = settle(pair(home=goals,away=0),line=line)
    assert r['status'] == 'SETTLED' and r['binary_label'] == label


@pytest.mark.parametrize('home,away,label', [(0,0,0),(1,0,0),(0,1,0),(1,1,1),(3,2,1)])
@pytest.mark.parametrize('period,metric', [('FT','goals_ft'),('1H','goals_first_half'),('2H','goals_second_half')])
def test_btts(home,away,label,period,metric):
    assert settle(pair(metric,home,away,period), market='btts',period=period)['binary_label'] == label


@pytest.mark.parametrize('h,a,result', [(2,1,'HOME'),(0,0,'DRAW'),(0,1,'AWAY')])
@pytest.mark.parametrize('period,metric', [('FT','goals_ft'),('1H','goals_first_half')])
def test_1x2(h,a,result,period,metric):
    assert settle(pair(metric,h,a,period),market='1x2',period=period)['outcome'] == result


@pytest.mark.parametrize('ht,ft,outcome', [((0,0),(1,2),'DRAW/AWAY'),((1,0),(2,0),'HOME/HOME'),((0,1),(1,1),'AWAY/DRAW')])
def test_ht_ft(ht,ft,outcome):
    rows = pair('goals_first_half',*ht,'1H')+pair(home=ft[0],away=ft[1])
    assert settle(rows,market='ht_ft')['outcome'] == outcome


def test_second_half_derivation():
    rows = pair(home=2,away=1)+pair('goals_first_half',1,1,'1H')
    assert settle(rows,period='2H',line=.5)['status'] == 'MISSING_OPERAND'
    r = settle(rows,period='2H',line=.5,derive_second_half=True)
    assert r['binary_label'] == 1 and r['derivation'] == 'regulation-ft-minus-ht-v1'
    assert len(r['observation_hashes']) == 4
    assert settle(pair('goals_second_half',1,0,'2H'),period='2H',line=.5)['binary_label'] == 1
    invalid = pair(home=0,away=1)+pair('goals_first_half',1,0,'1H')
    assert settle(invalid,period='2H',derive_second_half=True)['status'] == 'SETTLEMENT_INCOMPATIBLE'
    assert settle([edit(c, score_scope='including_extra_time') for c in rows],period='2H',derive_second_half=True)['status'] == 'SETTLEMENT_INCOMPATIBLE'
    assert settle(rows+pair('goals_second_half',2,0,'2H'),period='2H',line=.5)['binary_label'] == 1


@pytest.mark.parametrize('scope', ['extra_time','shootout','including_extra_time','unknown'])
def test_nonregulation(scope):
    assert settle([edit(c,score_scope=scope) for c in pair()])['status'] == 'SETTLEMENT_INCOMPATIBLE'


@pytest.mark.parametrize('line', [7.5,8.5,9.5,10.5,11.5])
def test_corners_thresholds(line):
    base = int(line)
    assert settle(pair('corners',base,0),family='corners',line=line)['binary_label'] == 0
    assert settle(pair('corners',base,1),family='corners',line=line)['binary_label'] == 1


@pytest.mark.parametrize('side', ['home','away'])
@pytest.mark.parametrize('line', [3.5,4.5,5.5])
def test_team_corners(side,line):
    assert settle(pair('corners',6,6),family='corners',side=side,line=line)['binary_label'] == 1


@pytest.mark.parametrize('line', [3.5,4.5,5.5])
def test_half_corners(line):
    assert settle(pair('corners',3,3,'1H'),family='corners',period='1H',line=line)['binary_label'] == 1


def test_most_corners_missing_side():
    assert settle(pair('corners',5,5),family='corners',market='most')['outcome'] == 'DRAW'
    assert settle(pair('corners',5,4),family='corners',market='most')['outcome'] == 'HOME'
    assert settle(pair('corners',3,4),family='corners',market='most')['outcome'] == 'AWAY'
    for family,metric in [('goals','goals_ft'),('corners','corners'),('shots','shots')]:
        r = settle([cap(metric=metric)],family=family,side='home' if family=='shots' else 'total')
        assert r['status'] == 'MISSING_OPERAND' and r['binary_label'] is None


CARDS = dict(yellow=2,direct_red=0,second_yellow_dismissals=1)


def card_pair(period='FT'):
    return pair('cards',CARDS,dict(yellow=0,direct_red=0,second_yellow_dismissals=0),period,
                settlement_rules=RESEARCH_CARDS.operand_rules,card_actor_scope='on_field_players')


@pytest.mark.parametrize('line,label', [(2.5,1),(3.5,0),(4.5,0),(5.5,0)])
def test_typed_cards(line,label):
    rows = card_pair()
    r = settle(rows,family='cards',line=line,card_policy=RESEARCH_CARDS)
    assert r['binary_label'] == label
    assert r['raw_operands'][0]['value'] == CARDS
    assert settle(rows,family='cards',line=line)['status'] == 'SETTLEMENT_INCOMPATIBLE'


def test_second_yellow_red_and_halves():
    rows = card_pair()
    assert settle(rows,family='cards',market='red',card_policy=RESEARCH_CARDS)['binary_label'] == 1
    no_red = [edit(c,value=dict(yellow=2,direct_red=0,second_yellow_dismissals=0)) for c in rows]
    assert settle(no_red,family='cards',market='red',card_policy=RESEARCH_CARDS)['binary_label'] == 0
    assert settle(rows,family='cards',period='1H',card_policy=RESEARCH_CARDS)['status'] == 'MISSING_OPERAND'
    assert settle(card_pair('1H'),family='cards',period='1H',card_policy=RESEARCH_CARDS)['binary_label'] == 1
    assert settle(rows,family='cards',side='home',card_policy=RESEARCH_CARDS)['binary_label'] == 1


@pytest.mark.parametrize('scope', ['players_including_bench','players_and_staff'])
def test_card_actor_scope(scope):
    rows = [edit(c,card_actor_scope=scope) for c in card_pair()]
    assert settle(rows,family='cards',card_policy=RESEARCH_CARDS)['status'] == 'SETTLEMENT_INCOMPATIBLE'
    policy = replace(RESEARCH_CARDS,version='research-other-scope',bench_scope=True,staff_scope=scope=='players_and_staff')
    assert settle(rows,family='cards',card_policy=policy)['status'] == 'SETTLED'
    assert feature([edit(c,card_actor_scope='on_field_players') for c in history(5,'cards',value=CARDS)],'cards_for')['status'] == 'SEMANTIC_INCOMPATIBLE'


@pytest.mark.parametrize('family,line', [('shots',8.5),('shots_on_target',2.5),('shots_on_target',3.5),('shots_on_target',4.5)])
def test_shots(family,line):
    r = settle(pair(family,int(line)+1,0),family=family,side='home',line=line)
    assert r['binary_label'] == 1
    assert settle(pair(family,int(line),0),family=family,side='home',line=line)['binary_label'] == 0


def player_evidence(**changes):
    row = dict(player_id='P1',team_id='A',side='home',participated=True,minutes=90,position='F')
    row.update(changes)
    stats = cap(metric='shots_on_target',value=3,level='player',entity='P1')
    surface = cap(metric='player_stats',level='match',value=dict(validated=True,rows=[row],completeness_reference='synthetic-roster'))
    return [stats,surface]


def player_settle(rows,policy=True):
    return TargetEngine(rows).settle(TARGET,specs=[MarketSpec('player_sot','over',side='home',line=2.5,player_id='P1')],
        player_policy=PlayerMarketPolicy('research-min1-v1',1,('F',)) if policy else None)[0]


def test_player_sot():
    assert player_settle(player_evidence())['binary_label'] == 1
    assert player_settle(player_evidence(),False)['status'] == 'UNASSESSED'
    assert player_settle(player_evidence()[:1])['status'] == 'UNASSESSED'


@pytest.mark.parametrize('changes', [dict(player_id='P2'),dict(team_id='B'),dict(side='away'),
    dict(participated=False,minutes=0),dict(position='GK'),dict(minutes=.5)])
def test_ineligible_player(changes):
    assert player_settle(player_evidence(**changes))['binary_label'] is None


@pytest.mark.parametrize('lifecycle,status', [('scheduled','UNSETTLED'),('live','UNSETTLED'),
    ('postponed','UNSETTLED'),('cancelled','VOID'),('abandoned','UNSETTLED')])
def test_lifecycle(lifecycle,status):
    f = replace(TARGET,lifecycle=lifecycle)
    r = TargetEngine(pair_for_fixture(f)).settle(f,specs=[MarketSpec('goals','over',line=2.5)])[0]
    assert r['status'] == status and r['binary_label'] is None and r['settled_at'] is None


def pair_for_fixture(f):
    return [cap(f),cap(f,side='away')]


@pytest.mark.parametrize('value,line,outcome', [(2,2,'PUSH'),(3,2,'WIN'),(1,2,'LOSS'),(0,0,'PUSH')])
def test_generic_integer_lines(value,line,outcome):
    assert evaluate_over(value,line).value == outcome


def test_integer_target_push():
    r = settle(pair(home=1,away=1),line=2)
    assert r['outcome'] == 'PUSH' and r['binary_label'] is None


def test_target_determinism_latest_and_hashes():
    rows = pair()
    first = settle(rows)
    assert dumps(settle(list(reversed(rows))+rows)) == dumps(first)
    assert first['settled_at'] is None and len(first['observation_hashes']) == 2
    newer = edit(rows[0],value=None,observed_at='2026-11-01T00:00:00Z')
    assert settle(rows+[newer])['status'] == 'UNASSESSED'
    conflict = edit(rows[0],value=9)
    assert settle(rows+[conflict])['status'] == 'UNASSESSED'
    assert first['target_key'] != settle(rows,line=3.5)['target_key']
    assert dumps(TargetEngine(rows).settle(TARGET,specs=list(reversed(research_markets())))) == dumps(TargetEngine(rows).settle(TARGET))


def test_all_catalog_paths_and_scale():
    # Thousands of capabilities; one index build, dictionary operand lookups.
    rows = history(1500)
    materializer = FeatureMaterializer(rows)
    result = materializer.materialize(TARGET,CUTOFF)
    assert len(result) == 2 * 3 * sum(len(s.windows) for s in CATALOG)
    assert all(r['value'] is None or r['status'] == 'AVAILABLE' for r in result)
    assert all(r['n_available'] <= r['n_eligible'] <= r['n_required'] for r in result)


@pytest.mark.parametrize('kwargs', [dict(family='corners',market='handicap',line=1.5),
    dict(family='goals',market='over',line=.25),dict(family='shots',market='over',line=2.5),
    dict(family='player_sot',market='over',side='home',line=2.5)])
def test_invalid_market_specs(kwargs):
    with pytest.raises(ValueError):
        MarketSpec(**kwargs)


@pytest.mark.parametrize('spec', CATALOG, ids=lambda s:s.name)
def test_each_catalog_family_materializes(spec):
    value = CARDS if spec.metric == 'cards' else 1
    nums = [cap(replace(c.request.fixture),spec.metric,value,c.request.side,spec.period)
            for c in history(5)]
    if spec.metric == 'cards':
        nums = [edit(c,settlement_rules=RESEARCH_CARDS.operand_rules,card_actor_scope='on_field_players') for c in nums]
    if spec.orientation == 'against':
        nums = [cap(c.request.fixture,spec.metric,value,'away',spec.period) for c in nums]
        if spec.metric == 'cards':
            nums = [edit(c,settlement_rules=RESEARCH_CARDS.operand_rules,card_actor_scope='on_field_players') for c in nums]
    denoms = history(5,spec.denominator,value=8) if spec.denominator else []
    r = feature(nums+denoms,spec.name,card_policy=RESEARCH_CARDS)
    expected = RESEARCH_CARDS.count(CARDS) if spec.metric=='cards' else 1
    expected = expected/8 if spec.denominator else expected
    assert r['status'] == 'AVAILABLE' and r['value'] == expected


def test_ordering_cutoff_and_unknown_dates():
    rows = history(6)
    rows = [edit(c,value=i) for i,c in enumerate(rows)]
    assert feature(rows)['value'] == 2
    # Unknown fixture dates and unrelated teams cannot enter the sample.
    unknown = replace(rows[0],request=replace(rows[0].request,fixture=replace(rows[0].request.fixture,match_id='undated',match_date=None)))
    unrelated = cap(replace(TARGET,match_id='unrelated',home_id='X',away_id='Y',match_date='2026-10-20'),value=99)
    assert feature(rows+[unknown,unrelated])['value'] == 2
    result = FeatureMaterializer(rows).materialize(TARGET,'2026-10-28T12:00:00Z',names=['goals_for'],scopes=['overall'])
    home = next(r for r in result if r['side']=='home' and r['window']=='L5')
    assert home['status'] == 'AVAILABLE' and home['value'] == 3
    early = FeatureMaterializer(rows).materialize(TARGET,'2026-10-28T07:00:00Z',names=['goals_for'],scopes=['overall'])
    assert next(r for r in early if r['side']=='home' and r['window']=='L5')['status'] == 'TEMPORAL_INELIGIBLE'
    with pytest.raises(ValueError):
        FeatureMaterializer(rows).materialize(TARGET,'2026-10-31T12:00:00Z')


def test_settlement_wrong_identity_and_orientation():
    for changes in (dict(inspected_entity_id='wrong'),dict(inspected_side='away')):
        rows = pair(); rows[0] = edit(rows[0],**changes)
        assert settle(rows)['status'] == 'UNASSESSED'
    rows = pair(); rows[0] = edit(rows[0],access_blocked_reason='denied')
    assert settle(rows)['status'] == 'BLOCKED_SOURCE'
    with pytest.raises(ValueError,match='conflicts'):
        TargetEngine(pair()).settle(replace(TARGET,stage='wrong'))


def test_ht_ft_invalid_and_second_half_partial_conflict():
    rows = pair(home=0,away=0)+pair('goals_first_half',1,0,'1H')
    assert settle(rows,market='ht_ft')['status'] == 'SETTLEMENT_INCOMPATIBLE'
    rows = pair(home=2,away=1)+pair('goals_first_half',1,0,'1H')+[cap(metric='goals_second_half',period='2H',value=2)]
    assert settle(rows,period='2H',derive_second_half=True)['status'] == 'SETTLEMENT_INCOMPATIBLE'
    rows[-1] = edit(rows[-1],score_scope='including_extra_time')
    assert settle(rows,period='2H',derive_second_half=True)['status'] == 'SETTLEMENT_INCOMPATIBLE'


def test_player_malformed_participation_surface():
    rows = player_evidence()
    rows[1] = edit(rows[1],value=dict(validated=True,rows=[dict(player_id='P1')],completeness_reference='synthetic'))
    assert player_settle(rows)['status'] == 'UNASSESSED'


def test_synthetic_demo_golden():
    import json
    from pathlib import Path
    from v3.flashscore.demo import synthetic_demo
    example = synthetic_demo()
    assert example['sample_kind'] == 'synthetic'
    assert all(r['status']=='AVAILABLE' for r in example['features'])
    assert all(r['status']=='SETTLED' for r in example['targets'])
    assert example == json.loads(Path('docs/v3/flashscore/examples/synthetic-fs-4-5.json').read_text())
