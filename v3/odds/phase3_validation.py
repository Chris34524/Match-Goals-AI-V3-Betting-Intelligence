"""Offline Phase 3 invariants and read-only protected-tree fingerprints.

Run from the repository: python -m v3.odds.phase3_validation --write-report.
Content reads do not set mtimes. No acquisition endpoint is contacted.
"""
import argparse
from contextlib import ExitStack
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
from unittest.mock import patch

from .contract import canonical_json, MARKETS
from .provider import Config, load_targets, utc
from .reconciliation import Reconciliation
from .storage import REPO, digest, encoded

DOCS = REPO/'docs/v3'
BASELINE = DOCS/'odds/integrity-before.json'


def compact_digest(value):
    return digest(json.dumps(value,sort_keys=True,separators=(',',':')).encode())


def fingerprints(baseline):
    files={}
    roots=[r for r in baseline['roots'] if not r.startswith('lineage:')]
    # New backup roots also invalidate integrity, instead of being ignored.
    roots=sorted(set(roots)|{p.name for p in REPO.glob('analysis_backup_*')})
    for root in roots:
        p=REPO/root
        paths=sorted(p.rglob('*')) if p.is_dir() else [p]
        for f in paths:
            if f.is_file():
                before=f.stat()
                h=hashlib.sha256()
                with f.open('rb') as stream:
                    while chunk:=stream.read(1024*1024): h.update(chunk)
                after=f.stat()
                if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
                    raise ValueError('protected_file_changed_during_read')
                files[str(f.relative_to(REPO))]={'sha256':h.hexdigest(),'mtime_ns':before.st_mtime_ns}
    values={}
    for root in roots+['lineage:BT0','lineage:J_BT_sin_temporada']:
        if root.startswith('lineage:'):
            selected={p:v for p,v in files.items() if root.split(':')[1].lower() in p.lower()}
        else:
            selected={p:v for p,v in files.items() if p==root or p.startswith(root+'/')}
        values[root]=dict(files=len(selected),content_sha256=compact_digest({p:v['sha256'] for p,v in selected.items()}),
                          mtime_sha256=compact_digest({p:v['mtime_ns'] for p,v in selected.items()}))
    return values


def changed_paths():
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=REPO,text=True).splitlines()
    return sorted(set(git('diff','--name-only','HEAD')+git('ls-files','--others','--exclude-standard')))


def validation(*, test_count=None):
    from .source_matrix import source_matrix,automatable,matrix_errors
    from .the_odds_api import live_status,TheOddsAPI,ProviderError
    from .collector import parse,collect_fixture,collect_live,plan
    from .quota import Budget,estimate
    from .scheduler import schedule,execute
    from .snapshots import load_snapshots,make_snapshot,store_snapshot,accredited
    from .movement import movement
    from .clv import clv
    baseline=json.loads(BASELINE.read_text())
    after=fingerprints(baseline)
    integrity={r:dict(before=baseline['roots'].get(r),after=after.get(r),
                      unchanged=baseline['roots'].get(r)==after.get(r)) for r in sorted(set(after)|set(baseline['roots']))}
    checks={}
    checks['01_contract_3_1_intact']=all(integrity[r]['unchanged'] for r in
        ('v3/odds/contract.py','v3/odds/source_matrix.py','v3/odds/audit.py'))
    rows=source_matrix()
    checks['02_source_matrix_fail_closed']=not matrix_errors(rows) and not any(map(automatable,rows))
    checks['03_blocked_sources_remain_blocked']=integrity['docs/v3/odds/source-matrix.json']['unchanged']
    paths=changed_paths()
    secret=os.environ.get('THE_ODDS_API_KEY')
    secret_free=True
    for name in paths:
        f=REPO/name
        if not f.is_file(): continue
        content=f.read_bytes()
        if secret and secret.encode() in content: secret_free=False
        # Detect credential assignments, while permitting environment lookups and
        # variable-name documentation. Fixture sentinels are deliberately synthetic.
        if re.search(rb'(?i)["\']?(?:THE_ODDS_API_KEY|apiKey)["\']?\s*[:=]\s*["\'][a-z0-9]{16,}["\']',content):
            secret_free=False
    checks['05_no_secrets_in_changes']=secret_free
    adapter_source=(REPO/'v3/odds/the_odds_api.py').read_text()
    checks['06_no_historical_endpoints']=('/historical/' not in adapter_source
        and "path = f'/sports/{sport}'" in adapter_source)
    c=Config(('soccer_synthetic',),bookmakers=('synthetic_book',))
    fixture_dir=REPO/'tests/v3/fixtures/odds'
    payload=json.loads((fixture_dir/'response.json').read_text())
    targets=load_targets(json.loads((fixture_dir/'targets.json').read_text()))
    rec=Reconciliation({'soccer_synthetic':'Synthetic League'},'synthetic-1')
    now='2026-11-01T17:00:00Z'
    calls=[]
    def blocked(*a,**kw):
        calls.append(True)
        raise AssertionError('network_forbidden')
    with ExitStack() as stack:
        for owner,name in ((socket,'create_connection'),(socket,'getaddrinfo'),(socket.socket,'connect'),(socket.socket,'connect_ex')):
            stack.enter_context(patch.object(owner,name,blocked))
        with tempfile.TemporaryDirectory(prefix='phase3-validation-') as tmp:
            with patch.dict(os.environ):
                os.environ.pop('THE_ODDS_API_KEY',None)
                try: collect_live(targets,c,rec,live=True,root=tmp,adapter=TheOddsAPI(c,blocked))
                except ProviderError as exc: missing=str(exc)=='blocked_missing_credentials'
                else: missing=False
                os.environ['THE_ODDS_API_KEY']='synthetic-validation-credential'
                try: collect_live(targets,c,rec,live=True,root=tmp,adapter=TheOddsAPI(c,blocked))
                except ProviderError as exc: unauthorized=str(exc)=='blocked_source_authorization'
                else: unauthorized=False
            checks['04_live_requires_credentials_and_authorization']=missing and unauthorized and not calls
            run=collect_fixture(payload,targets,c,rec,observed_at=now,root=tmp)
            manifest=json.loads((run/'manifest.json').read_text())
            before=(run/'canonical.jsonl').read_bytes()
            repeat=collect_fixture(payload,targets,c,rec,observed_at=now,root=tmp)
            checks['13_deterministic_outputs']=run==repeat and before==(repeat/'canonical.jsonl').read_bytes()
            execute(targets,c,rec,root=tmp,fixture_payload=payload,fixture_now=now)
            snapshots=load_snapshots(tmp)
            post=parse(payload,targets,c,rec,targets[0].kickoff_at)[0]
            checks['07_snapshots_pre_match_without_leakage']=bool(snapshots) and not post and all(
                utc(s['record']['observed_at'])<utc(s['record']['kickoff_at']) for s in snapshots)
            checks['08_closing_not_inferred']=all(not s['closing_accredited'] for s in snapshots)
            checks['09_clv_blocked_without_accredited_closing']=all(clv(s)['clv_status']=='blocked' for s in snapshots)
            # Create a valid earlier observation with the same market and price;
            # change just the book to demonstrate failed comparability.
            from copy import deepcopy
            late=snapshots[0];early=deepcopy(late)
            early['slot']='T-6h';early['scheduled_offset']=21600
            earlier=utc(early['record']['kickoff_at'])-timedelta(hours=6)
            early['scheduled_at']=earlier.isoformat()
            early['record']['observed_at']=earlier.isoformat()
            early['record']['source_published_at']=earlier.isoformat()
            early['provider_last_update']=earlier.isoformat()
            good=movement(early,late)
            early['record']['bookmaker']='different_book'
            checks['10_movement_only_comparable']=good is not None and movement(early,late) is None
            b=Budget()
            checks['11_quota_guard_active']=(plan(c,targets)['estimated_cost']==3
                and b.check(3,499)=='monthly_hard_limit' and b.check(3,449)=='monthly_soft_limit'
                and b.check(3,0,2)=='provider_remaining')
            checks['12_no_network_in_validation_and_tests']=not calls and all(s in
                (REPO/'tests/v3/conftest.py').read_text() for s in ('autouse=True','getaddrinfo','connect_ex','create_connection'))
            example=dict(run_id=run.name,source_sha256=manifest['source_sha256'],
                         canonical_sha256=manifest['canonical_sha256'],record_count=manifest['record_count'])
    for n,root in ((14,'data'),(15,'scraper'),(16,'analysis'),(17,'lineage:BT0'),(18,'lineage:J_BT_sin_temporada')):
        checks[f'{n:02}_{root.replace(":","_")}_intact']=integrity[root]['unchanged']
    checks['19_all_protected_roots_and_mtimes_intact']=all(v['unchanged'] for v in integrity.values())
    checks['20_changes_isolated_to_v3']=all(p.startswith(('v3/','tests/v3/','docs/v3/','v3_data/odds/')) for p in paths)
    return dict(schema_version='3.3.0',roadmap={'3.1':'validated_intact','3.2':'implemented_offline_validated_live_blocked',
                '3.3':'implemented_offline_validated_clv_ready'},
                result='passed' if all(checks.values()) else 'failed',checks=checks,
                sources=['https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/29',
                         'https://github.com/Chris34524/Match-Goals-AI-V3-Betting-Intelligence/issues/30',
                         'https://the-odds-api.com/liveapi/guides/v4/', 'docs/v3/odds/source-matrix.json'],
                supported_markets=list(MARKETS),live_enabled_markets=[],
                blocked_markets=['ASIAN_HANDICAP','CORNERS','CARDS','props','unsupported totals lines'],
                provider='the_odds_api',provider_status='adapter_implemented_not_authorized',live_status=live_status(True),
                quota=dict(monthly_hard_limit=500,monthly_soft_limit=450,max_credits_per_run=30,
                    cost='unique provider markets × region equivalents × calls; explicit bookmakers ceil(N/10)',
                    ledger='locked append-only monthly conservative reservations before network; retain unknown costs'),
                snapshots=dict(slots=['T-24h','T-6h','T-1h'],window_seconds=60,decision_enabled=False,
                    missed='no retrospective fill',store='immutable exact semantic dedupe including provenance'),
                movement='same match/provider/book/market/selection/line; T24→T6/T6→T1/T24→T1',
                closing_status='unavailable_without_explicit_accreditation',clv_status='blocked_without_accredited_closing',
                clv_convention='odds_taken / odds_close - 1',
                tests=dict(total_passed=test_count,network='socket and DNS autouse guard for entire tests/v3 suite',
                    commands=['python -m compileall -q v3 tests','python -m pytest -q tests/v3','python -m v3.odds.phase3_validation']),
                integrity=integrity,example_fixture_manifest=example,files_touched=paths,
                gaps=['No real provider acquisition/coverage validated','No project source grant or credentials',
                      'No accredited current-provider opening/closing; real CLV blocked',
                      'Separate roots/clients sharing a credential need an external budget coordinator'],
                next_dependency='Phase 4 must consume only authorized, temporally eligible observations; accredited closing is required for CLV')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-report',action='store_true')
    p.add_argument('--test-count',type=int)
    args=p.parse_args(argv)
    value=validation(test_count=args.test_count)
    if args.write_report:
        (DOCS/'phase-3-validation-report.json').write_text(canonical_json(value))
        (DOCS/'odds/integrity-after.json').write_text(canonical_json({r:v['after'] for r,v in value['integrity'].items()}))
    print(canonical_json({'result':value['result'],'checks':value['checks'],'live_status':value['live_status'],
                          'example_fixture_manifest':value['example_fixture_manifest']}),end='')
    return 0 if value['result']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
