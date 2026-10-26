"""Deterministic derived report; source observations are never overwritten."""
import json
from .snapshots import load_snapshots
from .scheduler import load_history
from .movement import movements, dispersion
from .storage import DEFAULT_ROOT, digest, encoded, publish


def report(root=DEFAULT_ROOT, *, expected_books=()):
    snapshots=load_snapshots(root)
    history=load_history(root)
    groups={}
    for s in snapshots:
        r=s['record']
        key=(r['internal_match_id'],r['provider'],r['market'],r['selection'],r['line'],s['slot'],r['observed_at'],s['run_id'])
        groups.setdefault(key,[]).append(s)
    populations=[]
    for key, values in sorted(groups.items(),key=lambda item:str(item[0])):
        value=dispersion(values,expected_books=expected_books)
        if value is not None:
            populations.append({'series':list(key),**value})
    return dict(schema_version='3.3.0',snapshot_count=len(snapshots),
                snapshots_sha256=digest(encoded(snapshots)), schedule_history=history,
                movements=movements(snapshots),dispersion=populations,
                closing_accredited=any(s['closing_accredited'] for s in snapshots),
                clv_status='blocked', clv_reason='no_explicit_decision_and_comparable_closing_pair',
                markets=sorted({s['record']['market'] for s in snapshots}),
                books=sorted({s['record']['bookmaker'] for s in snapshots}))


def store_report(root=DEFAULT_ROOT, *, expected_books=()):
    from .storage import safe_root
    value=report(root,expected_books=expected_books)
    return publish(safe_root(root)/'reports',digest(encoded(value)),{'report.json':encoded(value)})
