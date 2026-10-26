"""Canonical declarative contract; schema validity never grants ingestion rights."""
import json
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = '3.1.0'
MARKETS = {
    '1X2': ('home', 'draw', 'away'),
    'BTTS': ('yes', 'no'),
    'OVER_1_5': ('over', 'under'),
    'OVER_2_5': ('over', 'under'),
    'OVER_3_5': ('over', 'under'),
}
FUTURE_MARKETS = ('ASIAN_HANDICAP', 'CORNERS', 'CARDS')
SNAPSHOTS = ('opening', 'current', 'closing', 'unknown')
SURFACES = ('public_visible', 'documented_api', 'existing_local', 'unknown', 'unavailable')
POLICIES = ('blocked', 'requires_authorization', 'review', 'licensed_api', 'read_only_local')
STATUSES = ('available', 'planned', 'review', 'blocked')
PRICE_STATES = ('active', 'suspended', 'crossed_out', 'unavailable', 'unknown')
AGGREGATIONS = ('individual', 'average', 'maximum', 'consensus')
REQUIRED = {
    'internal_match_id', 'external_match_id', 'competition', 'season', 'kickoff_at',
    'timezone', 'market', 'selection', 'line', 'bookmaker', 'provider', 'decimal_odds',
    'observed_at', 'source_published_at', 'snapshot_type', 'source',
    'surface_availability', 'capture_policy', 'provenance', 'validity',
    'exclusion_reason', 'temporal_semantics', 'aggregation', 'population',
    'price_state', 'status',
}
FORBIDDEN = re.compile(r'(?i)(?:(?<![a-z0-9])(?:labels?|results?|champion|bt0)(?![a-z0-9])|backtest_pool|j_bt_sin_temporada)')


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None
    except ValueError:
        return None


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def member(value, choices):
    return isinstance(value, str) and value in choices


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def schema_errors(record, cutoff):
    """Validate a record, including excluded observations, without mutating it.

    Post-cutoff observations may be inventoried only with validity.pre_match=False
    and an exclusion reason. source_published_at=None remains explicitly unknown.
    """
    if not isinstance(record, dict):
        return ('invalid_record',)
    r, errors = record, []
    if set(r) != REQUIRED:
        errors.append('invalid_fields')
    for field in ('internal_match_id', 'external_match_id', 'competition', 'season', 'provider'):
        if not nonempty(r.get(field)):
            errors.append('invalid_' + field)
    for field, choices in (('market', MARKETS), ('snapshot_type', SNAPSHOTS),
                           ('surface_availability', SURFACES), ('capture_policy', POLICIES),
                           ('price_state', PRICE_STATES), ('aggregation', AGGREGATIONS), ('status', STATUSES)):
        if not member(r.get(field), choices):
            errors.append('invalid_' + field)
    market = r.get('market')
    if isinstance(market, str) and market in MARKETS:
        if not member(r.get('selection'), MARKETS[market]):
            errors.append('invalid_selection')
        line = r.get('line')
        expected = {'OVER_1_5': 1.5, 'OVER_2_5': 2.5, 'OVER_3_5': 3.5}.get(market)
        if (expected is None and line is not None) or (expected is not None and (not finite(line) or line != expected)):
            errors.append('invalid_line')
    if not finite(r.get('decimal_odds')) or r['decimal_odds'] <= 1:
        errors.append('invalid_decimal_odds')
    try:
        zone = ZoneInfo(r.get('timezone')) if nonempty(r.get('timezone')) else None
    except (ZoneInfoNotFoundError, ValueError):
        zone = None
    if zone is None:
        errors.append('invalid_timezone')
    times = {k: timestamp(r.get(k)) for k in ('kickoff_at', 'observed_at', 'source_published_at')}
    limit = timestamp(cutoff)
    if times['kickoff_at'] is None or times['observed_at'] is None or limit is None:
        errors.append('invalid_timestamp')
    if r.get('source_published_at') is not None and times['source_published_at'] is None:
        errors.append('invalid_publication_timestamp')
    if zone is not None and times['kickoff_at'] is not None:
        if times['kickoff_at'].astimezone(zone).utcoffset() != times['kickoff_at'].utcoffset():
            errors.append('timezone_offset_mismatch')
    if times['source_published_at'] and times['observed_at'] and times['source_published_at'] > times['observed_at']:
        errors.append('publication_after_observation')
    validity = r.get('validity')
    if not isinstance(validity, dict) or set(validity) != {'pre_match'} or type(validity.get('pre_match')) is not bool:
        errors.append('invalid_validity')
        prematch = False
    else:
        prematch = validity['pre_match']
    if not prematch and not nonempty(r.get('exclusion_reason')):
        errors.append('missing_exclusion_reason')
    if prematch:
        if r.get('exclusion_reason') is not None:
            errors.append('contradictory_exclusion')
        if times['observed_at'] and times['kickoff_at'] and limit:
            if not times['observed_at'] < times['kickoff_at'] or times['observed_at'] > limit or limit >= times['kickoff_at']:
                errors.append('not_available_pre_match_at_cutoff')
        if r.get('price_state') != 'active':
            errors.append('inactive_price')
    semantics = r.get('temporal_semantics')
    if not isinstance(semantics, dict) or set(semantics) != {'definition', 'evidence'}:
        errors.append('invalid_temporal_semantics')
    elif r.get('snapshot_type') in ('opening', 'closing'):
        if not all(nonempty(semantics.get(k)) for k in ('definition', 'evidence')):
            errors.append('snapshot_requires_explicit_temporal_evidence')
        if times['observed_at'] and times['kickoff_at'] and times['observed_at'] >= times['kickoff_at']:
            errors.append('opening_or_closing_not_before_kickoff')
    source = r.get('source')
    if not isinstance(source, dict) or set(source) != {'id', 'artifact', 'url'} or not any(nonempty(v) for v in source.values()):
        errors.append('invalid_source_reference')
    provenance = r.get('provenance')
    if not isinstance(provenance, dict) or set(provenance) != {'evidence', 'sha256', 'origin'} or not all(nonempty(v) for v in provenance.values()):
        errors.append('invalid_provenance')
    elif not re.fullmatch('[a-f0-9]{64}', provenance['sha256']):
        errors.append('invalid_artifact_digest')
    # Inspect only source lineage, never sporting competition names or outcomes.
    lineage = {'provider': r.get('provider'), 'source': source, 'provenance': provenance}
    if FORBIDDEN.search(json.dumps(lineage, sort_keys=True, default=str)):
        errors.append('forbidden_odds_source')
    if r.get('aggregation') == 'individual':
        if not nonempty(r.get('bookmaker')) or r.get('bookmaker', '').lower() in ('unknown', 'anonymous'):
            errors.append('bookmaker_required')
        if r.get('population') != []:
            errors.append('individual_has_population')
    elif member(r.get('aggregation'), AGGREGATIONS):
        population = r.get('population')
        if r.get('bookmaker') is not None:
            errors.append('aggregate_has_individual_bookmaker')
        good = isinstance(population, list) and len(population) >= 2
        if good:
            for p in population:
                if (not isinstance(p, dict) or set(p) != {'bookmaker', 'source_id', 'decimal_odds', 'observed_at'}
                        or not nonempty(p.get('bookmaker')) or p['bookmaker'].lower() in ('unknown', 'anonymous')
                        or not nonempty(p.get('source_id'))
                        or not finite(p.get('decimal_odds')) or p['decimal_odds'] <= 1
                        or timestamp(p.get('observed_at')) != times['observed_at']):
                    good = False
                    break
        if good and len({p['bookmaker'] for p in population}) != len(population):
            good = False
        if not good:
            errors.append('population_not_reproducible')
    return tuple(sorted(set(errors)))


def validate(record, cutoff):
    errors = schema_errors(record, cutoff)
    if errors:
        raise ValueError(', '.join(errors))
    return record


def filter_records(records, *, market=None, provider=None, snapshot=None, status=None):
    filters = {'market': market, 'provider': provider, 'snapshot_type': snapshot, 'status': status}
    return [r for r in records if all(value is None or r.get(key) == value for key, value in filters.items())]


def ingestion_errors(record, cutoff):
    from .source_matrix import automatable, source_matrix
    errors = list(schema_errors(record, cutoff))
    rows = [r for r in source_matrix() if r['provider'] == record.get('provider')] if isinstance(record, dict) else []
    if not any(automatable(r) for r in rows):
        errors.append('provider_not_authorized_for_ingestion')
    return tuple(sorted(set(errors)))
