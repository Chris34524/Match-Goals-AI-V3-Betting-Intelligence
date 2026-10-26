"""Target-driven current odds collection; schema validity is not live authority."""
from dataclasses import asdict
from .contract import VERSION as SCHEMA_VERSION, schema_errors
from .provider import PROVIDER, VERSION, utc, utc_now
from .quota import Budget, estimate, ledger
from .storage import DEFAULT_ROOT, digest, encoded, store_run
from .the_odds_api import TheOddsAPI, ProviderError, authorize, assert_safe_payload, validate_response


def plan(config, targets, budget=Budget(), credits_used_local=0, credits_remaining_provider=None):
    if len({t.internal_match_id for t in targets}) != len(targets):
        raise ValueError('duplicate_target')
    calls = []
    for t in sorted(targets, key=lambda t: (t.priority, t.internal_match_id)):
        if t.sport_key not in config.sports or not set(t.markets) <= set(config.markets):
            raise ValueError('target_outside_allowlist')
        if t.external_event_id is None:
            raise ValueError('external_event_id_required_for_live_plan')
        calls.append({'sport': t.sport_key, 'event_id': t.external_event_id,
                      'markets': list(t.markets), 'internal_match_id': t.internal_match_id,
                      'estimated_cost': estimate(config, t.markets)})
    cost = sum(c['estimated_cost'] for c in calls)
    return {'calls': calls, 'estimated_cost': cost, 'credits_used_local': credits_used_local,
            'credits_remaining_provider': credits_remaining_provider,
            'rejection': budget.check(cost, credits_used_local, credits_remaining_provider)}


def parse(payload, targets, config, reconciliation, observed_at):
    utc(observed_at)
    assert_safe_payload(payload)
    events = validate_response(payload)
    sha = digest(encoded(payload))
    records, audits, rejected = [], [], []
    for event in events:
        if event['sport_key'] not in config.sports:
            continue
        target, audit = reconciliation.reconcile(event, targets)
        audits.append(audit)
        if target is None:
            continue
        for book in event['bookmakers']:
            if config.bookmakers and book['key'] not in config.bookmakers:
                continue
            for market in book['markets']:
                for outcome in market['outcomes']:
                    name, line, selection, mapped = outcome['name'], None, None, None
                    if market['key'] == 'h2h':
                        mapped = '1X2'
                        selection = {event['home_team']: 'home', event['away_team']: 'away', 'Draw': 'draw'}.get(name)
                    elif market['key'] == 'btts':
                        mapped, selection = 'BTTS', {'Yes': 'yes', 'No': 'no'}.get(name)
                    elif market['key'] == 'totals':
                        line = outcome.get('point')
                        mapped = {1.5: 'OVER_1_5', 2.5: 'OVER_2_5', 3.5: 'OVER_3_5'}.get(line) if type(line) in (float, int) else None
                        selection = {'Over': 'over', 'Under': 'under'}.get(name)
                    if mapped not in config.markets or mapped not in target.markets or selection is None:
                        continue
                    prematch = utc(observed_at) < utc(target.kickoff_at) and utc(observed_at) < utc(event['commence_time'])
                    r = dict(internal_match_id=target.internal_match_id, external_match_id=event['id'],
                        competition=target.competition, season=target.season, kickoff_at=target.kickoff_at,
                        timezone='UTC', market=mapped, selection=selection, line=line,
                        bookmaker=book['key'], provider=PROVIDER, decimal_odds=outcome['price'],
                        observed_at=observed_at, source_published_at=market.get('last_update', book.get('last_update')),
                        snapshot_type='current', source=dict(id=event['id'], artifact='raw/response.json', url=None),
                        surface_availability='documented_api', capture_policy='review',
                        provenance=dict(evidence='current V4 capture; provider_last_update=source_published_at', sha256=sha, origin='the_odds_api'),
                        validity=dict(pre_match=prematch), exclusion_reason=None if prematch else 'not_pre_match',
                        temporal_semantics=dict(definition=None, evidence=None), aggregation='individual',
                        population=[], price_state='active', status='review')
                    errors = schema_errors(r, observed_at)
                    if errors or not prematch:
                        rejected.append({'event_id': event['id'], 'bookmaker': book['key'], 'market': mapped,
                                         'selection': selection, 'reasons': list(errors) or ['not_pre_match']})
                    else:
                        records.append(r)
    records.sort(key=lambda r: (r['internal_match_id'], r['bookmaker'], r['market'], r['selection'], r['decimal_odds']))
    return records, audits, rejected


def collect_fixture(payload, targets, config, reconciliation, *, observed_at=None, root=DEFAULT_ROOT):
    observed_at = observed_at or utc_now()
    assert_safe_payload({'config': config.safe(), 'targets': [asdict(t) for t in targets],
                         'reconciliation': asdict(reconciliation)})
    records, audits, rejected = parse(payload, targets, config, reconciliation, observed_at)
    manifest = _manifest(config, targets, reconciliation, observed_at, 'offline_fixture')
    manifest.update(reconciliation=audits, rejected=rejected, credits_estimated=sum(estimate(config, t.markets) for t in targets), credits_actual=0, quota_headers=[])
    return store_run(payload, records, manifest, root)


def _manifest(config, targets, reconciliation, observed_at, mode):
    return dict(schema_version=SCHEMA_VERSION, collector_version=VERSION, provider=PROVIDER,
                config={'provider': config.safe(), 'targets': [asdict(t) for t in targets],
                        'reconciliation': asdict(reconciliation), 'mode': mode},
                observed_at=observed_at, markets=list(config.markets), sports=list(config.sports),
                regions=list(config.regions), mode=mode)


def collect_live(targets, config, reconciliation, *, live=False, budget=Budget(), root=DEFAULT_ROOT, adapter=None):
    authorize(live, config.markets)
    observed_at = utc_now()
    if any(utc(observed_at) >= utc(t.kickoff_at) for t in targets):
        raise ProviderError('target_not_pre_match')
    adapter = adapter or TheOddsAPI(config)
    payloads, headers, records, audits, rejected = [], [], [], [], []
    failure = None
    with ledger(root, observed_at) as (state, reserve, record_headers):
        p = plan(config, targets, budget, state['used'], state['remaining'])
        if p['rejection']:
            raise ProviderError('quota_' + p['rejection'])
        state['cost'] = p['estimated_cost']
        reserve(p['estimated_cost'])
        for call in p['calls']:
            try:
                payload, h = adapter.fetch(call['sport'], call['markets'], event_id=call['event_id'], live=live)
            except ProviderError as exc:
                failure = str(exc)
                headers.append(exc.quota_headers)
                break
            captured_at = utc_now()  # actual capture clock, never scheduled/provider time
            r, a, e = parse(payload, targets, config, reconciliation, captured_at)
            payloads.append(payload); headers.append(h); records.extend(r); audits.extend(a); rejected.extend(e)
        if headers:
            record_headers(headers[-1])
    manifest = _manifest(config, targets, reconciliation, observed_at, 'live_enabled')
    manifest['config']['budget'] = asdict(budget)
    manifest.update(status='failed' if failure else 'executed', failure=failure, reconciliation=audits, rejected=rejected, credits_estimated=p['estimated_cost'],
                    credits_actual=sum(h['x-requests-last'] for h in headers) if all('x-requests-last' in h for h in headers) else None,
                    quota_headers=headers)
    # Each record's raw provenance is its individual event digest; retain these artifacts.
    from .storage import publish, jsonl
    raw = encoded(payloads)
    run_id = digest(encoded({'config': manifest['config'], 'observed_at': observed_at, 'source_sha256': digest(raw)}))
    canonical = jsonl(records)
    manifest.update(run_id=run_id, source_sha256=digest(raw), canonical_sha256=digest(canonical), record_count=len(records))
    files = {'raw/response.json': raw, 'canonical.jsonl': canonical, 'manifest.json': encoded(manifest)}
    for payload in payloads:
        files['raw/' + digest(encoded(payload)) + '.json'] = encoded(payload)
    for r in records:
        r['source']['artifact'] = 'raw/' + r['provenance']['sha256'] + '.json'
    files['canonical.jsonl'] = jsonl(records)
    manifest['canonical_sha256'] = digest(files['canonical.jsonl'])
    files['manifest.json'] = encoded(manifest)
    path = publish(root, run_id, files)
    if failure:
        raise ProviderError('collection_failed_audit_persisted')
    return path
