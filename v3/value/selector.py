"""Revalidate evidence, then apply independent unrounded policy gates."""
from v3.odds.contract import finite
from .engine import evaluate
from .policy import default_policy
from .contract import safe


def minimum_odds(p, fair, policy):
    if not finite(p) or p <= 0 or not finite(fair):
        raise ValueError('minimum_odds_not_computable')
    markup = fair * (1 + policy.safety_margin)
    ev = (1 + policy.min_ev) / p
    if not finite(markup) or not finite(ev):
        raise ValueError('minimum_odds_not_computable')
    return dict(method='max_markup_and_ev', safety_margin=policy.safety_margin,
                min_ev=policy.min_ev, min_absolute_edge=policy.min_absolute_edge,
                min_relative_edge=policy.min_relative_edge,
                minimum_odds_markup=markup, minimum_odds_ev=ev,
                minimum_acceptable_odds=max(markup, ev))


def select(candidate, policy=None, *, allow_synthetic=False):
    """Never trust serialized eligibility/metrics: replay original 4.1 evidence."""
    policy = policy or default_policy()
    provenance = candidate.get('provenance', {}) if isinstance(candidate, dict) else {}
    if not isinstance(provenance, dict):
        provenance = {}
    verified = evaluate(provenance.get('target'), provenance.get('observations'), allow_synthetic=allow_synthetic)
    mismatch = not isinstance(candidate, dict) or candidate != verified
    out = {k: v for k, v in verified.items() if k not in ('eligibility', 'exclusion_reason')}
    out.update(decision='BLOCKED', reason_codes=[], policy_id=policy.policy_id,
               policy_version=policy.policy_version, policy_components=None, minimum_acceptable_odds=None)
    if verified['eligibility'] != 'ELIGIBLE':
        out['reason_codes'] = [verified['exclusion_reason']]
        return out
    if mismatch:
        out['reason_codes'] = ['candidate_integrity_mismatch']
        return out
    try:
        parameters = policy.for_market(verified['market'])
        components = minimum_odds(verified['model_probability'], verified['fair_odds'], parameters)
    except (ValueError, KeyError):
        out['reason_codes'] = ['minimum_odds_not_computable']
        return out
    out.update(policy_components=components, minimum_acceptable_odds=components['minimum_acceptable_odds'])
    gates = [('odds_below_minimum', verified['market_odds'] >= components['minimum_acceptable_odds']),
             ('edge_below_threshold', verified['absolute_edge'] >= parameters.min_absolute_edge),
             ('relative_edge_below_threshold', verified['relative_edge'] is not None and verified['relative_edge'] >= parameters.min_relative_edge),
             # Compare equivalent EV price boundary: avoids cancellation at exact equality.
             ('ev_below_threshold', verified['market_odds'] >= components['minimum_odds_ev'])]
    out['reason_codes'] = [reason for reason, passed in gates if not passed]
    out['decision'] = 'NO_BET' if out['reason_codes'] else 'PASS'
    return safe(out)
