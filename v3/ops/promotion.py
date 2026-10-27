"""O-06 recommendation wraps frozen Phase 6.3 policy; never mutates models."""
from v3.validation.promotion import evaluate, CHAMPION


def recommend(oos, evidence=None):
    evidence = evidence or {}
    reasons = []
    if oos['oos_gate_status'] != 'MET' or oos['real_oos_count'] < 200:
        reasons.append('minimum_real_oos_not_met')
    if evidence.get('oos_count') != oos['real_oos_count']:
        reasons.append('oos_population_count_mismatch')
    for key in ('challenger_real_predictions', 'same_population', 'same_market', 'calibration_comparable', 'walk_forward_valid', 'paper_economics_comparable'):
        if evidence.get(key) is not True:
            reasons.append(key + '_missing')
    decision = evaluate(evidence)
    reasons += decision['reason_codes']
    status = 'BLOCKED'
    if not reasons and decision['gate_status'] == 'PROMOTE_ELIGIBLE':
        status = 'PROMOTE'
    elif not any(r.endswith('_missing') for r in reasons) and decision['gate_status'] == 'DO_NOT_PROMOTE' and oos['oos_gate_status']=='MET':
        # Policy negatives can recommend keeping only when prerequisite checks pass.
        prereqs = all(evidence.get(k) is True for k in ('challenger_real_predictions','same_population','same_market','calibration_comparable','walk_forward_valid','paper_economics_comparable'))
        if prereqs and evidence.get('oos_count') == oos['real_oos_count'] and 'minimum_windows_not_met' not in reasons:
            status = 'KEEP_CHAMPION'
    return dict(implementation_status='PASS', real_status=status, promotion_status=status,
                champion=CHAMPION, gate_prerequisite_status='MET' if status!='BLOCKED' else 'BLOCKED', champion_changed=False, human_confirmation_required=True,
                auto_promotion=False, challengers_evaluable=status!='BLOCKED', reason_codes=sorted(set(reasons)), policy_evaluation=decision)
