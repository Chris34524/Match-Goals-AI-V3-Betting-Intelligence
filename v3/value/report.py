"""Descriptive sensitivity for caller-predefined policies; no ranking."""
from collections import Counter
from v3.odds.contract import MARKETS
from .selector import select


def distribution(values):
    values = sorted(v for v in values if v is not None)
    return dict(count=len(values), minimum=values[0] if values else None,
                maximum=values[-1] if values else None, values=values)


def summarize(rows):
    decisions = Counter(r['decision'] for r in rows)
    return dict(candidate_count=len(rows), pass_count=decisions['PASS'], no_bet_count=decisions['NO_BET'],
                blocked_count=decisions['BLOCKED'],
                reason_counts=dict(sorted(Counter(reason for r in rows for reason in r['reason_codes']).items())),
                edge_distribution=distribution([r['absolute_edge'] for r in rows]),
                ev_distribution=distribution([r['ev_per_unit'] for r in rows]),
                minimum_odds_distribution=distribution([r['minimum_acceptable_odds'] for r in rows]))


def sensitivity(candidates, policies, *, allow_synthetic=False):
    candidates, policies = list(candidates), list(policies)
    identities = [(p.policy_id, p.policy_version) for p in policies]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate_policy_identity')
    reports = []
    for policy in sorted(policies, key=lambda p:(p.policy_id, p.policy_version)):
        rows = [select(c, policy, allow_synthetic=allow_synthetic) for c in candidates]
        reports.append(dict(policy=policy.to_dict(), **summarize(rows),
            by_market={m:summarize([r for r in rows if r['market']==m]) for m in sorted(MARKETS)},
            candidates=rows))
    return dict(report_version='4.2.0', purpose='descriptive_predefined_policy_sensitivity', policies=reports)
