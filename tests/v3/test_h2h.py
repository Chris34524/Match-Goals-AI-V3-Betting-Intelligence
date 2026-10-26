from copy import deepcopy
import pytest
from v3.features.catalog import CATALOG
from v3.features.h2h import SPECS, materialize, build_features
from test_form_engine import history, sample


def pair_history(n=5):
    h = history()
    samples = []
    for i in range(n):
        s = sample(i, home=i % 2 == 0, gf=i, ga=1)
        s['local' if i % 2 else 'visitante'] = 'Away'
        samples.append(s)
    h['secciones'].append(dict(titulo='ENFRENTAMIENTOS', partidos=samples))
    return h


def test_orientation_and_auxiliary_isolation():
    h = pair_history()
    r = materialize(h, 'target')
    assert len(SPECS) == 14
    assert set(SPECS) == {s.name for s in CATALOG if s.name.startswith('h2h_')}
    assert set(r['features']) == set(SPECS)
    assert not any(name.startswith('h2h_away_gf_mean_') for name in r['features'])
    assert not any(name.startswith('h2h_away_ga_mean_') for name in r['features'])
    assert r['features']['h2h_home_gf_mean_h5']['value'] == 2
    for cap in (5, 10):
        assert r['features'][f'h2h_home_gf_mean_h{cap}']['value'] == 2
        assert r['features'][f'h2h_home_ga_mean_h{cap}']['value'] == 1
    h['secciones'] = h['secciones'][-1:]
    h['result'] = {'score': 99}
    assert materialize(h, 'target') == r


@pytest.mark.parametrize('n', [0, 1, 2, 3, 4, 5, 9, 10, 11])
def test_minimum_catalog_three_and_caps(n):
    r = materialize(pair_history(n), 'target')
    for cap in (5, 10):
        assert r['features'][f'h2h_sample_count_h{cap}']['value'] == min(n, cap)
        assert (r['features'][f'h2h_btts_rate_h{cap}']['value'] is None) == (n < 3)


@pytest.mark.parametrize('change,reason', [
    ({'match_id': 'target'}, 'target_in_input'),
    ({'fecha': '2026-10-24'}, 'same_day_input_without_verified_time'),
    ({'fecha': '2026-10-25'}, 'future_input'),
    ({'fecha': None}, 'unknown_input_date'),
    ({'visitante': 'Other'}, 'h2h_pair_conflict'),
    ({'goles_local': True}, 'invalid_score'),
    ({'score_scope': 'EXTRA_TIME'}, 'unverified_regulation_scope'),
    ({'decidido_penales': True}, 'unverified_regulation_scope'),
])
def test_exclusions(change, reason):
    h = pair_history()
    h['secciones'][-1]['partidos'][0].update(change)
    r = materialize(h, 'target')
    assert reason in r['exclusions']['h2h'][0]['reasons']
    assert r['features']['h2h_sample_count_h5']['value'] == 4


def test_duplicates_all_excluded_order_independent():
    h = pair_history()
    h['secciones'][-1]['partidos'].append(deepcopy(h['secciones'][-1]['partidos'][0]))
    r = materialize(h, 'target')
    h['secciones'][-1]['partidos'].reverse()
    assert materialize(h, 'target') == r
    assert r['features']['h2h_sample_count_h5']['value'] == 4


def test_missing_and_ambiguous_are_null():
    h = history()
    assert all(f['value'] is None for f in materialize(h, 'target')['features'].values())
    h = pair_history()
    h['secciones'].append(deepcopy(h['secciones'][-1]))
    assert all(f['value'] is None for f in materialize(h, 'target')['features'].values())


def test_build_deterministic_and_protect_source(tmp_path):
    import json
    root = tmp_path/'sources'; folder = root/'target'; folder.mkdir(parents=True)
    p = folder/'history.json'; p.write_text(json.dumps(pair_history()))
    before = p.read_bytes(), p.stat().st_mtime_ns
    a, b = tmp_path/'a', tmp_path/'b'
    assert build_features(root,a) == build_features(root,b)
    for path in a.iterdir(): assert path.read_bytes() == (b/path.name).read_bytes()
    assert before == (p.read_bytes(),p.stat().st_mtime_ns)
    with pytest.raises(ValueError): build_features(root,root/'output')
    (a/'h2h_features.jsonl').unlink(); (a/'h2h_features.jsonl').symlink_to(p)
    with pytest.raises(ValueError): build_features(root,a)


def test_thresholds_and_zero_are_observed():
    h = pair_history(3)
    for s in h['secciones'][-1]['partidos']:
        s.update(goles_local=0, goles_visitante=0)
    r = materialize(h,'target')
    assert all(v['value'] == 0 for k,v in r['features'].items() if 'sample_count' not in k)
    for s in h['secciones'][-1]['partidos']: s.update(goles_local=2,goles_visitante=1)
    r = materialize(h,'target')['features']
    assert r['h2h_btts_rate_h5']['value'] == 1
    assert r['h2h_over_1_5_rate_h5']['value'] == 1
    assert r['h2h_over_2_5_rate_h5']['value'] == 1
    assert r['h2h_over_3_5_rate_h5']['value'] == 0


def test_date_tie_id_order_and_cap():
    h = pair_history(6)
    for s in h['secciones'][-1]['partidos']: s['fecha'] = '2026-09-01'
    r = materialize(h,'target')
    assert [s['match_id'] for s in r['windows']['h5']['contributing']] == [f'Home-{i:02}' for i in range(5)]


def test_prohibited_artifacts_cannot_change_h2h():
    h = pair_history(); before = materialize(h,'target')
    for name in ('labels','backtest_pool','result.json','Champion','confidence.json','lambda_comparison.json','h2h_analysis.json'):
        h[name] = {'home_goals': 999}
    assert materialize(h,'target') == before


def test_real_six_field_h2h_grammar_and_annotations():
    h = pair_history(5)
    for s in h['secciones'][-1]['partidos']:
        s.pop('score_scope')
        s['competicion_codigo'] = 'LEAGUE'
        s['lineas_raw'] = [s['fecha'],s['competicion_codigo'],s['local'],s['visitante'],str(s['goles_local']),str(s['goles_visitante'])]
    r = materialize(h,'target')
    assert r['features']['h2h_sample_count_h5']['value'] == 5
    assert all(s['score_evidence']=='flashscore_ordinary_h2h_row_v1' for s in r['windows']['h5']['contributing'])
    h['secciones'][-1]['partidos'][0]['lineas_raw'].append('Tras prórroga')
    assert materialize(h,'target')['features']['h2h_sample_count_h5']['value'] == 4
    h['secciones'][-1]['partidos'][1]['decidido_penales'] = True
    assert materialize(h,'target')['features']['h2h_sample_count_h5']['value'] == 3


@pytest.mark.parametrize('bad_id', [[], {}])
def test_malformed_identity_fails_closed(bad_id):
    h=pair_history(); h['secciones'][-1]['partidos'][0]['match_id']=bad_id
    r=materialize(h,'target')
    assert r['features']['h2h_sample_count_h5']['value']==4
    assert any('unknown_input_identity' in x['reasons'] for x in r['exclusions']['h2h'])
