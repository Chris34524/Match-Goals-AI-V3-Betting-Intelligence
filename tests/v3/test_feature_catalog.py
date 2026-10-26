"""Catalog contract and read-only audit regression tests."""
from dataclasses import FrozenInstanceError, asdict
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from v3.features import CATALOG, MARKETS, catalog_json, get_catalog
from v3.features.catalog import STATUSES, WINDOWS
from v3.features.audit import audit_sources


def test_names_unique_and_sorted():
    names = [f.name for f in CATALOG]
    assert len(names) == len(set(names))
    assert names == sorted(names)


def test_serialization_is_canonical_and_detached():
    original = catalog_json()
    obj = json.loads(original)
    assert obj['catalog_version'] == '2.1.0'
    assert original == json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                  allow_nan=False, separators=(',', ':')) + '\n'
    obj['features'][0]['markets'].clear()
    assert catalog_json() == original


def test_serialization_across_hash_seeds():
    outputs = [subprocess.check_output(
        [sys.executable, '-c', 'from v3.features import catalog_json; print(catalog_json(), end="")'],
        env={**os.environ, 'PYTHONHASHSEED': str(seed)}) for seed in (1, 42)]
    assert outputs[0] == outputs[1] == catalog_json().encode()


@pytest.mark.parametrize('spec', CATALOG, ids=lambda f: f.name)
def test_feature_contract(spec):
    assert all(asdict(spec)[k] for k in ('name', 'group', 'description', 'dtype', 'side',
                                        'temporal_requirement', 'missing_policy', 'leakage_risk'))
    assert spec.status in STATUSES
    assert spec.window in WINDOWS
    assert spec.dtype in ('float', 'int', 'bool')
    assert spec.markets and set(spec.markets) <= set(MARKETS)
    assert len(spec.markets) == len(set(spec.markets))
    assert spec.min_sample is None or (type(spec.min_sample) is int and spec.min_sample >= 0)
    assert spec.source_artifacts
    assert isinstance(spec.source_artifacts, tuple)
    assert spec.blocked_reason if spec.status == 'blocked' else spec.blocked_reason is None
    for artifact in spec.source_artifacts:
        assert not any(s in artifact.casefold() for s in
                       ('labels', 'backtest_pool', 'champion', 'lambda_comparison', 'result.json', 'enriched'))
    if spec.status == 'available':
        assert 'strictly before' in spec.temporal_requirement
        assert 'same-day' in spec.temporal_requirement
        assert 'sample_reasons' in spec.temporal_requirement


@pytest.mark.parametrize('key,values', [('market', MARKETS), ('status', STATUSES),
                                        ('group', sorted({f.group for f in CATALOG}))])
def test_filters_are_exact_and_nonmutating(key, values):
    before = catalog_json()
    for value in values:
        filtered = get_catalog(**{key: value})
        expected = tuple(f for f in CATALOG if (value in f.markets if key == 'market'
                                                else getattr(f, key) == value))
        assert filtered == expected
        assert json.loads(catalog_json(**{key: value}))['features'] == json.loads(
            json.dumps([asdict(f) for f in expected]))
    assert catalog_json() == before


def test_combined_filters_and_immutability():
    assert get_catalog(market='BTTS', group='strength', status='available') == ()
    assert get_catalog(market='BTTS', group='recent_form', status='available')
    with pytest.raises(FrozenInstanceError):
        CATALOG[0].name = 'changed'
    for key in ('market', 'group', 'status'):
        with pytest.raises(ValueError):
            get_catalog(**{key: 'unknown'})


def test_required_families_and_market_specificity():
    names = {f.name for f in CATALOG}
    for side in ('home', 'away'):
        for n in (5, 10):
            for prefix in (side, side + '_venue'):
                for metric in ('gf_mean', 'ga_mean', 'btts_rate', 'over_1_5_rate',
                               'over_2_5_rate', 'over_3_5_rate', 'clean_sheet_rate',
                               'failed_to_score_rate', 'sample_count'):
                    assert f'{prefix}_{metric}_l{n}' in names
    assert all(f.status == 'blocked' for f in get_catalog(group='xg'))
    assert all(f.status == 'blocked' for f in get_catalog(group='strength'))
    assert all(f.group == 'h2h_auxiliary' for f in CATALOG if f.side == 'h2h')
    assert get_catalog(market='OVER_3_5')
    assert next(f for f in CATALOG if f.name == 'home_btts_rate_l5').markets == ('BTTS',)


def write_history(root, samples):
    folder = root / 'target'
    folder.mkdir()
    history = {'match_id': 'target', 'partido': {'id': 'target', 'fecha': '2026-10-20',
                                                'local': 'A', 'visitante': 'B'},
               'secciones': [{'titulo': 'ÚLTIMOS PARTIDOS: A', 'partidos': samples}]}
    (folder / 'history.json').write_text(json.dumps(history))
    return folder


def sample(mid='old', date='2026-10-19', **updates):
    return dict(match_id=mid, fecha=date, local='A', visitante='C',
                goles_local=1, goles_visitante=0, resultado_parseado=True, **updates)


def test_audit_temporal_exclusion_and_source_immutability(tmp_path):
    folder = write_history(tmp_path, [sample(), sample('target'),
                                    sample('same', '2026-10-20'),
                                    sample('future', '2026-10-21'),
                                    sample('unknown', 'bad')])
    files = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()}
    report = audit_sources(tmp_path)
    assert report['directories'] == 1
    assert report['evidence_counts']['home:valid_count_ge_1'] == 1
    assert report['evidence_counts']['home:valid_count_ge_5'] == 0
    assert report['evidence_counts']['home:sections_without_rejections'] == 0
    assert report['sample_rejections'] == {'target_in_input': 1, 'future_input': 1,
                                         'same_day_input_without_verified_time': 1,
                                         'unknown_input_date': 1}
    assert report == audit_sources(tmp_path)
    assert files == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.iterdir()}


def test_audit_rejects_duplicate_keys_and_symlinks(tmp_path):
    folder = write_history(tmp_path, [])
    (folder / 'standings.json').write_text('{"x":1,"x":2}')
    (folder / 'enriched.json').symlink_to(folder / 'history.json')
    report = audit_sources(tmp_path)
    assert report['artifact_counts']['invalid:standings.json'] == 1
    assert report['artifact_counts']['symlink:enriched.json'] == 1
    assert report['evidence_counts']['home:recognized_sections'] == 1
    assert report['evidence_counts']['home:valid_count_ge_1'] == 0


def test_audit_numeric_xg_is_not_authorization(tmp_path):
    folder = write_history(tmp_path, [])
    (folder / 'xg_history.json').write_text(json.dumps({
        'local': {'partidos': [{'match_id': 'future', 'fecha': '2026-10-21', 'xgf': 1, 'xga': 2}]},
        'visitante': {'partidos': [{'xgf': True, 'xga': 2}]}}))
    report = audit_sources(tmp_path)
    assert report['evidence_counts']['xg:paired_samples'] == 1
    assert report['evidence_counts']['xg:paired_samples_temporally_rejected'] == 1
    assert report['evidence_counts']['xg:bilateral_any_numeric_pair'] == 0
    assert all(f.status == 'blocked' for f in get_catalog(group='xg'))


def test_audit_hash_tracks_relative_path_and_bytes(tmp_path):
    folder = write_history(tmp_path, [])
    original = audit_sources(tmp_path)['source_content_sha256']
    (folder / 'history.json').write_text((folder / 'history.json').read_text() + '\n')
    assert audit_sources(tmp_path)['source_content_sha256'] != original
