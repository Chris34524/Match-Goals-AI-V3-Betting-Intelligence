"""Versioned Lane B market specifications and explicit research policies."""
from dataclasses import asdict, dataclass
from enum import Enum
import math

from .contract import dumps

VERSION = 'fs-targets-1'


class TargetStatus(str, Enum):
    SETTLED = 'SETTLED'
    UNSETTLED = 'UNSETTLED'
    MISSING_OPERAND = 'MISSING_OPERAND'
    SETTLEMENT_INCOMPATIBLE = 'SETTLEMENT_INCOMPATIBLE'
    VOID = 'VOID'
    UNASSESSED = 'UNASSESSED'
    BLOCKED_SOURCE = 'BLOCKED_SOURCE'
    NOT_COVERED = 'NOT_COVERED'


class Outcome(str, Enum):
    WIN = 'WIN'
    LOSS = 'LOSS'
    PUSH = 'PUSH'
    VOID = 'VOID'
    UNSETTLED = 'UNSETTLED'


def evaluate_over(value, line):
    for number in (value, line):
        if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
            raise ValueError('finite nonnegative value and line required')
    if line * 2 != int(line * 2):
        raise ValueError('only integer and half lines supported')
    return Outcome.WIN if value > line else Outcome.PUSH if value == line else Outcome.LOSS


@dataclass(frozen=True)
class CardSettlementPolicy:
    version: str
    operand_rules: str
    yellow_count: int
    direct_red_count: int
    second_yellow_count: int
    second_yellow_policy: str
    bench_scope: bool
    staff_scope: bool

    def __post_init__(self):
        if (not self.version or not self.operand_rules or self.second_yellow_policy != 'exclusive_components'
                or any(type(x) is not int or x < 0 for x in
                       (self.yellow_count, self.direct_red_count, self.second_yellow_count))
                or type(self.bench_scope) is not bool or type(self.staff_scope) is not bool
                or (self.staff_scope and not self.bench_scope)):
            raise ValueError('explicit supported card policy required')

    @property
    def actor_scope(self):
        return 'players_and_staff' if self.staff_scope else 'players_including_bench' if self.bench_scope else 'on_field_players'

    def compatible(self, c):
        return (c.evidence.settlement_rules == self.operand_rules
                and c.evidence.card_actor_scope == self.actor_scope)

    def count(self, value):
        # Input rule must certify yellow excludes the second dismissal caution,
        # direct_red excludes synthetic red representations of second yellows.
        return (value['yellow'] * self.yellow_count + value['direct_red'] * self.direct_red_count
                + value['second_yellow_dismissals'] * self.second_yellow_count)

    def to_dict(self):
        return asdict(self)


RESEARCH_CARDS = CardSettlementPolicy(
    'research-exclusive-cards-v1', 'research-exclusive-components-v1',
    1, 1, 1, 'exclusive_components', False, False)


@dataclass(frozen=True)
class PlayerMarketPolicy:
    version: str
    min_minutes: float
    positions: tuple[str, ...]
    participation_rule: str = 'participated_and_min_minutes'

    def __post_init__(self):
        if (not self.version or type(self.min_minutes) not in (int, float)
                or not math.isfinite(self.min_minutes) or self.min_minutes < 0
                or not self.positions or any(not isinstance(p, str) or not p for p in self.positions)
                or self.participation_rule != 'participated_and_min_minutes'):
            raise ValueError('explicit player eligibility policy required')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class MarketSpec:
    family: str
    market: str
    period: str = 'FT'
    side: str = 'total'
    line: float | None = None
    player_id: str | None = None

    def __post_init__(self):
        allowed = {'goals': ('over', 'btts', '1x2', 'ht_ft'),
                   'corners': ('over', 'most'), 'cards': ('over', 'red'),
                   'shots': ('over',), 'shots_on_target': ('over',), 'player_sot': ('over',)}
        if (self.family not in allowed or self.market not in allowed[self.family]
                or self.period not in ('FT', '1H', '2H') or self.side not in ('total', 'home', 'away')):
            raise ValueError('unsupported market specification')
        if self.market == 'over':
            if self.line is None:
                raise ValueError('over requires line')
            evaluate_over(0, self.line)
        elif self.line is not None:
            raise ValueError('non-line market cannot have line')
        if self.market in ('btts', '1x2', 'ht_ft', 'most', 'red') and self.side != 'total':
            raise ValueError('bilateral market requires total side')
        if self.market == 'ht_ft' and self.period != 'FT':
            raise ValueError('HT/FT has FT scope')
        if self.family in ('shots', 'shots_on_target', 'player_sot') and self.side == 'total':
            raise ValueError('shot markets require an explicit team side')
        if self.family == 'player_sot':
            if not isinstance(self.player_id, str) or not self.player_id.strip() or self.period != 'FT':
                raise ValueError('stable player ID and FT required')
        elif self.player_id is not None:
            raise ValueError('player identity only for player market')
        dumps(asdict(self))


def research_markets(*, shots_lines=(8.5, 10.5), sot_lines=(2.5, 3.5, 4.5)):
    """Explicit research examples; callers can pass their own validated specs."""
    rows = []
    def overs(family, period, side, lines):
        rows.extend(MarketSpec(family, 'over', period, side, line) for line in lines)
    overs('goals', 'FT', 'total', (.5, 1.5, 2.5, 3.5, 4.5))
    for period in ('1H', '2H'):
        overs('goals', period, 'total', (.5, 1.5))
    for period in ('FT', '1H', '2H'):
        rows.append(MarketSpec('goals', 'btts', period))
    rows.extend((MarketSpec('goals', '1x2'), MarketSpec('goals', '1x2', '1H'), MarketSpec('goals', 'ht_ft')))
    overs('corners', 'FT', 'total', (7.5, 8.5, 9.5, 10.5, 11.5))
    overs('corners', '1H', 'total', (3.5, 4.5, 5.5))
    rows.append(MarketSpec('corners', 'most'))
    for period in ('FT', '1H'):
        overs('cards', period, 'total', (2.5, 3.5, 4.5, 5.5))
    rows.append(MarketSpec('cards', 'red'))
    for side in ('home', 'away'):
        overs('goals', 'FT', side, (.5, 1.5))
        overs('corners', 'FT', side, (3.5, 4.5, 5.5))
        overs('cards', 'FT', side, (2.5, 3.5, 4.5, 5.5))
        overs('shots', 'FT', side, shots_lines)
        overs('shots_on_target', 'FT', side, sot_lines)
    return tuple(rows)
