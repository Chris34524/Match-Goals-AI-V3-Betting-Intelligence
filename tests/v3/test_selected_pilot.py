"""Clearly synthetic future-fixture pilot tests; no sports/provider HTTP."""
import json
from pathlib import Path

import pytest

from v3.flashscore.contract import dumps
from v3.selected_analysis import pilot
from v3.selected_analysis.fixtures import normalize
from test_selected_analysis import legacy_history, raw_fixture

BEFORE = '2026-11-06T12:00:00-06:00'


def inputs(tmp_path):
    _,history = legacy_history(tmp_path)
    other = json.loads(dumps(history).replace('ABC','DEF').replace('Home','OtherHome').replace('Away','OtherAway'))
    (tmp_path/'DEF').mkdir()
    (tmp_path/'DEF/history.json').write_text(dumps(other))
    rows = [dict(raw_fixture('ABC','flashscore'),home='Home',away='Away'),
            dict(raw_fixture('DEF','flashscore'),home='OtherHome',away='OtherAway',kickoff='2026-11-06T19:00:00-06:00')]
    records = []
    for row in rows:
        f = normalize(row,'flashscore')
        records.append(dict(provider='flashscore',provider_fixture_id=f['provider_fixture_id'],
            identity=dict(home=f['home']['name'],away=f['away']['name'],date=f['date'],competition=f['competition']),
            kickoff_at=f['kickoff'],timezone='America/Mexico_City',timezone_basis='explicit_utc_offset',
            reviewed_at='2026-11-06T11:00:00-06:00',
            supporting_sources=[dict(url='https://synthetic.invalid/schedule',claim='SYNTHETIC_TEST_ONLY schedule',
                                     evidence_method='synthetic_test_fixture')]))
    source,schedule = tmp_path/'fixtures.json',tmp_path/'schedule.json'
    source.write_text(dumps(rows))
    document = dict(schema_version='pilot-schedule-review-1',synthetic_test_only=True,records=records)
    schedule.write_text(dumps(document))
    return source,schedule,document


def run(tmp_path, **changes):
    source,schedule,_ = inputs(tmp_path)
    args = dict(date='2026-11-06',ids=['ABC','DEF'],history_root=tmp_path,
                output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)
    args.update(changes)
    return pilot.run(source,schedule,**args)


def test_two_future_fixtures_complete_e2e_and_replay(tmp_path):
    directory,result = run(tmp_path)
    assert result['status']=='SYNTHETIC_TEST_ONLY'
    assert result['cutoff']==result['sealed_at']==BEFORE
    assert len(result['reports'])==2 and result['network_requests']==0
    assert not result['oos_eligible'] and result['decision']=='NO_BET'
    assert (directory/'index.html').exists()
    for row in result['reports']:
        report=json.loads((directory/row['json']).read_text())
        assert report['analysis_mode']=='OPERATIONAL_PREMATCH_FROZEN_NOT_OOS'
        assert report['pilot']['input_manifest_sha256']==result['input_manifest_sha256']
        assert [r['market'] for r in report['market_matrix']]==[
            'GOLES','1X2','DOBLE OPORTUNIDAD','xG','PRIMERA MITAD','SEGUNDA MITAD','CÓRNERS','TARJETAS']
        assert report['market_matrix'][0]['status']=='IMPLEMENTED'
        assert all(r['frozen_inputs'] and not r['oos_eligible'] for r in report['market_matrix'])
        assert not report['source_policy']['automatic_fallback']
    assert pilot.replay(directory)['status']=='REPLAY_PASS'


def test_replay_uses_frozen_inputs_when_originals_change(tmp_path):
    directory,_ = run(tmp_path)
    original=tmp_path/'ABC/history.json'
    original.write_text('invalid source after the freeze')
    assert pilot.replay(directory)['status']=='REPLAY_PASS'


def test_frozen_input_mutation_is_rejected(tmp_path):
    directory,_ = run(tmp_path)
    frozen=directory/'inputs/matches/ABC/history.json'
    content=json.loads(frozen.read_text());content['secciones'][0]['partidos'][0]['goles_local']=999
    frozen.write_text(dumps(content))
    with pytest.raises(ValueError,match='snapshot_digest_mismatch'):
        pilot.replay(directory)


def test_additional_snapshot_file_is_rejected(tmp_path):
    directory,_ = run(tmp_path)
    (directory/'inputs/future.json').write_text('{}')
    with pytest.raises(ValueError,match='inventory_changed'):
        pilot.replay(directory)


def test_target_result_is_never_a_frozen_feature(tmp_path):
    source,schedule,_=inputs(tmp_path)
    (tmp_path/'ABC/result.json').write_text(dumps(dict(goals_home=999,goals_away=999)))
    directory,result=pilot.run(source,schedule,date='2026-11-06',ids=['ABC','DEF'],
        history_root=tmp_path,output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)
    assert not any(p.endswith('result.json') for p in result['snapshot_files'])
    report=json.loads((directory/result['reports'][0]['json']).read_text())
    assert report['markets'][0]['expected_total']==3


@pytest.mark.parametrize('ids',[['ABC'],['ABC','ABC'],['ABC','DEF','MISSING']])
def test_exactly_two_unique_known_fixtures_required(tmp_path,ids):
    with pytest.raises(ValueError):
        run(tmp_path,ids=ids)


def test_real_pilot_cannot_set_a_fake_clock(tmp_path):
    with pytest.raises(ValueError,match='test_clock_requires_synthetic'):
        run(tmp_path,synthetic_test_only=False)


def test_past_fixture_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='future_fixture'):
        run(tmp_path,clock=lambda:'2026-11-06T20:00:00-06:00')


def test_clock_crossing_kickoff_during_sealing_is_rejected(tmp_path):
    calls=[]
    def clock():
        calls.append(1)
        return BEFORE if len(calls)<8 else '2026-11-06T18:30:00-06:00'
    with pytest.raises(ValueError,match='seal_not_prematch'):
        run(tmp_path,clock=clock)


@pytest.mark.parametrize('field,value,reason',[
    ('identity',dict(home='Wrong',away='Away',date='2026-11-06',competition='Synthetic League'),'identity_conflict'),
    ('timezone_basis','locale_es_MX','timezone_evidence'),
    ('supporting_sources',[],'independent_schedule_sources'),
    ('reviewed_at','2026-11-07T00:00:00-06:00','temporal_conflict'),
    ('kickoff_at','2026-11-06T18:01:00-06:00','kickoff_conflict')])
def test_schedule_evidence_is_checked(tmp_path,field,value,reason):
    source,schedule,doc=inputs(tmp_path)
    doc['records'][0][field]=value;schedule.write_text(dumps(doc))
    with pytest.raises(ValueError,match=reason):
        pilot.run(source,schedule,date='2026-11-06',ids=['ABC','DEF'],history_root=tmp_path,
                  output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)


def test_missing_history_yields_insufficient_data_without_zero_probability(tmp_path):
    source,schedule,_=inputs(tmp_path)
    (tmp_path/'DEF/history.json').unlink()
    directory,result=pilot.run(source,schedule,date='2026-11-06',ids=['ABC','DEF'],history_root=tmp_path,
                              output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)
    report=json.loads((directory/result['reports'][1]['json']).read_text())
    assert report['markets'][0]['status']=='INSUFFICIENT_DATA'
    assert all(p is None for p in report['market_matrix'][0]['probabilities'].values())
    assert pilot.replay(directory)['status']=='REPLAY_PASS'


def test_report_mutation_is_rejected(tmp_path):
    directory,result=run(tmp_path)
    (directory/result['reports'][0]['html']).write_text('tampered')
    with pytest.raises(ValueError,match='report_digest_mismatch'):
        pilot.replay(directory)


def test_snapshot_symlink_is_rejected(tmp_path):
    directory,_=run(tmp_path)
    frozen=directory/'inputs/matches/ABC/history.json'
    frozen.unlink();frozen.symlink_to(tmp_path/'ABC/history.json')
    with pytest.raises(ValueError,match='symlink'):
        pilot.replay(directory)


def test_independent_markets_operate_with_sufficient_synthetic_capabilities(tmp_path):
    from dataclasses import asdict
    from v3.flashscore.market_contract import RESEARCH_CARDS
    from test_selected_analysis import history, save_caps
    source=tmp_path/'fixtures.json';schedule=tmp_path/'schedule.json'
    rows=[raw_fixture('900001'),dict(raw_fixture('900002'),kickoff='2026-11-06T19:00:00-06:00')]
    source.write_text(dumps(rows))
    records=[]
    for row in rows:
        f=normalize(row,'api_football')
        records.append(dict(provider='api_football',provider_fixture_id=f['provider_fixture_id'],
            identity=dict(home=f['home']['name'],away=f['away']['name'],date=f['date'],competition=f['competition']),
            kickoff_at=f['kickoff'],timezone=f['timezone'],timezone_basis='explicit_utc_offset',
            reviewed_at='2026-11-06T11:00:00-06:00',supporting_sources=[dict(url='https://synthetic.invalid',
                claim='SYNTHETIC_TEST_ONLY',evidence_method='synthetic_test_fixture')]))
    schedule.write_text(dumps(dict(schema_version='pilot-schedule-review-1',synthetic_test_only=True,records=records)))
    caps=save_caps(tmp_path,history(20))
    policy=tmp_path/'policy.json';policy.write_text(dumps(asdict(RESEARCH_CARDS)))
    directory,result=pilot.run(source,schedule,date='2026-11-06',ids=['900001','900002'],provider='api_football',
        history_root=tmp_path/'empty',capability_paths=[caps],card_policy_path=policy,
        output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)
    for row in result['reports']:
        report=json.loads((directory/row['json']).read_text())
        assert report['synthetic_test_only'] and not report['oos_eligible']
        assert report['source_policy']['primary_reference']=='flashscore_mx'
        assert all(g['expected_total'] is not None for g in report['markets'])
        assert all(g['status']=='EXPERIMENTAL' for g in report['markets'][1:])
        assert report['markets'][1]['expected_home']==.5
        assert report['markets'][2]['expected_home']==1
        assert report['markets'][3]['expected_home']==4
    assert pilot.replay(directory)['status']=='REPLAY_PASS'


def test_capability_observed_after_freeze_is_rejected(tmp_path):
    from dataclasses import replace
    from test_selected_analysis import history, save_caps
    source,schedule,_=inputs(tmp_path)
    rows=history()
    rows[0]=replace(rows[0],evidence=replace(rows[0].evidence,observed_at='2026-11-07T12:00:00Z'))
    caps=save_caps(tmp_path,rows)
    with pytest.raises(ValueError,match='observation_after_freeze'):
        pilot.run(source,schedule,date='2026-11-06',ids=['ABC','DEF'],history_root=tmp_path,
            capability_paths=[caps],output=tmp_path/'pilots',clock=lambda:BEFORE,synthetic_test_only=True)
