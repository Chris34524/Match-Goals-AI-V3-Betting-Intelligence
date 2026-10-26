"""One prospective scheduler tick or offline report, with explicit targets."""
import argparse
import json
from .provider import Config,load_targets,utc_now
from .quota import Budget,ledger
from .reconciliation import Reconciliation
from .scheduler import ScheduleConfig,schedule,execute,load_history
from .snapshot_report import store_report
from .storage import DEFAULT_ROOT
from .contract import canonical_json
from .the_odds_api import assert_safe_payload


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('plan','fixture-tick','live-tick','report'))
    p.add_argument('--config',required=True)
    p.add_argument('--targets',required=True)
    p.add_argument('--output-dir',default=str(DEFAULT_ROOT))
    p.add_argument('--fixture')
    p.add_argument('--now',help='Fixture/planning clock only')
    p.add_argument('--live',action='store_true')
    args=p.parse_args(argv)
    try:
        with open(args.config) as f: settings=json.load(f)
        with open(args.targets) as f: target_rows=json.load(f)
        assert_safe_payload(settings); assert_safe_payload(target_rows)
        c=Config(**{k:tuple(v) if k in ('sports','regions','bookmakers','markets') else v for k,v in settings['provider'].items()})
        targets=load_targets(target_rows)
        rec=Reconciliation(**settings['reconciliation'])
        policy=ScheduleConfig(**settings.get('schedule',{}))
        budget=Budget(**settings.get('budget',{}))
        if args.command=='report':
            print(store_report(args.output_dir,expected_books=c.bookmakers))
        elif args.command=='plan':
            now=args.now or utc_now()
            # Dry-run has no ledger writes and no network. Existing ledger state is
            # read under lock only if present; actual tick rechecks budget anyway.
            from pathlib import Path
            from .storage import safe_root
            root=safe_root(args.output_dir)
            state={'used':0,'remaining':None}
            if (root/'quota/ledger.jsonl').exists():
                with ledger(root,now) as (current,*_): state=dict(current)
            print(canonical_json(schedule(targets,c,now=now,budget=budget,policy=policy,
                  credits_used_local=state['used'],credits_remaining_provider=state['remaining'],
                  history=load_history(root))),end='')
        elif args.command=='fixture-tick':
            if not args.fixture or args.live: raise ValueError('fixture_required')
            with open(args.fixture) as f: payload=json.load(f)
            print(execute(targets,c,rec,root=args.output_dir,budget=budget,policy=policy,
                          fixture_payload=payload,fixture_now=args.now))
        else:
            if args.now or args.fixture: raise ValueError('live_override_forbidden')
            print(execute(targets,c,rec,root=args.output_dir,budget=budget,policy=policy,live=args.live))
        return 0
    except (ValueError,KeyError,TypeError,RuntimeError,OSError):
        print(canonical_json({'status':'blocked','reason':'invalid_input_or_live_guard'}),end='')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
