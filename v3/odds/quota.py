"""Conservative upper bounds and a locked monthly reservation ledger.

Unknown/failed response costs retain the full reservation. No automatic retries.
"""
from dataclasses import dataclass
from contextlib import contextmanager
import json
import math
from .provider import utc
from .storage import safe_root, encoded


@dataclass(frozen=True)
class Budget:
    monthly_hard_limit: int = 500
    monthly_soft_limit: int = 450
    max_credits_per_run: int = 30

    def __post_init__(self):
        if any(type(v) is not int for v in (self.monthly_hard_limit,self.monthly_soft_limit,self.max_credits_per_run)):
            raise ValueError('invalid_budget')
        if not (0 <= self.monthly_soft_limit < self.monthly_hard_limit
                and 0 < self.max_credits_per_run <= self.monthly_hard_limit):
            raise ValueError('invalid_budget')

    def check(self, estimated_cost, credits_used_local=0, credits_remaining_provider=None):
        if (any(type(v) is not int or v < 0 for v in (estimated_cost,credits_used_local))
                or (credits_remaining_provider is not None
                    and (type(credits_remaining_provider) is not int or credits_remaining_provider < 0))):
            raise ValueError('invalid_cost')
        if estimated_cost > self.max_credits_per_run:
            return 'max_credits_per_run'
        if credits_used_local + estimated_cost > self.monthly_hard_limit:
            return 'monthly_hard_limit'
        if credits_remaining_provider is not None and estimated_cost > credits_remaining_provider:
            return 'provider_remaining'
        if credits_used_local + estimated_cost > self.monthly_soft_limit:
            return 'monthly_soft_limit'
        return None


def estimate(config, markets, calls=1):
    if type(calls) is not int or calls < 0:
        raise ValueError('invalid_calls')
    regions = math.ceil(len(config.bookmakers) / 10) if config.bookmakers else len(config.regions)
    return regions * len(config.provider_markets(markets)) * calls


@contextmanager
def ledger(root, observed_at):
    """Hold lock through request; reserve before network, survive failure/crash."""
    import fcntl
    root = safe_root(root) / 'quota'
    root.mkdir(parents=True, exist_ok=True)
    month = utc(observed_at).strftime('%Y-%m')
    with (root / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        entries = [json.loads(line) for line in (root / 'ledger.jsonl').read_text().splitlines()] if (root / 'ledger.jsonl').exists() else []
        if any(type(e.get('reserved')) is not int or e['reserved'] < 0
               or not isinstance(e.get('month'),str)
               or (e.get('remaining') is not None and (type(e['remaining']) is not int or e['remaining'] < 0))
               for e in entries):
            raise ValueError('invalid_quota_ledger')
        used = sum(e['reserved'] for e in entries if e['month'] == month)
        remaining = None
        for entry in entries:
            if entry['month'] != month:
                continue
            if remaining is not None:
                remaining = max(0, remaining - entry['reserved'])
            if entry.get('remaining') is not None:
                remaining = min(remaining, entry['remaining']) if remaining is not None else entry['remaining']
        state = {'used': used, 'remaining': remaining}

        def reserve(cost):
            with (root / 'ledger.jsonl').open('ab') as out:
                out.write(json.dumps({'month': month, 'reserved': cost, 'observed_at': observed_at}).encode() + b'\n')
                out.flush()
                import os
                os.fsync(out.fileno())

        def headers(values):
            # Reservations remain conservative; provider used can reflect other clients.
            provider_used = values.get('x-requests-used', 0)
            correction = max(0, provider_used - used - state.get('cost', 0))
            with (root / 'ledger.jsonl').open('ab') as out:
                out.write(json.dumps({'month': month, 'reserved': correction,
                                      'remaining': values.get('x-requests-remaining')}).encode() + b'\n')
        yield state, reserve, headers
