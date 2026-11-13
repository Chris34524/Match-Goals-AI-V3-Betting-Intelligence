"""Adapt existing fixture universes, retaining provider-local identity."""
from datetime import datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from v3.providers.full_capture import match_id
from v3.providers.selection import provider_id, resolve, select
from v3.flashscore.contract import timestamp

TIMEZONE = 'America/Mexico_City'


def resolve_date(value='today', timezone=TIMEZONE, now=None):
    today = (now or datetime.now(ZoneInfo(timezone))).astimezone(ZoneInfo(timezone)).date()
    key = value.casefold().strip()
    if key in ('today', 'hoy'):
        return today
    if key in ('tomorrow', 'mañana', 'manana'):
        return today + timedelta(days=1)
    return datetime.strptime(value, '%Y-%m-%d').date()


def rows_from_document(document):
    if isinstance(document, list):
        rows = document
    elif isinstance(document, dict):
        rows = next((document[k] for k in ('fixtures', 'response', 'partidos', 'matches', 'targets')
                     if isinstance(document.get(k), list)), None)
        if rows is None and isinstance(document.get('secciones'), list):
            rows = [dict(p, competicion=p.get('competicion') or s.get('titulo'))
                    for s in document['secciones'] for p in s.get('partidos', [])]
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('invalid_fixture_universe')
    return rows


def normalize(row, provider, timezone=TIMEZONE):
    row = dict(row)
    official = all(k in row for k in ('fixture', 'league', 'teams'))
    legacy = 'local' in row and 'visitante' in row and not official
    origin = row.get('provider') or ('api_football' if official else 'flashscore' if legacy else None)
    if official and origin != 'api_football':
        raise ValueError('official_payload_provider_conflict')
    # A foreign provider_ids entry is only a proposed mapping, never verification.
    if origin != provider:
        raise ValueError('provider_mapping_requires_stable_identity_resolution')
    if legacy and provider == 'flashscore':
        ids = [str(row[k]) for k in ('id', 'match_id', 'flashscore_id') if row.get(k) is not None]
        if not ids or len(set(ids)) != 1:
            raise ValueError('ambiguous_fixture_identity')
        row['provider_fixture_id'] = ids[0]
    row['provider'] = provider
    declared = [str(v) for v in (row.get('provider_fixture_id'), row.get('provider_ids', {}).get(provider),
                                row.get('fixture', {}).get('id') if official else None) if v is not None]
    if len(set(declared)) > 1:
        raise ValueError('ambiguous_fixture_identity')
    mid = match_id(row, provider)
    if not mid:
        raise ValueError('PROVIDER_ID_UNRESOLVED')
    if official:
        f, league, teams = row['fixture'], row['league'], row['teams']
        kickoff, raw_date = f.get('date'), None
        home, away = teams['home'], teams['away']
        competition, season, country = league.get('name'), league.get('season'), league.get('country')
        competition_id = league.get('id')
    else:
        kickoff, raw_date = row.get('kickoff'), row.get('fecha', row.get('date'))
        home, away = row.get('home', row.get('local')), row.get('away', row.get('visitante'))
        competition, season = row.get('competition', row.get('competicion')), row.get('season')
        country, competition_id = row.get('country', row.get('pais')), row.get('competition_id')
    if kickoff:
        event_date = timestamp(kickoff).astimezone(ZoneInfo(timezone)).date()
    else:
        event_date = None
        for fmt in ('%Y-%m-%d', '%d.%m.%y', '%d.%m.%Y', '%d/%m/%Y'):
            try:
                event_date = datetime.strptime(str(raw_date), fmt).date()
                break
            except ValueError:
                pass
        if event_date is None:
            raise ValueError('fixture_date_missing')
    def team(value):
        if isinstance(value, dict):
            return dict(id=str(value['id']) if value.get('id') is not None else None,
                        name=value.get('name') or str(value.get('id', '')))
        return dict(id=None, name=value)
    home, away = team(home), team(away)
    if not all(isinstance(t['name'], str) and t['name'].strip() for t in (home, away)):
        raise ValueError('fixture_team_missing')
    if home['name'] == away['name'] or (home['id'] is not None and home['id'] == away['id']):
        raise ValueError('fixture_orientation_conflict')
    return dict(provider=provider, provider_fixture_id=mid, date=event_date.isoformat(),
                kickoff=kickoff, display_time=row.get('hora') or (timestamp(kickoff).astimezone(
                    ZoneInfo(timezone)).strftime('%H:%M') if kickoff else None),
                timezone=timezone, home=home, away=away, competition=competition,
                source_lifecycle=row.get('estado', row.get('fixture', {}).get('status', {}).get('short')),
                competition_id=str(competition_id) if competition_id is not None else None,
                country=country, season=str(season) if season is not None else None,
                provider_ids={provider: mid}, source_fixture_reference=row.get('source_fixture_reference'),
                identity_status='PROVIDER_LOCAL', synthetic_test_only=row.get('synthetic_test_only', False))


def universe(rows, provider, timezone=TIMEZONE, candidates=(), exclusions=None):
    result, conflicted = {}, set()
    for raw in rows:
        try:
            fixture = normalize(raw, provider, timezone)
        except ValueError as error:
            if str(error) != 'provider_mapping_requires_stable_identity_resolution' or not candidates:
                raise
            proposal = resolve(raw, candidates, provider)
            if proposal['status'] != 'RESOLVED':
                raise ValueError('PROVIDER_ID_UNRESOLVED') from None
            matches = [c for c in candidates if provider_id(c, provider) == proposal['provider_fixture_id']]
            if len(matches) != 1:
                raise ValueError('ambiguous_provider_mapping')
            fixture = normalize(matches[0], provider, timezone)
            fixture['identity_status'] = 'VERIFIED_STABLE_IDS'
            proposed = raw.get('provider_ids', {})
            if proposed.get(provider) is not None and str(proposed[provider]) != proposal['provider_fixture_id']:
                raise ValueError('proposed_provider_mapping_conflict')
            fixture['proposed_provider_ids'] = proposed
            if raw.get('provider') and provider_id(raw, raw['provider']):
                fixture['provider_ids'][raw['provider']] = provider_id(raw, raw['provider'])
        key = (fixture['provider'], fixture['provider_fixture_id'])
        if key in conflicted:
            continue
        if key in result:
            if fixture != result[key]:
                if exclusions is None:
                    raise ValueError('conflicting_fixture_identity')
                exclusions.append(dict(provider=key[0], match_id=key[1], reason='conflicting_fixture_identity',
                                       variants=[result[key], fixture]))
                del result[key]
                conflicted.add(key)
        else:
            result[key] = fixture
    return sorted(result.values(), key=lambda r: (r['date'], r['display_time'] or '', r['provider_fixture_id']))


def load(path, provider, timezone=TIMEZONE, candidates=()):
    rows = rows_from_document(json.loads(Path(path).read_text(encoding='utf-8')))
    return universe(rows, provider, timezone, candidates)


def filtered(rows, date, country=None, competition=None, team=None):
    def contains(query, value):
        return not query or query.casefold() in str(value or '').casefold()
    return [r for r in rows if r['date'] == date.isoformat()
            and contains(country, r['country']) and contains(competition, r['competition'])
            and (not team or any(contains(team, r[s]['name']) for s in ('home', 'away')))]


def choose(rows, indices=None, ids=(), limit=6):
    if type(limit) is not int or limit < 1:
        raise ValueError('positive_match_limit_required')
    chosen = select(rows, indices) if indices else []
    for mid in ids:
        found = [r for r in rows if r['provider_fixture_id'] == mid]
        if len(found) != 1:
            raise ValueError('exact_match_id_not_in_filtered_universe')
        chosen.extend(found)
    unique = {(r['provider'], r['provider_fixture_id']): r for r in chosen}
    if not unique:
        raise ValueError('selection_required')
    if len(unique) > limit:
        raise ValueError('selection_exceeds_match_limit')
    return list(unique.values())
