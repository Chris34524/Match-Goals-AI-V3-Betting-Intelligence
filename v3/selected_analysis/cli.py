"""Select fixtures and produce isolated multimarket reports. Offline by default."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys
import webbrowser

from v3.flashscore.contract import dumps
from v3.flashscore.market_contract import CardSettlementPolicy
from v3.providers.api_football.client import AcquisitionError, Client
from v3.providers.full_capture import capture, flashscore_live_state, plan
from . import fixtures
from .engine import analyze
from .evidence import ROOT, read_json
from .report import destination, write


def validate_capture_identity(fixture, manifest):
    if manifest['reason'] == 'PLANNED' or not manifest['completed_surfaces']:
        return
    if manifest['provider_fixture_id'] != fixture['provider_fixture_id']:
        raise ValueError('capture_fixture_identity_conflict')
    for key, actual in (('competition_id', manifest.get('competition')), ('season', manifest.get('season'))):
        if fixture.get(key) is not None and str(actual) != fixture[key]:
            raise ValueError('capture_fixture_identity_conflict')
    for side in ('home', 'away'):
        actual = manifest.get(side)
        if fixture[side]['id'] is not None and (
                not isinstance(actual, dict) or str(actual.get('id')) != fixture[side]['id']):
            raise ValueError('capture_fixture_identity_conflict')
    if fixture['kickoff'] and manifest.get('kickoff'):
        from v3.flashscore.contract import timestamp
        if timestamp(fixture['kickoff']) != timestamp(manifest['kickoff']):
            raise ValueError('capture_fixture_identity_conflict')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('list', 'select', 'analyze', 'audit-flashscore'))
    parser.add_argument('--provider', choices=('flashscore', 'api_football'), default='flashscore')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--candidates', type=Path, help='Official provider fixture candidates for stable-ID reconciliation')
    parser.add_argument('--date', default='today', help='today, tomorrow, hoy, mañana or YYYY-MM-DD')
    parser.add_argument('--timezone', default=fixtures.TIMEZONE)
    for key in ('country', 'competition', 'team'):
        parser.add_argument('--'+key)
    parser.add_argument('--indices')
    parser.add_argument('--match-id', action='append', default=[])
    parser.add_argument('--max-matches', type=int, default=6)
    parser.add_argument('--history-root', type=Path, default=ROOT/'data/matches')
    parser.add_argument('--capabilities', type=Path, action='append', default=[])
    parser.add_argument('--card-policy', type=Path)
    parser.add_argument('--cutoff', help='Explicit timezone-aware prematch feature cutoff')
    parser.add_argument('--generated-at', help='Fixed report time for deterministic offline replay; never OOS accreditation')
    parser.add_argument('--output', type=Path, default=Path('v3_data/selected_analysis'))
    parser.add_argument('--live', action='store_true', help='Explicit authorization for bounded official API acquisition')
    parser.add_argument('--max-requests', type=int)
    parser.add_argument('--replay-dir', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='Print selection/capture plan only; zero HTTP and no reports')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args(argv)
    client = None
    try:
        if args.command == 'audit-flashscore':
            if args.live:
                raise ValueError('coverage_audit_is_offline_only')
            from .flashscore_reference import coverage
            print(dumps(coverage(args.history_root)))
            return 0
        if args.live and args.dry_run:
            raise ValueError('live_and_dry_run_are_exclusive')
        if args.live and args.generated_at:
            raise ValueError('fixed_report_time_only_allowed_for_offline_replay')
        if args.replay_dir and args.provider != 'flashscore':
            raise ValueError('structured_replay_directory_requires_flashscore')
        if args.live and args.provider == 'flashscore':
            print(dumps(dict(status='BLOCKED', reason=flashscore_live_state(), request_count=0)))
            return 2
        if args.live:
            if args.max_requests is None or args.max_requests < 1:
                raise ValueError('explicit_positive_request_budget_required')
            print(dumps(dict(acquisition='explicit_live', provider=args.provider,
                             maximum_requests=args.max_requests)), flush=True)
            client = Client(live=True, max_requests=args.max_requests, retries=0)
            if args.max_requests > 3:
                client.get('/status')
        date = fixtures.resolve_date(args.date, args.timezone)
        source_evidence, source_exclusions = None, []
        if client and args.source is None:
            payload, receipt = client.get('/fixtures', dict(date=date.isoformat(), timezone=args.timezone))
            if payload.get('paging', {}).get('total', 1) > 1:
                raise ValueError('fixture_discovery_pagination_incomplete')
            rows = fixtures.universe(payload['response'], args.provider, args.timezone, exclusions=source_exclusions)
            source_evidence = asdict(receipt)
        else:
            path = args.source or ROOT/'data/partidos.json'
            candidates = fixtures.rows_from_document(read_json(args.candidates)[0]) if args.candidates else []
            document, source_evidence = read_json(path)
            rows = fixtures.universe(fixtures.rows_from_document(document), args.provider, args.timezone, candidates,
                                     exclusions=source_exclusions)
        rows = fixtures.filtered(rows, date, args.country, args.competition, args.team)
        print('MATCH GOALS AI — PARTIDOS DISPONIBLES\nFecha: '+date.isoformat())
        for i, row in enumerate(rows, 1):
            print(f"{i:02}. {row['home']['name']} vs {row['away']['name']} | "
                  f"{row['competition']} | {row['display_time'] or 'N/D'} | "
                  f"{row['provider']}:{row['provider_fixture_id']}")
        if source_exclusions:
            print(dumps(dict(excluded_conflicting_fixtures=[
                {k: v for k, v in r.items() if k != 'variants'} for r in source_exclusions])))
        if args.command == 'list':
            print(dumps(dict(total=len(rows), network_requests=client.used if client else 0,
                             source=source_evidence)))
            return 0
        expression = args.indices
        if not expression and not args.match_id:
            if not sys.stdin.isatty():
                raise ValueError('explicit_selection_required_for_automation')
            expression = input('Selecciona partidos (1,3 / 1-5): ')
        selected = fixtures.choose(rows, expression, args.match_id, args.max_matches)
        capture_plan = plan(selected, args.provider, args.max_requests, client.quota if client else None)
        print(dumps(dict(selected=selected, capture_plan=capture_plan,
                         network_requests=client.used if client else 0)), flush=True)
        if args.command == 'select' or args.dry_run:
            return 0
        destination(args.output)
        policy = CardSettlementPolicy(**read_json(args.card_policy)[0]) if args.card_policy else None
        paths = args.capabilities or sorted((ROOT/'v3_data/providers'/args.provider/'matches').glob('*/capabilities.json'))
        if args.replay_dir:
            paths = list(paths)+sorted(args.replay_dir.glob('*.json'))
        for fixture in selected:
            generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
            manifest, _ = capture(fixture, args.provider, client=client, replay_dir=args.replay_dir,
                                   root=Path('v3_data/providers') if client or args.replay_dir else None)
            validate_capture_identity(fixture, manifest)
            if client is None:
                manifest['captured_at'] = None  # No new provider capture occurred.
                if args.replay_dir:
                    manifest['replayed_at'] = generated_at
            report = analyze(fixture, history_root=args.history_root, capability_paths=paths,
                cutoff=args.cutoff, generated_at=generated_at, card_policy=policy, capture_manifest=manifest)
            # Discovery/status are shared across fixtures, never hidden in per-match counts.
            report['execution_request_count'] = client.used if client else 0
            report['fixture_universe_source'] = source_evidence
            report['fixture_universe_exclusions'] = source_exclusions
            from hashlib import sha256
            report['analysis_id'] = sha256(dumps({k: v for k, v in report.items() if k != 'analysis_id'}).encode()).hexdigest()
            directory = write(report, args.output)
            print(dumps(dict(status='REPORT_CREATED', provider=args.provider,
                match_id=fixture['provider_fixture_id'], json=str(directory/'report.json'),
                html=str(directory/'report.html'), decision='NO_BET', oos_eligible=False)))
            if args.open:
                webbrowser.open((directory/'report.html').resolve().as_uri())
        print(dumps(dict(execution_request_count=client.used if client else 0,
                         quota_after=client.quota if client else None)))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AcquisitionError) as error:
        # Transport errors contain only fixed safe codes. Do not print arbitrary source bodies.
        allowed = {'live_and_dry_run_are_exclusive', 'explicit_positive_request_budget_required',
            'coverage_audit_is_offline_only',
            'structured_replay_directory_requires_flashscore', 'fixture_discovery_pagination_incomplete',
            'explicit_selection_required_for_automation', 'selection_exceeds_match_limit',
            'selection_required', 'exact_match_id_not_in_filtered_universe', 'invalid_selection',
            'PROVIDER_ID_UNRESOLVED', 'provider_mapping_requires_stable_identity_resolution',
            'ambiguous_fixture_identity', 'legacy_fixture_identity_conflict', 'cutoff_after_target_date',
            'cutoff_must_precede_kickoff', 'credential_in_evidence_forbidden',
            'feature_cutoff_cannot_follow_generation', 'capture_fixture_identity_conflict',
            'fixed_report_time_only_allowed_for_offline_replay',
            'outside_isolated_selected_analysis_root', 'positive_match_limit_required'}
        known = str(error) if isinstance(error, AcquisitionError) or str(error) in allowed else 'invalid_configuration_or_evidence'
        print(dumps(dict(status='BLOCKED', reason=known, request_count=client.used if client else 0)))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
