"""Safe stdout metadata CLI; no raw transport diagnostics or persistence."""
import argparse
import json
from .discovery import Discovery
from .the_odds_api import ProviderError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('sports', 'events', 'validate-key'))
    parser.add_argument('--sport', choices=None)
    args = parser.parse_args(argv)
    try:
        if args.command == 'events' and not args.sport:
            raise ProviderError('sport_required')
        client = Discovery((args.sport,) if args.sport else ())
        result = (client.validate_key() if args.command == 'validate-key' else
                  client.events(args.sport) if args.command == 'events' else client.sports_list())
    except ProviderError as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
