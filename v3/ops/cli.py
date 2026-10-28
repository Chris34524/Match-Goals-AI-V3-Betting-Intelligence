"""One bounded tick only. prepare/capture/cycle need --live for provider access."""
import argparse
import json
from . import prospective, paper_cycle
from .report import report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('forecast','picks','status','prepare','capture','paper','settle','report','cycle'))
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--source')
    args=parser.parse_args(argv)
    try:
        if args.command in ('forecast','picks'):
            from .forecast import generate
            result=generate(args.source)
            result={k:v for k,v in result.items() if k != 'matches'}
        elif args.command=='prepare':
            result=prospective.prepare(live=args.live)
        elif args.command=='capture':
            result=prospective.capture(live=args.live)
        elif args.command=='paper':
            result=paper_cycle.paper()
        elif args.command=='settle':
            result=paper_cycle.settle()
        elif args.command=='cycle':
            # Validation is offline; no request occurs when prerequisites fail.
            from .validation import validate_and_receipt
            if not validate_and_receipt():
                result=dict(real_status='BLOCKED_VALIDATION_REQUIRED')
            else:
                prospective.prepare(live=args.live)
                prospective.capture(live=args.live)
                paper_cycle.paper();paper_cycle.settle()
                result=report(persist=True)
        else:
            result=report(persist=args.command=='report')
        from .runtime import ensure_safe
        ensure_safe(result)
        print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except Exception:
        # Untrusted input and transport exceptions must never reach tracebacks.
        print('{"real_status":"BLOCKED","reason_codes":["invalid_input_or_runtime_integrity"]}')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
