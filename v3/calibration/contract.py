"""Shared strict contracts for the isolated final phases."""
from datetime import datetime, timezone
from v3.models.contract import canonical, digest
from v3.models.metrics import probability, vector

VERSION = '6.1.0'
BLOCK_REASON = 'phase5_no_accredited_temporal_predictions'


def time(value):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('offset_aware_timestamp_required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('offset_aware_timestamp_required') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('offset_aware_timestamp_required')
    return result.astimezone(timezone.utc)


def required(record, keys):
    if any(record.get(k) is None or record.get(k) == '' for k in keys):
        raise ValueError('missing_required_evidence')


def sealed(value):
    return dict(value, hash=digest(value))


def verify(value):
    if not isinstance(value, dict) or value.get('hash') != digest({k:v for k,v in value.items() if k != 'hash'}):
        raise ValueError('artifact_hash_mismatch')


def prediction_rows(rows, partition, market, synthetic):
    if not rows:
        raise ValueError('empty_partition')
    seen = set()
    for row in rows:
        required(row, ('id','source_model_hash','label_version','temporal_lineage','label_available_at'))
        if row['id'] in seen or row.get('partition') != partition:
            raise ValueError('partition_or_duplicate_invalid')
        seen.add(row['id'])
        if row.get('synthetic_test_only') is not synthetic or row.get('temporal_accredited') is not True:
            raise ValueError('evidence_not_accredited')
        if not time(row['predicted_at']) <= time(row['cutoff']) < time(row['kickoff_at']) < time(row['label_available_at']):
            raise ValueError('prediction_temporal_invalid')
        if market == '1X2':
            vector(row['p'])
            if type(row['y']) is not int or row['y'] not in (0,1,2):
                raise ValueError('invalid_label')
        else:
            probability(row['p'])
            if type(row['y']) is not int or row['y'] not in (0,1):
                raise ValueError('invalid_label')
    return rows
