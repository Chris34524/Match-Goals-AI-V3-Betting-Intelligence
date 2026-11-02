"""Bounded GET transport. Every attempted HTTP request, including retries, costs budget."""
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
import time
import requests
from v3.providers.contract import Capture, digest
from v3.flashscore.contract import dumps
from v3.providers.registry import registration
from .schemas import ENDPOINTS, validate

SMOKE_MAX = 3


class AcquisitionError(RuntimeError):
    """Only fixed safe messages escape transport; never provider bodies/exceptions."""

    def __init__(self, message, *, requests_made=0):
        super().__init__(message)
        self.requests_made = requests_made


def now():
    return datetime.now(timezone.utc).isoformat()


def quota_headers(headers):
    headers = {k.lower(): v for k, v in headers.items()}
    result = {}
    for name in ('x-ratelimit-requests-limit', 'x-ratelimit-requests-remaining',
                 'x-ratelimit-limit', 'x-ratelimit-remaining'):
        try:
            value = int(headers[name])
            if value >= 0:
                result[name] = value
        except (KeyError, TypeError, ValueError):
            pass
    return result


class Client:
    def __init__(self, *, live=False, max_requests=None, timeout=15, retries=1):
        reg = registration('api_football')
        if not live:
            raise AcquisitionError('explicit_live_required')
        if not reg.enabled:
            raise AcquisitionError('provider_adapter_not_enabled')
        if not os.environ.get(reg.credential_env):
            raise AcquisitionError('BLOCKED_NO_KEY')
        if type(max_requests) is not int or max_requests < 1:
            raise AcquisitionError('explicit_positive_request_budget_required')
        if not 0 < timeout <= 60 or type(retries) is not int or not 0 <= retries <= 2:
            raise AcquisitionError('invalid_transport_limits')
        self.maximum, self.timeout, self.retries = max_requests, timeout, retries
        self.used = 0
        self.quota = {}
        self.captures = []
        self._base = reg.base_url

    @property
    def remaining(self):
        values = [v for k, v in self.quota.items() if k.endswith('remaining')]
        return min(values) if values else None

    def _guard(self, endpoint):
        left = self.maximum - self.used
        if left <= 0:
            raise AcquisitionError('request_budget_exhausted')
        remaining = self.remaining
        if remaining is not None and left > remaining:
            raise AcquisitionError('budget_exceeds_remaining_quota')
        if remaining is None and self.maximum > SMOKE_MAX and endpoint != '/status':
            raise AcquisitionError('unknown_quota_exceeds_safe_maximum')

    def get(self, endpoint, parameters=None):
        parameters = dict(parameters or {})
        if endpoint not in ENDPOINTS or set(parameters) - ENDPOINTS[endpoint]:
            raise AcquisitionError('endpoint_or_parameters_not_allowed')
        credential = os.environ.get('API_FOOTBALL_KEY')
        if not credential:
            raise AcquisitionError('BLOCKED_NO_KEY')
        if credential in dumps(parameters):
            raise AcquisitionError('credential_in_query_forbidden')
        del credential
        for key, value in parameters.items():
            if key in ('status', 'timezone', 'date', 'from', 'to', 'name', 'country'):
                if not isinstance(value, str) or not value or len(value) > 100 or any(c in value for c in '\r\n?&='):
                    raise AcquisitionError('invalid_query_value')
            elif key == 'h2h':
                import re
                if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*', value):
                    raise AcquisitionError('invalid_h2h_identity')
            elif key == 'half':
                if value not in ('true', 'false'):
                    raise AcquisitionError('invalid_half_parameter')
            elif type(value) is not int or value <= 0:
                raise AcquisitionError('positive_provider_id_required')
        for attempt in range(self.retries + 1):
            self._guard(endpoint)
            self.used += 1
            for key in tuple(self.quota):
                if key.endswith('remaining'):
                    self.quota[key] = max(0, self.quota[key] - 1)
            # Never retain headers/session/key, and never expose chained transport exceptions.
            failed = None
            try:
                response = requests.get(self._base + endpoint, params=parameters,
                    headers={'x-apisports-key': os.environ['API_FOOTBALL_KEY']},
                    timeout=self.timeout, allow_redirects=False)
            except (requests.Timeout, requests.ConnectionError):
                failed = 'transient_transport_error'
            except requests.RequestException:
                failed = 'transport_error'
            if failed:
                if failed == 'transient_transport_error' and attempt < self.retries and self.used < self.maximum:
                    time.sleep(.25 * (attempt + 1))
                    continue
                raise AcquisitionError(failed) from None
            self.quota.update(quota_headers(response.headers))
            if response.status_code == 429:
                raise AcquisitionError('rate_limited')
            if 500 <= response.status_code < 600 and attempt < self.retries and self.used < self.maximum:
                time.sleep(.25 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise AcquisitionError('http_status_rejected')
            invalid = False
            try:
                payload = response.json()
                if os.environ['API_FOOTBALL_KEY'] in dumps(payload):
                    raise ValueError('credential_echo_forbidden')
                validate(payload, endpoint)
            except (ValueError, TypeError, KeyError):
                invalid = True
            if invalid:
                raise AcquisitionError('invalid_provider_response') from None
            if endpoint == '/status':
                usage = payload['response'].get('requests', {})
                if type(usage.get('limit_day')) is int and type(usage.get('current')) is int:
                    self.quota['x-ratelimit-requests-remaining'] = max(0, usage['limit_day'] - usage['current'])
            response_at = None
            try:
                response_at = parsedate_to_datetime(response.headers['Date']).isoformat()
            except (KeyError, ValueError, TypeError, OverflowError):
                pass
            capture = Capture('api_football', endpoint, parameters, now(), response_at,
                              digest(payload), dict(self.quota), True)
            self.captures.append(asdict(capture))
            return payload, capture
        raise AcquisitionError('request_failed')
