import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError, URLError
import pytest
from v3.odds.provider import Config, load_targets, PROVIDER
from v3.odds.reconciliation import Reconciliation, normalize
from v3.odds.collector import parse, plan, collect_fixture, collect_live
from v3.odds.quota import Budget, estimate, ledger
from v3.odds.the_odds_api import TheOddsAPI, ProviderError, live_status
from v3.odds.storage import publish, digest

FIXTURES = Path(__file__).parent / 'fixtures/odds'
NOW = '2026-11-01T17:00:00Z'


def inputs():
    payload = json.loads((FIXTURES / 'response.json').read_text())
    targets = load_targets(json.loads((FIXTURES / 'targets.json').read_text()))
    config = Config(('soccer_synthetic',), bookmakers=('synthetic_book',))
    rec = Reconciliation({'soccer_synthetic': 'Synthetic League'}, 'synthetic-1')
    return payload, targets, config, rec


def test_parser_orientation_lines_and_clocks():
    payload, targets, config, rec = inputs()
    records, audits, rejected = parse(payload, targets, config, rec, NOW)
    assert len(records) == 11 and not rejected
    assert {r['line'] for r in records if r['market'].startswith('OVER')} == {1.5, 2.5, 3.5}
    assert {r['selection']: r['decimal_odds'] for r in records if r['market'] == '1X2'} == dict(home=2.2, away=3.2, draw=3.4)
    assert {r['selection'] for r in records if r['market'] == 'BTTS'} == {'yes', 'no'}
    assert all(r['observed_at'] == NOW and r['observed_at'] != r['source_published_at'] for r in records)
    assert records == parse(payload, targets, config, rec, NOW)[0]
    assert audits[0]['status'] == 'MATCHED'


@pytest.mark.parametrize('price', [0, 1, -1, float('nan'), float('inf')])
def test_invalid_prices(price):
    p,t,c,r = inputs()
    p[0]['bookmakers'][0]['markets'][0]['outcomes'][0]['price'] = price
    if price != price or price == float('inf'):
        with pytest.raises(ValueError): parse(p,t,c,r,NOW)
    else:
        records,_, rejected = parse(p,t,c,r,NOW)
        assert len(records) == 10 and rejected[0]['reasons'] == ['invalid_decimal_odds']


def test_future_update_and_postkickoff_excluded():
    p,t,c,r = inputs()
    p[0]['bookmakers'][0]['last_update'] = '2026-11-01T17:01:00Z'
    records,_,rejected = parse(p,t,c,r,NOW)
    assert len(records) == 6
    assert all('publication_after_observation' in e['reasons'] for e in rejected)
    assert parse(p,t,c,r,t[0].kickoff_at)[0] == []


def test_no_fill_missing_or_wrong_book():
    p,t,c,r = inputs()
    p[0]['bookmakers'][0]['markets'] = []
    assert parse(p,t,c,r,NOW)[0] == []
    p,t,c,r = inputs()
    assert parse(p,t,replace(c, bookmakers=('absent',)),r,NOW)[0] == []


def test_reconciliation_fail_closed():
    p,t,c,r = inputs()
    assert normalize('Á Team') == normalize('a  team')
    assert r.reconcile(p[0], t+t)[1]['status'] == 'AMBIGUOUS'
    for field, value in [('external_event_id','wrong'),('home','Different'),('sport_key','soccer_other'),('competition','other'),('kickoff_at','2026-11-02T18:00:00Z')]:
        assert r.reconcile(p[0], [replace(t[0], **{field:value})])[0] is None


def test_quota_plan_and_limits():
    _,t,c,_ = inputs()
    assert estimate(c,c.markets) == 3  # three totals lines count once
    assert estimate(replace(c, bookmakers=(), regions=('eu','uk')),c.markets,2) == 12
    assert estimate(replace(c,bookmakers=tuple('book'+str(n) for n in range(11))),c.markets) == 6
    assert plan(c,t)['estimated_cost'] == 3
    b=Budget()
    assert b.check(31) == 'max_credits_per_run'
    assert b.check(3,499) == 'monthly_hard_limit'
    assert b.check(3,449) == 'monthly_soft_limit'
    assert b.check(3,0,2) == 'provider_remaining'
    with pytest.raises(ValueError): plan(c,[replace(t[0],external_event_id=None)])


def test_live_missing_credentials_zero_transport(monkeypatch,tmp_path):
    p,t,c,r=inputs()
    monkeypatch.delenv('THE_ODDS_API_KEY',raising=False)
    def forbidden(*a,**k): pytest.fail('transport_called')
    assert live_status(True) == 'blocked_missing_credentials'
    with pytest.raises(ProviderError,match='missing_credentials'):
        collect_live(t,c,r,live=True,root=tmp_path,adapter=TheOddsAPI(c,forbidden))
    monkeypatch.setenv('THE_ODDS_API_KEY','synthetic-credential-sentinel')
    assert live_status(True) == 'live_enabled'
    monkeypatch.setattr('v3.odds.the_odds_api.source_matrix', lambda **kw: [])
    with pytest.raises(ProviderError,match='authorization'):
        TheOddsAPI(c,forbidden).fetch(c.sports[0],c.markets,event_id='x',live=True)
    with pytest.raises(ProviderError,match='live_flag'):
        collect_live(t,c,r,root=tmp_path)


class Response:
    status=200
    headers={'x-requests-remaining':'497','x-requests-used':'3','x-requests-last':'3'}
    def __init__(self,body): self.body=body
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self): return self.body


def authorized(monkeypatch):
    monkeypatch.setenv('THE_ODDS_API_KEY','synthetic-credential-sentinel')
    monkeypatch.setattr('v3.odds.the_odds_api.source_matrix', lambda **kw: [dict(provider=PROVIDER,status='available',capture_policy='licensed_api',authorization_status='verified_project_grant',acquisition_method='official_api',automatable=True,markets=list(Config(('soccer_synthetic',)).markets))])


@pytest.mark.parametrize('code',[400,401,403,404,422,429,500,503])
def test_http_errors_sanitized(monkeypatch,code):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    calls=[]
    def transport(url,**kw):
        calls.append(url)
        raise HTTPError(url,code,'synthetic-credential-sentinel',{},None)
    with pytest.raises(ProviderError) as e:
        TheOddsAPI(c,transport).fetch(c.sports[0],c.markets,event_id='x',live=True)
    assert str(e.value) == 'http_'+str(code) and e.value.__context__ is None and len(calls)==1


@pytest.mark.parametrize('body,error',[(b'', 'empty_response'),(b'bad','invalid_json'),(b'{}','unexpected_schema'),(b'null','unexpected_schema')])
def test_bad_responses(monkeypatch,body,error):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    with pytest.raises(ProviderError, match=error):
        TheOddsAPI(c,lambda *a,**k:Response(body)).fetch(c.sports[0],c.markets,event_id='x',live=True)


@pytest.mark.parametrize('exc,code',[(TimeoutError('sensitive'),'timeout'),(URLError('sensitive'),'network_error'),(OSError('dns'),'network_error')])
def test_network_errors(monkeypatch,exc,code):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    def fail(*a,**k): raise exc
    with pytest.raises(ProviderError,match=code):
        TheOddsAPI(c,fail).fetch(c.sports[0],c.markets,event_id='x',live=True)


def test_request_paths_headers_and_no_historical(monkeypatch):
    authorized(monkeypatch)
    p,t,c,_=inputs(); seen=[]
    def transport(url,**kw):
        seen.append(url)
        return Response(json.dumps(p[0] if '/events/' in url else p).encode())
    adapter=TheOddsAPI(c,transport)
    payload,h=adapter.fetch(c.sports[0],c.markets,event_id=t[0].external_event_id,live=True)
    assert h == {k:int(v) for k,v in Response.headers.items()}
    adapter.fetch(c.sports[0],('1X2',),event_ids=(t[0].external_event_id,),live=True)
    assert all('/v4/sports/' in u and 'historical' not in u and 'oddsFormat=decimal' in u and 'dateFormat=iso' in u for u in seen)
    with pytest.raises(ProviderError): adapter.fetch(c.sports[0],('BTTS',),event_ids=('x',),live=True)


def test_storage_idempotent_no_overwrite_and_hashes(tmp_path,monkeypatch):
    p,t,c,r=inputs()
    out=collect_fixture(p,t,c,r,observed_at=NOW,root=tmp_path)
    before={f.name:f.read_bytes() for f in out.rglob('*') if f.is_file()}
    assert collect_fixture(p,t,c,r,observed_at=NOW,root=tmp_path)==out
    assert before=={f.name:f.read_bytes() for f in out.rglob('*') if f.is_file()}
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['canonical_sha256']==digest((out/'canonical.jsonl').read_bytes())
    assert manifest['source_sha256']==digest((out/'raw/response.json').read_bytes())
    with pytest.raises(ValueError,match='conflict'): publish(tmp_path,out.name,{'different':b'bad'})
    monkeypatch.setenv('THE_ODDS_API_KEY','synthetic-credential-sentinel')
    p[0]['credential']='synthetic-credential-sentinel'
    with pytest.raises(ProviderError,match='unsafe'): collect_fixture(p,t,c,r,observed_at=NOW,root=tmp_path)


def test_ledger_reserves_on_failure(tmp_path):
    with ledger(tmp_path,NOW) as (state,reserve,headers):
        assert state['used']==0
        reserve(3)
    with ledger(tmp_path,NOW) as (state,reserve,headers): assert state['used']==3
    with ledger(tmp_path,'2026-12-01T00:00:00Z') as (state,reserve,headers): assert state['used']==0


def test_network_guard():
    import socket
    with pytest.raises(AssertionError,match='network_forbidden'): socket.create_connection(('example.com',443))


def test_cli_offline(tmp_path,capsys):
    from v3.odds.cli import main
    base=['--config',str(FIXTURES/'config.json'),'--targets',str(FIXTURES/'targets.json')]
    assert main(['plan',*base])==0
    assert json.loads(capsys.readouterr().out)['estimated_cost']==3
    assert main(['collect-fixture',*base,'--fixture',str(FIXTURES/'response.json'),'--observed-at',NOW,'--output-dir',str(tmp_path)])==0
    capsys.readouterr()
    assert main(['collect-live',*base])==2


def test_live_collection_preserves_provenance_and_reservation(monkeypatch,tmp_path):
    authorized(monkeypatch)
    p,t,c,r=inputs()
    monkeypatch.setattr('v3.odds.collector.utc_now',lambda: NOW)
    adapter=TheOddsAPI(c,lambda *a,**k:Response(json.dumps(p[0]).encode()))
    out=collect_live(t,c,r,live=True,root=tmp_path,adapter=adapter)
    m=json.loads((out/'manifest.json').read_text())
    assert m['credits_actual']==3 and m['status']=='executed'
    for line in (out/'canonical.jsonl').read_text().splitlines():
        record=json.loads(line)
        assert digest((out/record['source']['artifact']).read_bytes())==record['provenance']['sha256']
    with ledger(tmp_path,NOW) as (state,*_):
        assert state['used']==3 and state['remaining']==497
    def failed(*a,**k): raise TimeoutError('sensitive')
    with pytest.raises(ProviderError,match='audit_persisted'):
        collect_live(t,c,r,live=True,root=tmp_path,adapter=TheOddsAPI(c,failed))
    manifests=[json.loads(f.read_text()) for f in tmp_path.glob('*/manifest.json')]
    assert any(m.get('status')=='failed' for m in manifests)
    with ledger(tmp_path,NOW) as (state,*_): assert state['remaining']==494


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1,True,'3'])
def test_invalid_quota_inputs_fail_closed(value):
    with pytest.raises(ValueError): Budget().check(value)


def test_secret_in_untrusted_transport_exception_is_never_echoed(monkeypatch):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    def bad(*a,**k):raise ProviderError(os.environ['THE_ODDS_API_KEY'])
    with pytest.raises(ProviderError) as exc:
        TheOddsAPI(c,bad).fetch(c.sports[0],c.markets,event_id='x',live=True)
    assert str(exc.value)=='transport_error' and exc.value.__context__ is None


def test_output_paths_protected_and_path_traversal(tmp_path):
    from v3.odds.storage import REPO
    with pytest.raises(ValueError,match='outside_v3'):
        publish(REPO/'data/odds','a'*64,{'x':b'x'})
    with pytest.raises(ValueError,match='run_id'):
        publish(tmp_path,'../escape',{'x':b'x'})
    with pytest.raises(ValueError,match='artifact_path'):
        publish(tmp_path,'a'*64,{'../escape':b'x'})


def test_empty_event_list_and_malformed_schema(monkeypatch):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    payload,h=TheOddsAPI(c,lambda *a,**k:Response(b'[]')).fetch(c.sports[0],('1X2',),event_ids=('x',),live=True)
    assert payload==[]
    p,_,_,_=inputs();p[0]['bookmakers'][0]['markets'][0]['outcomes']=[None]
    with pytest.raises(ProviderError,match='schema'):
        TheOddsAPI(c,lambda *a,**k:Response(json.dumps(p).encode())).fetch(c.sports[0],('1X2',),event_ids=('x',),live=True)


def test_error_quota_headers_retained_without_sensitive_details(monkeypatch):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    def fail(url,**kw):raise HTTPError(url,429,'sensitive',Response.headers,None)
    with pytest.raises(ProviderError) as exc:
        TheOddsAPI(c,fail).fetch(c.sports[0],c.markets,event_id='x',live=True)
    assert exc.value.quota_headers['x-requests-remaining']==497
    assert str(exc.value)=='http_429'


def test_failed_collection_does_not_report_unknown_cost_as_zero(monkeypatch,tmp_path):
    authorized(monkeypatch)
    _,t,c,r=inputs()
    monkeypatch.setattr('v3.odds.collector.utc_now',lambda:NOW)
    def fail(*a,**k):raise TimeoutError('sensitive')
    with pytest.raises(ProviderError):collect_live(t,c,r,live=True,root=tmp_path,adapter=TheOddsAPI(c,fail))
    manifest=json.loads(next(tmp_path.glob('*/manifest.json')).read_text())
    assert manifest['credits_actual'] is None and manifest['credits_estimated']==3


@pytest.mark.parametrize('sport,markets,event_id,event_ids',[
    ('soccer_synthetic',(), 'x',()),
    ('soccer_other',('1X2',),'x',()),
    ('soccer_synthetic',('CORNERS',),'x',()),
    ('soccer_synthetic',('1X2',),'../outside',()),
    ('soccer_synthetic',('1X2',),None,()),
])
def test_request_allowlists_fail_before_transport(monkeypatch,sport,markets,event_id,event_ids):
    authorized(monkeypatch)
    _,_,c,_=inputs()
    def forbidden(*a,**k):pytest.fail('transport_called')
    with pytest.raises(ProviderError):
        TheOddsAPI(c,forbidden).fetch(sport,markets,event_id=event_id,event_ids=event_ids,live=True)
