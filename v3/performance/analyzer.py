"""Only replayed, settled OOS ledger entries are eligible for descriptive metrics."""
from v3.calibration.contract import sealed,time
from v3.calibration.engine import transform
from v3.calibration.reliability import metrics
from v3.validation.economics import economics
from .drawdown import drawdown


def eligible(p, *, synthetic_test_only=False):
    try:
        return (p['synthetic_test_only'] is synthetic_test_only and p['real'] is (not synthetic_test_only)
                and p['status']=='SETTLED' and p['partition']=='OOS' and p['decision']=='PASS'
                and p['eligible'] is True and p['backfilled'] is False and bool(p['temporal_lineage'])
                and p['settlement_accredited'] is True and bool(p['settlement_lineage'])
                and p['stake_units']==1.0
                and time(p['observed_at'])<time(p['cutoff'])<=time(p['created_at'])<time(p['kickoff_at'])<time(p['completed_at'])<time(p['settled_at']))
    except (KeyError,TypeError,ValueError):return False


def summarize(positions,synthetic):
    if not positions:return dict(status='BLOCKED',predictive_status='BLOCKED',economic_status='BLOCKED',metrics=None,economics=None,clv_status='BLOCKED',drawdown=None)
    economic=[];groups={}
    for p in positions:
        candidate=p['decision_provenance']['candidate']
        economic.append(dict(p,decision_model=dict(candidate['value_model'],model_probability=p['calibrated_probability']),odds_observations=candidate['odds_observations']))
        if p['result']=='VOID':continue
        cal=candidate['calibration'];model=candidate['model']
        cp=transform(cal,model['probability'],cutoff=p['cutoff'],source_model_hash=model['hash'],allow_synthetic=synthetic)
        groups.setdefault(p['market'],[]).append((p['label'],cp))
    predictive={market:metrics([x[0] for x in pairs],[x[1] for x in pairs],market) for market,pairs in sorted(groups.items())}
    # Cross-market aggregate uses normalized per-record loss conventions explicitly.
    count=sum(len(pairs) for pairs in groups.values())
    aggregate={key:sum(predictive[m][key]*len(groups[m]) for m in groups)/count for key in ('brier','logloss','accuracy')} if count else None
    econ=economics(economic,allow_synthetic=synthetic)
    return dict(status='COMPUTABLE',predictive_status='COMPUTABLE' if count else 'NOT_APPLICABLE',
                metrics=dict(overall=aggregate,by_market=predictive,brier_convention='binary squared error; 1X2 sum class errors; pooled descriptive mean'),
                economic_status=econ['economic_status'],economics=econ,clv_status=econ['clv_status'],drawdown=drawdown(positions))


def analyze(ledger, *, allow_synthetic=False):
    if ledger.synthetic is not allow_synthetic:raise ValueError('ledger_analyzer_origin_mismatch')
    positions=ledger.positions() # validates event hashes, sequence, duplicate settlements
    selected=[p for p in positions if eligible(p,synthetic_test_only=allow_synthetic)]
    report=summarize(selected,allow_synthetic)
    by_model={};by_period={}
    for p in selected:
        by_model.setdefault(p['model_id'],[]).append(p)
        by_period.setdefault(time(p['settled_at']).strftime('%Y-%m'),[]).append(p)
    return sealed(dict(version='performance-v1',synthetic_test_only=allow_synthetic,eligible_count=len(selected),excluded_count=len(positions)-len(selected),
                       overall=report,by_model={k:summarize(v,allow_synthetic) for k,v in sorted(by_model.items())},
                       by_period={k:summarize(v,allow_synthetic) for k,v in sorted(by_period.items())},
                       real_status='BLOCKED' if allow_synthetic or not selected else 'COMPUTABLE',
                       limitations=['Descriptive only; no policy/model refit from paper outcomes.','Local hash-chain integrity is not independent temporal accreditation.']))
