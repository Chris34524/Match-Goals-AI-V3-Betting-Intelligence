"""Deterministic binary registry; portable JSON inference, no pickle loading."""
from importlib.util import find_spec
import math

CONFIG = dict(random_state=68, logistic_C=1.0, logistic_max_iter=1000,
              hgb_max_iter=60, hgb_max_leaf_nodes=7, hgb_min_samples_leaf=15,
              hgb_learning_rate=.1, hgb_l2_regularization=1.0, hgb_early_stopping=False)


def registry():
    sklearn = find_spec('sklearn') is not None
    return {name: dict(role='BASELINE' if name == 'BASE_RATE' else 'CHALLENGER',
        model_status='SUPPORTED' if name == 'BASE_RATE' or sklearn and name in ('LOGISTIC', 'HGB')
                     else 'UNSUPPORTED_DEPENDENCY' if name != 'NEGATIVE_BINOMIAL' or find_spec('statsmodels') is None
                     else 'UNSUPPORTED_RESPONSE')
        for name in ('BASE_RATE', 'LOGISTIC', 'HGB', 'NEGATIVE_BINOMIAL')}


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def fit(name, xs, ys):
    if name not in registry() or registry()[name]['model_status'] != 'SUPPORTED':
        return dict(model_status=registry().get(name, {}).get('model_status', 'UNSUPPORTED_MODEL'), family=name)
    if not xs or len(xs) != len(ys) or any(type(y) is not int or y not in (0, 1) for y in ys):
        raise ValueError('invalid_training_data')
    width = len(xs[0])
    if not width or any(len(x) != width or any(type(v) not in (int, float) or not math.isfinite(v) for v in x) for x in xs):
        raise ValueError('invalid_features')
    base = dict(family=name, model_status='FITTED', sample_size=len(ys), width=width, config=CONFIG)
    if name == 'BASE_RATE':
        return dict(base, probability=sum(ys) / len(ys))
    if len(set(ys)) != 2:
        return dict(base, model_status='INSUFFICIENT_CLASSES')
    import sklearn
    import numpy as np
    base['sklearn_version'] = sklearn.__version__
    if name == 'LOGISTIC':
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        scaler = StandardScaler().fit(xs)
        model = LogisticRegression(C=CONFIG['logistic_C'], solver='lbfgs',
            max_iter=CONFIG['logistic_max_iter'], random_state=CONFIG['random_state']).fit(scaler.transform(xs), ys)
        return dict(base, mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist(),
                    weights=model.coef_[0].tolist(), intercept=float(model.intercept_[0]))
    from sklearn.ensemble import HistGradientBoostingClassifier
    model = HistGradientBoostingClassifier(max_iter=CONFIG['hgb_max_iter'],
        max_leaf_nodes=CONFIG['hgb_max_leaf_nodes'], min_samples_leaf=CONFIG['hgb_min_samples_leaf'],
        learning_rate=CONFIG['hgb_learning_rate'], l2_regularization=CONFIG['hgb_l2_regularization'],
        early_stopping=False, random_state=CONFIG['random_state']).fit(np.asarray(xs), ys)
    # Export only numeric split nodes; categorical/missing inputs are unsupported.
    trees = []
    for iteration in model._predictors:
        nodes = []
        for node in iteration[0].nodes:
            if node['is_categorical']:
                raise ValueError('categorical_tree_not_supported')
            nodes.append(dict(leaf=bool(node['is_leaf']), value=float(node['value']),
                feature=int(node['feature_idx']), threshold=float(node['num_threshold']),
                left=int(node['left']), right=int(node['right'])))
        trees.append(nodes)
    artifact = dict(base, intercept=float(model._baseline_prediction[0, 0]), trees=trees)
    if not np.allclose(predict(artifact, xs), model.predict_proba(xs)[:, 1], rtol=0, atol=1e-12):
        raise ValueError('portable_hgb_export_mismatch')
    return artifact


def predict(model, xs):
    if model['model_status'] != 'FITTED':
        raise ValueError('model_not_fitted')
    result = []
    for x in xs:
        if len(x) != model['width'] or any(type(v) not in (int, float) or not math.isfinite(v) for v in x):
            raise ValueError('invalid_features')
        if model['family'] == 'BASE_RATE':
            p = model['probability']
        elif model['family'] == 'LOGISTIC':
            p = sigmoid(model['intercept'] + sum(w * (v - m) / s
                for w, v, m, s in zip(model['weights'], x, model['mean'], model['scale'])))
        elif model['family'] == 'HGB':
            z = model['intercept']
            for nodes in model['trees']:
                index = 0
                while not nodes[index]['leaf']:
                    node = nodes[index]
                    index = node['left'] if x[node['feature']] <= node['threshold'] else node['right']
                z += nodes[index]['value']
            p = sigmoid(z)
        else:
            raise ValueError('unsupported_model')
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('invalid_probability')
        result.append(p)
    return result
