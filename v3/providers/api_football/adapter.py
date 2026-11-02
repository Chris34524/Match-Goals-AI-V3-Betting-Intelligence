"""API-Football → FS-1 capabilities; preserves conservative FS-4/FS-5 gates."""
from dataclasses import asdict
from v3.flashscore.contract import Capability, Evidence, Request
from v3.flashscore.normalization import unit_for
from v3.providers.contract import digest
from . import VERSION
from .normalization import LABELS, number
from .parser import parse_fixture, stable_id, context_rows
from .schemas import validate

SURFACES = {'FT': 'stats_overall', '1H': 'stats_first_half', '2H': 'stats_second_half'}


def verify_capture(payload, capture, endpoint):
    if capture.provider != 'api_football' or capture.endpoint != endpoint or capture.payload_sha256 != digest(payload):
        raise ValueError('capture_provenance_mismatch')
    validate(payload, endpoint)


def capability(fixture, capture, field, period, side, value, *, label=None, scope='regulation', reason=None):
    surface = 'summary' if field.startswith('goals_') else SURFACES[period]
    team = getattr(fixture, side + '_id')
    evidence = Evidence(capture.captured_at, 'https://v3.football.api-sports.io' + capture.endpoint,
        'official_api_json' if capture.live else 'deterministic_offline_fixture',
        inspected_fixture=fixture, inspected_surface=surface, selected_period=period,
        selected_period_evidence='provider_explicit_' + period, period_evidence_method='structured_period',
        inspected_entity_id=team, inspected_side=side, inspection='success', expected_covered=True,
        acquisition_authorization='verified' if capture.live else 'unverified',
        acquisition_mode='live' if capture.live else 'offline', value=value, unit=unit_for(field),
        null_reason=reason or ('absent_value' if value is None else None), score_scope=scope,
        parser_version=VERSION, sample_reference=digest(dict(capture=asdict(capture), raw_label=label)),
        # A current capture does not certify historical publication or revision lineage.
        evidence_quality='provider_capture_no_historical_asof' if capture.live else 'synthetic')
    return Capability(Request(fixture, surface, period, field, 'team', side, team), evidence)


class Adapter:
    provider = 'api_football'

    def __init__(self):
        self.provenance = []

    def normalize(self, fixture_payload, statistics_payload, fixture_capture, statistics_capture):
        self.provenance = []
        verify_capture(fixture_payload, fixture_capture, '/fixtures')
        verify_capture(statistics_payload, statistics_capture, '/fixtures/statistics')
        candidates = [row for row in fixture_payload['response']
                      if row['fixture']['id'] == statistics_capture.parameters.get('fixture')]
        if len(candidates) != 1:
            raise ValueError('exactly_one_matching_fixture_required')
        fixture, metadata = parse_fixture(candidates[0])
        if 'id' in fixture_capture.parameters and fixture_capture.parameters['id'] != int(fixture.match_id):
            raise ValueError('fixture_capture_query_identity_mismatch')
        if statistics_capture.parameters.get('fixture') != int(fixture.match_id):
            raise ValueError('wrong_fixture_identity')
        rows = statistics_payload['response']
        by_team = {}
        for row in rows:
            team = stable_id(row['team']['id'])
            if team not in (fixture.home_id, fixture.away_id) or team in by_team:
                raise ValueError('duplicate_or_wrong_team_identity')
            by_team[team] = row
        result = []
        # Extra-time totals may include 120 minutes; do not settle regulation stats from them.
        stats_scope = 'regulation' if metadata['status'] == 'FT' else 'unknown'
        for side in ('home', 'away'):
            team = getattr(fixture, side + '_id')
            block = by_team.get(team, {})
            periods = [('FT', 'statistics')]
            if statistics_capture.parameters.get('half') == 'true':
                periods += [('1H', 'statistics_1h'), ('2H', 'statistics_2h')]
            for period, key in periods:
                values, unknown = {}, []
                if key in block and not isinstance(block[key], list):
                    raise ValueError('invalid_statistic_array')
                for stat in block.get(key, []):
                    if not isinstance(stat, dict) or not isinstance(stat.get('type'), str) or 'value' not in stat:
                        raise ValueError('invalid_statistic_row')
                    label = stat['type']
                    field = LABELS.get(label)
                    if field is None:
                        unknown.append(dict(raw_label=label, raw_value=stat['value']))
                    elif field in values:
                        raise ValueError('duplicate_statistic_type')
                    else:
                        values[field] = (label, stat['value'])
                for field in LABELS.values():
                    label, raw = values.get(field, (None, None))
                    value = number(raw, field)
                    reason = ('period_not_provided' if key not in block else
                              'invalid_numeric_value' if raw is not None and value is None else None)
                    c = capability(fixture, statistics_capture, field, period, side, value,
                        label=label, scope=stats_scope if period != '1H' else 'regulation', reason=reason)
                    result.append(c)
                    self.provenance.append(dict(sample_reference=c.evidence.sample_reference, capability_key=list(c.request.key), raw_label=label,
                        raw_value=raw, unknown_labels=unknown, capture=asdict(statistics_capture),
                        fixture=metadata, parser_version=VERSION))
                # Totals do not certify exclusive direct-red/second-yellow/actor semantics.
                card = capability(fixture, statistics_capture, 'cards', period, side, None,
                    scope=stats_scope, reason='typed_card_components_and_actor_scope_unverified')
                result.append(card)
                self.provenance.append(dict(sample_reference=card.evidence.sample_reference, capability_key=list(card.request.key),
                    raw_label='Yellow Cards / Red Cards (not exclusive components)', raw_value=None,
                    capture=asdict(statistics_capture), fixture=metadata, parser_version=VERSION))
            for period, score_key, field in (('FT', 'fulltime', 'goals_ft'), ('1H', 'halftime', 'goals_first_half')):
                score = metadata['scores'].get(score_key) or {}
                raw = score.get(side)
                c = capability(fixture, fixture_capture, field, period, side, number(raw, field))
                result.append(c)
                self.provenance.append(dict(sample_reference=c.evidence.sample_reference, capability_key=list(c.request.key), raw_label=score_key,
                    raw_value=raw, capture=asdict(fixture_capture), fixture=metadata, parser_version=VERSION))
        return sorted(result, key=lambda c: c.request.key)

    def events(self, payload, fixture, capture):
        verify_capture(payload, capture, '/fixtures/events')
        return context_rows(payload, '/fixtures/events', fixture, capture)

    def lineups(self, payload, fixture, capture):
        verify_capture(payload, capture, '/fixtures/lineups')
        return context_rows(payload, '/fixtures/lineups', fixture, capture)
