"""Provider-local fixture selection and deterministic identity resolution."""
import json
from pathlib import Path


def provider_id(row, provider):
    value = row.get('provider_ids', {}).get(provider)
    if value is None and row.get('provider') == provider:
        value = row.get('provider_fixture_id', row.get('match_id'))
    if (value is None and provider == 'api_football' and row.get('provider') in (None, provider)
            and 'fixture' in row and 'teams' in row and 'league' in row):
        value = row['fixture'].get('id')
    return str(value) if value is not None else None


def load_source(path, provider):
    content = Path(path).read_text(encoding='utf-8')
    if Path(path).suffix.lower() != '.json':
        return [dict(provider=provider, provider_fixture_id=x.strip()) for x in content.splitlines() if x.strip()]
    data = json.loads(content)
    rows = data if isinstance(data, list) else data.get('fixtures', data.get('response'))
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('invalid_fixture_universe')
    return rows


def select(rows, expression):
    if expression.strip().lower() == 'all':
        return list(rows)
    indices = set()
    try:
        for token in expression.split(','):
            parts = token.strip().split('-')
            if len(parts) == 1:
                start = end = int(parts[0])
            elif len(parts) == 2:
                start, end = map(int, parts)
            else:
                raise ValueError()
            if not 1 <= start <= end <= len(rows):
                raise ValueError()
            indices.update(range(start-1, end))
    except (ValueError, TypeError):
        raise ValueError('invalid_selection') from None
    return [rows[i] for i in sorted(indices)]


def resolve(row, candidates, provider='api_football'):
    """Only provider-local stable teams, league, season and date can verify a match."""
    context = row.get('resolution_context', {}).get(provider, {})
    required = ('date', 'competition_id', 'season', 'home_id', 'away_id')
    if any(context.get(k) is None for k in required):
        return dict(status='PROVIDER_ID_UNRESOLVED', candidates_verified=False)
    matches = []
    for c in candidates:
        try:
            actual = dict(date=c['fixture']['date'][:10], competition_id=c['league']['id'],
                          season=c['league']['season'], home_id=c['teams']['home']['id'], away_id=c['teams']['away']['id'])
            if all(str(actual[k]) == str(context[k]) for k in required):
                matches.append(c)
        except (KeyError, TypeError):
            continue
    if len(matches) != 1:
        return dict(status='PROVIDER_ID_UNRESOLVED', candidates_verified=False)
    return dict(status='RESOLVED', provider_fixture_id=provider_id(matches[0], provider), candidates_verified=True)
