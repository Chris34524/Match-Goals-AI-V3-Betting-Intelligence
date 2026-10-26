"""Content-addressed immutable bundles, published atomically without overwrite."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .contract import canonical_json

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / 'v3_data/odds'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return canonical_json(value).encode()


def jsonl(records):
    return ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')) + '\n' for r in records).encode()


def safe_root(root):
    root = Path(root).resolve()
    # Production writes stay in the dedicated V3 area. /tmp permits isolated tests.
    if not (root.is_relative_to(DEFAULT_ROOT) or root.is_relative_to(Path('/tmp'))):
        raise ValueError('output_outside_v3_odds')
    return root


def publish(root, run_id, files):
    import re
    if not re.fullmatch('[a-f0-9]{64}', run_id):
        raise ValueError('invalid_run_id')
    if any(Path(k).is_absolute() or '..' in Path(k).parts for k in files):
        raise ValueError('invalid_artifact_path')
    from .the_odds_api import assert_safe_payload
    assert_safe_payload({k: v.decode('utf-8') for k, v in files.items()})
    root = safe_root(root)
    root.mkdir(parents=True, exist_ok=True)
    final = root / run_id
    if final.is_symlink():
        raise ValueError('symlink_run_forbidden')
    if final.exists():
        actual = {str(p.relative_to(final)): p.read_bytes() for p in final.rglob('*') if p.is_file()}
        if actual != files:
            raise ValueError('immutable_run_conflict')
        return final
    with tempfile.TemporaryDirectory(prefix='.pending-', dir=root) as tmp:
        stage = Path(tmp) / 'bundle'
        stage.mkdir()
        for name, content in files.items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        # Serialize publication; a concurrent identical publisher may safely dedupe.
        import fcntl
        with (root / '.publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if final.exists():
                actual = {str(p.relative_to(final)): p.read_bytes() for p in final.rglob('*') if p.is_file()}
                if actual != files:
                    raise ValueError('immutable_run_conflict')
                return final
            os.rename(stage, final)
    return final


def store_run(raw, records, manifest, root=DEFAULT_ROOT):
    source = encoded(raw)
    canonical = jsonl(records)
    identity = {'config': manifest['config'], 'observed_at': manifest['observed_at'],
                'source_sha256': digest(source)}
    run_id = digest(encoded(identity))
    manifest = {**manifest, 'run_id': run_id, 'source_sha256': digest(source),
                'canonical_sha256': digest(canonical), 'record_count': len(records)}
    return publish(root, run_id, {'raw/response.json': source, 'canonical.jsonl': canonical,
                                  'manifest.json': encoded(manifest)})
