"""PAVA; equal p pooled first; step interpolation right-continuous within [0,1].

Endpoint extension uses nearest fitted block, explicitly part of version 1 contract.
"""
from bisect import bisect_right
from v3.models.metrics import probability


def fit(ps, ys):
    if not ps or len(ps)!=len(ys) or any(type(y) is not int or y not in (0,1) for y in ys):raise ValueError("invalid_calibration_data")
    for p in ps:probability(p)
    ties = {}
    for p,y in zip(ps,ys):
        total,n = ties.get(p,(0,0))
        ties[p] = total+y,n+1
    blocks = []
    for p,(total,n) in sorted(ties.items()):
        blocks.append([p,p,total,n])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3] > blocks[-1][2]/blocks[-1][3]:
            right=blocks.pop(); left=blocks.pop()
            blocks.append([left[0],right[1],left[2]+right[2],left[3]+right[3]])
    return dict(blocks=blocks,domain=[0,1],interpolation='step_lower_boundary_nearest_endpoint_v1')


def predict(parameters,p):
    probability(p)
    blocks=parameters['blocks']
    block=blocks[max(0,bisect_right([b[0] for b in blocks],p)-1)]
    return block[2]/block[3]
