import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import pytest
from test_odds_collector import inputs, NOW, FIXTURES
from v3.odds.provider import utc
from v3.odds.collector import parse
from v3.odds.scheduler import schedule,execute,ScheduleConfig,load_history
from v3.odds.snapshots import make_snapshot,store_snapshot,load_snapshots,accredited,validate_snapshot
from v3.odds.movement import movement,movements,dispersion
from v3.odds.clv import clv
from v3.odds.quota import Budget
from v3.odds.snapshot_report import report,store_report


def snapshot(slot='T-1h',price=2.2,kind='current'):
    payload,targets,c,rec=inputs()
    offset={'T-24h':86400,'T-6h':21600,'T-1h':3600}[slot]
    now=(utc(targets[0].kickoff_at)-timedelta(seconds=offset)).isoformat()
    payload[0]['bookmakers'][0]['last_update']=now
    for m in payload[0]['bookmakers'][0]['markets']: m['last_update']=now
    records,_,_=parse(payload,targets,c,rec,now)
    r=next(r for r in records if r['market']=='1X2' and r['selection']=='home')
    r['decimal_odds']=price
    r['snapshot_type']=kind
    if kind in ('opening','closing'):
        r['temporal_semantics']=dict(definition='Synthetic provider-declared '+kind+' boundary',evidence='Synthetic accreditation fixture; not a production grant')
    row=next(row for row in schedule(targets,c,now=now) if row['slot']==slot)
    return make_snapshot(r,row,run_id='a'*64,source_digest='b'*64)


def test_slots_utc_determinism():
    _,targets,c,_=inputs()
    target=replace(targets[0],kickoff_at='2026-11-01T20:00:00+02:00')
    rows=schedule([target],c,now='2026-10-30T18:00:00Z')
    assert rows==schedule([target],c,now='2026-10-30T18:00:00Z')
    assert {r['slot']:r['scheduled_at'] for r in rows}=={
        'T-24h':'2026-10-31T18:00:00+00:00','T-6h':'2026-11-01T12:00:00+00:00','T-1h':'2026-11-01T17:00:00+00:00'}
    assert all(r['status']=='planned' and not r['due'] for r in rows)


@pytest.mark.parametrize('now',['2026-11-01T18:00:00Z','2026-11-01T18:01:00Z'])
def test_kickoff_not_pre_match(now):
    _,t,c,_=inputs()
    assert all(r['status']=='missed' and not r['due'] for r in schedule(t,c,now=now))
    s=snapshot();s['record']['observed_at']=now
    with pytest.raises(ValueError): validate_snapshot(s)


def test_late_missed_never_backfill(tmp_path):
    p,t,c,r=inputs()
    rows=schedule(t,c,now='2026-11-01T17:01:01Z')
    assert all(row['status']=='missed' for row in rows)
    execute(t,c,r,root=tmp_path,fixture_payload=p,fixture_now='2026-11-01T17:01:01Z')
    assert load_snapshots(tmp_path)==[]
    history=load_history(tmp_path)
    earlier=schedule(t,c,now=NOW,history=history)
    assert all(r['status']=='missed' and not r['due'] for r in earlier)


def test_priority_and_aggregate_budget():
    _,t,c,_=inputs()
    targets=[replace(t[0],internal_match_id='p3',priority='P3'),replace(t[0],internal_match_id='p0',priority='P0')]
    b=Budget(monthly_hard_limit=10,monthly_soft_limit=9,max_credits_per_run=3)
    rows=schedule(targets,c,now='2026-10-30T18:00:00Z',budget=b)
    chosen=[r for r in rows if r['status']=='planned']
    assert [(r['internal_match_id'],r['slot']) for r in chosen]==[('p0','T-1h')]
    assert sum(r['estimated_cost'] for r in chosen)<=b.max_credits_per_run
    assert all(r['status']=='skipped_budget' for r in schedule(targets,c,now='2026-10-30T18:00:00Z',credits_used_local=499))


def test_decision_disabled_by_default():
    _,t,c,_=inputs()
    assert len(schedule(t,c,now=NOW))==3
    policy=ScheduleConfig(decision_offset_seconds=900)
    rows=schedule(t,c,now='2026-11-01T17:45:00Z',policy=policy)
    assert next(r for r in rows if r['slot']=='decision')['due']
    for seconds in [0,60,3600]:
        with pytest.raises(ValueError): ScheduleConfig(decision_offset_seconds=seconds)


def test_store_dedupe_and_conflict(tmp_path):
    s=snapshot()
    path=store_snapshot(s,root=tmp_path)
    before=(path/'snapshot.json').stat().st_mtime_ns
    assert store_snapshot(deepcopy(s),root=tmp_path)==path
    assert (path/'snapshot.json').stat().st_mtime_ns==before
    different=deepcopy(s);different['record']['decimal_odds']=2.4
    with pytest.raises(ValueError,match='conflict'):store_snapshot(different,root=tmp_path)
    assert load_snapshots(tmp_path)==[s]
    different['record']['observed_at']='2026-11-01T17:00:01Z'
    store_snapshot(different,root=tmp_path)
    assert len(load_snapshots(tmp_path))==2


@pytest.mark.parametrize('field,value',[('internal_match_id','other'),('provider','other'),('bookmaker','other'),('market','BTTS'),('selection','away'),('line',3.5),('external_match_id','other'),('kickoff_at','2026-11-02T18:00:00Z')])
def test_movement_requires_same_series(field,value):
    a=snapshot('T-24h',2.2);b=snapshot('T-1h',2.0)
    b['record'][field]=value
    assert movement(a,b) is None


def test_movement_formula_intervals_and_direction():
    a=snapshot('T-24h',2.2);b=snapshot('T-6h',2.1);c=snapshot('T-1h',2.0)
    values=movements([c,a,b])
    assert len(values)==3 and values==movements([b,c,a])
    m=movement(a,c)
    assert m['decimal_odds_delta']==pytest.approx(-.2)
    assert m['implied_probability_before']==pytest.approx(1/2.2)
    assert m['implied_probability_after']==.5
    assert m['implied_probability_delta']==pytest.approx(.5-1/2.2)
    assert m['relative_price_change']==pytest.approx(2/2.2-1)
    assert m['interval_seconds']==23*3600 and m['direction']=='shortened'
    assert movement(a,snapshot('T-1h',2.4))['direction']=='lengthened'
    assert movement(a,snapshot('T-1h',2.2))['direction']=='unchanged'
    assert movement(c,a) is None


def test_exact_valid_line_change_is_separate_series():
    a=snapshot('T-24h');b=snapshot('T-1h')
    for s,line,market in [(a,2.5,'OVER_2_5'),(b,3.5,'OVER_3_5')]:
        s['record'].update(market=market,line=line,selection='over')
        validate_snapshot(s)
    assert movement(a,b) is None


def test_opening_requires_explicit_evidence():
    current=snapshot('T-1h')
    assert movement(snapshot('T-24h'),current,open_to_current=True) is None
    assert movement(snapshot('T-24h',kind='unknown'),current,open_to_current=True) is None
    opening=snapshot('T-24h',kind='opening')
    assert accredited(opening['record'],'opening')
    assert movement(opening,current,open_to_current=True) is not None
    opening['record']['temporal_semantics']['evidence']=None
    assert movement(opening,current,open_to_current=True) is None


def test_closing_not_inferred_and_clv_blocked():
    a=snapshot('T-6h');last=snapshot('T-1h')
    assert not last['closing_accredited']
    assert clv(a,last)==dict(clv_status='blocked',reason='no_accredited_closing',clv_price=None)
    assert clv(a)['clv_status']=='blocked'
    assert clv(None)['clv_status']=='not_applicable'
    last['closing_accredited']=True
    with pytest.raises(ValueError):validate_snapshot(last)
    assert clv(a,last)['clv_status']=='blocked'


def test_synthetic_accredited_closing_formula():
    a=snapshot('T-6h',2.2);close=snapshot('T-1h',2.0,kind='closing')
    assert close['closing_accredited']
    assert clv(a,close)['clv_price']==pytest.approx(.1)
    assert clv(a,close)['clv_status']=='computable'
    close['record']['bookmaker']='other'
    assert clv(a,close)['clv_status']=='blocked'
    close=snapshot('T-24h',2.,kind='closing')
    assert clv(a,close)['clv_status']=='blocked'


def test_dispersion_known_population_same_capture():
    a=snapshot(price=2.0);b=deepcopy(a)
    a['record']['bookmaker']='a';b['record'].update(bookmaker='b',decimal_odds=2.4)
    d=dispersion([b,a],expected_books=('a','b'))
    assert d['n_books']==2 and d['mean_odds']==2.2 and d['median_odds']==2.2
    assert d['range']==pytest.approx(.4) and d['stdev']==pytest.approx(.28284271247)
    assert d['consensus_implied_probability']==pytest.approx((1/2+1/2.4)/2)
    assert dispersion([a],expected_books=('a','b')) is None
    assert dispersion([a,b],expected_books=()) is None
    b['record']['observed_at']='2026-11-01T17:00:01Z'
    assert dispersion([a,b],expected_books=('a','b')) is None


def test_execution_audit_and_deterministic_reports(tmp_path):
    p,t,c,r=inputs()
    run=execute(t,c,r,root=tmp_path,fixture_payload=p,fixture_now=NOW)
    m=json.loads((run/'manifest.json').read_text())
    executed=[row for row in m['targets'] if row['status']=='executed']
    assert len(executed)==1 and executed[0]['slot']=='T-1h'
    assert len(executed[0]['snapshot_digests'])==11
    assert len(load_snapshots(tmp_path))==11
    assert executed[0]['credits_actual']==0 and not m['closing_accredited'] and m['clv_status']=='blocked'
    value=report(tmp_path,expected_books=c.bookmakers)
    assert value==report(tmp_path,expected_books=c.bookmakers)
    assert not value['dispersion'] and value['clv_status']=='blocked'
    path=store_report(tmp_path)
    assert store_report(tmp_path)==path
    execute(t,c,r,root=tmp_path,fixture_payload=p,fixture_now=NOW)
    assert len(load_snapshots(tmp_path))==11


def test_missing_prices_failed_and_no_network_live(tmp_path,monkeypatch):
    p,t,c,r=inputs();p[0]['bookmakers']=[]
    path=execute(t,c,r,root=tmp_path,fixture_payload=p,fixture_now=NOW)
    assert next(row for row in json.loads((path/'manifest.json').read_text())['targets'] if row['slot']=='T-1h')['status']=='failed'
    monkeypatch.delenv('THE_ODDS_API_KEY',raising=False)
    with pytest.raises(RuntimeError,match='missing_credentials'):execute(t,c,r,root=tmp_path,live=True)


def test_snapshot_cli(tmp_path,capsys):
    from v3.odds.snapshots_cli import main
    base=['--config',str(FIXTURES/'config.json'),'--targets',str(FIXTURES/'targets.json'),'--output-dir',str(tmp_path)]
    assert main(['plan',*base,'--now',NOW])==0
    assert len(json.loads(capsys.readouterr().out))==3
    assert main(['fixture-tick',*base,'--fixture',str(FIXTURES/'response.json'),'--now',NOW])==0
    capsys.readouterr()
    assert main(['report',*base])==0
    capsys.readouterr()
    assert main(['live-tick',*base])==2


def test_provider_timestamp_alias_cannot_be_changed():
    s=snapshot();s['provider_last_update']='2026-11-01T16:59:00Z'
    with pytest.raises(ValueError,match='provider_timestamp_mismatch'):validate_snapshot(s)


def test_no_leakage_after_observation_or_without_evidence():
    s=snapshot(kind='closing');s['record']['source_published_at']='2026-11-01T17:01:00Z'
    s['provider_last_update']=s['record']['source_published_at']
    with pytest.raises(ValueError):validate_snapshot(s)
    s=snapshot(kind='opening');s['record']['temporal_semantics']['definition']=None
    assert not accredited(s['record'],'opening')


def test_failed_live_tick_reports_unknown_credit_cost(tmp_path,monkeypatch):
    import v3.odds.scheduler as scheduler
    _,t,c,r=inputs()
    monkeypatch.setattr('v3.odds.the_odds_api.authorize',lambda *a,**k:None)
    monkeypatch.setattr(scheduler,'utc_now',lambda:NOW)
    def failed(*a,**k):raise RuntimeError('fixed_failure')
    monkeypatch.setattr('v3.odds.collector.collect_live',failed)
    out=execute(t,c,r,root=tmp_path,live=True)
    value=json.loads((out/'manifest.json').read_text())
    assert value['credits_actual'] is None
    row=next(row for row in value['targets'] if row['slot']=='T-1h')
    assert row['status']=='failed' and row['credits_actual'] is None


def test_unknown_external_id_can_reconcile_offline_without_global_polling(tmp_path):
    p,t,c,r=inputs()
    targets=[replace(t[0],external_event_id=None)]
    rows=schedule(targets,c,now=NOW)
    assert next(row for row in rows if row['slot']=='T-1h')['due']
    execute(targets,c,r,root=tmp_path,fixture_payload=p,fixture_now=NOW)
    snapshots=load_snapshots(tmp_path)
    assert len(snapshots)==11
    assert all(s['record']['external_match_id']==p[0]['id'] for s in snapshots)
