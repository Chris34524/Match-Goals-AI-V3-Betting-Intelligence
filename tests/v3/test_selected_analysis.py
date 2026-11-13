"""Synthetic inputs only. All HTTP is forbidden by the shared V3 test fixture."""
import ast
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from v3.flashscore.contract import Capability, Evidence, Fixture, Request, dumps
from v3.flashscore.market_contract import RESEARCH_CARDS
from v3.flashscore.normalization import unit_for
from v3.flashscore.observation_index import ObservationIndex
from v3.selected_analysis import fixtures, counts
from v3.selected_analysis.cli import main
from v3.selected_analysis.engine import analyze, advanced_group
from v3.selected_analysis.evidence import ROOT, cutoff_for, legacy, series, target_fixture
from v3.selected_analysis.report import render, write

CUTOFF = '2026-11-06T00:00:00-06:00'
GENERATED = '2026-11-06T12:00:00-06:00'


def raw_fixture(mid='900001', provider='api_football'):
    return dict(provider=provider, provider_fixture_id=mid, date='2026-11-06',
                kickoff='2026-11-06T18:00:00-06:00', competition='Synthetic League',
                competition_id='10', season='2026', country='Synthetic',
                home=dict(id='1', name='Home'), away=dict(id='2', name='Away'), synthetic_test_only=True)


def fixture(mid='900001', provider='api_football'):
    return fixtures.normalize(raw_fixture(mid, provider), provider)


def capability(f, metric, value, period='FT', side='home', **changes):
    surface = 'summary' if metric.startswith('goals_') else {
        'FT': 'stats_overall', '1H': 'stats_first_half', '2H': 'stats_second_half'}[period]
    entity = getattr(f, side+'_id')
    publication = (date.fromisoformat(f.match_date)+timedelta(days=1)).isoformat()+'T08:00:00Z'
    evidence = Evidence(publication, 'synthetic://selected-history', 'synthetic-test-only',
        inspected_fixture=f, inspected_surface=surface, selected_period=period,
        selected_period_evidence='synthetic_period', period_evidence_method='structured_period',
        inspected_side=side, inspected_entity_id=entity, inspection='success', value=value,
        unit=unit_for(metric), score_scope='regulation', acquisition_authorization='verified',
        publication_at=publication, publication_verified=True, revision_history_verified=True,
        evidence_quality='synthetic_test_only')
    if metric == 'cards':
        evidence = replace(evidence, settlement_rules=RESEARCH_CARDS.operand_rules,
                           card_actor_scope=RESEARCH_CARDS.actor_scope)
    return Capability(Request(f, surface, period, metric, 'team', side, entity), replace(evidence, **changes))


def history(n=6, include_cards=True):
    rows = []
    for team in ('1', '2'):
        for i in range(n):
            f = Fixture('api_football', str(10000+int(team)*100+i), '10', '2026', 'regular', 'finished',
                        team, '3', (date(2026, 11, 3)-timedelta(days=i)).isoformat())
            for period in ('FT', '1H', '2H'):
                metric = {'FT': 'goals_ft', '1H': 'goals_first_half', '2H': 'goals_second_half'}[period]
                for side, value in (('home', 2 if period == 'FT' else 1), ('away', 1 if period != '1H' else 0)):
                    rows.append(capability(f, metric, value, period, side))
                    rows.append(capability(f, 'corners', 5 if side == 'home' else 3, period, side))
                    if include_cards:
                        rows.append(capability(f, 'cards', dict(yellow=2, direct_red=0, second_yellow_dismissals=0), period, side))
            for metric in ('xg', 'shots', 'shots_on_target', 'possession'):
                for side in ('home', 'away'):
                    rows.append(capability(f, metric, 1.5 if metric == 'xg' else 2, side=side))
    return rows


def save_caps(tmp_path, rows):
    path = tmp_path/'capabilities.json'
    path.write_text(dumps([c.to_dict() for c in rows]), encoding='utf-8')
    return path


def legacy_history(tmp_path, n=6):
    f = fixture('ABC', 'flashscore')
    f['home']['id'] = f['away']['id'] = None
    data = dict(match_id='ABC', partido=dict(id='ABC', fecha=f['date'], local='Home', visitante='Away'), secciones=[])
    for team in ('Home', 'Away'):
        rows = [dict(match_id=f'{team}{i}', fecha=(date(2026, 11, 3)-timedelta(days=i)).strftime('%d.%m.%y'),
                     local=team, visitante='Opponent', goles_local=2, goles_visitante=1,
                     resultado_parseado=True, score_scope='REGULATION') for i in range(n)]
        data['secciones'].append(dict(titulo='ÚLTIMOS PARTIDOS: '+team, partidos=rows))
    folder = tmp_path/'ABC'; folder.mkdir()
    (folder/'history.json').write_text(dumps(data), encoding='utf-8')
    return f, data


@pytest.mark.parametrize('alias,expected', [('today','2026-11-05'), ('hoy','2026-11-05'),
    ('tomorrow','2026-11-06'), ('mañana','2026-11-06'), ('2026-11-20','2026-11-20')])
def test_local_date_aliases(alias, expected):
    now = datetime(2026, 11, 6, 2, tzinfo=timezone.utc)
    assert fixtures.resolve_date(alias, now=now).isoformat() == expected


@pytest.mark.parametrize('expression', ['0', '7', '3-2', '1,,2', 'nonsense', ''])
def test_invalid_indices(expression):
    with pytest.raises(ValueError):
        fixtures.choose([fixture()], expression)


def test_selection_filters_dedup_and_limit():
    rows = fixtures.universe([raw_fixture(str(900001+i)) for i in range(7)], 'api_football')
    assert len(fixtures.choose(rows, '1,1,3', ['900001'])) == 2
    assert len(fixtures.filtered(rows, date(2026,11,6), country='syn', competition='league', team='away')) == 7
    assert not fixtures.filtered(rows, date(2026,11,7))
    with pytest.raises(ValueError, match='limit'):
        fixtures.choose(rows, 'all')
    assert len(fixtures.choose(rows, 'all', limit=7)) == 7
    with pytest.raises(ValueError, match='not_in_filtered'):
        fixtures.choose(rows, ids=['unknown'])


def test_identity_conflicts_and_quarantine():
    raw = raw_fixture()
    assert len(fixtures.universe([raw, raw], 'api_football')) == 1
    changed = dict(raw, date='2026-11-07', kickoff='2026-11-07T18:00:00-06:00')
    with pytest.raises(ValueError, match='conflicting_fixture'):
        fixtures.universe([raw, changed], 'api_football')
    excluded = []
    assert fixtures.universe([raw, changed, raw], 'api_football', exclusions=excluded) == []
    assert excluded[0]['match_id'] == '900001'
    with pytest.raises(ValueError, match='ambiguous_fixture'):
        fixtures.normalize(dict(raw, provider_ids={'api_football':'4'}), 'api_football')


def test_cross_provider_names_never_resolve_and_exact_context_does():
    foreign = dict(raw_fixture('ABC', 'flashscore'), provider_ids={'api_football':'900001'})
    candidate = dict(fixture=dict(id=900001, date='2026-11-06T18:00:00-06:00'),
                     league=dict(id=10, season=2026, name='Synthetic League'),
                     teams=dict(home=dict(id=1,name='Home'),away=dict(id=2,name='Away')))
    with pytest.raises(ValueError, match='UNRESOLVED'):
        fixtures.universe([foreign], 'api_football', candidates=[candidate])
    foreign['resolution_context'] = {'api_football':dict(date='2026-11-06',competition_id=10,season=2026,home_id=1,away_id=2)}
    resolved = fixtures.universe([foreign], 'api_football', candidates=[candidate])[0]
    assert resolved['provider_ids'] == {'api_football':'900001','flashscore':'ABC'}
    assert resolved['identity_status'] == 'VERIFIED_STABLE_IDS'
    foreign['resolution_context']['api_football']['home_id'] = 2
    with pytest.raises(ValueError):
        fixtures.universe([foreign], 'api_football', candidates=[candidate])


@pytest.mark.parametrize('cutoff', ['2026-11-06T18:00:00-06:00', '2026-11-07T00:00:00Z', '2026-11-06T12:00:00'])
def test_invalid_prematch_cutoff(cutoff):
    with pytest.raises(ValueError):
        cutoff_for(fixture(), cutoff)


def test_legacy_excludes_target_future_duplicates_and_scope(tmp_path):
    f, data = legacy_history(tmp_path)
    rows = data['secciones'][0]['partidos']
    rows.extend([dict(rows[0]), dict(rows[1],match_id='ABC'),
                 dict(rows[1],match_id='future',fecha='07.11.26'),
                 dict(rows[1],match_id='same',fecha='06.11.26'),
                 dict(rows[1],match_id='ambiguous',score_scope='EXTRA_TIME')])
    (tmp_path/'ABC/history.json').write_text(dumps(data))
    result = legacy(f, tmp_path, CUTOFF)
    assert len(result['samples']['home']) == 5
    ids = {s['match_id'] for s in result['samples']['home']}
    assert not ids.intersection({'Home0','ABC','future','same','ambiguous'})
    assert result['observed']['home']['l20']['partial_sample']


def test_insufficient_history_and_missing_xg_are_null(tmp_path):
    f, _ = legacy_history(tmp_path, 2)
    report = analyze(f, history_root=tmp_path, generated_at=GENERATED)
    assert report['markets'][0]['status'] == 'INSUFFICIENT_DATA'
    assert all(m['probability'] is None for g in report['markets'] for m in g['markets'])
    assert report['observed_statistics']['xg']['home']['mean'] is None
    assert not report['oos_eligible'] and report['decision'] == 'NO_BET'


def test_all_supported_markets_have_metadata_and_synthetic_label(tmp_path):
    path = save_caps(tmp_path, history(20))
    report = analyze(fixture(), history_root=tmp_path, capability_paths=[path],
                     generated_at=GENERATED, card_policy=RESEARCH_CARDS)
    assert report['synthetic_test_only']
    assert report['markets'][0]['status'] == 'IMPLEMENTED'
    assert all(g['expected_total'] is not None for g in report['markets'])
    assert all(g['status'] == 'EXPERIMENTAL' for g in report['markets'][1:])
    for g in report['markets']:
        for m in g['markets']:
            assert 0 <= m['probability'] <= 1
            assert m['prematch_cutoff'] and m['model'] and m['sample_size']
            assert m['calibrated'] is False and m['oos_eligible'] is False
    assert report['observed_statistics']['xga']['home']['mean'] == 1.5
    first, second = report['markets'][1:3]
    assert first['expected_home'] == .5 and second['expected_home'] == 1
    assert report['markets'][3]['expected_home'] == 4


@pytest.mark.parametrize('change', [dict(publication_at=CUTOFF), dict(revision_at=CUTOFF),
    dict(publication_verified=False), dict(revision_history_verified=False),
    dict(score_scope='including_extra_time'), dict(acquisition_authorization='unverified')])
def test_temporal_and_authorization_gates(change):
    rows = history()
    i = next(i for i,c in enumerate(rows) if c.request.capability_name=='corners' and c.request.period=='FT')
    rows[i] = replace(rows[i], evidence=replace(rows[i].evidence, **change))
    result = advanced_group(ObservationIndex(rows), target_fixture(fixture()), CUTOFF, 'corners', 'FT')
    assert result['status'] == 'BLOCKED'
    assert all(m['probability'] is None for m in result['markets'])


@pytest.mark.parametrize('family,period,metric', [('goals','1H','goals_first_half'),
    ('goals','2H','goals_second_half'), ('corners','FT','corners'), ('corners','1H','corners')])
def test_missing_period_or_corner_does_not_backfill(family,period,metric):
    rows = [c for c in history() if not (c.request.period==period and c.request.capability_name==metric)]
    group = advanced_group(ObservationIndex(rows), target_fixture(fixture()), CUTOFF, family, period)
    assert group['status'] == 'INSUFFICIENT_DATA'
    assert group['expected_total'] is None
    assert all(m['probability'] is None for m in group['markets'])


@pytest.mark.parametrize('policy', [None, replace(RESEARCH_CARDS, operand_rules='incompatible')])
def test_incompatible_card_semantics_block(policy):
    result = advanced_group(ObservationIndex(history()),target_fixture(fixture()),CUTOFF,'cards','FT',policy)
    assert result['status'] == 'BLOCKED' and result['expected_total'] is None
    assert all(m['probability'] is None for m in result['markets'])


def test_count_families_and_temporal_holdout():
    poisson = counts.fit([4]*20)
    negative_binomial = counts.fit([0,0,0,16]*5)
    assert poisson['family'] == 'poisson' and negative_binomial['family']=='negative_binomial'
    assert counts.over(0.5,[dict(mean=0,dispersion_alpha=0)]) == 0
    assert counts.over(2.5,[dict(mean=1,dispersion_alpha=0)]*2) == pytest.approx(
        counts.over(2.5,[dict(mean=2,dispersion_alpha=0)]))
    assert counts.evaluate([3]*6,[7.5])['status']=='INSUFFICIENT_DATA'
    result = counts.evaluate([0,1,2,3,4]*4,[2.5,3.5])
    assert result['n_train']==14 and result['n_validation']==6 and not result['calibrated']
    assert result['metrics']['poisson']['brier'] >= 0


def test_future_and_target_stats_cannot_change_probabilities():
    rows = history()
    baseline = advanced_group(ObservationIndex(rows), target_fixture(fixture()), CUTOFF, 'corners', 'FT')
    f = rows[0].request.fixture
    extras = [capability(replace(f,match_id=mid,match_date=d), 'corners', 999)
              for mid,d in [('900001','2026-11-01'),('future','2026-11-07'),('same','2026-11-06')]]
    result = advanced_group(ObservationIndex(rows+extras),target_fixture(fixture()),CUTOFF,'corners','FT')
    assert result == baseline


def test_reproducible_json_html_and_safe_output(tmp_path):
    f, _ = legacy_history(tmp_path)
    before = (tmp_path/'ABC/history.json').read_bytes()
    report = analyze(f, history_root=tmp_path, generated_at=GENERATED)
    again = analyze(f, history_root=tmp_path, generated_at=GENERATED)
    assert dumps(report)==dumps(again)
    folder = write(report,tmp_path/'reports')
    assert write(again,tmp_path/'reports') == folder
    assert json.loads((folder/'report.json').read_text())==report
    document = (folder/'report.html').read_text()
    assert 'NO_BET' in document and 'INSUFFICIENT_DATA' in document
    assert 'src="http' not in document and 'href="http' not in document
    report['fixture']['home']['name']='<script>alert(1)</script>'
    assert '<script>alert(1)</script>' not in render(report)
    assert (tmp_path/'ABC/history.json').read_bytes()==before
    with pytest.raises(ValueError,match='outside_isolated'):
        write(report,ROOT/'data')


def test_dry_run_never_constructs_http_client(tmp_path,monkeypatch,capsys):
    def blocked(*a,**k):
        raise AssertionError('HTTP_client_not_allowed')
    monkeypatch.setattr('v3.selected_analysis.cli.Client',blocked)
    path=tmp_path/'fixtures.json';path.write_text(dumps([raw_fixture()]))
    assert main(['analyze','--provider','api_football','--source',str(path),'--date','2026-11-06',
                 '--indices','1','--dry-run','--output',str(tmp_path/'output')])==0
    assert not (tmp_path/'output').exists()
    assert '"network_requests":0' in capsys.readouterr().out


def test_flashscore_live_remains_blocked(capsys):
    assert main(['list','--live'])==2
    assert 'BLOCKED_SOURCE_AUTHORIZATION' in capsys.readouterr().out


def test_live_requires_explicit_budget_and_key(monkeypatch,capsys):
    monkeypatch.delenv('API_FOOTBALL_KEY',raising=False)
    assert main(['list','--provider','api_football','--live'])==2
    assert 'explicit_positive_request_budget_required' in capsys.readouterr().out
    assert main(['list','--provider','api_football','--live','--max-requests','1'])==2
    assert 'BLOCKED_NO_KEY' in capsys.readouterr().out


def test_cli_offline_end_to_end_is_reproducible(tmp_path,capsys):
    f, _ = legacy_history(tmp_path)
    source=tmp_path/'fixtures.json';source.write_text(dumps([dict(raw_fixture('ABC','flashscore'),home='Home',away='Away')]))
    args=['analyze','--source',str(source),'--date','2026-11-06','--match-id','ABC',
          '--history-root',str(tmp_path),'--output',str(tmp_path/'reports'),'--generated-at',GENERATED]
    assert main(args)==0
    first=[json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    assert main(args)==0
    second=[json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    assert first==second
    reports=list((tmp_path/'reports').glob('*/*/*/report.json'))
    assert len(reports)==1
    report=json.loads(reports[0].read_text())
    assert report['network_requests']==0 and report['capture']['captured_at'] is None


def test_live_discovery_and_capture_share_a_hard_budget(tmp_path,monkeypatch,capsys):
    # Synthetic mocked official HTTP only; the global network fixture stays active.
    import requests
    row=json.loads((ROOT/'tests/v3/providers/fixtures/scheduled.json').read_text())['response'][0]
    row['fixture']['id']=900001
    row['fixture']['date']='2026-11-06T18:00:00-06:00'
    payload=dict(response=[row],results=1,errors=[],paging=dict(total=1))
    calls=[]
    class Response:
        status_code=200
        headers={}
        def json(self):
            return payload
    def get(url,**kwargs):
        calls.append(url)
        return Response()
    monkeypatch.setenv('API_FOOTBALL_KEY','synthetic-test-key')
    monkeypatch.setattr(requests,'get',get)
    monkeypatch.chdir(tmp_path)
    assert main(['analyze','--provider','api_football','--date','2026-11-06','--indices','1',
                 '--live','--max-requests','2','--output',str(tmp_path/'reports'),
                 '--history-root',str(tmp_path/'empty')])==0
    assert len(calls)==2
    out=capsys.readouterr().out
    assert '"execution_request_count":2' in out and 'synthetic-test-key' not in out
    report=json.loads(next((tmp_path/'reports').glob('*/*/*/report.json')).read_text())
    assert report['capture']['overall_status']=='PARTIAL' and report['decision']=='NO_BET'


def test_capture_reversed_stable_identity_is_blocked():
    from v3.selected_analysis.cli import validate_capture_identity
    f=fixture()
    manifest=dict(reason=None,completed_surfaces=['fixture'],provider_fixture_id='900001',competition='10',
                  season='2026',home=dict(id='2'),away=dict(id='1'),kickoff=f['kickoff'])
    with pytest.raises(ValueError,match='identity_conflict'):
        validate_capture_identity(f,manifest)


def test_future_cutoff_and_invalid_identity_cannot_escape_output(tmp_path):
    with pytest.raises(ValueError,match='follow_generation'):
        analyze(fixture(),history_root=tmp_path,cutoff=CUTOFF,generated_at='2026-11-05T23:00:00-06:00')
    report=analyze(fixture(),history_root=tmp_path,generated_at='2026-11-05T23:00:00-06:00')
    assert report['cutoff']=='2026-11-05T23:00:00-06:00'
    report['fixture']['provider_fixture_id']='../../escape'
    with pytest.raises(ValueError,match='invalid_report_identity'):
        write(report,tmp_path/'reports')


def test_conflicting_capabilities_and_untyped_card_totals_fail_closed():
    rows=history(include_cards=False)
    original=next(c for c in rows if c.request.capability_name=='corners')
    with_conflict=rows+[replace(original,evidence=replace(original.evidence,value=99))]
    result=advanced_group(ObservationIndex(with_conflict),target_fixture(fixture()),CUTOFF,'corners','FT')
    assert result['status']=='BLOCKED'
    result=advanced_group(ObservationIndex(rows),target_fixture(fixture()),CUTOFF,'cards','FT',RESEARCH_CARDS)
    assert result['status']=='INSUFFICIENT_DATA' and result['expected_total'] is None


def test_card_components_do_not_double_count_second_yellow():
    rows=history()
    rows=[replace(c,evidence=replace(c.evidence,value=dict(yellow=2,direct_red=1,second_yellow_dismissals=1)))
          if c.request.capability_name=='cards' else c for c in rows]
    group=advanced_group(ObservationIndex(rows),target_fixture(fixture()),CUTOFF,'cards','FT',RESEARCH_CARDS)
    assert group['expected_home']==4 and group['expected_total']==8
    assert group['expected_dismissals_total']==4
    assert group['observed_components']['home']['direct_red']==1
    assert next(m for m in group['markets'] if m['market']=='ANY_DISMISSAL')['probability']>0


def test_champion_formula_ast_matches_initial_commit():
    tree=ast.parse((ROOT/'analysis/compare_lambda.py').read_text())
    main_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    def assignment(node,name):
        return isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets)
    start=next(i for i,n in enumerate(main_node.body) if assignment(n,'obs'))
    end=next(i for i,n in enumerate(main_node.body) if assignment(n,'archivo_salida'))
    digest=hashlib.sha256(ast.dump(ast.Module(body=main_node.body[start:end],type_ignores=[]),include_attributes=False).encode()).hexdigest()
    assert digest=='bc0fed8fd2e3c07344f50c450f2dd94488487d98e292a219046f920c54dafc10'


def test_exact_compatibility_exception_rejects_model_or_other_changes():
    from v3.selected_analysis.compatibility import presentation_only
    baseline=subprocess.check_output(['git','show','HEAD:analysis/compare_lambda.py'],cwd=ROOT,text=True)
    current=(ROOT/'analysis/compare_lambda.py').read_text()
    assert presentation_only(current,baseline)
    assert not presentation_only(current.replace('0.45,','0.46,',1),baseline)
    assert not presentation_only(current+'\nprint(123)\n',baseline)


def test_compare_lambda_none_regression_keeps_null_and_all_models(tmp_path):
    f, _=legacy_history(tmp_path)
    form=legacy(f,tmp_path,CUTOFF)
    directory=tmp_path/'data/matches/ABC';directory.mkdir(parents=True)
    enriched=dict(partido=dict(fecha='2026-11-06'),datos_observados=dict(
        local=form['observed']['home'],visitante=form['observed']['away'],
        temporada=dict(local=dict(promedio_gf=None,promedio_gc=None),
                       visitante=dict(promedio_gf=None,promedio_gc=None))))
    for name,value in [('enriched',enriched),('xg_history',dict(local=dict(partidos=[]),visitante=dict(partidos=[]))),('h2h_analysis',{})]:
        (directory/(name+'.json')).write_text(dumps(value))
    import os
    run=subprocess.run([sys.executable,'-W','error','-m','analysis.compare_lambda','--match-id','ABC'],
        cwd=tmp_path,env=dict(os.environ,PYTHONPATH=str(ROOT)),capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert 'N/D' in run.stdout
    result=json.loads((directory/'lambda_comparison.json').read_text())
    assert result['metodos']['G_temporada']==dict(local=None,visitante=None,total=None)
    assert result['metodos']['J_BT_sin_temporada']['total']==3
