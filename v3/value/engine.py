"""Fail-closed evaluation over a model target and canonical odds envelopes.

Each observation is {record: Phase3 record, cutoff, period, rules}.
Synthetic evaluation requires both an explicit caller flag and synthetic lineage;
that flag never confers production source authorization.
"""
from copy import deepcopy
from v3.odds.contract import schema_errors, finite, timestamp, nonempty
from v3.odds.source_matrix import source_matrix, automatable
from .contract import IDENTITY, METRICS, VERSION, safe, serialize
from .probability import probability, fair_odds
from .market import normalize


def evaluate(model, observations, *, allow_synthetic=False):
    model = deepcopy(model) if isinstance(model, dict) else {}
    observations = deepcopy(observations) if isinstance(observations, list) else []
    first = observations[0].get('record', {}) if observations and isinstance(observations[0], dict) else {}
    first = first if isinstance(first, dict) else {}
    out = {k: model.get(k) if k in model else first.get(k) for k in IDENTITY}
    out.update({k: None for k in METRICS})
    out.update(model_id=model.get('model_id'), model_version=model.get('model_version'),
               model_probability=model.get('model_probability'), market_odds=None,
               observed_at=first.get('observed_at'), cutoff=model.get('cutoff'),
               kickoff_at=first.get('kickoff_at'), eligibility='BLOCKED', exclusion_reason=None,
               value_engine_version=VERSION, provenance={'mode': 'production', 'model': model.get('provenance'),
                   'observations': sorted(observations, key=lambda e: serialize(safe(e))), 'target': model})
    try:
        p = probability(model.get('model_probability'))
        fair = fair_odds(p)
        if not all(nonempty(model.get(k)) for k in ('model_id', 'model_version', 'internal_match_id', 'market', 'selection', 'period', 'rules')):
            raise ValueError('invalid_model_contract')
        if not isinstance(model.get('provenance'), dict) or not all(nonempty(model['provenance'].get(k)) for k in ('origin', 'evidence')):
            raise ValueError('missing_provenance')
        if not observations:
            raise ValueError('market_incomplete')
        records = []
        synthetic = model['provenance']['origin'] == 'synthetic_test_only'
        for envelope in observations:
            if not isinstance(envelope, dict) or not isinstance(envelope.get('record'), dict):
                raise ValueError('invalid_record')
            r = envelope['record']
            for field in ('cutoff', 'period', 'rules'):
                if envelope.get(field) != model.get(field) or envelope.get(field) is None:
                    raise ValueError('snapshot_mismatch' if field == 'cutoff' else 'rules_mismatch')
            if r.get('snapshot_type') == 'closing':
                raise ValueError('closing_not_pre_match_input')
            if r.get('snapshot_type') not in ('opening', 'current'):
                raise ValueError('unknown_snapshot_type')
            times = [timestamp(r.get('observed_at')), timestamp(model.get('cutoff')), timestamp(r.get('kickoff_at'))]
            if None in times or not times[0] <= times[1] < times[2] or not times[0] < times[2] or r.get('validity') != {'pre_match': True}:
                raise ValueError('temporally_ineligible')
            if r.get('price_state') != 'active':
                raise ValueError('price_not_active')
            if not finite(r.get('decimal_odds')) or r['decimal_odds'] <= 1:
                raise ValueError('invalid_odds')
            if not r.get('provenance'):
                raise ValueError('missing_provenance')
            errors = schema_errors(r, model['cutoff'])
            if errors:
                raise ValueError('invalid_odds_contract:' + ','.join(errors))
            test_record = r['provider'] == 'synthetic_test_only' and r['provenance']['origin'] == 'synthetic_test_only'
            if allow_synthetic and synthetic and test_record:
                out['provenance']['mode'] = 'synthetic_test_only'
            elif not any(automatable(row) and row['capture_policy'] == r['capture_policy']
                         and row['surface_availability'] == r['surface_availability']
                         for row in source_matrix(provider=r['provider'], market=r['market'], snapshot=r['snapshot_type'])):
                raise ValueError('source_not_authorized')
            if r.get('aggregation') != 'individual':
                raise ValueError('unsupported_aggregation')
            records.append(r)
        q, nv, overround = normalize(records)
        for field in ('internal_match_id', 'market', 'line'):
            if model.get(field) != records[0].get(field):
                raise ValueError({'line': 'line_mismatch', 'market': 'market_mismatch'}.get(field, 'match_mismatch'))
        selected = [r for r in records if r['selection'] == model['selection']]
        if len(selected) != 1:
            raise ValueError('selection_mismatch')
        r = selected[0]
        pm = nv[r['selection']]
        metrics = dict(fair_odds=fair, implied_probability_raw=q[r['selection']],
                       market_probability_no_vig=pm, overround=overround,
                       absolute_edge=p-pm, relative_edge=p/pm-1 if pm > 0 else None,
                       ev_per_unit=p*r['decimal_odds']-1)
        if any(v is not None and not finite(v) for v in metrics.values()):
            raise ValueError('nonfinite_computation')
        out.update({k: r[k] for k in IDENTITY})
        out.update(metrics, market_odds=r['decimal_odds'], eligibility='ELIGIBLE')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        out['exclusion_reason'] = str(exc) if isinstance(exc, ValueError) else 'invalid_contract'
    return safe(out)
