"""Zero-credit metadata discovery only. No odds paths, redirects or retries."""
import json
import os
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from .provider import token, utc
from .the_odds_api import BASE, ProviderError, assert_safe_payload, live_status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_sports(payload):
    assert_safe_payload(payload)
    if not isinstance(payload, list):
        raise ProviderError('unexpected_schema')
    seen = set()
    for row in payload:
        if (not isinstance(row, dict)
                or not {'key', 'group', 'title', 'active'} <= row.keys()
                or row.keys() - {'key', 'group', 'title', 'active', 'description', 'has_outrights'}
                or not token(row['key'])
                or any(not isinstance(row[k], str) or not row[k].strip() for k in ('group', 'title'))
                or type(row['active']) is not bool
                or ('description' in row and not isinstance(row['description'], str))
                or ('has_outrights' in row and type(row['has_outrights']) is not bool)):
            raise ProviderError('unexpected_schema')
        if row['key'] in seen:
            raise ProviderError('duplicate_sport')
        seen.add(row['key'])
    return payload


def validate_events(payload, sport, allowlist):
    assert_safe_payload(payload)
    if not token(sport) or not sport.startswith('soccer_') or sport not in allowlist:
        raise ProviderError('invalid_sport')
    if not isinstance(payload, list):
        raise ProviderError('unexpected_schema')
    seen = set()
    fields = {'id', 'sport_key', 'commence_time', 'home_team', 'away_team'}
    for row in payload:
        if (not isinstance(row, dict) or not fields <= row.keys()
                or row.keys() - (fields | {'sport_title'})
                or any(not isinstance(row[k], str) or not row[k].strip() for k in fields)
                or ('sport_title' in row and not isinstance(row['sport_title'], str))):
            raise ProviderError('unexpected_schema')
        if not token(row['id']):
            raise ProviderError('invalid_event_id')
        if row['sport_key'] != sport:
            raise ProviderError('invalid_sport')
        invalid = False
        try:
            utc(row['commence_time'])
        except (ValueError, TypeError):
            invalid = True
        if invalid:
            raise ProviderError('invalid_kickoff')
        if row['home_team'] == row['away_team']:
            raise ProviderError('invalid_teams')
        if row['id'] in seen:
            raise ProviderError('duplicate_event')
        seen.add(row['id'])
    return payload


class Discovery:
    def __init__(self, sports=(), *, transport=None, timeout=10):
        if (not isinstance(sports, tuple) or len(sports) != len(set(sports))
                or any(not token(s) or not s.startswith('soccer_') for s in sports)
                or not 0 < timeout <= 120):
            raise ProviderError('invalid_config')
        self.sports = sports
        self.timeout = timeout
        self._transport = transport or build_opener(NoRedirect()).open

    def _get(self, sport=None):
        status = live_status(True)
        if status != 'live_enabled':
            raise ProviderError(status)
        if sport is not None and sport not in self.sports:
            raise ProviderError('invalid_sport')
        path = '/sports' if sport is None else f'/sports/{sport}/events'
        error = None
        payload = None
        try:
            with self._transport(BASE + path + '?' + urlencode({'apiKey': os.environ['THE_ODDS_API_KEY']}), timeout=self.timeout) as response:
                if response.status != 200:
                    error = 'http_error'
                else:
                    payload = json.loads(response.read())
        except HTTPError:
            error = 'http_error'
        except (URLError, OSError):
            error = 'network_error'
        except (ValueError, UnicodeError):
            error = 'invalid_json'
        except Exception:
            error = 'transport_error'
        # Raise outside handler so credential-bearing exceptions are never chained.
        if error:
            raise ProviderError(error)
        return validate_sports(payload) if sport is None else validate_events(payload, sport, self.sports)

    def sports_list(self):
        return self._get()

    def events(self, sport):
        return self._get(sport)

    def validate_key(self):
        self.sports_list()
        return {'status': 'valid', 'provider': 'the_odds_api'}


def reconcile_pilot(events, targets, policy, *, now):
    """Require one pair globally, with unique internal and external identities."""
    if len({t.internal_match_id for t in targets}) != len(targets):
        raise ProviderError('ambiguous_reconciliation')
    pairs = []
    for event in events:
        validate_events([event], event.get('sport_key'), tuple(policy.competition_mapping))
        if utc(event['commence_time']) <= utc(now):
            continue
        target, audit = policy.reconcile(event, targets)
        if audit['status'] == 'AMBIGUOUS':
            raise ProviderError('ambiguous_reconciliation')
        if target is not None and utc(target.kickoff_at) > utc(now):
            pairs.append((target, event['id']))
    if len(pairs) != 1 or len({e['id'] for e in events}) != len(events):
        raise ProviderError('ambiguous_reconciliation' if pairs else 'no_reconciled_target')
    from dataclasses import replace
    return replace(pairs[0][0], external_event_id=pairs[0][1])
