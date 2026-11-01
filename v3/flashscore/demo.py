"""Reproducible synthetic FS-4/FS-5 illustration: python -m v3.flashscore.demo."""
from dataclasses import replace
from datetime import date, timedelta

from .contract import Capability, Evidence, Fixture, Request, dumps
from .feature_materializer import FeatureMaterializer
from .market_contract import MarketSpec, RESEARCH_CARDS
from .normalization import unit_for
from .targets import TargetEngine


def synthetic_demo():
    target = Fixture('synthetic', 'demo-target', 'synthetic-league', '2026', 'demo',
                     'finished', 'A', 'B', '2026-10-30')
    cutoff = '2026-10-30T12:00:00Z'
    observations = []

    def add(f, metric, period, side, value):
        surface = 'summary' if metric.startswith('goals_') else {
            'FT': 'stats_overall', '1H': 'stats_first_half', '2H': 'stats_second_half'}[period]
        entity = getattr(f, side + '_id')
        request = Request(f, surface, period, metric, side=side, entity_id=entity)
        published = (date.fromisoformat(f.match_date)+timedelta(days=1)).isoformat()+'T08:00:00Z'
        evidence = Evidence(published, 'synthetic://fs45-demo', 'synthetic',
            inspected_fixture=f, inspected_surface=surface, selected_period=period,
            selected_period_evidence='synthetic-explicit-period', period_evidence_method='structured_period',
            inspected_entity_id=entity, inspected_side=side, inspection='success', value=value,
            unit=unit_for(metric), score_scope='regulation', publication_at=published,
            publication_verified=True, revision_history_verified=True, sample_reference='synthetic-only',
            evidence_quality='synthetic', settlement_rules=RESEARCH_CARDS.operand_rules if metric=='cards' else None,
            card_actor_scope='on_field_players' if metric=='cards' else None)
        observations.append(Capability(request, evidence))

    for i in range(10):
        away = i % 2 == 1
        f = replace(target, match_id=f'demo-history-{i:02}', home_id='C' if away else 'A',
                    away_id='A' if away else 'C', match_date=(date(2026,10,28)-timedelta(days=i)).isoformat())
        add(f, 'goals_ft', 'FT', 'away' if away else 'home', i % 3)
    for metric, period, home, away in (
        ('goals_ft','FT',2,1), ('goals_first_half','1H',1,0), ('goals_second_half','2H',1,1),
        ('corners','FT',6,4), ('shots_on_target','FT',5,3),
        ('cards','FT',dict(yellow=2,direct_red=0,second_yellow_dismissals=1),
         dict(yellow=1,direct_red=0,second_yellow_dismissals=0))):
        add(target,metric,period,'home',home)
        add(target,metric,period,'away',away)
    specs = [MarketSpec('goals','over',line=2.5), MarketSpec('goals','over','1H',line=.5),
        MarketSpec('goals','over','2H',line=.5), MarketSpec('goals','btts'),
        MarketSpec('corners','over',line=9.5), MarketSpec('corners','most'),
        MarketSpec('cards','over',line=3.5), MarketSpec('shots_on_target','over',side='home',line=4.5)]
    features = FeatureMaterializer(observations).materialize(target,cutoff,names=['goals_for'])
    targets = TargetEngine(observations).settle(target,specs=specs,card_policy=RESEARCH_CARDS)
    feature_fields = ('feature_id','feature_name','scope','value','status','n_required','n_eligible','n_available','source_match_ids')
    target_fields = ('target_key','market_family','market','side','period','line','status','outcome','binary_label')
    return dict(sample_kind='synthetic', meaning='Illustration only; no real coverage or prediction quality claim.',
        card_policy=RESEARCH_CARDS.to_dict(),
        features=[{k:r[k] for k in feature_fields} for r in features if r['side']=='home' and r['window']=='L5'],
        targets=[{k:r[k] for k in target_fields} for r in targets])


if __name__ == '__main__':
    print(dumps(synthetic_demo()))
