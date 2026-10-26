"""2.6: raw H2H auxiliary features, never part of recent form."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from v3.data.builder import dumps
from v3.features.catalog import CATALOG_VERSION
from v3.features.history_adapter import read_history, target_metadata, team_history

FEATURE_VERSION = '2.6.0'
METRICS = ('sample_count', 'btts_rate', 'over_1_5_rate', 'over_2_5_rate',
           'over_3_5_rate', 'home_gf_mean', 'home_ga_mean', 'away_gf_mean', 'away_ga_mean')
# 14 canonical 2.1 columns plus 4 explicit away-perspective aliases.
SPECS = tuple(f'h2h_{metric}_h{n}' for n in (5, 10) for metric in METRICS)
BLOCKED = {}


def materialize(history, target_id, source_error=None):
    metadata, error = target_metadata(history, target_id)
    error = source_error or error
    sections = history.get('secciones')
    matches = [s for s in sections if isinstance(s, dict) and s.get('titulo') == 'ENFRENTAMIENTOS'] if isinstance(sections, list) else []
    valid, excluded = [], []
    if not error:
        if len(matches) != 1 or not isinstance(matches[0].get('partidos'), list):
            error = 'missing_or_ambiguous_h2h_section'
        else:
            # Reuse all score/temporal/duplicate gates without touching core form.
            raw_samples, ordinary_ids = [], set()
            for raw in matches[0]['partidos']:
                sample = dict(raw) if isinstance(raw, dict) else raw
                # H2H ordinary rows omit the team-relative G/E/P suffix.
                # Exact six-field grammar only; annotated scores stay excluded.
                if isinstance(sample, dict):
                    expected = [sample.get('fecha'), sample.get('competicion_codigo'),
                                sample.get('local'), sample.get('visitante'),
                                str(sample.get('goles_local')), str(sample.get('goles_visitante'))]
                    if (sample.get('score_scope') is None and sample.get('lineas_raw') == expected
                            and all(isinstance(v, str) and v for v in expected)
                            and sample.get('decidido_penales') in (None, False)
                            and all(sample.get(k) is None for k in ('penales_local', 'penales_visitante'))
                            and isinstance(sample.get('match_id'), str)):
                        sample['score_scope'] = 'REGULATION'
                        ordinary_ids.add(sample['match_id'])
                raw_samples.append(sample)
            section = dict(titulo='ÚLTIMOS PARTIDOS: ' + metadata['home'], partidos=raw_samples)
            adapted = dict(history, secciones=[section])
            candidates, excluded, error = team_history(adapted, target_id, metadata, 'home')
            pair_ids = {s.get('match_id') for s in matches[0]['partidos'] if isinstance(s, dict)
                        and isinstance(s.get('match_id'), str)
                        and isinstance(s.get('local'), str) and isinstance(s.get('visitante'), str)
                        and {s.get('local'), s.get('visitante')} == {metadata['home'], metadata['away']}}
            for s in candidates:
                if s['match_id'] in pair_ids:
                    if s['match_id'] in ordinary_ids:
                        s['score_evidence'] = 'flashscore_ordinary_h2h_row_v1'
                    valid.append(s)
                else:
                    excluded.append(dict(match_id=s['match_id'], date=s['date'], reasons=['h2h_pair_conflict']))
    features, windows = {}, {}
    for n in (5, 10):
        selected = valid[:n]
        count = None if error else len(selected)
        key = f'h{n}'
        windows[key] = dict(contributing=selected, sample_count=count, minimum_sample=3,
                            partial_sample=count < n if count is not None else None,
                            source_artifact=f'{target_id}/history.json', family='h2h_auxiliary')
        for metric in METRICS:
            reason = error or ('insufficient_sample' if metric != 'sample_count' and len(selected) < 3 else None)
            value = None
            if not reason:
                if metric == 'sample_count': value = len(selected)
                elif metric == 'btts_rate': value = sum(s['gf'] > 0 and s['ga'] > 0 for s in selected)/len(selected)
                elif metric.startswith('over_'):
                    threshold = int(metric.split('_')[1])
                    value = sum(s['gf'] + s['ga'] > threshold for s in selected)/len(selected)
                else:
                    field = 'gf' if metric in ('home_gf_mean', 'away_ga_mean') else 'ga'
                    value = sum(s[field] for s in selected)/len(selected)
            features[f'h2h_{metric}_h{n}'] = dict(value=value, reason=reason, sample_count=count, window=key)
    return dict(match_id=target_id, feature_version=FEATURE_VERSION, catalog_version=CATALOG_VERSION,
                metadata=metadata, family='h2h_auxiliary', features=features, windows=windows,
                exclusions={'h2h': sorted(excluded, key=dumps)})


def coverage(rows):
    return {'features': {name: dict(nonnull=sum(r['features'][name]['value'] is not None for r in rows),
             null=sum(r['features'][name]['value'] is None for r in rows),
             reasons=dict(sorted(Counter(r['features'][name]['reason'] for r in rows if r['features'][name]['reason']).items())))
             for name in SPECS}}


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
    paths = [output / name for name in ('h2h_features.jsonl', 'h2h_manifest.json')]
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
