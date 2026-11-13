"""Additive multimarket analysis; no fitting/promotion of the production Champion."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
from statistics import mean

from analysis.enrich_match import calcular_ventanas_equipo
from analysis.poisson import analizar
from v3.flashscore.contract import dumps
from . import VERSION, CHAMPION
from . import counts
from .evidence import (ROOT, champion, cutoff_for, legacy, observations, read_json,
                       series, target_fixture)
from .flashscore_reference import policy as source_policy, reference as flashscore_reference


def metadata(parts, cutoff, model, *, limitations=(), accreditation='EXPERIMENTAL_PREMATCH_INPUTS'):
    provenance = [p for part in parts for p in part.get('provenance', [])]
    dates = [d for part in parts for d in part.get('dates', [])]
    coverage = [part.get('coverage') for part in parts]
    return dict(model=model, sample_size=[len(part['values']) for part in parts],
                sample_size_unit='per_input_series_not_sum_of_independent_fixtures',
                temporal_window=dict(start=min(dates) if dates else None, end=max(dates) if dates else None),
                coverage=min(coverage) if coverage and all(c is not None for c in coverage) else None,
                source=sorted({p['evidence']['source_url'] for p in provenance}),
                captured_at=sorted({p['evidence']['observed_at'] for p in provenance}),
                prematch_cutoff=cutoff, accreditation=accreditation, oos_eligible=False,
                calibrated=False, limitations=list(limitations),
                statistical_justification='Independent counts; explicit historical means, no goal-rate reuse across families.')


def market(name, probability, status, meta, reason=None):
    return dict(market=name, probability=probability, status=status, reason=reason, **meta)


def goal_group(period, lambdas, status, meta, reason=None):
    probabilities, scores, tail = {}, [], None
    good = status in ('IMPLEMENTED', 'EXPERIMENTAL')
    if good:
        lh, la = lambdas
        if not all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 50 for x in (lh, la)):
            good, status, reason = False, 'BLOCKED', 'invalid_or_out_of_domain_goal_expectation'
        else:
            size = max(12, math.ceil(max(lh, la)+12*math.sqrt(max(lh, la)+1)))
            result = analizar(lh, la, max_goles=size)
            probabilities.update({'1': result['resultado']['victoria_local'], 'X': result['resultado']['empate'],
                                  '2': result['resultado']['victoria_visitante'], **result['doble_oportunidad'],
                                  'BTTS_YES': result['btts']['si'], 'BTTS_NO': result['btts']['no'],
                                  'HOME_SCORES': -math.expm1(-lh), 'AWAY_SCORES': -math.expm1(-la)})
            total = dict(mean=lh+la, dispersion_alpha=0)
            for line in ((1.5, 2.5, 3.5, 4.5) if period == 'FT' else (.5, 1.5)):
                p = counts.over(line, [total])
                probabilities[f'OVER_{line}'], probabilities[f'UNDER_{line}'] = p, 1-p
            probabilities = {name: max(0.0, min(1.0, p)) for name, p in probabilities.items()}
            scores, tail = result['marcadores_probables'], max(0.0, 1-result['masa_matriz'])
    names = (('1', 'X', '2', '1X', 'X2', '12', 'BTTS_YES', 'BTTS_NO') if period == 'FT'
             else ('HOME_SCORES', 'AWAY_SCORES', 'BTTS_YES'))
    names += tuple(f'{direction}_{line}' for line in ((1.5, 2.5, 3.5, 4.5) if period == 'FT' else (.5, 1.5))
                   for direction in ('OVER', 'UNDER'))
    return dict(family='goals', period=period, status=status, reason=reason,
                expected_home=lambdas[0] if good else None, expected_away=lambdas[1] if good else None,
                expected_total=sum(lambdas) if good else None, expectation_kind='model_lambda_not_observed_xG',
                markets=[market(name, probabilities.get(name), status, meta, reason) for name in names],
                likely_scores=scores, omitted_score_matrix_mass=tail, metadata=meta)


def blocked_status(parts):
    return next((s for s in ('BLOCKED', 'NOT_COVERED', 'INSUFFICIENT_DATA')
                 if any(p['status'] == s for p in parts)), 'EXPERIMENTAL')


def advanced_group(index, target, cutoff, family, period, card_policy=None):
    metric = {'goals': {'1H': 'goals_first_half', '2H': 'goals_second_half'}.get(period),
              'corners': 'corners', 'cards': 'cards'}[family]
    parts = [series(index, target, cutoff, side, metric, period, card_policy=card_policy)
             for side in ('home', 'away')]
    limitations = ['Experimental independent-count assumption; probabilities are not calibrated.']
    if family in ('goals', 'corners'):
        parts += [series(index, target, cutoff, side, metric, period, against=True)
                  for side in ('home', 'away')]
    if family == 'corners' and target is not None:
        venue_parts = [series(index, target, cutoff, side, metric, period, against=against, scope=side)
                       for against in (False, True) for side in ('home', 'away')]
        if all(p['status'] == 'EXPERIMENTAL' for p in venue_parts):
            parts = venue_parts
        else:
            limitations.append('Insufficient complete venue samples: explicitly pooled overall home/away history.')
    status = blocked_status(parts)
    reason = '; '.join(sorted({p['reason'] for p in parts if p.get('reason')})) or None
    if family == 'cards' and card_policy is None:
        status, reason = 'BLOCKED', 'explicit_verified_card_counting_policy_required'
    meta = metadata(parts, cutoff, 'independent_poisson' if family == 'goals' else 'independent_count_moments_v1',
                    limitations=limitations)
    if family == 'goals':
        lambdas = ((mean(parts[0]['values'])+mean(parts[3]['values']))/2,
                   (mean(parts[1]['values'])+mean(parts[2]['values']))/2) if status == 'EXPERIMENTAL' else (None, None)
        result = goal_group(period, lambdas, status, meta, reason)
    else:
        lines = (7.5, 8.5, 9.5, 10.5, 11.5) if family == 'corners' and period == 'FT' else (
            (3.5, 4.5, 5.5) if family == 'corners' else (2.5, 3.5, 4.5, 5.5))
        models, evaluations = [], {}
        if status == 'EXPERIMENTAL':
            for i, side in enumerate(('home', 'away')):
                values = parts[i]['values']
                expectation = mean(values)
                if family == 'corners':
                    opponent = parts[3-i]
                    expectation = (expectation+mean(opponent['values']))/2
                    # H2H overlap is one observed team count, never two independent samples.
                    unique = {(s['match_id'], s['entity_id']): s['value']
                              for part in (parts[i], opponent) for s in part['samples']}
                    values = list(unique.values())
                models.append(counts.fit(values, expectation=expectation))
                evaluations[side] = counts.evaluate(list(reversed(parts[i]['values'])), lines)
        result = dict(family=family, period=period, status=status, reason=reason, metadata=meta,
            expected_home=models[0]['mean'] if models else None, expected_away=models[1]['mean'] if models else None,
            expected_total=sum(m['mean'] for m in models) if models else None, models=models,
            validation=evaluations or dict(status='INSUFFICIENT_DATA', metrics=None),
            markets=[market(f'OVER_{line}', counts.over(line, models) if models else None, status, meta, reason)
                     for line in lines])
        if family == 'cards':
            result['counting_policy'] = card_policy.to_dict() if card_policy else None
            result['observed_components'] = {side: {
                key: mean(c[key] for c in part.get('components', [])) if part.get('components') else None
                for key in ('yellow', 'direct_red', 'second_yellow_dismissals')}
                for side, part in zip(('home', 'away'), parts)}
            result['expected_components'] = result['observed_components'] if models else None
            if models:
                red_models = [counts.fit([c['direct_red']+c['second_yellow_dismissals']
                                          for c in part['components']]) for part in parts]
                result['expected_dismissals_total'] = sum(m['mean'] for m in red_models)
                result['markets'].append(market('ANY_DISMISSAL', counts.over(.5, red_models), status, meta))
            else:
                result['expected_dismissals_total'] = None
                result['markets'].append(market('ANY_DISMISSAL', None, status, meta, reason))
            # No unverified event ledger or bookmaker point equivalence is inferred.
            result['metadata']['limitations'].append('Policy counts exclusive components; no bookmaker equivalence is assumed.')
    result['input_series'] = parts
    return result


def observed_advanced(index, target, cutoff):
    result = {}
    for metric in ('xg', 'xga', 'shots', 'shots_on_target', 'possession', 'yellow_cards', 'red_cards', 'fouls'):
        result[metric] = {}
        for side in ('home', 'away'):
            part = series(index, target, cutoff, side, 'xg' if metric == 'xga' else metric, 'FT',
                          against=metric == 'xga')
            result[metric][side] = dict(status=part['status'], reason=part['reason'],
                mean=mean(part['values']) if part['values'] else None,
                n=len(part['values']), coverage=part['coverage'], provenance=part['provenance'])
    return result


def capability_form(fixture, index, target, cutoff):
    samples, observed, exclusions, parts = {}, {}, {}, []
    for side, venue in (('home', 'local'), ('away', 'visitante')):
        gf = series(index, target, cutoff, side, 'goals_ft', 'FT')
        ga = series(index, target, cutoff, side, 'goals_ft', 'FT', against=True)
        parts.extend((gf, ga))
        good = gf['status'] == ga['status'] == 'EXPERIMENTAL'
        against = {s['match_id']: s for s in ga.get('samples', [])}
        rows = [dict(match_id=s['match_id'], date=s['date'], gf=s['value'],
                     ga=against[s['match_id']]['value'], venue=s['venue'])
                for s in gf.get('samples', []) if s['match_id'] in against] if good else []
        samples[side], exclusions[side] = rows, [dict(reason=gf['reason']), dict(reason=ga['reason'])]
        prepared = [dict(r, gc=r['ga'], total_goles=r['gf']+r['ga'],
                         condicion='local' if r['venue'] == 'home' else 'visitante') for r in rows]
        observed[side] = dict(equipo=fixture[side]['name'], **calcular_ventanas_equipo(prepared, venue))
        for key, stats in observed[side].items():
            if isinstance(stats, dict):
                stats['requested_n'] = int(key[1:]) if key.startswith('l') else None
                stats['partial_sample'] = key.startswith('l') and stats['pj'] < int(key[1:])
                if stats['pj'] == 0:
                    for k in ('gf', 'gc', 'victorias', 'empates', 'derrotas'):
                        stats[k] = None
    return dict(samples=samples, exclusions=exclusions, observed=observed, h2h=None, sources=[],
                input_series=parts,
                warnings=['Capability inputs use existing publication/revision and authorization gates; predictions remain operational, not OOS.'])


def analyze(fixture, *, history_root=ROOT/'data/matches', capability_paths=(), cutoff=None,
            card_policy=None, generated_at=None, capture_manifest=None):
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    from v3.flashscore.contract import timestamp
    generated = timestamp(generated_at)
    requested_cutoff = cutoff
    cutoff = cutoff_for(fixture, cutoff)
    if timestamp(cutoff) > generated:
        if requested_cutoff is not None:
            raise ValueError('feature_cutoff_cannot_follow_generation')
        cutoff = generated.isoformat()
    form = legacy(fixture, history_root, cutoff)
    index, sources = observations(capability_paths)
    target = target_fixture(fixture)
    if not any(form['samples'].values()) and target is not None:
        form = capability_form(fixture, index, target, cutoff)
    reference = flashscore_reference(fixture, history_root, form)
    # Legacy xG lacks historical publication lineage. Only FS-gated xG can feed BT0.
    xg = {}
    for side, label in (('home', 'local'), ('away', 'visitante')):
        xf = series(index, target, cutoff, side, 'xg', 'FT', window=10)
        xa = series(index, target, cutoff, side, 'xg', 'FT', window=10, against=True)
        valid = xf['status'] == xa['status'] == 'EXPERIMENTAL' and xf['dates'] == xa['dates']
        xg[label] = dict(partidos=[dict(xg_disponible=True, xgf=f, xga=a) for f, a in
                                   zip(xf['values'], xa['values'])] if valid else [])
    methods, formula_hash = champion(fixture, form, xg)
    rates = methods.get(CHAMPION, {})
    own = [form['samples'].get(s, []) for s in ('home', 'away')]
    status = 'IMPLEMENTED' if min(map(len, own)) >= 5 and all(rates.get(k) is not None
                    for k in ('local', 'visitante')) else 'INSUFFICIENT_DATA'
    goal_meta = metadata([dict(values=s, dates=[r['date'] for r in s], coverage=min(len(s)/20, 1))
                          for s in own], cutoff, 'BT0 / '+CHAMPION,
                        accreditation='OPERATIONAL_DATE_FILTERED_LEGACY_NOT_OOS',
                        limitations=['Legacy publication lineage unaccredited; no OOS or validation claim.',
                                     'Historical xG without verified as-of lineage is excluded from model inputs.'])
    goal_meta['source'] = [s['path'] for s in form['sources']]
    goal_meta['captured_at'] = None
    if form.get('input_series'):
        goal_meta = metadata(form['input_series'], cutoff, 'BT0 / '+CHAMPION,
                             accreditation='OPERATIONAL_PREMATCH_INPUTS_NOT_OOS',
                             limitations=['Operational reconstruction; no OOS or calibration accreditation.'])
    goal_meta['statistical_justification'] = 'Existing BT0 formula and original weights; independent Poisson score matrix.'
    groups = [goal_group('FT', (rates.get('local'), rates.get('visitante')), status, goal_meta,
                         None if status == 'IMPLEMENTED' else 'minimum_5_vetted_scores_per_team_required')]
    for family, periods in (('goals', ('1H', '2H')), ('corners', ('FT', '1H')), ('cards', ('FT', '1H'))):
        groups.extend(advanced_group(index, target, cutoff, family, period, card_policy) for period in periods)
    warnings = list(form['warnings'])
    if fixture['kickoff'] is None:
        warnings.append('Kickoff timezone/lineage unavailable; display time is unverified and no kickoff is inferred.')
    for group in groups:
        if group['status'] in ('BLOCKED', 'INSUFFICIENT_DATA', 'NOT_COVERED'):
            warnings.append(group['family']+'/'+group['period']+': '+str(group['reason']))
    synthetic = fixture.get('synthetic_test_only') is True or any(
        'synthetic' in c.evidence.evidence_quality.casefold() for cs in index.by_key.values() for c in cs)
    if synthetic:
        warnings.append('SYNTHETIC_TEST_ONLY: these inputs are test fixtures, never real evidence.')
    cached = None
    cache_path = Path(history_root)/fixture['provider_fixture_id']/'lambda_comparison.json'
    if fixture['provider'] == 'flashscore' and cache_path.exists():
        cache, source = read_json(cache_path)
        if cache.get('match_id') != fixture['provider_fixture_id']:
            raise ValueError('cached_comparison_identity_conflict')
        cached = dict(model=CHAMPION, values=cache.get('metodos', {}).get(CHAMPION),
                      status='BLOCKED', reason='cached_predictions_not_accredited_for_requested_cutoff')
        sources.append(source)
    half1, half2 = groups[1], groups[2]
    conclusions = []
    if groups[0]['expected_total'] is not None:
        conclusions.append(f"BT0 estima λ total={groups[0]['expected_total']:.3f}; es una expectativa del modelo, con incertidumbre.")
        scores = groups[0]['likely_scores'][:3]
        conclusions.append('Marcadores con mayor masa: '+', '.join(
            f"{s['marcador']} ({s['probabilidad']:.1%})" for s in scores)+'.')
    for side in ('home', 'away'):
        stats = form['observed'].get(side, {})
        recent, longer = stats.get('l5', {}), stats.get('l20', {})
        if recent.get('promedio_gf') is not None and longer.get('promedio_gf') is not None:
            conclusions.append(f"{fixture[side]['name']}: GF/partido L5={recent['promedio_gf']:.2f} "
                               f"frente a L20 observado={longer['promedio_gf']:.2f} (n={longer['pj']}); comparación descriptiva.")
    conclusions.extend(f"{g['family']} {g['period']}: {g['status']}" for g in groups)
    code_paths = sorted(Path(__file__).parent.glob('*.py')) + [ROOT/'analysis/poisson.py', ROOT/'analysis/compare_lambda.py']
    implementation_sha256 = hashlib.sha256(dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in code_paths}).encode()).hexdigest()
    report = dict(schema_version=VERSION, implementation_sha256=implementation_sha256,
        fixture=fixture, generated_at=generated_at,
        cutoff=cutoff, decision='NO_BET', synthetic_test_only=synthetic, oos_eligible=False,
        analysis_mode='OPERATIONAL_RECONSTRUCTION_NOT_OOS', champion='BT0 / '+CHAMPION,
        champion_formula_sha256=formula_hash, form=form, markets=groups,
        observed_statistics=observed_advanced(index, target, cutoff),
        half_comparison=dict(first_half=half1['expected_total'], second_half=half2['expected_total'],
            second_minus_first=(half2['expected_total']-half1['expected_total'])
                if all(g['expected_total'] is not None for g in (half1, half2)) else None),
        model_comparison=[dict(model=k, values=v, status='IMPLEMENTED' if k == CHAMPION else 'EXPERIMENTAL',
                               reason='same_vetted_inputs_no_promotion') for k, v in methods.items()] + ([cached] if cached else []),
        sources=form['sources']+sources+reference['sources'], capture=capture_manifest,
        source_policy=source_policy(fixture['provider']), flashscore_reference=reference,
        quality=dict(states=dict(Counter(g['status'] for g in groups)),
                     accreditation='OPERATIONAL_ONLY', calibrated=False, warnings=warnings),
        conclusions=conclusions,
        additional_variables=dict(opponent_strength='BLOCKED: opponent histories as-of each adjusted fixture required',
            rest='BLOCKED: complete verified schedule required', injuries='BLOCKED: verified pre-cutoff publication required',
            lineups='BLOCKED: official pre-cutoff lineup lineage required', standings='BLOCKED: historical as-of snapshot required'),
        network_requests=capture_manifest.get('request_count', 0) if capture_manifest else 0)
    from .market_matrix import build
    report['market_matrix'] = build(report)
    report['analysis_id'] = hashlib.sha256(dumps(report).encode()).hexdigest()
    return report
