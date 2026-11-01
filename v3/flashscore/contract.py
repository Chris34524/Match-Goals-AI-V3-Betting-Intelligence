"""Capability facts and fail-closed interpretation. No acquisition or feature adapter."""
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import json
import math

from v3.data.temporal import sample_reasons
from . import VERSION


class State(str, Enum):
    AVAILABLE = 'AVAILABLE'
    MISSING = 'MISSING'
    NOT_COVERED = 'NOT_COVERED'
    BLOCKED = 'BLOCKED'
    UNKNOWN = 'UNKNOWN'


PERIODS = ('FT', '1H', '2H')
LIFECYCLES = ('scheduled', 'live', 'finished', 'postponed', 'cancelled', 'abandoned')
SURFACES = ('summary', 'stats_overall', 'stats_first_half', 'stats_second_half',
            'events', 'lineups', 'standings', 'h2h', 'player_stats')
METRICS = tuple('goals_ft goals_first_half goals_second_half corners cards fouls shots '
    'shots_on_target shots_off_target blocked_shots shots_inside_box shots_outside_box '
    'xg xgot xa big_chances big_chances_scored big_chances_missed box_touches possession '
    'passes completed_passes pass_accuracy final_third_passes long_balls crosses key_passes '
    'offsides free_kicks throw_ins duels tackles interceptions clearances errors_leading_shot '
    'errors_leading_goal goalkeeper_saves xgot_faced goals_prevented'.split())
CAPABILITIES = SURFACES + METRICS
DECIMALS = ('xg', 'xgot', 'xa', 'xgot_faced', 'goals_prevented')
PERCENTAGES = ('possession', 'pass_accuracy')


def dumps(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'))


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must have an explicit timezone')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp must have an explicit timezone')
    return parsed


@dataclass(frozen=True)
class Fixture:
    provider: str
    match_id: str
    competition_id: str
    season: str
    stage: str
    lifecycle: str
    home_id: str
    away_id: str
    match_date: str | None = None
    competition_tier: str = 'unknown'
    archive_age: str = 'unknown'

    def __post_init__(self):
        for key in ('provider', 'match_id', 'competition_id', 'season', 'stage', 'home_id', 'away_id', 'competition_tier', 'archive_age'):
            if not isinstance(getattr(self, key), str) or not getattr(self, key).strip():
                raise ValueError('unresolved fixture ' + key)
        if self.lifecycle not in LIFECYCLES or self.home_id == self.away_id:
            raise ValueError('invalid fixture lifecycle/orientation')

    @property
    def identity(self):
        return tuple(getattr(self, key) for key in
                     ('provider', 'match_id', 'competition_id', 'season', 'stage', 'home_id', 'away_id'))


@dataclass(frozen=True)
class Request:
    fixture: Fixture
    surface: str
    period: str
    capability_name: str
    level: str = 'team'
    side: str | None = None
    entity_id: str | None = None

    def __post_init__(self):
        if self.surface not in SURFACES or self.period not in PERIODS or self.capability_name not in CAPABILITIES:
            raise ValueError('unknown surface, period or capability')
        if self.level not in ('match', 'team', 'player'):
            raise ValueError('unknown level')
        if self.level in ('team', 'player'):
            if self.side not in ('home', 'away') or not isinstance(self.entity_id, str) or not self.entity_id.strip():
                raise ValueError('explicit orientation and entity required')
            if self.level == 'team' and self.entity_id != getattr(self.fixture, self.side + '_id'):
                raise ValueError('team identity conflicts with orientation')
        elif self.capability_name not in SURFACES:
            raise ValueError('numeric capabilities require an oriented team or player')
        elif self.side is not None or self.entity_id is not None:
            raise ValueError('match level has no side/entity')
        expected = {'stats_overall': 'FT', 'stats_first_half': '1H', 'stats_second_half': '2H',
                    'goals_ft': 'FT', 'goals_first_half': '1H', 'goals_second_half': '2H'}
        if any(expected.get(x, self.period) != self.period for x in (self.surface, self.capability_name)):
            raise ValueError('inconsistent requested period')
        if self.capability_name not in SURFACES:
            allowed = ('player_stats',) if self.level == 'player' else ('summary',) if self.capability_name.startswith('goals_') else ('stats_overall', 'stats_first_half', 'stats_second_half')
            if self.surface not in allowed:
                raise ValueError('capability not implemented on requested surface/level')
        if self.capability_name in SURFACES and (self.capability_name != self.surface or self.level != 'match'):
            raise ValueError('surface capability must be match-level on its own surface')

    @property
    def key(self):
        return (self.fixture.provider, self.fixture.match_id, self.capability_name,
                self.period, self.level, self.side or '', self.entity_id or '')


@dataclass(frozen=True)
class Evidence:
    observed_at: str
    source_url: str
    evidence_method: str
    inspected_fixture: Fixture | None = None
    inspected_surface: str | None = None
    selected_period: str | None = None
    selected_period_evidence: str | None = None
    period_evidence_method: str | None = None
    inspected_entity_id: str | None = None
    inspected_side: str | None = None
    inspection: str = 'not_inspected'
    expected_covered: bool = False
    noncoverage_reference: str | None = None
    noncoverage_method: str | None = None
    access_blocked_reason: str | None = None
    acquisition_authorization: str = 'unverified'
    acquisition_mode: str = 'offline'
    value: object = None
    unit: str | None = None
    null_reason: str | None = None
    score_scope: str = 'unknown'
    raw_or_derived: str = 'raw'
    operand_references: tuple[str, ...] = ()
    publication_at: str | None = None
    revision_at: str | None = None
    publication_verified: bool = False
    revision_history_verified: bool = False
    parser_version: str = VERSION
    sample_reference: str | None = None
    evidence_quality: str = 'unassessed'
    settlement_rules: str | None = None
    card_actor_scope: str | None = None

    def __post_init__(self):
        timestamp(self.observed_at)
        for key in ('expected_covered', 'publication_verified', 'revision_history_verified'):
            if type(getattr(self, key)) is not bool:
                raise ValueError('evidence flags must be explicit booleans')
        for value in (self.publication_at, self.revision_at):
            if value is not None:
                timestamp(value)
        for key in ('source_url', 'evidence_method', 'parser_version', 'evidence_quality'):
            if not isinstance(getattr(self, key), str) or not getattr(self, key).strip():
                raise ValueError('source, parser and quality provenance must be strings')
        for key in ('inspected_surface', 'selected_period', 'selected_period_evidence',
                    'period_evidence_method', 'inspected_entity_id', 'inspected_side',
                    'noncoverage_reference', 'noncoverage_method', 'access_blocked_reason',
                    'unit', 'null_reason', 'sample_reference', 'settlement_rules', 'card_actor_scope'):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError('optional evidence text must be a nonempty string or null')
        if not isinstance(self.operand_references, tuple) or any(not isinstance(x, str) or not x for x in self.operand_references):
            raise ValueError('operand references must be a tuple of strings')
        if self.acquisition_mode not in ('offline', 'live') or self.acquisition_authorization not in ('unverified', 'blocked', 'verified'):
            raise ValueError('invalid acquisition dimensions')
        if self.inspection not in ('not_inspected', 'success', 'shell', 'timeout', 'error'):
            raise ValueError('invalid inspection')
        if self.score_scope not in ('regulation', 'extra_time', 'shootout', 'including_extra_time', 'unknown'):
            raise ValueError('invalid score scope')
        if self.raw_or_derived not in ('raw', 'derived'):
            raise ValueError('invalid derivation')
        dumps(asdict(self))  # Reject NaN/infinity, including in nested typed payloads.


def valid_value(name, value, unit):
    if name in SURFACES:
        return isinstance(value, dict) and value.get('validated') is True and unit == 'surface'
    if name == 'cards':
        required = {'yellow', 'direct_red', 'second_yellow_dismissals'}
        return (isinstance(value, dict) and set(value) == required and unit == 'typed_cards'
                and all(type(x) is int and x >= 0 for x in value.values()))
    if type(value) not in (int, float) or not math.isfinite(value):
        return False
    if name in PERCENTAGES:
        return unit == 'percent' and 0 <= value <= 100
    if name in DECIMALS:
        return unit == 'expected_goals' and (value >= 0 or name == 'goals_prevented')
    return unit == 'count' and type(value) is int and value >= 0


@dataclass(frozen=True)
class Capability:
    request: Request
    evidence: Evidence

    @property
    def inspection_decision(self):
        r, e = self.request, self.evidence
        if e.access_blocked_reason or (e.acquisition_mode == 'live' and e.acquisition_authorization != 'verified'):
            return State.BLOCKED, e.access_blocked_reason or 'acquisition_not_authorized'
        if e.inspection != 'success':
            return State.UNKNOWN, e.null_reason or e.inspection
        if e.inspected_fixture is None or e.inspected_fixture.identity != r.fixture.identity:
            return State.UNKNOWN, 'unresolved_or_wrong_identity'
        if r.fixture.match_date is not None and e.inspected_fixture.match_date != r.fixture.match_date:
            return State.UNKNOWN, 'fixture_date_mismatch'
        if e.inspected_fixture.lifecycle != r.fixture.lifecycle:
            return State.UNKNOWN, 'lifecycle_mismatch'
        if e.inspected_surface != r.surface:
            return State.UNKNOWN, 'wrong_surface'
        if (e.selected_period != r.period or not e.selected_period_evidence
                or e.period_evidence_method not in ('active_control', 'explicit_heading', 'structured_period')):
            return State.UNKNOWN, 'unverified_selected_period'
        if r.level != 'match' and (e.inspected_entity_id != r.entity_id or e.inspected_side != r.side):
            return State.UNKNOWN, 'unresolved_or_wrong_entity'
        return None

    @property
    def decision(self):
        failure = self.inspection_decision
        if failure is not None:
            return failure
        r, e = self.request, self.evidence
        if r.fixture.lifecycle in ('scheduled', 'postponed', 'cancelled', 'abandoned') and r.capability_name not in ('summary', 'lineups', 'standings', 'h2h'):
            return State.UNKNOWN, 'not_yet_available_or_unsettled'
        if e.noncoverage_reference and e.noncoverage_method in ('provider_statement', 'licensed_coverage_registry'):
            if e.value is not None:
                return State.UNKNOWN, 'conflicting_noncoverage_and_value'
            return State.NOT_COVERED, 'explicit_noncoverage'
        if e.raw_or_derived == 'derived':
            return State.UNKNOWN, 'derived_operand_adapter_not_implemented'
        if e.value is None:
            if e.expected_covered and e.null_reason == 'absent_value':
                return State.MISSING, 'absent_value'
            return State.UNKNOWN, e.null_reason or 'unknown_null'
        if r.capability_name == 'cards' and e.card_actor_scope not in ('on_field_players', 'players_including_bench', 'players_and_staff'):
            return State.UNKNOWN, 'ambiguous_card_actor_scope'
        if not valid_value(r.capability_name, e.value, e.unit):
            return State.UNKNOWN, 'invalid_or_ambiguous_value'
        return State.AVAILABLE, None

    @property
    def state(self):
        return self.decision[0]

    @property
    def successful_inspection(self):
        return self.inspection_decision is None

    @property
    def settlement_compatible(self):
        r, e = self.request, self.evidence
        return (self.state == State.AVAILABLE and r.fixture.lifecycle == 'finished'
                and e.score_scope == 'regulation' and r.capability_name not in SURFACES
                and (r.capability_name != 'cards' or bool(e.settlement_rules)))

    def prematch_usable(self, target_id, target_date, cutoff):
        e, r = self.evidence, self.request
        if (self.state != State.AVAILABLE or r.fixture.lifecycle != 'finished'
                or e.score_scope != 'regulation' or r.capability_name in SURFACES
                or sample_reasons(target_id, target_date, r.fixture.match_id, r.fixture.match_date)
                or not e.publication_verified or not e.revision_history_verified or e.publication_at is None):
            return False
        limit = timestamp(cutoff)
        if e.revision_at is not None and timestamp(e.revision_at) < timestamp(e.publication_at):
            return False
        return all(timestamp(t) < limit for t in (e.publication_at, e.revision_at) if t is not None)

    def to_dict(self):
        return dict(schema_version=VERSION, request=asdict(self.request), evidence=asdict(self.evidence),
                    state=self.state.value, null_reason=self.decision[1],
                    normalized_value=self.evidence.value if self.state == State.AVAILABLE else None,
                    technical_visibility='visible' if self.evidence.value is not None else 'unassessed',
                    acquisition_authorization=self.evidence.acquisition_authorization,
                    temporal_usability='requires_target_cutoff_check', evidence_quality=self.evidence.evidence_quality,
                    settlement_compatibility=self.settlement_compatible)

    @classmethod
    def from_dict(cls, data):
        if data['schema_version'] != VERSION:
            raise ValueError('unsupported observation schema')
        r, e = dict(data['request']), dict(data['evidence'])
        r['fixture'] = Fixture(**r['fixture'])
        if e['inspected_fixture'] is not None:
            e['inspected_fixture'] = Fixture(**e['inspected_fixture'])
        e['operand_references'] = tuple(e['operand_references'])
        result = cls(Request(**r), Evidence(**e))
        if dumps(result.to_dict()) != dumps(data):
            raise ValueError('observation derived fields disagree with evidence')
        return result
