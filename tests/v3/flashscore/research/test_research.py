"""Synthetic replay tests: no real coverage, model performance or promotion claim."""
from copy import deepcopy
from dataclasses import asdict, replace
import importlib.util
import math
import json
import socket
import ssl  # Load SSLSocket's base class before the suite replaces socket.socket.
import subprocess
import sys

import pytest

from v3.flashscore.contract import dumps
from v3.flashscore.research.dataset import BASE_POLICY, FEATURE_SETS, build_dataset
from v3.flashscore.research.demo import materialized_cohort
from v3.flashscore.research.splits import expanding_folds
from v3.flashscore.research.models import fit, predict, registry
from v3.flashscore.research.calibration import partition, fit_calibrator, transform
from v3.flashscore.research.metrics import binary_metrics, probability_bucket
from v3.flashscore.research.effectiveness import evidence_state, effectiveness
from v3.flashscore.research.error_ledger import error_ledger
from v3.flashscore.research.training import run_experiment, sealed, verify
from v3.flashscore.research.forecast import forecast, rank_forecasts
from v3.flashscore.research.artifacts import atomic_json, write_experiment

SKLEARN = importlib.util.find_spec('sklearn') is not None


@pytest.fixture(scope='module')
def cohort():
    return materialized_cohort(260)


@pytest.fixture(scope='module')
def experiment(cohort):
    return run_experiment(cohort['goals']['dataset']['accepted'], synthetic_demo=True)


def rebuild(inputs, **changes):
    return build_dataset(changes.get('features', inputs['features']),changes.get('targets',inputs['targets']),
        changes.get('fixtures',inputs['fixtures']), feature_set='goals-core-v1')


def test_all_feature_sets(cohort):
    assert set(FEATURE_SETS) == {family+'-core-v1' for family in cohort}
    for inputs in cohort.values():
        ds = inputs['dataset']
        assert len(ds['accepted']) == 260 and ds['rejected'] == []
        assert all(len(r['x']) == 4 and r['synthetic'] and not r['production_evidence'] for r in ds['accepted'])


def test_dataset_determinism(cohort):
    inputs = cohort['goals']
    actual = rebuild(inputs,features=list(reversed(inputs['features'])),targets=list(reversed(inputs['targets'])),
                     fixtures=list(reversed(inputs['fixtures'])))
    assert dumps(actual) == dumps(inputs['dataset'])


@pytest.mark.parametrize('mutation,reason', [
    ('source','TARGET_LEAKAGE'), ('provenance','TARGET_LEAKAGE'),
    ('schema','FEATURE_SCHEMA_MISMATCH'), ('target_policy','TARGET_POLICY_MISMATCH'),
    ('target_schema','TARGET_POLICY_MISMATCH'), ('unsettled','TARGET_UNSETTLED'),
    ('missing','FEATURE_MISSING'), ('identity','FEATURE_SCHEMA_MISMATCH'),
    ('cutoff','FEATURE_TEMPORAL_INELIGIBLE'), ('status','INSUFFICIENT_FEATURES'),
    ('value','FEATURE_SCHEMA_MISMATCH'), ('feature_conflict','DUPLICATE_CONFLICT'),
    ('target_conflict','DUPLICATE_CONFLICT'), ('hash','UNASSESSED'),
    ('source_hash','FEATURE_SCHEMA_MISMATCH'), ('source_date','UNASSESSED'),
    ('target_outcome','UNASSESSED'), ('wrong_match','FEATURE_MISSING'),
])
def test_fail_closed(cohort, mutation, reason):
    inputs = cohort['goals']
    fixture = inputs['fixtures'][0]
    features = deepcopy([f for f in inputs['features'] if f['target_match_id'] == fixture.match_id])
    targets = deepcopy(inputs['targets'][:1])
    f, t = features[0], targets[0]
    if mutation == 'source': f['source_match_ids'].append(fixture.match_id)
    elif mutation == 'provenance': f['provenance'] = deepcopy(t['provenance'])
    elif mutation == 'schema': f['schema_version'] = 'bad'
    elif mutation == 'target_policy': t['settlement_policy_version'] = {}
    elif mutation == 'target_schema': t['schema_version'] = 'bad'
    elif mutation == 'unsettled': t['status'] = 'UNSETTLED'
    elif mutation == 'missing': features = []
    elif mutation == 'identity': f['target_identity'][0] = 'wrong'
    elif mutation == 'cutoff': f['cutoff'] = fixture.match_date+'T12:00:00Z'
    elif mutation == 'status': f['status'] = 'INSUFFICIENT_HISTORY'
    elif mutation == 'value': f['value'] += .1
    elif mutation == 'feature_conflict': features.append(dict(f, value=f['value']+1))
    elif mutation == 'target_conflict': targets.append(dict(t,binary_label=1-t['binary_label']))
    elif mutation == 'hash': f['provenance'][0]['observation_sha256'] = 'bad'
    elif mutation == 'source_hash': f['source_observation_hashes'] = ['bad']
    elif mutation == 'source_date': f['provenance'][0]['request']['fixture']['match_date'] = fixture.match_date
    elif mutation == 'target_outcome': t['outcome'] = 'PUSH'
    elif mutation == 'wrong_match':
        for row in features: row['target_match_id'] = 'other'
    result = rebuild(inputs,features=features,targets=targets,fixtures=[fixture])
    assert not result['accepted']
    assert result['reason_counts'][reason] == 1


def test_missing_target_and_duplicates(cohort):
    inputs = cohort['goals']
    result = rebuild(inputs,targets=[])
    assert result['reason_counts'] == {'TARGET_MISSING':260}
    assert rebuild(inputs,targets=inputs['targets']*2) == inputs['dataset']
    assert rebuild(inputs,features=inputs['features']*2) == inputs['dataset']


def test_split_contract(cohort):
    rows = cohort['goals']['dataset']['accepted']
    folds = expanding_folds(rows)
    assert len(folds) == 3
    assert [f['train_n'] for f in folds] == [100,150,200]
    assert folds == expanding_folds(list(reversed(rows)))
    for fold in folds:
        assert fold['train_end'] < fold['test_start']
        assert not {r['match_id'] for r in fold['train']} & {r['match_id'] for r in fold['test']}
    assert expanding_folds(rows[:110]) == []
    assert expanding_folds([]) == []
    with pytest.raises(ValueError): expanding_folds(rows,min_train=0)
    with pytest.raises(ValueError): expanding_folds(rows+[rows[0]])
    bad = deepcopy(rows)
    bad[0]['label_available_at'] = rows[-1]['label_available_at']
    with pytest.raises(ValueError,match='train_labels'): expanding_folds(bad)
    bad[0]['cutoff'] = bad[0]['target_date']+'T12:00:00Z'
    with pytest.raises(ValueError,match='untrustworthy'): expanding_folds(bad)


def test_whole_date_groups(cohort):
    rows = deepcopy(cohort['goals']['dataset']['accepted'])
    for r in rows[:30]:
        other = dict(r,target_key=r['target_key']+'other',match_id=r['match_id']+'other')
        rows.append(other)
    for fold in expanding_folds(rows):
        assert {r['target_date'] for r in fold['train']}.isdisjoint(r['target_date'] for r in fold['test'])


def test_baseline():
    model = fit('BASE_RATE',[[1],[2],[3]],[0,0,1])
    assert predict(model,[[999],[-999]]) == [1/3,1/3]
    assert predict(fit('BASE_RATE',[[1]],[0]),[[2]]) == [0]
    with pytest.raises(ValueError): fit('BASE_RATE',[[math.nan]],[0])
    with pytest.raises(ValueError): predict(model,[[1,2]])


@pytest.mark.parametrize('name',['LOGISTIC','HGB'])
def test_model_deterministic(name):
    xs = [[i % 17, i % 11] for i in range(120)]
    ys = [int(i % 3 == 0) for i in range(120)]
    a, b = fit(name,xs,ys), fit(name,xs,ys)
    assert a == b
    if not SKLEARN:
        assert a['model_status'] == 'UNSUPPORTED_DEPENDENCY'
    else:
        assert all(0 <= p <= 1 for p in predict(a,xs))
        assert fit(name,xs,[0]*len(xs))['model_status'] == 'INSUFFICIENT_CLASSES'


def test_optional_registry():
    assert registry()['NEGATIVE_BINOMIAL']['model_status'] in ('UNSUPPORTED_DEPENDENCY','UNSUPPORTED_RESPONSE')
    assert fit('NEGATIVE_BINOMIAL',[[1]],[0])['model_status'].startswith('UNSUPPORTED')


def test_calibration(cohort):
    rows = cohort['goals']['dataset']['accepted']
    fit_rows, cal_rows = partition(rows[:220])
    assert len(cal_rows) >= 50
    assert fit_rows[-1]['target_date'] < cal_rows[0]['target_date']
    assert not {r['target_key'] for r in fit_rows} & {r['target_key'] for r in cal_rows}
    assert partition(rows[:100])[1] == []
    assert fit_calibrator([.5]*49,[0]*49)['status'] == 'UNASSESSED'
    ps = [.2,.8]*30; ys=[0,1]*30
    c = fit_calibrator(ps,ys)
    assert c == fit_calibrator(ps,ys)
    assert all(0 <= p <= 1 for p in transform(c,[0,.5,1]))


def test_train_only_and_outer_isolation(cohort, experiment):
    rows = deepcopy(cohort['goals']['dataset']['accepted'])
    for r in rows[200:]:
        r['binary_label'] = 1-r['binary_label']
        r['x'] = [v + 10000 for v in r['x']]
    changed = run_experiment(rows,synthetic_demo=True)
    last = experiment['folds'][-1]['fold_id']
    assert [m for m in experiment['models'] if m['fold_id']==last] == [m for m in changed['models'] if m['fold_id']==last]
    assert any(m['calibrator']['status'] == 'FITTED' for m in experiment['models'] if m['fold_id'] == last)
    for fold in experiment['folds']:
        assert set(fold['fit_ids']).isdisjoint(fold['calibration_ids'])
        assert set(fold['test_ids']).isdisjoint(fold['fit_ids']+fold['calibration_ids'])
    model = next((m['model'] for m in experiment['models'] if m['model']['family']=='LOGISTIC'),None)
    if model:
        train = rows[:100]
        assert model['mean'] == pytest.approx([sum(r['x'][i] for r in train)/100 for i in range(4)])


def test_metrics():
    m = binary_metrics([0,1],[.25,.75])
    assert m['brier'] == .0625
    assert m['logloss'] == pytest.approx(-math.log(.75))
    assert m['ece'] == .25 and m['calibration_error'] == 0
    assert m['accuracy'] == 1
    assert m['mean_probability'] == m['observed_frequency'] == .5
    assert binary_metrics([0,1],[0,1])['brier'] == 0
    assert math.isfinite(binary_metrics([1,0],[0,1])['logloss'])
    assert binary_metrics([0,1],[.5,.5])['accuracy'] == .5
    assert binary_metrics([0,1],[.51,.52])['ece'] == pytest.approx(.015)
    assert probability_bucket(1) == 9 and probability_bucket(0) == 0
    assert probability_bucket(.1) == 1
    assert binary_metrics([1],[1])['bins'][-1]['n'] == 1
    for ps in ([math.nan],[1.01],[-.1]):
        with pytest.raises(ValueError): binary_metrics([0],ps)


@pytest.mark.parametrize('n,state',[(0,'OBSERVE'),(49,'OBSERVE'),(50,'DIAGNOSE'),(99,'DIAGNOSE'),
    (100,'COMPARE_CHALLENGERS'),(199,'COMPARE_CHALLENGERS'),(200,'FORMAL_EVALUATION')])
def test_gates(n,state):
    assert evidence_state(n) == state


def test_error_ledger(experiment):
    predictions = experiment['predictions']
    ledger = error_ledger(predictions)
    assert ledger == error_ledger(list(reversed(predictions))*2)
    assert len({r['entry_id'] for r in ledger}) == len(ledger)
    row = predictions[0]
    for p,y,expected in [(.9,0,['HIGH_CONFIDENCE_MISS','OVERCONFIDENCE']),
                          (.55,1,['LOW_CONFIDENCE_HIT','UNDERCONFIDENCE']),(.7,1,[])]:
        entry = error_ledger([dict(row,probability=p,binary_label=y)])[0]
        assert entry['error_classes'] == expected
        assert entry['brier_component'] == (p-y)**2
    with pytest.raises(ValueError,match='duplicate'):
        error_ledger([row,dict(row,probability=1-row['probability'])])


def test_evidence(experiment):
    assert experiment['status'] == 'DEMO_ONLY'
    assert experiment['REAL_EVALUATION'] == 'BLOCKED'
    assert not experiment['real_performance'] and not experiment['production_evidence']
    assert set(experiment['effectiveness']['selection'].values()) <= {'BASELINE','CHALLENGER','DEMO_ONLY'}
    for segment in experiment['effectiveness']['segments']:
        assert segment['metrics']['n'] > 0 and segment['real_n'] == 0
        assert segment['real_state'] == 'OBSERVE' and not segment['stable_conclusion']


def test_real_training_blocked(cohort):
    rows = cohort['goals']['dataset']['accepted']
    assert run_experiment(rows)['status'] == 'BLOCKED'
    assert run_experiment([dict(rows[0],synthetic=False)],synthetic_demo=True)['status'] == 'BLOCKED'
    assert run_experiment([],synthetic_demo=True)['status'] == 'BLOCKED'
    with pytest.raises(ValueError,match='mixed'):
        run_experiment(rows+[dict(rows[0],line=7.5)],synthetic_demo=True)


def test_forecast(cohort,experiment,monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**k: pytest.fail('network forbidden'))
    inputs = cohort['goals']; fixture = inputs['fixtures'][-1]
    model = experiment['models'][-1]
    assert forecast(fixture,inputs['features'])['status'] == 'NO_MODEL'
    assert forecast(fixture,inputs['features'],model)['status'] == 'INSUFFICIENT_EVIDENCE'
    output = forecast(fixture,inputs['features'],model,allow_synthetic=True)
    assert output['status'] == 'AVAILABLE', output
    assert output['fair_odds'] == 1/output['probability']
    assert output['fair_odds_label'] == 'MODEL_FAIR_ODDS'
    assert output['network_calls'] == 0 and output['odds_status'] == 'UNAVAILABLE'
    assert output['EV'] is output['edge'] is output['PickScore'] is None
    assert output['value_status'] == 'NOT_EVALUATED'
    assert output['brier'] is output['logloss'] is None
    assert forecast(fixture,[],model,allow_synthetic=True)['status'] == 'INSUFFICIENT_FEATURES'
    assert forecast(inputs['fixtures'][0],inputs['features'],model,allow_synthetic=True)['status'] == 'BLOCKED'
    assert forecast(replace(fixture,provider='real'),inputs['features'],model,allow_synthetic=True)['probability'] is None
    tampered = deepcopy(model); tampered['model']['sample_size'] += 1
    assert forecast(fixture,inputs['features'],tampered,allow_synthetic=True)['status'] == 'BLOCKED'
    invalid = sealed(dict({k:v for k,v in model.items() if k != 'artifact_sha256'},evaluation_status='UNASSESSED'))
    assert forecast(fixture,inputs['features'],invalid,allow_synthetic=True)['status'] == 'MODEL_NOT_VALIDATED'
    small = deepcopy(model)
    small.pop('artifact_sha256')
    small['evaluation_window']['test_n'] = 1
    assert forecast(fixture,inputs['features'],sealed(small),allow_synthetic=True)['status'] == 'INSUFFICIENT_EVIDENCE'
    baseline = deepcopy(next(m for m in experiment['models'] if m['model']['family'] == 'BASE_RATE'))
    baseline.pop('artifact_sha256')
    for p in (0,1):
        baseline['model']['probability'] = p
        edge = forecast(fixture,inputs['features'],sealed(baseline),allow_synthetic=True)
        assert edge['probability'] == p
        assert edge['fair_odds'] == (None if p == 0 else 1)
    assert [r['probability'] for r in rank_forecasts([dict(output,probability=None),dict(output,probability=.2),dict(output,probability=.9)])] == [.9,.2,None]


def test_artifacts(experiment,tmp_path):
    verify(experiment)
    path = write_experiment(experiment,tmp_path)
    before = {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert (path/'manifest.json').exists()
    write_experiment(experiment,tmp_path)
    assert before == {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*.json')}
    with pytest.raises(ValueError,match='outside_research'):
        atomic_json('v3_data/ops/forecast/latest.json',{})
    target = tmp_path/'unsafe.json'; target.symlink_to(tmp_path/'destination.json')
    with pytest.raises(ValueError,match='symlink'): atomic_json(target,{})


def test_production_boundary(monkeypatch):
    from pathlib import Path
    latest = Path('v3_data/ops/forecast/latest.json')
    before = latest.read_bytes() if latest.exists() else None
    monkeypatch.setattr(socket,'socket',lambda *a,**k: pytest.fail('network forbidden'))
    import v3.ops.forecast
    assert v3.ops.forecast.CHAMPION == 'J_BT_sin_temporada'
    result = subprocess.run([sys.executable,'-m','v3.ops.cli','--help'],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert (latest.read_bytes() if latest.exists() else None) == before


def test_cli_help():
    result = subprocess.run([sys.executable,'-m','v3.flashscore.research.cli','--help'],capture_output=True,text=True)
    assert result.returncode == 0
    assert 'NOT_PRODUCTION' in result.stdout


def test_selection_controls(experiment):
    # Precomputed noisy probabilities exercise the rule, not model performance.
    template = experiment['predictions'][0]
    rows = []
    for i in range(120):
        y = i % 2
        for model in ('BASE_RATE','LOGISTIC'):
            p = .5 if model == 'BASE_RATE' else (.8 if (y == 1) != (i % 5 == 0) else .2)
            rows.append(dict(template, model=model, match_id=f'selection-{i}',target_key=f's-{i}',
                fold_id=f'fold-{i//60}', binary_label=y, probability=p))
    report = effectiveness(rows)
    assert report['selection']['LOGISTIC'] == 'DEMO_ONLY'
    assert all(group['real_n'] == 0 for group in report['by_model'].values())
    assert effectiveness(rows[:160])['selection']['LOGISTIC'] == 'CHALLENGER'
    incomplete = [r for r in rows if r['model'] != 'LOGISTIC' or r['match_id'] != 'selection-1']
    assert effectiveness(incomplete)['selection']['LOGISTIC'] == 'CHALLENGER'


def test_forecast_cli_json_roundtrip(cohort,experiment,tmp_path,capsys):
    from v3.flashscore.research.cli import main
    inputs = cohort['goals']
    fixture, model = inputs['fixtures'][-1], experiment['models'][-1]
    payloads = dict(fixture=asdict(fixture), features=inputs['features'], model=model)
    for name,payload in payloads.items():
        (tmp_path/(name+'.json')).write_text(dumps(payload))
    output = tmp_path/'research-forecast.json'
    main(['forecast','--fixture',str(tmp_path/'fixture.json'),'--features',str(tmp_path/'features.json'),
          '--model',str(tmp_path/'model.json'),'--allow-synthetic','--output',str(output)])
    result = json.loads(output.read_text())
    assert result == json.loads(capsys.readouterr().out)
    assert result['status'] == 'AVAILABLE'
    assert result['probability'] == forecast(fixture,inputs['features'],model,allow_synthetic=True)['probability']
