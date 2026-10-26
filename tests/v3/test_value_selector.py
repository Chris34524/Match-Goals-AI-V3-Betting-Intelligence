"""Policy boundaries, replay integrity and deterministic offline CLI."""
from copy import deepcopy
from dataclasses import replace
import json
import math
import socket
import pytest
from v3.odds.contract import MARKETS
from v3.value.fixtures import fixture
from v3.value.engine import evaluate
from v3.value.policy import MarketPolicy, Policy, default_policy
from v3.value.selector import select, minimum_odds
from v3.value.report import sensitivity
from v3.value.contract import serialize
from v3.value.cli import main


def candidate(p=.6,odds=2.,market='BTTS'):
    m,r=fixture(market,p,odds)
    return evaluate(m,r,allow_synthetic=True)


def policy(**kwargs):
    return Policy('test','1',tuple((k,MarketPolicy(**kwargs)) for k in sorted(MARKETS)))


def decision(c,pol=None):
    return select(c,pol,allow_synthetic=True)


def test_minimum_components():
    mp=MarketPolicy(safety_margin=.1,min_ev=.2)
    c=minimum_odds(.5,2.,mp)
    assert c['minimum_odds_markup']==2.2
    assert c['minimum_odds_ev']==2.4
    assert c['minimum_acceptable_odds']==2.4
    assert minimum_odds(.5,2.,replace(mp,min_ev=0))['minimum_acceptable_odds']==2.2


@pytest.mark.parametrize('margin,ev',[(0,0),(.05,.05),(.1,.2),(.2,.1)])
def test_exact_price_boundary(margin,ev):
    pol=policy(safety_margin=margin,min_ev=ev,min_absolute_edge=0,min_relative_edge=0)
    threshold=minimum_odds(.6,1/.6,pol.for_market('BTTS'))['minimum_acceptable_odds']
    below=math.nextafter(threshold,0)
    assert decision(candidate(odds=below),pol)['decision']=='NO_BET'
    assert 'odds_below_minimum' in decision(candidate(odds=below),pol)['reason_codes']
    assert decision(candidate(odds=threshold),pol)['decision']=='PASS'
    assert decision(candidate(odds=math.nextafter(threshold,math.inf)),pol)['decision']=='PASS'


def test_no_rounding():
    pol=policy(safety_margin=.05,min_ev=.05,min_absolute_edge=0,min_relative_edge=0)
    threshold=minimum_odds(.6,1/.6,pol.for_market('BTTS'))['minimum_acceptable_odds']
    assert round(threshold,2)==round(threshold-1e-10,2)
    assert decision(candidate(odds=threshold-1e-10),pol)['decision']=='NO_BET'
    assert decision(candidate(odds=threshold),pol)['decision']=='PASS'


@pytest.mark.parametrize('kwargs,reason',[
    ({'min_absolute_edge':.2},'edge_below_threshold'),
    ({'min_relative_edge':.3},'relative_edge_below_threshold'),
    ({'min_ev':.3},'ev_below_threshold')])
def test_value_gates(kwargs,reason):
    out=decision(candidate(),policy(**kwargs))
    assert out['decision']=='NO_BET'
    assert reason in out['reason_codes']


@pytest.mark.parametrize('field',['safety_margin','min_ev','min_absolute_edge','min_relative_edge'])
@pytest.mark.parametrize('value',[-.1,float('nan'),float('inf'),-float('inf'),True,'0.1',None,1000])
def test_bad_policy(field,value):
    with pytest.raises(ValueError):MarketPolicy(**{field:value})


def test_market_isolation_and_config_roundtrip():
    base=default_policy()
    changes=dict(base.markets);changes['BTTS']=MarketPolicy(min_ev=.8)
    other=replace(base,markets=tuple(sorted(changes.items())))
    assert decision(candidate(),other)['decision']=='NO_BET'
    for market in MARKETS:
        if market!='BTTS':
            assert decision(candidate(market=market),base)==decision(candidate(market=market),other)
    assert Policy.from_dict(other.to_dict())==other
    bad=other.to_dict();del bad['markets']['1X2']
    with pytest.raises(ValueError):Policy.from_dict(bad)


@pytest.mark.parametrize('kind',['closing','late','unauthorized','incomplete','inactive','probability','provenance','zero'])
def test_blocked_semantics(kind):
    m,r=fixture()
    if kind=='closing':r[0]['record']['snapshot_type']='closing'
    if kind=='late':r[0]['record']['observed_at']='2026-10-26T12:01:00Z'
    if kind=='unauthorized':r[0]['record']['provider']='other'
    if kind=='incomplete':r.pop()
    if kind=='inactive':r[0]['record']['price_state']='suspended'
    if kind=='probability':m['model_probability']=-1
    if kind=='provenance':m['provenance']={}
    if kind=='zero':m['model_probability']=0
    out=decision(evaluate(m,r,allow_synthetic=True))
    assert out['decision']=='BLOCKED'
    assert out['minimum_acceptable_odds'] is None
    assert out['reason_codes']
    serialize(out)


def test_replay_and_no_synthetic_production_escape():
    c=candidate()
    assert select(c)['decision']=='BLOCKED'
    for field,value in [('ev_per_unit',100),('eligibility','BLOCKED'),('market_odds',100),('model_probability',1)]:
        forged=deepcopy(c);forged[field]=value
        assert decision(forged)['reason_codes']==['candidate_integrity_mismatch']
    assert decision({})['decision']=='BLOCKED'
    assert decision(None)['decision']=='BLOCKED'


def test_sensitivity_counts_and_no_optimization():
    c=[candidate(),candidate(p=.1),candidate(p=0)]
    pol=default_policy()
    report=sensitivity(c,[pol],allow_synthetic=True)
    assert serialize(report)==serialize(sensitivity(c,[pol],allow_synthetic=True))
    row=report['policies'][0]
    assert (row['candidate_count'],row['pass_count'],row['no_bet_count'],row['blocked_count'])==(3,1,1,1)
    assert row['by_market']['BTTS']['candidate_count']==3
    assert row['edge_distribution']['count']==3
    assert row['minimum_odds_distribution']['count']==2
    assert row['candidates'][1]['reason_codes']
    assert len(sensitivity(c,[pol,replace(pol,policy_id='strict')],allow_synthetic=True)['policies'])==2
    text=serialize(report).lower()
    for forbidden in ['best_policy','best_threshold','roi','profit','stake','kelly','bet_amount']:
        assert forbidden not in text
    with pytest.raises(ValueError):sensitivity(c,[pol,pol])


def test_cli_offline_json_jsonl(tmp_path,monkeypatch,capsys):
    def denied(*args,**kwargs):raise AssertionError('network prohibited')
    monkeypatch.setattr(socket,'socket',denied)
    m,r=fixture();input_path=tmp_path/'input.json'
    input_path.write_text(serialize([dict(model=m,observations=r)]))
    args=['evaluate','--input',str(input_path),'--synthetic-test-only']
    main(args);first=capsys.readouterr().out
    main(args);assert first==capsys.readouterr().out
    assert json.loads(first)[0]['decision']=='PASS'
    config=tmp_path/'policies.json';config.write_text(serialize([default_policy().to_dict()]))
    main(['sensitivity','--input',str(input_path),'--policy',str(config),'--synthetic-test-only'])
    assert json.loads(capsys.readouterr().out)['policies'][0]['pass_count']==1
    input_path.write_text(json.dumps(candidate())+'\n')
    main(['evaluate','--input',str(input_path),'--input-jsonl','--jsonl','--synthetic-test-only'])
    assert json.loads(capsys.readouterr().out)['decision']=='PASS'
    input_path.write_text('[NaN]')
    with pytest.raises(SystemExit):main(args)
