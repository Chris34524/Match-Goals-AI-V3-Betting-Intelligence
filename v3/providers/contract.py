"""Provider-neutral capture, identity and adapter contracts."""
from dataclasses import dataclass
from typing import Protocol
from hashlib import sha256
from v3.flashscore.contract import Capability, dumps, timestamp

VERSION = 'provider-capture-1'


def digest(payload):
    return sha256(dumps(payload).encode()).hexdigest()


@dataclass(frozen=True)
class Identity:
    provider: str
    entity_type: str
    provider_entity_id: str
    normalized_name: str
    competition_context: str

    def __post_init__(self):
        if self.entity_type not in ('fixture', 'team', 'competition', 'player') or any(
                not isinstance(v, str) or not v.strip() for v in vars(self).values()):
            raise ValueError('unresolved provider identity')


@dataclass(frozen=True)
class Capture:
    provider: str
    endpoint: str
    parameters: dict
    captured_at: str
    response_at: str | None
    payload_sha256: str
    quota: dict
    live: bool = False

    def __post_init__(self):
        timestamp(self.captured_at)
        if len(self.payload_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.payload_sha256):
            raise ValueError('invalid payload digest')
        dumps(vars(self))


class ProviderAdapter(Protocol):
    provider: str

    def normalize(self, fixture_payload: dict, statistics_payload: dict,
                  fixture_capture: Capture, statistics_capture: Capture) -> list[Capability]: ...
