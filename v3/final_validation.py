"""Offline final audit: python -m v3.final_validation.

Runs actual tests with socket/DNS guards, maps requirements to named assertions,
compares all protected bytes/counts/mtimes and writes a deterministic status report.
No check substitutes synthetic performance for real evidence.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from v3.calibration.contract import digest

DOCS=Path('docs/v3/final')
RUNTIME=Path('v3_data/operation')
AREAS=('calibration','validation','selection','paper','performance','operation')


def odds_release_evidence():
    from v3.odds.source_matrix import source_matrix, automatable
    authorized=any(automatable(r) for r in source_matrix(provider='the_odds_api'))
    return dict(odds_source_authorization='PASS' if authorized else 'BLOCKED',
                odds_evidence_status='MISSING', release_status='BLOCKED',
                blockers=([] if authorized else ['odds_source_not_authorized'])
                         + ['no_accredited_prospective_odds_observation'])


def inventory(roots):
    result={}
    for name in roots:
        root=Path(name)
        for f in sorted(root.rglob('*')) if root.is_dir() else [root]:
            if f.is_file():
                if f.is_symlink():raise ValueError('protected_symlink')
                result[str(f)]=dict(sha256=hashlib.sha256(f.read_bytes()).hexdigest(),mtime_ns=f.stat().st_mtime_ns)
    return result


def unchanged(before,after,roots):
    def group(files):return {p:v for p,v in files.items() if any(p==r or p.startswith(r+'/') for r in roots)}
    return group(before)==group(after)


# Each mapping points to executed assertions, never an unconditional PASS stub.
TEST_REQUIREMENTS={
 '11':('no fabricated kickoff/cutoff',('test_final_timestamp_contract','test_real_calibration_blocked')),
 '12':('no fabricated real predictions',('test_real_operation_dry_run_no_fabricated_picks',)),
 '13':('no fabricated real metrics',('test_real_calibration_blocked','test_final_real_state_source')),
 '14':('calibration fit/OOS separation',('test_calibration_future_overlap_and_missing_lineage','test_calibration_forbidden_fit')),
 '15':('no fitting on final TEST',('test_calibration_forbidden_fit',)),
 '16':('Platt deterministic',('test_platt_endpoints_deterministic',)),
 '17':('isotonic monotonic',('test_isotonic_ties_monotonic_and_serializable',)),
 '18':('reliability deterministic',('test_reliability_ece_known',)),
 '19':('walk-forward temporal',('test_walkforward_multiple_folds_temporal_deterministic',)),
 '20':('no fold leakage',('test_walkforward_leakage_rejected','test_walkforward_oos_labels_do_not_change_fit','test_same_date_never_crosses_fold_and_oos_disjoint')),
 '21':('economics requires valid odds',('test_economics_rejects_invalid_odds_or_settlement',)),
 '22':('CLV requires accredited closing',('test_final_clv_contract',)),
 '23':('promotion fail-closed',('test_promotion_blocked','test_promotion_rejects_insufficient_or_worse')),
 '25':('PickScore range',('test_score_breakdown_range_deterministic',)),
 '26':('PickScore component breakdown',('test_score_breakdown_range_deterministic',)),
 '27':('blocked components cannot create score',('test_score_required_components_blocked',)),
 '28':('weights not optimized on TEST/ROI',('test_score_breakdown_range_deterministic','test_final_no_optimization_interface')),
 '29':('PASS/NO_BET/BLOCKED semantics',('test_policy_pass_no_bet_blocked',)),
 '30':('deterministic Daily Picks ranking',('test_daily_fields_and_deterministic_ranking',)),
 '31':('blocked dependencies no real picks',('test_daily_blocked_real_no_bet_and_duplicates',)),
 '32':('paper append-only',('test_paper_append_only_fixed_unit_settlement','test_paper_detects_tampering')),
 '33':('paper pre-kickoff/no backdating',('test_paper_no_backdating_or_postkickoff',)),
 '34':('settlement post-event',('test_settlement_post_event_and_label_consistent',)),
 '35':('fixed 1u stake',('test_paper_append_only_fixed_unit_settlement',)),
 '36':('no Kelly',('test_final_no_execution_or_adaptive_staking',)),
 '37':('no martingale',('test_final_no_execution_or_adaptive_staking',)),
 '38':('correct predictive metrics',('test_predictive_economic_known_formulas_and_clv_blocked','test_operation_all_markets_software_only')),
 '39':('correct ROI/Yield formulas',('test_predictive_economic_known_formulas_and_clv_blocked','test_loss_void_and_unsettled')),
 '40':('correct temporal drawdown',('test_drawdown_chronology_initial_loss_and_ties',)),
 '41':('CLV blocked without closing',('test_final_clv_contract','test_predictive_economic_known_formulas_and_clv_blocked')),
 '42':('counter excludes synthetic',('test_synthetic_journal_never_counts_real',)),
 '43':('counter excludes duplicates',('test_oos_duplicates_and_multiple_markets_cannot_inflate',)),
 '44':('threshold >=200 default 200',('test_oos_counter_threshold_contract_only',)),
 '45':('current real gate not falsely MET',('test_synthetic_journal_never_counts_real','test_final_real_state_source')),
 '46':('synthetic E2E passes',('test_synthetic_e2e_all_layers_never_ready',)),
 '47':('synthetic E2E cannot release READY',('test_synthetic_e2e_all_layers_never_ready',)),
 '48':('real release fail-closed',('test_release_all_missing_and_synthetic_fail_closed',)),
 '49':('human confirmation required',('test_human_acknowledgement_immutable_no_execution',)),
 '50':('automated real betting false',('test_human_acknowledgement_immutable_no_execution',)),
 '51':('no sportsbook order implementation',('test_final_no_execution_or_adaptive_staking',)),
 '52':('no network during tests',('test_final_network_guard','test_final_no_network_imports')),
 '53':('deterministic outputs',('test_synthetic_e2e_all_layers_never_ready','test_calibration_deterministic_original_preserved')),
 '54':('runtime isolated in v3_data',('test_production_clock_runtime_and_synthetic_protection',)),
}


def test_mapping_passed(results,names):
    for name in names:
        matches=[passed for test,passed in results if test==name or test.startswith(name+'[')]
        if not matches or not all(matches):return False
    return True


def traceability_checks(release):
    from v3.operation.manifest import source_hashes, GENERATION_HEAD_MEANING, SOURCE_IDENTITY
    from v3.operation.pipeline import current_report
    from v3.calibration.contract import verify
    current=source_hashes()
    head=release.get('generation_head')
    valid_head=isinstance(head,str) and re.fullmatch(r'[0-9a-fA-F]{40}',head) is not None
    if valid_head:
        valid_head=subprocess.run(['git','cat-file','-t',head],capture_output=True,text=True).stdout.strip()=='commit'
    try:
        verify(release)
        sealed=True
    except (ValueError,TypeError):
        sealed=False
    state=current_report()
    checks={
        '61':('manifest source identity matches current sources',release.get('source_hashes')==current and release.get('source_digest')==digest(current)),
        '62':('generation HEAD is an existing Git commit',valid_head),
        '63':('generation worktree state has explicit snapshot vocabulary',release.get('generation_worktree_state') in ('CLEAN','DIRTY_PRECOMMIT')),
        '64':('no self-referential final commit claim',not any(k in release for k in ('commit','final_commit','release_commit','working_tree_uncommitted')) and release.get('generation_head_meaning')==GENERATION_HEAD_MEANING and release.get('source_identity')==SOURCE_IDENTITY),
        '65':('release remains blocked with missing real evidence',release.get('release_status')==state['release']['release_status']=='BLOCKED' and release.get('oos_count')==state['oos_gate']['real_oos_count']==0 and state['oos_gate']['required_oos_count']==200 and state['real_state']['real_status']=='BLOCKED' and 'phase5_no_accredited_temporal_predictions' in state['real_state']['reason_codes'] and all(release.get(k)=='BLOCKED' for k in ('model_status','calibration_status','odds_status','promotion_status')) and 'odds_evidence_missing_or_invalid' in state['release']['reason_codes']),
        '66':('manifest seal and human-only controls',sealed and release.get('human_confirmation_required') is True and release.get('automated_real_betting') is False),
        '68':('Champion identity remains frozen',all(json.loads(Path(f'docs/v3/models/checkpoint-5.{i}.json').read_text())['champion']['operational_champion']=='BT0 / J_BT_sin_temporada' for i in range(1,7))),
    }
    return {i:dict(id=i,name=name,status='PASS' if ok else 'FAIL') for i,(name,ok) in checks.items()}


def main():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    baseline_summary=json.loads((DOCS/'integrity-before.json').read_text())
    baseline_path=Path(baseline_summary['inventory_path'])
    if hashlib.sha256(baseline_path.read_bytes()).hexdigest()!=baseline_summary['inventory_sha256']:
        raise ValueError('baseline_inventory_hash_mismatch')
    baseline=json.loads(baseline_path.read_text())
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    operational_batch=branch=='ops/batch-o02-o06'
    historical_baseline=baseline
    if operational_batch:
        # O-01 is already merged. Preserve the historical inventory and audit
        # this authorized operational batch against its separately sealed start.
        from v3.ops.validation import batch_baseline
        baseline=dict(batch_baseline(),lineage=historical_baseline['lineage'])
        baseline_summary=json.loads(Path('docs/v3/operations/batch-integrity-baseline.json').read_text())
        baseline_summary['groups']={r:digest({p:v for p,v in baseline['files'].items() if p==r or p.startswith(r+'/')}) for r in baseline['roots']}
    env=dict(os.environ,PYTHONPYCACHEPREFIX='/tmp/match-goals-final-bytecode')
    compile_result=subprocess.run([sys.executable,'-m','compileall','-q','v3','tests'],env=env,capture_output=True,text=True)
    pytest_result=subprocess.run([sys.executable,'-m','pytest','-q','tests/v3','--junitxml='+str(RUNTIME/'pytest.xml')],env=env,capture_output=True,text=True)
    print(pytest_result.stdout)
    if pytest_result.stderr:print(pytest_result.stderr)
    xml=ET.parse(RUNTIME/'pytest.xml')
    results=[(c.attrib['name'],not any(c.find(k) is not None for k in ('failure','error','skipped'))) for c in xml.iter('testcase')]
    after=inventory(baseline['roots']);before=baseline['files']
    if operational_batch:
        from v3.ops.validation import source_inventory
        after=source_inventory(after)
    groups=[('01','Phase1 intact',['v3/data','docs/v3/data-contract.md']),
            ('02','Phase2 intact',['v3/features','docs/v3/phase-2']),
            ('03','Phase3 intact',['v3/odds','docs/v3/odds']),
            ('04','Phase4 intact',['v3/value','docs/v3/value']),
            ('05','Phase5 intact',['v3/models','docs/v3/models']),
            ('06','data intact',['data']),('07','scraper intact',['scraper']),
            ('08','analysis/backups intact',['analysis']+[r for r in baseline['roots'] if r.startswith('analysis_backup_')]),
            ('09','main.py intact',['main.py']),('10','Champion lineage intact',baseline['lineage'])]
    checks={i:dict(id=i,name=name,status='PASS' if unchanged(before,after,roots) else 'FAIL') for i,name,roots in groups}
    # Champion absence/presence itself is part of the full protected inventory.
    checks['24']=dict(id='24',name='current Champion unchanged',status='PASS' if unchanged(before,after,['data','analysis','scraper']) and test_mapping_passed(results,('test_promotion_recommendation_never_mutates_champion',)) else 'FAIL')
    for i,(name,names) in TEST_REQUIREMENTS.items():
        checks[i]=dict(id=i,name=name,status='PASS' if test_mapping_passed(results,names) else 'FAIL',evidence_tests=list(names))
    checks['55']=dict(id='55',name='all protected fingerprints/counts/mtimes unchanged',status='PASS' if before==after else 'FAIL')
    checks['56']=dict(id='56',name='compile and full tests pass',status='PASS' if pytest_result.returncode==0 and compile_result.returncode==0 else 'FAIL')
    diff=subprocess.run(['git','diff','--check'],capture_output=True,text=True)
    checks['57']=dict(id='57',name='git diff check clean',status='PASS' if diff.returncode==0 else 'FAIL')
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    checks['58']=dict(id='58',name='exclusive requested branch',status='PASS' if branch in ('feature/final-batch-6.1-9.2','ops/batch-o02-o06') else 'FAIL')
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip()
    checks['59']=dict(id='59',name='nothing staged',status='PASS' if not staged else 'FAIL')
    preexisting=json.loads(Path('docs/v3/value/preexisting-untracked.json').read_text())
    if operational_batch:
        summary=json.loads(Path('docs/v3/operations/batch-integrity-baseline.json').read_text())
        preexisting=summary['preexisting_runtime_sha256']
    preexisting_intact=all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in preexisting.items())
    checks['60']=dict(id='60',name='preexisting untracked odds artifacts intact',status='PASS' if preexisting_intact else 'FAIL')
    new_files=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
    new_files=[p for p in new_files if p not in preexisting]
    tracked=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
    checkpoints=[json.loads(p.read_text()) for p in sorted((DOCS/'checkpoints').glob('*.json'))]
    release=json.loads((DOCS/'release-manifest.json').read_text())
    checks.update(traceability_checks(release))
    checks['69']=dict(id='69',name='unaccredited closing remains blocked',status='PASS' if test_mapping_passed(results,('test_final_clv_contract',)) else 'FAIL')
    checks['67']=dict(id='67',name='traceability regression tests executed',status='PASS' if test_mapping_passed(results,('test_manifest_digest_deterministic','test_manifest_digest_source_change','test_manifest_generation_head','test_manifest_worktree_state','test_manifest_no_final_commit','test_manifest_release_blocked','test_traceability_rejects_regressions')) else 'FAIL')
    operational_integrity = {}
    if operational_batch:
        from v3.ops.integrity import code_integrity, data_drift, champion_integrity
        operational_integrity = dict(**code_integrity(), **data_drift(baseline))
        code_ok = operational_integrity['immutable_code_integrity'] == 'PASS'
        checks['06'] = dict(id='06', name='no branch-versioned operational data changes', status='PASS' if code_ok else 'FAIL')
        checks['24'] = dict(id='24', name='direct Champion contract and checkpoint lineage', status='PASS' if champion_integrity() else 'FAIL')
        checks['55'] = dict(id='55', name='immutable code integrity against origin/main', status='PASS' if code_ok else 'FAIL')
    passed=sum(c['status']=='PASS' for c in checks.values());failed=len(checks)-passed
    report=dict(implementation_status='PASS' if not failed else 'FAIL',passed=passed,failed=failed,checks=[checks[k] for k in sorted(checks)],
                tests_total=len(results),tests_new=sum(1 for c in xml.iter('testcase') if c.attrib.get('classname','').endswith('_final')),
                compile_status='PASS' if compile_result.returncode==0 else 'FAIL',
                checkpoints=checkpoints,real_status='BLOCKED',real_oos_count=0,required_oos_count=200,gate_status='NOT_MET',
                current_champion='BT0 / J_BT_sin_temporada',closing_status='BLOCKED',clv_status='BLOCKED',real_daily_picks_status='BLOCKED',
                odds_source_authorization=odds_release_evidence()['odds_source_authorization'],
                odds_evidence_status=odds_release_evidence()['odds_evidence_status'],
                release_status=release['release_status'],blockers=['phase5_no_accredited_temporal_predictions','champion_cutoff_not_accredited',*odds_release_evidence()['blockers'],'no_accredited_closing','minimum_real_oos_not_met'],
                **operational_integrity, protected_integrity=(operational_integrity['immutable_code_integrity'] if operational_batch else 'PASS' if before==after else 'FAIL'),protected_file_count=len(before),
                hashes=dict(validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            tests_sha256=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('tests/v3').glob('*_final.py'))}),
                            issues_sha256=hashlib.sha256((DOCS/'source-issues.json').read_bytes()).hexdigest(),protected_inventory=baseline_summary['inventory_sha256'],release_manifest=release['hash'],
                            final_source=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for a in AREAS for p in sorted((Path('v3')/a).rglob('*.py'))})),
                files_created=new_files,files_modified=tracked,preexisting_untracked_preserved=sorted(preexisting),
                limitations=['Local fingerprints are not independent signed attestations.','Synthetic tests are software evidence only.','Real source adapters and prospective accreditation remain required.'])
    output_docs=Path('docs/v3/operations') if operational_batch else DOCS
    (output_docs/'integrity-after.json').write_text(json.dumps(dict(protected_integrity=report['protected_integrity'],file_count=len(after),
                **operational_integrity, before_files_hash=digest(before),after_files_hash=digest(after),groups=baseline_summary['groups'] if before==after else None),sort_keys=True,indent=2)+'\n')
    if operational_batch:
        report['baseline_scope']='O02-O06 start; original Phase baselines preserved'
        report['historical_baseline_differences_at_start']=json.loads(Path('docs/v3/operations/batch-integrity-baseline.json').read_text())['historical_final_validator_initial']
    (output_docs/'final-validation-report.json' if operational_batch else Path('docs/v3/final-validation-report.json')).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(f'Final validation: {passed} PASS, {failed} FAIL. Real release: BLOCKED; OOS: 0/200.')
    return int(failed>0)

if __name__=='__main__':raise SystemExit(main())
