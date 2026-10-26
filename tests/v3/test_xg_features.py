"""Issue #15: temporal, identity, pair, lineage and reproducibility gates."""
from copy import deepcopy
import hashlib
import json

import pytest

from v3.data.builder import dumps
from v3.features.engine import materialize as form
from v3.features.xg_adapter import value_digest
from v3.features.xg_engine import materialize, build_features


def fixture(n=10):
    history = dict(match_id='target', partido=dict(id='target', fecha='2026-10-20', local='A', visitante='B'), secciones=[])
    xg = dict(match_id='target', partido=dict(local='A', visitante='B'))
    attestations = {}
    for side, team in [('local', 'A'), ('visitante', 'B')]:
        rows = []
        for i in range(n):
            home = i % 2 == 0
            row = dict(match_id=f'{team}{i}', fecha=f'2026-10-{19-i:02}',
                       local=team if home else 'C', visitante='C' if home else team,
                       equipo=team, condicion_equipo='local' if home else 'visitante',
                       xg_local=2.0, xg_visitante=1.0, xgf=2.0 if home else 1.0,
                       xga=1.0 if home else 2.0, goles_local=2, goles_visitante=1,
                       resultado_parseado=True, score_scope='REGULATION')
            rows.append(row)
            attestations[row['match_id']] = dict(observed_at=row['fecha']+'T23:00:00Z',
                source_artifact='independently-verified-capture/'+row['match_id'], value_sha256=value_digest(row))
        xg[side] = dict(equipo=team, partidos=rows, l5=dict(xgf_promedio=999))
        history['secciones'].append(dict(titulo='ÚLTIMOS PARTIDOS: '+team, partidos=deepcopy(rows)))
    return history, xg, attestations


def run(h, x, a=None, cache=None):
    return materialize(h, x, cache or {}, 'target', attestations=a)


@pytest.mark.parametrize('field,value,reason', [
    ('match_id', 'target', 'target_in_input'),
    ('fecha', '2026-10-20', 'same_day_input_without_verified_time'),
    ('fecha', '2026-10-21', 'future_input'),
    ('fecha', None, 'unknown_input_date'),
    ('local', 'Other', 'unreconciled_history_identity'),
    ('condicion_equipo', 'visitante', 'team_orientation_conflict'),
    ('xg_local', -1, 'invalid_or_incomplete_bilateral_xg'),
    ('xg_local', float('nan'), 'invalid_or_incomplete_bilateral_xg'),
    ('xg_local', float('inf'), 'invalid_or_incomplete_bilateral_xg'),
    ('xg_local', True, 'invalid_or_incomplete_bilateral_xg'),
    ('xg_visitante', None, 'invalid_or_incomplete_bilateral_xg'),
    ('xgf', True, 'oriented_value_conflict'),
])
def test_rejections(field, value, reason):
    h, x, a = fixture()
    x['local']['partidos'][0][field] = value
    row = run(h, x, a)
    assert any(reason in e['reasons'] for e in row['exclusions']['home'])
    assert row['features']['home_xg_mean_l5']['value'] is None
    assert row['features']['home_xg_sample_count_l5']['value'] == 4


@pytest.mark.parametrize('n', [0, 1, 4, 5, 9, 10])
def test_exact_windows_and_partial_count(n):
    h, x, a = fixture(n)
    row = run(h, x, a)
    for size in (5, 10):
        f = row['features'][f'home_xg_mean_l{size}']
        assert f['sample_count'] == min(n, size)
        assert (f['value'] is not None) == (n >= size)
        assert f['reason'] == (None if n >= size else 'insufficient_sample')
    if n >= 5:
        assert row['features']['home_xg_mean_l5']['value'] == 1.6
        assert row['features']['home_xga_mean_l5']['value'] == 1.4


def test_duplicates_and_order():
    h, x, a = fixture()
    x['local']['partidos'].append(deepcopy(x['local']['partidos'][0]))
    first = dumps(run(h, x, a))
    for section in x.values():
        if isinstance(section, dict) and isinstance(section.get('partidos'), list):
            section['partidos'].reverse()
    for section in h['secciones']:
        section['partidos'].reverse()
    assert first == dumps(run(h, x, a))
    assert 'duplicate_match_id' in first


def test_cache_collapse_and_conflict():
    h, x, a = fixture()
    r = deepcopy(x['local']['partidos'][0])
    cache = {r['match_id']: r}
    row = run(h, x, a, cache)
    assert row['features']['home_xg_sample_count_l5']['value'] == 5
    assert len(row['windows']['home_l5']['contributing'][0]['source_artifacts']) == 2
    cache[r['match_id']]['xg_local'] = 99
    assert run(h, x, a, cache)['features']['home_xg_sample_count_l5']['value'] == 4


def test_no_lineage_no_aggregate_fallback_or_backfill():
    h, x, a = fixture()
    assert run(h, x)['features']['home_xg_sample_count_l10']['value'] == 0
    del a['A0']
    row = run(h, x, a)
    assert row['features']['home_xg_mean_l5']['value'] is None
    assert row['features']['home_xg_sample_count_l5']['value'] == 4
    assert row['features']['bilateral_xg_available_l5']['value'] is False


@pytest.mark.parametrize('observed', ['2026-10-20T00:00:00Z', '2026-10-21T00:00:00Z', '2026-10-19', 'unknown', '2026-10-01T00:00:00Z'])
def test_availability_date(observed):
    h, x, a = fixture()
    a['A0']['observed_at'] = observed
    assert run(h, x, a)['features']['home_xg_sample_count_l5']['value'] == 4


def test_form_isolation_and_unknown_sections():
    h, x, a = fixture()
    before = dumps(form(h, 'target'))
    assert len(form(h, 'target')['features']) == 72
    run(h, x, a)
    missing = run(h, {})
    assert missing['features']['home_xg_sample_count_l5']['value'] is None
    assert dumps(form(h, 'target')) == before


def test_build_deterministic_readonly_and_no_data_staged(tmp_path):
    root = tmp_path / 'data'
    folder = root / 'matches' / 'target'
    folder.mkdir(parents=True)
    (root / 'xg_cache').mkdir()
    h, x, _ = fixture()
    (folder / 'history.json').write_text(json.dumps(h))
    (folder / 'xg_history.json').write_text(json.dumps(x))
    (root / 'xg_cache' / 'A0.json').write_text(json.dumps(x['local']['partidos'][0]))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    m1 = build_features(root, tmp_path / 'one')
    m2 = build_features(root, tmp_path / 'two')
    assert m1 == m2
    for name in ('xg_features.jsonl', 'xg_manifest.json'):
        assert (tmp_path / 'one' / name).read_bytes() == (tmp_path / 'two' / name).read_bytes()
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):
        build_features(root, root / 'output')
    import subprocess
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True)
    assert not any(p.startswith('data/') for p in staged.splitlines())


@pytest.mark.parametrize('bad', [None, [], {}, {'observed_at': '2026-10-19T23:00:00Z', 'source_artifact': 'capture', 'value_sha256': 'wrong'}])
def test_untrusted_or_unbound_attestation(bad):
    h, x, a = fixture()
    a['A0'] = bad
    assert run(h, x, a)['features']['home_xg_sample_count_l5']['value'] == 4


def test_cross_side_conflict_and_no_venue_catalog():
    from v3.features.catalog import CATALOG
    h, x, a = fixture()
    other = deepcopy(x['local']['partidos'][0])
    other['xg_local'] = 20
    x['visitante']['partidos'].append(other)
    assert run(h, x, a)['features']['home_xg_sample_count_l5']['value'] == 4
    assert not any('venue' in s.name for s in CATALOG if s.group == 'xg')


def test_missing_identity_and_malformed_target():
    h, x, a = fixture()
    x['local']['partidos'][0]['match_id'] = []
    assert 'unknown_input_identity' in dumps(run(h, x, a))
    x['partido'] = None
    assert run(h, x, a)['features']['home_xg_sample_count_l5']['value'] is None
