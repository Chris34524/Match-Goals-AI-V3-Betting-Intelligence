"""Labels never enter preprocessing. Fit accepts only the TRAIN feature matrix."""
import math
from statistics import median
from .contract import digest


def valid(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value))


class Preprocessor:
    def fit(self, rows, names):
        if not rows or tuple(names) != tuple(sorted(set(names))):
            raise ValueError('empty_train_or_unstable_feature_order')
        self.names = tuple(names)
        if any(set(r['features']) != set(names) for r in rows):
            raise ValueError('feature_order_contract')
        params = {}
        for name in names:
            values = [r['features'][name] for r in rows]
            if not all(valid(v) for v in values):
                raise ValueError('invalid_feature_value')
            observed = [v for v in values if v is not None]
            fill = median(observed) if observed else 0.0
            filled = [fill if v is None else v for v in values]
            mean = sum(filled)/len(filled)
            std = math.sqrt(sum((v-mean)**2 for v in filled)/len(filled))
            params[name] = dict(median=fill, mean=mean, std=std or 1.0,
                                all_missing=not observed, zero_variance=std == 0)
        self.manifest = dict(fit_partition='TRAIN', fit_ids=[r['target_id'] for r in rows],
                             feature_names=list(names), parameters=params,
                             missing_policy='median; all_missing=0; zero_variance_scale=1')
        self.manifest['hash'] = digest(self.manifest)
        return self

    def transform(self, rows):
        result = []
        for row in rows:
            if set(row['features']) != set(self.names):
                raise ValueError('unexpected_or_missing_feature')
            values = []
            for name in self.names:
                value = row['features'][name]
                if not valid(value):
                    raise ValueError('invalid_feature_value')
                p = self.manifest['parameters'][name]
                values.append(((p['median'] if value is None else value)-p['mean'])/p['std'])
            result.append(values)
        return result
