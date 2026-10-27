"""Operational projections of the existing real OOS and performance contracts."""
from collections import Counter
from v3.performance.oos_gate import count_positions
from v3.performance.analyzer import eligible, summarize
from v3.paper.ledger import Ledger


def checkpoint(count):
    return 'GATE_MET' if count >= 200 else 'CHECKPOINT_100' if count >= 100 else 'CHECKPOINT_50' if count >= 50 else 'COLLECTING'


def report(positions=None, *, integrity_status='PASS'):
    decision_counts=Counter()
    if positions is None:
        import hashlib
        from .runtime import ROOT,read
        decisions=[]
        for path in sorted((ROOT/'decisions').glob('*.json')):
            if hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem:
                raise ValueError('decision_digest_mismatch')
            decisions.append(read(path))
        # Distinct candidate evidence only; repeated ticks cannot inflate decisions.
        unique={d['candidate_digest']:d for d in decisions if d.get('candidate_present')}
        decision_counts.update(d['candidate_status'] for d in unique.values())
        try:
            positions = Ledger().positions()
        except (ValueError, KeyError, TypeError, OSError):
            positions = []; integrity_status = 'FAIL'
    gate = count_positions(positions, integrity_status=integrity_status)
    ids = Counter(p.get('paper_bet_id') for p in positions)
    selected = [p for p in positions if eligible(p) and ids[p['paper_bet_id']] == 1]
    markets = {}
    for market in sorted({p['market'] for p in selected}):
        group = [p for p in selected if p['market'] == market]
        try:
            metrics = summarize(group, False)
        except (ValueError, KeyError, TypeError):
            metrics = dict(status='BLOCKED', reason_codes=['performance_lineage_invalid'])
        markets[market] = dict(count=len(group), performance=metrics)
    count = gate['real_oos_count']
    return dict(implementation_status='PASS', real_status=gate['gate_status'], oos_gate_status=gate['gate_status'],
                real_oos_count=count, required_oos_count=200, progress_fraction=min(count / 200, 1),
                progress_percent=min(count / 2, 100), checkpoint_status=checkpoint(count),
                unique_matches=count, eligible_picks=len(selected), settled_picks=sum(p.get('status')=='SETTLED' for p in positions),
                unsettled_picks=sum(p.get('status') in ('OPEN','UNSETTLED') for p in positions),
                blocked_picks=decision_counts['BLOCKED']+sum(p.get('decision')=='BLOCKED' for p in positions),
                no_bet=decision_counts['NO_BET']+sum(p.get('decision')=='NO_BET' for p in positions),
                duplicates_excluded=sum(n for n in ids.values() if n>1),
                synthetic_excluded=sum(p.get('synthetic_test_only') is not False for p in positions),
                by_market=markets, quality=integrity_status, reason_codes=gate['reason_codes'],
                metrics_available=bool(selected) and all(m['performance']['status']!='BLOCKED' for m in markets.values()),
                metrics_blocked=[] if selected else ['no_eligible_settled_real_paper'], gate=gate)
