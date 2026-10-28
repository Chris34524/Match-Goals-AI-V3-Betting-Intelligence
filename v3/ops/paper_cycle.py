"""Reuse selection and the original hash-chained paper ledger; no new ledger.

Current Phase 5 has no accredited real model adapter. A candidate is never
upgraded to real by changing synthetic flags. This remains an explicit blocker.
"""
from pathlib import Path
import os
import hashlib
import json
from v3.selection.policy import decide
from v3.paper.ledger import Ledger, identity
from .runtime import ROOT, read, locked, write


def prediction_audit():
    evidence=[]
    for path in [Path('data/all_predictions.json'),Path('data/day_predictions_v2.json')]:
        if not path.is_file():continue
        raw=path.read_bytes();payload=json.loads(raw);rows=payload.get('partidos',[])
        accredited=sum(isinstance(r,dict) and bool(r.get('generated_at') or r.get('predicted_at')) and bool(r.get('prediction_lineage')) for r in rows)
        evidence.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),rows=len(rows),timestamp_and_lineage_candidates=accredited))
    checkpoints=[]
    for path in sorted(Path('docs/v3/models').glob('checkpoint-5.*.json')):
        raw=path.read_bytes();payload=json.loads(raw)
        checkpoints.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),predictions_hash=payload.get('predictions_hash')))
    return dict(champion_sources=evidence,v3_sources=checkpoints,identity_matching_uses_predictions=False)


def paper():
    with locked('paper'):
        candidate = read(ROOT/'candidate.json')
        result = dict(implementation_status='PASS', real_status='BLOCKED_NO_ELIGIBLE_MODEL_PREDICTION',
                      paper_status='BLOCKED_NO_ELIGIBLE_MODEL_PREDICTION', eligible_model_prediction=False,
                      candidate_status='BLOCKED', candidate_present=candidate is not None, paper_entry_created=False, stake_units=1.0,
                      settlement='UNSETTLED', real_oos_contribution=0,
                      reason_codes=['no_accredited_prospective_prediction'],
                      model_search=['docs/v3/models/checkpoint-5.1.json','v3_data/ops/candidate.json'],
                      runtime_artifacts=['v3_data/paper/ledger.jsonl'])
        result['prediction_audit']=prediction_audit()
        if candidate is not None:
            decision = decide(candidate)
            result.update(candidate_status=decision['decision'], reason_codes=decision['reason_codes'])
            if decision['decision'] == 'PASS':
                result['eligible_model_prediction'] = True
                ledger = Ledger()
                existing = next((p for p in ledger.positions() if p['paper_bet_id']==identity(candidate)), None)
                if existing:
                    result.update(real_status='PAPER_RECORDED', paper_status='PAPER_RECORDED', settlement=existing.get('result') or 'UNSETTLED')
                else:
                    try:
                        ledger.record(candidate)
                        result.update(real_status='PAPER_RECORDED', paper_status='PAPER_RECORDED', paper_entry_created=True)
                    except ValueError:
                        result.update(real_status='BLOCKED_NO_ACCREDITED_MODEL_ADAPTER',paper_status='BLOCKED_NO_ACCREDITED_MODEL_ADAPTER',reason_codes=['real_paper_blocked_no_accredited_model_adapter'])
            elif decision['decision']=='NO_BET':
                result.update(real_status='NO_BET',paper_status='NO_BET')
        # Decision records are immutable and deduplicated separately from the
        # existing betting ledger. BLOCKED/NO_BET never create a paper bet.
        content=json.dumps(dict(result,candidate_digest=hashlib.sha256(json.dumps(candidate,sort_keys=True).encode()).hexdigest()),sort_keys=True,indent=2)+'\n'
        digest=hashlib.sha256(content.encode()).hexdigest()
        from .runtime import safe_path,ensure_safe
        ensure_safe(result)
        path=safe_path(ROOT/'decisions'/(digest+'.json'));path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('x') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
        elif path.read_text()!=content:raise ValueError('immutable_decision_conflict')
        return write(ROOT/'paper-status.json', result)


def settle():
    """Only explicit accredited result envelopes; no result retrieval or waiting."""
    with locked('paper'):
        ledger = Ledger(); results = read(ROOT/'results.json', [])
        outcomes = []
        for position in ledger.positions():
            if position['status']=='SETTLED':
                continue
            matches = [r for r in results if r.get('paper_bet_id')==position['paper_bet_id']]
            state = 'UNSETTLED'
            if len(matches)==1:
                result = matches[0]
                if (result.get('synthetic_test_only') is False and result.get('official_result_accredited') is True
                        and result.get('internal_match_id')==position['internal_match_id']):
                    try:
                        ledger.settle(position['paper_bet_id'], result=result['result'], completed_at=result['completed_at'],
                                      settlement_lineage=result['settlement_lineage'],label=result.get('label'))
                        state = result['result']
                    except (ValueError, KeyError, TypeError):
                        state = 'BLOCKED_INVALID_SETTLEMENT'
            outcomes.append(dict(paper_bet_id=position['paper_bet_id'],settlement=state))
        return dict(implementation_status='PASS',positions=outcomes,settlement='UNSETTLED' if not outcomes else 'PROCESSED')
