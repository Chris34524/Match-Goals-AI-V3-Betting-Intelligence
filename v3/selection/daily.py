"""Daily offline recommendation report; ranking uses unrounded values."""
from collections import Counter
from v3.calibration.contract import sealed,time,canonical
from v3.calibration.engine import real_state
from .policy import decide


def daily(candidates, *, allow_synthetic=False):
    result=dict(version='daily-v1',synthetic_test_only=allow_synthetic,pass_candidates=[],no_bet=[],blocked=[],
                real_daily_picks_status='BLOCKED',reason_codes=real_state()['reason_codes'])
    counts=Counter(tuple(c.get('target',{}).get(k) for k in ('internal_match_id','market','selection','line')) for c in candidates)
    for candidate in candidates:
        d=decide(candidate,allow_synthetic=allow_synthetic)
        target=candidate.get('target',{})
        key=tuple(target.get(k) for k in ('internal_match_id','market','selection','line'))
        if counts[key]>1:
            d=dict(d,decision='BLOCKED',reason_codes=['duplicate_candidate'])
        v=d.get('value') or {};model=candidate.get('model',{})
        row={k:target.get(k) for k in ('date','internal_match_id','kickoff_at','target_id','market','selection','line')}
        row.update({k:v.get(k) for k in ('fair_odds','market_odds','minimum_acceptable_odds','absolute_edge','relative_edge','ev_per_unit','bookmaker','provider','observed_at')})
        row.update(model_id=candidate.get('value_model',{}).get('model_id'),model_probability=model.get('probability'),
                   calibrated_probability=d.get('calibrated_probability'),market_no_vig_probability=v.get('market_probability_no_vig'),
                   PickScore=(d.get('pickscore') or {}).get('score'),PickScore_components=(d.get('pickscore') or {}).get('components',[]),
                   decision=d['decision'],reason_codes=d['reason_codes'],synthetic_test_only=allow_synthetic,
                   provenance=dict(candidate=candidate,decision=d),versions=dict(daily='daily-v1',selection='no-bet-v1',pickscore='pickscore-v1',calibration=candidate.get('calibration',{}).get('version'),value=v.get('value_engine_version')))
        # Real output remains closed until a separately accredited Phase 5 adapter exists.
        if not allow_synthetic:
            row.update(decision='BLOCKED',reason_codes=sorted(set(row['reason_codes']+result['reason_codes'])))
        result[{'PASS':'pass_candidates','NO_BET':'no_bet','BLOCKED':'blocked'}[row['decision']]].append(row)
    result['pass_candidates'].sort(key=lambda r:(-r['PickScore'],-r['ev_per_unit'],-r['absolute_edge'],time(r['kickoff_at']),r['target_id']))
    for group in ('no_bet','blocked'):
        result[group].sort(key=lambda r:tuple(str(r.get(k)) for k in ('target_id','market','selection','line'))+(canonical(r),))
    return sealed(result)
