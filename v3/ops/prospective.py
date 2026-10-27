"""Bounded discovery and a single event odds request per UTC operational day.

Durable intent is written before network. Failed/crashed attempts are terminal
for this tick; the provider quota ledger retains conservative reservations.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from v3.odds.discovery import Discovery, reconcile_pilot
from v3.odds.provider import Config, load_targets, utc
from v3.odds.quota import Budget
from v3.odds.reconciliation import Reconciliation
from v3.odds.collector import plan, collect_live
from v3.odds.the_odds_api import ProviderError, TheOddsAPI
from .runtime import ROOT, read, write, locked
from .target_discovery import inspect, COMPETITIONS

BUDGET = Budget(monthly_hard_limit=500, monthly_soft_limit=450, max_credits_per_run=1)


def now():
    return datetime.now(timezone.utc).isoformat()


def tick_path():
    return ROOT/'ticks'/ (utc(now()).date().isoformat()+'.json')


def tick():
    return read(tick_path(), dict(metadata_calls_attempted=0, metadata_calls_succeeded=0,
                                 sports_calls_attempted=0, events_calls_attempted=0,
                                 odds_calls_attempted=0, odds_calls_succeeded=0,
                                 credits_reserved=0, credits_reported_used=None, provider_remaining_credits=None))


def config_for(sport):
    return dict(provider=asdict(Config((sport,), markets=('1X2',))),budget=asdict(BUDGET),
                reconciliation=dict(competition_mapping={s:c for s,c in COMPETITIONS.values()},
                                    mapping_version='ops-reviewed-exact-v1',kickoff_tolerance_seconds=0))


def prepare(*, live=False):
    with locked('tick'):
        internal = inspect(now())
        targets = load_targets(internal['targets'])
        state = tick()
        result = dict(implementation_status='PASS', real_status=internal['internal_target_status'],
                      capture_status=internal['internal_target_status'], internal_target_status=internal['internal_target_status'],
                      internal_inventory=internal, discovery_status='NOT_RUN', pilot_target_status='BLOCKED',
                      external_event_id_present=False, kickoff=None, plan=None, plan_estimated_cost=None, plan_rejection='NOT_EVALUATED', canonical_record_count=0,
                      snapshot_status='NOT_CAPTURED', reason_codes=[])
        write(ROOT/'pilot-targets.json', [])
        # A config is an allowlist, never evidence that a pilot exists.
        sport = (internal['candidates'] or ['soccer_spain_la_liga'])[0]
        write(ROOT/'pilot-config.json', config_for(sport))
        if live and state['sports_calls_attempted']==0:
            discovery = Discovery(tuple(sorted({t.sport_key for t in targets})[:3]))
            state['sports_calls_attempted'] += 1; state['metadata_calls_attempted'] += 1
            write(tick_path(), state)
            try:
                sports = discovery.sports_list()
                state['metadata_calls_succeeded'] += 1
                result['discovery_status']='PASS'
                # Only mapped competitions with independent accredited targets.
                available = {r['key'] for r in sports if r['active']}
                candidates = sorted({t.sport_key for t in targets} & available)[:3]
                for candidate in candidates:
                    if state['events_calls_attempted'] >= 3:
                        break
                    state['events_calls_attempted'] += 1; state['metadata_calls_attempted'] += 1
                    write(tick_path(),state)
                    events = discovery.events(candidate)
                    state['metadata_calls_succeeded'] += 1
                    try:
                        reconciled = reconcile_pilot(events,[t for t in targets if t.sport_key==candidate],
                                                     Reconciliation(**config_for(candidate)['reconciliation']),now=now())
                    except ProviderError as exc:
                        if str(exc)=='ambiguous_reconciliation':
                            result['reason_codes'].append('ambiguous_reconciliation'); break
                        continue
                    config = config_for(candidate)
                    pilot = plan(Config((candidate,),markets=('1X2',)),[reconciled],BUDGET)
                    if len(pilot['calls'])!=1 or pilot['estimated_cost']!=1 or pilot['rejection'] is not None:
                        raise ValueError('pilot_plan_rejected')
                    write(ROOT/'pilot-config.json',config)
                    write(ROOT/'pilot-targets.json',[asdict(reconciled)])
                    result.update(real_status='PREPARED',capture_status='PREPARED',pilot_target_status='ELIGIBLE',
                                  external_event_id_present=True,kickoff=reconciled.kickoff_at,plan=pilot,plan_estimated_cost=pilot['estimated_cost'],plan_rejection=pilot['rejection'],
                                  target=asdict(reconciled))
                    break
            except ProviderError as exc:
                # ProviderError exposes fixed codes, never the credential-bearing URL.
                result['discovery_status']='BLOCKED_NETWORK' if str(exc)=='network_error' else 'BLOCKED_DISCOVERY'
                result['reason_codes'].append(str(exc))
            write(tick_path(),state)
        elif live:
            result['discovery_status']='ALREADY_ATTEMPTED_NO_RETRY'
        if not targets:
            result['real_status']=result['capture_status']='BLOCKED_NO_FRESH_INTERNAL_TARGET'
            result['reason_codes'].append('no_independent_accredited_future_timezone_aware_internal_target')
        # Preserve evidence of a previous capture; prepare cannot reset a spent credit.
        result['credits']=state
        return write(ROOT/'capture-status.json',result)


def capture(*, live=False):
    with locked('tick'):
        result = read(ROOT/'capture-status.json',{})
        state = tick()
        if not live:
            return dict(result, capture_status='BLOCKED_MISSING_LIVE_FLAG')
        if state['odds_calls_attempted']:
            return dict(result,capture_status='ALREADY_ATTEMPTED_NO_RETRY',credits=state)
        from .validation import receipt_valid
        if not receipt_valid():
            return dict(result,capture_status='BLOCKED_VALIDATION_REQUIRED')
        rows = read(ROOT/'pilot-targets.json',[])
        if len(rows)!=1:
            return dict(result,capture_status='BLOCKED_NO_FRESH_INTERNAL_TARGET')
        target = load_targets(rows)[0]
        # Replay independent internal lineage at the wall clock, never trust old prepare.
        fresh = load_targets(inspect(now())['targets'])
        if not any(asdict(t)==dict(asdict(target),external_event_id=None) for t in fresh):
            return dict(result,capture_status='BLOCKED_INTERNAL_TARGET_CHANGED')
        settings = config_for(target.sport_key)
        config = Config((target.sport_key,), markets=('1X2',))
        pilot = plan(config,[target],BUDGET)
        if (target.external_event_id is None or utc(target.kickoff_at)<=utc(now())
                or len(pilot['calls'])!=1 or pilot['estimated_cost']!=1 or pilot['rejection'] is not None):
            return dict(result,capture_status='BLOCKED_PLAN')
        # Intent consumes the daily attempt even if interruption occurs before HTTP.
        from v3.odds.the_odds_api import authorize
        authorize(True,config.markets)
        state.update(odds_calls_attempted=1,credits_reserved=1)
        write(tick_path(),state)
        try:
            adapter=TheOddsAPI(config,transport=Discovery((target.sport_key,))._transport)
            path = collect_live([target],config,Reconciliation(**settings['reconciliation']),live=True,budget=BUDGET,root='v3_data/odds',adapter=adapter)
            manifest=json.loads((path/'manifest.json').read_text())
            raw=(path/'canonical.jsonl').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=manifest['canonical_sha256']:
                raise ValueError('capture_digest_mismatch')
            records=[json.loads(line) for line in raw.splitlines()]
            if any(r['snapshot_type']!='current' or not utc(r['observed_at'])<utc(r['kickoff_at']) for r in records):
                raise ValueError('capture_temporal_invalid')
            state.update(odds_calls_succeeded=1,credits_reported_used=manifest['credits_actual'])
            headers=manifest.get('quota_headers',[])
            if headers:
                state['provider_remaining_credits']=headers[-1].get('x-requests-remaining')
            status='CAPTURED' if records else 'BLOCKED_NO_CANONICAL_RECORDS'
            result.update(real_status=status,capture_status=status,canonical_record_count=len(records),
                          manifest_path=str(path/'manifest.json'),snapshot_status='pilot_current' if records else 'NOT_CAPTURED')
            # Operational wrapper deliberately does not claim a scheduled Phase 3 slot.
            write(ROOT/'pilot-current.json',dict(semantic='pilot_current',phase3_snapshot_type='current',
                                                run_id=manifest['run_id'],canonical_sha256=manifest['canonical_sha256'],
                                                source_sha256=manifest['source_sha256'],manifest_path=str(path/'manifest.json'),
                                                opening_accredited=False,closing_accredited=False))
        except (ProviderError, ValueError, OSError, KeyError, TypeError):
            result.update(real_status='BLOCKED_CAPTURE_FAILED',capture_status='BLOCKED_CAPTURE_FAILED',
                          reason_codes=['single_attempt_terminal_reservation_retained'])
        write(tick_path(),state)
        result['credits']=state
        return write(ROOT/'capture-status.json',result)
