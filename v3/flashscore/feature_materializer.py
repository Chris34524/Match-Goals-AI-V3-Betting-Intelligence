"""Strict complete-window historical features, independent of settlement labels."""
from enum import Enum

from v3.data.temporal import sample_reasons
from v3.data.validation import day
from .contract import Fixture, State, timestamp
from .feature_catalog import BY_NAME, CATALOG, VERSION
from .market_contract import CardSettlementPolicy
from .observation_index import ObservationIndex, digest, operand_key, provenance


class FeatureStatus(str, Enum):
    AVAILABLE = 'AVAILABLE'
    INSUFFICIENT_HISTORY = 'INSUFFICIENT_HISTORY'
    MISSING_OPERAND = 'MISSING_OPERAND'
    BLOCKED_SOURCE = 'BLOCKED_SOURCE'
    TEMPORAL_INELIGIBLE = 'TEMPORAL_INELIGIBLE'
    UNASSESSED = 'UNASSESSED'
    NOT_COVERED = 'NOT_COVERED'
    SEMANTIC_INCOMPATIBLE = 'SEMANTIC_INCOMPATIBLE'


class FeatureMaterializer:
    def __init__(self, observations):
        self.index = ObservationIndex(observations)

    def materialize(self, target, cutoff, *, names=None, scopes=('overall', 'home', 'away'), card_policy=None):
        if not isinstance(target, Fixture) or day(target.match_date) is None:
            raise ValueError('resolved target fixture/date required')
        if card_policy is not None and not isinstance(card_policy, CardSettlementPolicy):
            raise ValueError('validated card policy required')
        limit = timestamp(cutoff)
        if limit.date() > day(target.match_date):
            raise ValueError('prematch cutoff cannot follow target date')
        if not scopes or any(s not in ('overall', 'home', 'away') for s in scopes):
            raise ValueError('invalid history scope')
        specs = [BY_NAME[name] for name in sorted(set(names))] if names is not None else CATALOG
        rows = []
        for side in ('home', 'away'):
            team = getattr(target, side + '_id')
            fixtures, excluded = [], []
            for f in self.index.by_team.get((target.provider, team), ()):
                reasons = sample_reasons(target.match_id, target.match_date, f.match_id, f.match_date)
                if not reasons and day(f.match_date) >= limit.date():
                    reasons = ['source_date_not_strictly_before_cutoff_day']
                if f.lifecycle != 'finished':
                    reasons.append('unfinished_history')
                if reasons:
                    excluded.append(dict(match_id=f.match_id, reasons=sorted(reasons)))
                else:
                    fixtures.append(f)
            # Date ordering is intentional; intraday order is not accredited.
            fixtures.sort(key=lambda f: (-day(f.match_date).toordinal(), f.match_id))
            for scope in sorted(set(scopes)):
                history = [f for f in fixtures if scope == 'overall' or getattr(f, scope + '_id') == team]
                for spec in specs:
                    for n in spec.windows:
                        selected = history[:n]  # never backfill missing operands
                        values, used, diagnostics = [], [], []
                        for f in selected:
                            source_side = 'home' if f.home_id == team else 'away'
                            if spec.orientation == 'against':
                                source_side = 'away' if source_side == 'home' else 'home'
                            operands, failures, sources, keys, selections = [], [], [], [], []
                            for metric in (spec.metric,) + ((spec.denominator,) if spec.denominator else ()):
                                key = operand_key(f, metric, spec.period, source_side)
                                keys.append(list(key))
                                c, reason = self.index.select(key, cutoff)
                                selections.append(dict(key=list(key), reason=reason,
                                    rejected_observations=[dict(observation_sha256=digest(candidate.to_dict()),
                                        state=candidate.state.value, source_reason=candidate.decision[1])
                                        for candidate in sorted(self.index.by_key.get(key, ()),
                                            key=lambda item: digest(item.to_dict()))] if c is None else []))
                                if c is None:
                                    failures.append('TEMPORAL_INELIGIBLE' if reason == 'temporal_ineligible' else
                                                    'UNASSESSED' if reason == 'conflicting_latest_observations' else 'MISSING_OPERAND')
                                else:
                                    sources.append(provenance(c))
                                    if c.state != State.AVAILABLE:
                                        failures.append({State.BLOCKED: 'BLOCKED_SOURCE', State.NOT_COVERED: 'NOT_COVERED',
                                                         State.MISSING: 'MISSING_OPERAND', State.UNKNOWN: 'UNASSESSED'}[c.state])
                                    elif not c.prematch_usable(target.match_id, target.match_date, cutoff):
                                        failures.append('TEMPORAL_INELIGIBLE')
                                    elif metric == 'cards':
                                        if card_policy is None or not card_policy.compatible(c):
                                            failures.append('SEMANTIC_INCOMPATIBLE')
                                        else:
                                            operands.append(card_policy.count(c.evidence.value))
                                    else:
                                        operands.append(c.evidence.value)
                            if not failures and spec.denominator and (operands[1] == 0 or
                                    (spec.name == 'shot_accuracy' and operands[0] > operands[1])):
                                failures.append('SEMANTIC_INCOMPATIBLE')
                            if not failures:
                                values.append(operands)
                            used.extend(sources)
                            diagnostics.append(dict(match_id=f.match_id, reasons=sorted(set(failures)),
                                                    operand_keys=keys, selections=selections))
                        reasons = sorted({r for d in diagnostics for r in d['reasons']})
                        if len(selected) < n:
                            status = 'INSUFFICIENT_HISTORY'
                        elif reasons:
                            priority = ('BLOCKED_SOURCE', 'TEMPORAL_INELIGIBLE', 'NOT_COVERED', 'UNASSESSED',
                                        'SEMANTIC_INCOMPATIBLE', 'MISSING_OPERAND')
                            status = next(r for r in priority if r in reasons)
                        else:
                            status = 'AVAILABLE'
                        value = None
                        if status == 'AVAILABLE':
                            value = (sum(v[0] for v in values) / sum(v[1] for v in values) if spec.denominator
                                     else sum(v[0] for v in values) / n)
                        policy = card_policy.to_dict() if card_policy and spec.metric == 'cards' else None
                        identity = dict(schema_version=VERSION, target_identity=list(target.identity), team_id=team,
                                        side=side, feature_name=spec.name + f'_L{n}', window=f'L{n}', scope=scope,
                                        cutoff=cutoff, card_policy=policy)
                        rows.append(dict(**identity, feature_id=digest(identity), target_match_id=target.match_id,
                            value=value, status=FeatureStatus(status).value, n_required=n, n_eligible=len(selected), n_available=len(values),
                            n_history_eligible=len(history), coverage_rate=len(values)/n, coverage_denominator='n_required',
                            aggregation='ratio_of_sums' if spec.denominator else 'arithmetic_mean',
                            source_match_ids=[f.match_id for f in selected],
                            source_observation_hashes=sorted({s['observation_sha256'] for s in used}),
                            provenance=sorted(used, key=lambda s: s['capability_key']), diagnostics=diagnostics,
                            excluded_fixtures=sorted(excluded, key=lambda d: d['match_id']),
                            materializer_version=VERSION))
        return sorted(rows, key=lambda row: row['feature_id'])
