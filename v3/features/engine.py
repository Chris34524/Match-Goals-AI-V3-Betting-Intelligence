"""Deterministic P0 form materialization, isolated from the canonical dataset.

python -m v3.features.engine --source-root data/matches --output-dir /tmp/form-v3
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from v3.data.builder import dumps
from v3.features.catalog import CATALOG, CATALOG_VERSION, MARKETS
from v3.features.history_adapter import read_history, target_metadata, team_history

FEATURE_VERSION = '2.2.0'
SPECS = tuple(f for f in CATALOG if f.group in ('recent_form', 'venue_form', 'sample_quality'))


def materialize(history, target_id, source_error=None):
    metadata, error = target_metadata(history, target_id)
    error = source_error or error
    windows, exclusions, features = {}, {}, {}
    for side in ('home', 'away'):
        valid, rejected, section_error = team_history(history, target_id, metadata, side) if not error else ([], [], error)
        exclusions[side] = rejected
        for venue in (False, True):
            candidates = [s for s in valid if not venue or s['venue'] == side]
            for n in (5, 10):
                key = f'{side}_{"venue_" if venue else ""}l{n}'
                selected = candidates[:n]
                windows[key] = dict(sample_count=len(selected) if not section_error else None,
                                    reason=section_error or ('insufficient_sample' if len(selected) < n else None),
                                    contributing=selected)
    for spec in SPECS:
        n = 10 if spec.name.endswith('l10') else 5
        venue = '_venue_' in spec.name
        key = f'{spec.side}_{"venue_" if venue else ""}l{n}'
        window = windows[key]
        metric = spec.name[len(spec.side) + (7 if venue else 1):].rsplit('_l', 1)[0]
        count, reason = window['sample_count'], window['reason']
        value = None
        if metric == 'sample_count':
            value = count
            reason = None if count is not None else reason
        elif reason is None:
            samples = window['contributing']
            values = {
                'gf_mean': lambda s: s['gf'], 'ga_mean': lambda s: s['ga'],
                'btts_rate': lambda s: s['gf'] > 0 and s['ga'] > 0,
                'clean_sheet_rate': lambda s: s['ga'] == 0,
                'failed_to_score_rate': lambda s: s['gf'] == 0,
                **{f'over_{k}_5_rate': lambda s, k=k: s['gf'] + s['ga'] > k + .5 for k in (1, 2, 3)},
            }
            value = sum(values[metric](s) for s in samples) / n
        features[spec.name] = dict(value=value, sample_count=count, reason=reason, window=key)
    return dict(match_id=target_id, feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                metadata=metadata, source='history.json', features=features,
                windows=windows, exclusions=exclusions)


def coverage(rows):
    counts = Counter()
    for row in rows:
        for key, window in row['windows'].items():
            counts['windows:' + key] += window['reason'] is None
        for family in ('recent_form', 'venue_form', 'sample_quality'):
            specs = [s for s in SPECS if s.group == family]
            counts['complete_family:' + family] += all(row['features'][s.name]['value'] is not None for s in specs)
        for market in MARKETS:
            specs = [s for s in SPECS if market in s.markets]
            counts['complete_market:' + market] += all(row['features'][s.name]['value'] is not None for s in specs)
        counts['complete_all'] += all(f['value'] is not None for f in row['features'].values())
        counts['nonnull_values'] += sum(f['value'] is not None for f in row['features'].values())
    return dict(sorted(counts.items()))


def build_features(source_root, output_dir):
    root, output = Path(source_root), Path(output_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source-root must be a real directory')
    # Never allow output in the evidence tree, including resolved symlink aliases.
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError('output-dir must be outside source-root')
    rows, digest = [], hashlib.sha256()
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        history, raw, error = read_history(folder)
        digest.update((folder.name + '/history.json\0').encode())
        digest.update(hashlib.sha256(raw).digest() if raw is not None else b'MISSING_OR_INVALID')
        rows.append(materialize(history, folder.name, error))
    content = ''.join(dumps(row) + '\n' for row in rows).encode('utf-8')
    manifest = dict(feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                    rows=len(rows), features_per_row=len(SPECS), coverage=coverage(rows),
                    source_sha256=digest.hexdigest(), jsonl_sha256=hashlib.sha256(content).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in ('form_features.jsonl', 'form_manifest.json')]
    if any(p.is_symlink() for p in paths):
        raise ValueError('symlink output')
    paths[0].write_bytes(content)
    paths[1].write_text(dumps(manifest) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data/matches')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    try:
        result = build_features(args.source_root, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(dumps(result))


if __name__ == '__main__':
    main()
