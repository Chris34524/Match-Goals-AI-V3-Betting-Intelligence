import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from v3.data.builder import dumps
from v3.features.engine import materialize, build_features, SPECS


def sample(i, team='Home', home=True, gf=2, ga=1):
    return dict(match_id=f'{team}-{i:02}', fecha=f'2026-09-{28-i:02}',
                local=team if home else 'Other', visitante='Other' if home else team,
                goles_local=gf if home else ga, goles_visitante=ga if home else gf,
                resultado_parseado=True, score_scope='REGULATION')


def history(n=20):
    return dict(match_id='target', partido=dict(id='target', fecha='2026-10-24', local='Home', visitante='Away'),
                secciones=[dict(titulo='ÚLTIMOS PARTIDOS: ' + t,
                                partidos=[sample(i, t, home=i % 2 == 0) for i in range(n)]) for t in ('Home', 'Away')])


def test_catalog_and_orientation():
    h = history()
    r = materialize(h, 'target')
    assert len(SPECS) == len(r['features']) == 72
    assert all(v['value'] is not None for v in r['features'].values())
    for side in ('home', 'away'):
        for venue in ('', 'venue_'):
            for n in (5, 10):
                prefix = f'{side}_{venue}'
                assert r['features'][f'{prefix}gf_mean_l{n}']['value'] == 2
                assert r['features'][f'{prefix}ga_mean_l{n}']['value'] == 1
                assert r['features'][f'{prefix}sample_count_l{n}']['value'] == n
    assert r['windows']['away_venue_l10']['contributing'][0]['match_id'] == 'Away-01'
    assert len(r['windows']['home_venue_l10']['contributing']) == 10


def test_order_and_deterministic_duplicate_exclusion():
    h = history()
    h['secciones'][0]['partidos'].append(dict(sample(0), goles_local=99))
    before = materialize(h, 'target')
    for section in h['secciones']:
        section['partidos'].reverse()
    h['secciones'].reverse()
    assert dumps(before) == dumps(materialize(h, 'target'))
    assert all(s['match_id'] != 'Home-00' for s in before['windows']['home_l10']['contributing'])
    assert sum('duplicate_match_id' in e['reasons'] for e in before['exclusions']['home']) == 2


@pytest.mark.parametrize('changes,reason', [
    ({'match_id': 'target'}, 'target_in_input'),
    ({'fecha': '2026-10-24'}, 'same_day_input_without_verified_time'),
    ({'fecha': '2026-10-25'}, 'future_input'),
    ({'fecha': None}, 'unknown_input_date'),
    ({'match_id': None}, 'unknown_input_identity'),
    ({'goles_local': True}, 'invalid_score'),
    ({'goles_local': -1}, 'invalid_score'),
    ({'local': 'Unknown'}, 'team_conflict'),
    ({'score_scope': 'EXTRA_TIME'}, 'unverified_regulation_scope'),
    ({'decidido_penales': True}, 'unverified_regulation_scope'),
])
def test_rejections(changes, reason):
    h = history(5)
    h['secciones'][0]['partidos'][0].update(changes)
    r = materialize(h, 'target')
    assert reason in r['exclusions']['home'][0]['reasons']
    assert r['features']['home_sample_count_l5']['value'] == 4
    assert r['features']['home_gf_mean_l5']['value'] is None


@pytest.mark.parametrize('n', [0, 1, 4, 5, 9, 10])
def test_exact_sample_and_nulls(n):
    r = materialize(history(n), 'target')
    for window in (5, 10):
        assert r['features'][f'home_sample_count_l{window}']['value'] == min(n, window)
        f = r['features'][f'home_gf_mean_l{window}']
        assert (f['value'] is None) == (n < window)
        assert f['reason'] == ('insufficient_sample' if n < window else None)


def test_missing_not_zero():
    h = history()
    h['secciones'] = []
    assert all(f['value'] is None and f['reason'] for f in materialize(h, 'target')['features'].values())


def test_thresholds_and_zero_rates():
    h = history(5)
    h['secciones'][0]['partidos'] = [sample(i, gf=gf, ga=ga) for i, (gf, ga) in enumerate([(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)])]
    r = materialize(h, 'target')['features']
    for metric, value in [('gf_mean', 1.2), ('ga_mean', .8), ('btts_rate', .6),
                          ('over_1_5_rate', .6), ('over_2_5_rate', .4), ('over_3_5_rate', .2),
                          ('clean_sheet_rate', .4), ('failed_to_score_rate', .2)]:
        assert r[f'home_{metric}_l5']['value'] == value


def test_raw_scope_grammar():
    h = history(5)
    s = h['secciones'][0]['partidos'][0]
    del s['score_scope']
    s['competicion_codigo'] = 'LEAGUE'
    s['lineas_raw'] = [s['fecha'], 'LEAGUE', s['local'], s['visitante'], '2', '1', 'G']
    assert materialize(h, 'target')['features']['home_gf_mean_l5']['value'] == 2
    for marker in ('Prórroga', 'Pen.', 'AET'):
        modified = copy.deepcopy(h)
        modified['secciones'][0]['partidos'][0]['lineas_raw'].insert(4, marker)
        assert materialize(modified, 'target')['features']['home_gf_mean_l5']['value'] is None


def test_venue_before_window_and_tie_break():
    h = history()
    samples = h['secciones'][0]['partidos']
    for s in samples[:10]:
        s.update(local='Other', visitante='Home', goles_local=1, goles_visitante=2)
    for s in samples[10:]:
        s.update(local='Home', visitante='Other', goles_local=3, goles_visitante=0)
    r = materialize(h, 'target')
    assert r['features']['home_venue_sample_count_l10']['value'] == 10
    assert r['features']['home_venue_gf_mean_l10']['value'] == 3
    samples[0]['fecha'] = samples[1]['fecha']
    r = materialize(h, 'target')
    assert [s['match_id'] for s in r['windows']['home_l5']['contributing']][:2] == ['Home-00', 'Home-01']


def tree_hash(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_build_reproducible_readonly_and_poison_independent(tmp_path):
    root = tmp_path / 'source'
    folder = root / 'target'
    folder.mkdir(parents=True)
    h = history()
    (folder / 'history.json').write_text(json.dumps(h))
    before = tree_hash(root)
    first = build_features(root, tmp_path / 'one')
    assert before == tree_hash(root)
    for name in ('result.json', 'champion_snapshot.json', 'lambda_comparison.json', 'labels.json', 'backtest_pool.json'):
        (folder / name).write_text('POISON')
    h.update(labels={'goals': 999}, predictions={'lambda': 999}, confidence=999, result=999)
    (folder / 'history.json').write_text(json.dumps(h))
    before = tree_hash(root)
    second = build_features(root, tmp_path / 'two')
    assert before == tree_hash(root)
    assert first['jsonl_sha256'] == second['jsonl_sha256']
    assert (tmp_path / 'one/form_features.jsonl').read_bytes() == (tmp_path / 'two/form_features.jsonl').read_bytes()
    third = build_features(root, tmp_path / 'three')
    assert second == third
    assert (tmp_path / 'two/form_manifest.json').read_bytes() == (tmp_path / 'three/form_manifest.json').read_bytes()
    assert third['coverage']['complete_all'] == 1
    with pytest.raises(ValueError):
        build_features(root, folder)


@pytest.mark.parametrize('mutation', [lambda h: h.update(partido=[]),
    lambda h: h['partido'].update(id='wrong'), lambda h: h.update(secciones='invalid'),
    lambda h: h['secciones'].append(copy.deepcopy(h['secciones'][0]))])
def test_invalid_structures_fail_closed(mutation):
    h = history()
    mutation(h)
    r = materialize(h, 'target')
    assert r['features']['home_sample_count_l5']['value'] is None
    assert r['features']['home_gf_mean_l5']['reason']


def test_no_data_staged_or_tracked():
    root = Path(__file__).resolve().parents[2]
    for args in (['ls-files', '--', 'data/'], ['diff', '--cached', '--name-only', '--', 'data/']):
        result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True)
        assert not result.stdout.strip()
