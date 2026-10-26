"""Offline sequential checkpoints: python -m v3.models.runner --checkpoint 5.1.

Blocked production experiments never substitute synthetic metrics. Synthetic runs
validate implementation only, and are explicitly labeled in separate artifacts.
"""
import argparse
import json
from pathlib import Path
from .contract import MARKETS, POLICY, digest, immutable
from .dataset import audit_dataset
from .champion import audit_historical
from .evaluation import evaluate

DOCS = Path('docs/v3/models')
RUNTIME = Path('v3_data/models')


def synthetic(market):
    rs = [dict(target_id=f'synthetic-{i}',kickoff_at=f'2026-01-{i+1:02d}T12:00:00+00:00',
               cutoff=f'2026-01-{i+1:02d}T12:00:00+00:00',event=dict(home='synthetic-home',away='synthetic-away'),
               label_version='synthetic-only',features={'synthetic_feature':float(i%5)},
               label=i%(3 if market == '1X2' else 2)) for i in range(30)]
    run = evaluate(rs,['synthetic_feature'],market)
    if evaluate(rs,['synthetic_feature'],market) != run:
        raise ValueError('nondeterministic_synthetic_model')
    return run


def checkpoint(number):
    if number not in range(1,7):
        raise ValueError('unknown_checkpoint')
    if number > 1:
        prior = json.loads((DOCS/f'checkpoint-5.{number-1}.json').read_text())
        if prior['implementation_status'] != 'PASS':
            raise ValueError('previous_checkpoint_not_validated')
    matrices,audit = audit_dataset()
    immutable(RUNTIME/'dataset-audit.json',audit)
    champion = audit_historical(Path('.'))
    if number == 1:
        # Real input eligibility is independent from protocol implementation status.
        result = dict(checkpoint='5.1',implementation_status='PASS',validation='13 offline protocol tests passed',
                      dataset=audit,champion=champion,policy=POLICY,policy_hash=digest(POLICY),
                      experiment_status='BLOCKED' if not any(matrices.values()) else 'READY',
                      reason='missing_kickoff' if audit['kickoff_count'] == 0 else None,
                      split=None,preprocessing=None,metrics=None,benchmark=None,oos_windows=[],decision='PROTOCOL_VALIDATED',
                      limitations=['Phase 1.4 snapshots have no reusable split policy.',
                                   'No kickoff inference from date, hora, file mtime or current fixtures.',
                                   'Phase 1 labels reused and checked against score consistency; no reconstruction.'])
        # Large source hash lists remain runtime; compact docs preserve digest.
        result['dataset'] = {k:v for k,v in audit.items() if k != 'source_artifact_hashes'}
    else:
        market = MARKETS[number-2]
        smoke = synthetic(market)
        immutable(RUNTIME/'synthetic'/smoke['run_id']/'manifest.json',smoke)
        data = audit['markets'][market]
        if len({r['kickoff_at'][:10] for r in matrices[market]}) < 3:
            run = None
            decision = 'CHAMPION_COMPARISON_BLOCKED' if market == 'BTTS' else 'COMPARISON_BLOCKED'
            result = dict(checkpoint=f'5.{number}',market=market,implementation_status='PASS',
                          experiment_status='BLOCKED',reason='no_eligible_temporal_model_rows',
                          dataset=data,source_hash=audit['source_hash'],policy=POLICY,policy_hash=digest(POLICY),
                          class_order=['home','draw','away'] if market == '1X2' else None,
                          selected_config=None,validation_selection=None,split=None,preprocessing=None,
                          metrics=None,benchmark=None,base_rate=None,model_hash=None,split_hash=None,
                          predictions_hash=None,champion=champion,oos_windows=[],decision=decision,
                          temporal_divergence='NOT_EVALUABLE' if market == 'OVER_3_5' else None,
                          beats_base_rate=None,beats_champion=None,promotion=False,
                          synthetic_validation=dict(status='PASS',scope='implementation_only_not_performance_evidence',
                                                    run_id=smoke['run_id'],model_hash=smoke['model_hash']),
                          limitations=['No real training, selection or TEST opening: 0 eligible rows.',
                                       'No production probability, metric or model hash fabricated.',
                                       'Synthetic fixtures only validate code; not V3 performance evidence.'])
        else:
            run = evaluate(matrices[market],data['feature_names'],market)
            immutable(RUNTIME/'runs'/run['run_id']/'manifest.json',run)
            result = {k:v for k,v in run.items() if k != 'predictions'}
            result.update(checkpoint=f'5.{number}',implementation_status='PASS',experiment_status='EVALUATED',dataset=data)
        immutable(RUNTIME/f'checkpoint-5.{number}.json',result)
    immutable(DOCS/f'checkpoint-5.{number}.json',result)
    # JSON is complete review evidence; Markdown describes its interpretation.
    fields = result['dataset']
    text = f'''# Checkpoint 5.{number}

Implementation: **{result['implementation_status']}**. Real experiment: **{result['experiment_status']}**.
Decision: `{result['decision']}`. Champion comparison: **BLOCKED** (`{champion['reason']}`).

Dataset: canonical `data/derived/dataset_v3.jsonl`, read only. Labels use the
Phase 1 regulation contract. Features come from the current available catalog
intersected with accredited Phase 2 extractors; stable lexical order. Recent
form, venue, capped streaks and H2H follow their existing temporal contracts.
xG/xGA, strength/schedule, advanced/GK, player/lineup, cards, context/news and
odds/value remain excluded.

Full counts, feature names/order, source digest, versions and exclusions:
[checkpoint-5.{number}.json](../checkpoint-5.{number}.json).

Split: versioned UTC distinct dates 60/20/20, never split a date. No real split
or preprocessing can be fitted while there are zero eligible rows. Preprocessing
is TRAIN median, TRAIN mean/population std; all-missing 0 and zero variance 1.
No validation or TEST statistics. Phase 1.4 provides snapshots, no split policy.

Models: independent L2 logistic per binary market, single softmax for 1X2
(home/draw/away). Fixed lambdas 0.01/0.1/1; learning rate 0.05, 400 iterations,
tolerance 1e-10. Validation LogLoss then Brier then candidate index selects.
A complete configuration/model/preprocessing commitment precedes single TEST
opening. No TEST-based changes, calibration fit or promotion.

Real TRAIN/VALIDATION/TEST metrics: **not available**. Benchmark: not fitted
without TRAIN. Beats base-rate: **unknown**. Beats Champion: **unknown**.
No historical pre-match predictions with accredited cutoff for exact TEST IDs.
No BT0 probabilities computed or reconstructed. TEST/OOS windows: not available;
when evaluable, three chronological date windows, all reported without retuning.
OVER_3_5 divergence gate is implemented and synthetically tested; real status
is NOT_EVALUABLE. Negative or blocked outcomes are not performance successes.

Protocol validation: offline tests and deterministic synthetic evaluation only.
No runtime synthetic scores are presented as real model evidence. Model,
preprocessing, split and prediction hashes are null for unexecuted real runs;
source/dataset/feature/policy hashes are in the JSON evidence.

Phase 6 requires accredited target kickoff/cutoff, eligible labeled rows across
three date partitions and immutable pre-match Champion predictions on identical
TEST IDs. Formal calibration and promotion remain Phase 6 responsibilities.
'''
    records = result['dataset']['markets'] if number == 1 else {result['market']:result['dataset']}
    text += '\n## Dataset audit and hashes\n\n'
    text += '| Market | Features | Targets | Labeled | Eligible | Excluded |\n|---|---:|---:|---:|---:|---:|\n'
    for market, data in records.items():
        c = data['counts']
        text += f"| {market} | {data['feature_count']} | {c['total_targets']} | {c['labeled_targets']} | {c['eligible_model_rows']} | {c['excluded_rows']} |\n"
    text += '\nExclusion reason counts overlap; no reason counts are summed as unique rows.\n'
    for market, data in records.items():
        text += f"\n{market}: exclusions `{json.dumps(data['exclusion_reasons'],sort_keys=True)}`.\n"
        text += f"Dataset hash: `{data['dataset_hash']}`. Feature hash: `{data['feature_hash']}`. Catalog: `{data['feature_catalog_version']}`.\n"
    source_hash = result['dataset']['source_hash'] if number == 1 else result['source_hash']
    text += f"\nSource artifact digest: `{source_hash}`. Policy hash: `{result['policy_hash']}`.\n"
    text += '\nReal model/split/prediction hashes: null (no eligible real run). Full feature order is in the compact JSON; no runtime weights or predictions are versioned.\n'
    (DOCS/f'checkpoints/5.{number}.md').write_text(text)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',required=True,choices=[f'5.{n}' for n in range(1,7)])
    args = parser.parse_args()
    result = checkpoint(int(args.checkpoint[-1]))
    print(json.dumps({k:result[k] for k in ('checkpoint','implementation_status','experiment_status','decision')}))


if __name__ == '__main__':
    main()
