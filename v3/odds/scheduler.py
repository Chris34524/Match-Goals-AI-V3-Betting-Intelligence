"""Deterministic target schedule; clocks are UTC and missed slots never backfill."""
from dataclasses import dataclass
from datetime import timedelta
from .provider import utc, utc_now
from .quota import Budget, estimate
from .storage import DEFAULT_ROOT, digest, encoded, publish

SLOTS = {'T-24h': 86400, 'T-6h': 21600, 'T-1h': 3600}
SLOT_PRIORITY = {'T-1h': 0, 'T-6h': 1, 'T-24h': 2, 'decision': 3}
VERSION = 'schedule-1'


@dataclass(frozen=True)
class ScheduleConfig:
    window_seconds: int = 60
    decision_offset_seconds: int | None = None

    def __post_init__(self):
        if (not 0 <= self.window_seconds <= 300
                or (self.decision_offset_seconds is not None
                    and not self.window_seconds < self.decision_offset_seconds < 3600)):
            raise ValueError('invalid_schedule_config')

    def slots(self):
        return {**SLOTS, **({'decision': self.decision_offset_seconds}
                            if self.decision_offset_seconds is not None else {})}


def schedule(targets, config, *, now, budget=Budget(), credits_used_local=0,
             credits_remaining_provider=None, policy=ScheduleConfig(), history=()):
    """Reserve a virtual budget for selected slots; no network or ledger mutations.

    Budget order: P0..P3, T1/T6/T24/decision, then stable match ID. Planned future
    slots consume the virtual plan budget, but never reserve real credits early.
    Terminal history prevents replay, including when a caller supplies an old clock.
    """
    clock = utc(now)
    if len({t.internal_match_id for t in targets}) != len(targets):
        raise ValueError('duplicate_target')
    terminal = {(h['internal_match_id'], h['slot']): h for h in history
                if h['status'] in ('executed', 'missed', 'skipped_budget', 'failed')}
    rows = []
    for target in targets:
        if target.sport_key not in config.sports or not set(target.markets) <= set(config.markets):
            raise ValueError('target_outside_allowlist')
        for slot, offset in policy.slots().items():
            scheduled = utc(target.kickoff_at) - timedelta(seconds=offset)
            row = dict(internal_match_id=target.internal_match_id, slot=slot,
                       scheduled_at=scheduled.isoformat(), scheduled_offset=offset,
                       kickoff_at=utc(target.kickoff_at).isoformat(), priority=target.priority,
                       estimated_cost=estimate(config,target.markets),
                       due=scheduled <= clock <= scheduled + timedelta(seconds=policy.window_seconds)
                       and clock < utc(target.kickoff_at), policy_version=VERSION,
                       window_seconds=policy.window_seconds)
            key = (target.internal_match_id, slot)
            if key in terminal:
                row.update(status=terminal[key]['status'], due=False, reason='terminal_history')
            elif clock >= utc(target.kickoff_at) or clock > scheduled + timedelta(seconds=policy.window_seconds):
                row.update(status='missed', reason='window_elapsed')
            else:
                row.update(status='planned', reason=None)
            rows.append(row)
    rows.sort(key=lambda r: (r['priority'], SLOT_PRIORITY[r['slot']], r['internal_match_id']))
    allocated = 0
    for row in rows:
        if row['status'] != 'planned':
            continue
        # The run cap applies to the aggregate selected plan, too.
        reason = budget.check(allocated + row['estimated_cost'], credits_used_local, credits_remaining_provider)
        if reason:
            row.update(status='skipped_budget', due=False, reason=reason)
        else:
            allocated += row['estimated_cost']
    return rows


def load_history(root=DEFAULT_ROOT):
    import json
    from .storage import safe_root
    return [row for p in sorted((safe_root(root)/'schedule').glob('*/manifest.json'))
            for row in json.loads(p.read_text())['targets']]


def execute(targets, config, reconciliation, *, root=DEFAULT_ROOT, live=False,
            budget=Budget(), policy=ScheduleConfig(), fixture_payload=None, fixture_now=None):
    """One scheduler tick. Use an external timer; there is no continuous polling.

    Offline fixture clocks are explicit. A live caller cannot override capture time.
    Failed/missing prices do not become executed snapshots. Each tick is immutable.
    """
    from .collector import collect_fixture, collect_live
    from .snapshots import make_snapshot, store_snapshot
    from .the_odds_api import authorize
    from .quota import ledger
    import json
    import fcntl
    from .storage import safe_root
    root = safe_root(root)
    root.mkdir(parents=True, exist_ok=True)
    if fixture_payload is None:
        authorize(live, config.markets)
        if fixture_now is not None:
            raise ValueError('live_clock_override_forbidden')
    elif live:
        raise ValueError('fixture_live_mixed')
    now = fixture_now if fixture_payload is not None and fixture_now is not None else utc_now()
    with (root/'.scheduler.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with ledger(root, now) as (state, *_):
            rows = schedule(targets, config, now=now, budget=budget, policy=policy,
                            credits_used_local=state['used'], credits_remaining_provider=state['remaining'],
                            history=load_history(root))
        by_id = {t.internal_match_id: t for t in targets}
        for row in rows:
            row.update(run_id=None, snapshot_digests=[], snapshot_ids=[], credits_actual=0,
                       markets_covered=[], books_covered=[], rejected_count=0, rejection_reasons=[],
                       markets_requested=list(by_id[row['internal_match_id']].markets),
                       books_requested=list(config.bookmakers), closing_accredited=False,
                       clv_status='blocked', clv_reason='no_accredited_closing')
            if row['status'] != 'planned' or not row['due']:
                continue
            target = by_id[row['internal_match_id']]
            # Recheck actual execution clock: earlier requests can exhaust the window.
            actual_now = now if fixture_payload is not None else utc_now()
            if (utc(actual_now) >= utc(target.kickoff_at)
                    or utc(actual_now) > utc(row['scheduled_at']) + timedelta(seconds=policy.window_seconds)):
                row.update(status='missed', reason='execution_window_elapsed')
                continue
            try:
                if fixture_payload is not None:
                    run = collect_fixture(fixture_payload,[target],config,reconciliation,
                                          observed_at=actual_now,root=root)
                else:
                    run = collect_live([target],config,reconciliation,live=live,budget=budget,root=root)
                manifest = json.loads((run/'manifest.json').read_text())
                row.update(run_id=manifest['run_id'], credits_actual=manifest['credits_actual'],
                           rejected_count=len(manifest['rejected']),
                           rejection_reasons=sorted({reason for item in manifest['rejected'] for reason in item['reasons']}))
                records = [json.loads(line) for line in (run/'canonical.jsonl').read_text().splitlines()]
                if any(utc(r['observed_at']) > utc(row['scheduled_at']) + timedelta(seconds=policy.window_seconds)
                       or utc(r['observed_at']) >= utc(target.kickoff_at) for r in records):
                    row.update(status='missed', reason='response_outside_capture_window')
                    continue
                for record in records:
                    snapshot = make_snapshot(record,row,run_id=run.name,
                                             source_digest=manifest['source_sha256'])
                    path = store_snapshot(snapshot,root=root)
                    row['snapshot_digests'].append(digest(encoded(snapshot)))
                    row['snapshot_ids'].append(path.name)
                    row['markets_covered'].append(record['market'])
                    row['books_covered'].append(record['bookmaker'])
                row['markets_covered'] = sorted(set(row['markets_covered']))
                row['books_covered'] = sorted(set(row['books_covered']))
                row['status'] = 'executed' if row['snapshot_digests'] else 'failed'
                row['reason'] = None if row['snapshot_digests'] else 'no_valid_observations'
            except (ValueError, RuntimeError, OSError):
                row.update(status='failed',reason='capture_or_snapshot_validation_failed',
                           credits_actual=0 if fixture_payload is not None else None)
        report = dict(schema_version='3.3.0', schedule_version=VERSION, observed_at=now, targets=rows,
                      credits_estimated=sum(r['estimated_cost'] for r in rows if r['status']=='executed' or (r['status']=='failed' and r['due'])),
                      credits_actual=sum(r['credits_actual'] for r in rows) if all(r['credits_actual'] is not None for r in rows) else None,
                      closing_accredited=False, clv_status='blocked',
                      temporal_comparison='use only comparable stored snapshot series')
        run_id = digest(encoded(report))
        return publish(root/'schedule',run_id,{'manifest.json':encoded(report)})
