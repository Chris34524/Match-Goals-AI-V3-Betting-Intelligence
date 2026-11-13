"""Deterministic response-shaped fixtures; these are synthetic, never real evidence."""
import ssl  # Load before suite-wide socket replacement.
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import requests
import pytest

from v3.providers.contract import Capture, Identity, digest
from v3.providers.api_football.adapter import Adapter
from v3.providers.api_football.accreditation import assess
from v3.providers.api_football.client import Client, AcquisitionError, quota_headers
from v3.providers.api_football.cohort import plan, collect, audit_manifest, validate_manifest
from v3.providers.api_football.bridge import coverage
from v3.providers.api_football.cli import main
from v3.providers.api_football.normalization import derive_second_half
from v3.providers.api_football.parser import parse_fixture
from v3.providers.api_football.storage import atomic_json
from v3.flashscore.contract import State, Capability, dumps
from v3.flashscore.feature_materializer import FeatureMaterializer
from v3.flashscore.targets import TargetEngine
from v3.flashscore.observation_index import ObservationIndex
from v3.flashscore.market_contract import MarketSpec

FIXTURES = Path(__file__).parent / 'fixtures'
AT = '2025-09-02T12:00:00+00:00'


def payload(name):
    return json.loads((FIXTURES / (name + '.json')).read_text())


def capture(p, endpoint, params=None, live=False):
    return Capture('api_football', endpoint, params or {}, AT, AT, digest(p), {}, live)


def normalized(name='finished', live=False):
    f, s = payload(name), payload('statistics_half')
    fc, sc = capture(f, '/fixtures', live=live), capture(s, '/fixtures/statistics', {'fixture':900001,'half':'true'},live)
    adapter = Adapter()
    return adapter.normalize(f, s, fc, sc), adapter, (f, fc, s, sc)


def get(rows, field, period='FT', side='home'):
    return next(c for c in rows if (c.request.capability_name,c.request.period,c.request.side)==(field,period,side))


def manifest(**kwargs):
    args = dict(cohort_id='test', created_at='2025-09-01T00:00:00+00:00',
        competition_ids=[900], seasons=[2025], fixture_ids=[900001],
        date_from='2025-09-01', date_to='2025-09-02', request_budget=3)
    args.update(kwargs)
    return plan(**args)


class Response:
    def __init__(self, body=None, status=200, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.body = body if body is not None else payload('finished')

    def json(self):
        return self.body


@pytest.fixture
def key(monkeypatch):
    # Deliberately fake credential; never use a real account in tests.
    monkeypatch.setenv('API_FOOTBALL_KEY', 'offline-test-credential')
    monkeypatch.setattr('v3.providers.api_football.client.time.sleep', lambda _: None)


def test_absent_key_no_network(monkeypatch):
    monkeypatch.delenv('API_FOOTBALL_KEY', raising=False)
    with pytest.raises(AcquisitionError, match='BLOCKED_NO_KEY'):
        Client(live=True, max_requests=3)


@pytest.mark.parametrize('kwargs,reason', [({},'explicit_live'),({'live':True},'budget'),
    ({'live':True,'max_requests':0},'budget'),({'live':True,'max_requests':True},'budget')])
def test_client_gates(key, kwargs, reason):
    with pytest.raises(AcquisitionError, match=reason):Client(**kwargs)


@pytest.mark.parametrize('status', [301,400,401,403,404,429,500,503])
def test_http_errors_secret_safe(key, monkeypatch, caplog, status):
    seen=[]
    def fake(url, **kwargs):
        seen.append((url,kwargs))
        return Response(status=status, body={'secret':'offline-test-credential'})
    monkeypatch.setattr(requests,'get',fake)
    client=Client(live=True,max_requests=3)
    with pytest.raises(AcquisitionError) as error:client.get('/fixtures',{'id':900001})
    assert 'offline-test-credential' not in str(error.value) + caplog.text + dumps(client.captures)
    assert len(seen)<=2
    assert all(url=='https://v3.football.api-sports.io/fixtures' and kw['allow_redirects'] is False for url,kw in seen)
    assert len(seen)==(2 if status in (500,503) else 1)


@pytest.mark.parametrize('error', [requests.Timeout,requests.ConnectionError,requests.RequestException])
def test_timeout_network_retry_budget(key,monkeypatch,error):
    def fail(*args,**kwargs):raise error('offline-test-credential')
    monkeypatch.setattr(requests,'get',fail)
    client=Client(live=True,max_requests=1)
    with pytest.raises(AcquisitionError) as exc:client.get('/fixtures',{'id':1})
    assert 'offline-test-credential' not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
    assert client.used==1


def test_retry_success_counted(key,monkeypatch):
    responses=iter([Response(status=503),Response()])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:next(responses))
    client=Client(live=True,max_requests=2)
    data,cap=client.get('/fixtures',{'id':900001})
    assert client.used==2 and cap.payload_sha256==digest(data)
    with pytest.raises(AcquisitionError,match='exhausted'):client.get('/fixtures',{'id':900001})


@pytest.mark.parametrize('headers,expected', [({'X-RateLimit-Remaining':'2','x-ratelimit-requests-remaining':'8'},2),
    ({'x-ratelimit-requests-remaining':'0'},0),({'X-RateLimit-Limit':'100','X-RateLimit-Remaining':'bad'},None)])
def test_quota_headers(key,headers,expected):
    client=Client(live=True,max_requests=3)
    client.quota=quota_headers(headers)
    assert client.remaining==expected
    if expected is not None:
        with pytest.raises(AcquisitionError,match='quota'):client.get('/fixtures',{'id':1})
        assert client.used==0


def test_unknown_quota_large_budget_status_only(key,monkeypatch):
    calls=[]
    def fake(url,**kwargs):
        calls.append(url)
        return Response(dict(errors=[],response=dict(requests=dict(limit_day=100,current=10))))
    monkeypatch.setattr(requests,'get',fake)
    client=Client(live=True,max_requests=10)
    with pytest.raises(AcquisitionError,match='unknown_quota'):client.get('/fixtures',{'id':1})
    assert not calls
    client.get('/status')
    assert client.remaining==90 and client.used==1


@pytest.mark.parametrize('endpoint,params',[('https://evil.test',{}),('/predictions',{'fixture':1}),
    ('/fixtures',{'key':'secret'}),('/fixtures',{'id':'1&key=secret'}),('/fixtures',{'date':'bad?key=secret'})])
def test_endpoint_query_allowlist(key,endpoint,params):
    client=Client(live=True,max_requests=3)
    with pytest.raises(AcquisitionError):client.get(endpoint,params)
    assert client.used==0


@pytest.mark.parametrize('body',[{}, {'errors':['not allowed'],'response':[],'results':0},
    {'errors':[],'response':'oops','results':0},{'errors':[],'response':[{}],'results':1},
    {'errors':[],'response':[],'results':1}])
def test_schema_fail_closed(key,monkeypatch,body):
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(body))
    with pytest.raises(AcquisitionError,match='invalid_provider'):Client(live=True,max_requests=1).get('/fixtures',{'id':1})


@pytest.mark.parametrize('field,value',[('shots',12),('shots_on_target',5),('shots_off_target',4),
    ('blocked_shots',3),('shots_inside_box',8),('shots_outside_box',4),('fouls',10),('corners',6),
    ('offsides',0),('possession',55),('yellow_cards',2),('red_cards',0),('passes',400),
    ('completed_passes',320),('pass_accuracy',80)])
def test_normalized_numeric(field,value):
    rows,adapter,_=normalized()
    c=get(rows,field)
    assert c.state==State.AVAILABLE and c.evidence.value==value
    assert c.request.fixture.provider=='api_football'
    assert Capability.from_dict(c.to_dict())==c
    assert adapter.provenance


def test_null_missing_unknown_labels_reorder_and_orientation():
    rows,adapter,args=normalized()
    assert get(rows,'goalkeeper_saves').state==State.MISSING
    assert get(rows,'shots','1H').state==State.MISSING
    assert get(rows,'shots','1H').evidence.value is None
    assert get(rows,'shots_on_target','1H').evidence.value==0
    assert get(rows,'corners','2H').evidence.value==4
    assert get(rows,'corners',side='home').request.entity_id=='101'
    assert get(rows,'corners',side='away').request.entity_id=='202'
    assert any(p.get('unknown_labels') for p in adapter.provenance)
    f,fc,s,sc=args
    for row in s['response']:row['statistics'].reverse()
    reordered=Adapter().normalize(f,s,fc,replace(sc,payload_sha256=digest(s)))
    assert dumps([c.to_dict() for c in rows]) != dumps([c.to_dict() for c in reordered])  # Raw digest changes.
    assert [(c.request.key,c.evidence.value,c.state) for c in rows]==[(c.request.key,c.evidence.value,c.state) for c in reordered]


@pytest.mark.parametrize('mutation', ['fixture','team','duplicate','digest'])
def test_wrong_identity_and_digest(mutation):
    _,_,(f,fc,s,sc)=normalized()
    if mutation=='fixture':sc=replace(sc,parameters={'fixture':999})
    if mutation=='team':s['response'][0]['team']['id']=999
    if mutation=='duplicate':s['response'].append(deepcopy(s['response'][0]));s['results']+=1
    if mutation!='digest':sc=replace(sc,payload_sha256=digest(s))
    else:sc=replace(sc,payload_sha256='0'*64)
    with pytest.raises(ValueError):Adapter().normalize(f,s,fc,sc)


@pytest.mark.parametrize('field,ft,first,value',[('corners',6,2,4),('shots',0,0,0),
    ('shots_on_target',2,3,None),('fouls',None,1,None),('yellow_cards',3,1,2),
    ('possession',55,40,None),('pass_accuracy',80,70,None),('passes',True,0,None)])
def test_derived_second_half(field,ft,first,value):
    row=derive_second_half(field,ft,first)
    assert row['value']==value and row['status']==('AVAILABLE' if value is not None else 'UNKNOWN')
    assert row['raw_ft']==ft and row['raw_first_half']==first and row['derivation_version']


@pytest.mark.parametrize('name', ['finished','extra_time','shootout'])
def test_scores_separate_extra_time(name):
    rows,_,args=normalized(name)
    assert get(rows,'goals_ft').evidence.value==2
    assert get(rows,'goals_first_half','1H').evidence.value==1
    assert not any(c.request.capability_name=='goals_second_half' for c in rows)
    if name!='finished':assert not get(rows,'corners').settlement_compatible
    settled=TargetEngine(rows).settle(rows[0].request.fixture,
        specs=[MarketSpec('goals','over','2H',line=1.5)],derive_second_half=True)
    assert settled[0]['status']=='SETTLED' and settled[0]['derivation']=='regulation-ft-minus-ht-v1'
    assert settled[0]['raw_operands']


def test_scheduled_unsettled_and_cards_not_conflated():
    rows,_,_=normalized('scheduled')
    assert get(rows,'corners').state==State.UNKNOWN
    assert TargetEngine(rows).settle(rows[0].request.fixture)[0]['status']=='UNSETTLED'
    rows,_,_=normalized()
    assert get(rows,'yellow_cards').evidence.value==2
    assert get(rows,'red_cards').evidence.value==0
    assert get(rows,'cards').state==State.UNKNOWN
    cards=TargetEngine(rows).settle(rows[0].request.fixture,specs=[MarketSpec('cards','over',line=3.5)])
    assert cards[0]['status']=='UNASSESSED'


def test_event_and_lineup_provenance():
    rows,adapter,_=normalized()
    fixture=rows[0].request.fixture
    p=payload('events');events=adapter.events(p,fixture,capture(p,'/fixtures/events',{'fixture':900001}))
    assert [r['detail'] for r in events]==['Yellow Card','Second Yellow card','Red Card']
    assert all(r['actor_scope']=='unknown' for r in events)
    p=payload('lineups');lineups=adapter.lineups(p,fixture,capture(p,'/fixtures/lineups',{'fixture':900001}))
    assert lineups[0]['players'][1]['role']=='bench' and lineups[1]['side']=='away'
    with pytest.raises(ValueError):adapter.lineups(p,fixture,capture(p,'/fixtures/lineups',{'fixture':999}))


def test_capture_accreditation_is_not_temporal_or_training_grant():
    rows,_,args=normalized()
    assert not assess(get(rows,'corners'),*args)['capture_accredited']
    rows,_,args=normalized(live=True)
    result=assess(get(rows,'corners'),*args)
    assert result['capture_accredited'] and not result['historical_asof_accredited']
    assert result['real_model_training']=='BLOCKED'
    assert not get(rows,'corners').prematch_usable('later','2025-10-10','2025-10-09T00:00:00Z')


def test_manifest_serialization_and_digests():
    one=manifest(fixture_ids=[900001,900001])
    two=manifest()
    assert dumps(one)==dumps(two) and digest(one)==digest(two)
    validate_manifest(json.loads(dumps(one)))
    with pytest.raises(ValueError):manifest(fixture_ids=['900001'])
    with pytest.raises(ValueError):manifest(periods=['3H'])
    with pytest.raises(ValueError):manifest(request_budget=0)
    identity=Identity('api_football','team','101','same name','900')
    assert identity != replace(identity,provider_entity_id='202')


def test_cohort_dry_run_cli_and_live_gates(monkeypatch,capsys,tmp_path):
    monkeypatch.delenv('API_FOOTBALL_KEY',raising=False)
    path=tmp_path/'manifest.json';path.write_text(dumps(manifest()))
    assert collect(manifest())['requests_made']==0
    assert main(['cohort','--manifest',str(path)])==0
    assert 'DRY_RUN' in capsys.readouterr().out
    assert main(['cohort','--manifest',str(path),'--live'])==2
    assert main(['cohort','--manifest',str(path),'--live','--max-requests','3'])==0
    assert 'BLOCKED_NO_KEY' in capsys.readouterr().out
    assert main(['smoke'])==0
    assert 'DRY_RUN' in capsys.readouterr().out
    assert main(['smoke','--live'])==0
    assert 'BLOCKED_NO_KEY' in capsys.readouterr().out


def test_cohort_budget_and_successful_bounded_capture(key,monkeypatch,tmp_path):
    with pytest.raises(AcquisitionError,match='explicit'):collect(manifest(),live=True)
    with pytest.raises(AcquisitionError,match='manifest'):collect(manifest(),live=True,max_requests=4)
    with pytest.raises(AcquisitionError,match='planned'):collect(manifest(),live=True,max_requests=1)
    responses=iter([Response(payload('finished')),Response(payload('statistics_half'))])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:next(responses))
    result=collect(manifest(),live=True,max_requests=2,root=tmp_path)
    assert result['requests_made']==2 and result['live_status']=='PARTIAL'
    m=result['manifest'];assert len(m['captures'])==2 and m['hashes']['normalized'] and m['hashes']['audit']
    artifacts=''.join(p.read_text() for p in tmp_path.rglob('*.json'))
    assert 'offline-test-credential' not in artifacts and 'real_model_training' in artifacts


def test_partial_capture_on_wrong_fixture(key,monkeypatch,tmp_path):
    f=payload('finished');f['response'][0]['fixture']['id']=123
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(f))
    result=collect(manifest(),live=True,max_requests=2,root=tmp_path)
    assert result['requests_made']==1 and result['live_status']=='BLOCKED'


def test_coverage_bridge_and_fs4_fs5_semantics():
    rows,_,_=normalized()
    report=coverage(audit_manifest(manifest(),rows),rows)
    assert set(report['metrics']['states'])=={s.value for s in State}
    ready={r['market']:r['ready'] for r in report['markets']['units']}
    assert all(ready[m] for m in ('TOTAL_CORNERS','CORNERS_1H','TEAM_SOT','GOALS_HT','HT_FT'))
    assert not ready['CARDS']
    assert ObservationIndex(rows).fixtures
    specs=[MarketSpec('corners','over',line=9.5),MarketSpec('shots_on_target','over',side='home',line=4.5),
           MarketSpec('goals','over','1H',line=.5),MarketSpec('goals','ht_ft')]
    assert all(r['status']=='SETTLED' for r in TargetEngine(rows).settle(rows[0].request.fixture,specs=specs))
    target=replace(rows[0].request.fixture,match_id='900100',match_date='2025-10-10',lifecycle='scheduled')
    history=[]
    for i in range(5):
        for c in rows:
            f=replace(c.request.fixture,match_id=str(910000+i),match_date=f'2025-09-{i+1:02}')
            # Explicit synthetic lineage proof only: never asserted by live adapter.
            e=replace(c.evidence,inspected_fixture=f,publication_at='2025-09-07T00:00:00Z',
                publication_verified=True,revision_history_verified=True)
            history.append(Capability(replace(c.request,fixture=f),e))
    features=FeatureMaterializer(history).materialize(target,'2025-10-09T00:00:00Z',
        names=['corners_for','sot_for','goals_for','goals_1H_for'],scopes=['overall'])
    l5=[r for r in features if r['window']=='L5']
    assert all(r['status']=='AVAILABLE' for r in l5)
    # Current capture has no historical lineage; actual adapter output remains blocked in FS-4.
    no_lineage=[Capability(c.request,replace(c.evidence,publication_verified=False)) for c in history]
    blocked=FeatureMaterializer(no_lineage).materialize(target,'2025-10-09T00:00:00Z',names=['corners_for'],scopes=['overall'])
    assert any(r['status']=='TEMPORAL_INELIGIBLE' for r in blocked)


def test_atomic_storage_and_protected_paths(tmp_path):
    p=tmp_path/'nested'/'test.json';atomic_json(p,{'zero':0})
    first=p.read_bytes();atomic_json(p,{'zero':0});assert first==p.read_bytes()
    with pytest.raises(ValueError):atomic_json('v3_data/ops/forecast/forbidden.json',{})
    link=tmp_path/'link';link.symlink_to(tmp_path/'nested',target_is_directory=True)
    with pytest.raises(ValueError):atomic_json(link/'bad.json',{})
    from v3.selected_analysis.compatibility import legacy_compatibility
    assert legacy_compatibility(Path(__file__).resolve().parents[3])
    import v3.ops.forecast


def test_authorization_matrix_keeps_flashscore_blocked():
    from v3.features.source_matrix import source_matrix,ingestion_allowed
    from v3.flashscore.collector import live_authorized
    assert any(r['provider']=='api_football' for r in source_matrix())
    for r in source_matrix():
        assert not ingestion_allowed(r['provider'],r['signal_family'])
        assert not live_authorized(r['provider'],'permitted_ingestion',r['signal_family'])


def test_unknown_period_not_invented_and_nonfinite_rejected():
    _,_,(f,fc,s,sc)=normalized()
    for r in s['response']:
        r.pop('statistics_1h');r.pop('statistics_2h')
        r['statistics'][0]={'type':'Corner Kicks','value':None}
        # Remove duplicate canonical field before testing missing periods.
        r['statistics']=[v for v in r['statistics'] if v['type']!='Corner Kicks']
    rows=Adapter().normalize(f,s,fc,replace(sc,payload_sha256=digest(s)))
    assert get(rows,'corners','1H').state==State.UNKNOWN
    assert get(rows,'corners','2H').state==State.UNKNOWN
    assert get(rows,'corners').state==State.MISSING
    from v3.providers.api_football.normalization import number
    for invalid in (True,-1,float('nan'),float('inf'),'12'):
        assert number(invalid,'shots') is None
    for invalid in ('101%','oops%',True,-1):
        assert number(invalid,'possession') is None


def test_quota_not_lost_if_next_response_omits_headers(key,monkeypatch):
    responses=iter([Response(headers={'x-ratelimit-requests-remaining':'10'}),Response()])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:next(responses))
    client=Client(live=True,max_requests=3)
    client.get('/fixtures',{'id':900001});client.get('/fixtures',{'id':900001})
    assert client.remaining==9


def test_response_time_and_minimal_usage_metadata(key,monkeypatch):
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(headers={
        'Date':'Tue, 02 Sep 2025 12:00:00 GMT',
        'x-ratelimit-requests-limit':'100','x-ratelimit-requests-remaining':'80',
        'x-apisports-key':'offline-test-credential'}))
    client=Client(live=True,max_requests=1)
    p,c=client.get('/fixtures',{'id':900001})
    assert c.response_at=='2025-09-02T12:00:00+00:00'
    assert c.quota['x-ratelimit-requests-remaining']==80
    assert 'offline-test-credential' not in dumps(client.captures)


def test_duplicate_labels_and_ambiguous_fixture_status():
    _,_,(f,fc,s,sc)=normalized()
    s['response'][0]['statistics'].append({'type':'Corner Kicks','value':6})
    with pytest.raises(ValueError,match='duplicate_statistic'):
        Adapter().normalize(f,s,fc,replace(sc,payload_sha256=digest(s)))
    f['response'][0]['fixture']['status']['short']='NEW_STATUS'
    with pytest.raises(ValueError,match='unknown_fixture_status'):parse_fixture(f['response'][0])


def test_context_endpoints_standings_and_leagues(key,monkeypatch):
    for endpoint,params,p in [('/standings',{'league':900,'season':2025},
        dict(errors=[],results=1,response=[dict(league=dict(id=900,season=2025,standings=[]))])),
        ('/leagues',{'name':'Test League'},dict(errors=[],results=1,response=[
        dict(league=dict(id=900,name='Test League'),country=dict(name='Test country'),seasons=[dict(year=2025)])]))]:
        monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(p))
        actual,c=Client(live=True,max_requests=1).get(endpoint,params)
        assert actual==p and c.endpoint==endpoint


def test_smoke_success_stays_within_three_mock_requests(key,monkeypatch,tmp_path,capsys):
    calls=[]
    def fake(url,**kwargs):
        calls.append(url)
        return Response(payload('finished' if url.endswith('/fixtures') else 'statistics_half'))
    monkeypatch.setattr(requests,'get',fake)
    assert main(['smoke','--live','--output',str(tmp_path/'smoke.json')])==0
    result=json.loads(capsys.readouterr().out)
    assert result['live_status']=='CAPTURED' and result['requests_made']==3 and len(calls)==3
    assert result['half_status']=='EXPLICIT_DATA' and 'corners' in result['fields_observed']
    assert 'offline-test-credential' not in ''.join(p.read_text() for p in tmp_path.rglob('*.json'))


def test_metadata_resolution_explicit_and_bounded(key,monkeypatch,tmp_path,capsys):
    args=['metadata','--name','Test League','--country','Test country','--season','2025']
    assert main(args)==0 and 'DRY_RUN' in capsys.readouterr().out
    assert main(args+['--live'])==2
    capsys.readouterr()
    p=dict(errors=[],results=1,response=[dict(league=dict(id=900,name='Test League'),
        country=dict(name='Test country'),seasons=[dict(year=2025)])])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(p))
    assert main(args+['--live','--max-requests','1','--output',str(tmp_path/'leagues.json')])==0
    result=json.loads(capsys.readouterr().out)
    assert result['requests_made']==1 and result['competitions'][0]['competition_id']==900


def test_exact_successful_cohort_and_all_manifest_states(key,monkeypatch,tmp_path):
    responses=iter([Response(payload('finished')),Response(payload('statistics_half'))])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:next(responses))
    result=collect(manifest(requested_fields=['corners'],periods=['FT']),live=True,max_requests=2,root=tmp_path)
    assert result['manifest']['status']=='CAPTURED'
    assert collect(manifest())['manifest']['status']=='PLANNED'


def test_remaining_quota_blocks_large_cohort_before_data(key,monkeypatch,tmp_path):
    calls=[]
    def fake(url,**kwargs):
        calls.append(url)
        return Response(dict(errors=[],response=dict(requests=dict(limit_day=2,current=1))))
    monkeypatch.setattr(requests,'get',fake)
    m=manifest(request_budget=5)
    result=collect(m,live=True,max_requests=5,root=tmp_path)
    assert result['requests_made']==1 and calls==['https://v3.football.api-sports.io/status']
    assert result['manifest']['blocked_reasons']==['budget_exceeds_remaining_quota']


def test_credential_echo_and_query_never_escape_transport(key,monkeypatch,caplog):
    p=payload('finished');p['debug']='offline-test-credential'
    monkeypatch.setattr(requests,'get',lambda *a,**kw:Response(p))
    client=Client(live=True,max_requests=2)
    with pytest.raises(AcquisitionError,match='credential_in_query'):
        client.get('/leagues',{'name':'offline-test-credential'})
    assert client.used==0
    with pytest.raises(AcquisitionError,match='invalid_provider_response'):
        client.get('/fixtures',{'id':900001})
    assert client.captures==[] and 'offline-test-credential' not in caplog.text


def test_accreditation_rejects_edited_observation():
    rows,_,args=normalized(live=True)
    c=get(rows,'corners')
    edited=Capability(c.request,replace(c.evidence,value=999))
    result=assess(edited,*args)
    assert not result['capture_accredited']
    assert 'observation_does_not_match_capture_replay' in result['reasons']


def test_storage_failure_reports_actual_requests(key,monkeypatch,tmp_path):
    responses=iter([Response(payload('finished')),Response(payload('statistics_half'))])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:next(responses))
    def fail(*a,**kw):raise OSError('offline-test-credential')
    monkeypatch.setattr('v3.providers.api_football.cohort.atomic_json',fail)
    with pytest.raises(AcquisitionError,match='artifact_write_failed') as exc:
        collect(manifest(requested_fields=['corners'],periods=['FT']),live=True,max_requests=2,root=tmp_path)
    assert exc.value.requests_made==2
    assert 'offline-test-credential' not in str(exc.value)


def test_planned_example_is_offline_and_unresolved():
    p=Path('docs/v3/providers/examples/first-real-pilot.planned.json')
    m=validate_manifest(json.loads(p.read_text()))
    assert m['status']=='PLANNED' and m['fixture_ids']==[]
    assert collect(m)['requests_made']==0


def test_disabled_adapter_cannot_acquire(key,monkeypatch):
    from v3.providers.registry import API_FOOTBALL
    monkeypatch.setattr('v3.providers.api_football.client.registration',lambda _:replace(API_FOOTBALL,enabled=False))
    with pytest.raises(AcquisitionError,match='provider_adapter_not_enabled'):
        Client(live=True,max_requests=3)
