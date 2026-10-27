import ast
import json
import socket
from pathlib import Path
import pytest
from v3.calibration.contract import time
from v3.calibration.engine import real_state
from v3.final_validation import unchanged,test_mapping_passed as mapping_passed,TEST_REQUIREMENTS,AREAS
from v3.operation.pipeline import current_report
from test_odds_snapshots import snapshot


@pytest.mark.parametrize('value',['2026-01-01','2026-01-01T12:00:00',None,'folder-2026-01-01'])
def test_final_timestamp_contract(value):
    with pytest.raises(ValueError):time(value)


def test_final_real_state_source():
    p=json.loads(Path('docs/v3/models/checkpoint-5.1.json').read_text())
    assert p['dataset']['canonical_rows']==4256 and p['dataset']['kickoff_count']==0
    assert all(m['counts']['eligible_model_rows']==0 and m['counts']['labeled_targets']==500 for m in p['dataset']['markets'].values())
    for n in range(2,7):
        c=json.loads(Path(f'docs/v3/models/checkpoint-5.{n}.json').read_text())
        assert c['model_hash'] is None and c['predictions_hash'] is None and c['metrics'] is None
    r=current_report()
    assert real_state()['calibration'] is None and real_state()['real_metrics'] is None
    assert r['oos_gate']['real_oos_count']==0 and r['release']['release_status']=='BLOCKED'


def test_final_no_optimization_interface():
    from v3.selection import pickscore
    assert pickscore.POLICY['optimized'] is False
    assert pickscore.POLICY['origin']=='conservative_hand_defined'
    assert not any(name in vars(pickscore) for name in ('fit','optimize','tune'))


def test_final_no_execution_or_adaptive_staking():
    prohibited={'place_order','place_bet','execute_bet','auto_wager','kelly','martingale','deposit','withdraw','confirm_bet','bankroll_scale'}
    for area in AREAS:
        for p in (Path('v3')/area).rglob('*.py'):
            tree=ast.parse(p.read_text())
            assert not {n.name.lower() for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}&prohibited
    from v3.operation.handoff import HUMAN_CONFIRMATION_REQUIRED,AUTOMATED_REAL_BETTING
    assert HUMAN_CONFIRMATION_REQUIRED is True and AUTOMATED_REAL_BETTING is False


def test_final_network_guard():
    with pytest.raises(AssertionError,match='network_forbidden'):socket.getaddrinfo('offline-test.invalid',443)
    with pytest.raises(AssertionError,match='network_forbidden'):socket.socket()


def test_final_no_network_imports():
    denied={'requests','httpx','urllib','http','socket','aiohttp','selenium','playwright'}
    for area in AREAS:
        for p in (Path('v3')/area).rglob('*.py'):
            tree=ast.parse(p.read_text())
            imports={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
            imports|={a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
            assert not imports&denied


def test_final_clv_contract():
    from v3.odds.clv import clv
    a=snapshot('T-24h',2.2);b=snapshot('T-1h',2.0,'closing')
    assert clv(a,b)['clv_price']==pytest.approx(.1)
    b['closing_accredited']=False
    assert clv(a,b)['clv_status']=='blocked' and clv(a,b)['clv_price'] is None
    assert clv(a)['clv_status']=='blocked'


def test_final_validator_detects_regressions_and_missing_tests():
    before={'data/a':dict(sha256='a',mtime_ns=1)}
    assert unchanged(before,before,['data'])
    for after in ({},{'data/a':dict(sha256='b',mtime_ns=1)},{**before,'data/b':before['data/a']},{'data/a':dict(sha256='a',mtime_ns=2)}):
        assert not unchanged(before,after,['data'])
    assert not mapping_passed([],('unknown',))
    assert not mapping_passed([('test_x[a]',True),('test_x[b]',False)],('test_x',))
    assert mapping_passed([('test_x[a]',True)],('test_x',))
    assert len(TEST_REQUIREMENTS)>=40


def test_manifest_digest_deterministic():
    from v3.operation.manifest import source_hashes, manifest
    from v3.calibration.contract import digest
    hashes=source_hashes()
    assert digest(hashes)==digest(dict(reversed(list(hashes.items()))))
    assert manifest()['source_digest']==manifest()['source_digest']==digest(hashes)


def test_manifest_digest_source_change(tmp_path):
    from v3.operation.manifest import source_hashes, COMPONENTS
    from v3.calibration.contract import digest
    for area in COMPONENTS:
        folder=tmp_path/area;folder.mkdir();(folder/'module.py').write_text('value = 1\n')
    before=digest(source_hashes(tmp_path))
    (tmp_path/'operation/module.py').write_text('value = 2\n')
    assert digest(source_hashes(tmp_path))!=before


def test_manifest_generation_head():
    import subprocess
    from v3.operation.manifest import manifest
    head=manifest()['generation_head']
    assert len(head)==40 and int(head,16)>=0
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
    assert subprocess.check_output(['git','cat-file','-t',head],text=True).strip()=='commit'


@pytest.mark.parametrize('porcelain,expected',[('','CLEAN'),(' M v3/operation/manifest.py\n','DIRTY_PRECOMMIT'),('?? evidence.json\n','DIRTY_PRECOMMIT')])
def test_manifest_worktree_state(monkeypatch,porcelain,expected):
    import importlib
    module=importlib.import_module('v3.operation.manifest')
    def output(command,**kwargs):
        assert command==['git','status','--porcelain']
        return porcelain
    monkeypatch.setattr(module.subprocess,'check_output',output)
    assert module.generation_worktree_state()==expected


def test_manifest_no_final_commit():
    from v3.operation.manifest import manifest, GENERATION_HEAD_MEANING
    m=manifest()
    assert not {'commit','final_commit','release_commit','working_tree_uncommitted'} & m.keys()
    assert m['generation_head_meaning']==GENERATION_HEAD_MEANING
    assert 'not the final containing commit' in m['generation_head_meaning']


def test_manifest_release_blocked():
    from v3.operation.manifest import manifest
    m=manifest()
    assert m['release_status']=='BLOCKED' and m['oos_count']==0
    assert m['human_confirmation_required'] is True and m['automated_real_betting'] is False
    assert all(m[k]=='BLOCKED' for k in ('model_status','calibration_status','odds_status','promotion_status'))


@pytest.mark.parametrize('key,value,check',[
    ('source_digest','stale','61'),('source_hashes',{},'61'),
    ('generation_head',None,'62'),('generation_head','0'*40,'62'),
    ('generation_head','HEAD','62'),('generation_worktree_state',True,'63'),
    ('commit','claimed-final','64'),('generation_head_meaning','final commit','64'),
    ('release_status','READY','65'),('human_confirmation_required',False,'66')])
def test_traceability_rejects_regressions(key,value,check):
    from v3.operation.manifest import manifest
    from v3.final_validation import traceability_checks
    from v3.calibration.contract import sealed
    m=manifest()
    assert traceability_checks(m)[check]['status']=='PASS'
    m[key]=value
    m=sealed({k:v for k,v in m.items() if k!='hash'})
    assert traceability_checks(m)[check]['status']=='FAIL'
