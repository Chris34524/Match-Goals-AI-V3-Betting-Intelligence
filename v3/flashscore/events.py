"""Typed event ledger, not a bookmaker card-points or first-scorer adapter."""
from .contract import PERIODS

KINDS = ('goal', 'penalty_goal', 'own_goal', 'cancelled_goal', 'yellow',
         'second_yellow', 'red', 'substitution')
SCOPES = ('regulation', 'extra_time', 'shootout')


def normalize_events(rows, fixture, completeness_reference):
    if not isinstance(rows, list) or not completeness_reference:
        raise ValueError('event ledger needs explicit completeness evidence')
    seen, dismissals, normalized = set(), {}, []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid event')
        required = ('event_id', 'kind', 'period', 'score_scope', 'side', 'actor_id',
                    'actor_scope', 'minute', 'added_time', 'sequence')
        if any(key not in row for key in required):
            raise ValueError('incomplete event identity/type/time')
        if not isinstance(row['event_id'], str) or not row['event_id'] or row['event_id'] in seen:
            raise ValueError('duplicate/unresolved event')
        seen.add(row['event_id'])
        if (row['kind'] not in KINDS or row['period'] not in PERIODS
                or row['score_scope'] not in SCOPES or row['side'] not in ('home', 'away')
                or row['actor_scope'] not in ('player', 'bench', 'staff', 'unknown')
                or not isinstance(row['actor_id'], str) or not row['actor_id']
                or any(type(row[k]) is not int or row[k] < 0 for k in ('minute', 'added_time', 'sequence'))):
            raise ValueError('ambiguous event')
        if row['kind'] == 'substitution' and not row.get('replacement_id'):
            raise ValueError('substitution requires both player IDs')
        if row['kind'] in ('second_yellow', 'red'):
            if not row.get('dismissal_id') or row.get('dismissal_kind') not in ('direct_red', 'second_yellow'):
                raise ValueError('red-card ambiguity')
            if row['kind'] == 'second_yellow' and row['dismissal_kind'] != 'second_yellow':
                raise ValueError('second-yellow type mismatch')
            identity = (row['side'], row['actor_id'], row['actor_scope'], row['period'],
                        row['score_scope'], row['dismissal_kind'])
            key = row['dismissal_id']
            if key in dismissals and dismissals[key] != identity:
                raise ValueError('conflicting dismissal linkage')
            dismissals[key] = identity
        normalized.append(dict(row))
    # A second-yellow red representation is only credible with its triggering caution.
    triggers = {r['dismissal_id'] for r in normalized if r['kind'] == 'second_yellow'}
    if any(r['kind'] == 'red' and r['dismissal_kind'] == 'second_yellow'
           and r['dismissal_id'] not in triggers for r in normalized):
        raise ValueError('unlinked second-yellow red')
    return dict(validated=True, rows=sorted(normalized, key=lambda r: (
        SCOPES.index(r['score_scope']), PERIODS.index(r['period']), r['minute'],
        r['added_time'], r['sequence'], r['event_id'])),
        completeness_reference=completeness_reference,
        unique_dismissals=len(dismissals),
        # This is diagnostic only: includes bench/staff and all scopes, never team market cards.
        market_card_count=None, card_count_reason='requires_explicit_actor_period_and_settlement_rules')
