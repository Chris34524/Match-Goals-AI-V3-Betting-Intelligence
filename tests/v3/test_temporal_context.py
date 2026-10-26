"""Issue #17: observed streak contract and isolation regressions."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from v3.data.builder import dumps
from v3.features.catalog import get_catalog
from v3.features.engine import materialize as form_materialize, build_features as build_form
from v3.features.xg_engine import materialize as xg_materialize, build_features as build_xg
from v3.features.temporal_context import materialize, build_features, SPECS, BLOCKED
from test_form_engine import history, sample, tree_hash


def feature(row, metric='scoring', side='home'):
    return row['features'][f'{side}_{metric}_streak_capped_l10']


@pytest.mark.parametrize('metric,scores,expected', [
    ('scoring', [(1, 0), (2, 1), (0, 1), (3, 1)], 2),
    ('btts', [(1, 1), (2, 3), (1, 0), (1, 1)], 2),
    ('clean_sheet', [(1, 0), (0, 0), (1, 1), (1, 0)], 2),
    ('scoring', [(0, 1), (2, 1)], 0),
    ('btts', [(0, 0), (2, 1)], 0),
    ('clean_sheet', [(0, 1), (2, 0)], 0),
])
def test_prefix_predicates_and_orientation(metric, scores, expected):
    h = history()
    for side, team in enumerate(('Home', 'Away')):
        h['secciones'][side]['partidos'] = [sample(i, team, home=i % 2 == 0, gf=gf, ga=ga)
                                           for i, (gf, ga) in enumerate(scores)]
    r = materialize(h, 'target')
    for side in ('home', 'away'):
        f = feature(r, metric, side)
        assert f['value'] == expected
        assert not f['censored'] and not f['capped']
        assert f['partial_sample']
        assert f['breaking_match_id'] == ('Home' if side == 'home' else 'Away') + f'-{expected:02}'
        assert len(f['contributing_match_ids']) == expected


@pytest.mark.parametrize('n', [0, 1, 4, 9, 10, 11, 20])
def test_cap_partial_and_empty(n):
    r = materialize(history(n), 'target')
    f = feature(r)
    assert f['observed_sample_count'] == min(n, 10)
    assert f['value'] == (min(n, 10) if n else None)
    assert f['reason'] == (None if n else 'no_eligible_samples')
    assert f['censored'] and f['capped'] == (n >= 10)
    assert f['partial_sample'] == (n < 10)
    assert len(r['windows']['home_l10']['contributing']) == min(n, 10)


@pytest.mark.parametrize('changes,reason', [
    ({'match_id': 'target'}, 'target_in_input'),
    ({'fecha': '2026-10-24', 'hora': '00:01'}, 'same_day_input_without_verified_time'),
    ({'fecha': '2026-10-25'}, 'future_input'),
    ({'fecha': None}, 'unknown_input_date'),
    ({'match_id': None}, 'unknown_input_identity'),
    ({'goles_local': True}, 'invalid_score'),
    ({'goles_local': -1}, 'invalid_score'),
    ({'local': 'Unknown'}, 'team_conflict'),
    ({'score_scope': 'EXTRA_TIME'}, 'unverified_regulation_scope'),
    ({'decidido_penales': True}, 'unverified_regulation_scope'),
    ({'penales_local': 4}, 'unverified_regulation_scope'),
    ({'score_scope': None}, 'unverified_regulation_scope'),
])
def test_shared_exclusions(changes, reason):
    h = history(3)
    h['secciones'][0]['partidos'][0].update(changes)
    r = materialize(h, 'target')
    assert feature(r)['value'] == 2
    assert reason in r['exclusions']['home'][0]['reasons']
    assert r['exclusions'] == form_materialize(h, 'target')['exclusions']
    assert r['windows']['home_l10']['contributing'] == form_materialize(h, 'target')['windows']['home_l10']['contributing']


def test_duplicate_exclusion_order_and_tie_break():
    h = history(5)
    samples = h['secciones'][0]['partidos']
    samples.append(dict(samples[0], goles_local=0))
    samples[1]['fecha'] = samples[2]['fecha']
    first = materialize(h, 'target')
    assert feature(first)['value'] == 4
    assert [s['match_id'] for s in first['windows']['home_l10']['contributing']][:2] == ['Home-01', 'Home-02']
    assert sum('duplicate_match_id' in e['reasons'] for e in first['exclusions']['home']) == 2
    for section in h['secciones']:
        section['partidos'].reverse()
    h['secciones'].reverse()
    assert dumps(first) == dumps(materialize(h, 'target'))


@pytest.mark.parametrize('mutation', [
    lambda h: h.update(partido=[]), lambda h: h['partido'].update(id='wrong'),
    lambda h: h.update(secciones='invalid'), lambda h: h.update(secciones=[]),
    lambda h: h['secciones'].append(copy.deepcopy(h['secciones'][0])),
    lambda h: h['secciones'][0].update(partidos=None),
])
def test_invalid_section_or_target(mutation):
    h = history()
    mutation(h)
    f = feature(materialize(h, 'target'))
    assert f['value'] is None and f['reason']
    assert f['observed_sample_count'] is None
    assert f['censored'] is None and f['capped'] is None


def test_raw_scope_and_annotated_rows():
    h = history(1)
    s = h['secciones'][0]['partidos'][0]
    del s['score_scope']
    s['competicion_codigo'] = 'L'
    s['lineas_raw'] = [s['fecha'], 'L', s['local'], s['visitante'], '2', '1', 'G']
    assert feature(materialize(h, 'target'))['value'] == 1
    for marker in ('Pen.', 'Prórroga', 'AET'):
        changed = copy.deepcopy(h)
        changed['secciones'][0]['partidos'][0]['lineas_raw'].insert(4, marker)
        assert feature(materialize(changed, 'target'))['value'] is None


def test_catalog_blocked_features_and_provenance():
    assert len(SPECS) == 6
    assert all(s.status == 'available' and s.dtype == 'int' for s in SPECS)
    assert set(BLOCKED) == {f'{s}_{m}' for s in ('home', 'away') for m in ('days_rest', 'matches_last_14_days')}
    assert all(s.status == 'blocked' for s in get_catalog(group='temporal_context') if s.name in BLOCKED)
    r = materialize(history(1), 'target')
    assert not set(BLOCKED) & r['features'].keys()
    w = r['windows']['home_l10']
    assert w['source_artifact'] == 'target/history.json'
    assert w['contributing'][0] == dict(match_id='Home-00', date='2026-09-28', venue='home', gf=2, ga=1, score_evidence='explicit_REGULATION')
    assert w['observed_sample_count'] == 1


def test_build_reproducible_readonly_poison_and_prior_outputs(tmp_path):
    root = tmp_path / 'data'
    folder = root / 'matches/target'
    folder.mkdir(parents=True)
    h = history()
    (folder / 'history.json').write_text(json.dumps(h))
    prior_form = build_form(root / 'matches', tmp_path / 'form-a')
    prior_xg = build_xg(root, tmp_path / 'xg-a')
    first = build_features(root / 'matches', tmp_path / 'one')
    before = tree_hash(root)
    second = build_features(root / 'matches', tmp_path / 'two')
    assert before == tree_hash(root)
    assert first == second
    for name in ('temporal_features.jsonl', 'temporal_manifest.json'):
        assert (tmp_path / 'one' / name).read_bytes() == (tmp_path / 'two' / name).read_bytes()
    assert first['jsonl_sha256'] == hashlib.sha256((tmp_path / 'one/temporal_features.jsonl').read_bytes()).hexdigest()
    assert prior_form == build_form(root / 'matches', tmp_path / 'form-b')
    assert prior_xg == build_xg(root, tmp_path / 'xg-b')
    for name, stem in [('form', 'form_features.jsonl'), ('xg', 'xg_features.jsonl')]:
        assert (tmp_path / f'{name}-a' / stem).read_bytes() == (tmp_path / f'{name}-b' / stem).read_bytes()
    original = dumps(materialize(h, 'target'))
    h.update(labels=999, backtest_pool=999, Champion=999, result=999, confidence=999, **{'lambda': 999})
    h['secciones'].append(dict(titulo='ENFRENTAMIENTOS: Home - Away', partidos=[sample(0, gf=0)]))
    assert original == dumps(materialize(h, 'target'))
    # Neither filesystem artifacts nor fabricated completeness claims authorize a ledger.
    for name in ('labels', 'backtest_pool', 'Champion', 'result', 'confidence', 'lambda', 'fixture_ledger'):
        (folder / f'{name}.json').write_text('{"complete":true}')
    (folder / 'history.json').write_text(json.dumps(h))
    before = tree_hash(root)
    third = build_features(root / 'matches', tmp_path / 'three')
    assert third['jsonl_sha256'] == first['jsonl_sha256']
    assert before == tree_hash(root)
    assert third['blocked_features'] == BLOCKED
    for output in (root, root / 'generated', folder):
        with pytest.raises(ValueError):
            build_features(root / 'matches', output)


def test_unsafe_outputs_and_invalid_history(tmp_path):
    root = tmp_path / 'source'
    folder = root / 'target'
    folder.mkdir(parents=True)
    (folder / 'history.json').write_text('{"x":1,"x":2}')
    build_features(root, tmp_path / 'one')
    row = json.loads((tmp_path / 'one/temporal_features.jsonl').read_text())
    assert all(f['value'] is None and f['reason'] == 'missing_or_invalid_history' for f in row['features'].values())
    out = tmp_path / 'unsafe'
    out.mkdir()
    (out / 'temporal_features.jsonl').symlink_to(folder / 'history.json')
    with pytest.raises(ValueError):
        build_features(root, out)
    (out / 'temporal_features.jsonl').unlink()
    import os
    os.link(folder / 'history.json', out / 'temporal_features.jsonl')
    with pytest.raises(ValueError):
        build_features(root, out)


def test_ledger_audit_readonly_and_untrusted_completeness(tmp_path):
    from v3.features.ledger_audit import audit_ledger
    root = tmp_path / 'data'
    folder = root / 'matches/target'
    folder.mkdir(parents=True)
    h = history(3)
    h['complete_ledger'] = True
    (folder / 'history.json').write_text(json.dumps(h))
    (root / 'partidos.json').write_text('{"complete":true,"partidos":[]}')
    (root / 'match_detail.html').write_text('Mostrar más partidos calendar')
    (root / 'result.json').write_text('FORBIDDEN')
    (root / 'fixture_ledger.json').symlink_to(folder / 'history.json')
    before = tree_hash(root)
    first = audit_ledger(root)
    assert first == audit_ledger(root)
    assert tree_hash(root) == before
    assert first['candidate_files'] == 3
    assert first['history_section_lengths'] == {'3': 2}
    assert first['groups']['matches/<id>/history.json']['completeness_key_paths']['$/complete_ledger'] == 1
    assert len(first['decisions']) == 4
    assert all(d['status'] == 'blocked' for d in first['decisions'].values())
