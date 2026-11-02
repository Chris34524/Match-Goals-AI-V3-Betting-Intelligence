"""Provider-neutral selected fixture capture. Default execution is plan-only."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import sys
from v3.flashscore.contract import dumps
from .selection import load_source, select, provider_id, resolve
from .full_capture import capture, plan, matrix, flashscore_live_state
from .api_football.client import Client, AcquisitionError
from .storage import atomic_json, checked_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('select', 'full-capture', 'resolve'):
        p = sub.add_parser(command)
        p.add_argument('--provider', required=True, choices=('api_football', 'flashscore'))
        p.add_argument('--source', type=Path)
        p.add_argument('--match-id', action='append', default=[])
        p.add_argument('--indices')
        p.add_argument('--live', action='store_true')
        p.add_argument('--max-requests', type=int)
        p.add_argument('--replay-dir', type=Path)
        p.add_argument('--output', type=Path, default=Path('v3_data/providers'))
        p.add_argument('--build-capabilities', action='store_true')
        p.add_argument('--coverage-audit', action='store_true')
        p.add_argument('--settle-targets', action='store_true')
        p.add_argument('--candidates', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.live and args.provider == 'flashscore':
            # No Flashscore network implementation exists; a flag cannot supply a grant.
            print(dumps(dict(status=flashscore_live_state(), request_count=0)))
            return 2
        if args.live and (args.max_requests is None or args.max_requests < 1):
            raise ValueError('explicit_positive_request_budget_required')
        rows = load_source(args.source, args.provider) if args.source else []
        credential = os.environ.get('API_FOOTBALL_KEY')
        if credential and credential in dumps(dict(rows=rows, match_ids=args.match_id)):
            raise ValueError('credential_in_selection_forbidden')
        if args.command == 'resolve':
            if args.provider != 'api_football' or not args.source:
                raise ValueError('resolver_requires_api_football_context')
            candidates = load_source(args.candidates, args.provider) if args.candidates else []
            if args.live:
                client = Client(live=True, max_requests=args.max_requests, retries=0)
                for row in rows:
                    ctx = row.get('resolution_context', {}).get(args.provider, {})
                    if all(ctx.get(k) for k in ('date', 'competition_id', 'season', 'home_id', 'away_id')):
                        payload, _ = client.get('/fixtures', dict(date=ctx['date'], league=int(ctx['competition_id']), season=int(ctx['season'])))
                        candidates.extend(payload['response'])
            print(dumps([resolve(r, candidates) for r in rows]))
            return 0
        if rows:
            print('index time competition home away provider_id capture_status')
            for i, r in enumerate(rows, 1):
                r.setdefault('source_fixture_reference', str(args.source)+'#'+str(i))
                print(i, r.get('kickoff', r.get('fixture', {}).get('date', '?')), r.get('competition', r.get('league', {}).get('name', r.get('league', {}).get('id', '?'))),
                      r.get('home', r.get('teams', {}).get('home', '?')), r.get('away', r.get('teams', {}).get('away', '?')),
                      provider_id(r, args.provider) or '?', r.get('capture_status', 'PLANNED') if provider_id(r, args.provider) else 'PROVIDER_ID_UNRESOLVED')
            expression = args.indices
            if expression is None and not args.match_id:
                if not sys.stdin.isatty():
                    raise ValueError('explicit_indices_required_for_automation')
                expression = input('Select (1 / 1,3,7 / 1-5 / all): ')
            rows = select(rows, expression) if expression else []
        rows.extend(dict(provider=args.provider, provider_fixture_id=mid) for mid in args.match_id)
        if not rows:
            raise ValueError('selection_required')
        preview = plan(rows, args.provider, args.max_requests)
        print(dumps(preview), flush=True)
        client = None
        if args.live or args.replay_dir:
            checked_path(args.output / args.provider / 'matches' / 'plan.json')
        if args.live:
            try:
                client = Client(live=True, max_requests=args.max_requests, retries=0)
                # Discovery is part of the displayed shared budget; never silently unbounded.
                if args.max_requests > 3:
                    client.get('/status')
            except AcquisitionError as error:
                print(dumps(dict(status='BLOCKED', reason=str(error), request_count=client.used if client else 0)))
                return 2
        for row in rows:
            manifest, observations = capture(row, args.provider, client=client, replay_dir=args.replay_dir,
                root=args.output if args.live or args.replay_dir else None)
            print(dumps({k: v for k, v in manifest.items() if k != 'surfaces'}))
            print(matrix(observations, manifest))
            if observations and (args.coverage_audit or args.settle_targets):
                fixture = observations[0].request.fixture
                directory = args.output / args.provider / 'matches' / fixture.match_id
                if args.coverage_audit:
                    from v3.flashscore.audit import audit
                    fields = sorted({(c.request.surface, c.request.period, c.request.capability_name) for c in observations if c.request.level == 'team'})
                    frame = dict(schema_version='fs-audit-manifest-1', manifest_id='selected-'+fixture.match_id,
                        declared_at=min(c.evidence.observed_at for c in observations), fixtures=[asdict(fixture)],
                        fields=[dict(surface=s, period=p, canonical_stat=f) for s,p,f in fields])
                    atomic_json(directory / 'coverage.json', audit(frame, observations))
                if args.settle_targets:
                    from v3.flashscore.targets import TargetEngine
                    atomic_json(directory / 'targets.json', TargetEngine(observations).settle(fixture))
        print(dumps(dict(execution_request_count=client.used if client else 0, quota_after=client.quota if client else {})))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AcquisitionError):
        print(dumps(dict(status='BLOCKED_INVALID_CONFIGURATION_OR_REQUEST')))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
