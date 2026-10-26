import hashlib
import json
import os
from pathlib import Path

import pytest

from test_dataset_builder import write
from v3.data.builder import build_dataset
from v3.data import snapshot as s


@pytest.fixture
def inputs(tmp_path):
    write(tmp_path / 'source')
    out = tmp_path / 'derived'
    build_dataset(tmp_path / 'source', out)
    return out / s.FILES[0], out / s.FILES[1], tmp_path / 'snapshots'


def create(inputs):
    result = s.create_snapshot(*inputs)
    return result, inputs[2] / result['snapshot_id']


def state(paths):
    return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}


def test_valid_idempotent_and_sources_untouched(inputs):
    before = state(inputs[:2])
    result, folder = create(inputs)
    frozen = state(folder.iterdir())
    assert s.verify_snapshot(folder) == result
    assert s.create_snapshot(*inputs) == result
    assert state(folder.iterdir()) == frozen
    assert state(inputs[:2]) == before
    assert list(inputs[2].iterdir()) == [folder]
    assert result['total_rows'] == result['eligible_rows'] == 1
    assert result['rows_with_labels'] == 0
    assert result['dataset_sha256'] == hashlib.sha256(inputs[0].read_bytes()).hexdigest()
    assert str(inputs[0].parent.parent) not in (folder / 'snapshot_manifest.json').read_text()
    # Independent roots preserve identity and canonical frozen bytes.
    other, other_folder = create((*inputs[:2], inputs[2].with_name('other')))
    assert other['snapshot_id'] == result['snapshot_id']
    assert other['files'] == result['files']
    for name in s.FILES:
        assert (folder / name).read_bytes() == (other_folder / name).read_bytes()


def test_byte_change_changes_identity(inputs):
    first, _ = create(inputs)
    inputs[0].write_bytes(inputs[0].read_bytes().replace(b'"metadata":', b'"metadata": ', 1))
    manifest = json.loads(inputs[1].read_text())
    manifest['jsonl_sha256'] = s.sha(inputs[0].read_bytes())
    inputs[1].write_bytes(s.encoded(manifest))
    second, _ = create(inputs)
    assert second['snapshot_id'] != first['snapshot_id']


@pytest.mark.parametrize('name', [*s.FILES, 'snapshot_manifest.json'])
def test_tamper_and_conflict_never_overwrite(inputs, name):
    _, folder = create(inputs)
    path = folder / name
    path.write_bytes(path.read_bytes() + b' ')
    before = state(folder.iterdir())
    with pytest.raises(ValueError):
        s.verify_snapshot(folder)
    with pytest.raises(ValueError):
        s.create_snapshot(*inputs)
    assert state(folder.iterdir()) == before


@pytest.mark.parametrize('failure', ['duplicate', 'structure', 'manifest'])
def test_quality_gates(inputs, failure):
    if failure == 'duplicate':
        inputs[0].write_bytes(inputs[0].read_bytes() * 2)
    elif failure == 'structure':
        row = json.loads(inputs[0].read_text())
        row['audit']['eligible'] = 'yes'
        inputs[0].write_bytes(s.encoded(row))
    else:
        inputs[1].write_text('{}')
    with pytest.raises(ValueError):
        s.create_snapshot(*inputs)
    assert list(inputs[2].iterdir()) == []


def test_failure_cleanup(inputs, monkeypatch):
    def fail(*args):
        raise OSError('injected publish failure')
    monkeypatch.setattr(s, 'publish', fail)
    with pytest.raises(OSError):
        s.create_snapshot(*inputs)
    assert list(inputs[2].iterdir()) == []


@pytest.mark.parametrize('hard', [False, True])
@pytest.mark.parametrize('target', ['source', 'frozen', 'root'])
def test_unsafe_links(inputs, tmp_path, hard, target):
    if target == 'root':
        if hard:
            return
        actual = tmp_path / 'actual'
        actual.mkdir()
        inputs[2].symlink_to(actual, target_is_directory=True)
        with pytest.raises(ValueError):
            s.create_snapshot(*inputs)
        return
    if target == 'source':
        path = inputs[0]
    else:
        _, folder = create(inputs)
        path = folder / s.FILES[0]
    saved = tmp_path / 'saved'
    path.rename(saved)
    if hard:
        os.link(saved, path)
    else:
        path.symlink_to(saved)
    with pytest.raises(ValueError):
        s.create_snapshot(*inputs) if target == 'source' else s.verify_snapshot(folder)


def test_overlap_rejected(inputs):
    with pytest.raises(ValueError):
        s.create_snapshot(*inputs[:2], inputs[0].parent / 'snapshots')


def test_empty_destination_is_not_replaced(inputs):
    result, folder = create(inputs)
    for path in folder.iterdir():
        path.unlink()
    with pytest.raises(ValueError):
        s.create_snapshot(*inputs)
    assert list(folder.iterdir()) == []


def test_concurrent_creation(inputs):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: s.create_snapshot(*inputs), range(2)))
    assert results[0] == results[1]
    assert len(list(inputs[2].iterdir())) == 1


def test_report_recomputed_even_if_hashes_are_rewritten(inputs):
    result, folder = create(inputs)
    report = json.loads((folder / s.FILES[2]).read_text())
    report['total_rows'] += 1
    (folder / s.FILES[2]).write_bytes(s.encoded(report))
    result['files'][s.FILES[2]] = s.sha((folder / s.FILES[2]).read_bytes())
    (folder / 'snapshot_manifest.json').write_bytes(s.encoded(result))
    with pytest.raises(ValueError, match='quality report'):
        s.verify_snapshot(folder)
