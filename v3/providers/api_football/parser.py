"""Provider identity, score, event and lineup parsing. No name-based merging."""
from datetime import timezone
from v3.flashscore.contract import Fixture, timestamp
from v3.providers.contract import Identity
from .schemas import validate


def stable_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('unresolved_provider_id')
    return str(value)


def parse_fixture(row):
    try:
        f, league, teams = row['fixture'], row['league'], row['teams']
        kickoff = timestamp(f['date']).astimezone(timezone.utc).isoformat()
        code = f['status']['short']
        lifecycle = ('finished' if code in ('FT', 'AET', 'PEN') else
            'scheduled' if code in ('NS', 'TBD') else 'postponed' if code == 'PST' else
            'cancelled' if code in ('CANC', 'AWD', 'WO') else 'abandoned' if code in ('ABD', 'SUSP', 'INT') else
            'live' if code in ('1H', 'HT', '2H', 'ET', 'BT', 'P') else None)
        if lifecycle is None:
            raise ValueError('unknown_fixture_status')
        fixture = Fixture('api_football', stable_id(f['id']), stable_id(league['id']),
            stable_id(league['season']), str(league.get('round') or 'unspecified'), lifecycle,
            stable_id(teams['home']['id']), stable_id(teams['away']['id']), kickoff[:10])
        identities = [Identity('api_football', 'team', getattr(fixture, side + '_id'),
            ' '.join(teams[side]['name'].casefold().split()), fixture.competition_id)
            for side in ('home', 'away')]
        return fixture, dict(kickoff_utc=kickoff, status=code,
            scores={k: row['score'].get(k) for k in ('halftime', 'fulltime', 'extratime', 'penalty')},
            identities=[vars(i) for i in identities])
    except (KeyError, TypeError, AttributeError):
        raise ValueError('invalid_fixture_schema') from None


def context_rows(payload, endpoint, fixture, capture):
    if capture.endpoint != endpoint or capture.parameters.get('fixture') != int(fixture.match_id):
        raise ValueError('wrong_fixture_identity')
    rows = validate(payload, endpoint)
    result = []
    seen = set()
    for row in rows:
        team = stable_id(row['team']['id'])
        if team not in (fixture.home_id, fixture.away_id):
            raise ValueError('wrong_team_identity')
        side = 'home' if team == fixture.home_id else 'away'
        if endpoint == '/fixtures/events':
            result.append(dict(provider='api_football', fixture_id=fixture.match_id,
                team_id=team, side=side, time=row['time'], type=row['type'], detail=row['detail'],
                actor_id=str(row['player']['id']) if row['player'].get('id') else None,
                actor_scope='unknown', comments=row.get('comments'),
                source_endpoint=endpoint, captured_at=capture.captured_at,
                payload_sha256=capture.payload_sha256))
        else:
            if team in seen or not isinstance(row['startXI'], list) or not isinstance(row['substitutes'], list):
                raise ValueError('invalid_lineup_schema')
            seen.add(team)
            players = []
            for role, key in (('starter', 'startXI'), ('bench', 'substitutes')):
                for entry in row[key]:
                    player = entry['player']
                    players.append(dict(player_id=stable_id(player['id']), role=role,
                        name=player.get('name'), position=player.get('pos'), grid=player.get('grid')))
            result.append(dict(provider='api_football', fixture_id=fixture.match_id,
                team_id=team, side=side, formation=row.get('formation'), players=players,
                source_endpoint=endpoint, captured_at=capture.captured_at,
                payload_sha256=capture.payload_sha256))
    return result
