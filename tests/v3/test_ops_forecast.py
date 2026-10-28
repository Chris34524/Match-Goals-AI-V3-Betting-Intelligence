"""Synthetic contract fixtures only; never runtime accreditation."""
import hashlib
import json
import pytest
from v3.ops import forecast as f
from v3.ops import oos
from test_ops_cycle import internal, evidence, seal, NOW


def sealed(tmp_path, document):
    raw=json.dumps(document).encode();sha=hashlib.sha256(raw).hexdigest()
    path=tmp_path/'v3_data/ops/evidence'/(sha+'.json')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return dict(source_path=str(path),source_sha256=sha,source_record_id='p1')


@pytest.fixture
def row(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    r=internal();doc,lineage=evidence(tmp_path,r);seal(tmp_path,doc,lineage)
    r.update(kickoff_lineage=lineage,model=f.CHAMPION,model_lineage={'version':'BT0'},
             generated_at=NOW,feature_cutoff_at=NOW,probabilities={'BTTS':.6})
    record={k:r[k] for k in (*f.IDENTITY,'model','model_lineage','generated_at','feature_cutoff_at','kickoff_at','probabilities')}
    record['identity']={k:r[k] for k in f.IDENTITY}
    record.update(source_record_id='p1',synthetic_test_only=False)
    r['prediction_lineage']=sealed(tmp_path,dict(synthetic_test_only=False,records=[record]))
    r['source_digest']=r['prediction_lineage']['source_sha256']
    return r


def settlement(tmp_path,r):
    s={k:r[k] for k in (*f.IDENTITY,'kickoff_at')}
    s.update(home_goals=2,away_goals=1)
    rec=dict(identity={k:r[k] for k in f.IDENTITY},source_record_id='p1',synthetic_test_only=False,
             home_goals=2,away_goals=1,settled_at='2026-11-03T12:00:00Z')
    s['settlement_lineage']=sealed(tmp_path,dict(synthetic_test_only=False,records=[rec]))
    return s


@pytest.mark.parametrize('failure',['missing_key','quota_exhausted','provider_unavailable','odds_none'])
def test_forecast_independent(row,monkeypatch,failure):
    monkeypatch.delenv('THE_ODDS_API_KEY',raising=False)
    row.update(odds=None,odds_status=failure)
    r=f.candidates(row,NOW)[0]
    assert r['forecast_status']=='FORECAST_PASS'
    assert r['odds_status']=='UNAVAILABLE' and r['value_status']=='NOT_EVALUATED'
    assert all(r[k] is None for k in ('edge','ev','market_odds','market_probability','clv','PickScore'))
    assert r['fair_odds']==1/.6


def test_forecast_accredited_oos(row,tmp_path):
    rows=f.candidates(row,NOW);s=settlement(tmp_path,row)
    stats=f.oos_report(rows,[s],'2026-11-04T00:00:00Z')
    assert stats['forecast_oos_matches']==stats['forecast_oos_predictions']==1
    assert stats['by_market']['BTTS']['brier']==pytest.approx(.16)
    assert f.oos_report(rows*2,[s],'2026-11-04T00:00:00Z')['forecast_oos_count']==1
    assert oos.report(rows)['real_oos_count']==0
    assert not list(tmp_path.glob('v3_data/paper/**/*'))


@pytest.mark.parametrize('change',[{'generated_at':'2026-11-02T12:00:00Z'},
    {'generated_at':'2026-11-03T12:00:00Z'},{'synthetic_test_only':True},
    {'prediction_lineage':{}},{'model_lineage':None},{'kickoff_lineage':{}},
    {'feature_cutoff_at':'2026-11-03T12:00:00Z'}])
def test_forecast_rejects_unaccredited(row,change,tmp_path):
    row.update(change)
    assert not f.accredited(row,'2026-11-04T00:00:00Z')
    r=f.candidates(row,'2026-11-04T00:00:00Z')
    assert r and r[0]['accreditation_status']=='OPERATIONAL_LEGACY_FORECAST'
    assert f.oos_report(r,[settlement(tmp_path,row)],'2026-11-04T00:00:00Z')['forecast_oos_count']==0


def test_forecast_champion_reuses_poisson():
    from analysis.poisson import analizar
    r=f.candidates(dict(internal_match_id='x',lambda_home=1.2,lambda_away=.9),NOW)
    assert len(r)==10 and all(x['model']=='J_BT_sin_temporada' for x in r)
    assert next(x['probability'] for x in r if x['market']=='BTTS')==analizar(1.2,.9)['btts']['si']
    assert [x['probability'] for x in r]==sorted([x['probability'] for x in r],reverse=True)


def test_forecast_evidence_tamper(row):
    from pathlib import Path
    Path(row['prediction_lineage']['source_path']).write_text('{}')
    assert not f.accredited(row,NOW)


def test_forecast_settlement_requires_evidence(row,tmp_path):
    s=settlement(tmp_path,row);s['home_goals']=0
    assert f.oos_report(f.candidates(row,NOW),[s],'2026-11-04T00:00:00Z')['forecast_oos_count']==0


@pytest.mark.parametrize('failure',['missing_key','quota_exhausted','provider_unavailable'])
def test_forecast_command_never_calls_provider(tmp_path,monkeypatch,failure):
    from v3.ops import cli, prospective
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('THE_ODDS_API_KEY',raising=False)
    def forbidden(*args,**kwargs):
        pytest.fail('forecast reached provider or betting capture')
    monkeypatch.setattr(prospective,'collect_live',forbidden)
    monkeypatch.setattr(prospective,'plan',forbidden)
    monkeypatch.setattr(f,'sources',lambda:[dict(internal_match_id='offline',lambda_home=1.2,lambda_away=.9,odds_status=failure)])
    assert cli.main(['forecast'])==0
    result=json.loads((tmp_path/f.ROOT/'latest.json').read_text())
    assert result['forecast_candidates']==10 and not result['value_evaluated']
    assert result['betting_oos_matches']==0
    assert (tmp_path/f.ROOT/'journal.jsonl').read_text()==''
    assert not (tmp_path/'v3_data/paper/ledger.jsonl').exists()


def test_forecast_sources_tolerate_missing_lambda_base(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    p=tmp_path/'data/matches/null/confidence_v2.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(dict(modelo=f.CHAMPION,detalle_v1={'lambda_base':None})))
    assert f.sources()==[]


def test_forecast_journal_append_only_and_deduplicated(row,tmp_path,monkeypatch):
    from datetime import datetime
    class Clock:
        @staticmethod
        def now(tz):
            return datetime.fromisoformat(NOW.replace('Z','+00:00'))
    monkeypatch.setattr(f,'datetime',Clock)
    monkeypatch.setattr(f,'sources',lambda:[row])
    first=f.generate()
    path=tmp_path/f.ROOT/'journal.jsonl'
    original=path.read_bytes()
    f.generate()
    assert original==path.read_bytes()
    assert len(original.splitlines())==1
    assert first['accredited_forecasts']==1
    assert first['forecast_oos_count']==0
    assert first['betting_oos_matches']==0


def target_fixture(tmp_path, count):
    for i in range(count):
        p=tmp_path/f'data/matches/m{i}/lambda_comparison.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'metodos':{f.CHAMPION:{'local':1.2,'visitante':.9}}}))


@pytest.mark.parametrize('active',[2,3])
def test_forecast_explicit_allowlist(tmp_path,monkeypatch,active):
    monkeypatch.chdir(tmp_path)
    target_fixture(tmp_path,4315 if active==2 else 5)
    source=tmp_path/'targets.json'
    source.write_text(json.dumps([{'id':f'm{i}'} for i in range(active)]))
    result=f.generate(source)
    assert result['forecast_matches']==active
    assert result['forecast_candidates']==active*10
    assert {g['internal_match_id'] for g in result['matches']}=={f'm{i}' for i in range(active)}
    assert result['forecast_oos_count']==result['betting_oos_matches']==0
    assert all(not c['oos_eligible'] for g in result['matches'] for c in g['ranked_forecast_candidates'])


def test_forecast_safe_default_and_missing_source(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    target_fixture(tmp_path,2)
    result=f.generate()
    assert result['forecast_generation_status']=='NO_ACTIVE_FORECAST_TARGETS'
    assert result['forecast_matches']==result['forecast_candidates']==0
    with pytest.raises(ValueError,match='forecast_source_missing'):
        f.generate('missing.json')


def test_forecast_identity_and_duplicates(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    target_fixture(tmp_path,2)
    p=tmp_path/'targets.json'
    p.write_text(json.dumps([{'local':'m0'}, {'id':'m0'}, {'match_id':'m0'},
                             {'id':'m1','match_id':'different'}, {'id':'../m1'}]))
    result=f.generate(p)
    assert result['forecast_matches']==1 and result['forecast_candidates']==10
    assert result['matches'][0]['internal_match_id']=='m0'


@pytest.mark.parametrize('quota',['UNAVAILABLE','EXHAUSTED'])
def test_forecast_allowlist_without_odds(tmp_path,monkeypatch,quota):
    monkeypatch.chdir(tmp_path)
    target_fixture(tmp_path,1)
    p=tmp_path/'targets.json';p.write_text('[{"id":"m0"}]')
    monkeypatch.setenv('THE_ODDS_API_KEY','synthetic_test_key')
    first=f.generate(p)
    monkeypatch.delenv('THE_ODDS_API_KEY')
    (tmp_path/'v3_data/ops/quota.json').write_text(json.dumps({'status':quota}))
    assert first==f.generate(p)


def test_ops_code_integrity_gates(monkeypatch):
    from v3.ops import integrity as i
    def run(branch=(),work=()):
        def git(args,**kwargs):
            if 'origin/main...HEAD' in args:return '\n'.join(branch)
            if 'HEAD' in args:return '\n'.join(work)
            return ''
        monkeypatch.setattr(i.subprocess,'check_output',git)
        return i.code_integrity()['immutable_code_integrity']
    assert run(work=['data/live.json'])=='PASS'
    for path in ['data/artificial.json','analysis/model.py','scraper/a.py','main.py','v3/models/a.py']:
        assert run(branch=[path])=='FAIL'
    for path in ['analysis/a.py','scraper/a.py','main.py','v3/models/a.py']:
        assert run(work=[path])=='FAIL'


def test_ops_data_drift_informational(tmp_path,monkeypatch):
    from v3.ops import integrity as i
    monkeypatch.chdir(tmp_path)
    (tmp_path/'data').mkdir();p=tmp_path/'data/live.json';p.write_text('new')
    baseline={'files':{'data/live.json':{'sha256':'old','mtime_ns':0}}}
    report=i.data_drift(baseline)
    assert report['operational_data_drift_detected']
    assert report['operational_data_changed_files']==['data/live.json']
    monkeypatch.setattr(i.subprocess,'check_output',lambda *a,**k:'')
    assert i.code_integrity()['immutable_code_integrity']=='PASS'


def test_ops_champion_direct():
    from v3.ops.integrity import champion_integrity
    assert champion_integrity()
