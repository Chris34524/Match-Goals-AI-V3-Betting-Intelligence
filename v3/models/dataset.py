"""Read-only canonical Phase 1 label reuse and accredited Phase 2 extraction.

No repair of missing kickoff, no score-based features, no current odds inputs.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from v3.data.builder import unique_object, reject_constant
from v3.data.validation import timestamp, label_values
from v3.data.temporal import sample_reasons
from v3.features.catalog import get_catalog, CATALOG_VERSION
from v3.features.surface_catalog import SURFACE_CATALOG
from v3.features import engine, temporal_context, h2h
from v3.features.history_adapter import read_history
from .contract import MARKETS, digest
from .preprocess import valid

LABEL_KEYS = dict(BTTS='label_btts', OVER_1_5='label_over_1_5',
                  OVER_2_5='label_over_2_5', OVER_3_5='label_over_3_5', **{'1X2':'label_1x2'})
EXTRACTORS = (engine, temporal_context, h2h)


@lru_cache(maxsize=5)
def feature_specs(market):
    catalog_market = '1X2_EXPERIMENTAL' if market == '1X2' else market
    accredited = {s.name if hasattr(s,'name') else s for module in EXTRACTORS for s in module.SPECS}
    surface = {s.name:s for s in SURFACE_CATALOG}
    return tuple(s for s in get_catalog(market=catalog_market,status='available')
                 if s.name in accredited and surface[s.name].status == 'available')


def load_json(path):
    if path.is_symlink():
        raise ValueError('symlink_source')
    return json.loads(path.read_text(), object_pairs_hook=unique_object, parse_constant=reject_constant)


def labels_valid(labels):
    if not isinstance(labels,dict):
        return False
    h,a = labels.get('home_goals'),labels.get('away_goals')
    return (type(h) is int and type(a) is int and h >= 0 and a >= 0 and
            all(type(labels.get(k)) is type(v) and labels[k] == v for k,v in label_values(h,a).items()))


def check_features(features, names):
    allowed = {s.name for m in MARKETS for s in feature_specs(m)}
    if not set(features) <= allowed:
        raise ValueError('unexpected_or_blocked_feature')
    if set(features) != set(names):
        raise ValueError('missing_or_unexpected_feature')
    if not all(valid(v) for v in features.values()):
        raise ValueError('invalid_feature_values')
    specs = {s.name:s for m in MARKETS for s in feature_specs(m)}
    for name,value in features.items():
        if value is None:
            continue
        spec = specs[name]
        if value < 0 or (spec.dtype == 'int' and type(value) is not int):
            raise ValueError('invalid_feature_values')
        if '_rate_' in name and value > 1:
            raise ValueError('invalid_feature_values')


def model_matrix(canonical_rows, materialized, market):
    names = [s.name for s in feature_specs(market)]
    counts = Counter(total_targets=len(canonical_rows), labeled_targets=0, eligible_model_rows=0)
    exclusions = Counter()
    ids = [r['metadata']['match_id'] for r in canonical_rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate_target_id_or_ambiguous_join')
    if set(materialized)-set(ids):
        raise ValueError('missing_target_or_ambiguous_join')
    rows = []
    for source in canonical_rows:
        meta = source['metadata']
        tid = meta['match_id']
        reasons = []
        labels = source.get('labels')
        labeled = labels_valid(labels)
        counts['labeled_targets'] += labeled
        if not labeled:
            reasons.append('missing_target' if labels is None else 'conflicting_or_invalid_labels')
        kickoff = timestamp(meta.get('kickoff'))
        if kickoff is None:
            reasons.append('missing_kickoff')
        elif kickoff.date().isoformat() != meta.get('date'):
            reasons.append('kickoff_date_conflict')
        audit = source['audit']
        if audit.get('eligible') is not True or audit.get('temporal_status') != 'OK':
            reasons.append('canonical_temporal_ineligible')
        if audit.get('feature_cutoff') != meta.get('kickoff'):
            reasons.append('cutoff_conflict')
        artifact = materialized.get(tid)
        if artifact is None:
            reasons.append('missing_feature_artifact')
        else:
            features = artifact['features']
            allowed = {s.name for m in MARKETS for s in feature_specs(m)}
            if not set(features) <= allowed:
                raise ValueError('unexpected_or_blocked_feature')
            check_features({n:features[n] for n in names if n in features}, names)
            if artifact['metadata'] != dict(date=meta['date'], home=meta['home_team'], away=meta['away_team']):
                reasons.append('feature_identity_conflict')
            for sample in artifact['contributing']:
                if sample_reasons(tid,meta['date'],sample['match_id'],sample['date']):
                    reasons.append('feature_timestamp_not_pre_target')
            if not any(v is not None for n,v in features.items() if n in names):
                reasons.append('no_feature_evidence')
        if reasons:
            exclusions.update(set(reasons))
            continue
        label = labels[LABEL_KEYS[market]]
        if market == '1X2':
            label = {'1':0,'X':1,'2':2}[label]
        rows.append(dict(target_id=tid,kickoff_at=meta['kickoff'], market=market,
                         event=dict(home=meta['home_team'],away=meta['away_team']),
                         cutoff=meta['kickoff'], features={n:features[n] for n in names}, label=int(label),
                         feature_version=artifact['feature_versions'],label_version='phase1-regulation-3.0.0',
                         provenance=dict(canonical=audit['provenance'],features=artifact['provenance'])))
    rows.sort(key=lambda r:(timestamp(r['kickoff_at']),r['target_id']))
    counts['eligible_model_rows'] = len(rows)
    counts['excluded_rows'] = len(canonical_rows)-len(rows)
    return rows,dict(counts= dict(counts),exclusion_reasons=dict(sorted(exclusions.items())),
                     feature_names=names,feature_count=len(names),feature_catalog_version=CATALOG_VERSION,
                     feature_hash=digest(names),dataset_hash=digest(rows))


def audit_dataset(root=Path('.')):
    root = Path(root)
    path = root/'data/derived/dataset_v3.jsonl'
    raw = path.read_bytes()
    manifest_path = root/'data/derived/dataset_v3_manifest.json'
    manifest = load_json(manifest_path)
    if hashlib.sha256(raw).hexdigest() != manifest['jsonl_sha256']:
        raise ValueError('phase1_dataset_digest_mismatch')
    canonical_rows = [json.loads(line, object_pairs_hook=unique_object,parse_constant=reject_constant) for line in raw.splitlines()]
    if len(canonical_rows) != manifest['rows_emitted']:
        raise ValueError('phase1_dataset_count_mismatch')
    materialized = {}
    source_hashes = {str(path.relative_to(root)):hashlib.sha256(raw).hexdigest(),
                     str(manifest_path.relative_to(root)):hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    all_names = {s.name for m in MARKETS for s in feature_specs(m)}
    # Reuse approved Phase 2 pure materializers; output stays in memory.
    for source in canonical_rows:
        tid = source['metadata']['match_id']
        if not isinstance(tid,str) or not tid or Path(tid).name != tid:
            raise ValueError('invalid_target_id')
        folder = root/'data/matches'/tid
        history, history_raw, error = read_history(folder)
        blocks = [module.materialize(history,tid,error) for module in EXTRACTORS]
        features = {}
        contributing = []
        for block in blocks:
            for n,value in block['features'].items():
                if n in features:
                    raise ValueError('ambiguous_feature_join')
                if n in all_names:
                    features[n] = value['value']
            contributing.extend(s for w in block['windows'].values() for s in w['contributing'])
        src = f'data/matches/{tid}/history.json'
        source_hashes[src] = hashlib.sha256(history_raw).hexdigest() if history_raw is not None else None
        materialized[tid] = dict(features=features,metadata=blocks[0]['metadata'],
                                contributing=contributing,feature_versions=[b['feature_version'] for b in blocks],
                                provenance=dict(artifact=src,sha256=source_hashes[src],contributing=contributing))
    matrices,audits = {},{}
    for market in MARKETS:
        matrices[market],audits[market] = model_matrix(canonical_rows,materialized,market)
    return matrices,dict(markets=audits,source_artifact_hashes=source_hashes,
                         source_hash=digest(source_hashes),canonical_rows=len(canonical_rows),
                         label_contract='v3.data.validation.label_values; no labels reconstructed',
                         kickoff_count=sum(timestamp(r['metadata'].get('kickoff')) is not None for r in canonical_rows))
