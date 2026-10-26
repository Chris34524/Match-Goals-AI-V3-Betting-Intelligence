import json
import pytest
from v3.features.source_matrix import FAMILIES, FIELDS, source_matrix, ingestion_allowed, matrix_json


@pytest.mark.parametrize('family', FAMILIES)
def test_each_family_has_explicit_permission_and_limits(family):
    rows = [r for r in source_matrix() if r['signal_family'] == family]
    assert len(rows) == 2
    assert all(set(r) == set(FIELDS) for r in rows)
    assert all(r['status'] in ('available','planned','blocked','review') for r in rows)
    assert all(r['blocked_reason'] and r['rate_limit/operational_limit'] for r in rows)
    assert not any(ingestion_allowed(r['provider'], family) for r in rows)


def test_visibility_and_unknown_provider_never_authorize():
    assert not ingestion_allowed('unknown','lineups')
    rows = source_matrix(); rows[0]['authorization_status'] = 'verified'
    assert not ingestion_allowed('flashscore_existing_archive','advanced_team_stats')
    assert json.loads(matrix_json())['sources'] == source_matrix()
    assert matrix_json() == matrix_json()
