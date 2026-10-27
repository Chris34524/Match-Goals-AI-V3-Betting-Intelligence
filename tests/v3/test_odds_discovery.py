import json
import traceback
from dataclasses import replace
from urllib.parse import urlsplit
import pytest
from v3.odds.discovery import Discovery, validate_sports, validate_events, reconcile_pilot
from v3.odds.discovery_cli import main
from v3.odds.provider import Target
from v3.odds.reconciliation import Reconciliation
from v3.odds.source_matrix import source_matrix, automatable
from v3.odds.the_odds_api import ProviderError, live_status

SPORT = 'soccer_synthetic'
EVENT = dict(id='event1', sport_key=SPORT, commence_time='2099-01-01T18:00:00Z', home_team='Home', away_team='Away')
SPORT_ROW = dict(key=SPORT, group='Soccer', title='Synthetic', active=True)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('THE_ODDS_API_KEY', 'synthetic-discovery-sentinel')
    def forbidden(*a, **kw):
        pytest.fail('unexpected network')
    monkeypatch.setattr('urllib.request.OpenerDirector.open', forbidden)


class Response:
    status = 200
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps(self.payload).encode()


def test_authorization(monkeypatch):
    row = source_matrix(provider='the_odds_api')[0]
    assert automatable(row)
    assert not automatable({**row, 'authorization_status': 'not_verified_for_project'})
    assert row['snapshots'] == dict(opening='unverified', current='documented', closing='unverified')
    assert live_status(True) == 'live_enabled'
    assert live_status(False) == 'blocked_missing_live_flag'
    monkeypatch.delenv('THE_ODDS_API_KEY')
    assert live_status(True) == 'blocked_missing_credentials'


def test_paths_and_key_validation():
    paths = []
    def transport(url, **kw):
        path = urlsplit(url).path
        paths.append(path)
        assert path in ('/v4/sports', f'/v4/sports/{SPORT}/events')
        return Response([SPORT_ROW] if path == '/v4/sports' else [EVENT])
    client = Discovery((SPORT,), transport=transport)
    assert client.validate_key() == dict(status='valid', provider='the_odds_api')
    assert client.events(SPORT) == [EVENT]
    assert len(paths) == 2


@pytest.mark.parametrize('payload', [{}, [dict(SPORT_ROW, active=1)], [SPORT_ROW, SPORT_ROW], [dict(SPORT_ROW, odds=[])], [dict(SPORT_ROW, key='../bad')]])
def test_bad_sports(payload):
    with pytest.raises(ProviderError): validate_sports(payload)


@pytest.mark.parametrize('payload', [{}, [EVENT, EVENT], [dict(EVENT, commence_time='bad')], [dict(EVENT, commence_time='2099-01-01T18:00:00')], [dict(EVENT, id='../bad')], [dict(EVENT, sport_key='soccer_other')], [dict(EVENT, bookmakers=[])]])
def test_bad_events(payload):
    with pytest.raises(ProviderError): validate_events(payload, SPORT, (SPORT,))


def test_invalid_sport_no_transport():
    with pytest.raises(ProviderError, match='invalid_sport'):
        Discovery((SPORT,)).events('soccer_other')


def test_secret_rejected(capsys, monkeypatch):
    monkeypatch.setattr(Discovery, 'sports_list', lambda self: validate_sports([dict(SPORT_ROW, title='synthetic-discovery-sentinel')]))
    assert main(['sports']) == 2
    assert 'synthetic-discovery-sentinel' not in capsys.readouterr().out


@pytest.mark.parametrize('kind', ['network', 'unexpected', 'http', 'json'])
def test_safe_errors(kind):
    from urllib.error import HTTPError, URLError
    count = []
    def transport(*a, **kw):
        count.append(1)
        if kind == 'http': raise HTTPError('synthetic-discovery-sentinel', 401, 'synthetic-discovery-sentinel', {}, None)
        if kind == 'network': raise URLError('synthetic-discovery-sentinel')
        if kind == 'json': raise ValueError('synthetic-discovery-sentinel')
        raise RuntimeError('synthetic-discovery-sentinel')
    with pytest.raises(ProviderError) as caught:
        Discovery(transport=transport).sports_list()
    assert caught.value.__context__ is None
    assert 'synthetic-discovery-sentinel' not in ''.join(traceback.format_exception(caught.value))
    assert len(count) == 1


def test_reconciliation():
    target = Target('internal', SPORT, 'Competition', '2099', EVENT['commence_time'], 'Home', 'Away', ('1X2',))
    policy = Reconciliation({SPORT: 'Competition'}, 'pilot-1', 0)
    now = '2098-01-01T00:00:00Z'
    assert reconcile_pilot([EVENT], [target], policy, now=now).external_event_id == 'event1'
    with pytest.raises(ProviderError, match='ambiguous'):
        reconcile_pilot([EVENT], [target, replace(target, internal_match_id='other')], policy, now=now)
    with pytest.raises(ProviderError, match='ambiguous'):
        reconcile_pilot([EVENT, dict(EVENT, id='event2')], [target], policy, now=now)
    with pytest.raises(ProviderError, match='no_reconciled'):
        reconcile_pilot([EVENT], [replace(target, home='Other')], policy, now=now)
