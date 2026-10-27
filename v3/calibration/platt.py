"""Fixed full-batch gradient descent on logit(p), epsilon only for logit."""
import math
from v3.models.binary import sigmoid
from v3.models.metrics import probability


def logit(p):
    probability(p)
    p = min(1-1e-15, max(1e-15,p))
    return math.log(p/(1-p))


def fit(ps, ys):
    if not ps or len(ps)!=len(ys) or any(type(y) is not int or y not in (0,1) for y in ys):raise ValueError("invalid_calibration_data")
    for p in ps:probability(p)
    a,b = 1.0,0.0
    xs = [logit(p) for p in ps]
    for _ in range(600):
        residuals = [sigmoid(a*x+b)-y for x,y in zip(xs,ys)]
        a -= .01*sum(r*x for r,x in zip(residuals,xs))/len(xs)
        b -= .01*sum(residuals)/len(xs)
    return dict(a=a,b=b,iterations=600,learning_rate=.01,epsilon=1e-15)


def predict(parameters, p):
    return sigmoid(parameters['a']*logit(p)+parameters['b'])
