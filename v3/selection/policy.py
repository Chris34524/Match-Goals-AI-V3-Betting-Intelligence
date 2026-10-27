"""Independent deterministic NO BET gates replay every upstream artifact."""
from copy import deepcopy
from v3.calibration.contract import time, verify, sealed, digest
from v3.calibration.engine import transform
from v3.value.engine import evaluate
from v3.value.selector import select
from .pickscore import score

POLICY=dict(version='no-bet-v1',minimum_pickscore=65,minimum_stability_component=60,
            value_policy='phase4_default_unoptimized',human_confirmation_required=True)


def decide(candidate, *, allow_synthetic=False):
    out=dict(candidate=deepcopy(candidate),decision='BLOCKED',reason_codes=[],pickscore=None,value=None,
             policy=POLICY,synthetic_test_only=allow_synthetic)
    try:
        if candidate.get('synthetic_test_only') is not allow_synthetic:raise ValueError('synthetic_mode_mismatch')
        if candidate.get('integrity_status')!='PASS':raise ValueError('integrity_problem')
        model=candidate['model'];cal=candidate['calibration'];target=candidate['target'];qs=candidate['quality']
        if model.get('partition')!='OOS':raise ValueError('selection_requires_oos_prediction')
        if not target.get('target_id') or target.get('date')!=time(target['kickoff_at']).date().isoformat():raise ValueError('invalid_target_date_or_id')
        if model.get('status')!='ELIGIBLE' or model.get('temporal_accredited') is not True or not model.get('temporal_lineage'):raise ValueError('model_blocked')
        if model.get('synthetic_test_only') is not allow_synthetic:raise ValueError('model_origin_mismatch')
        if not time(model['predicted_at']) <= time(target['cutoff']) < time(target['kickoff_at']):raise ValueError('temporal_invalid')
        for k in ('internal_match_id','market','selection','line'):
            if model.get(k)!=target.get(k):raise ValueError('identity_mismatch')
        if cal['market']!=target['market']:raise ValueError('calibration_market_mismatch')
        cp=transform(cal,model['probability'],cutoff=target['cutoff'],source_model_hash=model['hash'],allow_synthetic=allow_synthetic)
        if target['market']=='1X2':
            index=('home','draw','away').index(target['selection']);cp=cp[index]
            ece=max(v['ece'] for v in cal['reliability'].values())
        else:
            # Phase 5 binary labels represent yes/over; opposite-side adapter is not accredited.
            if target['selection'] not in ('yes','over'):raise ValueError('opposite_side_adapter_unaccredited')
            ece=cal['reliability']['ece']
        # Bind quality components to the actual calibrated probability and calibrator.
        if qs['probability']['value']!=cp or qs['calibration']['value']!=ece:raise ValueError('quality_prediction_mismatch')
        vm=dict(candidate['value_model'],model_probability=cp)
        for k in ('internal_match_id','market','selection','line','cutoff'):
            if vm.get(k)!=target.get(k):raise ValueError('value_target_mismatch')
        observations=candidate['odds_observations']
        if any(o['record']['kickoff_at']!=target['kickoff_at'] or not time(o['record']['observed_at'])<time(target['cutoff']) for o in observations):raise ValueError('odds_temporal_invalid')
        value=evaluate(vm,observations,allow_synthetic=allow_synthetic)
        vselect=select(value,allow_synthetic=allow_synthetic)
        out['value']=vselect
        if vselect['decision']=='BLOCKED':raise ValueError('value_invalid:'+','.join(vselect['reason_codes']))
        if qs['value']['value']!=value['ev_per_unit']:raise ValueError('quality_value_mismatch')
        ps=score(qs,synthetic_test_only=allow_synthetic);out['pickscore']=ps
        if ps['status']!='ELIGIBLE':raise ValueError('pickscore_not_computable')
        reasons=vselect['reason_codes'][:]
        if ps['score']<POLICY['minimum_pickscore']:reasons.append('pickscore_below_minimum')
        stability=next(c for c in ps['components'] if c['name']=='stability')
        if stability['normalized_component']<POLICY['minimum_stability_component']:reasons.append('stability_below_minimum')
        out.update(decision='NO_BET' if reasons else 'PASS',reason_codes=reasons,calibrated_probability=cp)
    except (ValueError,KeyError,TypeError,StopIteration) as exc:
        out['reason_codes']=[str(exc) if isinstance(exc,ValueError) else 'missing_required_evidence']
    return sealed(out)
