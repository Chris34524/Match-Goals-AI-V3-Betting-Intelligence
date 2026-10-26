from copy import deepcopy
import json
import pytest
from v3.odds.contract import (MARKETS, FUTURE_MARKETS, SNAPSHOTS, SURFACES, POLICIES,
    schema_errors, validate, canonical_json, filter_records, ingestion_errors)

CUTOFF = '2026-10-26T11:00:00Z'


def record():
    return dict(internal_match_id='v3-1', external_match_id='provider-1',
        competition='Synthetic league', season='2026/27', kickoff_at='2026-10-26T12:00:00Z',
        timezone='UTC', market='1X2', selection='home', line=None, bookmaker='book-a',
        provider='synthetic_test_only', decimal_odds=2.1, observed_at='2026-10-26T10:00:00Z',
        source_published_at=None, snapshot_type='unknown',
        source=dict(id='price-1', artifact='synthetic.json', url=None),
        surface_availability='unknown', capture_policy='review',
        provenance=dict(evidence='synthetic fixture', sha256='a'*64, origin='synthetic'),
        validity=dict(pre_match=True), exclusion_reason=None,
        temporal_semantics=dict(definition=None, evidence=None), aggregation='individual',
        population=[], price_state='active', status='review')


def test_valid_schema_does_not_authorize_ingestion():
    r = record(); before = deepcopy(r)
    assert validate(r, CUTOFF) == r
    assert r == before
    assert ingestion_errors(r, CUTOFF) == ('provider_not_authorized_for_ingestion',)


@pytest.mark.parametrize('value', [1, 0, -2, float('nan'), float('inf'), -float('inf'), True, '2.0', None])
def test_bad_prices(value):
    r = record(); r['decimal_odds'] = value
    assert 'invalid_decimal_odds' in schema_errors(r, CUTOFF)
    with pytest.raises(ValueError): validate(r, CUTOFF)


@pytest.mark.parametrize('market', MARKETS)
def test_markets_and_both_sides(market):
    for selection in MARKETS[market]:
        r = record(); r.update(market=market, selection=selection)
        if market.startswith('OVER_'): r['line'] = float(market[5:].replace('_', '.'))
        assert not schema_errors(r, CUTOFF)
        r['selection'] = 'unsupported'
        assert 'invalid_selection' in schema_errors(r, CUTOFF)


@pytest.mark.parametrize('market', ['invalid', None, {}, *FUTURE_MARKETS])
def test_unsupported_and_future_markets(market):
    r = record(); r['market'] = market
    assert 'invalid_market' in schema_errors(r, CUTOFF)


@pytest.mark.parametrize('field,values', [('surface_availability', SURFACES), ('capture_policy', POLICIES), ('snapshot_type', SNAPSHOTS)])
def test_vocabularies(field, values):
    for value in values:
        r=record(); r[field]=value
        r['temporal_semantics'] = dict(definition='Provider-declared pre-kickoff observation boundary', evidence='synthetic declaration')
        assert not schema_errors(r,CUTOFF)
    for value in ('automatable', '', None, []):
        r=record(); r[field]=value
        assert 'invalid_'+field in schema_errors(r,CUTOFF)


@pytest.mark.parametrize('field,value,error', [
 ('timezone',None,'invalid_timezone'), ('timezone','Mars/Test','invalid_timezone'),
 ('timezone','America/Mexico_City','timezone_offset_mismatch'),
 ('observed_at','2026-10-26T10:00:00','invalid_timestamp'),
 ('source_published_at','2026-10-26T09:00:00','invalid_publication_timestamp'),
 ('source_published_at','2026-10-26T10:01:00Z','publication_after_observation'),
 ('bookmaker',None,'bookmaker_required'),('bookmaker','','bookmaker_required'),
 ('bookmaker','unknown','bookmaker_required'),('bookmaker','anonymous','bookmaker_required'),
 ('line',2.5,'invalid_line'),('validity',{'pre_match':'true'},'invalid_validity'),
 ('price_state','suspended','inactive_price'),('price_state','crossed_out','inactive_price'),
 ('price_state','unavailable','inactive_price'),('source',{},'invalid_source_reference'),
 ('provenance',{},'invalid_provenance'),('internal_match_id','','invalid_internal_match_id')])
def test_invalid_fields(field,value,error):
    r=record(); r[field]=value
    assert error in schema_errors(r,CUTOFF)


@pytest.mark.parametrize('time', ['2026-10-26T11:01:00Z','2026-10-26T12:00:00Z','2026-10-26T12:01:00Z'])
def test_late_snapshot_can_only_be_inventory(time):
    r=record(); r['observed_at']=time
    assert 'not_available_pre_match_at_cutoff' in schema_errors(r,CUTOFF)
    r.update(validity={'pre_match':False},exclusion_reason='not available at decision')
    assert not schema_errors(r,CUTOFF)


def test_cutoff_itself_must_precede_kickoff():
    assert 'not_available_pre_match_at_cutoff' in schema_errors(record(),'2026-10-26T12:00:00Z')
    assert 'invalid_timestamp' in schema_errors(record(),'undated')


@pytest.mark.parametrize('snapshot', ['opening','closing'])
def test_snapshot_requires_evidence(snapshot):
    r=record(); r['snapshot_type']=snapshot
    assert 'snapshot_requires_explicit_temporal_evidence' in schema_errors(r,CUTOFF)
    r['temporal_semantics']=dict(definition='Provider-declared boundary before kickoff',evidence='synthetic')
    assert not schema_errors(r,CUTOFF)
    r.update(observed_at='2026-10-26T12:01:00Z',validity={'pre_match':False},exclusion_reason='late')
    assert 'opening_or_closing_not_before_kickoff' in schema_errors(r,CUTOFF)


def test_unknown_is_preserved_and_deterministic():
    r=record(); r['source']['artifact']='closing/opening/0001.json'
    before=deepcopy(r)
    assert not schema_errors(r,CUTOFF)
    assert json.loads(canonical_json(r))['snapshot_type']=='unknown'
    assert canonical_json(r)==canonical_json(dict(reversed(list(r.items()))))
    assert r==before
    with pytest.raises(ValueError): canonical_json({'odds':float('nan')})


@pytest.mark.parametrize('aggregation',['average','maximum','consensus'])
def test_population_required_and_reproducible(aggregation):
    r=record(); r.update(aggregation=aggregation,bookmaker=None)
    assert 'population_not_reproducible' in schema_errors(r,CUTOFF)
    r['population']=[dict(bookmaker=b,source_id=b,decimal_odds=o,observed_at=r['observed_at']) for b,o in [('a',2.0),('b',2.2)]]
    assert not schema_errors(r,CUTOFF)
    for key,value in [('bookmaker','a'),('source_id',''),('decimal_odds',float('nan')),('observed_at','2026-10-26T11:30:00Z')]:
        broken=deepcopy(r); broken['population'][1][key]=value
        assert 'population_not_reproducible' in schema_errors(broken,CUTOFF)


@pytest.mark.parametrize('source',['labels','result','results','backtest_pool','Champion','BT0','J_BT_sin_temporada'])
@pytest.mark.parametrize('field',['provider','source','provenance'])
def test_forbidden_source_lineage(source,field):
    r=record()
    if field=='source': r['source']['artifact']=f'data/{source}/prices.json'
    elif field=='provenance': r['provenance']['origin']=source
    else: r[field]=source
    assert 'forbidden_odds_source' in schema_errors(r,CUTOFF)


def test_filters_compose_without_mutation():
    a=record(); b=record(); b.update(provider='other',snapshot_type='current',status='blocked',market='BTTS')
    rows=[a,b]; before=deepcopy(rows)
    assert filter_records(rows,market='1X2',provider='synthetic_test_only',snapshot='unknown',status='review')==[a]
    for kw in (dict(market='BTTS'),dict(provider='other'),dict(snapshot='current'),dict(status='blocked')):
        assert filter_records(rows,**kw)==[b]
    assert filter_records(rows,provider='missing')==[]
    assert rows==before


def test_invalid_roots_missing_extra_fields():
    assert schema_errors(None,CUTOFF)==('invalid_record',)
    for r in ({},dict(record(),extra=True)):
        assert 'invalid_fields' in schema_errors(r,CUTOFF)


@pytest.mark.parametrize('name',['results_archive.json','labels_v3.csv','Champion_snapshot.json','BT0_prices.json'])
def test_forbidden_lineage_with_underscore_boundaries(name):
    r=record(); r['source']['artifact']='data/'+name
    assert 'forbidden_odds_source' in schema_errors(r,CUTOFF)


@pytest.mark.parametrize('field,value,error',[
    ('decimal_odds',10**1000,'invalid_decimal_odds'),
    ('kickoff_at','2026-10-26T12:00:00','invalid_timestamp'),
    ('observed_at',None,'invalid_timestamp'),
    ('exclusion_reason','excluded','contradictory_exclusion'),
    ('validity',{'pre_match':False},'missing_exclusion_reason'),
    ('population',[{}],'individual_has_population'),
])
def test_additional_rejections(field,value,error):
    r=record();r[field]=value
    assert error in schema_errors(r,CUTOFF)
