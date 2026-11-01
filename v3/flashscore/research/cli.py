"""Offline Lane B entrypoint. python -m v3.flashscore.research.cli --help"""
import argparse
import json
from pathlib import Path

from ..contract import Fixture, dumps
from ..observation_index import digest
from .artifacts import ROOT, atomic_json, write_experiment
from .dataset import build_dataset
from .forecast import forecast
from .training import run_experiment


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline RESEARCH / NOT_PRODUCTION; no odds or network')
    commands = parser.add_subparsers(dest='command', required=True)
    demo = commands.add_parser('demo', help='Noisy synthetic demonstration, never real performance')
    demo.add_argument('--n', type=int, default=320)
    demo.add_argument('--output', type=Path, default=ROOT)
    dataset = commands.add_parser('dataset', help='Join FS-4/FS-5 JSON records with fixture universe')
    dataset.add_argument('--input', required=True)
    dataset.add_argument('--output', type=Path, default=ROOT/'datasets'/'dataset.json')
    experiment = commands.add_parser('experiment', help='Explicit synthetic-only chronological experiment')
    experiment.add_argument('--dataset', required=True)
    experiment.add_argument('--synthetic-demo', action='store_true')
    experiment.add_argument('--output', type=Path, default=ROOT)
    command = commands.add_parser('forecast', help='Highest research probabilities are not value picks')
    command.add_argument('--fixture', required=True)
    command.add_argument('--features', required=True)
    command.add_argument('--model')
    command.add_argument('--allow-synthetic', action='store_true')
    command.add_argument('--output', type=Path, default=ROOT/'forecasts'/'research.json')
    args = parser.parse_args(argv)
    if args.command == 'demo':
        from .demo import materialized_cohort
        summary = dict(synthetic=True, real_performance=False, production_evidence=False,
            REAL_EVALUATION='BLOCKED', REAL_MODEL_TRAINING='BLOCKED', network_calls=0, markets={})
        for family, inputs in materialized_cohort(args.n).items():
            ds = inputs['dataset']
            atomic_json(args.output/'datasets'/(family+'-'+digest(ds)+'.json'), ds)
            result = run_experiment(ds['accepted'], synthetic_demo=True)
            if result['status'] == 'BLOCKED':
                summary['markets'][family] = dict(status='BLOCKED', reason=result['reason'], rejection_counts=ds['reason_counts'])
                continue
            write_experiment(result,args.output)
            fixture = inputs['fixtures'][-1]
            forecasts = [forecast(fixture,inputs['features'],m,allow_synthetic=True)
                for m in result['models'] if m['fold_id']==result['folds'][-1]['fold_id']]
            atomic_json(args.output/'forecasts'/(family+'-demo.json'), forecasts)
            summary['markets'][family] = dict(accepted=len(ds['accepted']),rejected=len(ds['rejected']),
                folds=len(result['folds']), models=result['model_statuses'][-4:],
                metrics=result['effectiveness']['by_model'], selection=result['effectiveness']['selection'],
                forecasts=[dict(model_id=r['model_id'],status=r['status'],probability=r['probability']) for r in forecasts])
        atomic_json(args.output/'demo-summary.json',summary)
        print(dumps(summary))
    elif args.command == 'dataset':
        payload = read(args.input)
        result = build_dataset(payload['features'],payload['targets'],
            [Fixture(**f) for f in payload['fixtures']],feature_set=payload['feature_set'],policy=payload.get('policy'))
        atomic_json(args.output,result)
        print(dumps(dict(accepted=len(result['accepted']),rejected=len(result['rejected']),reason_counts=result['reason_counts'])))
    elif args.command == 'experiment':
        result = run_experiment(read(args.dataset)['accepted'],synthetic_demo=args.synthetic_demo)
        if result['status'] != 'BLOCKED':
            write_experiment(result,args.output)
        print(dumps(dict(status=result['status'],reason=result.get('reason'))))
    else:
        result = forecast(Fixture(**read(args.fixture)),read(args.features),read(args.model) if args.model else None,
            allow_synthetic=args.allow_synthetic)
        atomic_json(args.output,result)
        print(dumps(result))


if __name__ == '__main__':
    main()
