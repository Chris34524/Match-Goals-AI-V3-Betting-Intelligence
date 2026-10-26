"""L2 logistic, unpenalized intercept, mean loss + l2/2 * squared weights."""
import math
from .contract import digest


def sigmoid(z):
    return 1/(1+math.exp(-z)) if z >= 0 else math.exp(z)/(1+math.exp(z))


class Logistic:
    family = 'binary_l2_logistic'

    def fit(self, xs, ys, config):
        if not xs or len(xs) != len(ys) or any(y not in (0,1) for y in ys):
            raise ValueError('invalid_training_data')
        self.config = dict(config)
        self.weights = [0.0]*(len(xs[0])+1)
        if any(len(x)+1 != len(self.weights) for x in xs):
            raise ValueError('feature_dimension')
        for iteration in range(config['iterations']):
            grad = [0.0]*len(self.weights)
            for x,y in zip(xs,ys):
                residual = sigmoid(self.weights[0]+sum(w*v for w,v in zip(self.weights[1:],x)))-y
                grad[0] += residual/len(xs)
                for j,v in enumerate(x,1):
                    grad[j] += residual*v/len(xs)
            steps = [config['learning_rate']*(g+(config['l2']*self.weights[j] if j else 0)) for j,g in enumerate(grad)]
            self.weights = [w-s for w,s in zip(self.weights,steps)]
            if max(map(abs,steps)) <= config['tolerance']:
                break
        self.manifest = dict(family=self.family, config=self.config, weights=self.weights, iterations_run=iteration+1)
        self.model_hash = digest(self.manifest)
        return self

    def predict_proba(self, xs):
        if any(len(x)+1 != len(self.weights) for x in xs):
            raise ValueError('feature_dimension')
        return [sigmoid(self.weights[0]+sum(w*v for w,v in zip(self.weights[1:],x))) for x in xs]
