import hashlib
import json
from pathlib import Path

import pytest

from v3.data.builder import build_dataset
from v3.data.schema import CanonicalMatch, Metadata, Inputs, Audit


def write(root, name='a', **changes):
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    history = dict(match_id=name, available_at='2026-10-20T10:00:00+00:00',
                   partido=dict(id=name, fecha='2026-10-24', local='Home', visitante='Away'),
                   secciones=[dict(titulo='ÚLTIMOS PARTIDOS: ' + team, partidos=[
                       dict(match_id='old-' + team, fecha='19.10.26', local=team,
                            visitante='Other', resultado_parseado=True,
                            goles_local=1, goles_visitante=0)]) for team in ('Home', 'Away')])
    history.update(changes)
    put(folder, 'history.json', history)
    return folder


def put(folder, name, obj):
    (folder / name).write_text(json.dumps(obj), encoding='utf-8')


def rows(output):
    return [json.loads(line) for line in (output / 'dataset_v3.jsonl').read_text().splitlines()]


def run(tmp_path, **changes):
    source, output = tmp_path / 'sources', tmp_path / 'output'
    folder = write(source, **changes)
    build_dataset(source, output)
    return folder, rows(output)[0]


def test_minimal_and_optional_null(tmp_path):
    _, row = run(tmp_path)
    assert row['audit']['eligible']
    assert row['audit']['temporal_status'] == 'OK'
    assert row['inputs']['home']['history_count'] == 1
    assert row['inputs']['away']['venue_history_count'] == 0
    assert row['inputs']['home']['xg_count'] is None
    assert row['metadata']['kickoff'] is None
    assert row['labels'] is row['predictions'] is None
    for value, contract in [(row, CanonicalMatch), (row['metadata'], Metadata),
                            (row['inputs'], Inputs), (row['audit'], Audit)]:
        assert set(value) == set(contract.__annotations__)


@pytest.mark.parametrize('change', [dict(partido={}), dict(secciones='bad')])
def test_incomplete_temporal_or_structure(tmp_path, change):
    _, row = run(tmp_path, **change)
    assert not row['audit']['eligible']
    assert row['audit']['reasons']


def test_identity_and_duplicate(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    a = write(source)
    write(source, 'b', match_id='a')
    put(a, 'result.json', {'partido': {'local': 'Different'}})
    build_dataset(source, output)
    for row in rows(output):
        assert not row['audit']['eligible']
        assert 'duplicate_match_id:a' in row['audit']['reasons']
    assert any('identity_conflict:home_team' in r for r in rows(output)[0]['audit']['reasons'])


@pytest.mark.parametrize('raw', ['{', '[]', '{"x":NaN}', '{"x":1,"x":2}', '\udcff'])
def test_invalid_json(tmp_path, raw):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    (folder / 'result.json').write_bytes(raw.encode('utf-8', errors='surrogateescape'))
    manifest = build_dataset(source, output)
    assert manifest['artifact_counts']['invalid:result.json'] == 1
    assert not rows(output)[0]['audit']['eligible']


@pytest.mark.parametrize('status', ['REVISAR', 'ERROR', None])
def test_source_temporal_status(tmp_path, status):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'result.json', {'integridad_temporal': {'estado': status}})
    build_dataset(source, output)
    assert not rows(output)[0]['audit']['eligible']


@pytest.mark.parametrize('field,value', [('match_id', 'a'), ('fecha', '24.10.26'), ('fecha', '25.10.26'), ('fecha', 'invalid'), ('fecha', None)])
def test_sample_temporal_checks(tmp_path, field, value):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    history = json.loads((folder / 'history.json').read_text())
    history['secciones'][0]['partidos'][0][field] = value
    put(folder, 'history.json', history)
    build_dataset(source, output)
    assert not rows(output)[0]['audit']['eligible']


@pytest.mark.parametrize('inconsistent', [False, True])
def test_labels(tmp_path, inconsistent):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    settlement = dict(status='FINISHED', score_scope='REGULATION', home_goals=2, away_goals=1)
    if inconsistent:
        settlement['label_btts'] = False
    put(folder, 'result.json', dict(settlement=settlement))
    build_dataset(source, output)
    row = rows(output)[0]
    if inconsistent:
        assert row['labels'] is None
        assert not row['audit']['eligible']
    else:
        assert row['labels']['total_goals'] == 3
        assert row['labels']['label_btts'] is True
        assert row['labels']['label_1x2'] == '1'
        assert row['labels']['settled_at'] is None


@pytest.mark.parametrize('settlement', [dict(home_goals=2, away_goals=1),
    dict(status='LIVE', score_scope='REGULATION', home_goals=2, away_goals=1),
    dict(status='FINISHED', score_scope='EXTRA_TIME', home_goals=2, away_goals=1)])
def test_unsettled_labels_absent(tmp_path, settlement):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'result.json', dict(settlement=settlement))
    build_dataset(source, output)
    assert rows(output)[0]['labels'] is None


@pytest.mark.parametrize('fields', [dict(p_home=1.1), dict(lambda_home=-1),
    dict(lambda_home=1, lambda_away=1, lambda_total=3),
    dict(p_home=.5, p_draw=.5, p_away=.5)])
def test_invalid_champion(tmp_path, fields):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'champion_snapshot.json', dict(model='J_BT_sin_temporada', **fields))
    build_dataset(source, output)
    row = rows(output)[0]
    assert row['predictions'] is None
    assert not row['audit']['eligible']


def test_champion_attribution(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'lambda_comparison.json', dict(metodos={
        'J_hibrido_experimental': dict(local=9),
        'J_BT_sin_temporada': dict(local=1, visitante=2, total=3)}))
    build_dataset(source, output)
    prediction = rows(output)[0]['predictions']
    assert prediction['lambda_home'] == 1
    assert prediction['p_home'] is None
    assert prediction['model'] == 'J_BT_sin_temporada'


def test_deterministic_order_reproducible_and_read_only(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source, 'z')
    write(source, 'a')
    write(source, 'missing', partido={})
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in source.rglob('*') if p.is_file()}
    first = build_dataset(source, output)
    content = (output / 'dataset_v3.jsonl').read_bytes()
    csv = (output / 'dataset_v3.csv').read_bytes()
    second = build_dataset(source, output)
    assert first['jsonl_sha256'] == second['jsonl_sha256'] == hashlib.sha256(content).hexdigest()
    assert content == (output / 'dataset_v3.jsonl').read_bytes()
    assert csv == (output / 'dataset_v3.csv').read_bytes()
    first.pop('built_at'); second.pop('built_at')
    assert first == second
    assert [r['metadata']['match_id'] for r in rows(output)] == ['a', 'z', 'missing']
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in source.rglob('*') if p.is_file()}
    assert set(tmp_path.iterdir()) == {source, output}
    assert len(list(output.iterdir())) == 3


def test_output_source_overlap_and_symlink_rejected(tmp_path):
    source = tmp_path / 'sources'
    write(source)
    for output in (source, source / 'derived', tmp_path):
        with pytest.raises(ValueError):
            build_dataset(source, output)
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'dataset_v3.jsonl').symlink_to(source / 'a' / 'history.json')
    with pytest.raises(ValueError):
        build_dataset(source, out)


def test_limit_and_empty(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source, 'b'); write(source, 'a')
    assert build_dataset(source, output, limit=1)['rows_emitted'] == 1
    assert rows(output)[0]['metadata']['match_id'] == 'a'
    with pytest.raises(ValueError):
        build_dataset(source, output, limit=0)
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert build_dataset(empty, output)['rows_emitted'] == 0


def test_unknown_champion_never_selected(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'champion_snapshot.json', dict(model='Other', p_home=.8))
    put(folder, 'lambda_comparison.json', dict(metodos={'Other': dict(local=2)}))
    build_dataset(source, output)
    assert rows(output)[0]['predictions'] is None


def test_nonfinite_lambda_reported(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    (folder / 'champion_snapshot.json').write_text(
        '{"model":"J_BT_sin_temporada","lambda_home":1e309}')
    build_dataset(source, output)
    row = rows(output)[0]
    assert row['predictions'] is None
    assert 'invalid_prediction:lambda_home' in row['audit']['reasons']


def test_output_hardlink_cannot_modify_source(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    original = (folder / 'history.json').read_bytes()
    output.mkdir()
    (output / 'dataset_v3.jsonl').hardlink_to(folder / 'history.json')
    with pytest.raises(ValueError):
        build_dataset(source, output)
    assert (folder / 'history.json').read_bytes() == original


def test_no_label_leakage(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    build_dataset(source, output)
    before = rows(output)[0]['inputs']
    put(folder, 'result.json', dict(settlement=dict(status='FINISHED',
        score_scope='REGULATION', home_goals=20, away_goals=10)))
    build_dataset(source, output)
    assert rows(output)[0]['inputs'] == before


@pytest.mark.parametrize('availability', [None, '2026-10-25T00:00:00Z'])
def test_raw_history_uses_sample_dates(tmp_path, availability):
    folder, row = run(tmp_path, available_at=availability)
    assert row['audit']['eligible']
    evidence = [p for p in row['audit']['provenance'] if p['group'] == 'inputs']
    assert len(evidence) == 2
    assert all(p['source'] == 'flashscore:historical_sample_date' and
               '.date:2026-10-19' in p['field'] and p['available_at'] is None for p in evidence)
    history = json.loads((folder / 'history.json').read_text())
    history.pop('available_at')
    put(folder, 'history.json', history)
    build_dataset(folder.parent, tmp_path / 'output')
    rebuilt = rows(tmp_path / 'output')[0]
    assert rebuilt['audit']['eligible']
    assert rebuilt['inputs'] == row['inputs']


def pool_entry(**changes):
    entry = dict(match_id='a', local='Home', visitante='Away', goles_local=2, goles_visitante=1)
    entry.update(changes)
    return entry


def test_pool_labels_and_no_leakage(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source, available_at=None)
    build_dataset(source, output)
    before = rows(output)[0]
    pool = tmp_path / 'backtest_pool.json'
    put(tmp_path, pool.name, dict(partidos=[pool_entry()]))
    original = pool.read_bytes(), pool.stat().st_mtime_ns
    manifest = build_dataset(source, output)
    row = rows(output)[0]
    assert row['inputs'] == before['inputs']
    assert row['metadata'] == before['metadata']
    assert row['audit']['eligible'] == before['audit']['eligible']
    assert row['labels'] == dict(settled_at=None, home_goals=2, away_goals=1,
        total_goals=3, label_btts=True, label_1x2='1', label_over_1_5=True,
        label_over_2_5=True, label_over_3_5=False, label_over_4_5=False)
    assert manifest['labels_from_backtest_pool'] == 1
    assert any(p['artifact'] == pool.name for p in row['audit']['provenance'])
    assert original == (pool.read_bytes(), pool.stat().st_mtime_ns)
    first = (output / 'dataset_v3.jsonl').read_bytes()
    assert build_dataset(source, output)['jsonl_sha256'] == manifest['jsonl_sha256']
    assert first == (output / 'dataset_v3.jsonl').read_bytes()


@pytest.mark.parametrize('change', [dict(local='Wrong'), dict(visitante='Wrong'),
    dict(id='other'), dict(goles_local=True), dict(goles_local=-1),
    dict(goles_visitante=1.5), dict(goles_local=None)])
def test_pool_invalid_identity_or_score(tmp_path, change):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source)
    put(tmp_path, 'pool.json', dict(partidos=[pool_entry(**change)]))
    build_dataset(source, output, backtest_pool=tmp_path / 'pool.json')
    row = rows(output)[0]
    assert row['labels'] is None
    assert row['audit']['temporal_status'] == 'ERROR'
    assert not row['audit']['eligible']


@pytest.mark.parametrize('conflict', [False, True])
def test_pool_settlement_conflict(tmp_path, conflict):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    put(folder, 'result.json', dict(settlement=dict(status='FINISHED', score_scope='REGULATION',
        home_goals=0 if conflict else 2, away_goals=1)))
    put(tmp_path, 'backtest_pool.json', dict(partidos=[pool_entry()]))
    build_dataset(source, output)
    row = rows(output)[0]
    assert row['audit']['eligible'] is not conflict
    assert (row['labels'] is None) is conflict
    if conflict:
        assert row['audit']['temporal_status'] == 'ERROR'
        assert 'conflicting_labels:settlement:backtest_pool.json' in row['audit']['reasons']


def test_pool_duplicate_conflict_and_exact_lookup(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source)
    pool = tmp_path / 'backtest_pool.json'
    put(tmp_path, pool.name, dict(partidos=[pool_entry(match_id='A')]))
    build_dataset(source, output)
    assert rows(output)[0]['labels'] is None
    put(tmp_path, pool.name, dict(partidos=[pool_entry(), pool_entry(goles_local=3)]))
    build_dataset(source, output)
    assert rows(output)[0]['audit']['temporal_status'] == 'ERROR'
    assert rows(output)[0]['labels'] is None


def test_pool_absent_or_invalid(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    write(source)
    build_dataset(source, output, backtest_pool=tmp_path / 'missing.json')
    assert rows(output)[0]['audit']['eligible']
    assert rows(output)[0]['labels'] is None
    put(tmp_path, 'pool.json', {})
    build_dataset(source, output, backtest_pool=tmp_path / 'pool.json')
    assert not rows(output)[0]['audit']['eligible']
    assert 'invalid_artifact:backtest_pool.json' in rows(output)[0]['audit']['reasons']


@pytest.mark.parametrize('name', ['unknown.json', 'standings.json', 'enriched.json', 'xg_history.json'])
def test_unadapted_json_does_not_contaminate(tmp_path, name):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    build_dataset(source, output)
    before = rows(output)[0]
    put(folder, name, dict(match_id='wrong', partido=dict(local='Wrong', fecha='bad')))
    build_dataset(source, output)
    row = rows(output)[0]
    assert row['metadata'] == before['metadata']
    assert row['inputs'] == before['inputs']
    assert row['audit']['eligible']
    (folder / name).write_text('{')
    build_dataset(source, output)
    assert rows(output)[0]['audit']['eligible']


def test_pool_cannot_authorize_late_history(tmp_path):
    source, output = tmp_path / 'sources', tmp_path / 'out'
    folder = write(source)
    history = json.loads((folder / 'history.json').read_text())
    history['secciones'][0]['partidos'][0]['fecha'] = '24.10.26'
    put(folder, 'history.json', history)
    put(tmp_path, 'backtest_pool.json', dict(partidos=[pool_entry()]))
    build_dataset(source, output)
    row = rows(output)[0]
    assert row['labels'] is not None
    assert not row['audit']['eligible']
