"""Read small structured JSON replay envelopes; never visits URLs."""
import json
from pathlib import Path

from .contract import Fixture, Request, dumps
from .parser import StructuredParser


def replay_document(document):
    if document.get('schema_version') != 'fs-replay-batch-1':
        raise ValueError('unsupported replay batch')
    parser, result = StructuredParser(), []
    for item in document['items']:
        request = dict(item['request'])
        request['fixture'] = Fixture(**request['fixture'])
        result.append(parser.parse(Request(**request), item['sample']))
    return sorted(result, key=lambda c: (c.request.key, c.evidence.observed_at, dumps(c.to_dict())))


def read_replay(path):
    return replay_document(json.loads(Path(path).read_text(encoding='utf-8')))


def jsonl(observations):
    return ''.join(dumps(c.to_dict()) + '\n' for c in sorted(observations,
        key=lambda c: (c.request.key, c.evidence.observed_at, dumps(c.to_dict()))))
