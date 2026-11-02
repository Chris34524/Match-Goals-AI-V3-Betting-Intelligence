"""FULL_MATCH_V1 orchestration. Diagnostic derivations never become settlement evidence."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
from v3.flashscore.contract import dumps
from v3.providers.contract import digest
from .selection import provider_id
from .api_football.client import Client, AcquisitionError, now
from .storage import atomic_json, checked_path
from .api_football.adapter import Adapter
from .api_football import VERSION as NORMALIZER_VERSION
from .api_football.normalization import LABELS, derive_second_half

PROFILE = 'FULL_MATCH_V1'
SURFACES = ('fixture', 'summary', 'stats_ft', 'stats_1h', 'stats_2h', 'events', 'lineups', 'standings', 'h2h', 'player_stats')
VERSION = 'selected-match-1'


def flashscore_live_state():
    from v3.flashscore.collector import live_authorized
    families = ('advanced_team_stats', 'goalkeeper', 'players', 'cards', 'corners', 'lineups', 'context')
    if not all(live_authorized('flashscore', 'permitted_ingestion', family) for family in families):
        return 'BLOCKED_SOURCE_AUTHORIZATION'
    return 'BLOCKED_LIVE_TRANSPORT_NOT_IMPLEMENTED'


def match_id(row, provider):
    value = provider_id(row, provider)
    if value is not None and (not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) or
            (provider == 'api_football' and (not value.isdecimal() or int(value) <= 0))):
        raise ValueError('invalid_provider_fixture_id')
    return value


def plan(rows, provider, maximum=None, quota=None):
    if provider not in ('api_football', 'flashscore'):
        raise ValueError('unsupported_provider')
    fixtures = [dict(provider_fixture_id=match_id(r, provider), source_fixture_reference=r.get('source_fixture_reference'),
                     surfaces=list(SURFACES), status='PLANNED' if match_id(r, provider) else 'PROVIDER_ID_UNRESOLVED') for r in rows]
    # API: shared status + fixture, half stats, events, lineups, standings, H2H, players per match.
    estimated = (1 + 7 * sum(f['provider_fixture_id'] is not None for f in fixtures)) if provider == 'api_football' else 0
    return dict(capture_profile=PROFILE, provider=provider, fixtures=fixtures, estimated_requests=estimated,
                maximum_requests=maximum, known_quota=quota, missing_provider_ids=sum(f['provider_fixture_id'] is None for f in fixtures))


def compact(value):
    """Bound retained context, with explicit truncation rather than a raw archive."""
    if len(dumps(value).encode()) > 256_000:
        return dict(status='UNKNOWN', reason='payload_retention_limit', payload_sha256=digest(value))
    return dict(status='AVAILABLE' if value else 'MISSING', data=value)


def capture(row, provider, *, client=None, replay_dir=None, root=None, captured_at=None):
    credential = os.environ.get('API_FOOTBALL_KEY')
    if credential and credential in dumps(row):
        raise ValueError('credential_in_selection_forbidden')
    mid = match_id(row, provider)
    if root is not None and mid:
        checked_path(Path(root) / provider / 'matches' / mid / 'manifest.json')
    stamp = captured_at or now()
    results = {s: dict(status='UNKNOWN', reason='not_attempted') for s in SURFACES}
    observations, payloads, hashes = [], {}, {}
    before = dict(client.quota) if client else {}
    used = client.used if client else 0
    metadata = dict(competition=row.get('competition'), season=row.get('season'), kickoff=row.get('kickoff'), home=row.get('home'), away=row.get('away'))
    reason = None
    if not mid:
        reason = 'PROVIDER_ID_UNRESOLVED'
    elif provider == 'flashscore':
        if replay_dir is None:
            reason = 'REPLAY_DIRECTORY_REQUIRED'
        else:
            from v3.flashscore.replay import read_replay
            for path in sorted(Path(replay_dir).glob('*.json')):
                observations.extend(c for c in read_replay(path) if c.request.fixture.provider == provider and c.request.fixture.match_id == mid)
            mapping = dict(summary='summary', stats_overall='stats_ft', stats_first_half='stats_1h', stats_second_half='stats_2h', events='events', lineups='lineups', standings='standings', h2h='h2h', player_stats='player_stats')
            for surface in SURFACES:
                selected = [c for c in observations if mapping.get(c.request.surface) == surface]
                if selected:
                    results[surface] = compact([c.to_dict() for c in selected])
                    states = {c.state.value for c in selected}
                    results[surface]['status'] = next((s for s in ('AVAILABLE', 'BLOCKED', 'MISSING', 'NOT_COVERED', 'UNKNOWN') if s in states), 'UNKNOWN')
                    payloads[surface] = results[surface]
            if observations:
                fixture = asdict(observations[0].request.fixture)
                metadata = dict(competition=fixture['competition_id'], season=fixture['season'],
                    kickoff=fixture['match_date'], home=dict(id=fixture['home_id']), away=dict(id=fixture['away_id']))
                results['fixture'] = compact(fixture)
                payloads['fixture'] = results['fixture']
    elif client is not None:
        def fetch(surface, endpoint, params):
            try:
                payload, evidence = client.get(endpoint, params)
                hashes[surface] = evidence.payload_sha256
                results[surface] = compact(payload['response'])
                if payload.get('paging', {}).get('total', 1) > 1:
                    results[surface]['status'] = 'UNKNOWN'
                    results[surface]['reason'] = 'pagination_incomplete'
                payloads[surface] = results[surface]
                return payload, evidence
            except (AcquisitionError, ValueError):
                results[surface] = dict(status='BLOCKED', reason='acquisition_or_validation_failed')
                payloads[surface] = results[surface]
                return None
        fc = fetch('fixture', '/fixtures', {'id': int(mid)})
        fixture_row = None
        if fc:
            rows = fc[0]['response']
            if len(rows) != 1 or str(rows[0]['fixture']['id']) != mid:
                reason = 'fixture_identity_mismatch'
            else:
                fixture_row = rows[0]
                metadata = dict(competition=fixture_row['league']['id'], season=fixture_row['league']['season'], kickoff=fixture_row['fixture']['date'], home=fixture_row['teams']['home'], away=fixture_row['teams']['away'])
                results['summary'] = compact(fixture_row['score'])
        if fixture_row:
            sc = fetch('stats_ft', '/fixtures/statistics', {'fixture': int(mid), 'half': 'true'})
            if sc:
                try:
                    observations = Adapter().normalize(fc[0], sc[0], fc[1], sc[1])
                    for period, surface in (('FT', 'stats_ft'), ('1H', 'stats_1h'), ('2H', 'stats_2h')):
                        caps = [c.to_dict() for c in observations if c.request.period == period and not c.request.capability_name.startswith('goals_')]
                        results[surface] = dict(status='AVAILABLE' if any(c['state'] == 'AVAILABLE' for c in caps) else 'MISSING', observations=caps)
                        payloads[surface] = results[surface]
                    diagnostics = []
                    for side in ('home', 'away'):
                        for field in LABELS.values():
                            values = {c.request.period: c.evidence.value for c in observations if c.request.side == side and c.request.capability_name == field}
                            if values.get('2H') is None:
                                diagnostics.append(dict(side=side, **derive_second_half(field, values.get('FT'), values.get('1H'))))
                    results['stats_2h']['diagnostics'] = diagnostics
                except ValueError:
                    observations = []
                    for surface in ('stats_ft', 'stats_1h', 'stats_2h'):
                        results[surface] = dict(status='UNKNOWN', reason='normalization_failed')
                        payloads[surface] = results[surface]
            for s, endpoint, params in (
                ('events', '/fixtures/events', {'fixture': int(mid)}),
                ('lineups', '/fixtures/lineups', {'fixture': int(mid)}),
                ('standings', '/standings', {'league': metadata['competition'], 'season': metadata['season']}),
                ('h2h', '/fixtures/headtohead', {'h2h': str(fixture_row['teams']['home']['id'])+'-'+str(fixture_row['teams']['away']['id'])}),
                ('player_stats', '/fixtures/players', {'fixture': int(mid)})):
                if s == 'standings' and fixture_row['league'].get('standings') is False:
                    results[s] = dict(status='NOT_COVERED', reason='provider_explicit_noncoverage')
                else:
                    fetch(s, endpoint, params)
    else:
        reason = 'PLANNED'
    if reason and reason != 'PLANNED':
        results = {s: dict(status='BLOCKED', reason=reason) for s in SURFACES}
    completed = [s for s in SURFACES if results[s]['status'] == 'AVAILABLE']
    status = 'PLANNED' if reason == 'PLANNED' else 'CAPTURED' if len(completed) == len(SURFACES) else 'PARTIAL' if completed else 'BLOCKED'
    manifest = dict(schema_version=VERSION, capture_profile=PROFILE, provider=provider, provider_fixture_id=mid,
        source_fixture_reference=row.get('source_fixture_reference'), **metadata, requested_surfaces=list(SURFACES),
        completed_surfaces=completed, blocked_surfaces=[s for s in SURFACES if results[s]['status']=='BLOCKED'],
        unknown_surfaces=[s for s in SURFACES if results[s]['status']=='UNKNOWN'], surfaces=results,
        request_count=(client.used-used) if client else 0, quota_before=before, quota_after=dict(client.quota) if client else {},
        captured_at=stamp, payload_hashes=hashes, normalizer_versions=[NORMALIZER_VERSION if provider == 'api_football' else 'fs-structured-replay', VERSION], overall_status=status, reason=reason)
    # Hash normalized stored artifacts for replay and normalized periods too.
    manifest = json.loads(dumps(manifest))
    manifest['artifact_hashes'] = {s: digest(v) for s, v in sorted(payloads.items())}
    if credential and credential in dumps(dict(manifest=manifest, observations=[c.to_dict() for c in observations])):
        raise ValueError('credential_in_artifact_forbidden')
    if root is not None and mid and status != 'PLANNED':
        directory = Path(root) / provider / 'matches' / mid
        for surface, value in payloads.items():
            atomic_json(directory / (surface+'.json'), value)
        atomic_json(directory / 'capabilities.json', [c.to_dict() for c in observations])
        atomic_json(directory / 'manifest.json', manifest)
    return manifest, observations


def matrix(observations, manifest=None):
    lines = ['FIELD/PERIOD FT 1H 2H']
    for field in ('goals_ft', 'goals_first_half', *LABELS.values()):
        states = []
        for period in ('FT', '1H', '2H'):
            caps = [c for c in observations if c.request.capability_name == field and c.request.period == period]
            state = 'AVAILABLE' if len(caps) == 2 and all(c.state.value == 'AVAILABLE' for c in caps) else 'UNKNOWN'
            if period == '2H' and state == 'UNKNOWN' and manifest:
                diagnostics = manifest['surfaces']['stats_2h'].get('diagnostics', [])
                derived = [d for d in diagnostics if d['field'] == field and d['status'] == 'AVAILABLE']
                if len(derived) == 2:
                    state = 'derived'
            states.append(state)
        lines.append(field+' '+ ' '.join(states))
    return '\n'.join(lines)
