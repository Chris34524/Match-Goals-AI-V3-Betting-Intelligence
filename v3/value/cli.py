"""Offline JSON/JSONL interface; no operational integration."""
import argparse
import json
from pathlib import Path
from .contract import serialize
from .engine import evaluate
from .selector import select
from .policy import Policy, default_policy
from .report import sensitivity


def load(path, jsonl=False):
    text = Path(path).read_text(encoding='utf-8')
    def reject(value):
        raise ValueError('nonfinite_json_input:' + value)
    return ([json.loads(line, parse_constant=reject) for line in text.splitlines() if line.strip()]
            if jsonl else json.loads(text, parse_constant=reject))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['evaluate', 'sensitivity'])
    parser.add_argument('--input', required=True, help='JSON list or JSONL of {model, observations} or 4.1 candidates')
    parser.add_argument('--policy', help='Single policy for evaluate; predefined policy list for sensitivity')
    parser.add_argument('--input-jsonl', action='store_true')
    parser.add_argument('--jsonl', action='store_true', help='One selection/report per line')
    parser.add_argument('--synthetic-test-only', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        inputs = load(args.input, args.input_jsonl)
        if not isinstance(inputs, list):
            raise ValueError('input_must_be_list')
        candidates = [evaluate(c['model'], c['observations'], allow_synthetic=args.synthetic_test_only)
                      if isinstance(c, dict) and set(c)=={'model','observations'} else c for c in inputs]
        config = load(args.policy) if args.policy else None
        if args.command == 'evaluate':
            policy = Policy.from_dict(config) if config is not None else default_policy()
            result = [select(c, policy, allow_synthetic=args.synthetic_test_only) for c in candidates]
        else:
            policies = [Policy.from_dict(p) for p in config] if config is not None else [default_policy()]
            result = sensitivity(candidates, policies, allow_synthetic=args.synthetic_test_only)
        if args.jsonl:
            rows = result if isinstance(result, list) else [result]
            output = ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n' for r in rows)
        else:
            output = serialize(result)
        if args.output:
            Path(args.output).write_text(output, encoding='utf-8')
        else:
            print(output, end='')
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
