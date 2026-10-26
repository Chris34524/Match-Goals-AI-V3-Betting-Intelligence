"""Train/validation selection followed by exactly one sealed TEST evaluation."""
from .contract import CONFIGS, POLICY, CLASSES, TestSeal, digest
from .split import temporal_split, date_key
from .preprocess import Preprocessor
from .binary import Logistic
from .multiclass import Softmax
from .metrics import binary_metrics, multiclass_metrics, base_rate
from .champion import compare


def divergence(metrics, benchmark):
    """Predeclared: both earlier partitions improve both losses, then either
    TEST loss reverses direction; or TEST loss worsens by >=0.01 absolutely.
    """
    keys = ('brier','logloss')
    earlier = all(metrics[s][k] < benchmark[s][k] for s in ('TRAIN','VALIDATION') for k in keys)
    reversal = any(metrics['TEST'][k] > benchmark['TEST'][k] for k in keys)
    material = any(metrics['TEST'][k]-benchmark['TEST'][k] >= POLICY['divergence_material_delta'] for k in keys)
    return earlier and (reversal or material)


def decide(market, metrics, benchmark, champion, windows):
    if market == 'OVER_3_5' and divergence(metrics,benchmark):
        return 'TEMPORAL_DIVERGENCE'
    if champion['champion_comparison_status'] != 'ACCREDITED':
        return 'CHAMPION_COMPARISON_BLOCKED' if market == 'BTTS' else 'COMPARISON_BLOCKED'
    keys = ('brier','logloss')
    wins = all(metrics['TEST'][k] <= champion['metrics'][k] for k in keys)
    stable = all(all(w['challenger'][k] <= w['benchmark'][k] and
                         w['challenger'][k] <= w.get('champion', w['benchmark'])[k]
                         for k in keys) for w in windows)
    beats_base = all(metrics['TEST'][k] < benchmark['TEST'][k] for k in keys)
    if market == 'BTTS':
        return 'BEATS_OR_MATCHES_CHAMPION' if wins and stable else 'DOES_NOT_BEAT_CHAMPION'
    return 'PASS_FOR_PHASE6_REVIEW' if wins and beats_base and stable else 'DOES_NOT_PASS'


def evaluate(rows, names, market, champion_evidence=()):
    groups,split = temporal_split(rows)
    seal = TestSeal(groups.pop('TEST'))
    prep = Preprocessor().fit(groups['TRAIN'],names)
    metric = multiclass_metrics if market == '1X2' else binary_metrics
    family = Softmax if market == '1X2' else Logistic
    xs = {s:prep.transform(rs) for s,rs in groups.items()}
    ys = {s:[r['label'] for r in rs] for s,rs in groups.items()}
    candidates = []
    models = []
    for i,config in enumerate(CONFIGS):
        model = family().fit(xs['TRAIN'],ys['TRAIN'],config)
        validation = metric(ys['VALIDATION'],model.predict_proba(xs['VALIDATION']))
        candidates.append(dict(index=i,config=dict(config),validation=validation,model_hash=model.model_hash))
        models.append(model)
    chosen = min(range(len(candidates)),key=lambda i:(candidates[i]['validation']['logloss'],candidates[i]['validation']['brier'],i))
    model = models[chosen]
    commitment = dict(feature_names=list(names),preprocessing=prep.manifest,family=model.family,
                      candidates=CONFIGS,selection_metric='validation_logloss',tie_break=POLICY['tie_break'],
                      selected_config=dict(CONFIGS[chosen]),model_hash=model.model_hash)
    seal.freeze(commitment)
    groups['TEST'] = seal.open()
    xs['TEST'] = prep.transform(groups['TEST'])
    ys['TEST'] = [r['label'] for r in groups['TEST']]
    rate = base_rate(ys['TRAIN'],market == '1X2')
    predictions = {s:model.predict_proba(xs[s]) for s in groups}
    metrics = {s:metric(ys[s],predictions[s]) for s in groups}
    benchmark = {s:metric(ys[s],[rate]*len(rs)) for s,rs in groups.items()}
    test = groups['TEST']
    dates = sorted({date_key(r) for r in test})
    n = min(3,len(dates))
    windows = []
    for i in range(n):
        ds = dates[i*len(dates)//n:(i+1)*len(dates)//n]
        indices = [j for j,r in enumerate(test) if date_key(r) in ds]
        labels = [ys['TEST'][j] for j in indices]
        windows.append(dict(start=ds[0],end=ds[-1],ids=[test[j]['target_id'] for j in indices],count=len(indices),
                            challenger=metric(labels,[predictions['TEST'][j] for j in indices]),
                            benchmark=metric(labels,[rate]*len(indices))))
    champion = compare(test,champion_evidence,market)
    if champion['champion_comparison_status'] == 'ACCREDITED':
        champion_ps = champion.pop('probabilities')
        champion['metrics'] = metric(ys['TEST'],champion_ps)
        for window in windows:
            indices = [j for j,r in enumerate(test) if r['target_id'] in window['ids']]
            window['champion'] = metric([ys['TEST'][j] for j in indices], [champion_ps[j] for j in indices])
    output = dict(market=market, experimental=True, promotion=False, policy=POLICY, policy_hash=digest(POLICY),
                  split=split,dataset_hash=digest(rows),feature_names=list(names),feature_hash=digest(names),
                  preprocessing=prep.manifest,model=model.manifest,model_hash=model.model_hash,
                  training_cutoff=split['groups']['TRAIN']['end'],validation_selection=dict(candidates=candidates,selected_index=chosen),
                  test_commitment=commitment,test_open_count=1,metrics=metrics,benchmark=benchmark,base_rate=rate,
                  base_rate_fit_ids=split['groups']['TRAIN']['ids'],champion=champion,oos_windows=windows,
                  temporal_divergence=market == 'OVER_3_5' and divergence(metrics,benchmark),
                  beats_base_rate=all(metrics['TEST'][k] < benchmark['TEST'][k] for k in ('brier','logloss')),
                  beats_champion=None if champion['champion_comparison_status'] != 'ACCREDITED' else all(metrics['TEST'][k] <= champion['metrics'][k] for k in ('brier','logloss')),
                  predictions={s:[dict(target_id=r['target_id'],probability=p,label=r['label']) for r,p in zip(rs,predictions[s])] for s,rs in groups.items()})
    output['decision'] = decide(market,metrics,benchmark,champion,windows)
    output['predictions_hash'] = digest(output['predictions'])
    output['run_id'] = digest(output)
    return output
