"""Predeclared audit frame; identity conflicts are errors, exact duplicates deduplicate."""
from collections import defaultdict
from dataclasses import dataclass
import math

from .contract import Fixture, Request, timestamp

MANIFEST_VERSION = 'fs-audit-manifest-1'
STRATA = ('competition_id', 'season', 'stage', 'competition_tier', 'archive_age', 'lifecycle')


@dataclass(frozen=True)
class AuditFrame:
    manifest_id: str
    declared_at: str
    fixtures: tuple[Fixture, ...]
    requests: tuple[Request, ...]
    min_successful_inspections: int
    min_assessed_fraction: float
    duplicate_fixtures: int
    player_eligibility: tuple[dict, ...]
    target_context: dict | None


def load_manifest(data):
    if data.get('schema_version') != MANIFEST_VERSION or not data.get('manifest_id'):
        raise ValueError('unsupported or unidentified audit manifest')
    timestamp(data['declared_at'])
    minimum = data.get('min_successful_inspections', 30)
    fraction = data.get('min_assessed_fraction', 1.0)
    if type(minimum) is not int or minimum < 1:
        raise ValueError('minimum inspections must be positive')
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError('invalid minimum assessed fraction')
    fixtures, duplicate_fixtures = {}, 0
    for row in data['fixtures']:
        f = Fixture(**row)
        key = (f.provider, f.match_id)
        if key in fixtures:
            if fixtures[key] != f:
                raise ValueError('conflicting duplicate fixture identity/stratum')
            duplicate_fixtures += 1
        fixtures[key] = f
    if not fixtures or not data['fields']:
        raise ValueError('audit needs predeclared fixtures and fields')
    players = {}
    for row in data.get('players', []):
        key = (row['provider'], row['match_id'], row['player_id'])
        if key[:2] not in fixtures or not isinstance(row['player_id'], str) or not row['player_id']:
            raise ValueError('player outside manifest or unresolved')
        if key in players and players[key] != row:
            raise ValueError('conflicting player eligibility')
        if row.get('side') not in ('home', 'away'):
            raise ValueError('player orientation required')
        minutes = row.get('minutes')
        if minutes is not None and (type(minutes) not in (int, float) or not math.isfinite(minutes) or not 0 <= minutes <= 130):
            raise ValueError('invalid participation minutes')
        if row.get('participated') not in (True, False, None) or type(row.get('participated')) not in (bool, type(None)):
            raise ValueError('invalid participation')
        if row.get('participated') is True and minutes is not None and minutes <= 0:
            raise ValueError('contradictory participation')
        if row.get('participated') is False and minutes not in (None, 0):
            raise ValueError('contradictory nonparticipant minutes')
        players[key] = row
    players_by_fixture = defaultdict(list)
    for key, player in players.items():
        players_by_fixture[key[:2]].append(player)
    requests, eligibility = {}, []
    for f in fixtures.values():
        for field in data['fields']:
            level = field.get('level', 'team')
            if level == 'player':
                if field['period'] != 'FT':
                    raise ValueError('player-prop audit unit is participating player-fixture x field (FT)')
                rule = field.get('eligibility')
                if (not isinstance(rule, dict) or type(rule.get('min_minutes')) not in (int, float)
                        or not math.isfinite(rule['min_minutes']) or rule['min_minutes'] < 0
                        or not isinstance(rule.get('positions'), list) or not rule['positions']):
                    raise ValueError('player field needs explicit minutes and position eligibility')
                candidates = players_by_fixture[(f.provider, f.match_id)]
                if not candidates:
                    eligibility.append(dict(provider=f.provider, match_id=f.match_id, player_id=None,
                                            field=field['canonical_stat'], status='unassessed_roster'))
                for p in candidates:
                    status = ('unassessed' if p.get('participated') is None or p.get('minutes') is None
                              or not p.get('position') or not p.get('participation_reference') else
                              'eligible' if p['participated'] and p['minutes'] > 0
                              and p['minutes'] >= rule['min_minutes'] and p['position'] in rule['positions'] else 'excluded')
                    eligibility.append(dict(provider=f.provider, match_id=f.match_id, player_id=p['player_id'],
                                            field=field['canonical_stat'], status=status))
                    if status == 'eligible':
                        r = Request(f, field['surface'], field['period'], field['canonical_stat'],
                                    'player', p['side'], p['player_id'])
                        _add_request(requests, r)
            else:
                sides = field.get('sides', ['home', 'away']) if level == 'team' else [None]
                if level == 'team' and (not sides or any(s not in ('home', 'away') for s in sides)):
                    raise ValueError('invalid manifest sides')
                for side in sides:
                    r = Request(f, field['surface'], field['period'], field['canonical_stat'], level,
                                side, getattr(f, side + '_id') if side else None)
                    _add_request(requests, r)
    context = data.get('target_context')
    if context is not None:
        timestamp(context['cutoff'])
        if not context.get('match_id') or not context.get('match_date'):
            raise ValueError('target identity/date required')
    return AuditFrame(data['manifest_id'], data['declared_at'],
                      tuple(sorted(fixtures.values(), key=lambda f: (f.provider, f.match_id))),
                      tuple(sorted(requests.values(), key=lambda r: r.key)), minimum, fraction,
                      duplicate_fixtures, tuple(sorted(eligibility, key=lambda x: (
                          x['provider'], x['match_id'], x['field'], x['player_id'] or ''))), context)


def _add_request(requests, r):
    if r.key in requests and requests[r.key] != r:
        raise ValueError('conflicting duplicate field/surface')
    requests[r.key] = r
