"""Read identities independently from provider timestamps; strict accredited contract.

Legacy fecha/hora are never converted into an aware kickoff. Predictions, results,
file dates and mtimes are never identity sources. No season inference.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
from v3.odds.provider import Target, utc

# Explicit reviewed competition names, not timezone or season assumptions.
COMPETITIONS = {
    ('ESPAÑA', 'LaLiga EA Sports'): ('soccer_spain_la_liga', 'LaLiga EA Sports'),
    ('INGLATERRA', 'Premier League'): ('soccer_epl', 'Premier League'),
    ('ALEMANIA', 'Bundesliga'): ('soccer_germany_bundesliga', 'Bundesliga'),
}


LINEAGE_VERSION = 'kickoff-lineage-v1'
# Closed vocabulary: source timestamps themselves must carry their UTC offset.
TIMEZONE_BASES = {'explicit_utc_offset', 'explicit_utc'}


def verify_source_digest(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('kickoff_lineage_digest_mismatch')
    return json.loads(raw)


def verify_source_identity(document, lineage, identity):
    records = document.get('records') if isinstance(document, dict) else None
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError('kickoff_lineage_invalid')
    matches = [r for r in records if r.get('identity') == identity]
    selected = [r for r in records if r.get('source_record_id') == lineage.get('source_record_id')]
    if len(matches) != 1 or len(selected) != 1 or matches[0] != selected[0] or lineage.get('identity') != identity:
        raise ValueError('kickoff_lineage_identity_mismatch')
    return matches[0]


def validate_kickoff_lineage(row, target_path, identity, now):
    lineage = row.get('kickoff_lineage')
    if not isinstance(lineage, dict) or lineage.get('version') != LINEAGE_VERSION:
        raise ValueError('kickoff_lineage_invalid')
    if lineage.get('timezone_basis') not in TIMEZONE_BASES:
        raise ValueError('kickoff_timezone_basis_missing')
    source = lineage.get('source_path')
    if not isinstance(source, str) or not source:
        raise ValueError('kickoff_lineage_source_missing')
    path = Path(source)
    resolved = path.resolve()
    if resolved == Path(target_path).resolve() or path.name == 'internal-targets.json':
        raise ValueError('kickoff_lineage_not_independent')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('kickoff_lineage_source_symlink')
    roots = [Path('data').resolve(), Path('v3_data/ops/evidence').resolve()]
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError('kickoff_lineage_source_outside_root')
    if not path.is_file():
        raise ValueError('kickoff_lineage_source_missing')
    document = verify_source_digest(path, lineage.get('source_sha256'))
    if resolved.is_relative_to(roots[1]) and path.name != lineage['source_sha256'] + '.json':
        raise ValueError('kickoff_lineage_not_immutable')
    record = verify_source_identity(document, lineage, identity)
    if document.get('synthetic_test_only') is not False or record.get('synthetic_test_only') is not False:
        raise ValueError('kickoff_lineage_synthetic')
    if 'kickoff_lineage' in record or 'kickoff_accredited' in record:
        raise ValueError('kickoff_lineage_not_independent')
    field = lineage.get('kickoff_field')
    if field != 'kickoff_at' or record.get('timezone_basis') != lineage['timezone_basis']:
        raise ValueError('kickoff_timezone_basis_missing')
    if not lineage.get('source_record_id') or record.get('captured_at') != lineage.get('captured_at'):
        raise ValueError('kickoff_lineage_invalid')
    try:
        kickoff = utc(row['kickoff_at'])
        source_kickoff = utc(record[field])
        claimed = utc(lineage['kickoff_value'])
        captured = utc(lineage['captured_at'])
    except (ValueError, KeyError, TypeError):
        raise ValueError('kickoff_lineage_timestamp_invalid') from None
    if kickoff != source_kickoff or kickoff != claimed:
        raise ValueError('kickoff_lineage_kickoff_mismatch')
    if captured >= kickoff or captured > utc(now):
        raise ValueError('kickoff_lineage_capture_not_prospective')
    return True


def inspect(now, paths=None):
    paths = paths if paths is not None else [Path('data/partidos.json'), Path('data/partidos_candidatos.json'), Path('data/partidos_hoy.json'),
                                               Path('data/partidos_manana.json'),
                                               Path('v3_data/ops/internal-targets.json')]
    targets = []; evidence = []; candidates = set(); excluded = Counter()
    for path in map(Path, paths):
        if not path.exists():
            continue
        raw = path.read_bytes()
        data = json.loads(raw)
        rows = data.get('partidos', data.get('candidatos', [])) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError('invalid_internal_inventory')
        evidence.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), rows=len(rows)))
        for row in rows:
            if not isinstance(row, dict):
                excluded['invalid_identity'] += 1; continue
            mapped = COMPETITIONS.get((row.get('pais'), row.get('competicion')))
            if mapped:
                candidates.add(mapped[0])
            try:
                # These must be supplied by the internal source independently.
                if row.get('synthetic_test_only') is not False or row.get('kickoff_accredited') is not True:
                    raise ValueError('internal_kickoff_not_accredited')
                kickoff = row['kickoff_at']
                if utc(kickoff) <= utc(now):
                    raise ValueError('internal_target_not_future')
                sport, competition = mapped if mapped else (row['sport_key'], row['competition'])
                if (sport, competition) not in COMPETITIONS.values():
                    raise ValueError('competition_not_mapped')
                target = Target(internal_match_id=row.get('internal_match_id') or row['id'],
                                sport_key=sport, competition=competition, season=row['season'],
                                kickoff_at=kickoff, home=row.get('home') or row['local'],
                                away=row.get('away') or row['visitante'], markets=('1X2',), priority='P0')
                if target.home == target.away:
                    raise ValueError('invalid_identity')
                validate_kickoff_lineage(row, path, dict(internal_match_id=target.internal_match_id,
                    home=target.home, away=target.away, competition=target.competition), now)
                targets.append(target)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                code = str(exc) if isinstance(exc, ValueError) else 'missing_internal_identity_fields'
                excluded[code] += 1
    counts = Counter(t.internal_match_id for t in targets)
    if any(n != 1 for n in counts.values()):
        raise ValueError('ambiguous_internal_identity')
    return dict(internal_target_status='ELIGIBLE' if targets else 'BLOCKED_NO_FRESH_INTERNAL_TARGET',
                targets=[asdict(t) for t in targets], evidence=evidence,
                candidates=sorted(candidates)[:3], exclusions=dict(sorted(excluded.items())))
