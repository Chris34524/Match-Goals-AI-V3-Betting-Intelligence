"""2.7 permission matrix. Public surface visibility never authorizes acquisition.

This registry authorizes no network or ingestion provider. Local archival
inspection is distinct from permission to automate extraction/reuse for models.
"""
import json

VERSION = '2.7.0'
FAMILIES = ('advanced_team_stats', 'goalkeeper', 'players', 'lineups', 'injuries',
            'suspensions', 'cards', 'corners', 'news', 'context', 'manager_changes', 'transfers')
FIELDS = ('provider', 'signal_family', 'surface_available', 'capture_policy',
          'allowed_method', 'authorization_status', 'stable_ids',
          'publication_timestamp', 'as_of_capability', 'coverage',
          'rate_limit/operational_limit', 'retention_notes',
          'provenance_requirement', 'status', 'blocked_reason')


def source_matrix():
    rows = []
    for family in FAMILIES:
        rows.append(dict(zip(FIELDS, (
            'flashscore_existing_archive', family,
            'observed_local_partial' if family in ('players','lineups','injuries','suspensions','news','context','manager_changes') else 'not_accredited_in_local_archive',
            'existing_local_inventory_only', 'read_only_local_audit',
            'unproven_for_automation_and_feature_reuse', 'not_accredited',
            'not_accredited', False,
            'isolated undated TXT/HTML; no accredited structured historical stream',
            'zero network calls; no recapture authorized',
            'retain artifact references/digests; no corpus copying; reuse rights unresolved',
            'provider, grant evidence, stable entity/fixture IDs, publication/revision timestamps, artifact digest, field evidence',
            'review', 'No express authorization or accredited publication/revision lineage; public visibility is insufficient'))))
        rows.append(dict(zip(FIELDS, (
            'licensed_or_official_provider_not_selected', family, 'unknown',
            'requires_documented_permission', 'none_until_grant_verified',
            'not_evidenced', 'required', 'required', False, 'not_acquired',
            'no requests until documented provider limits and grant scope',
            'contract-specific storage/reuse/deletion terms required',
            'grant reference/scope, source ID/URL, stable IDs, publication/revision timestamp, evidence digest',
            'planned', 'Provider, license scope, operational limits, retention and as-of coverage must be selected and independently verified'))))
    return rows


def ingestion_allowed(provider, family):
    """Fail closed; current registry has no permission-backed ingestion row."""
    rows = [r for r in source_matrix() if r['provider'] == provider and r['signal_family'] == family]
    return any(r['status'] == 'available' and r['authorization_status'] == 'verified'
               and r['allowed_method'] == 'permitted_ingestion' and r['as_of_capability'] is True for r in rows)


def matrix_json():
    return json.dumps(dict(version=VERSION, sources=source_matrix()), ensure_ascii=False, sort_keys=True, indent=2)+'\n'


if __name__ == '__main__':
    print(matrix_json(), end='')
