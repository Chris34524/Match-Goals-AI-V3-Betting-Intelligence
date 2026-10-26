"""Reproducible synthetic observations. No production authorization."""
from v3.odds.contract import MARKETS


def fixture(market='BTTS', p=.6, odds=2.0):
    cutoff = '2026-10-26T11:00:00Z'
    line = {'OVER_1_5':1.5, 'OVER_2_5':2.5, 'OVER_3_5':3.5}.get(market)
    model = dict(internal_match_id='synthetic-1', market=market, selection=MARKETS[market][0],
        line=line, model_id='synthetic-model', model_version='1', model_probability=p,
        cutoff=cutoff, period='full_time', rules='90_minutes_including_stoppage_no_extra_time',
        provenance=dict(origin='synthetic_test_only', evidence='offline fixture'))
    records = []
    for selection in MARKETS[market]:
        r = dict(internal_match_id='synthetic-1', external_match_id='fixture-1', competition='Synthetic',
            season='2026', kickoff_at='2026-10-26T12:00:00Z', timezone='UTC', market=market,
            selection=selection, line=line, bookmaker='synthetic-book', provider='synthetic_test_only',
            decimal_odds=odds, observed_at='2026-10-26T10:00:00Z', source_published_at=None,
            snapshot_type='current', source=dict(id='fixture', artifact='synthetic.json', url=None),
            surface_availability='unknown', capture_policy='review',
            provenance=dict(origin='synthetic_test_only', evidence='offline fixture', sha256='a'*64),
            validity=dict(pre_match=True), exclusion_reason=None,
            temporal_semantics=dict(definition=None, evidence=None), aggregation='individual', population=[],
            price_state='active', status='review')
        records.append(dict(record=r, cutoff=cutoff, period=model['period'], rules=model['rules']))
    return model, records

