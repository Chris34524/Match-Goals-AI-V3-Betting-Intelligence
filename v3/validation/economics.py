"""Economics require replayable Phase 4 odds plus accredited later settlement."""
from v3.calibration.contract import time
from v3.value.engine import evaluate
from v3.odds.clv import clv


def economics(rows, *, allow_synthetic=False):
    blocked=dict(economic_status='BLOCKED',roi=None,yield_units=None,profit=None,clv_status='BLOCKED')
    if not rows:return blocked
    profits=[];clvs=[]
    for r in rows:
        try:
            v=evaluate(r['decision_model'],r['odds_observations'],allow_synthetic=allow_synthetic)
            if v['eligibility']!='ELIGIBLE' or r['stake_units']!=1.0 or r['result'] not in ('WIN','LOSS','VOID'):return blocked
            if r.get('settlement_accredited') is not True or not r.get('settlement_lineage'):return blocked
            if not time(v['observed_at']) < time(r['decision_model']['cutoff']) < time(r['kickoff_at']) < time(r['completed_at']) < time(r['settled_at']):return blocked
            if v['internal_match_id']!=r['internal_match_id'] or v['market']!=r['market'] or v['selection']!=r['selection']:return blocked
            if r['decision_model']['cutoff']!=r['cutoff'] or v['kickoff_at']!=r['kickoff_at']:return blocked
            profits.append(v['market_odds']-1 if r['result']=='WIN' else -1 if r['result']=='LOSS' else 0)
            taken=next(o for o in r['odds_observations'] if o['record']['selection']==v['selection'])
            c=clv(taken,r.get('closing'))
            if c['clv_status']=='computable':clvs.append(c['clv_price'])
        except (KeyError,TypeError,ValueError,StopIteration):return blocked
    n=len(profits);profit=sum(profits)
    return dict(economic_status='COMPUTABLE',total_staked=n,total_return=n+profit,profit=profit,
                roi=profit/n,yield_units=profit/n,convention='ROI = Yield = profit / total stake; void returns stake',
                clv_status='COMPUTABLE' if len(clvs)==n else 'BLOCKED',clv=sum(clvs)/n if len(clvs)==n else None)
