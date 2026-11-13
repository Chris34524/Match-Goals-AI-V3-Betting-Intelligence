"""Synthetic legacy archives only; no acquisition, grant changes or new scrapers."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from v3.flashscore.contract import dumps
from v3.selected_analysis.cli import main
from v3.selected_analysis.engine import analyze
from v3.selected_analysis.evidence import legacy
from v3.selected_analysis.flashscore_reference import coverage, reference
from v3.selected_analysis.report import render
from test_selected_analysis import legacy_history, fixture, GENERATED, CUTOFF


def archive(tmp_path, value=1.25, n=6):
    f, history = legacy_history(tmp_path,n)
    xg = dict(match_id='ABC',partido=dict(local='Home',visitante='Away'))
    for side,team,section in zip(('local','visitante'),('Home','Away'),history['secciones']):
        xg[side] = dict(equipo=team,partidos=[dict(r,equipo=team,condicion_equipo='local',
            xg_local=value,xg_visitante=value/2,xgf=value,xga=value/2,xg_disponible=True)
            for r in section['partidos']])
    snapshot=dict(partido=dict(id='ABC',local='Home',visitante='Away'),estado='ok',
        local=dict(equipo='Home',posicion=3,pj=0,ganados=0,empatados=0,perdidos=0,gf=0,gc=0,dg=0,puntos=0,forma=[]),
        visitante=dict(equipo='Away',posicion=5,pj=6,ganados=2,empatados=1,perdidos=3,gf=5,gc=7,dg=-2,puntos=7,forma=['G','P']))
    (tmp_path/'ABC/xg_history.json').write_text(dumps(xg))
    (tmp_path/'ABC/standings.json').write_text(dumps(snapshot))
    return f,history,xg,snapshot


def test_existing_xg_and_standings_are_displayed_without_model_promotion(tmp_path):
    f,_,_,_=archive(tmp_path)
    report=analyze(f,history_root=tmp_path,generated_at=GENERATED)
    raw=report['flashscore_reference']
    row=next(r for r in raw['observations'] if r['field']=='xg' and r['side']=='home' and r['window']=='L5')
    assert row['value']==1.25 and row['sample_size']==5 and row['coverage']==1
    assert row['observation_status']=='OBSERVED_UNACCREDITED' and not row['eligible_for_model']
    assert row['predictive_status']=='BLOCKED' and row['captured_at'] is None and row['period'] is None
    assert row['source']['sha256'] and len(row['contributing'])==5
    assert report['observed_statistics']['xg']['home']['mean'] is None
    assert report['source_policy']['primary_reference']=='flashscore_mx'
    assert not report['source_policy']['automatic_fallback']
    assert 'clasificación archivada' in render(report) and 'xG/xGA del archivo existente' in render(report)


def test_zero_is_observed_but_missing_is_null(tmp_path):
    f,_,xg,_=archive(tmp_path,value=0)
    form=legacy(f,tmp_path,CUTOFF)
    raw=reference(f,tmp_path,form)
    assert next(r for r in raw['observations'] if r['field']=='xg')['value']==0
    assert next(r for r in raw['observations'] if r['field']=='standings_gf' and r['side']=='home')['value']==0
    for side in ('local','visitante'):
        for row in xg[side]['partidos']:
            row.update(xg_local=None,xg_visitante=None,xgf=None,xga=None,xg_disponible=False)
    (tmp_path/'ABC/xg_history.json').write_text(dumps(xg))
    raw=reference(f,tmp_path,form)
    assert all(r['value'] is None for r in raw['observations'] if r['field'] in ('xg','xga'))


def test_raw_reference_changes_never_change_any_prediction(tmp_path):
    f,_,xg,_=archive(tmp_path)
    before=analyze(f,history_root=tmp_path,generated_at=GENERATED)
    for side in ('local','visitante'):
        for row in xg[side]['partidos']:
            row.update(xg_local=999,xg_visitante=999,xgf=999,xga=999)
    (tmp_path/'ABC/xg_history.json').write_text(dumps(xg))
    after=analyze(f,history_root=tmp_path,generated_at=GENERATED)
    assert before['markets']==after['markets']
    assert before['model_comparison']==after['model_comparison']
    assert before['flashscore_reference']!=after['flashscore_reference']


@pytest.mark.parametrize('change', ['duplicate','wrong_team','future','same_day','wrong_identity','missing_value'])
def test_xg_identity_dates_and_nulls_are_reconciled_before_display(tmp_path,change):
    f,_,xg,_=archive(tmp_path)
    rows=xg['local']['partidos']
    if change=='duplicate':rows.append(deepcopy(rows[0]))
    if change=='wrong_team':rows[0]['equipo']='Away'
    if change=='future':rows[0]['fecha']='07.11.26'
    if change=='same_day':rows[0]['fecha']='06.11.26'
    if change=='wrong_identity':rows[0]['match_id']='OTHER'
    if change=='missing_value':rows[0]['xg_local']=None
    (tmp_path/'ABC/xg_history.json').write_text(dumps(xg))
    raw=reference(f,tmp_path,legacy(f,tmp_path,CUTOFF))
    row=next(r for r in raw['observations'] if r['field']=='xg' and r['side']=='home' and r['window']=='L5')
    assert row['sample_size']==4 and row['coverage']==.8
    assert all(s['match_id']!='Home0' for s in row['contributing'])


def test_standings_wrong_fixture_is_not_shown(tmp_path):
    f,_,_,snapshot=archive(tmp_path)
    snapshot['partido']['id']='OTHER'
    (tmp_path/'ABC/standings.json').write_text(dumps(snapshot))
    raw=reference(f,tmp_path,legacy(f,tmp_path,CUTOFF))
    assert all(r['value'] is None for r in raw['observations'] if r['field'].startswith('standings_'))


@pytest.mark.parametrize('content',['not json','[]','null','{"local":null,"visitante":null}'])
def test_invalid_optional_reference_does_not_crash_goal_analysis(tmp_path,content):
    f,_,_,_=archive(tmp_path)
    (tmp_path/'ABC/xg_history.json').write_text(content)
    report=analyze(f,history_root=tmp_path,generated_at=GENERATED)
    assert report['markets'][0]['status']=='IMPLEMENTED'
    assert all(r['value'] is None for r in report['flashscore_reference']['observations'] if r['field']=='xg')


def test_other_provider_never_reads_flashscore_or_transfers_ids(tmp_path,monkeypatch):
    def blocked(*a,**k):raise AssertionError('no_automatic_flashscore_lookup_for_api_identity')
    monkeypatch.setattr('v3.selected_analysis.flashscore_reference.read_json',blocked)
    result=reference(fixture(),tmp_path,{})
    assert result['status']=='NOT_SELECTED' and result['observations']==[]
    assert result['source_policy']['active_provider']=='api_football'
    assert result['source_policy']['primary_reference']=='flashscore_mx'


def test_read_only_audit_reuses_existing_catalog_and_auditor(tmp_path,monkeypatch,capsys):
    matches=tmp_path/'matches';matches.mkdir()
    f,history,_,_=archive(matches)
    source=tmp_path/'partidos.json'
    raw=dict(id='ABC',fecha='2026-11-06',local='Home',visitante='Away',hora=None)
    source.write_text(dumps([raw,dict(raw,fecha='2026-11-07')]))
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*.json')}
    def blocked(*a,**k):raise AssertionError('audit_must_not_construct_client')
    monkeypatch.setattr('v3.selected_analysis.cli.Client',blocked)
    assert main(['audit-flashscore','--history-root',str(matches)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['corpus']['directories']==1 and result['calendar']['conflicting_ids']==['ABC']
    assert result['network_requests']==0
    rows={r['field']:r for r in result['fields']}
    assert rows['xg']['legacy_extraction']=='IMPLEMENTED' and rows['xg']['period_quality']=='FT_NOT_VERIFIED'
    assert rows['corners']['legacy_extraction']=='NOT_IMPLEMENTED'
    assert rows['corners_1h']['public_visibility']=='UNKNOWN'
    assert all(r['live_acquisition']=='BLOCKED_SOURCE_AUTHORIZATION' for r in result['fields'])
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert main(['audit-flashscore','--live','--history-root',str(matches)])==2


def test_xg_cache_conflicts_remain_excluded(tmp_path):
    matches=tmp_path/'data/matches';matches.mkdir(parents=True)
    f,_,xg,_=archive(matches)
    cache=tmp_path/'data/xg_cache';cache.mkdir()
    (cache/'Home0.json').write_text(dumps(dict(xg['local']['partidos'][0],xg_local=999)))
    raw=reference(f,matches,legacy(f,matches,CUTOFF))
    row=next(r for r in raw['observations'] if r['field']=='xg' and r['side']=='home' and r['window']=='L5')
    assert row['sample_size']==4
    assert any('cache_identity_or_value_conflict' in r['reasons'] for r in raw['exclusions']['home'])


def test_missing_optional_sources_preserve_nulls_and_provenance_cause(tmp_path):
    f,_=legacy_history(tmp_path)
    raw=reference(f,tmp_path,legacy(f,tmp_path,CUTOFF))
    assert raw['sources']==[]
    assert all(r['value'] is None and r['captured_at'] is None for r in raw['observations'])
    assert all(r['reason'] for r in raw['observations'])
