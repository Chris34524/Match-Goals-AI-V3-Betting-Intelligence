"""Reviewed adapter registry; no caller-supplied authorization grant."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderRegistration:
    provider: str
    enabled: bool
    base_url: str
    credential_env: str
    authorization_mode: str
    reuse_scope: str


API_FOOTBALL = ProviderRegistration('api_football', True,
    'https://v3.football.api-sports.io', 'API_FOOTBALL_KEY',
    'authenticated_official_api_account_terms',
    'subscription/quota bound; account terms govern retention/reuse; redistribution unverified')


def registration(provider):
    if provider != API_FOOTBALL.provider:
        raise ValueError('provider_adapter_not_enabled')
    return API_FOOTBALL
