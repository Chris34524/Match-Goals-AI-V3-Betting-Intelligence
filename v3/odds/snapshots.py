"""Append-only snapshots over unchanged canonical 3.1 records."""
from datetime import timedelta
from .contract import schema_errors
from .provider import utc
from .storage import DEFAULT_ROOT, digest, encoded, publish, safe_root

VERSION = '3.3.0'
SERIES_FIELDS = ('internal_match_id','provider','bookmaker','market','selection','line')


def series(record):
    return tuple(record[k] for k in SERIES_FIELDS)


def accredited(record, kind):
    """Explicit 3.1 definition + evidence, never first/last observation position."""
    return (kind in ('opening','closing') and record.get('snapshot_type') == kind
            and not schema_errors(record,record.get('observed_at'))
            and record['validity']['pre_match'])


def validate_snapshot(snapshot):
    r = snapshot['record']
    if schema_errors(r,r['observed_at']) or not r['validity']['pre_match']:
        raise ValueError('invalid_pre_match_snapshot')
    if utc(r['observed_at']) >= utc(r['kickoff_at']):
        raise ValueError('snapshot_not_pre_match')
    if snapshot['slot'] not in ('T-24h','T-6h','T-1h','decision'):
        raise ValueError('invalid_slot')
    expected = {'T-24h':86400,'T-6h':21600,'T-1h':3600}.get(snapshot['slot'])
    offset = snapshot['scheduled_offset']
    if expected is not None and offset != expected:
        raise ValueError('invalid_slot_offset')
    if snapshot['slot'] == 'decision' and not 0 < offset < 3600:
        raise ValueError('invalid_decision_offset')
    scheduled = utc(r['kickoff_at']) - timedelta(seconds=offset)
    if utc(snapshot['scheduled_at']) != scheduled:
        raise ValueError('scheduled_time_mismatch')
    if not (0 <= snapshot['window_seconds'] <= 300
            and scheduled <= utc(r['observed_at']) <= scheduled + timedelta(seconds=snapshot['window_seconds'])):
        raise ValueError('snapshot_outside_capture_window')
    if snapshot.get('provider_last_update') != r['source_published_at']:
        raise ValueError('provider_timestamp_mismatch')
    if snapshot['closing_accredited'] != accredited(r,'closing'):
        raise ValueError('closing_accreditation_mismatch')
    if snapshot['opening_accredited'] != accredited(r,'opening'):
        raise ValueError('opening_accreditation_mismatch')
    import re
    if any(not isinstance(snapshot.get(k),str) or not re.fullmatch('[a-f0-9]{64}',snapshot[k])
           for k in ('run_id','source_digest')):
        raise ValueError('invalid_snapshot_provenance')
    return snapshot


def make_snapshot(record, schedule_row, *, run_id, source_digest):
    from copy import deepcopy
    if schedule_row['internal_match_id'] != record['internal_match_id']:
        raise ValueError('snapshot_target_mismatch')
    snapshot = dict(schema_version=VERSION, record=deepcopy(record), slot=schedule_row['slot'],
                    scheduled_offset=schedule_row['scheduled_offset'], scheduled_at=schedule_row['scheduled_at'],
                    window_seconds=schedule_row['window_seconds'], run_id=run_id,source_digest=source_digest,
                    provider_last_update=record['source_published_at'],
                    closing_accredited=accredited(record,'closing'),opening_accredited=accredited(record,'opening'))
    return validate_snapshot(snapshot)


def identity(snapshot):
    r=snapshot['record']
    return {**{k:r[k] for k in SERIES_FIELDS}, 'slot':snapshot['slot'], 'observed_at':r['observed_at']}


def store_snapshot(snapshot, *, root=DEFAULT_ROOT):
    validate_snapshot(snapshot)
    # Identity conflict is rejected; only the complete semantically identical JSON
    # observation (including provenance) dedupes. No field or history is dropped.
    return publish(safe_root(root)/'snapshots',digest(encoded(identity(snapshot))),
                   {'snapshot.json':encoded(snapshot)})


def load_snapshots(root=DEFAULT_ROOT):
    import json
    return [validate_snapshot(json.loads(p.read_text()))
            for p in sorted((safe_root(root)/'snapshots').glob('*/snapshot.json'))]
