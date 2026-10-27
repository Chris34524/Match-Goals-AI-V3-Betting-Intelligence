"""Offline targets -> predictions/calibration -> Phase4 value -> selection -> paper -> metrics.

Model fitting is demonstration-only; no production model inferred from Phase 5.
All synthetic results are segregated and excluded from real release evidence.
"""
from pathlib import Path
from v3.calibration.contract import sealed,digest
from v3.calibration.engine import fit,transform,real_state
from v3.models.binary import Logistic
from v3.models.multiclass import Softmax
from v3.models.contract import CONFIGS
from v3.value.fixtures import fixture
from v3.selection.pickscore import WEIGHTS
from v3.selection.daily import daily
from v3.paper.ledger import Ledger
from v3.performance.analyzer import analyze
from v3.performance.oos_gate import evaluate as oos_evaluate
from .release_gate import evaluate as release_evaluate


def synthetic_candidate(market="BTTS"):
    # TRAIN precedes all calibration observations. Only x is given to predict_proba.
    xs=[[-1.] if i%2==0 else [1.] for i in range(100)];ys=[i%2 for i in range(100)]
    if market=='1X2':
        ys=[i%3 for i in range(99)];xs=[[float(k==y)*5 for k in range(3)] for y in ys]
    model=(Softmax() if market=='1X2' else Logistic()).fit(xs,ys,dict(CONFIGS[0]))
    parts=[]
    for partition,start in [('CALIBRATION',1),('CALIBRATION_VALIDATION',6)]:
        rs=[]
        for i in range(4):
            y=i%(3 if market=='1X2' else 2)
            x=[float(k==y)*5 for k in range(3)] if market=='1X2' else [-1.] if y==0 else [1.]
            rs.append(dict(id=f'synthetic-{partition}-{i}',partition=partition,
                           p=model.predict_proba([x])[0],y=y,
                           predicted_at=f'2026-01-{start+i:02d}T09:00:00Z',cutoff=f'2026-01-{start+i:02d}T10:00:00Z',
                           kickoff_at=f'2026-01-{start+i:02d}T12:00:00Z',label_available_at=f'2026-01-{start+i:02d}T15:00:00Z',
                           temporal_accredited=True,temporal_lineage='synthetic-generated-fixture',synthetic_test_only=True,
                           source_model_hash=model.model_hash,label_version='regulation-v1'))
        parts.append(rs)
    calibration=fit(*parts,market=market,synthetic_test_only=True)
    p=model.predict_proba([[5.,0.,0.]] if market=='1X2' else [[1.]])[0];vm,obs=fixture(market=market,p=p[0] if market=='1X2' else p)
    cp=transform(calibration,p,cutoff=vm['cutoff'],source_model_hash=model.model_hash,allow_synthetic=True)
    ece=max(r['ece'] for r in calibration['reliability'].values()) if market=='1X2' else calibration['reliability']['ece']
    selected=cp[0] if market=='1X2' else cp
    quality={k:dict(value=v,status='ELIGIBLE',accredited=True,lineage='synthetic-fixture',synthetic_test_only=True)
             for k,v in zip(WEIGHTS,(selected,100,ece,selected*2-1,0))}
    target={k:vm[k] for k in ('internal_match_id','market','selection','line','cutoff')}
    target.update(kickoff_at=obs[0]['record']['kickoff_at'],target_id='synthetic-target',date='2026-10-26')
    return dict(target=target,model=dict(status='ELIGIBLE',hash=model.model_hash,probability=p,partition='OOS',
                temporal_accredited=True,temporal_lineage='synthetic-fixture',predicted_at='2026-10-26T09:00:00Z',
                synthetic_test_only=True,**{k:vm[k] for k in ('internal_match_id','market','selection','line')}),
                calibration=calibration,value_model=vm,odds_observations=obs,quality=quality,
                integrity_status='PASS',synthetic_test_only=True)


def run(candidates,ledger,*,settlements=(),allow_synthetic=False,record=False):
    if ledger.synthetic is not allow_synthetic:raise ValueError('operation_mode_mismatch')
    picks=daily(candidates,allow_synthetic=allow_synthetic)
    if record:
        for row in picks['pass_candidates']:ledger.record(row['provenance']['candidate'])
        for settlement in settlements:ledger.settle(**settlement)
    performance=analyze(ledger,allow_synthetic=allow_synthetic)
    oos=oos_evaluate(ledger)
    release=release_evaluate({},oos,synthetic_test_only=allow_synthetic)
    return sealed(dict(version='operation-v1',mode='synthetic_test_only' if allow_synthetic else 'production_dry_run',
                       daily=picks,performance=performance,oos_gate=oos,release=release,
                       human_confirmation_required=True,automated_real_betting=False))


def demo(root):
    from v3.paper.ledger import identity
    ledger=Ledger(Path(root)/'v3_data/paper/synthetic-demo.jsonl',synthetic_test_only=True,
                  clock=iter(['2026-10-26T11:00:01Z','2026-10-26T16:00:00Z']).__next__)
    c=synthetic_candidate()
    report=run([c],ledger,allow_synthetic=True,record=True,settlements=[dict(paper_bet_id=identity(c),result='WIN',label=1,
                  completed_at='2026-10-26T15:00:00Z',settlement_lineage='synthetic-result')])
    if len(report['daily']['pass_candidates'])!=1 or report['performance']['eligible_count']!=1:raise ValueError('synthetic_e2e_failed')
    return report


def current_report():
    oos=sealed(dict(gate_status='NOT_MET',real_oos_count=0,required_oos_count=200,reason_codes=['minimum_real_oos_not_met']))
    return sealed(dict(version='operation-v1',real_state=real_state(),real_daily_picks_status='BLOCKED',
                       oos_gate=oos,release=release_evaluate({},oos),human_confirmation_required=True,automated_real_betting=False))
