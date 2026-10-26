"""Read-only source coverage audit, not a Feature Engine. Outputs JSON to stdout.

python -m v3.features.audit --source-root data/matches
Counts evidence only: presence is never authorization to extract a feature.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from v3.data.builder import reject_constant, unique_object
from v3.data.temporal import sample_reasons
from v3.data.validation import day

ARTIFACTS = ('history.json', 'xg_history.json', 'standings.json',
             'h2h_analysis.json', 'enriched.json')


def audit_sources(source_root='data/matches'):
    root = Path(source_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source-root must be a real directory')
    counts, shapes, coverage, rejections = Counter(), Counter(), Counter(), Counter()
    digest = hashlib.sha256()
    folders = sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink())
    for folder in folders:
        objects = {}
        for name in ARTIFACTS:
            path = folder / name
            if path.is_symlink():
                counts['symlink:' + name] += 1
                continue
            if not path.exists():
                counts['absent:' + name] += 1
                continue
            raw = path.read_bytes()
            # Bind path and content without machine-specific root or mtimes.
            digest.update((folder.name + '/' + name + '\0').encode())
            digest.update(hashlib.sha256(raw).digest())
            counts['present:' + name] += 1
            try:
                obj = json.loads(raw, object_pairs_hook=unique_object,
                                 parse_constant=reject_constant)
                if not isinstance(obj, dict):
                    raise ValueError('expected object')
                objects[name] = obj
                for key in obj:
                    shapes[name + ':' + key] += 1
            except (ValueError, UnicodeError):
                counts['invalid:' + name] += 1
        history = objects.get('history.json', {})
        target = history.get('partido', {})
        if not isinstance(target, dict):
            target = {}
        sections = history.get('secciones', [])
        if not isinstance(sections, list):
            sections = []
        identity = [history.get('match_id'), target.get('id'), target.get('match_id')]
        target_valid = (day(target.get('fecha')) is not None
                        and all(v is None or v == folder.name for v in identity)
                        and all(isinstance(target.get(k), str) and target[k].strip()
                                for k in ('local', 'visitante'))
                        and target.get('local') != target.get('visitante'))
        side_counts = {}
        for side, team_key in (('home', 'local'), ('away', 'visitante'), ('h2h', None)):
            matched = [s for s in sections if isinstance(s, dict)
                       and isinstance(s.get('titulo'), str)
                       and ((team_key and isinstance(target.get(team_key), str)
                             and s['titulo'].casefold() == 'últimos partidos: ' + target[team_key].casefold())
                            or (side == 'h2h' and s['titulo'].casefold().startswith('enfrentamientos')))]
            if not target_valid or len(matched) != 1 or not isinstance(matched[0].get('partidos'), list):
                continue
            valid, seen, venues = 0, set(), 0
            dirty = False
            for sample in matched[0]['partidos']:
                if not isinstance(sample, dict):
                    dirty = True
                    continue
                reasons = sample_reasons(folder.name, target.get('fecha'),
                                         sample.get('match_id'), sample.get('fecha'))
                if reasons:
                    rejections.update(reasons)
                    dirty = True
                    continue
                sid = sample['match_id']
                if sid in seen:
                    rejections['duplicate_history_sample'] += 1
                    dirty = True
                    continue
                seen.add(sid)
                if sample.get('resultado_parseado') is not True or not all(
                    type(sample.get(k)) is int and sample[k] >= 0 for k in ('goles_local', 'goles_visitante')):
                    rejections['unparsed_or_invalid_score'] += 1
                    dirty = True
                    continue
                teams = (sample.get('local'), sample.get('visitante'))
                if (team_key and target[team_key] not in teams) or (
                    not team_key and teams not in ((target['local'], target['visitante']),
                                                   (target['visitante'], target['local']))):
                    rejections['history_team_conflict'] += 1
                    dirty = True
                    continue
                valid += 1
                if team_key and sample.get('local' if side == 'home' else 'visitante') == target[team_key]:
                    venues += 1
            coverage[f'{side}:recognized_sections'] += 1
            coverage[f'{side}:sections_without_rejections'] += not dirty
            for n in (1, 3, 5, 10):
                coverage[f'{side}:valid_count_ge_{n}'] += valid >= n
                if team_key:
                    coverage[f'{side}:venue_count_ge_{n}'] += venues >= n
            side_counts[side] = valid
        for n in (5, 10):
            coverage[f'bilateral_history_count_ge_{n}'] += all(side_counts.get(s, 0) >= n for s in ('home', 'away'))
        xg = objects.get('xg_history.json', {})
        paired_sides = []
        for side in ('local', 'visitante'):
            block = xg.get(side)
            if not isinstance(block, dict):
                paired_sides.append(False)
                continue
            samples = block.get('partidos')
            if not isinstance(samples, list):
                paired_sides.append(False)
                continue
            coverage['xg:' + side + ':raw_list'] += 1
            paired = 0
            for s in samples:
                if not isinstance(s, dict):
                    continue
                if all(type(s.get(k)) in (int, float) and math.isfinite(s[k]) and s[k] >= 0 for k in ('xgf', 'xga')):
                    paired += 1
                    coverage['xg:paired_samples'] += 1
                    if sample_reasons(folder.name, target.get('fecha'), s.get('match_id'), s.get('fecha')):
                        coverage['xg:paired_samples_temporally_rejected'] += 1
            coverage['xg:' + side + ':any_numeric_pair'] += paired > 0
            paired_sides.append(paired > 0)
        coverage['xg:bilateral_any_numeric_pair'] += all(paired_sides)
    return dict(audit_version='2.1.0', directories=len(folders),
                inspected_artifacts=list(ARTIFACTS), source_content_sha256=digest.hexdigest(),
                artifact_counts=dict(sorted(counts.items())), top_level_keys=dict(sorted(shapes.items())),
                evidence_counts=dict(sorted(coverage.items())), sample_rejections=dict(sorted(rejections.items())),
                limitations=[
                    'Coverage counts candidate evidence, not generated features or row eligibility.',
                    'Counts with valid samples may include sections with other rejected samples.',
                    'xG numeric pairs are presence only; no as-of lineage accreditation.',
                    'No complete fixture ledger inferred from capped history.',
                ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data/matches')
    args = parser.parse_args()
    print(json.dumps(audit_sources(args.source_root), ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2))


if __name__ == '__main__':
    main()
