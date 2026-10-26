"""Explicit offline/live entry points; no operational scraper integration."""
import argparse
import json
from .collector import plan, collect_fixture, collect_live
from .contract import canonical_json
from .provider import Config, load_targets
from .quota import Budget
from .reconciliation import Reconciliation
from .storage import DEFAULT_ROOT
from .the_odds_api import ProviderError


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('plan', 'collect-fixture', 'collect-live'))
    p.add_argument('--config', required=True, help='Safe JSON configuration; never include credentials')
    p.add_argument('--targets', required=True, help='Explicit target JSON list')
    p.add_argument('--fixture')
    p.add_argument('--output-dir', default=str(DEFAULT_ROOT))
    p.add_argument('--observed-at', help='Offline fixture clock only')
    p.add_argument('--live', action='store_true')
    args = p.parse_args(argv)
    try:
        from .the_odds_api import assert_safe_payload
        with open(args.config) as f:
            settings = json.load(f)
        assert_safe_payload(settings)
        config = Config(**{k: tuple(v) if k in ('sports', 'regions', 'bookmakers', 'markets') else v
                           for k, v in settings['provider'].items()})
        reconciliation = Reconciliation(**settings['reconciliation'])
        budget = Budget(**settings.get('budget', {}))
        with open(args.targets) as f:
            rows = json.load(f)
        assert_safe_payload(rows)
        targets = load_targets(rows)
        if args.command == 'plan':
            print(canonical_json(plan(config, targets, budget)), end='')
        elif args.command == 'collect-fixture':
            if not args.fixture:
                raise ValueError('fixture_required')
            with open(args.fixture) as f:
                payload = json.load(f)
            print(collect_fixture(payload, targets, config, reconciliation, observed_at=args.observed_at, root=args.output_dir))
        else:
            if args.observed_at:
                raise ValueError('live_clock_override_forbidden')
            print(collect_live(targets, config, reconciliation, live=args.live, budget=budget, root=args.output_dir))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ProviderError):
        # Configuration/transport exceptions can embed untrusted values: never echo.
        print(canonical_json({'status': 'blocked', 'reason': 'invalid_input_or_live_guard'}), end='')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
