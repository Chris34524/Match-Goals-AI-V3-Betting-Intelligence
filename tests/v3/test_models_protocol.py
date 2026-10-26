"""Synthetic protocol tests. Existing V3 autouse guard forbids network."""
from copy import deepcopy
import math
import pytest
from v3.models.contract import TestSeal as Seal, CONFIGS, digest, POLICY
from v3.models.split import temporal_split
from v3.models.preprocess import Preprocessor
from v3.models.binary import Logistic, sigmoid
from v3.models.multiclass import Softmax
from v3.models.metrics import binary_metrics, multiclass_metrics, base_rate, vector
from v3.models.champion import compare
from v3.models.evaluation import evaluate, divergence, decide
from v3.models.dataset import feature_specs, check_features, labels_valid, model_matrix
from v3.data.validation import label_values


def rows(n=30,multiclass=False):
    return [dict(target_id=str(i), kickoff_at=f'2026-01-{i+1:02d}T12:00:00+00:00',
                 cutoff=f'2026-01-{i+1:02d}T12:00:00+00:00',event={'home':'A','away':'B'},
                 label_version='test',features={'x':float(i%5)},label=i%(3 if multiclass else 2)) for i in range(n)]


def test_split_ties_order_and_hash():
    rs = rows()
    twin = dict(rs[17],target_id='twin')
    a,manifest = temporal_split(rs+[twin])
    b,other = temporal_split(list(reversed(rs+[twin])))
    assert a == b and manifest == other
    assert [len(a[k]) for k in ('TRAIN','VALIDATION','TEST')] == [19,6,6]
    assert a['TRAIN'][-1]['kickoff_at'] < a['VALIDATION'][0]['kickoff_at']
    assert a['VALIDATION'][-1]['kickoff_at'] < a['TEST'][0]['kickoff_at']
    assert not ({r['target_id'] for r in a['TEST']} & {r['target_id'] for r in a['TRAIN']})
    with pytest.raises(ValueError,match='duplicate'):
        temporal_split(rs+[rs[0]])
    with pytest.raises(ValueError,match='insufficient'):
        temporal_split(rs[:2])


def test_preprocessor_train_only_missing_and_zero_variance():
    train = [dict(target_id='a',features={'x':1.,'z':None}),dict(target_id='b',features={'x':3.,'z':None})]
    prep = Preprocessor().fit(train,['x','z'])
    before = deepcopy(prep.manifest)
    assert prep.transform([dict(features={'x':None,'z':None})]) == [[0.,0.]]
    assert prep.transform([dict(features={'x':100.,'z':4.})]) == [[98.,4.]]
    assert prep.manifest == before and before['fit_ids'] == ['a','b']
    train[0]['label'] = 999
    assert Preprocessor().fit(train,['x','z']).manifest == before
    with pytest.raises(ValueError):
        prep.transform([dict(features={'x':float('nan'),'z':None})])


def test_test_seal_commitment_and_single_open():
    seal = Seal(rows())
    with pytest.raises(ValueError):
        seal.open()
    with pytest.raises(ValueError):
        seal.freeze({})
    c = {k:None for k in ('feature_names','preprocessing','family','candidates','selection_metric','tie_break','selected_config','model_hash')}
    seal.freeze(c)
    c['family'] = 'changed'
    assert 'changed' not in seal.commitment
    assert len(seal.open()) == 30
    with pytest.raises(ValueError):
        seal.open()
    with pytest.raises(ValueError):
        seal.freeze(c)


def test_metrics_and_log_clipping_preserves_predictions():
    ps = [0.,1.,0.25,0.75]
    original = ps[:]
    m = binary_metrics([1,0,0,1],ps)
    assert m['brier'] == pytest.approx((1+1+.0625+.0625)/4)
    assert m['logloss'] == pytest.approx(-(2*math.log(1e-15)+2*math.log(.75))/4)
    assert ps == original
    assert sum(b['count'] for b in m['reliability']) == 4
    for p in (-1,float('nan'),float('inf'),1.1):
        with pytest.raises(ValueError):
            binary_metrics([1],[p])
    m = multiclass_metrics([0,2],[[.5,.25,.25],[.1,.2,.7]])
    assert m['logloss'] == pytest.approx(-math.log(.35)/2)
    assert m['brier'] == pytest.approx((.375+.14)/2)
    assert tuple(m['per_class']) == ('home','draw','away')
    with pytest.raises(ValueError):
        vector([.5,.5,.5])


@pytest.mark.parametrize('family,multi',[(Logistic,False),(Softmax,True)])
def test_models_deterministic(family,multi):
    xs = [[-1.],[0.],[1.]]
    ys = [0,1,2] if multi else [0,0,1]
    a = family().fit(xs,ys,CONFIGS[0])
    b = family().fit(xs,ys,CONFIGS[0])
    assert a.model_hash == b.model_hash
    assert a.predict_proba(xs) == b.predict_proba(xs)
    if multi:
        for p in a.predict_proba(xs):
            vector(p)
    else:
        assert a.predict_proba(xs)[0] < a.predict_proba(xs)[-1]
    assert sigmoid(-10000) == 0 and sigmoid(10000) == 1


def test_base_rates_train_only():
    assert base_rate([0,0,1]) == 1/3
    assert base_rate([0,0,1],True) == [2/3,1/3,0]


def test_champion_blocked_and_exact_synthetic():
    rs = rows(3)
    assert compare(rs,[],'BTTS')['champion_comparison_status'] == 'BLOCKED'
    evidence = [dict(r,model='J_BT_sin_temporada',market='BTTS',source_hash='synthetic',lineage='synthetic-only',
                     generated_at=r['kickoff_at'].replace('12:00','11:00'),probability=.4) for r in rs]
    assert compare(rs,evidence,'BTTS')['probabilities'] == [.4]*3
    assert compare(rs,evidence[:1],'BTTS')['reason'] == 'row_universe_mismatch'
    evidence[0]['generated_at'] = rs[0]['kickoff_at']
    assert compare(rs,evidence,'BTTS')['champion_comparison_status'] == 'BLOCKED'


def test_catalog_only_available_and_labels_never_features():
    for market in ('BTTS','OVER_1_5','OVER_2_5','OVER_3_5','1X2'):
        specs = feature_specs(market)
        assert specs and all(s.status == 'available' for s in specs)
        assert [s.name for s in specs] == sorted(s.name for s in specs)
    name = feature_specs('BTTS')[0].name
    for forbidden in ('label','home_goals','closing_odds','home_xg_mean_l5','value'):
        with pytest.raises(ValueError):
            check_features({name:1,forbidden:1},[name])
    assert labels_valid(dict(home_goals=1,away_goals=2,**label_values(1,2)))
    assert not labels_valid(dict(home_goals=1,away_goals=2,**dict(label_values(1,2),label_btts=False)))


def canonical_fixture():
    return dict(metadata=dict(match_id='a',date='2026-01-01',kickoff='2026-01-01T12:00:00+00:00',home_team='A',away_team='B'),
                audit=dict(eligible=True,temporal_status='OK',feature_cutoff='2026-01-01T12:00:00+00:00',provenance=[]),
                labels=dict(home_goals=1,away_goals=2,**label_values(1,2)))


def test_dataset_duplicate_missing_and_temporal():
    c = canonical_fixture()
    names = [s.name for s in feature_specs('BTTS')]
    a = dict(features={s.name:(1 if s.dtype == 'int' else 1.) for s in feature_specs('BTTS')},metadata=dict(date='2026-01-01',home='A',away='B'),
             contributing=[dict(match_id='before',date='2025-12-31')],feature_versions=['test'],provenance={})
    rs,audit = model_matrix([c],{'a':a},'BTTS')
    assert len(rs) == 1 and audit['counts']['labeled_targets'] == 1
    with pytest.raises(ValueError,match='duplicate'):
        model_matrix([c,c],{'a':a},'BTTS')
    for date,mid in [('2026-01-01','before'),('2026-01-02','before'),('2025-12-31','a')]:
        a['contributing'] = [dict(match_id=mid,date=date)]
        assert model_matrix([c],{'a':a},'BTTS')[0] == []
    c['metadata']['kickoff'] = None
    assert 'missing_kickoff' in model_matrix([c],{'a':a},'BTTS')[1]['exclusion_reasons']


def test_divergence_and_no_promotion():
    metric = {s:dict(brier=.1,logloss=.2) for s in ('TRAIN','VALIDATION','TEST')}
    base = {s:dict(brier=.2,logloss=.4) for s in metric}
    assert not divergence(metric,base)
    metric['TEST']['brier'] = .21
    assert divergence(metric,base)
    assert decide('OVER_3_5',metric,base,{'champion_comparison_status':'BLOCKED'},[]) == 'TEMPORAL_DIVERGENCE'
    assert POLICY['promotion'] is False


@pytest.mark.parametrize('market',['BTTS','OVER_1_5','OVER_2_5','OVER_3_5','1X2'])
def test_evaluation_determinism_and_test_not_selection(market):
    rs = rows(multiclass=market=='1X2')
    a = evaluate(rs,['x'],market)
    b = evaluate(deepcopy(rs),['x'],market)
    assert a == b
    changed = deepcopy(rs)
    for r in changed[24:]:
        r['features']['x'] = 9999
        r['label'] = 0
    c = evaluate(changed,['x'],market)
    assert a['model_hash'] == c['model_hash']
    assert a['preprocessing'] == c['preprocessing']
    assert a['validation_selection'] == c['validation_selection']
    assert a['base_rate'] == c['base_rate']
    assert a['test_open_count'] == 1
    assert sum(w['count'] for w in a['oos_windows']) == 6
    assert a['promotion'] is False
    assert a['champion']['champion_comparison_status'] == 'BLOCKED'
    assert a['predictions_hash'] == digest(a['predictions'])
