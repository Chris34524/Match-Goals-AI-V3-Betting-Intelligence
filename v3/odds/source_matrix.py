"""Versioned evidence registry. Visibility, permission and time are independent.

Project authorization is explicit; credentials, budget and temporal accreditation
remain independent runtime controls.
"""
from pathlib import Path
from .contract import canonical_json, SURFACES, POLICIES, STATUSES, member

MATRIX_PATH = Path(__file__).resolve().parents[2] / 'docs/v3/odds/source-matrix.json'


def source_matrix(*, market=None, provider=None, snapshot=None, status=None):
    import json
    rows = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))['sources']
    return [r for r in rows if (market is None or market in r['markets'])
            and (provider is None or r['provider'] == provider)
            and (snapshot is None or r['snapshots'].get(snapshot) == 'documented')
            and (status is None or r['status'] == status)]


def automatable(row):
    """Fail closed on policy/status/grant; callers cannot override the registry."""
    return (row.get('status') == 'available'
            and row.get('capture_policy') == 'licensed_api'
            and row.get('authorization_status') == 'verified_project_grant'
            and row.get('acquisition_method') == 'official_api'
            and row.get('automatable') is True)


def matrix_errors(rows):
    errors = []
    required = {'provider', 'markets', 'future_markets', 'surface_availability',
                'leagues_countries', 'bookmaker_coverage', 'snapshots',
                'temporal_semantics', 'timestamp_semantics', 'acquisition_method',
                'permission_licence_status', 'authorization_status', 'rate_limits',
                'retention', 'stable_ids', 'capture_policy', 'status',
                'unblock_requirement', 'leakage_risk', 'priority', 'evidence',
                'automatable', 'reviewed_at'}
    providers = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            errors.append('invalid_matrix_fields')
            continue
        if not member(row['surface_availability'], SURFACES) or not member(row['capture_policy'], POLICIES) or not member(row['status'], STATUSES):
            errors.append('invalid_vocabulary')
        if row['automatable'] is not False and not automatable(row):
            errors.append('unauthorized_automation')
        if row['provider'] in providers:
            errors.append('duplicate_provider')
        providers.add(row['provider'])
        if row['priority'] not in ('P0', 'P1', 'P2', 'P3') or not row['evidence']:
            errors.append('missing_priority_or_evidence')
        if set(row['snapshots']) != {'opening', 'current', 'closing'}:
            errors.append('invalid_snapshot_coverage')
    return tuple(sorted(set(errors)))


def matrix_json():
    return canonical_json({'version': '3.1.0', 'sources': source_matrix()})
