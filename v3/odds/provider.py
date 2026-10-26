"""Safe configuration and target contracts for current V4 odds only."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from .contract import MARKETS, timestamp

PROVIDER = 'the_odds_api'
VERSION = '3.2.0'
MAPPING = {'1X2': 'h2h', 'BTTS': 'btts', 'OVER_1_5': 'totals',
           'OVER_2_5': 'totals', 'OVER_3_5': 'totals'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def utc(value):
    dt = timestamp(value)
    if dt is None:
        raise ValueError('invalid_aware_timestamp')
    return dt.astimezone(timezone.utc)


def token(value):
    return isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', value) is not None


@dataclass(frozen=True)
class Config:
    sports: tuple
    regions: tuple = ('eu',)
    bookmakers: tuple = ()
    markets: tuple = tuple(MARKETS)
    timeout: float = 10.0

    def __post_init__(self):
        for values in (self.sports, self.regions, self.bookmakers, self.markets):
            if not isinstance(values, tuple) or len(values) != len(set(values)):
                raise ValueError('invalid_allowlist')
        if (not self.sports or any(not token(s) or not s.startswith('soccer_') for s in self.sports)
                or not self.regions or any(r not in ('eu', 'uk', 'au', 'us', 'us2') for r in self.regions)
                or any(not token(b) for b in self.bookmakers)
                or not self.markets or any(m not in MARKETS for m in self.markets)
                or not 0 < self.timeout <= 120):
            raise ValueError('invalid_config')

    def safe(self):
        return asdict(self)

    def provider_markets(self, markets=None):
        return tuple(sorted({MAPPING[m] for m in (self.markets if markets is None else markets)}))


@dataclass(frozen=True)
class Target:
    internal_match_id: str
    sport_key: str
    competition: str
    season: str
    kickoff_at: str
    home: str
    away: str
    markets: tuple
    priority: str = 'P2'
    external_event_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'kickoff_at', utc(self.kickoff_at).isoformat())
        if (not all(isinstance(v, str) and v.strip() for v in
                    (self.internal_match_id, self.competition, self.season, self.home, self.away))
                or not token(self.sport_key) or not self.sport_key.startswith('soccer_')
                or self.priority not in ('P0', 'P1', 'P2', 'P3')
                or not isinstance(self.markets,tuple) or not self.markets or len(set(self.markets)) != len(self.markets)
                or any(m not in MARKETS for m in self.markets)
                or (self.external_event_id is not None and not token(self.external_event_id))):
            raise ValueError('invalid_target')


def load_targets(rows):
    return [Target(**{**r, 'markets': tuple(r['markets'])}) for r in rows]
