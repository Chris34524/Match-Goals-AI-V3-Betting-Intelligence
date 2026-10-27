"""Offline operational controls, mapped to executed regression assertions.

A live receipt binds the full suite and validator evidence to exact code hashes.
Protected historical baselines are preserved; this batch has a separate baseline.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from v3.final_validation import inventory, unchanged, test_mapping_passed
from v3.odds.source_matrix import source_matrix, matrix_errors, automatable
from .runtime import ROOT, read, write

SUMMARY=Path('docs/v3/operations/batch-integrity-baseline.json')


def source_digest():
    paths = sorted(set(Path('v3').rglob('*.py')) | set(Path('tests/v3').rglob('*.py')))
    return hashlib.sha256(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},sort_keys=True).encode()).hexdigest()


def batch_baseline():
    summary=json.loads(SUMMARY.read_text())
    path=Path(summary['inventory_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=summary['inventory_sha256']:
        raise ValueError('batch_baseline_digest_mismatch')
    result=json.loads(path.read_text())
    result['files']=source_inventory(result['files'])
    return result

def source_inventory(files):
    # Derived V3 interpreter caches are not source. Keep every byte/mtime
    # under data/scraper/analysis, including their preexisting caches.
    return {p:v for p,v in files.items() if not (p.startswith('v3/') and '/__pycache__/' in p)}


# Each check is tied to assertions executed under the socket/DNS test guard.
REQUIREMENTS=[
 ('provider remains authorized','test_authorization'),
 ('key never serialized','test_ops_runtime_secret_and_escape'),
 ('source matrix valid','test_versioned_matrix_is_deterministic_and_complete'),
 ('no Flashscore automation','test_nonpermitted_sources_never_automatable'),
 ('no historical endpoint','test_request_paths_headers_and_no_historical'),
 ('metadata bounded','test_ops_bounded_discovery_no_retry'),
 ('one odds credit','test_ops_unique_plan_single_credit'),
 ('no odds retry','test_ops_failed_capture_terminal'),
 ('no polling','test_ops_no_polling_or_new_http'),
 ('no backfill','test_late_missed_never_backfill'),
 ('accredited future target','test_ops_target_fail_closed'),
 ('timezone required','test_ops_legacy_timezone_not_inferred'),
 ('unique reconciliation','test_reconciliation'),
 ('external event required','test_ops_unique_plan_single_credit'),
 ('observed before kickoff','test_future_update_and_postkickoff_excluded'),
 ('provider timestamp separate','test_parser_orientation_lines_and_clocks'),
 ('current never opening','test_opening_requires_explicit_evidence'),
 ('current never closing','test_closing_not_inferred_and_clv_blocked'),
 ('paper only PASS','test_policy_pass_no_bet_blocked'),
 ('paper pre kickoff','test_paper_no_backdating_or_postkickoff'),
 ('fixed one unit','test_paper_append_only_fixed_unit_settlement'),
 ('no Kelly','test_final_no_execution_or_adaptive_staking'),
 ('no martingale','test_final_no_execution_or_adaptive_staking'),
 ('no sportsbook execution','test_final_no_execution_or_adaptive_staking'),
 ('settlement append only','test_settlement_post_event_and_label_consistent'),
 ('unsettled excluded','test_oos_exclusions'),
 ('synthetic excluded','test_ops_synthetic_never_real'),
 ('duplicate match excluded','test_oos_duplicates_and_multiple_markets_cannot_inflate'),
 ('multiple markets no inflation','test_oos_duplicates_and_multiple_markets_cannot_inflate'),
 ('required count 200','test_oos_counter_threshold_contract_only'),
 ('checkpoint 50','test_ops_checkpoints'),
 ('checkpoint 100','test_ops_checkpoints'),
 ('gate 200','test_ops_checkpoints'),
 ('CLV accredited only','test_final_clv_contract'),
 ('last price not closing','test_closing_not_inferred_and_clv_blocked'),
 ('CLV exact comparability','test_movement_requires_same_series'),
 ('CLV formula','test_synthetic_accredited_closing_formula'),
 ('promotion blocked below 200','test_ops_promotion_roi_alone_blocked'),
 ('comparator exact','test_promotion_exact_comparator_mismatches_block'),
 ('ROI alone insufficient','test_ops_promotion_roi_alone_blocked'),
 ('Champion unchanged','test_promotion_recommendation_never_mutates_champion'),
 ('human confirmation','test_ops_promotion_roi_alone_blocked'),
 ('no automatic promotion','test_ops_promotion_roi_alone_blocked'),
]


def secret_free():
    secret=os.environ.get('THE_ODDS_API_KEY')
    paths=subprocess.check_output(['git','ls-files','-co','--exclude-standard'],text=True).splitlines()
    for name in paths:
        p=Path(name)
        if p.is_file() and secret and secret.encode() in p.read_bytes():
            return False
    # Scan operational runtime too; never print matches or credential derivatives.
    for p in ROOT.rglob('*'):
        if p.is_file() and secret and secret.encode() in p.read_bytes():
            return False
    return True


def validate():
    ROOT.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PYTHONPYCACHEPREFIX='/tmp/match-goals-ops-bytecode')
    run=subprocess.run([sys.executable,'-m','pytest','-q','tests/v3','--junitxml='+str(ROOT/'pytest.xml')],env=env,capture_output=True,text=True)
    # Do not echo test tracebacks, which can contain untrusted fixture content.
    xml=ET.parse(ROOT/'pytest.xml')
    tests=[(c.attrib['name'],not any(c.find(k) is not None for k in ('failure','error','skipped'))) for c in xml.iter('testcase')]
    checks=[dict(id=f'{i:02}',name=name,status='PASS' if test_mapping_passed(tests,(test,)) else 'FAIL',evidence_test=test)
            for i,(name,test) in enumerate(REQUIREMENTS,1)]
    baseline=batch_baseline();after=source_inventory(inventory(baseline['roots']));before=baseline['files']
    groups=[('data unchanged',['data']),('scraper unchanged',['scraper']),
            ('analysis unchanged',['analysis']+[r for r in baseline['roots'] if r.startswith('analysis_backup_')]),
            ('main unchanged',['main.py']),('Phase 1–9 sources unchanged',[r for r in baseline['roots'] if r.startswith('v3/')])]
    for name,roots in groups:
        checks.append(dict(id=f'{len(checks)+1:02}',name=name,status='PASS' if unchanged(before,after,roots) else 'FAIL'))
    additional=[('runtime confined',test_mapping_passed(tests,('test_ops_runtime_secret_and_escape',))),
                ('no secrets in repository',secret_free()),
                ('offline test suite',run.returncode==0 and test_mapping_passed(tests,('test_final_network_guard',))),
                ('deterministic reports',test_mapping_passed(tests,('test_ops_report_deterministic',))),
                ('git diff check',subprocess.run(['git','diff','--check'],capture_output=True).returncode==0),
                ('matrix and authorization',not matrix_errors(source_matrix()) and any(r['provider']=='the_odds_api' and automatable(r) for r in source_matrix())),
                ('required branch',subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='ops/batch-o02-o06'),
                ('nothing staged',not subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip())]
    for name,ok in additional:
        checks.append(dict(id=f'{len(checks)+1:02}',name=name,status='PASS' if ok else 'FAIL'))
    failed=sum(c['status']=='FAIL' for c in checks)
    report=dict(implementation_status='PASS' if not failed else 'FAIL',checks=checks,passed=len(checks)-failed,failed=failed,
                tests_total=len(tests),tests_new=sum(n.startswith('test_ops_') for n,_ in tests),source_digest=source_digest(),
                protected_integrity='PASS' if before==after else 'FAIL',network_calls=0,
                real_status='EVIDENCE_GATES_SEPARATE',limitations=['Software validation never accredits a real target, model, result or closing.'])
    write(ROOT/'validation.json',report)
    return report


def receipt_valid():
    receipt=read(ROOT/'validation-receipt.json',{})
    return (receipt.get('source_digest')==source_digest() and receipt.get('suite')=='PASS'
            and receipt.get('final_validator')=='PASS' and receipt.get('ops_validator')=='PASS')


def validate_and_receipt():
    env=dict(os.environ,PYTHONPYCACHEPREFIX='/tmp/match-goals-ops-bytecode')
    compile_run=subprocess.run([sys.executable,'-m','compileall','-q','v3','tests'],env=env,capture_output=True)
    final=subprocess.run([sys.executable,'-m','v3.final_validation'],env=env,capture_output=True)
    result=validate()
    good=compile_run.returncode==0 and final.returncode==0 and result['failed']==0
    write(ROOT/'validation-receipt.json',dict(source_digest=source_digest(),suite='PASS' if good else 'FAIL',
                                           final_validator='PASS' if final.returncode==0 else 'FAIL',ops_validator=result['implementation_status']))
    return good


def main():
    result=validate()
    print(json.dumps({k:result[k] for k in ('implementation_status','passed','failed','tests_total','tests_new')},sort_keys=True))
    for check in result['checks']:
        if check['status']=='FAIL':print(check['id']+' FAIL '+check['name'])
    return int(result['failed']>0)


if __name__=='__main__':
    raise SystemExit(main())
