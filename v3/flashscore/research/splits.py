"""Expanding windows of whole dates; timing uncertainty blocks evaluation."""
from datetime import date, timezone
from ..contract import timestamp
from ..observation_index import digest


def expanding_folds(rows, *, min_train=100, min_test=25, fold_size=50):
    if any(type(n) is not int or n < 1 for n in (min_train, min_test, fold_size)):
        raise ValueError('invalid_window')
    if len({r['target_key'] for r in rows}) != len(rows):
        raise ValueError('duplicate_target')
    ordered = sorted(rows, key=lambda r: (r['target_date'], r['provider'], r['match_id'], r['target_key']))
    identity_dates = {}
    for r in ordered:
        day = date.fromisoformat(r['target_date'])
        identity = (r['provider'], r['match_id'])
        if identity in identity_dates and identity_dates[identity] != day:
            raise ValueError('conflicting_fixture_date')
        identity_dates[identity] = day
        if timestamp(r['cutoff']).astimezone(timezone.utc).date() >= day or not r.get('provenance_hashes'):
            raise ValueError('untrustworthy_timing')
        if timestamp(r['label_available_at']).astimezone(timezone.utc).date() < day:
            raise ValueError('invalid_label_timing')
    dates = sorted({r['target_date'] for r in ordered})
    folds, end = [], 1
    while end < len(dates):
        train = [r for r in ordered if r['target_date'] < dates[end]]
        if len({(r['provider'], r['match_id']) for r in train}) < min_train:
            end += 1
            continue
        stop = end
        test = []
        while stop < len(dates) and len({(r['provider'], r['match_id']) for r in test}) < fold_size:
            test.extend(r for r in ordered if r['target_date'] == dates[stop])
            stop += 1
        if len({(r['provider'], r['match_id']) for r in test}) < min_test:
            break
        if max(timestamp(r['label_available_at']) for r in train) >= min(timestamp(r['cutoff']) for r in test):
            raise ValueError('train_labels_not_available_before_test')
        identity = dict(train=[r['target_key'] for r in train], test=[r['target_key'] for r in test])
        folds.append(dict(fold_id='fold-' + digest(identity)[:16], train=train, test=test,
            train_start=train[0]['target_date'], train_end=train[-1]['target_date'],
            test_start=test[0]['target_date'], test_end=test[-1]['target_date'],
            train_n=len(train), test_n=len(test)))
        end = stop
    return folds
