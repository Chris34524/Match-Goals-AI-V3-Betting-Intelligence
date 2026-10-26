"""Offline Phase 5 validator: integrity, real evidence and synthetic invariants.

44 checks are implementation/integrity checks; PASS never implies a real model
won or that missing data became evaluable. Runtime/source evidence is mandatory.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from .contract import MARKETS, POLICY, CONFIGS, digest, canonical
from .dataset import feature_specs, audit_dataset, check_features
from .preprocess import Preprocessor
from .split import temporal_split, date_key
from .metrics import binary_metrics, multiclass_metrics, base_rate, probability, vector
from .champion import compare
from .evaluation import divergence
from .runner import synthetic

NAMES = (
 'Phase1–4 artifacts intact','data intact','scraper intact','analysis and backups intact',
 'main.py intact','Champion lineage intact','Phase3 odds intact','Phase4 value intact',
 'only available catalog features','blocked features excluded','no odds/value features','no label features',
 'deterministic temporal split','disjoint partitions','dates never cross partitions',
 'preprocessing fit TRAIN only','no held-out preprocessing statistics','TEST not used for selection',
 'predefined configuration commitment','no random split/shuffle','valid binary probabilities',
 'valid multiclass probabilities','correct Brier','correct LogLoss','correct multiclass metrics',
 'TRAIN-only base-rate','deterministic dataset hash','deterministic split hash','deterministic model hash',
 'deterministic prediction hash','exact-row Champion or explicit BLOCKED','no fabricated Champion probabilities',
 'BTTS decision recorded','O1.5 decision recorded','O2.5 decision recorded','O3.5 divergence gate',
 '1X2 experimental decision','no calibration fitting','no Champion promotion','no ROI/profit selection',
 'no stake/Kelly','no betting execution','no network','Phase5 change scope')


def require(value):
    if not value:
        raise AssertionError('invariant_not_satisfied')


def validate():
    root = Path('.')
    from .integrity import capture, summarize, protected_roots, verify
    baseline = json.loads((root/'docs/v3/models/integrity-before.json').read_text())
    current = summarize(capture(protected_roots()))
    def unchanged(prefixes,mtime=False):
        groups = set()
        for prefix in prefixes:
            parts = Path(prefix).parts
            groups.add('/'.join(parts[:2]) if parts[0] in ('v3','docs') else parts[0])
        verify(baseline,current,groups,mtime)
    checkpoints = [json.loads((root/f'docs/v3/models/checkpoint-5.{i}.json').read_text()) for i in range(1,7)]
    matrices,audit = audit_dataset()
    old_audit = json.loads((root/'v3_data/models/dataset-audit.json').read_text())
    binary = synthetic('BTTS')
    multi = synthetic('1X2')
    runs = (binary,multi)
    files = list((root/'v3/models').glob('*.py'))
    texts = '\n'.join(p.read_text() for p in files if p.name != 'phase5_validation.py')
    trees = [ast.parse(p.read_text()) for p in files if p.name != 'phase5_validation.py']
    imports = {n.module or '' for t in trees for n in ast.walk(t) if isinstance(n,ast.ImportFrom)}
    imports |= {n.name for t in trees for node in ast.walk(t) if isinstance(node,ast.Import) for n in node.names}
    feature_names = [s.name for m in MARKETS for s in feature_specs(m)]
    def rejects(name):
        try:
            check_features({name:1},[name])
        except ValueError:
            return True
        return False
    def altered_test():
        from .evaluation import evaluate
        from .runner import synthetic as make
        original = make('BTTS')
        # Reconstruct synthetic data, changing only sealed partition.
        rows = [dict(target_id=f'synthetic-{i}',kickoff_at=f'2026-01-{i+1:02d}T12:00:00+00:00',
                     cutoff=f'2026-01-{i+1:02d}T12:00:00+00:00',event=dict(home='synthetic-home',away='synthetic-away'),
                     label_version='synthetic-only',features={'synthetic_feature':9999. if i >= 24 else float(i%5)},
                     label=0 if i >= 24 else i%2) for i in range(30)]
        changed = evaluate(rows,['synthetic_feature'],'BTTS')
        require(original['preprocessing'] == changed['preprocessing'])
        require(original['model_hash'] == changed['model_hash'])
        require(original['validation_selection'] == changed['validation_selection'])
    def metric_check(which):
        import math
        if which == 'brier':
            require(abs(binary_metrics([0,1],[.25,.75])['brier']-.0625)<1e-14)
        elif which == 'logloss':
            ps = [0.,1.]
            require(abs(binary_metrics([1,0],ps)['logloss']+math.log(1e-15))<1e-12 and ps == [0.,1.])
        else:
            value = multiclass_metrics([0],[[.5,.25,.25]])
            require(abs(value['brier']-.375)<1e-14 and abs(value['logloss']+math.log(.5))<1e-14)
    def scope():
        require(subprocess.check_output(['git','branch','--show-current'],text=True).strip() == 'feature/phase5-batch-5.1-5.6')
        changed = subprocess.check_output(['git','diff','--name-only','HEAD'],text=True).splitlines()
        untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
        require(all(p == '.gitignore' or p.startswith(('v3/models/','tests/v3/test_models','docs/v3/models/')) or p in ('docs/v3/phase-5-final.md','docs/v3/phase-5-validation-report.json') for p in changed))
        require(all(p.startswith(('v3_data/odds/','v3/models/','tests/v3/test_models','docs/v3/models/')) or p in ('docs/v3/phase-5-final.md','docs/v3/phase-5-validation-report.json') for p in untracked))
    def gate():
        m = {s:dict(brier=.1,logloss=.2) for s in ('TRAIN','VALIDATION','TEST')}
        b = {s:dict(brier=.2,logloss=.4) for s in m}
        require(not divergence(m,b))
        m['TEST']['brier'] = .21
        require(divergence(m,b))
        require(checkpoints[4]['decision'] in ('TEMPORAL_DIVERGENCE','COMPARISON_BLOCKED','DOES_NOT_PASS','PASS_FOR_PHASE6_REVIEW'))
    def no_fabrication():
        require(compare([],[],'BTTS')['probabilities'] is None)
        require(not any(c.get('beats_champion') is True for c in checkpoints))
        for c in checkpoints[1:]:
            require(c['dataset'] == audit['markets'][c['market']])
            if c['experiment_status'] == 'BLOCKED':
                require(c['dataset']['counts']['eligible_model_rows'] == 0)
                require(all(c.get(k) is None for k in ('model_hash','split_hash','predictions_hash','metrics','benchmark','split','selected_config')))
                require(c['oos_windows'] == [])
            else:
                run = json.loads((root/'v3_data/models/runs'/c['run_id']/'manifest.json').read_text())
                require(run['model_hash'] == digest(run['model']))
                require(run['predictions_hash'] == digest(run['predictions']))
                require(run['dataset_hash'] == digest(matrices[c['market']]))
                metric = multiclass_metrics if c['market'] == '1X2' else binary_metrics
                for partition,ps in run['predictions'].items():
                    require(run['metrics'][partition] == metric([p['label'] for p in ps],[p['probability'] for p in ps]))
    def partitions():
        for run in runs:
            ids = [set(run['split']['groups'][s]['ids']) for s in ('TRAIN','VALIDATION','TEST')]
            require(not (ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2]))
    def date_order():
        for run in runs:
            g = run['split']['groups']
            require(g['TRAIN']['end'][:10] < g['VALIDATION']['start'][:10] and g['VALIDATION']['end'][:10] < g['TEST']['start'][:10])
    def base_check():
        require(base_rate([0,1,1]) == 2/3 and base_rate([0,1,1],True) == [1/3,2/3,0])
        for run in runs:
            require(run['base_rate_fit_ids'] == run['split']['groups']['TRAIN']['ids'])
            require(run['base_rate'] == base_rate([r['label'] for r in run['predictions']['TRAIN']],run['market']=='1X2'))
    checks = [
      lambda:unchanged(['v3/data','v3/features']+[str(p) for p in Path('docs/v3').iterdir() if p.name not in ('models','odds','value','phase-5-final.md','phase-5-validation-report.json')]),
      lambda:unchanged(['data'],True),lambda:unchanged(['scraper']),
      lambda:unchanged(['analysis']+[str(p) for p in Path('.').glob('analysis_backup_*')]),
      lambda:unchanged(['main.py']),lambda:unchanged(['analysis','data']),
      lambda:unchanged(['v3/odds','docs/v3/odds']),lambda:unchanged(['v3/value','docs/v3/value']),
      lambda:require(all(s.status == 'available' for m in MARKETS for s in feature_specs(m))),
      lambda:require(all(rejects(n) for n in ('home_xg_mean_l5','home_standing_position','team_shots'))),
      lambda:require(all(rejects(n) for n in ('closing_odds','opening_odds','market_movement','clv','value'))),
      lambda:require(all(rejects(n) for n in ('label','outcome','home_goals','away_goals','post_match_stats'))),
      lambda:require(binary['split'] == synthetic('BTTS')['split']),partitions,date_order,
      lambda:require(all(r['preprocessing']['fit_ids'] == r['split']['groups']['TRAIN']['ids'] for r in runs)),
      altered_test,altered_test,
      lambda:require(all(r['test_commitment']['candidates'] == CONFIGS and r['policy_hash'] == digest(POLICY) for r in runs)),
      lambda:require(not any(i.startswith(('random','numpy','sklearn')) for i in imports)),
      lambda:[probability(p['probability']) for s in binary['predictions'].values() for p in s],
      lambda:[vector(p['probability']) for s in multi['predictions'].values() for p in s],
      lambda:metric_check('brier'),lambda:metric_check('logloss'),lambda:metric_check('multiclass'),base_check,
      lambda:require(audit == old_audit),lambda:require(binary['split']['split_hash'] == synthetic('BTTS')['split']['split_hash']),
      lambda:require(all(r['model_hash'] == synthetic(r['market'])['model_hash'] for r in runs)),
      lambda:require(all(r['predictions_hash'] == digest(r['predictions']) for r in runs)),
      lambda:require(all(c['champion']['champion_comparison_status'] == 'BLOCKED' and c['champion']['reason'] for c in checkpoints)),
      no_fabrication,
      lambda:require(checkpoints[1]['decision'] in ('BEATS_OR_MATCHES_CHAMPION','DOES_NOT_BEAT_CHAMPION','CHAMPION_COMPARISON_BLOCKED')),
      lambda:require(checkpoints[2]['decision'] in ('PASS_FOR_PHASE6_REVIEW','DOES_NOT_PASS','COMPARISON_BLOCKED')),
      lambda:require(checkpoints[3]['decision'] in ('PASS_FOR_PHASE6_REVIEW','DOES_NOT_PASS','COMPARISON_BLOCKED')),gate,
      lambda:require(multi['experimental'] and checkpoints[5]['decision'] in ('PASS_FOR_PHASE6_REVIEW','DOES_NOT_PASS','COMPARISON_BLOCKED')),
      lambda:require(POLICY['calibration'] == 'descriptive_only' and not any('calibrat' in n.name.lower() for t in trees for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.ClassDef)))),
      lambda:require(POLICY['promotion'] is False and all(r['promotion'] is False for r in runs)),
      lambda:require(not any(word in canonical(POLICY).lower() for word in ('roi','profit'))),
      lambda:require(not any('kelly' in i or 'bankroll' in i for i in imports)),
      lambda:require(not any(i.startswith(('scraper','analysis','v3.value','v3.odds')) for i in imports)),
      lambda:require(not any(i.startswith(('socket','requests','urllib','http','subprocess')) for i in imports)),scope]
    require(len(checks) == len(NAMES) == 44)
    results = []
    for i,(name,check) in enumerate(zip(NAMES,checks),1):
        try:
            check()
            results.append(dict(id=f'{i:02d}',name=name,status='PASS'))
        except Exception as e:
            results.append(dict(id=f'{i:02d}',name=name,status='FAIL',reason=str(e)))
    return dict(protocol_version='5.1.0',checks=results,passed=sum(c['status']=='PASS' for c in results),
                failed=sum(c['status']=='FAIL' for c in results),
                status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',
                performance_status='BLOCKED' if all(c['experiment_status']=='BLOCKED' for c in checkpoints) else 'SEE_CHECKPOINTS',
                checkpoints=[{k:c.get(k) for k in ('checkpoint','implementation_status','experiment_status','decision','reason')} for c in checkpoints],
                hashes=dict(source_hash=audit['source_hash'],policy_hash=digest(POLICY),
                            implementation_hash=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),
                            datasets={m:a['dataset_hash'] for m,a in audit['markets'].items()},
                            features={m:a['feature_hash'] for m,a in audit['markets'].items()}),
                limitations=['Implementation checks use explicit synthetic fixtures where real experiments are blocked.',
                             'PASS does not mean challenger beats base-rate or Champion.',
                             'Integrity baseline captured locally before edits; not an independent signed attestation.'])


def main():
    report = validate()
    Path('docs/v3/phase-5-validation-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['status']=='PASS' else 1)


if __name__ == '__main__':
    main()
