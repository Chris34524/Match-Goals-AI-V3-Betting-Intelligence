"""Explicit closing audit; current API never implies closing."""
from v3.odds.source_matrix import source_matrix
from v3.odds.clv import clv


def report(taken=None, close=None):
    provider = next(r for r in source_matrix() if r['provider']=='the_odds_api')
    value = clv(taken,close)
    return dict(implementation_status='PASS',real_status='COMPUTABLE' if value['clv_status']=='computable' else 'BLOCKED_PROVIDER_CLOSING_SEMANTICS',
                closing_capability=provider['snapshots']['closing'],closing_accredited=value['clv_status']=='computable',
                clv_status='COMPUTABLE' if value['clv_status']=='computable' else 'BLOCKED_PROVIDER_CLOSING_SEMANTICS',clv_value=value['clv_price'],
                reason_codes=[] if value['clv_status']=='computable' else ['no_explicit_accredited_comparable_closing'],
                evidence=value,additional_odds_calls=0)
