import json
import subprocess
import sys

import pytest

from test_dataset_builder import write, put, pool_entry
from v3.data.builder import normalize, build_dataset
from v3.data.quality import quality_report, structural_errors
from v3.data.temporal import sample_reasons, eligible_status


@pytest.mark.parametrize('sample_id,date,reason,status', [
    ('a', '19.10.26', 'target_in_input', 'ERROR'),
    ('other', '25.10.26', 'future_input', 'ERROR'),
    ('other', '24.10.26', 'same_day_input_without_verified_time', 'ERROR'),
    ('other', None, 'unknown_input_date', 'REVIEW'),
])
@pytest.mark.parametrize('section', [0, 1, 2])
def test_temporal_policy_in_all_history_sections(tmp_path, sample_id, date, reason, status, section):
    folder = write(tmp_path)
    history = json.loads((folder / 'history.json').read_text())
    history['secciones'].append(dict(titulo='ENFRENTAMIENTOS', partidos=[dict(
        match_id='h2h', fecha='19.10.26', local='Home', visitante='Away',
        resultado_parseado=True, goles_local=1, goles_visitante=0)]))
    sample = history['secciones'][section]['partidos'][0]
    sample.update(match_id=sample_id, fecha=date, kickoff='2026-10-24T01:00:00Z')
    put(folder, 'history.json', history)
    row = normalize(folder)[0]
    assert row['audit']['temporal_status'] == status
    assert not row['audit']['eligible']
    assert 'input_temporal:' + reason in row['audit']['reasons']
    assert not any('.sample:' + sample_id + '.date:' in p['field'] for p in row['audit']['provenance'])


def test_target_and_unknown_date_both_reported():
    assert sample_reasons('a', '2026-10-24', 'a', None) == ['target_in_input', 'unknown_input_date']


@pytest.mark.parametrize('status', ['REVIEW', 'ERROR', None, 'UNKNOWN'])
def test_temporal_gate(status, tmp_path):
    assert not eligible_status(status)
    folder = write(tmp_path)
    row = normalize(folder)[0]
    row['audit'].update(temporal_status=status, eligible=True)
    assert 'audit:temporal_gate_violation' in structural_errors(row)


def test_pool_and_labels_mutations_preserve_prematch_state(tmp_path):
    folder = write(tmp_path)
    before = normalize(folder)[0]
    for entry in (pool_entry(), pool_entry(goles_local=99, goles_visitante=88)):
        after = normalize(folder, [entry])[0]
        assert after['labels'] != before['labels']
        for key in ('metadata', 'inputs'):
            assert after[key] == before[key]
        for key in ('eligible', 'temporal_status', 'reasons', 'feature_cutoff', 'quality_flags'):
            assert after['audit'][key] == before['audit'][key]
    put(folder, 'result.json', dict(settlement=dict(status='FINISHED', score_scope='REGULATION',
        home_goals=100, away_goals=100)))
    after = normalize(folder)[0]
    assert after['inputs'] == before['inputs']
    assert after['metadata'] == before['metadata']
    assert after['audit']['eligible'] == before['audit']['eligible']


@pytest.mark.parametrize('artifact', ['champion_snapshot.json', 'lambda_comparison.json'])
def test_predictions_cannot_supply_metadata_or_features(tmp_path, artifact):
    folder = write(tmp_path)
    before = normalize(folder)[0]
    for number in (1, 9):
        put(folder, artifact, dict(model='J_BT_sin_temporada', lambda_home=number,
            metodos={'J_BT_sin_temporada': dict(local=number)}, match_id='poison',
            partido=dict(local='Poison', fecha='2099-01-01', pais='Poison'),
            inputs={'home': {'history_count': 999}}))
        after = normalize(folder)[0]
        assert after['inputs'] == before['inputs']
        assert after['metadata'] == before['metadata']
        assert after['audit']['eligible'] == before['audit']['eligible']
        assert after['predictions']['lambda_home'] == number


@pytest.mark.parametrize('field,value', [('id', 'wrong'), ('local', 'wrong'), ('fecha', '2026-10-23')])
def test_identity_contradictions_block(tmp_path, field, value):
    folder = write(tmp_path)
    put(folder, 'result.json', {'partido': {field: value}})
    row = normalize(folder)[0]
    assert row['audit']['temporal_status'] == 'ERROR'
    assert not row['audit']['eligible']
    assert any(r.startswith('identity_conflict:') for r in row['audit']['reasons'])


def test_report_counts_and_order(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'out'
    write(source, 'b')
    folder = write(source)
    put(folder, 'champion_snapshot.json', {'model': 'J_BT_sin_temporada', 'lambda_home': 1})
    put(folder, 'result.json', {'integridad_temporal': {'estado': 'REVIEW'}})
    put(tmp_path, 'backtest_pool.json', {'partidos': [pool_entry()]})
    build_dataset(source, output)
    path = output / 'dataset_v3.jsonl'
    report = quality_report(path)
    assert report['total_rows'] == 2
    assert report['eligible_rows'] == report['ineligible_rows'] == 1
    assert report['temporal_status'] == {'OK': 1, 'REVIEW': 1}
    assert report['rows_with_labels'] == report['rows_with_champion_predictions'] == 1
    assert report['history_count'] == {'home': {'1': 2}, 'away': {'1': 2}}
    assert report['top_reasons'] == [{'reason': 'source_temporal_status:REVIEW', 'rows': 1}]
    assert report['duplicate_match_ids'] == report['structural_inconsistencies'] == {}
    assert report['manifest'] == {'present': True, 'mismatches': {}}
    assert quality_report(path) == report
    lines = path.read_text().splitlines()
    other = tmp_path / 'reverse.jsonl'
    other.write_text('\n'.join(reversed(lines)) + '\n')
    reversed_report = quality_report(other)
    for key in report.keys() - {'jsonl_sha256', 'manifest'}:
        assert report[key] == reversed_report[key]


def test_empty_report(tmp_path):
    path = tmp_path / 'empty.jsonl'
    path.write_text('')
    report = quality_report(path)
    assert report['total_rows'] == report['eligible_rows'] == report['ineligible_rows'] == 0
    assert report['top_reasons'] == []
    assert report['history_count'] == {'home': {}, 'away': {}}


@pytest.mark.parametrize('invalid', ['{', '[]', '{"x":NaN}', '{"x":1,"x":2}', '', '{"x":1e999}'])
def test_invalid_jsonl_fails_without_partial_report(tmp_path, invalid):
    path = tmp_path / 'broken.jsonl'
    path.write_text('{}\n' + invalid + '\n')
    result = subprocess.run([sys.executable, '-m', 'v3.data.quality', '--dataset', str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ''
    assert 'line 2' in result.stderr


def test_duplicate_and_manifest_mismatch_fail_cli(tmp_path):
    folder = write(tmp_path / 'source')
    row = normalize(folder)[0]
    path = tmp_path / 'dataset.jsonl'
    path.write_text((json.dumps(row) + '\n') * 2)
    put(tmp_path, 'dataset_manifest.json', {'rows_emitted': 1})
    report = quality_report(path)
    assert report['duplicate_match_ids'] == {'a': 2}
    assert report['manifest']['mismatches']['rows_emitted'] == {'expected': 1, 'actual': 2}
    result = subprocess.run([sys.executable, '-m', 'v3.data.quality', '--dataset', str(path)], capture_output=True)
    assert result.returncode == 1


@pytest.mark.parametrize('mutation,expected', [
    (lambda r: r['inputs']['home'].update(history_count=-1), 'inputs.home.history_count:invalid_count'),
    (lambda r: r['audit'].update(reasons=['z', 'a']), 'audit.reasons:noncanonical_order'),
    (lambda r: r['inputs'].update(labels={}), 'inputs:keys'),
    (lambda r: r['audit']['provenance'][3].update(artifact='backtest_pool.json'), 'provenance:isolated_artifact_in_features'),
])
def test_structural_inconsistencies(tmp_path, mutation, expected):
    row = normalize(write(tmp_path))[0]
    # Select an input evidence record independent of metadata provenance length.
    row['audit']['provenance'] = [p for p in row['audit']['provenance'] if p['group'] != 'inputs'][:3] + [next(p for p in row['audit']['provenance'] if p['group'] == 'inputs')]
    mutation(row)
    assert expected in structural_errors(row)


def test_report_tied_reasons_sort_by_name(tmp_path):
    row = normalize(write(tmp_path / 'source'))[0]
    row['audit'].update(eligible=False, temporal_status='REVIEW', reasons=['a', 'z'])
    path = tmp_path / 'tie.jsonl'
    path.write_text(json.dumps(row) + '\n')
    assert quality_report(path)['top_reasons'] == [
        {'reason': 'a', 'rows': 1}, {'reason': 'z', 'rows': 1}]


def test_report_invalid_encoding_is_explicit(tmp_path):
    path = tmp_path / 'invalid.jsonl'
    path.write_bytes(b'{}\n\xff\n')
    result = subprocess.run([sys.executable, '-m', 'v3.data.quality', '--dataset', str(path)], capture_output=True)
    assert result.returncode == 2
    assert not result.stdout
    assert result.stderr


def test_malformed_structures_are_reported(tmp_path):
    path = tmp_path / 'malformed.jsonl'
    path.write_text(json.dumps({'metadata': [], 'inputs': None, 'audit': 'bad'}) + '\n')
    report = quality_report(path)
    assert report['total_rows'] == 1
    assert report['structural_inconsistencies']['metadata:expected_object'] == 1
