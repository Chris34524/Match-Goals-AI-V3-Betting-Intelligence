"""Comparable price series and reproducible same-capture bookmaker populations."""
import statistics
from .provider import utc
from .snapshots import series, validate_snapshot, accredited

PAIRS = (('T-24h','T-6h'),('T-6h','T-1h'),('T-24h','T-1h'))


def comparable(before, after):
    try:
        validate_snapshot(before); validate_snapshot(after)
        a,b=before['record'],after['record']
        return (series(a)==series(b) and utc(a['kickoff_at'])==utc(b['kickoff_at'])
                and a['external_match_id']==b['external_match_id']
                and utc(a['observed_at']) < utc(b['observed_at']))
    except (ValueError, KeyError, TypeError):
        return False


def movement(before, after, *, open_to_current=False):
    if not comparable(before,after):
        return None
    if open_to_current:
        if not accredited(before['record'],'opening') or after['record']['snapshot_type'] != 'current':
            return None
    elif (before['slot'],after['slot']) not in PAIRS:
        return None
    a,b=before['record'],after['record']
    p,q=a['decimal_odds'],b['decimal_odds']
    return dict(series=list(series(a)), from_slot=before['slot'],to_slot=after['slot'],
                before_observed_at=a['observed_at'],after_observed_at=b['observed_at'],
                before_run_id=before['run_id'],after_run_id=after['run_id'],
                decimal_odds_delta=q-p, implied_probability_before=1/p,
                implied_probability_after=1/q, implied_probability_delta=1/q-1/p,
                relative_price_change=q/p-1,
                interval_seconds=(utc(b['observed_at'])-utc(a['observed_at'])).total_seconds(),
                direction='shortened' if q<p else 'lengthened' if q>p else 'unchanged')


def movements(snapshots):
    # Preserve repeated observations: enumerate every comparable pair, never select
    # an implicit opening/closing or silently discard intermediate observations.
    ordered=sorted(snapshots,key=lambda s:(s['record']['observed_at'],s['run_id']))
    values=[m for a in ordered for b in ordered if (m:=movement(a,b)) is not None]
    return sorted(values,key=lambda m:(str(m['series']),m['from_slot'],m['to_slot'],m['before_observed_at'],m['after_observed_at']))


def dispersion(snapshots, *, expected_books):
    """Population must be explicit, complete and captured in the same run/clock.

    Sample stdev; mean reciprocal odds is a descriptive consensus, not de-vigged.
    """
    if not expected_books or len(set(expected_books)) != len(expected_books) or len(expected_books)<2:
        return None
    if len(snapshots)!=len(expected_books):
        return None
    try:
        for s in snapshots: validate_snapshot(s)
    except (ValueError, KeyError, TypeError):
        return None
    records=[s['record'] for s in snapshots]
    if set(r['bookmaker'] for r in records)!=set(expected_books):
        return None
    def group(s):
        r=s['record']
        return (r['internal_match_id'],r['external_match_id'],r['provider'],r['market'],r['selection'],r['line'],
                r['observed_at'],r['kickoff_at'],s['slot'],s['run_id'])
    if len({group(s) for s in snapshots})!=1:
        return None
    odds=[r['decimal_odds'] for r in records]
    return dict(population=sorted(expected_books),n_books=len(odds),mean_odds=statistics.mean(odds),
                median_odds=statistics.median(odds),min=min(odds),max=max(odds),
                range=max(odds)-min(odds),stdev=statistics.stdev(odds),
                consensus_implied_probability=statistics.mean(1/p for p in odds),
                consensus_definition='mean reciprocal decimal odds; no margin removal',
                run_id=snapshots[0]['run_id'])
