"""Noisy, fixed-seed synthetic capabilities replayed through FS-4 and FS-5."""
from datetime import date, timedelta
import random

from ..contract import Capability, Evidence, Fixture, Request
from ..feature_materializer import FeatureMaterializer
from ..market_contract import MarketSpec, RESEARCH_CARDS
from ..normalization import unit_for
from ..targets import TargetEngine
from .dataset import BASE_POLICY, build_dataset


def synthetic_cohort(n=320, seed=68):
    if n < 1:
        raise ValueError('positive_sample_required')
    rng = random.Random(seed)
    observations, fixtures = [], []
    for i in range(n + 10):
        f = Fixture('synthetic', f'demo-{i:04}', 'synthetic-league', 'demo', 'demo',
            'finished', 'A' if i % 2 else 'B', 'B' if i % 2 else 'A',
            (date(2020,1,1) + timedelta(days=3*i)).isoformat())
        fixtures.append(f)
        published = (date.fromisoformat(f.match_date)+timedelta(days=1)).isoformat()+'T08:00:00Z'
        for metric in ('goals_ft','corners','cards','shots'):
            for side in ('home','away'):
                # Broad random variation and mild shared environment; no perfect labels.
                maximum = {'goals_ft':4,'corners':9,'cards':5,'shots':18}[metric]
                value = rng.randint(0, maximum)
                if metric == 'cards':
                    value = dict(yellow=value, direct_red=int(rng.random()<.04), second_yellow_dismissals=0)
                surface = 'summary' if metric == 'goals_ft' else 'stats_overall'
                entity = getattr(f, side+'_id')
                request = Request(f, surface, 'FT', metric, side=side, entity_id=entity)
                evidence = Evidence(published, 'synthetic://fs68/noisy', 'synthetic',
                    inspected_fixture=f, inspected_surface=surface, selected_period='FT',
                    selected_period_evidence='synthetic-explicit', period_evidence_method='structured_period',
                    inspected_entity_id=entity, inspected_side=side, inspection='success', value=value,
                    unit=unit_for(metric), score_scope='regulation', publication_at=published,
                    publication_verified=True, revision_history_verified=True,
                    sample_reference='synthetic-only-seed-68', evidence_quality='synthetic',
                    settlement_rules=RESEARCH_CARDS.operand_rules if metric == 'cards' else None,
                    card_actor_scope=RESEARCH_CARDS.actor_scope if metric == 'cards' else None)
                observations.append(Capability(request,evidence))
    return fixtures[10:], observations


def materialized_cohort(n=320):
    fixtures, observations = synthetic_cohort(n)
    materializer, targets = FeatureMaterializer(observations), TargetEngine(observations)
    output = {}
    for family, line, side in (('goals',3.5,'total'),('corners',8.5,'total'),
                               ('cards',4.5,'total'),('shots',8.5,'home')):
        features, labels = [], []
        policy = dict(BASE_POLICY, cards=RESEARCH_CARDS.to_dict() if family == 'cards' else None)
        for f in fixtures:
            cutoff = (date.fromisoformat(f.match_date)-timedelta(days=1)).isoformat()+'T12:00:00Z'
            features.extend(materializer.materialize(f,cutoff,
                names=[family+'_for',family+'_against'],scopes=['overall'],card_policy=RESEARCH_CARDS if family=='cards' else None))
            labels.extend(targets.settle(f,specs=[MarketSpec(family,'over',side=side,line=line)],
                card_policy=RESEARCH_CARDS if family=='cards' else None))
        dataset = build_dataset(features, labels, fixtures, feature_set=family+'-core-v1',policy=policy)
        output[family] = dict(dataset=dataset, fixtures=fixtures, features=features, targets=labels)
    return output
