"""Deterministic, read-only adapters for local V3 datasets. See README.md."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from v3.data.schema import (SCHEMA_VERSION, FEATURE_VERSION, Metadata, TeamSample,
                            ChampionPrediction, Labels)
from v3.data.validation import day, timestamp, prediction_errors, label_values
from v3.data.temporal import sample_reasons, eligible_status

BUILDER_VERSION = '1.3.0'
CHAMPION = 'J_BT_sin_temporada'
RELEVANT = ('history.json', 'result.json', 'lambda_comparison.json',
            'xg_history.json', 'standings.json', 'enriched.json', 'h2h_analysis.json')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':'))


def reject_constant(value):
    raise ValueError('nonfinite JSON constant')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


ADAPTED = {'history.json', 'result.json', 'lambda_comparison.json', 'champion_snapshot.json'}


def read_pool(path):
    """Index only exact match_id; preserve every duplicate for conflict validation."""
    if not path.exists():
        return {}, Counter({'absent:backtest_pool.json': 1}), None
    try:
        if path.is_symlink():
            raise ValueError('symlink pool')
        obj = json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant,
                         object_pairs_hook=unique_object)
        if not isinstance(obj, dict) or not isinstance(obj.get('partidos'), list):
            raise ValueError('expected partidos list')
        index = {}
        for entry in obj['partidos']:
            if not isinstance(entry, dict) or not isinstance(entry.get('match_id'), str) or not entry['match_id']:
                raise ValueError('missing exact match_id')
            index.setdefault(entry['match_id'], []).append(entry)
        return index, Counter(), None
    except (OSError, ValueError, UnicodeError):
        return {}, Counter({'invalid:backtest_pool.json': 1}), 'invalid_artifact:backtest_pool.json'


def normalize(folder, pool_entries=(), pool_error=None):
    reasons, flags, provenance, artifacts = [], [], [], {}
    counts = Counter()
    status = 'OK'

    def mark(reason, error=False):
        nonlocal status
        reasons.append(reason)
        if error or status == 'ERROR':
            status = 'ERROR'
        else:
            status = 'REVIEW'

    def trace(group, field, name, obj):
        provenance.append(dict(group=group, field=field, source='flashscore',
                               artifact=folder.name + '/' + name,
                               observed_at=obj.get('observed_at') if timestamp(obj.get('observed_at')) else None,
                               available_at=obj.get('available_at') if timestamp(obj.get('available_at')) else None))

    paths = sorted(p for p in folder.glob('*.json') if p.name in ADAPTED)
    flags.extend('unused_input_artifact:' + name for name in RELEVANT
                 if name not in ADAPTED and (folder / name).exists())
    for name in RELEVANT:
        if not (folder / name).exists():
            counts['absent:' + name] += 1
    for path in paths:
        try:
            if path.is_symlink():
                raise ValueError('symlink source')
            obj = json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant,
                             object_pairs_hook=unique_object)
            if not isinstance(obj, dict):
                raise ValueError('expected object')
            artifacts[path.name] = obj
        except (OSError, ValueError, UnicodeError):
            counts['invalid:' + path.name] += 1
            mark('invalid_artifact:' + path.name)

    meta = dict.fromkeys(Metadata.__annotations__)
    meta.update(source='flashscore', match_id=folder.name)
    aliases = dict(date='fecha', country='pais', competition='competicion',
                   season='temporada', home_team='local', away_team='visitante', kickoff='kickoff')
    claimed_ids = set()
    # Stable explicit precedence; all contradictory identities remain visible.
    for name in sorted(artifacts, key=lambda n: (n != 'history.json', n)):
        if name in ('champion_snapshot.json', 'lambda_comparison.json'):
            continue  # Predictions never supply identity or prematch metadata.
        obj = artifacts[name]
        partido = obj.get('partido', {})
        if not isinstance(partido, dict):
            mark('invalid_structure:' + name + ':partido')
            partido = {}
        for candidate in (obj.get('match_id'), partido.get('match_id'), partido.get('id')):
            if candidate is not None:
                if not isinstance(candidate, str) or not candidate:
                    mark('invalid_match_id:' + name)
                else:
                    claimed_ids.add(candidate)
                    if candidate != folder.name:
                        mark('identity_conflict:match_id:' + name, True)
        for field, alias in aliases.items():
            value = partido.get(alias)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                mark('invalid_metadata:' + field + ':' + name)
                continue
            if field == 'date' and not day(value):
                mark('invalid_date:' + name)
                continue
            if field == 'date':
                value = day(value).isoformat()
            if field == 'kickoff' and not timestamp(value):
                mark('invalid_kickoff:' + name)
                continue
            if meta[field] is not None and meta[field] != value:
                mark('identity_conflict:' + field + ':' + name, True)
            elif meta[field] is None:
                meta[field] = value
                trace('metadata', 'metadata.' + field, name, obj)
    trace('metadata', 'metadata.match_id', '(directory)', {})
    for field in ('date', 'home_team', 'away_team'):
        if meta[field] is None:
            mark('missing_structure:' + field)
    if meta['home_team'] is not None and meta['home_team'] == meta['away_team']:
        mark('identity_conflict:same_team', True)
    cutoff = timestamp(meta['kickoff'])
    if cutoff and cutoff.date() != day(meta['date']):
        mark('kickoff_date_conflict', True)
    inputs = dict(home=dict.fromkeys(TeamSample.__annotations__),
                  away=dict.fromkeys(TeamSample.__annotations__),
                  bilateral_xg_available=None, standings_available=None,
                  h2h_available=None, h2h_count=None)

    # Counts only from explicitly recognized raw history sections. No aggregates.
    history = artifacts.get('history.json')
    if history and 'secciones' in history:
        if not isinstance(history['secciones'], list):
            mark('invalid_structure:history.json:secciones')
        else:
            seen_sections = set()
            for section in history['secciones']:
                if not isinstance(section, dict) or not isinstance(section.get('titulo'), str) or not isinstance(section.get('partidos'), list):
                    mark('invalid_structure:history_section')
                    continue
                title = section['titulo'].casefold()
                side = next((s for s, field in [('home', 'home_team'), ('away', 'away_team')]
                             if meta[field] and title == 'últimos partidos: ' + meta[field].casefold()), None)
                h2h = title.startswith('enfrentamientos')
                if not side and not h2h:
                    flags.append('unsupported_history_section')
                    continue
                key = side or 'h2h'
                if key in seen_sections:
                    mark('duplicate_history_section:' + key)
                    continue
                seen_sections.add(key)
                valid = []
                ids = set()
                for sample in section['partidos']:
                    if not isinstance(sample, dict):
                        mark('invalid_history_sample')
                        continue
                    sample_id = sample.get('match_id')
                    violations = sample_reasons(folder.name, meta['date'],
                                                sample_id, sample.get('fecha'))
                    if violations:
                        for reason in violations:
                            mark('input_temporal:' + reason,
                                 reason in ('target_in_input', 'future_input',
                                            'same_day_input_without_verified_time'))
                        continue
                    if sample_id in ids:
                        mark('duplicate_history_sample')
                        continue
                    ids.add(sample_id)
                    if sample.get('resultado_parseado') is not True:
                        continue
                    if not all(type(sample.get(k)) is int and sample[k] >= 0 for k in ('goles_local', 'goles_visitante')):
                        continue
                    if side and meta['home_team' if side == 'home' else 'away_team'] not in (sample.get('local'), sample.get('visitante')):
                        mark('history_team_conflict', True)
                        continue
                    if h2h and (sample.get('local'), sample.get('visitante')) not in (
                        (meta['home_team'], meta['away_team']),
                        (meta['away_team'], meta['home_team']),
                    ):
                        mark('h2h_team_conflict', True)
                        continue
                    valid.append(sample)
                if side:
                    team = meta['home_team' if side == 'home' else 'away_team']
                    inputs[side]['history_count'] = len(valid)
                    inputs[side]['venue_history_count'] = sum(s.get('local' if side == 'home' else 'visitante') == team for s in valid)
                else:
                    inputs.update(h2h_available=bool(valid), h2h_count=len(valid))
                for sample in valid:
                    # A date is evidence at day resolution, never a fabricated timestamp.
                    trace('inputs', 'inputs.' + key + '.sample:' + sample['match_id']
                          + '.date:' + day(sample['fecha']).isoformat(), 'history.json', {})
                    provenance[-1]['source'] = 'flashscore:historical_sample_date'

    temporal = artifacts.get('result.json', {}).get('integridad_temporal')
    if temporal is not None:
        state = temporal.get('estado') if isinstance(temporal, dict) else None
        if state != 'OK':
            mark('source_temporal_status:' + str(state), state == 'ERROR')
    predictions = None
    comparison = artifacts.get('lambda_comparison.json', {})
    methods = comparison.get('metodos', {})
    if isinstance(methods, dict) and CHAMPION in methods:
        champion = methods[CHAMPION]
        if isinstance(champion, dict):
            predictions = dict.fromkeys(ChampionPrediction.__annotations__)
            predictions['model'] = CHAMPION
            for field, alias in [('lambda_home', 'local'), ('lambda_away', 'visitante'), ('lambda_total', 'total')]:
                predictions[field] = champion.get(alias)
            trace('predictions', 'predictions', 'lambda_comparison.json', comparison)
        else:
            mark('invalid_champion_structure')
    # Explicit canonical-scale snapshot adapter, never select an unnamed scenario.
    snapshot = artifacts.get('champion_snapshot.json')
    if snapshot and snapshot.get('model') == CHAMPION:
        predictions = {k: snapshot.get(k) for k in ChampionPrediction.__annotations__}
        if predictions['generated_at'] is not None and not timestamp(predictions['generated_at']):
            mark('invalid_prediction:generated_at')
            predictions['generated_at'] = None
        for field in ('confidence', 'global_quality'):
            if predictions[field] is not None and not isinstance(predictions[field], str):
                mark('invalid_prediction:' + field)
                predictions[field] = None
        if predictions['flags'] is not None and (not isinstance(predictions['flags'], list) or not all(isinstance(f, str) for f in predictions['flags'])):
            mark('invalid_prediction:flags')
            predictions['flags'] = None
        trace('predictions', 'predictions', 'champion_snapshot.json', snapshot)
    if predictions is not None:
        errors = prediction_errors(predictions)
        for error in errors:
            mark(error, True)
        if errors:
            # Invalid evidence stays in source; do not emit nonconforming numbers.
            predictions = None
    labels = None
    result = artifacts.get('result.json', {})
    settlement = result.get('settlement')
    # Explicit opt-in settlement shape; operational result scenarios aren't scores.
    if isinstance(settlement, dict) and settlement.get('status') == 'FINISHED' and settlement.get('score_scope') == 'REGULATION':
        labels = dict.fromkeys(Labels.__annotations__)
        labels['settled_at'] = settlement.get('settled_at') if timestamp(settlement.get('settled_at')) else None
        for field in ('home_goals', 'away_goals'):
            value = settlement.get(field)
            if value is not None and (type(value) is not int or value < 0):
                mark('invalid_label:' + field, True)
            else:
                labels[field] = value
        if labels['home_goals'] is not None and labels['away_goals'] is not None:
            derived = label_values(labels['home_goals'], labels['away_goals'])
            for field, expected in derived.items():
                if field in settlement and (type(settlement[field]) is not type(expected) or settlement[field] != expected):
                    mark('inconsistent_label:' + field, True)
            labels.update(derived)
        if any(r.startswith(('invalid_label:', 'inconsistent_label:')) for r in reasons):
            labels = None
        else:
            trace('labels', 'labels', 'result.json', result)
    # Retrospective results never contribute metadata, inputs or temporal evidence.
    if pool_error:
        mark(pool_error)
    pool_labels = None
    pool_invalid = False
    for entry in pool_entries:
        for field, alias in (('home_team', 'local'), ('away_team', 'visitante')):
            if alias in entry and (not isinstance(entry[alias], str) or not entry[alias].strip()
                                   or (meta[field] is not None and entry[alias] != meta[field])):
                mark('identity_conflict:' + field + ':backtest_pool.json', True)
                pool_invalid = True
        if 'id' in entry and entry['id'] != folder.name:
            mark('identity_conflict:match_id:backtest_pool.json', True)
            pool_invalid = True
        if not all(type(entry.get(k)) is int and entry[k] >= 0
                   for k in ('goles_local', 'goles_visitante')):
            mark('invalid_label:backtest_pool.json', True)
            pool_invalid = True
            continue
        candidate = dict.fromkeys(Labels.__annotations__)
        candidate.update(home_goals=entry['goles_local'], away_goals=entry['goles_visitante'])
        candidate.update(label_values(candidate['home_goals'], candidate['away_goals']))
        if pool_labels is not None and pool_labels != candidate:
            mark('conflicting_labels:backtest_pool.json', True)
            pool_invalid = True
        pool_labels = candidate
    if pool_labels is not None and labels is not None:
        if any(labels[k] is not None and labels[k] != pool_labels[k]
               for k in pool_labels if k != 'settled_at'):
            mark('conflicting_labels:settlement:backtest_pool.json', True)
            pool_invalid = True
    if pool_invalid:
        labels = None
    elif pool_labels is not None:
        if labels is None:
            labels = pool_labels
        trace('labels', 'labels', 'backtest_pool.json', {})
        provenance[-1]['artifact'] = 'backtest_pool.json'
    if all(inputs[side]['history_count'] is None for side in ('home', 'away')):
        mark('insufficient_input_evidence')
    if not all(inputs[side]['history_count'] is not None for side in ('home', 'away')):
        mark('incomplete_history_evidence')
    row = dict(schema_version=SCHEMA_VERSION, feature_version=FEATURE_VERSION,
               metadata=meta, inputs=inputs, predictions=predictions, labels=labels,
               audit=dict(feature_cutoff=meta['kickoff'], temporal_status=status,
                          eligible=eligible_status(status), reasons=sorted(set(reasons)),
                          quality_flags=sorted(set(flags)), provenance=provenance))
    return row, counts, claimed_ids


def flatten(value, prefix=''):
    if isinstance(value, dict):
        result = {}
        for key in sorted(value):
            result.update(flatten(value[key], prefix + '.' + key if prefix else key))
        return result
    return {prefix: dumps(value)}


def build_dataset(source_root='data/matches', output_dir='data/derived', limit=None, backtest_pool=None):
    source, output = Path(source_root), Path(output_dir)
    if not source.is_dir():
        raise ValueError('source-root must be an existing directory')
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError('limit must be positive')
    # Disallow any source/output overlap, including resolved symlinks.
    src, out = source.resolve(), output.resolve()
    if src == out or src in out.parents or out in src.parents:
        raise ValueError('output-dir must be disjoint from source-root')
    names = ('dataset_v3.jsonl', 'dataset_v3.csv', 'dataset_v3_manifest.json')
    if any((output / n).is_symlink() or
           ((output / n).exists() and (output / n).stat().st_nlink > 1)
           for n in names):
        raise ValueError('output files must not be symbolic or hard links')
    folders = sorted(p for p in source.iterdir() if p.is_dir() and not p.is_symlink())
    if limit:
        folders = folders[:limit]
    pool_path = Path(backtest_pool) if backtest_pool is not None else source.parent / 'backtest_pool.json'
    if pool_path.resolve() in {(output / n).resolve() for n in names}:
        raise ValueError('output must not overwrite backtest pool')
    pool, counts, pool_error = read_pool(pool_path)
    rows, identities = [], {}
    for folder in folders:
        row, found, claims = normalize(folder, pool.get(folder.name, ()), pool_error)
        counts.update(found)
        rows.append(row)
        for identity in claims | {folder.name}:
            identities.setdefault(identity, []).append(row)
    for identity, owners in identities.items():
        if len(owners) > 1:
            for row in owners:
                audit = row['audit']
                audit.update(eligible=False, temporal_status='ERROR')
                audit['reasons'] = sorted(set(audit['reasons'] + ['duplicate_match_id:' + identity]))
    rows.sort(key=lambda r: (r['metadata']['date'] is None, r['metadata']['date'] or '',
                             r['metadata']['kickoff'] or '', r['metadata']['match_id']))
    content = ''.join(dumps(r) + '\n' for r in rows).encode('utf-8')
    reasons = Counter(r['audit']['reasons'][0] for r in rows if r['audit']['reasons'])
    manifest = dict(schema_version=SCHEMA_VERSION, feature_version=FEATURE_VERSION,
                    builder_version=BUILDER_VERSION,
                    built_at=datetime.now(timezone.utc).isoformat(),
                    source_root=source.name, directories_inspected=len(folders),
                    rows_emitted=len(rows), eligible_rows=sum(r['audit']['eligible'] for r in rows),
                    ineligible_rows=sum(not r['audit']['eligible'] for r in rows),
                    labels_from_backtest_pool=sum(any(p['group'] == 'labels' and p['artifact'] == 'backtest_pool.json'
                                                      for p in r['audit']['provenance']) for r in rows),
                    primary_reasons=dict(sorted(reasons.items())),
                    artifact_counts=dict(sorted(counts.items())),
                    jsonl_sha256=hashlib.sha256(content).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    (output / names[0]).write_bytes(content)
    flat = [flatten(r) for r in rows]
    columns = sorted({k for r in flat for k in r})
    with (output / names[1]).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(flat)
    (output / names[2]).write_text(dumps(manifest) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', default='data/matches')
    parser.add_argument('--output-dir', default='data/derived')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--backtest-pool', help='optional pool; defaults to source-root sibling backtest_pool.json')
    args = parser.parse_args()
    try:
        manifest = build_dataset(args.source_root, args.output_dir, args.limit, args.backtest_pool)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(dumps(manifest))


if __name__ == '__main__':
    main()
