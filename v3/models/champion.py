"""Exact historical evidence only; never synthesize BT0 probabilities."""
from v3.data.validation import timestamp
from .metrics import probability, vector


def compare(rows, evidence, market):
    def blocked(reason):
        return dict(champion_comparison_status='BLOCKED',reason=reason,probabilities=None)
    if not evidence:
        return blocked('no_historical_pre_match_prediction')
    ids = [p['target_id'] for p in evidence]
    if len(ids) != len(set(ids)) or set(ids) != {r['target_id'] for r in rows}:
        return blocked('row_universe_mismatch')
    indexed = {p['target_id']:p for p in evidence}
    ps = []
    for row in rows:
        p = indexed[row['target_id']]
        if p.get('model') != 'J_BT_sin_temporada' or not p.get('source_hash') or not p.get('lineage'):
            return blocked('prediction_lineage_missing')
        if any(p.get(k) != row.get(k) for k in ('event','kickoff_at','cutoff','label_version')) or p.get('market') != market:
            return blocked('cutoff_not_accredited')
        generated, cutoff = timestamp(p.get('generated_at')),timestamp(row.get('cutoff'))
        if generated is None or cutoff is None or generated >= cutoff:
            return blocked('no_historical_pre_match_prediction')
        try:
            (vector if market == '1X2' else probability)(p.get('probability'))
        except (ValueError,TypeError):
            return blocked('invalid_champion_probability')
        ps.append(p['probability'])
    return dict(champion_comparison_status='ACCREDITED',reason=None,probabilities=ps)


def audit_historical(root):
    """Canonical history has no reliable generated_at/cutoff; don't run analysis."""
    import json
    from collections import Counter
    counts = Counter()
    for line in (root/'data/derived/dataset_v3.jsonl').read_text().splitlines():
        row = json.loads(line)
        p = row.get('predictions')
        counts['targets'] += 1
        counts['identified_champion'] += bool(p and p.get('model') == 'J_BT_sin_temporada')
        counts['generated_at_present'] += bool(p and timestamp(p.get('generated_at')))
        counts['cutoff_present'] += bool(timestamp(row['audit'].get('feature_cutoff')))
    return dict(champion_comparison_status='BLOCKED', reason='cutoff_not_accredited',
                evidence_counts=dict(counts), operational_champion='BT0 / J_BT_sin_temporada',promotion=False)
