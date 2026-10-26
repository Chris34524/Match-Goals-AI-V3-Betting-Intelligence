"""Exact deterministic names, versioned competition mapping; no outcome inputs."""
from dataclasses import dataclass
import unicodedata
from .provider import utc

VERSION = 'reconciliation-1'


def normalize(name):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', name).casefold()
                            if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).split())


@dataclass(frozen=True)
class Reconciliation:
    competition_mapping: dict
    mapping_version: str
    kickoff_tolerance_seconds: int = 300

    def __post_init__(self):
        if not self.mapping_version or not 0 <= self.kickoff_tolerance_seconds <= 3600:
            raise ValueError('invalid_reconciliation_policy')

    def reconcile(self, event, targets):
        candidates = []
        for t in targets:
            if (event.get('sport_key') != t.sport_key
                    or self.competition_mapping.get(t.sport_key) != t.competition
                    or (t.external_event_id is not None and event.get('id') != t.external_event_id)):
                continue
            try:
                good = (abs((utc(event['commence_time']) - utc(t.kickoff_at)).total_seconds())
                        <= self.kickoff_tolerance_seconds
                        and normalize(event['home_team']) == normalize(t.home)
                        and normalize(event['away_team']) == normalize(t.away))
            except (KeyError, TypeError, ValueError):
                good = False
            if good:
                candidates.append(t)
        status = 'MATCHED' if len(candidates) == 1 else 'AMBIGUOUS' if candidates else 'UNMATCHED'
        return (candidates[0] if status == 'MATCHED' else None), {
            'status': status, 'candidates': sorted(t.internal_match_id for t in candidates),
            'policy_version': VERSION, 'mapping_version': self.mapping_version,
            'kickoff_tolerance_seconds': self.kickoff_tolerance_seconds,
            'external_event_id': event.get('id')}
