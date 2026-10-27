"""Conservative fixed defaults; no fitting interface, no TEST/ROI optimization.

Quality is evidence quality, not an assertion that a high probability is accurate.
Probability component is selected-outcome p; sample saturates at 100 observations;
calibration is 1-ECE/.1; value saturates at EV=.2; stability is 1-max(loss delta)/.05.
"""
import math
from v3.calibration.contract import digest, sealed

WEIGHTS={'probability':.15,'sample':.25,'calibration':.25,'value':.15,'stability':.20}
POLICY=dict(version='pickscore-v1',weights=WEIGHTS,optimized=False,origin='conservative_hand_defined',
            sample_saturation=100,ev_saturation=.2,ece_limit=.1,stability_limit=.05)


def score(inputs, *, synthetic_test_only=False):
    out=dict(status='BLOCKED',score=None,components=[],reason_codes=[],policy=POLICY,
             policy_hash=digest(POLICY),synthetic_test_only=synthetic_test_only)
    raw={}
    for name in WEIGHTS:
        c=inputs.get(name,{})
        value=c.get('value')
        if (c.get('status')!='ELIGIBLE' or c.get('accredited') is not True or not c.get('lineage')
            or c.get('synthetic_test_only') is not synthetic_test_only
            or type(value) not in (int,float) or not math.isfinite(value)):
            out['reason_codes'].append(name+'_missing_or_unaccredited');continue
        if ((name in ('probability','calibration') and not 0<=value<=1)
            or (name=='sample' and (value<0 or value!=int(value)))):
            out['reason_codes'].append(name+'_invalid');continue
        raw[name]=value
    if out['reason_codes']:return sealed(out)
    normalized=dict(probability=100*raw['probability'],sample=100*min(1,raw['sample']/100),
                    calibration=100*max(0,1-raw['calibration']/.1),value=100*max(0,min(1,raw['value']/.2)),
                    stability=100*max(0,min(1,1-max(0,raw['stability'])/.05)))
    for name,weight in WEIGHTS.items():
        out['components'].append(dict(name=name,raw_input=raw[name],normalized_component=normalized[name],
                                     weight=weight,contribution=weight*normalized[name],reason='fixed_v1_normalization',
                                     evidence=inputs[name]))
    out.update(status='ELIGIBLE',score=min(100,max(0,sum(c['contribution'] for c in out['components']))))
    return sealed(out)
