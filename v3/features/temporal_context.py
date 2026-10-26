"""Observed streaks only; python -m v3.features.temporal_context --output-dir /tmp/temporal-v3."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from v3.data.builder import dumps
from v3.features.catalog import CATALOG, CATALOG_VERSION
from v3.features.history_adapter import read_history, target_metadata, team_history

FEATURE_VERSION = '2.4.0'
METRICS = ('scoring_streak', 'btts_streak', 'clean_sheet_streak')
SPECS = tuple(s for s in CATALOG if s.name.endswith('_streak_capped_l10'))
BLOCKED = {s.name: s.blocked_reason for s in CATALOG
           if s.group == 'temporal_context' and s.status == 'blocked'}


def holds(metric, sample):
    if metric == 'scoring_streak':
        return sample['gf'] > 0
    if metric == 'btts_streak':
        return sample['gf'] > 0 and sample['ga'] > 0
    return sample['ga'] == 0


def materialize(history, target_id, source_error=None):
    metadata, error = target_metadata(history, target_id)
    error = source_error or error
    features, windows, exclusions = {}, {}, {}
    source = f'{target_id}/history.json'
    for side in ('home', 'away'):
        valid, rejected, section_error = team_history(history, target_id, metadata, side) if not error else ([], [], error)
        selected = valid[:10]
        count = None if section_error else len(selected)
        reason = section_error or ('no_eligible_samples' if not selected else None)
        key = f'{side}_l10'
        windows[key] = dict(observed_sample_count=count, partial_sample=count < 10 if count is not None else None,
                            reason=reason, contributing=selected, source_artifact=source,
                            eligible_sample_count=len(valid) if not section_error else None)
        exclusions[side] = rejected
        for metric in METRICS:
            length = 0
            for sample in selected:
                if not holds(metric, sample):
                    break
                length += 1
            censored = length == len(selected) if not section_error else None
            capped = length == 10 if not section_error else None
            features[f'{side}_{metric}_capped_l10'] = dict(
                value=length if reason is None else None, reason=reason,
                observed_sample_count=count, partial_sample=windows[key]['partial_sample'],
                censored=censored, capped=capped,
                censoring_reason=('cap_10' if capped else 'observed_sample_boundary') if censored else None,
                contributing_match_ids=[s['match_id'] for s in selected[:length]],
                breaking_match_id=selected[length]['match_id'] if length < len(selected) else None,
                window=key)
    return dict(match_id=target_id, feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                metadata=metadata, source_artifact=source, features=features,
                windows=windows, exclusions=exclusions, blocked_features=BLOCKED)


def coverage(rows):
    stats, exclusions = {}, Counter()
    for spec in SPECS:
        values = [r['features'][spec.name] for r in rows]
        distribution = Counter(f['value'] for f in values if f['value'] is not None)
        stats[spec.name] = dict(nonnull=sum(distribution.values()), null=sum(f['value'] is None for f in values),
            lengths={str(n): distribution[n] for n in range(11)},
            partial_samples=sum(f['partial_sample'] is True for f in values),
            censored=sum(f['censored'] is True for f in values), capped=sum(f['capped'] is True for f in values),
            reasons=dict(sorted(Counter(f['reason'] for f in values if f['reason']).items())))
    for row in rows:
        for rejected in row['exclusions'].values():
            for sample in rejected:
                exclusions.update(sample['reasons'])
    return dict(features=stats, exclusions=dict(sorted(exclusions.items())))


def build_features(source_root, output_dir):
    root, output = Path(source_root), Path(output_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source-root must be a real directory')
    # Protect the entire data tree when invoked on its matches subdirectory.
    protected = root.parent if root.name == 'matches' else root
    if output.resolve().is_relative_to(protected.resolve()):
        raise ValueError('output-dir must be outside source data')
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
                    targets_inspected=len(rows), features_per_row=len(SPECS), coverage=coverage(rows),
                    blocked_features=BLOCKED, source_sha256=digest.hexdigest(),
                    jsonl_sha256=hashlib.sha256(content).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in ('temporal_features.jsonl', 'temporal_manifest.json')]
    if any(p.is_symlink() or (p.exists() and (not p.is_file() or p.stat().st_nlink != 1)) for p in paths):
        raise ValueError('unsafe output file')
    paths[0].write_bytes(content)
    paths[1].write_text(dumps(manifest) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data/matches')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(dumps(build_features(args.source_root, args.output_dir)))


if __name__ == '__main__':
    main()
