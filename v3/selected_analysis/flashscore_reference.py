"""Flashscore Mexico reference coverage and read-only legacy observations.

Reuses the existing corpus auditor, xG identity reconciler and stored scrapers'
outputs. No browser, HTTP, new extractor, grant override or model input adapter.
"""
from pathlib import Path
import re
from statistics import mean

from v3.features.audit import audit_sources
from v3.features.xg_adapter import reconcile
from .evidence import ROOT, read_json
from .fixtures import rows_from_document

PRIMARY = 'https://www.flashscore.com.mx/'
TERMS = PRIMARY+'terms-of-use/'
FAQ = PRIMARY+'faq/data/'
VERSION = 'flashscore-mx-reference-1'


def policy(provider):
    return dict(version=VERSION, primary_reference='flashscore_mx', reference_url=PRIMARY,
                active_provider=provider, automatic_fallback=False,
                complement_mode='EXPLICIT_PROVIDER_SELECTION_ONLY',
                live_flashscore_status='BLOCKED_SOURCE_AUTHORIZATION',
                terms_review_date='2026-11-07', terms_url=TERMS,
                reuse_policy='Existing archives first; no new extraction or source-rights accreditation.')


def coverage(source_root=ROOT/'data/matches'):
    """Field matrix from existing discovery, scraper contracts and corpus auditor."""
    corpus = audit_sources(source_root)
    calendar_path = Path(source_root).parent/'partidos.json'
    calendar = dict(path=str(calendar_path), status='MISSING', rows=None)
    if calendar_path.exists():
        document, calendar_source = read_json(calendar_path)
        items = rows_from_document(document)
        identities = {}
        for row in items:
            mid = row.get('id',row.get('match_id'))
            if mid is not None:
                identities.setdefault(str(mid),set()).add(tuple(str(row.get(k)) for k in ('fecha','local','visitante')))
        calendar = dict(source=calendar_source,status='EXISTING_ARCHIVE',rows=len(items),
            unique_ids=len(identities), conflicting_ids=sorted(mid for mid,variants in identities.items() if len(variants)>1),
            fields_nonnull={key:sum(row.get(key) not in (None,'') for row in items)
                            for key in ('id','fecha','hora','pais','competicion','local','visitante','estado','url')},
            captured_at=None,capture_time_reason='date_label_is_not_a_capture_timestamp')
    catalog, receipt = read_json(ROOT/'docs/v3/flashscore/observed-fields.json')
    existing = {
        'xg': ('scraper/extract_xg.py::extraer_xg_pagina', 'xg_history.json', 'FT_NOT_VERIFIED'),
        'xga': ('scraper/extract_xg.py::perspectiva_equipo', 'xg_history.json', 'FT_NOT_VERIFIED'),
        'final_score': ('scraper/extract_history.py::parsear_fila', 'history.json', 'SCOPE_REQUIRES_VALIDATION'),
        'h2h_results': ('scraper/extract_history.py::extraer_seccion', 'history.json', 'SCOPE_REQUIRES_VALIDATION'),
        **{name: ('scraper/standings.py::extraer_fila', 'standings.json', 'SEASON_SNAPSHOT_NOT_ASOF')
           for name in ('standing_position', 'standing_played', 'standing_wins', 'standing_draws',
                        'standing_losses', 'standing_goals', 'standing_goal_difference', 'standing_points', 'standing_form')},
        **{name: ('scraper/flashscore.py::extraer_partidos', 'partidos.json', 'FIXTURE_METADATA')
           for name in ('fixture_id', 'fixture_date', 'fixture_time', 'country', 'competition', 'home_team', 'away_team', 'fixture_status')},
        'form_l5_l10_l20': ('analysis/enrich_match.py::calcular_ventanas_equipo', 'history.json', 'DERIVED_FROM_VETTED_SCORES'),
        'venue_form': ('v3/features/history_adapter.py::team_history', 'history.json', 'DERIVED_FROM_VETTED_SCORES'),
    }
    fields = list(catalog['fields'])
    fields += [dict(canonical_name=name, period='metadata', status='OBSERVED_LOCAL', evidence_method='existing_scraper_contract')
               for name in existing if name not in {f['canonical_name'] for f in fields}]
    fields += [dict(canonical_name=name, period=period, status='UNKNOWN', evidence_method=None)
               for name,period in (('season_id','metadata'),('stable_team_ids','metadata'),
                                   ('card_second_yellow','event'),('card_direct_red','event'),
                                   ('card_dismissal_id','event'),('capture_timestamp','provenance'),
                                   ('publication_revision_lineage','provenance'))]
    public_mx = {'xg','shots_on_target','possession','corners','yellow_cards','red_cards','fouls',
                 'final_score','fixture_date','fixture_time','competition','home_team','away_team','fixture_status'}
    rows = []
    for field in sorted(fields, key=lambda f:f['canonical_name']):
        name = field['canonical_name']
        extractor, artifact, period_quality = existing.get(name, (None,None,'NOT_VERIFIED'))
        count = corpus['artifact_counts'].get('present:'+artifact) if artifact else None
        if artifact == 'partidos.json':
            count = int(calendar['status']=='EXISTING_ARCHIVE')
        rows.append(dict(field=name, requested_period=field['period'],
            public_visibility=('PUBLIC_MX_DOCUMENTED_VARIABLE_COVERAGE' if name in public_mx else
                               'PREVIOUS_PUBLIC_INDEX_ONLY' if field['status']=='OBSERVED' else field['status']),
            prior_evidence_method=field.get('evidence_method'), evidence_ids=field.get('evidence_ids',[]),
            legacy_extraction='IMPLEMENTED' if extractor else 'NOT_IMPLEMENTED',
            reusable_component=extractor, existing_artifact=artifact, period_quality=period_quality,
            corpus_artifact_presence=count, coverage_unit='artifact_presence_not_numeric_or_model_eligibility',
            captured_at=None, capture_time_reason='not_recorded_by_legacy_contract',
            live_acquisition='BLOCKED_SOURCE_AUTHORIZATION',
            next_step=('Reuse archive and validate identity/scope/cutoff; never infer capture time.' if extractor else
                       'Validate field and active period on permitted evidence; extend existing lane only after authorization.'),
            predictive_readiness=('DATE_FILTERED_OPERATIONAL_ONLY' if name in ('final_score','h2h_results','form_l5_l10_l20','venue_form')
                                  else 'BLOCKED_ASOF_OR_SCOPE' if extractor else 'BLOCKED_NO_EXTRACTOR_OR_DATA')))
    return dict(version=VERSION, source_policy=policy('flashscore'), corpus=corpus,calendar=calendar,
                field_catalog_source=receipt, fields=rows,
                current_primary_references=[PRIMARY,TERMS,FAQ],
                terms_assessment='No express acquisition grant evidenced; existing V3 gate remains blocked.',
                network_requests=0, limitations=[
                    'Public product description and previous indexed evidence do not prove per-fixture coverage.',
                    'No match/statistics pages were recaptured; no full live coverage percentage is claimed.',
                    'Legacy xG has numeric values but no verified selected period, capture time or historical revisions.',
                    'The existing negative xG cache persists unavailable states without a recorded TTL or capture time.',
                    'Market probabilities are model outputs, not observed Flashscore statistics.'])


def observation(field, side, value, source, *, window, n=None, denominator=None,
                samples=(), reason=None, period=None):
    return dict(field=field, side=side, value=value, window=window,
        observation_status='OBSERVED_UNACCREDITED' if value is not None else 'MISSING',
        predictive_status='BLOCKED', eligible_for_model=False,
        sample_size=n, coverage=n/denominator if n is not None and denominator else None,
        coverage_denominator=denominator, period=period, period_verified=False,
        provider='flashscore', reference_url=PRIMARY, source=source,
        captured_at=None, capture_time_reason='not_recorded_by_legacy_scraper',
        accreditation='EXISTING_ARCHIVE_ONLY_NOT_PREMATCH_ACCREDITED',
        reason=reason or ('period_capture_and_publication_lineage_unverified' if value is not None else 'absent_or_ineligible_observation'),
        contributing=list(samples))


def archive(path):
    """A broken optional reference must not destroy an otherwise valid forecast."""
    try:
        value, receipt = read_json(path)
        if not isinstance(value,dict):
            raise ValueError('invalid_reference_shape')
        return value, receipt
    except (OSError,ValueError,UnicodeError) as error:
        if isinstance(error,ValueError) and str(error) in ('credential_in_evidence_forbidden','symlink_evidence_forbidden'):
            raise
        return {}, dict(path=str(path),sha256=None,captured_at=None,
                        read_error='invalid_or_unavailable_reference')


def reference(fixture, history_root, form):
    """Observed xG and standings stay separate from all eligible model inputs."""
    result = dict(source_policy=policy(fixture['provider']), status='NOT_SELECTED', observations=[],
                  sources=[], exclusions={}, network_requests=0)
    if fixture['provider'] != 'flashscore':
        return result
    result['status'] = 'EXISTING_ARCHIVE_REVIEW'
    directory = Path(history_root)/fixture['provider_fixture_id']
    hp, xp, sp = (directory/name for name in ('history.json','xg_history.json','standings.json'))
    history = archive(hp)[0] if hp.exists() else {}
    xg, xg_source = archive(xp) if xp.exists() else ({},None)
    if xg_source:
        result['sources'].append(xg_source)
    cache = {}
    for side in ('local','visitante'):
        block = xg.get(side,{})
        for row in block.get('partidos',[]) if isinstance(block,dict) else []:
            sid = row.get('match_id') if isinstance(row,dict) else None
            if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',sid):
                continue
            path = Path(history_root).parent/'xg_cache'/(sid+'.json')
            if sid not in cache and path.exists():
                cache[sid], receipt = archive(path)
                result['sources'].append(receipt)
    # Never supply manufactured attestations to make the predictive gate pass.
    _, reconciled = reconcile(history,xg,cache,fixture['provider_fixture_id'])
    for side, raw_side in (('home','local'),('away','visitante')):
        checked = reconciled[side]
        result['exclusions'][side] = checked['exclusions']
        block = xg.get(raw_side,{})
        raw_rows = block.get('partidos',[]) if isinstance(block,dict) else []
        by_id = {r.get('match_id'):r for r in raw_rows if isinstance(r,dict) and isinstance(r.get('match_id'),str)}
        # These rows are display-only, not accepted by the reconciler for prediction.
        identities_valid = {r['match_id'] for r in checked['exclusions']
                            if set(r['reasons']) == {'unverified_pre_target_xg_lineage'}}
        for window in (5,10):
            selected = form['samples'].get(side,[])[:window]
            displayed = [by_id[s['match_id']] for s in selected
                         if s['match_id'] in identities_valid and by_id[s['match_id']].get('xg_disponible') is True]
            samples = [dict(match_id=r['match_id'], date=r['fecha'], source_url=r.get('url'),
                            xgf=r['xgf'],xga=r['xga'],period=None,captured_at=None) for r in displayed]
            for field,key in (('xg','xgf'),('xga','xga')):
                result['observations'].append(observation(field,side,
                    mean(r[key] for r in displayed) if displayed else None,xg_source,
                    window=f'L{window}',n=len(displayed),denominator=len(selected),samples=samples,
                    reason=checked['reason']))
    standings, source = archive(sp) if sp.exists() else ({},None)
    if source:
        result['sources'].append(source)
    match = standings.get('partido',{})
    if not isinstance(match,dict):
        match = {}
    identity_ok = (match.get('id') == fixture['provider_fixture_id'] and
                   match.get('local') == fixture['home']['name'] and match.get('visitante') == fixture['away']['name'])
    for side, raw_side in (('home','local'),('away','visitante')):
        block = standings.get(raw_side)
        valid = identity_ok and isinstance(block,dict) and block.get('equipo') == fixture[side]['name']
        played = block.get('pj') if valid and type(block.get('pj')) is int and block['pj']>=0 else None
        for field in ('posicion','pj','ganados','empatados','perdidos','gf','gc','dg','puntos','forma'):
            value = block.get(field) if valid else None
            if field != 'forma' and value is not None and (type(value) is not int or (field!='dg' and value<0)):
                value = None
            if field == 'forma' and value is not None and (not isinstance(value,list) or any(v not in ('G','E','P') for v in value)):
                value = None
            result['observations'].append(observation('standings_'+field,side,value,source,
                window='SEASON_SNAPSHOT',n=played,
                reason='snapshot_publication_and_capture_time_unverified' if valid else 'missing_or_conflicting_standings_snapshot'))
    return result
