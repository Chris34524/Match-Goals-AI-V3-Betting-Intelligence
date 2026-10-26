"""2.12 experimental P3 event schema. No corpus, scraping, NLP model or training.

Schema validity does NOT accredit source permission or timestamp authenticity.
Ingestion additionally checks the closed permission registry, which currently
admits no provider. A future provider adapter must independently verify source
publication/revision evidence; raw timestamp strings alone are insufficient.
"""
from datetime import datetime
import math
from urllib.parse import urlparse

from v3.features.source_matrix import ingestion_allowed

VERSION = '2.12.0'
EVENT_TYPES = {
    'injury_confirmed': ('player', ('confirmed',)),
    'suspension_confirmed': ('player', ('confirmed',)),
    'manager_change': ('team', ('appointed', 'departed')),
    'transfer_status': ('player', ('completed', 'negotiating', 'cancelled')),
    'rotation_statement': ('team', ('rotation_announced',)),
    'lineup_statement': ('team', ('predicted', 'official')),
    'competition_stakes': ('competition', ('title', 'relegation', 'qualification', 'knockout', 'final')),
}
REQUIRED = {'provider', 'publication_timestamp', 'entity', 'event_type',
            'structured_value', 'extraction_version', 'evidence', 'confidence'}
OPTIONAL = {'source_id', 'url', 'revision_timestamp'}


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    except ValueError:
        return None


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def schema_errors(event, cutoff):
    """Validate structure/time ordering only, without asserting authenticity."""
    if not isinstance(event, dict):
        return ('invalid_event',)
    errors = []
    if not REQUIRED <= event.keys() or set(event) - REQUIRED - OPTIONAL:
        errors.append('invalid_fields')
    for key in ('provider', 'extraction_version'):
        if not nonempty(event.get(key)):
            errors.append('invalid_' + key)
    if not (nonempty(event.get('source_id')) or nonempty(event.get('url'))):
        errors.append('missing_source_reference')
    if 'url' in event:
        try:
            u = urlparse(event['url']) if isinstance(event['url'], str) else None
        except ValueError:
            u = None
        if u is None or u.scheme != 'https' or not u.netloc:
            errors.append('invalid_source_url')
    published, limit = timestamp(event.get('publication_timestamp')), timestamp(cutoff)
    if published is None or limit is None:
        errors.append('unverified_timestamp_shape')
    elif published >= limit:
        errors.append('publication_not_before_cutoff')
    if 'revision_timestamp' in event:
        revision = timestamp(event['revision_timestamp'])
        if revision is None or published is None or limit is None or not published <= revision < limit:
            errors.append('invalid_or_late_revision')
    kind = event.get('event_type')
    spec = EVENT_TYPES.get(kind) if isinstance(kind, str) else None
    if spec is None:
        errors.append('unsupported_event_type')
    entity = event.get('entity')
    if (not isinstance(entity, dict) or set(entity) != {'kind', 'id'}
            or not nonempty(entity.get('id')) or (spec and entity.get('kind') != spec[0])):
        errors.append('invalid_entity')
    value = event.get('structured_value')
    if (not isinstance(value, dict) or set(value) != {'status'}
            or not isinstance(value.get('status'), str) or (spec and value.get('status') not in spec[1])):
        errors.append('invalid_structured_value')
    evidence = event.get('evidence')
    if not nonempty(evidence) or len(evidence) > 2000:
        errors.append('invalid_or_unbounded_evidence')
    confidence = event.get('confidence')
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
        errors.append('invalid_confidence')
    return tuple(sorted(set(errors)))


def ingestion_errors(event, cutoff):
    errors = list(schema_errors(event, cutoff))
    provider = event.get('provider') if isinstance(event, dict) else None
    if not ingestion_allowed(provider, 'news'):
        errors.append('provider_not_permitted_or_asof_unaccredited')
    return tuple(sorted(set(errors)))
