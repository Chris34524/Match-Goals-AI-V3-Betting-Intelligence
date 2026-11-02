"""Explicit live acquisition only. Default cohort execution is a dry run."""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from v3.flashscore.contract import dumps
from .client import Client, AcquisitionError
from .cohort import collect
from .parser import parse_fixture
from .adapter import Adapter
from .storage import ROOT, atomic_json, checked_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    cohort = commands.add_parser('cohort')
    cohort.add_argument('--manifest', required=True, type=Path)
    cohort.add_argument('--live', action='store_true')
    cohort.add_argument('--max-requests', type=int)
    cohort.add_argument('--output', type=Path, default=ROOT)
    smoke = commands.add_parser('smoke')
    smoke.add_argument('--live', action='store_true')
    smoke.add_argument('--date', default=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat())
    smoke.add_argument('--output', type=Path, default=ROOT / 'raw_metadata' / 'smoke.json')
    metadata = commands.add_parser('metadata', help='Resolve league IDs through one narrow official metadata query')
    metadata.add_argument('--country', required=True)
    metadata.add_argument('--name', required=True)
    metadata.add_argument('--season', type=int, required=True)
    metadata.add_argument('--live', action='store_true')
    metadata.add_argument('--max-requests', type=int)
    metadata.add_argument('--output', type=Path, default=ROOT / 'raw_metadata' / 'leagues.json')
    args = parser.parse_args(argv)
    client = None
    try:
        if args.command == 'metadata':
            if not args.live:
                result = dict(live_status='DRY_RUN', requests_made=0)
            elif not os.environ.get('API_FOOTBALL_KEY'):
                result = dict(live_status='BLOCKED_NO_KEY', requests_made=0)
            elif args.max_requests != 1:
                raise AcquisitionError('metadata_requires_budget_one')
            else:
                checked_path(args.output)
                client = Client(live=True, max_requests=1, retries=0)
                result = dict(live_status='BLOCKED', requests_made=0)
                try:
                    payload, capture = client.get('/leagues', dict(name=args.name, country=args.country, season=args.season))
                    from dataclasses import asdict
                    result.update(live_status='CAPTURED', capture=asdict(capture),
                        competitions=[dict(provider='api_football', competition_id=r['league']['id'],
                            name=r['league']['name'], country=r['country']['name'],
                            seasons=[s['year'] for s in r['seasons']]) for r in payload['response']])
                except (AcquisitionError, ValueError, KeyError, TypeError):
                    result['live_status'] = 'BLOCKED_METADATA_VALIDATION'
                result.update(requests_made=client.used, quota=client.quota)
                atomic_json(args.output, result)
        elif args.command == 'cohort':
            if args.live and args.max_requests is None:
                raise AcquisitionError('explicit_positive_request_budget_required')
            if args.live and not os.environ.get('API_FOOTBALL_KEY'):
                result = dict(live_status='BLOCKED_NO_KEY', requests_made=0)
            else:
                result = collect(json.loads(args.manifest.read_text()), live=args.live,
                                 max_requests=args.max_requests, root=args.output)
        elif not args.live:
            result = dict(live_status='DRY_RUN', requests_made=0)
        elif not os.environ.get('API_FOOTBALL_KEY'):
            result = dict(live_status='BLOCKED_NO_KEY', requests_made=0)
        else:
            checked_path(args.output)
            client = Client(live=True, max_requests=3, retries=0)
            result = dict(live_status='BLOCKED', requests_made=0)
            try:
                payload, fc = client.get('/fixtures', {'date': args.date, 'status': 'FT'})
                finished = sorted(payload['response'], key=lambda row: row['fixture']['id'])
                if not finished:
                    raise AcquisitionError('no_finished_fixture_in_query')
                # Do not rewrite the capture digest of the original multi-fixture response.
                selected = finished[0]
                fixture, metadata = parse_fixture(selected)
                stats, sc = client.get('/fixtures/statistics', {'fixture': int(fixture.match_id)})
                half, hc = client.get('/fixtures/statistics', {'fixture': int(fixture.match_id), 'half': 'true'})
                adapter = Adapter()
                observations = adapter.normalize(payload, half, fc, hc)
                normalized = [c.to_dict() for c in observations]
                from v3.providers.contract import digest
                atomic_json(args.output.parent / 'smoke-normalized.json',
                    dict(origin='real_provider_capture', observations=normalized, provenance=adapter.provenance))
                result.update(live_status='CAPTURED', fixture_id=fixture.match_id,
                    competition_id=fixture.competition_id, season=fixture.season,
                    home_id=fixture.home_id, away_id=fixture.away_id, kickoff_utc=metadata['kickoff_utc'],
                    normalized_sha256=digest(normalized),
                    fields_observed=sorted({c.request.capability_name for c in observations if c.state.value == 'AVAILABLE'}),
                    observed_labels=sorted({s['type'] for r in stats['response'] for s in r['statistics']}),
                    half_status='EXPLICIT_DATA' if any(r.get('statistics_1h') for r in half['response']) else 'NOT_PROVIDED')
            except (AcquisitionError, ValueError, KeyError, TypeError):
                result['live_status'] = 'BLOCKED_SMOKE_VALIDATION'
            result.update(requests_made=client.used, quota=client.quota, captures=client.captures,
                          real_model_training='BLOCKED')
            atomic_json(args.output, result)
        print(dumps(result))
        return 0
    except (AcquisitionError, ValueError, KeyError, TypeError, OSError) as error:
        used = client.used if client else getattr(error, 'requests_made', 0)
        print(dumps(dict(live_status='BLOCKED_INVALID_CONFIGURATION_OR_REQUEST', requests_made=used)))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
