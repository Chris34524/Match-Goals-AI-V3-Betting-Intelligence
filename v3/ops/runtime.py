"""Secret-safe, runtime-only durable documents and exclusive tick locks."""
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path


ROOT = Path('v3_data/ops')

def ensure_safe(value):
    secret = os.environ.get('THE_ODDS_API_KEY')
    content = json.dumps(value, sort_keys=True, allow_nan=False)
    if secret and secret in content:
        raise ValueError('secret_serialization_forbidden')
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if str(key).casefold() in {'apikey','api_key','the_odds_api_key','authorization'}:
                    raise ValueError('credential_field_forbidden')
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item: visit(child)
    visit(value)



def safe_path(path):
    path = Path(path)
    resolved = path.resolve()
    if not resolved.is_relative_to(Path('v3_data').resolve()):
        raise ValueError('runtime_outside_v3_data')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('unsafe_runtime_path')
    if path.exists() and path.stat().st_nlink != 1:
        raise ValueError('unsafe_runtime_path')
    return path


def read(path, default=None):
    path = safe_path(path)
    value = json.loads(path.read_text()) if path.exists() else default
    ensure_safe(value)
    return value


def write(path, value):
    path = safe_path(path)
    ensure_safe(value)
    content = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n'
    secret = os.environ.get('THE_ODDS_API_KEY')
    if secret and secret in content:
        raise ValueError('secret_serialization_forbidden')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = safe_path(path.with_suffix(path.suffix + '.tmp'))
    with temporary.open('w') as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)
    return value


@contextmanager
def locked(name):
    path = safe_path(ROOT / (name + '.lock'))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield
