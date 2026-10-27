"""Recommendation only. Never mutates Champion; synthetic evidence cannot promote."""
import math
from v3.calibration.contract import sealed,time
from v3.models.champion import compare
from v3.calibration.reliability import metrics

POLICY=dict(version='promotion-v1',minimum_oos=200,minimum_windows=2,
            maximum_ece=.05,maximum_window_loss_deterioration=.01,
            tie_rule='both_losses_not_worse',automated_promotion=False)
CHAMPION='BT0 / J_BT_sin_temporada'


def evaluate(evidence):
    required=('real_oos_accredited','champion_accredited','same_rows','same_label_definition',
              'same_temporal_cutoff','integrity_pass','temporal_lineage_accredited')
    blockers=[k+'_missing_or_unaccredited' for k in required if evidence.get(k) is not True]
    if evidence.get('synthetic_test_only') is not False:blockers.append('real_evidence_required')
    metric_keys=('challenger_brier','champion_brier','challenger_logloss','champion_logloss','ece')
    if any(type(evidence.get(k)) not in (int,float) or not math.isfinite(evidence[k]) or evidence[k]<0 for k in metric_keys):blockers.append('metrics_missing_or_invalid')
    windows=evidence.get('windows')
    if not isinstance(windows,list) or not windows:blockers.append('windows_missing')
    elif any(not isinstance(w,dict) or any(type(w.get(k)) not in (int,float) or not math.isfinite(w[k]) for k in ('brier_delta','logloss_delta')) for w in windows):blockers.append('window_metrics_invalid')
    count=evidence.get('oos_count')
    if type(count) is not int or count<0:blockers.append('oos_count_invalid')
    if evidence.get('temporal_divergence') not in (True,False):blockers.append('divergence_unknown')
    # Comparator is replayed on exact IDs, events, regulation labels and cutoffs.
    rows=evidence.get('rows',[]); champion=evidence.get('champion_predictions',[])
    try:
        if not rows or len({r['target_id'] for r in rows})!=len(rows):raise ValueError('missing_or_duplicate_oos_rows')
        market=evidence['market']
        for row in rows:
            if row.get('partition')!='OOS' or row.get('synthetic_test_only') is not False or row.get('temporal_accredited') is not True or not row.get('temporal_lineage'):
                raise ValueError('real_oos_rows_required')
            if not time(row['predicted_at'])<time(row['cutoff'])<time(row['kickoff_at'])<time(row['label_available_at']):raise ValueError('oos_temporal_invalid')
        comparison=compare(rows,champion,market)
        if comparison['champion_comparison_status']!='ACCREDITED':raise ValueError(comparison['reason'])
        ys=[r['y'] for r in rows]
        cm=metrics(ys,[r['p'] for r in rows],market);bm=metrics(ys,comparison['probabilities'],market)
        for prefix,m in (('challenger_',cm),('champion_',bm)):
            for loss in ('brier','logloss'):
                if not math.isclose(evidence[prefix+loss],m[loss],rel_tol=0,abs_tol=1e-12):raise ValueError('metric_evidence_mismatch')
        if count!=len(rows):raise ValueError('oos_count_mismatch')
        indexed={r['target_id']:r for r in rows}; covered=set();window_ids=set();previous_date=None
        for w in windows or []:
            ids=w['ids']
            if not ids or len(set(ids))!=len(ids) or covered & set(ids) or not set(ids)<=indexed.keys() or w['fold_id'] in window_ids:raise ValueError('window_overlap_or_identity_invalid')
            wr=[indexed[i] for i in ids];dates=[time(r['kickoff_at']).date() for r in wr]
            if previous_date is not None and min(dates)<=previous_date:raise ValueError('temporal_window_overlap')
            previous_date=max(dates);covered.update(ids);window_ids.add(w['fold_id'])
        if covered!=set(indexed):raise ValueError('window_universe_mismatch')
    except (KeyError,TypeError,ValueError) as exc:
        blockers.append('exact_comparator_blocked:'+str(exc))
    reasons=blockers[:]
    state='BLOCKED'
    if not blockers:
        if count<POLICY['minimum_oos']:reasons.append('minimum_oos_not_met')
        if len(windows)<POLICY['minimum_windows']:reasons.append('minimum_windows_not_met')
        for loss in ('brier','logloss'):
            if evidence['challenger_'+loss]>evidence['champion_'+loss]:reasons.append(loss+'_worse')
        if evidence['ece']>POLICY['maximum_ece']:reasons.append('calibration_unacceptable')
        if evidence['temporal_divergence']:reasons.append('temporal_divergence')
        if any(max(w['brier_delta'],w['logloss_delta'])>POLICY['maximum_window_loss_deterioration'] for w in windows):reasons.append('temporal_instability')
        state='DO_NOT_PROMOTE' if reasons else 'PROMOTE_ELIGIBLE'
    return sealed(dict(gate_status=state,reason_codes=reasons,policy=POLICY,champion=CHAMPION,
                       champion_changed=False,human_review_required=True,evidence=evidence))
