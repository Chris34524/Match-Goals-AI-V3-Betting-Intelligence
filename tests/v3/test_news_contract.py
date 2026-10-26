from copy import deepcopy
import pytest
from v3.features.news_contract import EVENT_TYPES, schema_errors, ingestion_errors

CUTOFF = '2026-10-24T12:00:00+00:00'


def event():
    return dict(provider='synthetic_test_only', source_id='article-1',
                publication_timestamp='2026-10-24T10:00:00+00:00',
                entity=dict(kind='player', id='p-1'), event_type='injury_confirmed',
                structured_value=dict(status='confirmed'), extraction_version='test-v1',
                evidence='Synthetic fixture evidence, not a real report.', confidence=.95)


def test_schema_validity_does_not_grant_ingestion_or_authenticity():
    e = event(); before = deepcopy(e)
    assert schema_errors(e,CUTOFF) == ()
    assert ingestion_errors(e,CUTOFF) == ('provider_not_permitted_or_asof_unaccredited',)
    assert e == before
    e['provider'] = 'flashscore_existing_archive'
    assert 'provider_not_permitted_or_asof_unaccredited' in ingestion_errors(e,CUTOFF)


@pytest.mark.parametrize('kind', EVENT_TYPES)
def test_objective_event_types_remain_separate(kind):
    e = event(); e['event_type'] = kind
    e['entity']['kind'], statuses = EVENT_TYPES[kind]
    e['structured_value']['status'] = statuses[0]
    assert schema_errors(e,CUTOFF) == ()
    assert ingestion_errors(e,CUTOFF)


@pytest.mark.parametrize('field,value,reason', [
    ('publication_timestamp',None,'unverified_timestamp_shape'),
    ('publication_timestamp','2026-10-24T10:00:00','unverified_timestamp_shape'),
    ('publication_timestamp',CUTOFF,'publication_not_before_cutoff'),
    ('publication_timestamp','2026-10-25T10:00:00+00:00','publication_not_before_cutoff'),
    ('revision_timestamp','2026-10-24T12:01:00+00:00','invalid_or_late_revision'),
    ('revision_timestamp','2026-10-23T12:01:00+00:00','invalid_or_late_revision'),
    ('confidence',True,'invalid_confidence'), ('confidence',float('nan'),'invalid_confidence'),
    ('confidence',float('inf'),'invalid_confidence'), ('confidence',1.1,'invalid_confidence'),
    ('confidence',-.1,'invalid_confidence'), ('evidence','','invalid_or_unbounded_evidence'),
    ('evidence','x'*2001,'invalid_or_unbounded_evidence'),
    ('entity',{'kind':'player','id':''},'invalid_entity'),
    ('entity',{'kind':'team','id':'shirt-10'},'invalid_entity'),
    ('event_type','psychological_sentiment','unsupported_event_type'),
    ('structured_value',{'motivation':'high'},'invalid_structured_value'),
    ('url','http://example.org','invalid_source_url'),
])
def test_invalid_or_leaky_evidence(field,value,reason):
    e = event(); e[field] = value
    assert reason in schema_errors(e,CUTOFF)
    assert ingestion_errors(e,CUTOFF)


def test_source_reference_and_predicted_official_separation():
    e=event(); del e['source_id']
    assert 'missing_source_reference' in schema_errors(e,CUTOFF)
    e['url']='https://example.org/synthetic'
    assert schema_errors(e,CUTOFF) == ()
    e['event_type']='lineup_statement'; e['entity']['kind']='team'
    for status in ('predicted','official'):
        e['structured_value']['status']=status
        assert schema_errors(e,CUTOFF) == ()
    e['structured_value']['status']='combined'
    assert 'invalid_structured_value' in schema_errors(e,CUTOFF)


def test_unknown_fields_and_invalid_root_are_rejected():
    assert schema_errors([],CUTOFF) == ('invalid_event',)
    e=event();e['sentiment']='confident'
    assert 'invalid_fields' in schema_errors(e,CUTOFF)


@pytest.mark.parametrize('changes,reason', [({'url':'https://['},'invalid_source_url'),
    ({'confidence':10**1000},'invalid_confidence'),
    ({'structured_value':{'status':'confirmed','confidence_psychological':'high'}},'invalid_structured_value')])
def test_untrusted_shapes_fail_closed_without_exception(changes,reason):
    e=event();e.update(changes)
    assert reason in ingestion_errors(e,CUTOFF)
