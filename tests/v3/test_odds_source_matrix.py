from copy import deepcopy
from pathlib import Path
import pytest
from v3.odds.source_matrix import source_matrix, matrix_errors, matrix_json, automatable, MATRIX_PATH


def test_versioned_matrix_is_deterministic_and_complete():
    rows=source_matrix()
    assert len(rows)==5
    assert not matrix_errors(rows)
    assert matrix_json()==MATRIX_PATH.read_text()
    assert [r['provider'] for r in rows if automatable(r)] == ['the_odds_api']
    assert {r['provider'] for r in rows}=={'flashscore','football_data','the_odds_api','api_football','local_inventory'}


@pytest.mark.parametrize('status',['blocked','review','planned'])
@pytest.mark.parametrize('policy',['blocked','requires_authorization','review','read_only_local'])
def test_nonpermitted_sources_never_automatable(status,policy):
    row=source_matrix()[0]
    row.update(status=status,capture_policy=policy,automatable=True,authorization_status='verified_project_grant',acquisition_method='official_api')
    assert not automatable(row)
    assert 'unauthorized_automation' in matrix_errors([row])


def test_registry_is_fresh_and_candidates_are_explicit():
    rows=source_matrix(); rows[0]['status']='available'
    assert source_matrix()[0]['status']=='blocked'
    fs=source_matrix(provider='flashscore')[0]
    assert fs['surface_availability']=='public_visible' and not automatable(fs)
    fd=source_matrix(provider='football_data')[0]
    assert fd['snapshots']['opening']=='unverified' and fd['capture_policy']=='requires_authorization'
    assert len(source_matrix(status='available')) == 1
    assert not any(r['surface_availability']=='existing_local' for r in source_matrix())


def test_matrix_filters_and_unknown_snapshots():
    assert len(source_matrix(market='BTTS'))==3
    assert [r['provider'] for r in source_matrix(snapshot='closing')]==['football_data']
    assert source_matrix(snapshot='opening')==[]
    assert len(source_matrix(status='review'))==3
    assert len(source_matrix(market='1X2',provider='flashscore',status='blocked',snapshot='current'))==1
    assert source_matrix(provider='nonexistent')==[]


def test_invalid_vocab_and_duplicates():
    rows=source_matrix(); rows[0]['capture_policy']='automatic'
    assert 'invalid_vocabulary' in matrix_errors(rows)
    rows=source_matrix(); rows.append(deepcopy(rows[0]))
    assert 'duplicate_provider' in matrix_errors(rows)
