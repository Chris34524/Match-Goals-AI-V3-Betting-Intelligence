"""Isolated 2.3 xG output. Run with --source-root data --output-dir /tmp/xg-v3."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from v3.data.builder import dumps, reject_constant, unique_object
from v3.data.temporal import sample_reasons
from v3.data.validation import day
from v3.features.catalog import CATALOG_VERSION
from v3.features.xg_adapter import reconcile

FEATURE_VERSION = '2.3.0'


def materialize(history, xg, cache, target_id, *, attestations=None):
    metadata, sides = reconcile(history, xg, cache, target_id, attestations=attestations)
    features, windows = {}, {}
    for side in ('home', 'away'):
        # Catalogue 2.1 forbids backfill: choose the recent fixture window BEFORE
        # testing xG availability, rather than reaching farther into the past.
        sections = history.get('secciones', [])
        matched = [s for s in sections if isinstance(s, dict)
                   and str(s.get('titulo', '')).casefold() == 'últimos partidos: ' + str(metadata.get(side, '')).casefold()] if isinstance(sections, list) else []
        fixtures = matched[0].get('partidos', []) if len(matched) == 1 else []
        if len(matched) != 1 or not isinstance(fixtures, list):
            sides[side]['reason'] = sides[side]['reason'] or 'missing_or_ambiguous_team_section'
            fixtures = []
        counts = Counter(r.get('match_id') for r in fixtures if isinstance(r, dict) and isinstance(r.get('match_id'), str))
        recent = [r for r in fixtures if isinstance(r, dict) and isinstance(r.get('match_id'), str)
                  and counts[r['match_id']] == 1
                  and not sample_reasons(target_id, metadata.get('date'), r.get('match_id'), r.get('fecha'))
                  and metadata.get(side) in (r.get('local'), r.get('visitante'))]
        recent.sort(key=lambda r: (-day(r['fecha']).toordinal(), r['match_id']))
        for n in (5, 10):
            ids = {r['match_id'] for r in recent[:n]}
            selected = [r for r in sides[side]['samples'] if r['match_id'] in ids]
            count = len(selected) if not sides[side]['reason'] else None
            reason = sides[side]['reason'] or ('insufficient_sample' if len(selected) < n else None)
            key = f'{side}_l{n}'
            windows[key] = dict(sample_count=count, reason=reason, contributing=selected,
                                fixture_match_ids=[r['match_id'] for r in recent[:n]],
                                quality_flags=sorted({q for r in sides[side]['exclusions'] for q in r['reasons']}),
                                bilateral_available=count == n if count is not None else None)
            for metric in ('xg_mean', 'xga_mean', 'xg_sample_count'):
                value = count if metric == 'xg_sample_count' else (
                    sum(r['xgf' if metric == 'xg_mean' else 'xga'] for r in selected) / n if reason is None else None)
                features[f'{side}_{metric}_l{n}'] = dict(value=value, sample_count=count,
                    reason=None if metric == 'xg_sample_count' and count is not None else reason, window=key)
    for n in (5, 10):
        counts = [windows[f'{s}_l{n}']['sample_count'] for s in ('home', 'away')]
        value = all(c == n for c in counts) if all(c is not None for c in counts) else None
        features[f'bilateral_xg_available_l{n}'] = dict(value=value, reason=None if value is not None else 'unknown_bilateral_availability', windows=[f'{s}_l{n}' for s in ('home', 'away')])
    return dict(match_id=target_id, feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                metadata=metadata, features=features, windows=windows,
                exclusions={s: sides[s]['exclusions'] for s in sides})


def load(path, digest, root):
    digest.update(str(path.relative_to(root)).encode() + b'\0')
    try:
        if path.is_symlink():
            raise ValueError('symlink source')
        raw = path.read_bytes()
        digest.update(hashlib.sha256(raw).digest())
        obj = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError, UnicodeError):
        digest.update(b'MISSING_OR_INVALID')
        return {}


def build_features(source_root, output_dir):
    root, output = Path(source_root), Path(output_dir)
    if root.is_symlink() or not root.is_dir() or output.resolve().is_relative_to(root.resolve()):
        raise ValueError('require real source root and output outside source data')
    digest, stats, distributions = hashlib.sha256(), Counter(), {f'{s}_l{n}': Counter() for s in ('home', 'away') for n in (5, 10)}
    cache = {}
    for name in ('history_raw.json', 'match_detail.txt', 'match_detail.html'):
        path = root / name
        if path.is_file():
            load(path, digest, root)
            stats['other_raw_blocked:' + name] += 1
    cache_root = root / 'xg_cache'
    if cache_root.is_symlink() or (root / 'matches').is_symlink():
        raise ValueError('symlink source directory')
    for path in sorted(cache_root.glob('*.json')):
        cache[path.stem] = load(path, digest, root)
        stats['xg_cache_artifacts'] += 1
    rows, seen_cache = [], set()
    for folder in sorted((root / 'matches').iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        history = load(folder / 'history.json', digest, root)
        xg = load(folder / 'xg_history.json', digest, root)
        stats['xg_history_artifacts'] += (folder / 'xg_history.json').is_file()
        row = materialize(history, xg, cache, folder.name)
        rows.append(row)
        stats['targets_inspected'] += 1
        stats['targets_with_valid_xg'] += any(w['contributing'] for w in row['windows'].values())
        for key, window in row['windows'].items():
            distributions[key][str(window['sample_count'])] += 1
            stats['complete:' + key] += window['bilateral_available'] is True
        for n in (5, 10):
            stats[f'bilateral_l{n}'] += row['features'][f'bilateral_xg_available_l{n}']['value'] is True
        history_reconciled = False
        for side in row['exclusions'].values():
            for exclusion in side:
                stats.update('exclusion:' + r for r in exclusion['reasons'])
                if 'unreconciled_history_identity' not in exclusion['reasons']:
                    history_reconciled = True
                    sid = exclusion['match_id']
                    if sid in cache and 'cache_identity_or_value_conflict' not in exclusion['reasons']:
                        seen_cache.add(sid)
        stats['xg_history_reconciled_identity'] += history_reconciled
        # Other raw candidates from 2.1A are inventory-only: no structured,
        # independently accredited xG publication/revision adapter exists.
        for name in ('history_raw.json', 'match_detail.txt', 'match_detail.html'):
            path = folder / name
            if path.is_file():
                load(path, digest, root)
                stats['other_raw_blocked:' + name] += 1
    stats['xg_cache_reconciled_identity'] = len(seen_cache)
    stats['xg_history_blocked_lineage'] = stats['xg_history_artifacts']
    stats['xg_cache_blocked_lineage'] = stats['xg_cache_artifacts']
    content = ''.join(dumps(r) + '\n' for r in rows).encode()
    manifest = dict(feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                    features_per_row=14, stats=dict(sorted(stats.items())),
                    sample_count_distribution={k: dict(sorted(v.items())) for k, v in distributions.items()},
                    venue='not_applicable_no_xg_venue_features_in_catalog_2.1',
                    source_sha256=digest.hexdigest(), jsonl_sha256=hashlib.sha256(content).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / 'xg_features.jsonl', output / 'xg_manifest.json']
    if any(p.is_symlink() for p in paths):
        raise ValueError('symlink output')
    paths[0].write_bytes(content)
    paths[1].write_text(dumps(manifest) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(dumps(build_features(args.source_root, args.output_dir)))


if __name__ == '__main__':
    main()
