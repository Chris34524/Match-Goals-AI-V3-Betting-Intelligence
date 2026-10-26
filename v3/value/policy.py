"""Versioned synthetic defaults, never tuned against outcomes or returns."""
from dataclasses import dataclass, asdict
from v3.odds.contract import MARKETS, finite, nonempty


@dataclass(frozen=True)
class MarketPolicy:
    safety_margin: float = .05
    min_ev: float = .05
    min_absolute_edge: float = .02
    min_relative_edge: float = .05

    def __post_init__(self):
        # Bounded V1 policy space; 100% maximum is a validation bound, not tuning.
        for value in asdict(self).values():
            if not finite(value) or not 0 <= value <= 1:
                raise ValueError('invalid_policy_threshold')


@dataclass(frozen=True)
class Policy:
    policy_id: str
    policy_version: str
    markets: tuple

    def __post_init__(self):
        if not nonempty(self.policy_id) or not nonempty(self.policy_version):
            raise ValueError('invalid_policy_identity')
        if not isinstance(self.markets, tuple) or len(self.markets) != len(MARKETS):
            raise ValueError('invalid_policy_markets')
        if {k for k, _ in self.markets} != set(MARKETS) or not all(isinstance(v, MarketPolicy) for _, v in self.markets):
            raise ValueError('invalid_policy_markets')

    def for_market(self, market):
        return dict(self.markets)[market]

    def to_dict(self):
        return dict(policy_id=self.policy_id, policy_version=self.policy_version,
                    markets={k: asdict(v) for k, v in self.markets})

    @classmethod
    def from_dict(cls, config):
        if set(config) != {'policy_id', 'policy_version', 'markets'} or set(config['markets']) != set(MARKETS):
            raise ValueError('invalid_policy_config')
        return cls(config['policy_id'], config['policy_version'],
                   tuple((k, MarketPolicy(**config['markets'][k])) for k in sorted(MARKETS)))


def default_policy():
    return Policy('synthetic-conservative', '4.2.0', tuple((k, MarketPolicy()) for k in sorted(MARKETS)))
