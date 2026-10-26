"""2.1A acquisition boundary, observable context and recursive read-only audit."""
from dataclasses import asdict, replace
import builtins
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from v3.features.catalog import CATALOG
from v3.features.context_catalog import CONTEXT_ROWS
from v3.features.surface_catalog import (
    AVAILABILITY, CAPTURE_POLICIES, LEVELS, MARKETS, PRIORITIES, STATUSES,
    SURFACE_CATALOG, get_surface_catalog, surface_catalog_json, surface_summary,
)
from v3.features.surface_audit import audit_surface, source_role


def test_deterministic_serialization_and_unique_names():
    names = [s.name for s in SURFACE_CATALOG]
    assert names == sorted(set(names))
    original = surface_catalog_json()
    decoded = json.loads(original)
    assert original == json.dumps(decoded, ensure_ascii=False, sort_keys=True,
                                  allow_nan=False, separators=(',', ':')) + '\n'
    decoded['signals'][0]['markets'].clear()
    assert surface_catalog_json() == original
    outputs = [subprocess.check_output([sys.executable, '-c',
        'from v3.features.surface_catalog import surface_catalog_json; print(surface_catalog_json(),end="")'],
        env={**os.environ, 'PYTHONHASHSEED': str(seed)}) for seed in (1, 42)]
    assert outputs[0] == outputs[1] == original.encode()


@pytest.mark.parametrize('spec', SURFACE_CATALOG, ids=lambda s: s.name)
def test_signal_contract(spec):
    for key, value in asdict(spec).items():
        if key not in ('automatable', 'source_artifacts', 'public_references'):
            assert value, key
    assert spec.level in LEVELS
    assert spec.capture_policy in CAPTURE_POLICIES
    assert spec.surface_availability in AVAILABILITY
    assert spec.status in STATUSES
    assert spec.priority in PRIORITIES
    assert set(spec.markets) <= set(MARKETS)
    assert spec.source_artifacts or spec.public_references
    assert not spec.automatable  # Catalog-only phase implements no capture/extractor.
    for path in spec.source_artifacts:
        assert not any(term in path.lower() for term in
            ('labels', 'backtest', 'champion', 'confidence', 'lambda_comparison', 'result.json'))
    if spec.priority == 'P0':
        assert spec.source_artifacts and spec.surface_availability == 'observed_local'
        assert spec.capture_policy == 'existing_local'
    if spec.capture_policy == 'requires_authorization':
        assert 'authorization' in spec.enablement_requirement


@pytest.mark.parametrize('policy', ['requires_authorization', 'blocked'])
def test_reject_automation_for_unauthorized_signals(policy):
    with pytest.raises(ValueError, match='cannot be automatable'):
        replace(SURFACE_CATALOG[0], capture_policy=policy, automatable=True)


@pytest.mark.parametrize('path', ['data/backtest_pool.json', 'data/Champion.json',
                                   'data/labels.json', 'data/matches/x/result.json'])
def test_reject_evaluation_provenance(path):
    with pytest.raises(ValueError, match='cannot be feature sources'):
        replace(SURFACE_CATALOG[0], source_artifacts=(path,))


@pytest.mark.parametrize('key,values', [('level', LEVELS), ('status', STATUSES),
                                       ('priority', PRIORITIES), ('market', MARKETS)])
def test_filters(key, values):
    before = surface_catalog_json()
    for value in values:
        expected = tuple(s for s in SURFACE_CATALOG if
                         (value in s.markets if key == 'market' else getattr(s, key) == value))
        assert get_surface_catalog(**{key: value}) == expected
        assert json.loads(surface_catalog_json(**{key: value}))['signals'] == json.loads(
            json.dumps([asdict(s) for s in expected]))
    with pytest.raises(ValueError):
        get_surface_catalog(**{key: 'invalid'})
    assert surface_catalog_json() == before


def test_combined_filters_and_base_compatibility():
    assert get_surface_catalog(level='player', status='available', priority='P0') == ()
    assert get_surface_catalog(level='team', priority='P0', market='BTTS')
    assert {s.name for s in CATALOG} <= {s.name for s in SURFACE_CATALOG}
    summary = surface_summary()
    assert sum(summary['level'].values()) == sum(summary['priority'].values()) == summary['signals']


def test_minimum_surface_and_observable_context():
    names = {s.name for s in SURFACE_CATALOG}
    assert {'team_xgot', 'team_xa', 'team_corners', 'team_goals_prevented',
            'player_identity', 'player_minutes', 'player_rating', 'player_xg', 'player_xa',
            'player_minutes_load', 'player_transfer_history', 'player_saves',
            'lineup_official_xi', 'lineup_predicted_xi', 'lineup_formation',
            'lineup_injury', 'lineup_illness', 'lineup_suspension', 'lineup_not_in_squad',
            'discipline_player_card_rates', 'discipline_cards_by_match_state',
            'odds_player_props', 'context_points_to_threshold', 'context_lineup_surprise'} <= names
    # Explicit closed, reviewed set of factual proxy definitions, not free-text emotion scores.
    for name, description, prerequisites in CONTEXT_ROWS:
        spec = next(s for s in SURFACE_CATALOG if s.name == 'context_' + name)
        assert spec.description == description
        assert prerequisites in spec.observable_basis
        assert spec.priority == 'P2'
    assert not any(word in s.name for s in SURFACE_CATALOG for word in
                   ('anxiety', 'happiness', 'anger', 'mental_state', 'motivation_score'))
    by_state = next(s for s in SURFACE_CATALOG if s.name == 'discipline_cards_by_match_state')
    assert 'Complete ordered card/goal events' in by_state.enablement_requirement


def test_audit_discovers_unknown_nested_files_and_file_coverage(tmp_path):
    root = tmp_path / 'matches'
    nested = root / 'one' / 'unknown'
    nested.mkdir(parents=True)
    (nested / 'players.json').write_text(json.dumps({'players': [
        {'id': 'secret', 'rating': None}, {'id': 'other', 'rating': 7.2}]}))
    (root / 'one' / 'new.txt').write_text('private article text')
    report = audit_surface(root)
    assert report['files'] == 2
    item = report['artifacts']['<id>/unknown/players.json']
    assert item['files'] == 1
    assert item['key_path_types']['$/players/[]/id:string'] == 1
    assert item['key_path_types']['$/players/[]/rating:null'] == 1
    assert item['key_path_types']['$/players/[]/rating:number'] == 1
    encoded = json.dumps(report)
    assert 'secret' not in encoded and 'private article text' not in encoded
    assert report == audit_surface(root)
    (nested / 'players.json').write_text('{"new_key":1}')
    assert audit_surface(root)['source_content_sha256'] != report['source_content_sha256']


def test_audit_skips_symlinks_and_retains_invalid_and_array_json(tmp_path):
    root = tmp_path / 'matches'
    folder = root / 'one'
    folder.mkdir(parents=True)
    (folder / 'duplicate.json').write_text('{"x":1,"x":2}')
    (folder / 'nan.json').write_text('{"x":NaN}')
    (folder / 'bad.json').write_bytes(b'\xff')
    (folder / 'array.json').write_text('[true,null,3]')
    (folder / 'loop').symlink_to(root, target_is_directory=True)
    (folder / 'link.json').symlink_to(folder / 'array.json')
    report = audit_surface(root)
    assert report['files'] == 4
    assert report['skipped_symlinks'] == ['one/link.json', 'one/loop']
    assert sum(x['invalid_json'] for x in report['artifacts'].values()) == 3
    assert report['artifacts']['<id>/array.json']['key_path_types']['$:array'] == 1
    with pytest.raises(ValueError):
        audit_surface(folder / 'loop')


def test_audit_no_writes_or_network_even_under_data(tmp_path, monkeypatch):
    root = tmp_path / 'data'
    root.mkdir()
    fixture = root / 'history.json'
    fixture.write_text('{"x":1}')
    before = (fixture.read_bytes(), fixture.stat().st_mtime_ns, root.stat().st_mtime_ns)
    real_open = builtins.open
    real_path_open = Path.open

    def read_only_open(path, mode='r', *args, **kwargs):
        assert not any(flag in mode for flag in 'wax+')
        return real_open(path, mode, *args, **kwargs)

    def read_only_path_open(path, mode='r', *args, **kwargs):
        assert not any(flag in mode for flag in 'wax+')
        return real_path_open(path, mode, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError('writes/network forbidden during audit')

    monkeypatch.setattr(builtins, 'open', read_only_open)
    monkeypatch.setattr(Path, 'open', read_only_path_open)
    for method in ('mkdir', 'touch', 'unlink', 'rename', 'replace', 'write_bytes', 'write_text'):
        monkeypatch.setattr(Path, method, forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    report = audit_surface(root)
    assert report['files'] == 1
    assert before == (fixture.read_bytes(), fixture.stat().st_mtime_ns, root.stat().st_mtime_ns)
    assert list(root.iterdir()) == [fixture]


def test_inventory_only_is_not_feature_permission():
    for path in ('matches/x/backtest.json', 'matches/x/confidence.json',
                 'experiments/a/history.json', 'evaluation/a.json',
                 'matches/x/enriched.json', 'matches/x/h2h_analysis.json', 'unknown.json'):
        assert source_role(path) == 'inventory_only'
    assert source_role('xg_cache/x.json') == 'candidate_raw_requires_validation'
    assert source_role('matches/x/history.json') == 'candidate_raw_requires_validation'


def test_local_text_evidence_does_not_promote_match_ratings_or_official_xi():
    rows = {s.name: s for s in SURFACE_CATALOG}
    for name in ('lineup_predicted_xi', 'lineup_injury', 'lineup_card_absence',
                 'player_season_average_rating', 'team_average_rating', 'odds_1x2'):
        assert rows[name].surface_availability == 'observed_local'
        assert rows[name].capture_policy == 'existing_local'
        assert rows[name].priority != 'P0'
        assert rows[name].status != 'available'
        assert 'unaccredited' in rows[name].enablement_requirement
    for name in ('player_rating', 'lineup_official_xi', 'lineup_formation'):
        assert rows[name].surface_availability != 'observed_local'
        assert rows[name].capture_policy == 'requires_authorization'


def test_audit_groups_cache_without_sampling_and_escapes_keys(tmp_path):
    cache = tmp_path / 'xg_cache'
    cache.mkdir()
    for name in ('a', 'b'):
        (cache / (name + '.json')).write_text('{"x/y~z":1}')
    report = audit_surface(tmp_path)
    item = report['artifacts']['xg_cache/<id>.json']
    assert item['files'] == 2
    assert item['key_path_types']['$/x~1y~0z:number'] == 2
    assert item['example_path'] == 'xg_cache/a.json'
