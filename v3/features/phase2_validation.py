"""Read-only Phase 2 regression reproduction; outputs must be outside data.

python -m v3.features.phase2_validation --output-dir /tmp/phase2-reproduce
No pytest invocation or report modification; test evidence is in checkpoints.
"""
import argparse
import hashlib
import json
from pathlib import Path

from v3.data.builder import dumps


def fingerprint(root):
    """Content and mtime fingerprints, ignoring only Python cache artifacts."""
    root = Path(root)
    content, mtimes = hashlib.sha256(), hashlib.sha256()
    count = 0
    for path in sorted(root.rglob('*')):
        if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        content.update(dumps([relative, sha]).encode() + b'\n')
        mtimes.update(dumps([relative, path.stat().st_mtime_ns]).encode() + b'\n')
        count += 1
    return dict(files=count, content_sha256=content.hexdigest(), mtime_sha256=mtimes.hexdigest())


def reproduce(source_root, output_dir, expected):
    from v3.features.engine import build_features as form
    from v3.features.xg_engine import build_features as xg
    from v3.features.temporal_context import build_features as temporal
    from v3.features.h2h import build_features as h2h
    root, output = Path(source_root), Path(output_dir)
    # Also reject ancestor output roots and symlinked paths that overlap sources.
    if output.resolve().is_relative_to(root.resolve()) or root.resolve().is_relative_to(output.resolve()):
        raise ValueError('output must not overlap source tree')
    before = fingerprint(root)
    hashes = {}
    for name, builder, source in (('form', form, root/'matches'), ('xg', xg, root),
                                   ('temporal', temporal, root/'matches'), ('h2h', h2h, root/'matches')):
        builder(source, output/name)
        for path in sorted((output/name).glob('*.json*')):
            if path.name not in expected:
                continue
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if hashes != expected:
        raise ValueError('regression hashes differ from frozen Phase 2 report')
    if fingerprint(root) != before:
        raise ValueError('source fingerprint changed during reproduction')
    return dict(regression_hashes=hashes, source_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--report', default='docs/v3/phase-2-validation-report.json')
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    print(dumps(reproduce(args.source_root, args.output_dir, report['regression_hashes'])))


if __name__ == '__main__':
    main()
