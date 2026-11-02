"""Small explicit validators for consumed provider response shapes."""
ENDPOINTS = {
    '/fixtures': {'id', 'date', 'league', 'season', 'status', 'timezone', 'last', 'from', 'to'},
    '/fixtures/statistics': {'fixture', 'half'},
    '/fixtures/events': {'fixture'}, '/fixtures/lineups': {'fixture'},
    '/standings': {'league', 'season'}, '/leagues': {'id', 'name', 'country', 'season'},
    '/fixtures/headtohead': {'h2h'},
    '/fixtures/players': {'fixture'},
    '/status': set(),
}


def validate(payload, endpoint):
    if endpoint not in ENDPOINTS or not isinstance(payload, dict):
        raise ValueError('invalid_provider_envelope')
    if payload.get('errors') not in ([], {}):
        raise ValueError('provider_reported_error')
    response = payload.get('response')
    if endpoint == '/status':
        if not isinstance(response, dict):
            raise ValueError('invalid_status_schema')
    else:
        if not isinstance(response, list) or any(not isinstance(row, dict) for row in response):
            raise ValueError('invalid_response_schema')
        if type(payload.get('results')) is not int or payload['results'] != len(response):
            raise ValueError('invalid_results_count')
        for row in response:
            required = {'/fixtures': ('fixture', 'league', 'teams', 'score'),
                        '/fixtures/statistics': ('team', 'statistics'),
                        '/fixtures/events': ('time', 'team', 'player', 'type', 'detail'),
                        '/fixtures/lineups': ('team', 'startXI', 'substitutes'),
                        '/fixtures/headtohead': ('fixture', 'league', 'teams', 'score'),
                        '/fixtures/players': ('team', 'players'),
                        '/standings': ('league',), '/leagues': ('league', 'country', 'seasons')}[endpoint]
            if any(key not in row for key in required):
                raise ValueError('incomplete_response_schema')
    return response
