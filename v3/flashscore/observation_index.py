"""Lane B observation storage. Inputs are capabilities, never feature/target rows."""
from collections import defaultdict
from hashlib import sha256

from .contract import Capability, dumps, timestamp


def digest(value):
    return sha256(dumps(value).encode('utf-8')).hexdigest()


class ObservationIndex:
    """Build once; exact duplicates collapse and conflicting fixture identities fail.

    Historical selection uses verified publication/revision time, not discovery
    time. Equal latest lineage with different payloads is unresolved. Settlement
    selection instead uses latest observation time, including failed inspections.
    """

    def __init__(self, observations):
        self.fixtures = {}
        self.by_key = defaultdict(list)
        self.by_team = defaultdict(list)
        seen = set()
        for original in observations:
            if not isinstance(original, Capability):
                raise ValueError('only FS capabilities accepted; labels/features forbidden')
            c = Capability.from_dict(original.to_dict())  # detach mutable payloads
            f = c.request.fixture
            key = (f.provider, f.match_id)
            if key in self.fixtures and self.fixtures[key] != f:
                raise ValueError('conflicting fixture identity/orientation')
            self.fixtures[key] = f
            hashed = digest(c.to_dict())
            if hashed not in seen:
                self.by_key[c.request.key].append(c)
                seen.add(hashed)
        for f in self.fixtures.values():
            for team in (f.home_id, f.away_id):
                self.by_team[(f.provider, team)].append(f)
        for fixtures in self.by_team.values():
            fixtures.sort(key=lambda f: (f.match_date or '', f.match_id), reverse=True)

    def select(self, key, cutoff=None):
        candidates = self.by_key.get(key, ())
        if cutoff is not None:
            limit = timestamp(cutoff)
            candidates = [c for c in candidates if lineage_before(c, limit)]
            rank = lambda c: timestamp(c.evidence.revision_at or c.evidence.publication_at)
        else:
            rank = lambda c: timestamp(c.evidence.observed_at)
        if not candidates:
            return None, 'temporal_ineligible' if self.by_key.get(key) else 'missing_operand'
        latest_time = max(map(rank, candidates))
        latest = [c for c in candidates if rank(c) == latest_time]
        # Discovery times can differ for identical historic payloads; keep this
        # conservative: conflicting full observations at equal lineage fail closed.
        if len(latest) != 1:
            return None, 'conflicting_latest_observations'
        return latest[0], None


def lineage_before(c, limit):
    e = c.evidence
    if not e.publication_verified or not e.revision_history_verified or e.publication_at is None:
        return False
    publication = timestamp(e.publication_at)
    revision = timestamp(e.revision_at) if e.revision_at else publication
    return publication <= revision < limit


def operand_key(fixture, metric, period, side, entity=None, level='team'):
    return (fixture.provider, fixture.match_id, metric, period, level, side,
            entity or getattr(fixture, side + '_id'))


def provenance(c):
    return dict(observation_sha256=digest(c.to_dict()), capability_key=list(c.request.key),
                request=c.to_dict()['request'], evidence=c.to_dict()['evidence'],
                state=c.state.value, settlement_compatible=c.settlement_compatible)
