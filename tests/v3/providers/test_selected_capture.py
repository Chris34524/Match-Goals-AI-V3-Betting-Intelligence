"""Selected capture regressions: deterministic synthetic data, no live calls."""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from v3.providers.selection import select, provider_id, resolve, load_source
from v3.providers.full_capture import capture, plan
from v3.providers.cli import main
from v3.providers.contract import Capture, digest
from v3.providers.api_football.client import AcquisitionError
from v3.providers.api_football.normalization import derive_second_half
from v3.providers.storage import atomic_json

DATA = Path(__file__).parent / 'fixtures'
AT = '2025-09-02T12:00:00+00:00'
ROW = dict(provider='api_football', provider_fixture_id='900001')


@pytest.mark.parametrize('expression,expected', [('1',[0]), ('1,3,7',[0,2,6]), ('1-5',list(range(5))), ('all',list(range(7)))])
def test_selection(expression, expected):
    assert select(list(range(7)), expression) == expected


@pytest.mark.parametrize('expression', ['', '0', '8', '3-1', '1,x', '-1', '1-2-3'])
def test_invalid_selection(expression):
    with pytest.raises(ValueError):
        select(list(range(7)), expression)


def test_id_and_plan():
    assert provider_id(dict(provider='flashscore', match_id='ABC'), 'api_football') is None
    assert plan([ROW, {}], 'api_football', 2)['estimated_requests'] == 8
    m, _ = capture({}, 'api_football', captured_at=AT)
    assert m['reason'] == 'PROVIDER_ID_UNRESOLVED'
    assert resolve(dict(home='A', away='B'), [])['status'] == 'PROVIDER_ID_UNRESOLVED'


class Fake:
    def __init__(self, maximum=7):
        self.used, self.maximum, self.quota = 0, maximum, {}
    def get(self, endpoint, parameters=None):
        if self.used >= self.maximum:
            raise AcquisitionError('request_budget_exhausted')
        self.used += 1
        name = {'/fixtures':'finished', '/fixtures/statistics':'statistics_half', '/fixtures/events':'events', '/fixtures/lineups':'lineups'}.get(endpoint)
        p = json.loads((DATA / (name+'.json')).read_text()) if name else dict(errors=[], results=0, response=[])
        return p, Capture('api_football', endpoint, parameters or {}, AT, AT, digest(p), {}, False)


def test_full_partial_zero_missing_atomic_deterministic(tmp_path):
    a, caps = capture(ROW, 'api_football', client=Fake(), root=tmp_path, captured_at=AT)
    b, _ = capture(ROW, 'api_football', client=Fake(), captured_at=AT)
    assert a == b
    assert a['request_count'] == 7
    assert a['overall_status'] == 'PARTIAL'
    assert a['surfaces']['standings']['status'] == 'MISSING'
    assert any(c.evidence.value == 0 and c.state.value == 'AVAILABLE' for c in caps)
    stored = tmp_path/'api_football/matches/900001'
    assert json.loads((stored/'manifest.json').read_text()) == a
    assert not list(stored.glob('.provider-*'))
    assert (stored/'stats_1h.json').exists()


@pytest.mark.parametrize('maximum', [0,1,2])
def test_budget(maximum):
    client = Fake(maximum)
    manifest, _ = capture(ROW, 'api_football', client=client, captured_at=AT)
    assert client.used <= maximum
    assert manifest['overall_status'] in ('PARTIAL','BLOCKED')


def test_derivation():
    assert derive_second_half('corners', 7, 2)['value'] == 5
    for field in ('possession','pass_accuracy','ratio'):
        assert derive_second_half(field, 70, 30)['value'] is None


def test_live_block_no_bypass(capsys):
    assert main(['full-capture','--provider','flashscore','--match-id','ABC','--live','--max-requests','10']) == 2
    assert 'BLOCKED_SOURCE_AUTHORIZATION' in capsys.readouterr().out


def test_secret_not_logged(monkeypatch, capsys):
    monkeypatch.setenv('API_FOOTBALL_KEY','secret-testing-value')
    assert main(['full-capture','--provider','api_football','--match-id','bad','--live','--max-requests','1']) == 2
    assert 'secret-testing-value' not in capsys.readouterr().out


def test_text_and_json(tmp_path):
    path = tmp_path/'ids.txt'
    path.write_text('123\n456\n')
    assert len(load_source(path,'api_football')) == 2
    path = tmp_path/'universe.json'
    path.write_text(json.dumps([ROW]))
    assert load_source(path,'api_football') == [ROW]


def test_atomic_failure(tmp_path, monkeypatch):
    path = tmp_path/'manifest.json'
    atomic_json(path, {'old':True})
    import os
    def fail(*args):
        raise OSError('test')
    monkeypatch.setattr(os,'replace',fail)
    with pytest.raises(OSError):
        atomic_json(path, {'new':True})
    assert json.loads(path.read_text()) == {'old':True}
    assert not list(tmp_path.glob('.provider-*'))


def test_flashscore_replay(tmp_path):
    from v3.flashscore.contract import Fixture, Request
    f = Fixture('flashscore','ABC','C','2025','regular','finished','h','a','2025-09-01')
    r = Request(f,'stats_overall','FT','corners',side='home',entity_id='h')
    sample = dict(schema_version='fs-replay-1',sample_kind='synthetic',permission_reference='test',
        inspected_fixture=asdict(f),surface='stats_overall',completeness_reference='test',
        metadata=dict(observed_at=AT, source_url='synthetic://ABC',inspection='success',selected_period='FT',
            selected_period_evidence='FT',period_evidence_method='structured_period',score_scope='regulation'),
        covered_fields=['corners'],stats=[dict(canonical_stat='corners',side='home',entity_id='h',value=0)])
    (tmp_path/'replay.json').write_text(json.dumps(dict(schema_version='fs-replay-batch-1',items=[dict(request=asdict(r),sample=sample)])))
    m, caps = capture(dict(provider='flashscore',match_id='ABC'),'flashscore',replay_dir=tmp_path,captured_at=AT)
    assert m['request_count'] == 0
    assert m['overall_status'] == 'PARTIAL'
    assert caps[0].evidence.value == 0


def test_cli_capture_bridge(tmp_path, monkeypatch, capsys):
    import v3.providers.cli as cli
    monkeypatch.setattr(cli, 'Client', lambda **kw: Fake(kw['max_requests']))
    assert main(['full-capture','--provider','api_football','--match-id','900001',
        '--live','--max-requests','3','--output',str(tmp_path),
        '--build-capabilities','--coverage-audit','--settle-targets']) == 0
    directory = tmp_path/'api_football/matches/900001'
    assert (directory/'coverage.json').exists()
    assert (directory/'targets.json').exists()


def test_resolver_verified_identity():
    candidate = json.loads((DATA/'finished.json').read_text())['response'][0]
    context = dict(date=candidate['fixture']['date'][:10],competition_id=candidate['league']['id'],
        season=candidate['league']['season'],home_id=candidate['teams']['home']['id'],away_id=candidate['teams']['away']['id'])
    row = dict(resolution_context=dict(api_football=context))
    assert resolve(row,[candidate])['status'] == 'RESOLVED'
    assert resolve(row,[candidate,candidate])['status'] == 'PROVIDER_ID_UNRESOLVED'
    context['home_id'] = 'wrong'
    assert resolve(row,[candidate])['status'] == 'PROVIDER_ID_UNRESOLVED'


def test_real_client_full_capture_mocked(tmp_path, monkeypatch, capsys):
    import requests
    monkeypatch.setenv('API_FOOTBALL_KEY','synthetic-test-key')
    calls = []
    class Response:
        status_code = 200
        headers = {'x-ratelimit-requests-remaining':'100'}
        def __init__(self, body):
            self.body = body
        def json(self):
            return self.body
    def get(url, **kwargs):
        endpoint = url.removeprefix('https://v3.football.api-sports.io')
        calls.append(endpoint)
        if endpoint == '/status':
            return Response(dict(errors=[],response=dict(requests=dict(limit_day=100,current=1))))
        name = {'/fixtures':'finished','/fixtures/statistics':'statistics_half','/fixtures/events':'events','/fixtures/lineups':'lineups'}.get(endpoint)
        return Response(json.loads((DATA/(name+'.json')).read_text()) if name else dict(errors=[],results=0,response=[]))
    monkeypatch.setattr(requests,'get',get)
    assert main(['full-capture','--provider','api_football','--match-id','900001','--live',
        '--max-requests','8','--output',str(tmp_path)]) == 0
    assert len(calls) == 8
    m = json.loads((tmp_path/'api_football/matches/900001/manifest.json').read_text())
    assert m['request_count'] == 7  # shared discovery is outside this match
    assert 'synthetic-test-key' not in capsys.readouterr().out
    assert all('synthetic-test-key' not in p.read_text() for p in tmp_path.rglob('*.json'))


@pytest.mark.parametrize('flag', ['--authorized', '--allow-live', '--bypass-authorization'])
def test_no_authorization_cli_flag(flag):
    with pytest.raises(SystemExit):
        main(['full-capture','--provider','flashscore','--match-id','ABC','--live',flag])


def test_foreign_native_fixture_cannot_supply_api_id():
    row = json.loads((DATA/'finished.json').read_text())['response'][0]
    row['provider'] = 'flashscore'
    assert provider_id(row,'api_football') is None


def test_explicit_noncoverage():
    class Noncoverage(Fake):
        def get(self, endpoint, parameters=None):
            payload, evidence = super().get(endpoint, parameters)
            if endpoint == '/fixtures':
                payload['response'][0]['league']['standings'] = False
                evidence = Capture('api_football',endpoint,parameters,AT,AT,digest(payload),{},False)
            return payload, evidence
    m, _ = capture(ROW,'api_football',client=Noncoverage(),captured_at=AT)
    assert m['surfaces']['standings']['status'] == 'NOT_COVERED'
    assert m['request_count'] == 6


def test_selection_secret_not_displayed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('API_FOOTBALL_KEY','synthetic-selection-secret')
    path = tmp_path/'universe.json'
    path.write_text(json.dumps([dict(ROW, home='synthetic-selection-secret')]))
    assert main(['select','--provider','api_football','--source',str(path),'--indices','all']) == 2
    assert 'synthetic-selection-secret' not in capsys.readouterr().out


def test_protected_paths_unchanged():
    import subprocess
    result = subprocess.run(['git','diff','--exit-code','main','--','scraper/','analysis/','v3/ops/'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_verified_matrix_does_not_create_transport(monkeypatch):
    from v3.providers.full_capture import flashscore_live_state
    import v3.flashscore.collector as collector
    calls = []
    def verified(provider, method, family):
        calls.append((provider,method,family))
        return True
    monkeypatch.setattr(collector, 'live_authorized', verified)
    assert flashscore_live_state() == 'BLOCKED_LIVE_TRANSPORT_NOT_IMPLEMENTED'
    assert all(p == 'flashscore' and m == 'permitted_ingestion' for p,m,f in calls)
    assert {f for p,m,f in calls} == {'advanced_team_stats','goalkeeper','players','cards','corners','lineups','context'}
