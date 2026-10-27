from v3.selection.daily import daily
from test_selection_policy_final import candidate


def test_daily_fields_and_deterministic_ranking():
    a=candidate();b=candidate(p=.8)
    b['target']['target_id']='b';b['target']['internal_match_id']='b';b['model']['internal_match_id']='b';b['value_model']['internal_match_id']='b'
    for o in b['odds_observations']:o['record']['internal_match_id']='b'
    r=daily([b,a],allow_synthetic=True)
    assert r==daily([a,b],allow_synthetic=True)
    assert [x['target_id'] for x in r['pass_candidates']]==['synthetic-target','b']
    for field in ('date','model_probability','calibrated_probability','fair_odds','market_odds','minimum_acceptable_odds','market_no_vig_probability','absolute_edge','relative_edge','ev_per_unit','PickScore','PickScore_components','provenance','versions'):
        assert field in r['pass_candidates'][0]


def test_daily_blocked_real_no_bet_and_duplicates():
    assert daily([candidate()])['pass_candidates']==[]
    r=daily([candidate(),candidate(p=.5),{}],allow_synthetic=True)
    assert len(r['pass_candidates'])==0 and len(r['blocked'])==3
    assert daily([candidate(p=.5)],allow_synthetic=True)['no_bet']
    assert daily([])['real_daily_picks_status']=='BLOCKED'
