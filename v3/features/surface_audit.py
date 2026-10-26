"""Discover local artifacts without an allowlist, writes, network or feature extraction.

Run from the repository root: python -m v3.features.surface_audit --source-root data
Redirect stdout outside data/ to retain a report. Scalar values are never exported.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from v3.data.builder import reject_constant, unique_object

RAW_NAMES = {'history.json', 'history_raw.json', 'xg_history.json', 'standings.json',
             'match_detail.txt', 'standings_page.txt', 'match_detail.html', 'standings_page.html',
             'partidos.json', 'partidos_hoy.json', 'partidos_manana.json', 'partidos_candidatos.json'}


def source_role(path):
    """Only known raw candidates; everything else remains inventory-only."""
    parts = Path(path).parts
    return ('candidate_raw_requires_validation' if
            (Path(path).name in RAW_NAMES or (parts[0] == 'xg_cache' and Path(path).suffix == '.json'))
            and not any(p in parts for p in ('experiments', 'evaluation', 'derived', 'snapshots', 'test_matches'))
            else 'inventory_only')


def _shape(obj, path='$', output=None):
    """Full key-path/type union; arrays use [] and no scalar content is retained."""
    if output is None:
        output = set()
    kind = ('null' if obj is None else 'bool' if isinstance(obj, bool)
            else 'object' if isinstance(obj, dict) else 'array' if isinstance(obj, list)
            else 'string' if isinstance(obj, str) else 'number')
    output.add((path, kind))
    if isinstance(obj, dict):
        for key, value in obj.items():
            # JSON pointer escaping prevents collisions with literal dots/slashes.
            _shape(value, path + '/' + key.replace('~', '~0').replace('/', '~1'), output)
    elif isinstance(obj, list):
        for value in obj:
            _shape(value, path + '/[]', output)
    return output


def audit_surface(source_root='data/matches'):
    """Deterministic exhaustive recursive file inventory; never follow symlinks.

    Coverage is file presence, key presence and non-null types, not usable samples.
    Malformed JSON remains inventoried. No output-path parameter exists by design.
    """
    root = Path(source_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source-root must be a real directory')
    groups = {}
    skipped = []
    digest = hashlib.sha256()
    directories = 0
    files = 0

    def walk(directory):
        nonlocal directories
        for path in sorted(directory.iterdir()):
            if path.is_symlink():
                skipped.append(path.relative_to(root).as_posix())
            elif path.is_dir():
                directories += 1
                yield from walk(path)
            elif path.is_file():
                yield path

    for path in walk(root):
        relative = path.relative_to(root).as_posix()
        # Group match artifacts by relative name, retaining unknown nested artifacts.
        parts = Path(relative).parts
        if root.name == 'matches' and len(parts) > 1:
            group = '<id>/' + '/'.join(parts[1:])
        elif len(parts) > 2 and parts[0] in ('matches', 'test_matches'):
            group = parts[0] + '/<id>/' + '/'.join(parts[2:])
        elif len(parts) == 2 and parts[0] in ('xg_cache', 'day_logs', 'tomorrow_logs', 'backtest_pool_logs'):
            group = parts[0] + '/<id>' + path.suffix
        else:
            group = relative
        item = groups.setdefault(group, {'files': 0, 'bytes': 0, 'valid_json': 0,
            'invalid_json': 0, 'source_role': source_role(relative),
            'top_level_keys': Counter(), 'key_path_types': Counter(),
            'example_path': relative, 'example_structure': None})
        raw = path.read_bytes()
        files += 1
        item['files'] += 1
        item['bytes'] += len(raw)
        digest.update(relative.encode() + b'\0')
        digest.update(hashlib.sha256(raw).digest())
        if path.suffix.lower() != '.json':
            continue
        try:
            obj = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
            shape = sorted(_shape(obj))
        except (ValueError, UnicodeError, RecursionError):
            item['invalid_json'] += 1
            continue
        item['valid_json'] += 1
        if isinstance(obj, dict):
            item['top_level_keys'].update(obj.keys())
        item['key_path_types'].update(p + ':' + t for p, t in shape)
        if item['example_structure'] is None:
            item['example_path'] = relative
            item['example_structure'] = [p + ':' + t for p, t in shape]
    for item in groups.values():
        for key in ('top_level_keys', 'key_path_types'):
            item[key] = dict(sorted(item[key].items()))
    return {'audit_version': '2.1A', 'files': files, 'subdirectories': directories,
            'source_content_sha256': digest.hexdigest(), 'skipped_symlinks': sorted(skipped),
            'artifacts': dict(sorted(groups.items())),
            'limitations': [
                'All regular files are hashed; JSON key paths inspected exhaustively, other formats inventoried only.',
                'Path/type counts are files containing the path/type, not player or match counts.',
                'No scalar contents, articles or commentary copied; examples contain structure only.',
                'Presence/non-null does not establish correctness, coverage, as-of availability or capture rights.',
                'Inventory-only artifacts must never become feature sources; raw candidates need independent validation.',
                'No evidence in inspected JSON does not prove absence from unparsed HTML/text.',
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data/matches')
    args = parser.parse_args()
    print(json.dumps(audit_surface(args.source_root), ensure_ascii=False, sort_keys=True,
                     allow_nan=False, indent=2))


if __name__ == '__main__':
    main()
