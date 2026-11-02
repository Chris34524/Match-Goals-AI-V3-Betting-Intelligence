"""Capture accreditation is separate from historical feature or training accreditation."""
from v3.flashscore.contract import State, timestamp
from .adapter import Adapter, verify_capture
from .parser import parse_fixture


def assess(observation, fixture_payload, fixture_capture, statistics_payload, statistics_capture):
    reasons = []
    try:
        verify_capture(fixture_payload, fixture_capture, '/fixtures')
        verify_capture(statistics_payload, statistics_capture, '/fixtures/statistics')
        matches = [parse_fixture(r)[0] for r in fixture_payload['response']
                   if str(r['fixture']['id']) == observation.request.fixture.match_id]
        if matches != [observation.request.fixture]:
            reasons.append('identity_not_resolved')
        if statistics_capture.parameters.get('fixture') != int(observation.request.fixture.match_id):
            reasons.append('statistics_fixture_mismatch')
        timestamp(fixture_capture.captured_at)
        timestamp(statistics_capture.captured_at)
        replay = Adapter().normalize(fixture_payload, statistics_payload, fixture_capture, statistics_capture)
        if not any(c.to_dict() == observation.to_dict() for c in replay):
            reasons.append('observation_does_not_match_capture_replay')
    except (ValueError, KeyError, TypeError):
        reasons.append('invalid_capture_or_identity')
    if not fixture_capture.live or not statistics_capture.live:
        reasons.append('offline_not_real')
    if observation.state != State.AVAILABLE:
        reasons.append('capability_not_available')
    if observation.inspection_decision is not None:
        reasons.append('period_or_identity_unverified')
    return dict(capture_accredited=not reasons, reasons=sorted(set(reasons)),
                historical_asof_accredited=False, real_model_training='BLOCKED')
