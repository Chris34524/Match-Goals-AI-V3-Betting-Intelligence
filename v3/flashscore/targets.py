"""Final-evidence labels only. No feature-engine imports or production adapter."""
from dataclasses import asdict

from .contract import Fixture, State
from .market_contract import (CardSettlementPolicy, MarketSpec, PlayerMarketPolicy,
                              TargetStatus, VERSION, evaluate_over, research_markets)
from .parser import validate_context_rows
from .observation_index import ObservationIndex, digest, operand_key, provenance

GOALS = {'FT': 'goals_ft', '1H': 'goals_first_half', '2H': 'goals_second_half'}
DERIVATION = 'regulation-ft-minus-ht-v1'


class TargetEngine:
    def __init__(self, observations):
        self.index = ObservationIndex(observations)

    def settle(self, fixture, *, specs=None, card_policy=None, player_policy=None, derive_second_half=False):
        if not isinstance(fixture, Fixture):
            raise ValueError('resolved fixture required')
        if card_policy is not None and not isinstance(card_policy, CardSettlementPolicy):
            raise ValueError('validated card policy required')
        if player_policy is not None and not isinstance(player_policy, PlayerMarketPolicy):
            raise ValueError('validated player policy required')
        if type(derive_second_half) is not bool:
            raise ValueError('second half derivation requires explicit boolean')
        known = self.index.fixtures.get((fixture.provider, fixture.match_id))
        if known is not None and known != fixture:
            raise ValueError('settlement fixture identity/lifecycle conflicts')
        rows = []
        for spec in research_markets() if specs is None else specs:
            if not isinstance(spec, MarketSpec):
                raise ValueError('validated MarketSpec required')
            used, reasons, raw = [], [], []

            def read(metric, period, side, *, level='team', entity=None):
                key = operand_key(fixture, metric, period, side, entity, level)
                c, reason = self.index.select(key)
                raw.append(dict(key=list(key), value=c.evidence.value if c else None, selection_reason=reason))
                if c is None:
                    reasons.append('UNASSESSED' if reason == 'conflicting_latest_observations' else 'MISSING_OPERAND')
                    return None
                used.append(provenance(c))
                if c.state != State.AVAILABLE:
                    reasons.append({State.MISSING: 'MISSING_OPERAND', State.BLOCKED: 'BLOCKED_SOURCE',
                                    State.NOT_COVERED: 'NOT_COVERED', State.UNKNOWN: 'UNASSESSED'}[c.state])
                    return None
                if not c.settlement_compatible:
                    reasons.append('SETTLEMENT_INCOMPATIBLE')
                    return None
                if metric == 'cards' and (card_policy is None or not card_policy.compatible(c)):
                    reasons.append('SETTLEMENT_INCOMPATIBLE')
                    return None
                return c.evidence.value

            derivation = None
            values, ht = [], []
            # A missing explicit 2H pair may use a separately versioned opt-in
            # derivation; an incompatible/conflicting explicit operand never falls back.
            if fixture.lifecycle == 'finished':
                periods = ('1H', 'FT') if spec.market == 'ht_ft' else (spec.period,)
                for period in periods:
                    pair = []
                    metric = GOALS[period] if spec.family == 'goals' else 'shots_on_target' if spec.family == 'player_sot' else spec.family
                    if spec.family == 'player_sot':
                        value = read(metric, period, spec.side, level='player', entity=spec.player_id)
                        pair = [value]
                        key = (fixture.provider, fixture.match_id, 'player_stats', 'FT', 'match', '', '')
                        c, selection_reason = self.index.select(key)
                        raw.append(dict(key=list(key), value=c.evidence.value if c else None,
                                        selection_reason=selection_reason))
                        if c is not None:
                            used.append(provenance(c))
                        eligible = []
                        if c and c.state == State.AVAILABLE and c.evidence.score_scope == 'regulation' and player_policy:
                            try:
                                payload = c.evidence.value
                                validate_context_rows('player_stats', payload.get('rows'), fixture,
                                                      payload.get('completeness_reference'))
                                eligible = [r for r in payload['rows'] if r['player_id'] == spec.player_id
                                    and r['team_id'] == getattr(fixture, spec.side + '_id') and r['side'] == spec.side
                                    and r['participated'] and r['minutes'] > 0 and r['minutes'] >= player_policy.min_minutes
                                    and r['position'] in player_policy.positions]
                            except (ValueError, TypeError, KeyError, AttributeError):
                                eligible = []
                        if len(eligible) != 1:
                            reasons.append('BLOCKED_SOURCE' if c and c.state == State.BLOCKED else
                                           'NOT_COVERED' if c and c.state == State.NOT_COVERED else 'UNASSESSED')
                    else:
                        # Even team lines require bilateral evidence in this phase.
                        before = len(reasons)
                        pair = [read(metric, period, side) for side in ('home', 'away')]
                        pair_reasons = reasons[before:]
                        if (spec.family == 'goals' and period == '2H' and derive_second_half
                                and pair_reasons and set(pair_reasons) == {'MISSING_OPERAND'}):
                            del reasons[before:]
                            ft = [read('goals_ft', 'FT', side) for side in ('home', 'away')]
                            first = [read('goals_first_half', '1H', side) for side in ('home', 'away')]
                            if all(x is not None for x in ft + first):
                                if any(a < b for a, b in zip(ft, first)):
                                    reasons.append('SETTLEMENT_INCOMPATIBLE')
                                else:
                                    derived = [a-b for a, b in zip(ft, first)]
                                    if any(x is not None and x != y for x, y in zip(pair, derived)):
                                        reasons.append('SETTLEMENT_INCOMPATIBLE')
                                    pair = derived
                                    derivation = DERIVATION
                        if spec.family == 'cards' and all(v is not None for v in pair):
                            if spec.market == 'red':
                                pair = [v['direct_red'] + v['second_yellow_dismissals'] for v in pair]
                            else:
                                pair = [card_policy.count(v) for v in pair]
                    if spec.market == 'ht_ft' and period == '1H':
                        ht = pair
                    else:
                        values = pair
                if ht and all(v is not None for v in ht + values) and any(a > b for a, b in zip(ht, values)):
                    reasons.append('SETTLEMENT_INCOMPATIBLE')
            outcome, binary = None, None
            if fixture.lifecycle == 'cancelled':
                status, outcome = 'VOID', 'VOID'  # research policy, not universal book rules
            elif fixture.lifecycle != 'finished':
                status = 'UNSETTLED'  # scheduled/live/postponed/abandoned never forced labels
            elif reasons:
                priority = ('BLOCKED_SOURCE', 'SETTLEMENT_INCOMPATIBLE', 'NOT_COVERED', 'UNASSESSED', 'MISSING_OPERAND')
                status = next(s for s in priority if s in reasons)
            else:
                status = 'SETTLED'
                if spec.market == 'over':
                    value = values[0] if spec.family == 'player_sot' else sum(values) if spec.side == 'total' else values[0 if spec.side == 'home' else 1]
                    outcome = evaluate_over(value, spec.line).value
                    binary = {'WIN': 1, 'LOSS': 0}.get(outcome)
                elif spec.market in ('btts', 'red'):
                    binary = int(all(v >= 1 for v in values) if spec.market == 'btts' else any(v >= 1 for v in values))
                    outcome = 'WIN' if binary else 'LOSS'
                elif spec.market in ('1x2', 'most'):
                    outcome = result(values)
                else:
                    outcome = result(ht) + '/' + result(values)
            policy = dict(base='research-regulation-settlement-v1', cancelled='VOID', abandoned='UNSETTLED',
                          cards=card_policy.to_dict() if card_policy and spec.family == 'cards' else None,
                          player=player_policy.to_dict() if player_policy and spec.family == 'player_sot' else None,
                          second_half_derivation=DERIVATION if derive_second_half and spec.family == 'goals' and spec.period == '2H' else None)
            identity = dict(schema_version=VERSION, fixture_identity=list(fixture.identity), specification=asdict(spec), policy=policy)
            rows.append(dict(schema_version=VERSION, target_key=digest(identity), provider=fixture.provider,
                match_id=fixture.match_id, market_family=spec.family, market=spec.market, side=spec.side,
                entity=spec.player_id or (getattr(fixture, spec.side + '_id') if spec.side != 'total' else None),
                period=spec.period, line=spec.line, settlement_policy_version=policy,
                status=TargetStatus(status).value, outcome=outcome, binary_label=binary, reasons=sorted(set(reasons)),
                raw_operands=raw, operand_keys=[v['key'] for v in raw],
                observation_hashes=sorted({u['observation_sha256'] for u in used}),
                provenance=sorted(used, key=lambda u: u['capability_key']), score_scope='regulation',
                derivation=derivation, settled_at=None))
        unique = {r['target_key']: r for r in rows}
        return [unique[key] for key in sorted(unique)]


def result(pair):
    return 'HOME' if pair[0] > pair[1] else 'AWAY' if pair[0] < pair[1] else 'DRAW'
