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
                if row.get('synthetic_test_only') is not False or row.get('kickoff_accredited') is not True or not row.get('kickoff_lineage'):
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
                targets.append(target)
            except (ValueError, KeyError, TypeError) as exc:
                code = str(exc) if isinstance(exc, ValueError) else 'missing_internal_identity_fields'
                excluded[code] += 1
    counts = Counter(t.internal_match_id for t in targets)
    if any(n != 1 for n in counts.values()):
        raise ValueError('ambiguous_internal_identity')
    return dict(internal_target_status='ELIGIBLE' if targets else 'BLOCKED_NO_FRESH_INTERNAL_TARGET',
                targets=[asdict(t) for t in targets], evidence=evidence,
                candidates=sorted(candidates)[:3], exclusions=dict(sorted(excluded.items())))
