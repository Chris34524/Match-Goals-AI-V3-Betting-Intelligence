"""Deterministic offline audit. Latest inspection wins; equal-time conflicts fail closed."""
from collections import defaultdict
from dataclasses import asdict
import hashlib

from . import VERSION
from .contract import Capability, State, dumps, timestamp
from .coverage import summarize, rate
from .manifest import STRATA, load_manifest

MARKETS = {
    'TOTAL_CORNERS': (('corners', 'FT'),),
    'MOST_CORNERS': (('corners', 'FT'),),
    'CORNERS_1H': (('corners', '1H'),),
    'CARDS': (('cards', 'FT'),),
    'HT_FT': (('goals_first_half', '1H'), ('goals_ft', 'FT')),
}


def audit(manifest, observations):
    frame = load_manifest(manifest)
    targets = {r.key: r for r in frame.requests}
    latest, attempted, seen = {}, set(), set()
    duplicates = 0
    for c in observations:
        if not isinstance(c, Capability):
            raise ValueError('audit requires validated capability records')
        key = c.request.key
        if key not in targets or targets[key] != c.request:
            raise ValueError('observation outside predeclared target frame')
        if timestamp(c.evidence.observed_at) < timestamp(frame.declared_at):
            raise ValueError('manifest must be declared before observations')
        encoded = dumps(c.to_dict())
        if encoded in seen:
            duplicates += 1
            continue
        seen.add(encoded)
        if c.evidence.inspection != 'not_inspected' or c.state == State.BLOCKED:
            attempted.add(key)
        when = timestamp(c.evidence.observed_at)
        if key not in latest or when > latest[key][0]:
            latest[key] = (when, c, False)
        elif when == latest[key][0]:
            latest[key] = (when, latest[key][1], True)
    units, by_stratum = [], defaultdict(list)
    for r in frame.requests:
        selected = latest.get(r.key)
        c = selected[1] if selected and not selected[2] else None
        context = frame.target_context
        unit = dict(key=list(r.key), request=asdict(r), state=c.state.value if c else State.UNKNOWN.value,
            null_reason=c.decision[1] if c else 'conflicting_latest_observations' if selected else 'not_inspected',
            attempted=r.key in attempted, successful_inspection=c.successful_inspection if c else False,
            settlement_compatible=c.settlement_compatible if c else False,
            prematch_usable=c.prematch_usable(context['match_id'], context['match_date'], context['cutoff'])
                if c and context else False if context else None,
            normalized_value=c.evidence.value if c and c.state == State.AVAILABLE else None,
            settlement_rules=c.evidence.settlement_rules if c else None,
            card_actor_scope=c.evidence.card_actor_scope if c else None,
            selected_observed_at=c.evidence.observed_at if c else None,
            observation_sha256=hashlib.sha256(dumps(c.to_dict()).encode()).hexdigest() if c else None)
        units.append(unit)
        stratum = tuple(getattr(r.fixture, k) for k in STRATA) + (
            r.capability_name, r.period, r.level, r.side or '')
        by_stratum[stratum].append(unit)
    unassessed_player_strata = set()
    fixture_index = {(f.provider, f.match_id): f for f in frame.fixtures}
    for eligibility in frame.player_eligibility:
        if eligibility['status'].startswith('unassessed'):
            f = fixture_index[(eligibility['provider'], eligibility['match_id'])]
            unassessed_player_strata.add(tuple(getattr(f, k) for k in STRATA) + (eligibility['field'],))
    strata = []
    for key, rows in sorted(by_stratum.items()):
        metrics = summarize(rows, frame.min_successful_inspections, frame.min_assessed_fraction)
        if key[:len(STRATA)+1] in unassessed_player_strata and key[-2] == 'player':
            metrics['research_tier'] = 'UNASSESSED'
            metrics['eligibility_incomplete'] = True
        strata.append(dict(stratum=dict(zip(STRATA + ('canonical_field', 'period', 'level', 'side'), key)),
                           metrics=metrics))
    markets = market_readiness(frame, units)
    metrics = summarize(units, frame.min_successful_inspections, frame.min_assessed_fraction)
    if unassessed_player_strata:
        metrics['research_tier'] = 'UNASSESSED'
    return dict(schema_version=VERSION, manifest_id=frame.manifest_id,
        manifest_sha256=hashlib.sha256(dumps(manifest).encode()).hexdigest(),
        unique_observations=len(seen), duplicate_observations=duplicates,
        duplicate_fixtures=frame.duplicate_fixtures, unique_fixtures=len(frame.fixtures),
        revisit_policy='latest_by_timestamp; equal-time conflicting observations UNKNOWN',
        tier_policy=dict(min_successful_inspections=frame.min_successful_inspections,
                         min_assessed_fraction=frame.min_assessed_fraction, basis='unrounded_all_target_point_estimate',
                         research_only=True),
        uncertainty='Wilson 95% descriptive unit intervals; fixture/player clustering and purposive sampling '
                    'are not modeled, so these are not population inference or promotion gates.',
        metrics=metrics,
        eligibility_incomplete=bool(unassessed_player_strata),
        player_denominator_policy='Only accredited eligible participants; unknown eligibility/rosters reported separately, tiers UNASSESSED. Unknown roster size is not invented.',
        strata=strata, units=units, player_eligibility=list(frame.player_eligibility), markets=markets)


def market_readiness(frame, units):
    index = {tuple(u['key']): u for u in units}
    rows = []
    for f in frame.fixtures:
        for market, operands in MARKETS.items():
            required, missing, incompatible = [], [], []
            for field, period in operands:
                for side in ('home', 'away'):
                    key = (f.provider, f.match_id, field, period, 'team', side, getattr(f, side + '_id'))
                    required.append(list(key))
                    unit = index.get(key)
                    if unit is None:
                        missing.append(list(key))
                    elif not unit['settlement_compatible']:
                        incompatible.append(list(key))
            semantic_reason = None
            if not missing and not incompatible and market == 'HT_FT':
                if any(index[(f.provider, f.match_id, 'goals_first_half', '1H', 'team', side, getattr(f, side + '_id'))]['normalized_value']
                       > index[(f.provider, f.match_id, 'goals_ft', 'FT', 'team', side, getattr(f, side + '_id'))]['normalized_value']
                       for side in ('home', 'away')):
                    semantic_reason = 'inconsistent_ht_ft_scores'
            if not missing and not incompatible and market == 'CARDS':
                if (len({index[tuple(key)]['settlement_rules'] for key in required}) != 1
                        or len({index[tuple(key)]['card_actor_scope'] for key in required}) != 1):
                    semantic_reason = 'incompatible_card_settlement_rules'
            rows.append(dict(provider=f.provider, match_id=f.match_id, market=market,
                player_id=None, ready=not missing and not incompatible and semantic_reason is None, required_units=required,
                unplanned_units=missing, unavailable_units=incompatible,
                reason='operands_not_predeclared' if missing else 'unavailable_or_incompatible_operands' if incompatible else semantic_reason))
    for r in frame.requests:
        if r.level == 'player' and r.capability_name == 'shots_on_target':
            u = index[r.key]
            rows.append(dict(provider=r.fixture.provider, match_id=r.fixture.match_id, market='PLAYER_SOT',
                player_id=r.entity_id, ready=u['settlement_compatible'], required_units=[list(r.key)],
                unplanned_units=[], unavailable_units=[] if u['settlement_compatible'] else [list(r.key)],
                reason=None if u['settlement_compatible'] else 'unavailable_or_incompatible_player_operand'))
    rows.sort(key=lambda r: (r['provider'], r['match_id'], r['market'], r['player_id'] or ''))
    totals = []
    for name in sorted(MARKETS.keys() | {'PLAYER_SOT'}):
        selected = [r for r in rows if r['market'] == name]
        totals.append(dict(market=name, readiness=rate(sum(r['ready'] for r in selected), len(selected)),
                           eligibility_unassessed=sum(e['status'].startswith('unassessed') for e in frame.player_eligibility
                               if e['field'] == 'shots_on_target') if name == 'PLAYER_SOT' else 0))
    return dict(units=rows, totals=totals,
                meaning='Research operand readiness only; no odds, bookmaker release, model or production promotion.')
