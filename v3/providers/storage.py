"""Atomic JSON confined to the provider runtime root, or /tmp for review/tests."""
import os
from pathlib import Path
import tempfile
from v3.flashscore.contract import dumps

ROOT = Path('v3_data/providers')


def checked_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink_artifact_path')
    if not any(path.resolve().is_relative_to(root) for root in (ROOT.resolve(), Path('/tmp'))):
        raise ValueError('outside_provider_artifact_root')
    return path


def atomic_json(path, value):
    path = checked_path(path)
    content = dumps(value) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.provider-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
