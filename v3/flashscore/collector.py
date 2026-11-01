"""Offline collector with an exact-method, exact-family authorization boundary."""
from v3.features.source_matrix import source_matrix
from .contract import Capability, Evidence
from .parser import StructuredParser


def live_authorized(provider, method, family):
    # Reuse the repository registry, with no caller-supplied grant or mutable override.
    return any(row['provider'] == provider and row['signal_family'] == family
               and row['allowed_method'] == method and method == 'permitted_ingestion'
               and row['authorization_status'] == 'verified' and row['status'] == 'available'
               for row in source_matrix())


def collect_replay(requests, samples, parser=None):
    parser = parser or StructuredParser()
    return [parser.parse(request, sample) for request, sample in zip(requests, samples, strict=True)]


def collect_live(request, *, method, family, observed_at, source_url):
    allowed = live_authorized(request.fixture.provider, method, family)
    evidence = Evidence(observed_at, source_url, 'authorization_gate', acquisition_mode='live',
                        acquisition_authorization='verified' if allowed else 'blocked',
                        access_blocked_reason='live_transport_not_implemented' if allowed else
                        'source_matrix_has_no_exact_provider_method_family_grant')
    # No transport, retries, or network imports. A future grant still needs a reviewed adapter.
    return Capability(request, evidence)
