"""Real release requires every component's accredited real evidence, no synthetic shortcut."""
from v3.calibration.contract import sealed,verify

REQUIRED={'model':'ELIGIBLE','calibration':'ELIGIBLE','walkforward':'PASS','promotion':'PROMOTE_ELIGIBLE',
          'odds':'ELIGIBLE','value':'ELIGIBLE','pickscore':'ELIGIBLE','paper':'RUNNING',
          'performance':'COMPUTABLE','integrity':'PASS'}


def evaluate(components,oos_gate,*,synthetic_test_only=False):
    reasons=[]
    for name,status in REQUIRED.items():
        c=components.get(name,{})
        try:
            verify(c)
            if c.get('status')!=status or c.get('real_accredited') is not True or c.get('synthetic_test_only') is not False or not c.get('evidence_hash'):
                reasons.append(name+'_not_real_eligible')
        except (ValueError,TypeError):reasons.append(name+'_evidence_missing_or_invalid')
    try:
        verify(oos_gate)
        if oos_gate.get('gate_status')!='MET' or oos_gate.get('real_oos_count',0)<200 or oos_gate.get('required_oos_count',0)<200:reasons.append('minimum_real_oos_not_met')
    except (ValueError,TypeError):reasons.append('oos_evidence_invalid')
    if synthetic_test_only:reasons.append('synthetic_e2e_not_release_evidence')
    return sealed(dict(version='release-gate-v1',release_status='BLOCKED' if reasons else 'READY',
                       reason_codes=reasons,components=components,oos_gate=oos_gate,automated_promotion=False,
                       human_confirmation_required=True,automated_real_betting=False))
