"""Chronological 60/20/20 by distinct UTC calendar dates; ties stay together."""
from datetime import timezone
from v3.data.validation import timestamp
from .contract import digest

VERSION = 'utc-distinct-dates-60-20-20-v1'


def date_key(row):
    dt = timestamp(row.get('kickoff_at'))
    if dt is None:
        raise ValueError('missing_kickoff')
    return dt.astimezone(timezone.utc).date().isoformat()


def temporal_split(rows):
    ids = [r['target_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate_target_id')
    ordered = sorted(rows, key=lambda r: (timestamp(r['kickoff_at']), r['target_id']))
    dates = sorted({date_key(r) for r in ordered})
    if len(dates) < 3:
        raise ValueError('insufficient_temporal_dates')
    a = max(1, min(len(dates)-2, int(len(dates)*0.6)))
    b = max(a+1, min(len(dates)-1, int(len(dates)*0.8)))
    groups = {'TRAIN': [], 'VALIDATION': [], 'TEST': []}
    for row in ordered:
        key = date_key(row)
        groups['TRAIN' if key < dates[a] else 'VALIDATION' if key < dates[b] else 'TEST'].append(row)
    manifest = dict(policy_version=VERSION, train_cutoff=dates[a-1],
                    validation_cutoff=dates[b-1], test_start=dates[b],
                    groups={k: dict(ids=[r['target_id'] for r in rs], count=len(rs),
                                    start=rs[0]['kickoff_at'], end=rs[-1]['kickoff_at'])
                            for k, rs in groups.items()})
    manifest['split_hash'] = digest(manifest)
    return groups, manifest
