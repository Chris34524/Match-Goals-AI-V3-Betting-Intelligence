"""V4 current odds transport. Errors contain fixed codes only; zero retries."""
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from .provider import PROVIDER, token
from .source_matrix import source_matrix, automatable

BASE = 'https://api.the-odds-api.com/v4'
HEADERS = ('x-requests-remaining', 'x-requests-used', 'x-requests-last')


class ProviderError(RuntimeError):
    def __init__(self, code, *, quota_headers=None):
        super().__init__(code)
        self.quota_headers = quota_headers or {}


def quota_headers(values):
    safe = {}
    for key in HEADERS:
        value = values.get(key) if values is not None else None
        if value is not None and str(value).isdigit():
            safe[key] = int(value)
    return safe


def live_status(live=False):
    if not live:
        return 'blocked_missing_live_flag'
    if not os.environ.get('THE_ODDS_API_KEY', '').strip():
        return 'blocked_missing_credentials'
    if not any(automatable(r) for r in source_matrix(provider=PROVIDER)):
        return 'blocked_source_authorization'
    return 'live_enabled'


def authorize(live, markets):
    from .contract import MARKETS
    if not markets or not set(markets) <= set(MARKETS):
        raise ProviderError('blocked_market_authorization')
    status = live_status(live)
    if status != 'live_enabled':
        raise ProviderError(status)
    if not any(automatable(r) and set(markets) <= set(r['markets'])
               for r in source_matrix(provider=PROVIDER)):
        raise ProviderError('blocked_market_authorization')


def assert_safe_payload(value):
    """Reject credentials instead of persisting/redacting a response with secrets."""
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
    secret = os.environ.get('THE_ODDS_API_KEY')
    if (secret and secret in serialized) or any(s in serialized.casefold() for s in
            ('apikey', 'api_key', 'authorization', 'the_odds_api_key')):
        raise ProviderError('unsafe_payload')


def validate_response(payload, event_id=None):
    events = [payload] if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        raise ProviderError('unexpected_schema')
    for event in events:
        if (not isinstance(event, dict) or not all(isinstance(event.get(k), str) and event[k]
                for k in ('id', 'sport_key', 'commence_time', 'home_team', 'away_team'))
                or not isinstance(event.get('bookmakers'), list)):
            raise ProviderError('unexpected_schema')
        if event_id is not None and event['id'] != event_id:
            raise ProviderError('unexpected_event')
        for book in event['bookmakers']:
            if not isinstance(book, dict) or not token(book.get('key')) or not isinstance(book.get('markets'), list):
                raise ProviderError('unexpected_schema')
            for market in book['markets']:
                if not isinstance(market, dict) or not isinstance(market.get('key'), str) or not isinstance(market.get('outcomes'), list):
                    raise ProviderError('unexpected_schema')
                if any(not isinstance(o, dict) or not isinstance(o.get('name'), str) or 'price' not in o for o in market['outcomes']):
                    raise ProviderError('unexpected_schema')
    return events


class TheOddsAPI:
    def __init__(self, config, transport=None):
        self.config = config
        self._transport = transport or urlopen

    def fetch(self, sport, markets, *, event_id=None, event_ids=(), live=False):
        authorize(live, markets)
        if (sport not in self.config.sports or not set(markets) <= set(self.config.markets)
                or any(not token(e) for e in event_ids)
                or (event_id is not None and not token(event_id))):
            raise ProviderError('request_outside_allowlist')
        mapped = self.config.provider_markets(markets)
        if 'btts' in mapped and event_id is None:
            raise ProviderError('btts_requires_event_endpoint')
        if event_id is None and not event_ids:
            raise ProviderError('explicit_targets_required')
        path = f'/sports/{sport}' + (f'/events/{event_id}/odds' if event_id else '/odds')
        params = dict(apiKey=os.environ['THE_ODDS_API_KEY'], regions=','.join(self.config.regions),
                      markets=','.join(mapped), oddsFormat='decimal', dateFormat='iso')
        if self.config.bookmakers:
            params['bookmakers'] = ','.join(self.config.bookmakers)
        if event_ids and event_id is None:
            params['eventIds'] = ','.join(sorted(set(event_ids)))
        error = None
        payload = None
        headers = {}
        try:
            with self._transport(BASE + path + '?' + urlencode(params), timeout=self.config.timeout) as response:
                headers = quota_headers(response.headers)
                status = getattr(response, 'status', 200)
                if status != 200:
                    raise ProviderError('http_' + str(status))
                for key in HEADERS:
                    value = response.headers.get(key)
                    if value is not None:
                        if not str(value).isdigit():
                            raise ProviderError('invalid_quota_header')
                        headers[key] = int(value)
                body = response.read()
                if not body.strip():
                    raise ProviderError('empty_response')
                payload = json.loads(body)
        except HTTPError as exc:
            headers = quota_headers(exc.headers)
            error = 'http_' + str(exc.code) if exc.code in (400, 401, 403, 404, 422, 429) or 500 <= exc.code <= 599 else 'http_error'
        except (TimeoutError, socket.timeout):
            error = 'timeout'
        except (URLError, OSError):
            error = 'network_error'
        except (ValueError, UnicodeError):
            error = 'invalid_json'
        except ProviderError as exc:
            code = str(exc)
            error = code if code in ('invalid_quota_header','empty_response') or code.startswith('http_') and code[5:].isdigit() else 'transport_error'
        except Exception:
            error = 'transport_error'
        # Outside exception handler: no sensitive chained transport exception.
        if error:
            raise ProviderError(error, quota_headers=headers)
        validation_error = None
        try:
            assert_safe_payload(payload)
            validate_response(payload, event_id)
        except ProviderError as exc:
            validation_error = str(exc)
        except (ValueError, TypeError):
            validation_error = 'invalid_json'
        if validation_error:
            raise ProviderError(validation_error, quota_headers=headers)
        return payload, headers
