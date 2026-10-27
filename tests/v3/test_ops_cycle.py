"""All fixtures here are synthetic_test_only; no runtime real evidence is created."""
import json
from dataclasses import asdict
from pathlib import Path
import pytest
from v3.ops import prospective, target_discovery, oos, promotion, runtime

NOW='2026-11-01T09:00:00Z'


def internal():
    return dict(synthetic_test_only=False, internal_match_id='synthetic-contract-target',
                kickoff_accredited=True,kickoff_lineage='synthetic-test-only-independent-clock',
                kickoff_at='2026-11-02T12:00:00Z',season='explicit-fixture-season',
                sport_key='soccer_epl',competition='Premier League',home='Home',away='Away')


@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(prospective,'now',lambda:NOW)
    return tmp_path


def source(tmp_path,row):
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
    path.write_text(json.dumps([internal(),internal()]))
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
    assert oos.report([row,row])['duplicates_excluded']==2
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
