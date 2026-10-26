"""Complete, comparable canonical outcome sets only."""
import math
from v3.odds.contract import MARKETS
from .probability import implied_probability

NORMALIZATION_TOLERANCE = 1e-12
# Period/rules are explicit envelope fields: the Phase 3 schema stays unchanged.
GROUP_FIELDS = {
    'internal_match_id': 'match_mismatch', 'provider': 'source_mismatch',
    'bookmaker': 'bookmaker_mismatch', 'market': 'market_mismatch',
    'line': 'line_mismatch', 'observed_at': 'snapshot_mismatch',
    'kickoff_at': 'snapshot_mismatch', 'snapshot_type': 'snapshot_mismatch',
    'temporal_semantics': 'snapshot_mismatch',
}


def normalize(records):
    if not records:
        raise ValueError('market_incomplete')
    first = records[0]
    market = first.get('market')
    if not isinstance(market, str) or market not in MARKETS:
        raise ValueError('market_mismatch')
    for record in records:
        for field, reason in GROUP_FIELDS.items():
            if record.get(field) != first.get(field):
                raise ValueError(reason)
    selections = [r.get('selection') for r in records]
    if len(selections) != len(MARKETS[market]) or set(selections) != set(MARKETS[market]):
        raise ValueError('market_incomplete')
    q = {r['selection']: implied_probability(r['decimal_odds']) for r in records}
    total = math.fsum(q.values())
    normalized = {k: v / total for k, v in q.items()}
    if not math.isclose(math.fsum(normalized.values()), 1, rel_tol=0, abs_tol=NORMALIZATION_TOLERANCE):
        raise ValueError('normalization_failed')
    return q, normalized, total - 1
