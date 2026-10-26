"""Content-addressed, atomic V3 snapshots (local filesystems on Linux)."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from v3.data.builder import dumps, reject_constant, unique_object
from v3.data.quality import quality_report, finite_float

FILES = ('dataset_v3.jsonl', 'dataset_v3_manifest.json', 'quality_report.json')
FORMAT = '1.0.0'
COUNTS = ('total_rows', 'eligible_rows', 'ineligible_rows', 'rows_with_labels')


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise ValueError('symlink path rejected: ' + str(part))
    return path


def read_safe(path):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError('expected regular file without hardlinks: ' + str(path))
        content = stream.read()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('file changed while reading')
        return content


def parse(content):
    return json.loads(content, parse_float=finite_float, parse_constant=reject_constant,
                      object_pairs_hook=unique_object)


def encoded(value):
    return (dumps(value) + '\n').encode('utf-8')


def sha(content):
    return hashlib.sha256(content).hexdigest()


def identity(hashes):
    return 'v3-' + sha(encoded(dict(snapshot_version=FORMAT, files=hashes)))


def checked_report(folder):
    report = quality_report(folder / FILES[0], folder / FILES[1])
    if (not report['manifest']['present'] or report['manifest']['mismatches'] or
            report['duplicate_match_ids'] or report['structural_inconsistencies']):
        raise ValueError('snapshot quality gates failed')
    return report


def core(contents, report):
    manifest = parse(contents[FILES[1]])
    if not isinstance(manifest, dict):
        raise ValueError('dataset manifest must be an object')
    if any(manifest.get(k) != '3.0.0' for k in ('schema_version', 'feature_version')):
        raise ValueError('unsupported dataset version')
    hashes = {name: sha(contents[name]) for name in FILES}
    return dict(snapshot_id=identity(hashes), snapshot_version=FORMAT,
                schema_version=manifest['schema_version'], feature_version=manifest['feature_version'],
                builder_version=manifest.get('builder_version'), dataset_sha256=hashes[FILES[0]],
                files=hashes, **{key: report[key] for key in COUNTS})


def verify_snapshot(folder, *, check_name=True):
    folder = safe_path(folder)
    if not folder.is_dir() or set(p.name for p in folder.iterdir()) != set(FILES) | {'snapshot_manifest.json'}:
        raise ValueError('unexpected snapshot directory contents')
    contents = {name: read_safe(folder / name) for name in FILES}
    raw = read_safe(folder / 'snapshot_manifest.json')
    manifest = parse(raw)
    if not isinstance(manifest, dict):
        raise ValueError('snapshot manifest must be an object')
    report = checked_report(folder)
    if encoded(report) != contents[FILES[2]]:
        raise ValueError('quality report differs from frozen dataset')
    expected = core(contents, report)
    created = manifest.get('created_at')
    if not isinstance(created, str) or datetime.fromisoformat(created).tzinfo is None:
        raise ValueError('invalid creation timestamp')
    expected['created_at'] = created
    if manifest != expected or raw != encoded(expected):
        raise ValueError('snapshot integrity mismatch')
    if check_name and folder.name != expected['snapshot_id']:
        raise ValueError('snapshot directory identity mismatch')
    return manifest


def publish(source, destination):
    # RENAME_NOREPLACE prevents even an empty conflicting directory from being replaced.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def create_snapshot(dataset, manifest, output_root):
    dataset, manifest, root = map(safe_path, (dataset, manifest, output_root))
    for source in (dataset, manifest):
        if root == source.parent or source.parent in root.parents or root == source or root in source.parents:
            raise ValueError('snapshot output overlaps source directory')
    contents = {FILES[0]: read_safe(dataset), FILES[1]: read_safe(manifest)}
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.snapshot-', dir=root))
    try:
        for name, content in contents.items():
            (temporary / name).write_bytes(content)
        report = checked_report(temporary)
        contents[FILES[2]] = encoded(report)
        (temporary / FILES[2]).write_bytes(contents[FILES[2]])
        result = core(contents, report)
        result['created_at'] = datetime.now(timezone.utc).isoformat()
        (temporary / 'snapshot_manifest.json').write_bytes(encoded(result))
        verify_snapshot(temporary, check_name=False)
        # Reject changes/replacements of sources during the operation as well.
        if read_safe(dataset) != contents[FILES[0]] or read_safe(manifest) != contents[FILES[1]]:
            raise ValueError('source changed during snapshot creation')
        destination = root / result['snapshot_id']
        try:
            publish(temporary, destination)
        except FileExistsError:
            existing = verify_snapshot(destination)
            if any(read_safe(destination / name) != contents[name] for name in FILES):
                raise ValueError('conflicting existing snapshot')
            return existing
        return result
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--dataset', required=True)
    create.add_argument('--manifest', required=True)
    create.add_argument('--output-root', required=True)
    commands.add_parser('verify').add_argument('snapshot')
    args = parser.parse_args()
    try:
        result = (create_snapshot(args.dataset, args.manifest, args.output_root)
                  if args.command == 'create' else verify_snapshot(args.snapshot))
    except (OSError, ValueError, UnicodeError, AttributeError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(dumps(result))


if __name__ == '__main__':
    main()
