"""Versioned structured replay protocol. Does not parse real website HTML/selectors.

An external permitted adapter must supply explicit identity and selected-period
proof. Arbitrary HTML, indexed labels and URL-only periods are inconclusive.
"""
from dataclasses import replace
from typing import Protocol

from . import VERSION
from .contract import Capability, Evidence, Fixture, Request, SURFACES
from .events import normalize_events
from .normalization import canonical_stat, unit_for

SAMPLE_VERSION = 'fs-replay-1'


class Parser(Protocol):
    def parse(self, request: Request, sample: dict) -> Capability: ...


def validate_context_rows(surface, rows, fixture, reference):
    """Minimal typed surface validators; no standings/H2H prematch inference."""
    if not isinstance(rows, list) or not reference:
        raise ValueError('missing row-completeness/snapshot evidence')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid row')
        if surface == 'lineups':
            key = row['player_id']
            if (row['side'] not in ('home', 'away') or not key
                    or row['team_id'] != getattr(fixture, row['side'] + '_id')
                    or row['kind'] not in ('official', 'predicted')
                    or row['role'] not in ('starter', 'bench') or not row['position']):
                raise ValueError('invalid lineup identity or kind')
        elif surface == 'standings':
            key = row['team_id']
            if (not key or type(row['rank']) is not int or row['rank'] < 1
                    or type(row['played']) is not int or row['played'] < 0
                    or type(row['points']) is not int or not row['snapshot_reference']):
                raise ValueError('invalid standing')
        elif surface == 'h2h':
            key = row['match_id']
            from v3.data.validation import day
            if (not key or day(row['match_date']) is None or row['home_id'] == row['away_id']
                    or not row['home_id'] or not row['away_id'] or row['score_scope'] != 'regulation'
                    or any(type(row[k]) is not int or row[k] < 0 for k in ('home_goals', 'away_goals'))):
                raise ValueError('invalid H2H row')
        else:  # player surface independently validates player identities and participation metadata.
            key = row['player_id']
            if (not key or row['side'] not in ('home', 'away')
                    or row['team_id'] != getattr(fixture, row['side'] + '_id')
                    or type(row['participated']) is not bool
                    or type(row['minutes']) not in (int, float) or not 0 <= row['minutes'] <= 130
                    or not row['position'] or (row['participated'] != (row['minutes'] > 0))):
                raise ValueError('invalid player participation')
        if not isinstance(key, str) or key in seen:
            raise ValueError('duplicate row identity')
        seen.add(key)
    return dict(validated=True, rows=sorted(rows, key=lambda r: (
        r.get('player_id', ''), r.get('team_id', ''), r.get('match_id', ''))),
        completeness_reference=reference)


class StructuredParser:
    def parse(self, request, sample):
        if sample.get('schema_version') != SAMPLE_VERSION:
            raise ValueError('unsupported replay schema')
        if sample.get('sample_kind') not in ('synthetic', 'permitted_manual') or not sample.get('permission_reference'):
            raise ValueError('replay requires synthetic provenance or documented sample permission')
        metadata = sample['metadata']
        fixture_data = sample.get('inspected_fixture')
        try:
            actual = Fixture(**fixture_data) if fixture_data is not None else None
        except (TypeError, ValueError):
            actual = None
        e = Evidence(
            observed_at=metadata['observed_at'], source_url=metadata['source_url'],
            evidence_method=sample['sample_kind'], inspected_fixture=actual,
            inspected_surface=sample.get('surface'), selected_period=metadata.get('selected_period'),
            selected_period_evidence=metadata.get('selected_period_evidence'),
            period_evidence_method=metadata.get('period_evidence_method'),
            inspection=metadata.get('inspection', 'not_inspected'),
            access_blocked_reason=metadata.get('access_blocked_reason'),
            acquisition_authorization='unverified', acquisition_mode='offline',
            score_scope=metadata.get('score_scope', 'unknown'),
            publication_at=metadata.get('publication_at'), revision_at=metadata.get('revision_at'),
            publication_verified=metadata.get('publication_verified', False),
            revision_history_verified=metadata.get('revision_history_verified', False),
            sample_reference=sample['permission_reference'], evidence_quality=sample['sample_kind'],
            parser_version=VERSION, null_reason=metadata.get('null_reason'))
        if request.capability_name in SURFACES:
            try:
                if sample['surface'] == 'events':
                    value = normalize_events(sample.get('events'), actual, sample.get('completeness_reference'))
                elif sample['surface'] in ('lineups', 'standings', 'h2h', 'player_stats'):
                    value = validate_context_rows(sample['surface'], sample.get('rows'), actual,
                                                  sample.get('completeness_reference'))
                else:
                    # Loaded structured container is distinct from its numeric child operands.
                    if not isinstance(sample.get('stats'), list) or not sample.get('completeness_reference'):
                        raise ValueError('unverified container')
                    value = dict(validated=True, completeness_reference=sample['completeness_reference'])
                e = replace(e, value=value, unit='surface')
            except (KeyError, TypeError, ValueError, AttributeError):
                e = replace(e, null_reason='invalid_or_unimplemented_surface_payload')
        else:
            allowed_surface = (request.surface.startswith('stats_') and not request.capability_name.startswith('goals_')
                               or request.surface == 'summary' and request.capability_name.startswith('goals_')
                               or request.surface == 'player_stats' and request.level == 'player')
            if not allowed_surface:
                return Capability(request, replace(e, null_reason='unsupported_field_surface'))
            rows = sample.get('stats', [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                return Capability(request, replace(e, null_reason='invalid_structured_rows'))
            candidates = [row for row in rows if canonical_stat(row.get('canonical_stat')) == request.capability_name]
            if any((row.get('side') == request.side and row.get('entity_id') != request.entity_id)
                   or (row.get('entity_id') == request.entity_id and row.get('side') != request.side)
                   for row in candidates):
                return Capability(request, replace(e, null_reason='conflicting_operand_orientation'))
            cells = [row for row in rows if
                     canonical_stat(row.get('canonical_stat')) == request.capability_name
                     and row.get('side') == request.side and row.get('entity_id') == request.entity_id]
            e = replace(e, inspected_entity_id=request.entity_id, inspected_side=request.side)
            if len(cells) > 1:
                e = replace(e, null_reason='duplicate_field_operand')
            elif not cells:
                e = replace(e, expected_covered=request.capability_name in sample.get('covered_fields', []),
                            null_reason='absent_value')
            else:
                row = cells[0]
                value = row.get('value')
                e = replace(e, value=value, unit=row.get('unit', unit_for(request.capability_name)),
                            expected_covered=row.get('expected_covered', False),
                            null_reason=row.get('null_reason'),
                            noncoverage_reference=row.get('noncoverage_reference'),
                            noncoverage_method=row.get('noncoverage_method'),
                            settlement_rules=row.get('settlement_rules'), card_actor_scope=row.get('card_actor_scope'))
                # Player fields cannot borrow identity/participation merely from a team row.
                if request.level == 'player':
                    try:
                        validate_context_rows('player_stats', sample.get('rows'), actual,
                                              sample.get('completeness_reference'))
                        players = [r for r in sample['rows'] if r['player_id'] == request.entity_id
                                   and r['side'] == request.side and r['participated']]
                        if len(players) != 1:
                            raise ValueError('unresolved participating player')
                    except (KeyError, TypeError, ValueError, AttributeError):
                        e = replace(e, value=None, null_reason='unresolved_player_participation')
        return Capability(request, e)
