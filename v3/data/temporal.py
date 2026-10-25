"""Conservative temporal policy for every future V3 input adapter.

Day resolution is intentional: timestamps in raw samples are not independently
verified, so even an apparent earlier kickoff cannot authorize same-day inputs.
"""
from v3.data.validation import day


def sample_reasons(target_id, target_date, sample_id, sample_date):
    reasons = []
    target, sample = day(target_date), day(sample_date)
    if sample_id == target_id:
        reasons.append('target_in_input')
    if not isinstance(sample_id, str) or not sample_id:
        reasons.append('unknown_input_identity')
    if sample is None:
        reasons.append('unknown_input_date')
    if target is None:
        reasons.append('unknown_target_date')
    if target is not None and sample is not None:
        if sample > target:
            reasons.append('future_input')
        elif sample == target:
            reasons.append('same_day_input_without_verified_time')
    return sorted(reasons)


def eligible_status(status):
    return status == 'OK'
