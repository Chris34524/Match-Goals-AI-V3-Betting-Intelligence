"""Single L2 softmax, fixed home/draw/away class order; no independent binaries."""
import math
from .contract import CLASSES, digest


def softmax(z):
    m = max(z)
    values = [math.exp(v-m) for v in z]
    return [v/sum(values) for v in values]


class Softmax:
    family = 'multiclass_l2_softmax'

    def fit(self, xs, ys, config):
        if not xs or len(xs) != len(ys) or any(y not in (0,1,2) for y in ys):
            raise ValueError('invalid_training_data')
        self.weights = [[0.0]*(len(xs[0])+1) for _ in CLASSES]
        if any(len(x)+1 != len(self.weights[0]) for x in xs):
            raise ValueError('feature_dimension')
        for iteration in range(config['iterations']):
            grads = [[0.0]*len(self.weights[0]) for _ in CLASSES]
            for x,y in zip(xs,ys):
                ps = self.predict_proba([x])[0]
                for k in range(3):
                    for j,v in enumerate([1.0]+list(x)):
                        grads[k][j] += (ps[k]-(y==k))*v/len(xs)
            largest = 0
            for k in range(3):
                for j,g in enumerate(grads[k]):
                    step = config['learning_rate']*(g+(config['l2']*self.weights[k][j] if j else 0))
                    self.weights[k][j] -= step
                    largest = max(largest,abs(step))
            if largest <= config['tolerance']:
                break
        self.manifest = dict(family=self.family, class_order=CLASSES, config=dict(config), weights=self.weights, iterations_run=iteration+1)
        self.model_hash = digest(self.manifest)
        return self

    def predict_proba(self, xs):
        if any(len(x)+1 != len(self.weights[0]) for x in xs):
            raise ValueError('feature_dimension')
        return [softmax([w[0]+sum(a*b for a,b in zip(w[1:],x)) for w in self.weights]) for x in xs]
