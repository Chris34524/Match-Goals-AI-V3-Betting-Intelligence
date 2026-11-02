"""Predeclared bounded cohort plans and minimal retained acquisition artifacts."""
from copy import deepcopy
from dataclasses import asdict
from v3.flashscore.contract import dumps, timestamp
from v3.flashscore.manifest import MANIFEST_VERSION
from v3.providers.contract import VERSION as CAPTURE_VERSION, digest
from v3.providers.registry import registration
from . import VERSION
from .adapter import Adapter
from .accreditation import assess
from .bridge import coverage
from .client import Client, AcquisitionError, now
from .normalization import LABELS
from .parser import parse_fixture
from .storage import ROOT, atomic_json

SCHEMA = 'api-football-cohort-1'
STATES = ('PLANNED', 'CAPTURED', 'PARTIAL', 'BLOCKED')
FIELDS = tuple(sorted((*LABELS.values(), 'cards', 'goals_ft', 'goals_first_half')))


def plan(*, cohort_id, created_at, competition_ids, seasons, fixture_ids, date_from, date_to,
         requested_fields=FIELDS, periods=('FT', '1H'), request_budget=3, metadata_references=()):
    result = dict(schema_version=SCHEMA, cohort_id=cohort_id, provider='api_football',
        created_at=created_at, status='PLANNED', competition_ids=sorted(set(competition_ids)),
        seasons=sorted(set(seasons)), fixture_ids=sorted(set(fixture_ids)),
        date_range=dict(start=date_from, end=date_to), requested_fields=sorted(set(requested_fields)),
        periods=sorted(set(periods)), authorization_mode=registration('api_football').authorization_mode,
        request_budget=request_budget, provider_quota_snapshot={},
        schema_versions=dict(parser=VERSION, capture=CAPTURE_VERSION, manifest=SCHEMA),
        metadata_references=list(metadata_references), captures=[], hashes={},
        real_model_training='BLOCKED', blocked_reasons=[])
    validate_manifest(result)
    return result


def validate_manifest(data):
    if data.get('schema_version') != SCHEMA or data.get('provider') != 'api_football' or data.get('status') not in STATES:
        raise ValueError('invalid_cohort_manifest')
    if not isinstance(data.get('cohort_id'), str) or not data['cohort_id'].strip():
        raise ValueError('cohort_id_required')
    timestamp(data['created_at'])
    from datetime import date
    if date.fromisoformat(data['date_range']['start']) > date.fromisoformat(data['date_range']['end']):
        raise ValueError('invalid_date_range')
    for key in ('competition_ids', 'seasons', 'fixture_ids'):
        values = data[key]
        if not isinstance(values, list) or any(type(x) is not int or x <= 0 for x in values) or values != sorted(set(values)):
            raise ValueError('explicit_stable_ids_required')
    if (not data['requested_fields'] or set(data['requested_fields']) - set(FIELDS)
            or not data['periods'] or set(data['periods']) - {'FT', '1H', '2H'}):
        raise ValueError('invalid_requested_fields_or_periods')
    if type(data['request_budget']) is not int or data['request_budget'] < 1:
        raise ValueError('positive_manifest_request_budget_required')
    if data['authorization_mode'] != registration('api_football').authorization_mode:
        raise ValueError('authorization_mode_is_not_a_grant')
    dumps(data)
    return data


def audit_manifest(manifest, observations):
    fixtures = {c.request.fixture.identity: c.request.fixture for c in observations}
    fields = {(c.request.capability_name, c.request.period, c.request.surface) for c in observations}
    return dict(schema_version=MANIFEST_VERSION, manifest_id=manifest['cohort_id'],
        declared_at=manifest['created_at'], fixtures=[asdict(f) for f in fixtures.values()],
        fields=[dict(canonical_stat=name, period=period, surface=surface)
                for name, period, surface in sorted(fields)], min_successful_inspections=30)


def retain(root, manifest, observations, provenance, accreditation):
    if observations:
        records = [c.to_dict() for c in observations]
        bundle = dict(schema_version=SCHEMA, observations=records, provenance=provenance,
                      accreditation=accreditation, origin='real_provider_capture', historical_asof='UNVERIFIED')
        manifest['hashes']['normalized'] = digest(bundle)
        atomic_json(root / 'normalized' / (digest(bundle) + '.json'), bundle)
        frame = audit_manifest(manifest, observations)
        report = coverage(frame, observations)
        report['cohort_unresolved_fixture_ids'] = manifest['unresolved_fixture_ids']
        report['cohort_complete'] = not manifest['unresolved_fixture_ids']
        report['denominator_scope'] = 'resolved fixtures only; unresolved planned IDs remain unassessed'
        atomic_json(root / 'audit' / (manifest['cohort_id'] + '.json'), report)
        manifest['hashes']['audit'] = digest(report)
    atomic_json(root / 'manifests' / (manifest['cohort_id'] + '.json'), manifest)


def collect(manifest, *, live=False, max_requests=None, root=ROOT):
    manifest = deepcopy(validate_manifest(manifest))
    # Validate every output path before any network activity.
    from .storage import checked_path
    from pathlib import Path
    root = Path(root)
    if '/' in manifest['cohort_id'] or '\\' in manifest['cohort_id'] or manifest['cohort_id'] in ('.', '..'):
        raise ValueError('invalid_cohort_id')
    checked_path(root / 'manifests' / (manifest['cohort_id'] + '.json'))
    if not live:
        return dict(manifest=manifest, live_status='DRY_RUN', requests_made=0,
                    planned_requests=len(manifest['fixture_ids']) * 2, real_model_training='BLOCKED')
    if type(max_requests) is not int or max_requests < 1:
        raise AcquisitionError('explicit_positive_request_budget_required')
    if max_requests > manifest['request_budget']:
        raise AcquisitionError('budget_exceeds_manifest')
    if not manifest['fixture_ids'] or not manifest['competition_ids'] or not manifest['seasons']:
        raise AcquisitionError('resolved_manifest_universe_required')
    if timestamp(manifest['created_at']) > timestamp(now()):
        raise AcquisitionError('manifest_declared_in_future')
    planned = len(manifest['fixture_ids']) * 2 + (max_requests > 3)
    if planned > max_requests:
        raise AcquisitionError('planned_requests_exceed_budget')
    observations, provenance, accreditation, client = [], [], [], None
    try:
        client = Client(live=True, max_requests=max_requests)
        if max_requests > 3:
            client.get('/status')
        for fixture_id in manifest['fixture_ids']:
            payload, fc = client.get('/fixtures', {'id': fixture_id})
            if len(payload['response']) != 1:
                raise AcquisitionError('fixture_not_resolved')
            fixture, metadata = parse_fixture(payload['response'][0])
            if (fixture.match_id != str(fixture_id) or int(fixture.competition_id) not in manifest['competition_ids']
                    or int(fixture.season) not in manifest['seasons']
                    or not manifest['date_range']['start'] <= fixture.match_date <= manifest['date_range']['end']):
                raise AcquisitionError('fixture_outside_manifest')
            params = dict(fixture=fixture_id)
            if set(manifest['periods']) & {'1H', '2H'}:
                params['half'] = 'true'
            stats, sc = client.get('/fixtures/statistics', params)
            adapter = Adapter()
            normalized = adapter.normalize(payload, stats, fc, sc)
            observations.extend(c for c in normalized if c.request.capability_name in manifest['requested_fields']
                                and c.request.period in manifest['periods'])
            provenance.extend(adapter.provenance)
            accreditation.extend(dict(capability_key=list(c.request.key),
                **assess(c, payload, fc, stats, sc)) for c in normalized
                if c.request.capability_name in manifest['requested_fields'] and c.request.period in manifest['periods'])
        manifest['status'] = 'CAPTURED' if observations and all(c.state.value == 'AVAILABLE' for c in observations) else 'PARTIAL'
    except (AcquisitionError, ValueError, KeyError, TypeError) as error:
        # Error details and provider payloads deliberately never enter artifacts.
        manifest['status'] = 'PARTIAL' if observations else 'BLOCKED'
        manifest['blocked_reasons'] = [str(error) if isinstance(error, AcquisitionError)
                                       else 'acquisition_or_identity_validation_failed']
    resolved = {int(c.request.fixture.match_id) for c in observations}
    manifest['unresolved_fixture_ids'] = sorted(set(manifest['fixture_ids']) - resolved)
    manifest['captures'] = client.captures if client else []
    manifest['provider_quota_snapshot'] = client.quota if client else {}
    manifest['hashes']['capture_metadata'] = digest(manifest['captures'])
    try:
        retain(root, manifest, observations, provenance, accreditation)
    except (OSError, ValueError):
        raise AcquisitionError('artifact_write_failed', requests_made=client.used if client else 0) from None
    return dict(manifest=manifest, live_status='BLOCKED_NO_KEY' if manifest['blocked_reasons'] == ['BLOCKED_NO_KEY']
                else manifest['status'], requests_made=client.used if client else 0,
                real_model_training='BLOCKED')
