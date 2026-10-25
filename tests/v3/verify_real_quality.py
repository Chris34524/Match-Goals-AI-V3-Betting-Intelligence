"""Optional read-only real-data isolation audit. Run from the repository root.

PYTHONPATH=. python tests/v3/verify_real_quality.py
No generated files or historical artifacts are written.
"""
import copy
import json
from pathlib import Path
from v3.data import builder
from v3.data.quality import quality_report

def main():
    report = quality_report('data/derived/dataset_v3.jsonl')
    assert report['manifest']['present'] and not report['manifest']['mismatches']
    assert not report['duplicate_match_ids']
    assert not report['structural_inconsistencies']
    root = Path('data/matches')
    pool, _, error = builder.read_pool(Path('data/backtest_pool.json'))
    assert error is None
    original = [json.loads(line) for line in Path('data/derived/dataset_v3.jsonl').read_text().splitlines()]
    original = {r['metadata']['match_id']: r for r in original}
    summary = dict(rows=0, labeled_rows=0, pool_input_or_metadata_changes=0,
                   label_mutation_input_or_metadata_changes=0,
                   prediction_removal_input_or_metadata_changes=0,
                   prematch_status_changes_from_pool=0,
                   original_input_or_metadata_changes=0)
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        entries = pool.get(folder.name, ())
        with_pool = builder.normalize(folder, entries)[0]
        without_pool = builder.normalize(folder)[0]
        mutated = copy.deepcopy(entries)
        for entry in mutated:
            entry.update(goles_local=100, goles_visitante=99)
        changed_labels = builder.normalize(folder, mutated)[0] if entries else without_pool
        adapted = builder.ADAPTED
        try:
            builder.ADAPTED = adapted - {'champion_snapshot.json', 'lambda_comparison.json'}
            without_predictions = builder.normalize(folder, entries)[0]
        finally:
            builder.ADAPTED = adapted
        def changed(a, b):
            return any(a[k] != b[k] for k in ('inputs', 'metadata'))
        summary['rows'] += 1
        summary['labeled_rows'] += bool(entries)
        summary['pool_input_or_metadata_changes'] += changed(with_pool, without_pool)
        summary['label_mutation_input_or_metadata_changes'] += changed(with_pool, changed_labels)
        summary['prediction_removal_input_or_metadata_changes'] += changed(with_pool, without_predictions)
        summary['original_input_or_metadata_changes'] += changed(with_pool, original[folder.name])
        summary['prematch_status_changes_from_pool'] += any(with_pool['audit'][k] != without_pool['audit'][k] for k in ('eligible', 'temporal_status', 'reasons'))
    assert summary['rows'] == len(original)
    assert summary['labeled_rows'] == sum(r['labels'] is not None for r in original.values())
    assert not any(v for k,v in summary.items() if k not in ('rows', 'labeled_rows'))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
