"""Explicit FS-4/FS-5 joins with evidence replay and rejection diagnostics."""
from collections import Counter, defaultdict
from datetime import date, timezone
import math

from ..contract import Capability, Evidence, Fixture, Request, timestamp
from ..feature_catalog import VERSION as FEATURE_VERSION
from ..feature_materializer import FeatureMaterializer
from ..market_contract import CardSettlementPolicy, MarketSpec, VERSION as TARGET_VERSION
from ..observation_index import digest
from ..targets import TargetEngine

FEATURE_SETS = {
    family + '-core-v1': tuple((side, name + '_L5', 'overall')
        for side in ('home', 'away') for name in names)
    for family, names in {
        'goals': ('goals_for', 'goals_against'),
        'corners': ('corners_for', 'corners_against'),
        'cards': ('cards_for', 'cards_against'),
        'shots': ('shots_for', 'shots_against'),
    }.items()
}
BASE_POLICY = dict(base='research-regulation-settlement-v1', cancelled='VOID',
    abandoned='UNSETTLED', cards=None, player=None, second_half_derivation=None)


def capability(p):
    r, e = dict(p['request']), dict(p['evidence'])
    r['fixture'] = Fixture(**r['fixture'])
    if e['inspected_fixture']:
        e['inspected_fixture'] = Fixture(**e['inspected_fixture'])
    e['operand_references'] = tuple(e['operand_references'])
    c = Capability(Request(**r), Evidence(**e))
    if digest(c.to_dict()) != p['observation_sha256'] or list(c.request.key) != p['capability_key']:
        raise ValueError('provenance_hash_mismatch')
    return c


def policy_cards(policy):
    if set(policy) != set(BASE_POLICY) or any(policy[k] != BASE_POLICY[k]
            for k in BASE_POLICY if k != 'cards'):
        raise ValueError('unsupported_settlement_policy')
    return CardSettlementPolicy(**policy['cards']) if policy['cards'] else None


def validate_features(fixture, features, feature_set, policy):
    """Return ordered records, reasons. Recompute selected FS-4 values from hashes."""
    selected, reasons = [], set()
    try:
        cards = policy_cards(policy)
        expected = FEATURE_SETS[feature_set]
    except (ValueError, KeyError, TypeError):
        return [], ['TARGET_POLICY_MISMATCH']
    candidates = [f for f in features if f.get('target_match_id') == fixture.match_id]
    by_id = defaultdict(set)
    for f in candidates:
        by_id[f.get('feature_id')].add(digest(f))
    if any(len(v) > 1 for v in by_id.values()):
        reasons.add('DUPLICATE_CONFLICT')
    for side, name, scope in expected:
        matches = {digest(f): f for f in candidates if
            (f.get('side'), f.get('feature_name'), f.get('scope')) == (side, name, scope)}
        if not matches:
            reasons.add('FEATURE_MISSING')
            continue
        if len(matches) != 1:
            reasons.add('DUPLICATE_CONFLICT')
            continue
        f = next(iter(matches.values()))
        selected.append(f)
        if f.get('schema_version') != FEATURE_VERSION or f.get('materializer_version') != FEATURE_VERSION:
            reasons.add('FEATURE_SCHEMA_MISMATCH')
        if f.get('target_identity') != list(fixture.identity):
            reasons.add('FEATURE_SCHEMA_MISMATCH')
        if f.get('status') != 'AVAILABLE':
            reasons.add({'TEMPORAL_INELIGIBLE': 'FEATURE_TEMPORAL_INELIGIBLE',
                'MISSING_OPERAND': 'FEATURE_MISSING', 'UNASSESSED': 'UNASSESSED'}.get(
                    f.get('status'), 'INSUFFICIENT_FEATURES'))
        if type(f.get('value')) not in (int, float) or not math.isfinite(f['value']):
            reasons.add('INSUFFICIENT_FEATURES')
        try:
            # No accredited intraday kickoff exists: cutoff must be on an earlier UTC day.
            if timestamp(f['cutoff']).astimezone(timezone.utc).date() >= date.fromisoformat(fixture.match_date):
                reasons.add('FEATURE_TEMPORAL_INELIGIBLE')
            if fixture.match_id in f['source_match_ids']:
                reasons.add('TARGET_LEAKAGE')
            observations = [capability(p) for p in f['provenance']]
            if any(c.request.fixture.match_id == fixture.match_id for c in observations):
                reasons.add('TARGET_LEAKAGE')
            if not observations or any(not c.prematch_usable(fixture.match_id, fixture.match_date, f['cutoff']) for c in observations):
                reasons.add('FEATURE_TEMPORAL_INELIGIBLE')
            replay = FeatureMaterializer(observations).materialize(fixture, f['cutoff'],
                names=[name.rsplit('_L', 1)[0]], scopes=[scope], card_policy=cards)
            original = next(x for x in replay if x['feature_id'] == f['feature_id'])
            for field in ('value', 'status', 'source_match_ids', 'source_observation_hashes',
                          'n_required', 'n_available', 'coverage_rate', 'card_policy'):
                if original[field] != f[field]:
                    reasons.add('FEATURE_SCHEMA_MISMATCH')
        except (ValueError, KeyError, TypeError, StopIteration):
            reasons.add('UNASSESSED')
    if len({f.get('cutoff') for f in selected}) != 1:
        reasons.add('FEATURE_TEMPORAL_INELIGIBLE')
    return selected, sorted(reasons)


def build_dataset(features, targets, fixtures, *, feature_set, policy=None):
    """No silent exclusions. Fixtures declare the requested target universe."""
    if feature_set not in FEATURE_SETS:
        raise ValueError('unknown_feature_set')
    policy = dict(BASE_POLICY if policy is None else policy)
    policy_cards(policy)
    fixtures = list(fixtures)
    frame = {}
    for fixture in fixtures:
        key = (fixture.provider, fixture.match_id)
        if key in frame and frame[key] != fixture:
            raise ValueError('conflicting_fixture_identity')
        frame[key] = fixture
    groups = defaultdict(list)
    feature_groups, feature_hashes = defaultdict(list), defaultdict(set)
    for f in features:
        feature_groups[f.get('target_match_id')].append(f)
        feature_hashes[f.get('feature_id')].add(digest(f))
    conflicting_ids = {key for key, values in feature_hashes.items() if len(values) > 1}
    for t in targets:
        groups[t.get('target_key')].append(t)
    accepted, rejected, seen_fixture = [], [], set()
    for key, copies in sorted(groups.items(), key=lambda x: str(x[0])):
        t = min(copies, key=digest)
        reasons = set()
        if len({digest(x) for x in copies}) != 1:
            reasons.add('DUPLICATE_CONFLICT')
        fixture = frame.get((t.get('provider'), t.get('match_id')))
        seen_fixture.add((t.get('provider'), t.get('match_id')))
        if t.get('status') != 'SETTLED':
            reasons.add('TARGET_MISSING' if t.get('status') == 'MISSING_OPERAND' else 'TARGET_UNSETTLED')
        if type(t.get('binary_label')) is not int or t['binary_label'] not in (0, 1):
            reasons.add('UNASSESSED')
        if t.get('schema_version') != TARGET_VERSION or t.get('settlement_policy_version') != policy:
            reasons.add('TARGET_POLICY_MISMATCH')
        if t.get('market_family') != feature_set.split('-core-')[0]:
            reasons.add('FEATURE_SCHEMA_MISMATCH')
        selected, observations = [], []
        if fixture is None or not fixture.match_date:
            reasons.add('UNASSESSED')
        else:
            selected, failures = validate_features(fixture, feature_groups[fixture.match_id], feature_set, policy)
            reasons.update(failures)
            if any(f.get('feature_id') in conflicting_ids for f in selected):
                reasons.add('DUPLICATE_CONFLICT')
            try:
                observations = [capability(p) for p in t['provenance']]
                if not observations or any(c.request.fixture != fixture for c in observations):
                    raise ValueError('target_identity_mismatch')
                spec = MarketSpec(t['market_family'], t['market'], t['period'], t['side'], t['line'])
                replay = TargetEngine(observations).settle(fixture, specs=[spec], card_policy=policy_cards(policy))[0]
                if any(replay[k] != t[k] for k in ('target_key', 'outcome', 'binary_label', 'status', 'observation_hashes', 'entity', 'score_scope')):
                    raise ValueError('target_replay_mismatch')
            except (ValueError, KeyError, TypeError):
                reasons.add('UNASSESSED')
        if reasons:
            rejected.append(dict(target_key=key, match_id=t.get('match_id'), reasons=sorted(reasons)))
            continue
        provenance = [capability(p) for f in selected for p in f['provenance']] + observations
        synthetic = any(c.evidence.evidence_method == 'synthetic' or
            c.evidence.evidence_quality == 'synthetic' or c.request.fixture.provider == 'synthetic' for c in provenance)
        # Accreditation is never inferred from an input flag or a numeric row.
        accepted.append(dict(**{k:t[k] for k in ('match_id','provider','target_key','market_family','market',
            'period','side','line','entity','schema_version','settlement_policy_version','outcome','binary_label')},
            competition_id=fixture.competition_id, target_date=fixture.match_date,
            label_available_at=max(timestamp(c.evidence.observed_at) for c in observations).astimezone(timezone.utc).isoformat(),
            feature_set=feature_set, feature_schema_version=FEATURE_VERSION,
            target_schema_version=TARGET_VERSION,
            feature_ids=[f['feature_id'] for f in selected], x=[f['value'] for f in selected],
            feature_coverage=[dict(feature_id=f['feature_id'], n_required=f['n_required'],
                n_available=f['n_available'], coverage_rate=f['coverage_rate']) for f in selected],
            feature_quality='COMPLETE', coverage=min(f['coverage_rate'] for f in selected),
            cutoff=selected[0]['cutoff'], provenance_hashes=sorted({digest(c.to_dict()) for c in provenance}),
            synthetic=synthetic, real_accredited=False, production_evidence=False))
    for identity, fixture in sorted(frame.items()):
        if identity not in seen_fixture:
            rejected.append(dict(target_key=None, match_id=fixture.match_id, reasons=['TARGET_MISSING']))
    accepted.sort(key=lambda r: (r['target_date'], r['provider'], r['match_id'], r['target_key']))
    rejected.sort(key=lambda r: (r['match_id'] or '', r['target_key'] or ''))
    return dict(accepted=accepted, rejected=rejected,
        reason_counts=dict(sorted(Counter(reason for r in rejected for reason in r['reasons']).items())))
