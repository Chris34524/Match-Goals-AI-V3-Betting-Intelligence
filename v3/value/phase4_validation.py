"""Offline Phase 4 validation, suite execution and deterministic integrity report.

Writes only Phase 4 documentation artifacts. Every check must pass. Baselines
are never refreshed by this command. Run: python -m v3.value.phase4_validation
"""
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch

from v3.odds.contract import MARKETS, canonical_json
from v3.odds.source_matrix import source_matrix, automatable, matrix_errors
from v3.odds.phase3_validation import fingerprints
from .fixtures import fixture
from .engine import evaluate
from .selector import select, minimum_odds
from .policy import default_policy, Policy, MarketPolicy
from .report import sensitivity

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / 'docs/v3/value'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def tracked_after(before):
    return {p: sha(REPO/p) if (REPO/p).is_file() else None for p in before}


def evaluate_fixture(p=.6, odds=2., market='BTTS'):
    m, r = fixture(market, p, odds)
    return evaluate(m, r, allow_synthetic=True)


def blocked(field, value):
    m, r = fixture()
    r[0]['record'][field] = value
    candidate = evaluate(m, r, allow_synthetic=True)
    return candidate['eligibility'] == 'BLOCKED' and select(candidate, allow_synthetic=True)['decision'] == 'BLOCKED'


def math_checks():
    c = evaluate_fixture()
    checks = {}
    checks['05_fair_odds'] = (c['fair_odds'] == 1/.6 and evaluate_fixture(p=0)['fair_odds'] is None
                              and evaluate_fixture(p=1)['fair_odds'] == 1)
    invalid = []
    for p in (float('nan'), float('inf'), -float('inf')):
        x = evaluate_fixture(p=p)
        invalid.append(x['eligibility'] == 'BLOCKED' and json.loads(canonical_json(x)) == x)
    checks['06_no_nonfinite_json'] = all(invalid) and evaluate_fixture(p=5e-324)['eligibility'] == 'BLOCKED'
    m, r = fixture()
    checks['07_complete_market_required'] = evaluate(m, r[:1], allow_synthetic=True)['exclusion_reason'] == 'market_incomplete'
    from .market import normalize
    checks['08_no_vig_normalized'] = all(math.isclose(math.fsum(normalize([e['record'] for e in fixture(market)[1]])[1].values()),
                                                      1, abs_tol=1e-12, rel_tol=0) for market in MARKETS)
    checks['09_edges'] = math.isclose(c['absolute_edge'], .1) and math.isclose(c['relative_edge'], .2)
    checks['10_ev'] = all(math.isclose(evaluate_fixture(p=p)['ev_per_unit'], expected, abs_tol=1e-15)
                           for p, expected in ((.6,.2),(.5,0),(.4,-.2)))
    checks['11_post_cutoff_blocked'] = blocked('observed_at', '2026-10-26T11:00:01Z')
    checks['12_post_kickoff_blocked'] = blocked('observed_at', '2026-10-26T12:00:01Z')
    checks['13_closing_blocked'] = blocked('snapshot_type', 'closing')
    pol = default_policy()
    parts = minimum_odds(.6, 1/.6, pol.for_market('BTTS'))
    checks['14_minimum_odds'] = parts['minimum_acceptable_odds'] == max((1/.6)*1.05, 1.05/.6)
    gate_policy = Policy('boundary', '1', tuple((k, MarketPolicy(min_absolute_edge=0, min_relative_edge=0)) for k in sorted(MARKETS)))
    threshold = parts['minimum_acceptable_odds']
    exact = select(evaluate_fixture(odds=threshold), gate_policy, allow_synthetic=True)
    below = select(evaluate_fixture(odds=math.nextafter(threshold, 0)), gate_policy, allow_synthetic=True)
    checks['15_equality_deterministic'] = exact['decision'] == 'PASS' and below['decision'] == 'NO_BET'
    m, r = fixture()
    production = evaluate(m, r)
    checks['16_decision_semantics'] = (select(c, allow_synthetic=True)['decision'] == 'PASS'
        and select(evaluate_fixture(p=.1), allow_synthetic=True)['decision'] == 'NO_BET'
        and select(production)['decision'] == 'BLOCKED'
        and select(evaluate_fixture(p=0), allow_synthetic=True)['decision'] == 'BLOCKED')
    report = sensitivity([c, evaluate_fixture(p=.1), production], [pol], allow_synthetic=True)
    checks['17_sensitivity_descriptive'] = (len(report['policies']) == 1
        and report['policies'][0]['candidate_count'] == 3
        and all(word not in canonical_json(report).lower() for word in ('best_policy', 'roi', 'profit', 'best_threshold')))
    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(v) for v in value))
        return set()
    checks['18_no_sizing_fields'] = not (keys(report) & {'stake', 'kelly', 'bet_amount', 'bankroll', 'roi_forecast'})
    checks['19_deterministic_outputs'] = (canonical_json(c) == canonical_json(evaluate_fixture())
        and canonical_json(report) == canonical_json(sensitivity([c, evaluate_fixture(p=.1), production], [pol], allow_synthetic=True)))
    return checks, dict(candidate_sha256=digest(c), selector_sha256=digest(exact), sensitivity_sha256=digest(report))


def validation():
    before = json.loads((DOCS/'integrity-before.json').read_text())
    after = tracked_after(before)
    original_roots = json.loads((REPO/'docs/v3/odds/integrity-before.json').read_text())
    protected_before = json.loads((DOCS/'protected-before.json').read_text())
    protected_after = fingerprints(original_roots)
    # Verify the current core against both the Phase 4 baseline and Phase 3's
    # preexisting baseline (including mtimes and ignored datasets).
    integrity = {k: dict(before=v, after=protected_after.get(k), unchanged=v == protected_after.get(k),
                         phase3_unchanged=original_roots['roots'].get(k) == protected_after.get(k))
                 for k, v in protected_before.items()}
    checks = {}
    checks['01_phase3_odds_files_intact'] = all(after[p] == v for p, v in before.items()
        if p.startswith(('v3/odds/', 'tests/v3/test_odds', 'docs/v3/odds/', 'docs/v3/phase-3')))
    checks['02_odds_contract_intact'] = after['v3/odds/contract.py'] == before['v3/odds/contract.py']
    checks['03_source_matrix_fail_closed'] = not matrix_errors(source_matrix()) and not any(map(automatable, source_matrix()))
    checks['04_no_fabricated_authorization'] = (after['v3/odds/source_matrix.py'] == before['v3/odds/source_matrix.py']
        and after['docs/v3/odds/source-matrix.json'] == before['docs/v3/odds/source-matrix.json']
        and evaluate(*fixture())['exclusion_reason'] == 'source_not_authorized')
    network_calls = []
    def no_network(*args, **kwargs):
        network_calls.append('blocked_network_attempt')
        raise AssertionError('network_forbidden')
    with ExitStack() as stack:
        for obj, field in ((socket, 'socket'), (socket, 'getaddrinfo'), (socket, 'create_connection')):
            stack.enter_context(patch.object(obj, field, no_network))
        numeric, examples = math_checks()
        checks.update(numeric)
        compile_result = subprocess.run([sys.executable, '-m', 'compileall', '-q', 'v3', 'tests'], cwd=REPO, capture_output=True, text=True)
        suite = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/v3'], cwd=REPO, capture_output=True, text=True)
    passed = re.search(r'(\d+) passed', suite.stdout)
    checks['20_full_v3_suite_passes'] = compile_result.returncode == suite.returncode == 0 and passed is not None
    for number, root in ((21, 'data'), (22, 'scraper'), (23, 'analysis'), (24, 'main.py')):
        checks[f'{number:02}_{root.replace(".", "_")}_intact'] = integrity[root]['unchanged'] and integrity[root]['phase3_unchanged']
    checks['25_lineage_intact'] = all(integrity[k]['unchanged'] and integrity[k]['phase3_unchanged']
        for k in ('BT0', 'J_BT_sin_temporada', 'lineage:BT0', 'lineage:J_BT_sin_temporada'))
    checks['26_champion_and_existing_files_intact'] = before == after and protected_before == protected_after and all(v['unchanged'] and v['phase3_unchanged'] for v in integrity.values())
    guard = (REPO/'tests/v3/conftest.py').read_text()
    checks['27_offline'] = not network_calls and all(k in guard for k in ('autouse=True', 'getaddrinfo', 'connect_ex', 'sendto', "'socket'"))
    preexisting = json.loads((DOCS/'preexisting-untracked.json').read_text())
    preexisting_after = {str(p.relative_to(REPO)): sha(p) for p in (REPO/'v3_data').rglob('*') if p.is_file()}
    changed = sorted(set(subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=REPO, text=True).splitlines()
        + subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()))
    allowed = ('v3/value/', 'tests/v3/test_value_', 'docs/v3/value/', 'docs/v3/phase-4-')
    own_changes = [p for p in changed if p not in preexisting]
    checks['28_scope_isolated'] = (preexisting == preexisting_after
        and all(p.startswith(allowed) for p in own_changes)
        and subprocess.check_output(['git', 'branch', '--show-current'], cwd=REPO, text=True).strip() == 'feature/phase4-batch-4.1-4.2')
    excluded = {'docs/v3/value/integrity-after.json', 'docs/v3/value/protected-after.json',
                'docs/v3/value/artifacts-manifest.json', 'docs/v3/phase-4-validation-report.json'}
    artifacts = {p: sha(REPO/p) for p in own_changes if p not in excluded and (REPO/p).is_file()}
    result = dict(version='4.2.0', result='passed' if all(checks.values()) else 'failed', checks=checks,
        tests=dict(total_passed=int(passed.group(1)) if passed else None, exit_code=suite.returncode,
                   compile_exit_code=compile_result.returncode, summary=suite.stdout.strip().splitlines()[-1:] if suite.returncode else f'{passed.group(1)} passed'),
        integrity=integrity, tracked_files_unchanged=before == after,
        manifest_sha256=digest(artifacts), example_hashes=examples, files_created=own_changes,
        preexisting_untracked=dict(root='v3_data/', unchanged=preexisting == preexisting_after, files=len(preexisting)),
        network=dict(validation_attempts=len(network_calls), tests='autouse socket/DNS guard'),
        source_issues=[32, 33], live_authorized=False,
        gaps=['No live source project grant', 'Synthetic policy defaults are not historically validated',
              'No probability calibration assessment', 'J_BT_sin_temporada has no separately present local artifacts'],
        phase5_dependency='Consume only revalidated eligible evidence and explicitly versioned policies; production remains blocked pending source authorization.')
    for path, value in ((DOCS/'integrity-after.json', after), (DOCS/'protected-after.json', protected_after),
                        (DOCS/'artifacts-manifest.json', artifacts), (REPO/'docs/v3/phase-4-validation-report.json', result)):
        path.write_text(canonical_json(value), encoding='utf-8')
    return result


def main():
    result = validation()
    print(canonical_json({k: result[k] for k in ('result', 'checks', 'tests', 'manifest_sha256', 'example_hashes')}), end='')
    return 0 if result['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
