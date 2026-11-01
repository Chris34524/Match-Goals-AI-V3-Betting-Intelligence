"""Isolated offline replay and coverage commands; no live mode."""
import argparse
import hashlib
import json
from pathlib import Path

from .audit import audit
from .contract import Capability, dumps
from .replay import jsonl, read_replay


def write_artifacts(output_dir, artifacts, inputs=()):
    output = Path(output_dir)
    # Resolve aliases, and reject dangerous output entries before any writes.
    protected = {Path(p).resolve() for p in inputs}
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in artifacts]
    for p in paths:
        if p.resolve() in protected or p.is_symlink() or (p.exists() and (not p.is_file() or p.stat().st_nlink != 1)):
            raise ValueError('unsafe output file or input overwrite')
    for p in paths:
        p.write_text(artifacts[p.name], encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    replay = sub.add_parser('replay')
    replay.add_argument('--input', required=True)
    replay.add_argument('--output', required=True)
    coverage = sub.add_parser('coverage')
    coverage.add_argument('--manifest', required=True)
    coverage.add_argument('--observations', required=True)
    coverage.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'replay':
        content = jsonl(read_replay(args.input))
        metadata = dict(schema_version='fs-replay-output-1',
                        input_sha256=hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                        observations_sha256=hashlib.sha256(content.encode()).hexdigest())
        write_artifacts(args.output, {'observations.jsonl': content, 'replay-manifest.json': dumps(metadata)+'\n'}, [args.input])
    else:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        observations = [Capability.from_dict(json.loads(line)) for line in
                        Path(args.observations).read_text(encoding='utf-8').splitlines() if line.strip()]
        result = audit(manifest, observations)
        write_artifacts(args.output, {'coverage.json': dumps(result)+'\n'}, [args.manifest, args.observations])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
