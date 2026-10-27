"""Minimum 200 unique real matches; multiple markets never inflate the count."""
from collections import Counter
from v3.calibration.contract import sealed
from .analyzer import eligible

POLICY=dict(version='real-unique-settled-oos-v1',threshold=200,count_unit='unique_internal_match_id',auto_promote=False)


def count_positions(positions, *, threshold=200,integrity_status='PASS'):
    if type(threshold) is not int or threshold<200:raise ValueError('oos_threshold_must_be_at_least_200')
    identities=Counter(p.get('paper_bet_id') for p in positions)
    valid=[p for p in positions if eligible(p) and identities[p['paper_bet_id']]==1]
    matches=sorted({p['internal_match_id'] for p in valid})
    return sealed(dict(gate_status='BLOCKED' if integrity_status!='PASS' else 'MET' if len(matches)>=threshold else 'NOT_MET',
                       real_oos_count=len(matches),required_oos_count=threshold,eligible_paper_count=len(valid),
                       reason_codes=['integrity_problem'] if integrity_status!='PASS' else [] if len(matches)>=threshold else ['minimum_real_oos_not_met'],
                       eligible_match_ids=matches,excluded_count=len(positions)-len(valid),policy=dict(POLICY,threshold=threshold)))


def evaluate(ledger, *, threshold=200):
    try:positions=ledger.positions()
    except (ValueError,KeyError,TypeError):return count_positions([],threshold=threshold,integrity_status='FAIL')
    return count_positions(positions,threshold=threshold)
