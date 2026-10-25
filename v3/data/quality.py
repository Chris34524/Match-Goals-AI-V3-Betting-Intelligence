"""Read-only deterministic dataset quality report; invalid JSONL fails atomically."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from v3.data.builder import dumps, reject_constant, unique_object, CHAMPION
from v3.data.schema import (CanonicalMatch, Metadata, Inputs, Audit, TeamSample,
                            Labels, ChampionPrediction, Provenance)
from v3.data.temporal import sample_reasons
from v3.data.validation import day, timestamp, prediction_errors, label_values


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('nonfinite JSON number')
    return parsed


def structural_errors(row):
    errors = []

    def shape(value, contract, path):
        if not isinstance(value, dict):
            errors.append(path + ':expected_object')
            return {}
        if set(value) != set(contract.__annotations__):
            errors.append(path + ':keys')
        return value

    row = shape(row, CanonicalMatch, 'row')
    meta = shape(row.get('metadata'), Metadata, 'metadata')
    inputs = shape(row.get('inputs'), Inputs, 'inputs')
    audit = shape(row.get('audit'), Audit, 'audit')
    for key in ('schema_version', 'feature_version'):
        if row.get(key) != '3.0.0':
            errors.append(key + ':unsupported')
    for key in Metadata.__annotations__:
        value = meta.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append('metadata.' + key + ':invalid')
    if not isinstance(meta.get('match_id'), str) or not meta.get('match_id'):
        errors.append('metadata.match_id:missing')
    if meta.get('date') is not None and not day(meta['date']):
        errors.append('metadata.date:invalid')
    for key in ('kickoff',):
        if meta.get(key) is not None and not timestamp(meta[key]):
            errors.append('metadata.' + key + ':invalid')
    if meta.get('home_team') and meta.get('home_team') == meta.get('away_team'):
        errors.append('metadata:identity_conflict')
    if timestamp(meta.get('kickoff')) and timestamp(meta['kickoff']).date() != day(meta.get('date')):
        errors.append('metadata:kickoff_date_conflict')
    for side in ('home', 'away'):
        team = shape(inputs.get(side), TeamSample, 'inputs.' + side)
        for key, value in team.items():
            if value is not None and (type(value) is not int or value < 0):
                errors.append('inputs.' + side + '.' + key + ':invalid_count')
        h, v = team.get('history_count'), team.get('venue_history_count')
        if type(h) is int and type(v) is int and v > h:
            errors.append('inputs.' + side + ':venue_exceeds_history')
    for key in ('bilateral_xg_available', 'standings_available', 'h2h_available'):
        if inputs.get(key) is not None and type(inputs[key]) is not bool:
            errors.append('inputs.' + key + ':invalid_boolean')
    count = inputs.get('h2h_count')
    if count is not None and (type(count) is not int or count < 0):
        errors.append('inputs.h2h_count:invalid_count')
    status = audit.get('temporal_status')
    if status not in ('OK', 'REVIEW', 'ERROR'):
        errors.append('audit.temporal_status:invalid')
    if type(audit.get('eligible')) is not bool:
        errors.append('audit.eligible:invalid')
    if audit.get('eligible') is True and status != 'OK':
        errors.append('audit:temporal_gate_violation')
    for key in ('reasons', 'quality_flags'):
        value = audit.get(key)
        if key == 'quality_flags' and value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append('audit.' + key + ':invalid')
        elif value != sorted(set(value)):
            errors.append('audit.' + key + ':noncanonical_order')
    if audit.get('feature_cutoff') != meta.get('kickoff'):
        errors.append('audit.feature_cutoff:conflict')
    provenance = audit.get('provenance')
    if not isinstance(provenance, list):
        errors.append('audit.provenance:invalid')
        provenance = []
    evidence_counts = Counter()
    for entry in provenance:
        entry = shape(entry, Provenance, 'provenance')
        group, field = entry.get('group'), entry.get('field')
        if group not in ('metadata', 'inputs', 'labels', 'predictions') or not isinstance(field, str) or not field.startswith(str(group) + '.') and field != group:
            errors.append('provenance:group_field_conflict')
        artifact = entry.get('artifact')
        if group in ('metadata', 'inputs') and isinstance(artifact, str) and artifact.split('/')[-1] in ('backtest_pool.json', 'champion_snapshot.json', 'lambda_comparison.json'):
            errors.append('provenance:isolated_artifact_in_features')
        if group == 'inputs':
            if entry.get('source') != 'flashscore:historical_sample_date' or not isinstance(field, str) or '.sample:' not in field or '.date:' not in field:
                errors.append('provenance:unverified_input')
            else:
                identity, date = field.split('.sample:', 1)[1].rsplit('.date:', 1)
                errors.extend('provenance:' + r for r in sample_reasons(meta.get('match_id'), meta.get('date'), identity, date))
                evidence_counts[field.split('.sample:', 1)[0]] += 1
    for side in ('home', 'away'):
        team = inputs.get(side)
        count = team.get('history_count') if isinstance(team, dict) else None
        if type(count) is int and count != evidence_counts['inputs.' + side]:
            errors.append('inputs.' + side + ':history_provenance_count_conflict')
        if audit.get('eligible') is True and count is None:
            errors.append('audit:eligible_without_history')
    if audit.get('eligible') is True and (not day(meta.get('date')) or
            not meta.get('home_team') or not meta.get('away_team')):
        errors.append('audit:eligible_without_identity')
    prediction = row.get('predictions')
    if prediction is not None:
        prediction = shape(prediction, ChampionPrediction, 'predictions')
        if prediction.get('model') != CHAMPION:
            errors.append('predictions:model')
        errors.extend('predictions:' + e for e in prediction_errors(prediction))
    labels = row.get('labels')
    if labels is not None:
        labels = shape(labels, Labels, 'labels')
        home, away = labels.get('home_goals'), labels.get('away_goals')
        for value in (home, away):
            if value is not None and (type(value) is not int or value < 0):
                errors.append('labels:invalid_score')
        if type(home) is int and type(away) is int and home >= 0 and away >= 0:
            for key, expected in label_values(home, away).items():
                if type(labels.get(key)) is not type(expected) or labels.get(key) != expected:
                    errors.append('labels:inconsistent_' + key)
    return sorted(set(errors))


def quality_report(dataset, manifest=None):
    path = Path(dataset)
    content = path.read_bytes()
    rows = []
    for line_number, line in enumerate(content.decode('utf-8').splitlines(), 1):
        try:
            row = json.loads(line, parse_float=finite_float, parse_constant=reject_constant, object_pairs_hook=unique_object)
        except ValueError as exc:
            raise ValueError(f'invalid JSONL at line {line_number}: {exc}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'invalid JSONL at line {line_number}: expected object')
        rows.append(row)
    statuses, reasons, primary, identities, dates, issues = (Counter() for _ in range(6))
    coverage = {side: Counter() for side in ('home', 'away')}
    eligible = labels = predictions = pool_labels = 0
    for row in rows:
        issues.update(structural_errors(row))
        audit = row.get('audit') if isinstance(row.get('audit'), dict) else {}
        meta = row.get('metadata') if isinstance(row.get('metadata'), dict) else {}
        inputs = row.get('inputs') if isinstance(row.get('inputs'), dict) else {}
        statuses[str(audit.get('temporal_status'))] += 1
        eligible += audit.get('eligible') is True
        labels += isinstance(row.get('labels'), dict)
        predictions += isinstance(row.get('predictions'), dict)
        rs = audit.get('reasons')
        if isinstance(rs, list) and all(isinstance(r, str) for r in rs):
            reasons.update(set(rs))
            if rs:
                primary[sorted(rs)[0]] += 1
        if isinstance(meta.get('match_id'), str):
            identities[meta['match_id']] += 1
        date = day(meta.get('date'))
        dates[date.isoformat() if date else 'unknown'] += 1
        prov = audit.get('provenance')
        pool_labels += isinstance(prov, list) and any(isinstance(p, dict) and p.get('group') == 'labels' and p.get('artifact') == 'backtest_pool.json' for p in prov)
        for side in coverage:
            team = inputs.get(side)
            count = team.get('history_count') if isinstance(team, dict) else None
            coverage[side][str(count) if type(count) is int and count >= 0 else 'unknown'] += 1
    report = dict(total_rows=len(rows), eligible_rows=eligible, ineligible_rows=len(rows)-eligible,
                  temporal_status=dict(sorted(statuses.items())),
                  top_reasons=[dict(reason=r, rows=n) for r, n in sorted(reasons.items(), key=lambda x: (-x[1], x[0]))],
                  primary_reasons=dict(sorted(primary.items())), rows_with_labels=labels,
                  rows_with_champion_predictions=predictions, labels_from_backtest_pool=pool_labels,
                  history_count={s: dict(sorted(c.items())) for s, c in coverage.items()},
                  date_distribution=dict(sorted(dates.items())),
                  duplicate_match_ids={k: v for k, v in sorted(identities.items()) if v > 1},
                  structural_inconsistencies=dict(sorted(issues.items())),
                  jsonl_sha256=hashlib.sha256(content).hexdigest())
    manifest_path = Path(manifest) if manifest else path.with_name(path.stem + '_manifest.json')
    report['manifest'] = dict(present=manifest_path.exists(), mismatches={})
    if manifest_path.exists():
        expected = json.loads(manifest_path.read_text(encoding='utf-8'), parse_float=finite_float, parse_constant=reject_constant, object_pairs_hook=unique_object)
        if not isinstance(expected, dict):
            raise ValueError('manifest must be an object')
        for key, actual in dict(rows_emitted=len(rows), eligible_rows=eligible,
                                ineligible_rows=len(rows)-eligible, labels_from_backtest_pool=pool_labels,
                                primary_reasons=report['primary_reasons'], jsonl_sha256=report['jsonl_sha256']).items():
            if expected.get(key) != actual:
                report['manifest']['mismatches'][key] = dict(expected=expected.get(key), actual=actual)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--manifest')
    args = parser.parse_args()
    try:
        report = quality_report(args.dataset, args.manifest)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(dumps(report))
    if report['duplicate_match_ids'] or report['structural_inconsistencies'] or report['manifest']['mismatches']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
