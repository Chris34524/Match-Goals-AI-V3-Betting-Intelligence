"""All fixtures here are synthetic_test_only; no runtime real evidence is created."""
import json
import hashlib
from dataclasses import asdict
from pathlib import Path
import pytest
from v3.ops import prospective, target_discovery, oos, promotion, runtime

NOW='2026-11-01T09:00:00Z'


def internal():
    return dict(synthetic_test_only=False, internal_match_id='synthetic-contract-target',
                kickoff_accredited=True,kickoff_lineage={},
                kickoff_at='2026-11-02T12:00:00Z',season='explicit-fixture-season',
                sport_key='soccer_epl',competition='Premier League',home='Home',away='Away')


@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(prospective,'now',lambda:NOW)
    return tmp_path


def evidence(tmp_path, row):
    identity={k:row[k] for k in ('internal_match_id','home','away','competition')}
    record=dict(source_record_id='record-1', identity=identity, kickoff_at=row['kickoff_at'],
                captured_at=NOW, timezone_basis='explicit_utc_offset', synthetic_test_only=False)
    document=dict(synthetic_test_only=False, records=[record])
    lineage=dict(version='kickoff-lineage-v1', source_record_id='record-1', identity=identity,
                 kickoff_field='kickoff_at', kickoff_value=row['kickoff_at'],
                 captured_at=NOW, timezone_basis='explicit_utc_offset')
    return document,lineage


def seal(tmp_path, document, lineage):
    raw=json.dumps(document).encode();digest=hashlib.sha256(raw).hexdigest()
    path=tmp_path/'v3_data/ops/evidence'/ (digest+'.json')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    lineage.update(source_path=str(path),source_sha256=digest)
    return path


@pytest.fixture(autouse=True)
def evidence_root(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)


def source(tmp_path,row):
    if row.get('kickoff_lineage') == {}:
        document,lineage=evidence(tmp_path,row)
        seal(tmp_path,document,lineage);row=dict(row,kickoff_lineage=lineage)
    path=tmp_path/'internal.json';path.write_text(json.dumps([row]));return path


@pytest.mark.parametrize('patch',[{'kickoff_at':'2026-11-02T12:00:00'}, {'kickoff_at':'2026-10-01T12:00:00Z'},
                                   {'kickoff_accredited':False},{'kickoff_lineage':None},{'season':None},
                                   {'synthetic_test_only':True}])
def test_ops_target_fail_closed(tmp_path,patch):
    report=target_discovery.inspect(NOW,[source(tmp_path,dict(internal(),**patch))])
    assert report['targets']==[] and report['internal_target_status']=='BLOCKED_NO_FRESH_INTERNAL_TARGET'


def test_ops_target_independent_and_duplicate(tmp_path):
    path=source(tmp_path,internal());result=target_discovery.inspect(NOW,[path])
    assert len(result['targets'])==1 and result['targets'][0]['external_event_id'] is None
    row=json.loads(path.read_text())[0];path.write_text(json.dumps([row,row]))
    with pytest.raises(ValueError,match='ambiguous'):target_discovery.inspect(NOW,[path])


def test_ops_legacy_timezone_not_inferred(tmp_path):
    row=dict(id='synthetic',pais='ESPAÑA',competicion='LaLiga EA Sports',fecha='2026-11-02',hora='14:00')
    assert target_discovery.inspect(NOW,[source(tmp_path,row)])['targets']==[]


def test_ops_bounded_discovery_no_retry(isolated,monkeypatch):
    inv=dict(internal_target_status='BLOCKED_NO_FRESH_INTERNAL_TARGET',targets=[],candidates=[],evidence=[],exclusions={})
    monkeypatch.setattr(prospective,'inspect',lambda *a:inv)
    calls=[]
    class Fake:
        def __init__(self,*a):pass
        def sports_list(self):
            calls.append('sports');raise prospective.ProviderError('network_error')
    monkeypatch.setattr(prospective,'Discovery',Fake)
    r=prospective.prepare(live=True);prospective.prepare(live=True)
    assert calls==['sports'] and r['capture_status']=='BLOCKED_NO_FRESH_INTERNAL_TARGET'
    assert prospective.tick()['odds_calls_attempted']==0


def test_ops_unique_plan_single_credit(isolated,monkeypatch):
    target=target_discovery.inspect(NOW,[source(isolated,internal())])
    monkeypatch.setattr(prospective,'inspect',lambda *a:target)
    calls=[]
    class Fake:
        def __init__(self,*a):pass
        def sports_list(self):return [dict(key='soccer_epl',active=True)]
        def events(self,sport):
            calls.append(sport)
            return [dict(id='external-synthetic',sport_key=sport,home_team='Home',away_team='Away',commence_time=internal()['kickoff_at'])]
    monkeypatch.setattr(prospective,'Discovery',Fake)
    r=prospective.prepare(live=True)
    assert calls==['soccer_epl'] and r['plan']['estimated_cost']==1 and r['plan']['rejection'] is None
    assert len(r['plan']['calls'])==1 and r['external_event_id_present']
    assert prospective.BUDGET.max_credits_per_run==1


def test_ops_capture_requires_validation_and_target(isolated,monkeypatch):
    from v3.ops import validation
    monkeypatch.setattr(validation,'receipt_valid',lambda:False)
    assert prospective.capture(live=True)['capture_status']=='BLOCKED_VALIDATION_REQUIRED'
    monkeypatch.setattr(validation,'receipt_valid',lambda:True)
    assert prospective.capture(live=True)['capture_status']=='BLOCKED_NO_FRESH_INTERNAL_TARGET'
    assert prospective.tick()['odds_calls_attempted']==0


def test_ops_failed_capture_terminal(isolated,monkeypatch):
    from v3.ops import validation
    target=target_discovery.inspect(NOW,[source(isolated,internal())])
    monkeypatch.setattr(prospective,'inspect',lambda *a:target)
    row=dict(target['targets'][0],external_event_id='external-synthetic')
    runtime.write(runtime.ROOT/'pilot-targets.json',[row])
    monkeypatch.setattr(validation,'receipt_valid',lambda:True)
    monkeypatch.setattr('v3.odds.the_odds_api.authorize',lambda *a:None)
    calls=[]
    def fail(*a,**kw):
        calls.append(True);raise prospective.ProviderError('collection_failed_audit_persisted')
    monkeypatch.setattr(prospective,'collect_live',fail)
    first=prospective.capture(live=True);second=prospective.capture(live=True)
    assert len(calls)==1 and first['credits']['credits_reserved']==1
    assert second['capture_status']=='ALREADY_ATTEMPTED_NO_RETRY'
    assert first['credits']['credits_reported_used'] is None


@pytest.mark.parametrize('count,state',[(0,'COLLECTING'),(49,'COLLECTING'),(50,'CHECKPOINT_50'),(99,'CHECKPOINT_50'),
                                         (100,'CHECKPOINT_100'),(199,'CHECKPOINT_100'),(200,'GATE_MET'),(201,'GATE_MET')])
def test_ops_checkpoints(count,state):
    assert oos.checkpoint(count)==state


def test_ops_synthetic_never_real():
    records=[dict(synthetic_test_only=True,paper_bet_id=str(i),internal_match_id=str(i),decision='PASS',status='SETTLED') for i in range(201)]
    r=oos.report(records)
    assert r['real_oos_count']==0 and r['synthetic_excluded']==201
    assert r['checkpoint_status']=='COLLECTING' and not r['metrics_available']


def test_ops_duplicates_no_inflation():
    from test_performance_oos_final import real_position
    # Existing counter contract fixture only; never serialized as operational evidence.
    row=dict(real_position(),market='1X2')
    assert oos.report([row,row])['duplicate_records_excluded']==1
    assert oos.report([row,row])['records_total']==2
    assert oos.report([row,row])['duplicate_identity_records_ineligible']==2
    assert oos.report([row,row])['real_oos_count']==0


def test_ops_promotion_roi_alone_blocked():
    r=promotion.recommend(oos.report([]),dict(roi=1000))
    assert r['promotion_status']=='BLOCKED' and r['human_confirmation_required'] and not r['auto_promotion']
    assert r['champion']=='BT0 / J_BT_sin_temporada' and not r['champion_changed']


def test_ops_paper_missing_and_unsettled(isolated):
    from v3.ops.paper_cycle import paper,settle
    r=paper();assert r['candidate_status']=='BLOCKED' and not r['paper_entry_created']
    assert r['stake_units']==1 and r['real_oos_contribution']==0
    assert settle()['settlement']=='UNSETTLED'


def test_ops_runtime_secret_and_escape(isolated,monkeypatch):
    monkeypatch.setenv('THE_ODDS_API_KEY','synthetic-ops-credential')
    with pytest.raises((ValueError,prospective.ProviderError)):
        runtime.write(runtime.ROOT/'secret.json',{'text':'synthetic-ops-credential'})
    with pytest.raises(ValueError):runtime.write(Path('/tmp/escape.json'),{})
    assert not (runtime.ROOT/'secret.json').exists()


def test_ops_report_deterministic(isolated):
    from v3.ops.report import report
    assert report()==report()
    assert report()['O05']['real_oos_count']==0


def test_ops_no_polling_or_new_http():
    import ast
    for path in Path(__file__).resolve().parents[2].joinpath('v3/ops').glob('*.py'):
        tree=ast.parse(path.read_text())
        assert not any(isinstance(n,ast.While) for n in ast.walk(tree))
        denied={'urllib','requests','httpx','socket','time'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):assert not {a.name.split('.')[0] for a in node.names}&denied
            if isinstance(node,ast.ImportFrom) and node.module:assert node.module.split('.')[0] not in denied


def test_ops_baseline_digest_tampering(isolated,monkeypatch):
    from v3.ops import validation
    baseline=isolated/'baseline.json';baseline.write_text('{}')
    summary=isolated/'summary.json';summary.write_text(json.dumps(dict(inventory_path=str(baseline),inventory_sha256='0'*64)))
    monkeypatch.setattr(validation,'SUMMARY',summary)
    with pytest.raises(ValueError,match='digest_mismatch'):validation.batch_baseline()


def test_ops_receipt_rejects_code_change(isolated,monkeypatch):
    from v3.ops import validation
    runtime.write(runtime.ROOT/'validation-receipt.json',dict(source_digest='original',suite='PASS',final_validator='PASS',ops_validator='PASS'))
    monkeypatch.setattr(validation,'source_digest',lambda:'original')
    assert validation.receipt_valid()
    monkeypatch.setattr(validation,'source_digest',lambda:'modified')
    assert not validation.receipt_valid()


def test_ops_no_candidate_decision_idempotent(isolated):
    from v3.ops.paper_cycle import paper
    paper();paper()
    assert len(list((runtime.ROOT/'decisions').glob('*.json')))==1
    assert oos.report()['blocked_picks']==0
    assert not Path('v3_data/paper/ledger.jsonl').exists()


def test_ops_closing_current_is_blocked():
    from v3.ops.closing import report
    r=report()
    assert r['real_status']=='BLOCKED_PROVIDER_CLOSING_SEMANTICS'
    assert not r['closing_accredited'] and r['clv_value'] is None


@pytest.mark.parametrize('case,code',[
    ('string','kickoff_lineage_invalid'), ('none','kickoff_lineage_invalid'),
    ('version','kickoff_lineage_invalid'),
    ('missing','kickoff_lineage_source_missing'), ('symlink','kickoff_lineage_source_symlink'),
    ('hash','kickoff_lineage_digest_mismatch'), ('modified','kickoff_lineage_digest_mismatch'),
    ('internal_match_id','kickoff_lineage_identity_mismatch'), ('home','kickoff_lineage_identity_mismatch'),
    ('away','kickoff_lineage_identity_mismatch'), ('competition','kickoff_lineage_identity_mismatch'),
    ('kickoff','kickoff_lineage_kickoff_mismatch'), ('naive','kickoff_lineage_timestamp_invalid'),
    ('basis','kickoff_timezone_basis_missing'), ('self','kickoff_lineage_not_independent'),
    ('synthetic','kickoff_lineage_synthetic'), ('duplicate','kickoff_lineage_identity_mismatch'),
    ('naive_capture','kickoff_lineage_timestamp_invalid'),
    ('late_capture','kickoff_lineage_capture_not_prospective'),
    ('inferred_basis','kickoff_timezone_basis_missing'),
    ('outside','kickoff_lineage_source_outside_root'),
    ('mutable','kickoff_lineage_not_immutable'),
])
def test_ops_lineage_negative_cases(isolated,monkeypatch,case,code):
    row=internal();document,lineage=evidence(isolated,row)
    if case in ('internal_match_id','home','away','competition'):
        document['records'][0]['identity']=dict(lineage['identity'],**{case:'wrong'})
    if case=='synthetic':document['synthetic_test_only']=True
    if case=='duplicate':document['records']*=2
    if case=='naive_capture':
        lineage['captured_at']=document['records'][0]['captured_at']='2026-11-01T09:00:00'
    if case=='late_capture':
        lineage['captured_at']=document['records'][0]['captured_at']=row['kickoff_at']
    artifact=seal(isolated,document,lineage)
    if case=='string':lineage='synthetic-test-only-independent-clock'
    elif case=='none':lineage=None
    elif case=='version':lineage['version']='unsupported'
    elif case=='missing':artifact.unlink()
    elif case=='symlink':
        link=artifact.with_name('link.json');link.symlink_to(artifact);lineage['source_path']=str(link)
    elif case=='hash':lineage['source_sha256']='0'*64
    elif case=='modified':artifact.write_text('{}')
    elif case=='kickoff':row['kickoff_at']='2026-11-02T13:00:00Z'
    elif case=='naive':row['kickoff_at']='2026-11-02T12:00:00'
    elif case=='basis':lineage.pop('timezone_basis')
    elif case=='inferred_basis':lineage['timezone_basis']='inferred timezone'
    elif case=='self':lineage['source_path']=str(isolated/'internal.json')
    elif case=='outside':lineage['source_path']=str(isolated/'elsewhere.json')
    elif case=='mutable':
        other=artifact.with_name('mutable.json');other.write_bytes(artifact.read_bytes());lineage['source_path']=str(other)
    row['kickoff_lineage']=lineage
    path=source(isolated,row)
    # The naive target is rejected by the existing aware-time guard first.
    report=target_discovery.inspect(NOW,[path])
    assert report['targets']==[] and report['internal_target_status']=='BLOCKED_NO_FRESH_INTERNAL_TARGET'
    if case!='naive':assert report['exclusions']=={code:1}
    monkeypatch.setattr(prospective,'inspect',lambda *a:target_discovery.inspect(NOW,[path]))
    def forbidden(*args,**kwargs):pytest.fail('invalid lineage reached odds planner/capture')
    monkeypatch.setattr(prospective,'plan',forbidden)
    monkeypatch.setattr(prospective,'collect_live',forbidden)
    from v3.ops import validation
    monkeypatch.setattr(validation,'receipt_valid',lambda:True)
    assert prospective.prepare()['capture_status']=='BLOCKED_NO_FRESH_INTERNAL_TARGET'
    # Even a manually populated pilot envelope cannot bypass replay of lineage.
    pilot={k:v for k,v in internal().items() if k not in ('synthetic_test_only','kickoff_accredited','kickoff_lineage')}
    pilot.update(markets=['1X2'],priority='P0',external_event_id='manual')
    runtime.write(runtime.ROOT/'pilot-targets.json',[pilot])
    assert prospective.capture(live=True)['capture_status']=='BLOCKED_INTERNAL_TARGET_CHANGED'
    assert prospective.tick()['odds_calls_attempted']==0


def test_ops_authorized_source_missing_evidence():
    from v3.odds.source_matrix import source_matrix,automatable
    assert any(r['provider']=='the_odds_api' and automatable(r) for r in source_matrix())
    from v3.final_validation import odds_release_evidence
    result=odds_release_evidence()
    assert result['odds_source_authorization']=='PASS'
    assert result['odds_evidence_status']=='MISSING'
    assert result['release_status']=='BLOCKED'
    assert result['blockers']==['no_accredited_prospective_odds_observation']
