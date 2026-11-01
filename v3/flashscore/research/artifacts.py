"""Atomic artifacts confined to the research runtime root (or /tmp test roots)."""
import os
from pathlib import Path
import tempfile
from ..contract import dumps
from .training import verify

ROOT = Path('v3_data/flashscore_research')


def atomic_json(path, value):
    path = Path(path)
    allowed = (ROOT.resolve(), Path('/tmp').resolve())
    if not any(path.resolve().is_relative_to(root) for root in allowed):
        raise ValueError('outside_research_artifact_root')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink_artifact_path')
    content = dumps(value) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.research-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_experiment(experiment, root=ROOT):
    verify(experiment)
    root = Path(root)
    identity = experiment['artifact_sha256']
    directory = root / 'experiments' / identity
    atomic_json(directory / 'manifest.json', {k:v for k,v in experiment.items()
        if k not in ('predictions','error_ledger','models','effectiveness')})
    atomic_json(directory / 'predictions.json', experiment['predictions'])
    for model in experiment['models']:
        atomic_json(directory / 'models' / (model['artifact_sha256'] + '.json'), model)
    output = root / 'effectiveness' / identity
    report = experiment['effectiveness']
    atomic_json(output / 'aggregate.json', report['by_model'])
    atomic_json(output / 'segments.json', report['segments'])
    atomic_json(output / 'selection.json', dict(rule=report['selection_rule'], decisions=report['selection']))
    atomic_json(output / 'calibration.json', {m:r['metrics']['bins'] for m,r in report['by_model'].items()})
    atomic_json(output / 'error-ledger.json', experiment['error_ledger'])
    return directory
